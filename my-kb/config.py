#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""配置常量与全局状态"""

import os
import re
from pathlib import Path

# 抑制警告和日志
import warnings
import logging
warnings.filterwarnings("ignore")
logging.getLogger().setLevel(logging.CRITICAL)

# 国内镜像加速
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

# 路径配置
KB_ROOT = Path(__file__).resolve().parent.parent.parent / "knowledge"

# 知识库配置（2026-08-23 起单库制：原 KL001-my-knowledge + mes-common + quality 三库合并为 mes，
# 旧目录留档于 knowledge/ 下。子系统/业务域靠 module、技术/业务靠 category、工厂/项目线靠 factory 过滤）
DEFAULT_KB_ID = "mes"
ALLOWED_KB_IDS = {"mes"}
DEFAULT_SEARCH_KB_IDS = ["mes"]

# 模型配置
# 2026-09-04 代际升级（Qwen3-Embedding-0.6B，1024 维与 bge-large 一致）。
# 回滚（理论上）：改回 BAAI/bge-large-zh-v1.5 + kill model_service + 全量重建索引
# （bge 模型缓存与旧向量备份已于同日升级定案后清理，回滚需从 hf-mirror 重下）
MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"
# 2026-09-04 Step B 试过 Qwen3-Reranker-0.6B 后回滚：负优化（MRR 0.9457→0.9167、
# 延迟 288→1416ms）。根因：其 yes/logit 打分二元极化（相关全 0.99+），46 条评测
# 16 条 top10 精确并列（3 位舍入约 20 条，对照 bge 仅 2 条），排序分辨率坍缩——
# 它是"相关性判定器"非"排序器"，与库内精排场景（候选多相关、需细粒度排序）错配。
# bge-reranker 连续 sigmoid 分数分辨率好。
# 包装类 qwen3_reranker.py 保留（分流加载逻辑无害；Qwen3-Reranker 模型缓存已删，
# 未来重启试验需从 hf-mirror 重下 ~1.2GB，新版 sentence-transformers 可试原生 CrossEncoder）
RERANKER_MODEL = "BAAI/bge-reranker-base"

# 元数据默认值
DEFAULT_CATEGORY = "未分类"
DEFAULT_MODULE = "通用"
DEFAULT_FACTORY = "通用"

# factory（工厂/项目线）字段说明：
# 业务文档必填（标明业务规则所属项目线，不同厂业务不同）；技术文档缺省=通用（技术跨厂统一）。
# 取值开放枚举（示例：通用 / 工厂A / 工厂B / 产品线C …），按自己业务线自定义即可
# 校验只约束格式（非空字符串），不锁枚举。

# 文档格式校验配置
# category 命名规则：二段式（技术-XXX / 业务-XXX）或 部署运维 / 未分类
# 不限制具体值，允许随时新增分类，只约束格式防止拼写错误
CATEGORY_PATTERN = re.compile(r'^(技术|业务)-.+$|^(部署运维|未分类)$')
# 现有分类参考（仅供 AI 写文档时参考，不强制约束）
KNOWN_CATEGORIES = {
    "技术-.NET", "技术-数据库", "技术-前端", "部署运维",
    "业务-通用", "业务-产出消耗", "业务-质量检测", "业务-工艺附件", "业务-模具",
    "未分类",
}
# frontmatter 必填字段
REQUIRED_FM_FIELDS = ["title", "category", "module", "tags"]
# tags 最少数量
MIN_TAGS_COUNT = 3

# 知识生命周期字段（可选，缺省向后兼容）
# status: active=正常 / deprecated=已废弃（可检索但标注警告）/ archived=已归档（应移出检索库）
VALID_STATUS = {"active", "deprecated", "archived"}
# updated 距今天数超过 STALE_DAYS 视为"信息较旧"（检索结果标注提醒核对）
STALE_DAYS = 365

# 检索置信度阈值（基于 bge-reranker 相关性概率；仅在 reranker 生效时判定）
CONFIDENCE_HIGH = 0.5   # top1 >= 0.5 高置信
CONFIDENCE_LOW = 0.3    # top1 < 0.3 低置信（很可能无相关知识），中间为存疑

# 回收站保留策略（2026-10-09 P0 接线）：同一原文件最多保留最近 N 版、超龄（天）清理；
# 删除/覆盖前移入 knowledge/{kb}/raw/trash/，移动失败则中止操作（fail-safe）
TRASH_KEEP_VERSIONS = 3
TRASH_MAX_AGE_DAYS = 30

# 检索缺口日志（Agentic RAG 方向四：低置信检索自动记录，供回顾补文档）
GAP_LOG_ENABLED = True
GAP_LOG_PATH = Path(__file__).resolve().parent / "gap_log.jsonl"
GAP_LOG_DEDUPE_HOURS = 24  # 相同查询文本在窗口期内只记一次（进程内去重）

# 按 source 命中计数（Agentic RAG 方向六：淘汰决策数据源）
# 每次检索的最终返回结果（MMR 之后）记录呈现过哪些文档、次数与最近命中时间；
# 零命中 + 孤岛(get_orphans) + 较旧 = 淘汰候选，淘汰决策始终留人工
HIT_STATS_ENABLED = True
HIT_STATS_PATH = Path(__file__).resolve().parent / "hit_counts.json"

# 分块参数（技术文档一节约 1500 字符，含标题+代码+说明的完整知识点）
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 300

# Contextual Retrieval 弱化版（2026-09-04 试过即回滚：负优化，MRR 0.9457→0.8301、
# Top1 0.913→0.739）：文档级统一前缀（title+摘要对每个块相同）= 给全部向量加恒定
# 偏置，块间区分度被压向文档均值；且 rerank 输入按 1000 字符截断，前缀挤占正文。
# Anthropic 方案的精髓是 chunk 特异上下文（LLM 生成"这个块讲什么"），零 LLM 版
# 做不出特异性。代码与开关保留（preprocessing.extract_summary / process_document
# 第 4 步），重启试验需走完整版（写入侧 AI 生成章节级前缀）并解决 rerank 截断
CHUNK_CONTEXT_PREFIX = False

# ============ STAIR 结构化检索实验（2026-09-08，借鉴 IBM STAIR arXiv:2609.03874
# "目录=寻址方案"思想：文档结构不只用于切分，也用于寻址/排序）============
# 两项均 A/B 门控（benchmark_eval.py 46 条），负结果回 False 留 dormant 代码 + 注释，
# 处置方式复刻 CHUNK_CONTEXT_PREFIX 前例。flags 从 False 翻 True 前，sections
# 索引必须先 python section_index.py --rebuild 全量重建（关闭期间写入的文档不产 section）

# 3a. 规则重排 h3 加权：h3 元数据此前写入 chroma 但检索全链路无人消费
# 2026-09-08 A/B 负结果（46 条）：MRR 0.9457→0.9428、23/46 重排——h3 小节标题多为
# "2.1 xxx"式泛化词，query 词命中常抬升不相关文档（如 #14 台账查询被挤出 top5）。
# 回滚关闭，代码保留
RULE_H3_ENABLED = False
RULE_H3_WEIGHT = 0.08    # 介于 h2(0.10) 与 tags(0.08) 之间

# 3b. H2 章节级粗索引（sections collection）：每 (source,h1,h2) 节一条粗粒度索引，
# 检索时同 where 查 sections top-K，命中节旗下 chunk 在规则重排层获固定加成——
# 把"整节强相关"的结构信号喂给排序，对症概览类/跨章节问题（cross/colloquial 维度）
# 2026-09-08 A/B 负结果（46 条，报告 stair-sec）：MRR 0.9457→0.9337、Top1 0.913→0.8913、
# 延迟 248→299ms；分维度 cross 1.0→0.9286（假设受益方反而受损）。归因=幅度错配：
# BOOST 0.08 远大于 RRF 基础分（单通道 ~0.016），节文本一次向量命中即把整节无关文档
# 抬过正确文档（#44 慢查询被 semis 日报复制文档压制）。回滚关闭；基础设施保留
# （collection 端点/section_index.py/写入侧挂钩，flag 关闭时零开销），2272 节索引
# 留档。重启试验：先 python section_index.py --rebuild，并把 BOOST 校准到 RRF 量级
# （≤0.02，只破平局不压制语义分）再 A/B
SECTION_INDEX_ENABLED = False
SECTION_TOP_K = 6        # 查 sections 取前 K 个节
SECTION_BOOST = 0.08     # 命中节旗下 chunk 的规则加分（与 tags 同档；P1-1 方向统一后为加成）

# 混合检索配置（向量 + BM25 关键词召回，RRF 融合）
ENABLE_HYBRID_SEARCH = True
BM25_POOL_K = 20       # BM25 候选池大小
RRF_K = 60             # RRF 融合常数（标准值 60）

# 精排池大小（进入 cross-encoder 的候选条数）
# 2026-08-23 A/B 定案 10→30（同语料 46 条）：HitRate 0.9348→0.9783、Top1 0.7609→0.8261、
# 假❌低置信 2条→0（#27/#37 正确文档强分块被挤出10名额致 reranker 低分）；
# 代价 mean 延迟 164→453ms（CrossEncoder 单批 32，30 对仍一次 forward）。
# #14/#23 两条 MISS 亦被救回：黄金在召回内、融合排名落在 11-30 名。
RERANK_POOL_K = 30

# 共享模型服务（单实例加载 embedding+reranker，所有 my-kb 会话进程复用；
# 打开 ZCode 时由 SessionStart hook 预热拉起，空闲自动退出释放显存）
MODEL_SERVICE_HOST = "127.0.0.1"          # 只监听本机
MODEL_SERVICE_PORT = 18737
# 2026-08-27 1800→7200：空闲自杀后重连首个调用撞上"重拉模型+冷启动"，
# 与 Chroma 打开卡顿叠加顶满客户端 180s 超时（见 runtime.log 11:00 事件），放宽减少叠加概率
MODEL_SERVICE_IDLE_EXIT_SEC = 7200        # 无请求 2 小时自动退出
MODEL_SERVICE_LOG = Path(__file__).resolve().parent / "model_service.log"

# 运行日志落盘（utils.log tee）：所有会话 server.py + model_service 共用一个文件，
# 毫秒时间戳 + PID，多进程 O_APPEND 原子追加。量级 ~5KB/天，不做轮转。
# 动机：2026-08-23 两次写库假超时排查时，服务进程 stderr 不落盘导致进程内时间线无法回放
RUNTIME_LOG = Path(__file__).resolve().parent / "runtime.log"

# MMR 多样性配置（同 source 文档去冗余）
# 同一文档最多保留 MMR_MAX_PER_SOURCE 条，保证 top-N 结果覆盖不同文档
# 设为 0 或 1 表示完全去重（同文档只留最佳 1 条）
MMR_MAX_PER_SOURCE = 2

# MarkdownHeaderTextSplitter 配置：按标题层级切分
HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
]

# 设备检测（懒加载：仅共享模型服务进程调用，会话进程不 import torch——
# cu124 版 torch 一 import 就加载 CUDA DLL，单进程白吃 ~800MB）
def detect_device():
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


# ============ 全局状态（运行时可变） ============

_vectorstores = {}   # {kb_id: Chroma 实例}，按需懒加载
_embeddings = None   # 嵌入模型全局单例（多库共用同一模型）
_reranker = None     # cross-encoder 重排模型全局单例
_bm25_retrievers = {}  # {kb_id: BM25Retriever 实例}，按需懒加载（内存索引）
_async_tasks = {}    # {task_key: asyncio.Task}，后台异步任务追踪
_info_cache = {}     # {kb_id: (timestamp, data)}，get_knowledge_info 缓存
