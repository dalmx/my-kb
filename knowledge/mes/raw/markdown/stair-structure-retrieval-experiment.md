---
category: 部署运维
module: 通用
status: active
tags:
- STAIR
- 结构化检索
- RAG实验
- 章节粗索引
- h3加权
- 负结果回滚
- A/B评测
- get_outline
- 目录兜底
- 标题路径
- benchmark
title: STAIR 结构化检索实验（标题路径输出 + get_outline 兜底 + 章节索引负结果）
updated: '2026-09-08'
---

# STAIR 结构化检索实验（标题路径输出 + get_outline 兜底 + 章节索引负结果）

> 借鉴 IBM STAIR 论文（arXiv:2609.03874，"目录=寻址方案"）对 my-kb 检索链路做的三档结构化改造实录：两档落地生效（检索结果展示 h1>h2>h3 完整标题路径、get_outline 文档目录展开兜底工具），一档 A/B 实验负结果回滚（h3 规则加权与 H2 章节级粗索引均降 MRR，基础设施 dormant 留档并附重启试验配方）。

## 一、背景与对 STAIR 的取舍判断

STAIR（IBM Research，2026-09-03，arXiv:2609.03874）核心是把文档目录（ToC）当作生成式检索（DSI 路线）的寻址方案——模型参数直接记住"答案在第几章"，Recall@1 82.6% 超 BM25/DPR。

对 my-kb 的适用性判断（2026-09-08 定论）：
- **不照搬主路线**：DSI 需要按语料快照微调，my-kb 是活库（天天 append/重建索引），每次更新都要重训，不成立；且 82.6% 是"书内定位章节"任务，与本库 MRR@10 文件级评测不可比。
- **可借鉴方向**：本库此前"结构只用于切分、检索没用透"——h1/h2/h3 写进了 chunk metadata，但规则加权只消费 h1/h2、输出只展示 h2。三档改造按成本递进。

## 二、落地生效：零成本与低成本两档

### 2.1 检索结果展示完整标题路径（零成本）

retriever.py `_format_results` 原来只展示 h2，改为 `h1 > h2 > h3` 完整路径（空层级跳过；仅 h1 不展示避免与标题重复）。LLM 客户端拿到的"地址"精确到小节，引用定位更准。benchmark 验证：排序零扰动（评测只读 top_hits metadata，格式文本不参与打分）。

### 2.2 get_outline 文档目录展开工具（低成本兜底）

STAIR"目录寻址"的朴素落地——低置信兜底链路升级为 coarse-to-fine：
- **原链路**：get_categories → list_sources（只到文件名粒度）→ 反写查询
- **新链路**：list_sources 扫文件名 → 对题文件 `get_outline(source)` 展开章节树 → 按对题章节标题反写查询再检索，或 get_source 读全文直取该节
- 实现：graph_tools.py `build_outline()` 直接读 raw markdown 原文（正则抽 #/##/###，跳过代码围栏内伪标题），输出 frontmatter 概要 + 摘要 + 标题树 + 使用提示；server.py 注册 MCP 工具，search_knowledge(_multi) 工具描述的兜底第 3 步已同步更新。
- **注意：新 MCP 工具需重启 ZCode 才可见**（工具清单在连接时拉取）。

## 三、实验档负结果：h3 加权与 H2 章节粗索引（2026-09-08 A/B）

基准：46 条评测集（benchmark_queries.json v1），基线 MRR@10=0.9457 / Top1=0.913 / Recall@10=0.9891 / 延迟 245ms。报告：F:/rag/reports/benchmark_*_stair-*.json/md。

| 配置 | MRR@10 | Top1 | 延迟 | 结论 |
|---|---|---|---|---|
| 基线（flags 全关） | 0.9457 | 0.913 | 245ms | 锚点 |
| 新代码 flags 全关（stair-off） | 0.9457 | 0.913 | 248ms | ✅ 46/46 全等，回归门通过 |
| + h3 规则加权 0.08（stair-h3） | 0.9428 | 0.913 | 252ms | ❌ 负，回滚 |
| + sections 章节粗索引 BOOST 0.08（stair-sec） | 0.9337 | 0.8913 | 299ms | ❌ 负，回滚 |

### 3.1 h3 加权负因

h3 小节标题多为"2.1 xxx"式泛化词，query 分词命中常抬升不相关文档（#14 字段中文含义查询把台账文档挤出 top5）。23/46 查询重排，净效应微负。

### 3.2 sections 章节粗索引负因（幅度错配，机制未必错）

分维度数据打脸假设：**理论受益方 cross 维度反而 1.0→0.9286**，colloquial 0.8→0.795。
根因：SECTION_BOOST=0.08 远大于 RRF 基础分（单通道 1/(60+rank)≈0.016），节文本一次向量命中就能把整节无关文档抬到正确文档之上（#44"慢查询排查优化"被 semis 日报复制文档压制）。
教训：**在 RRF 融合分上叠加固定幅度规则时，幅度必须校准到基础分同量级**——0.08 是按 tags 规则拍的，但 tags 规则减的是"已经很强的语义命中"，错不在规则在量纲。

## 四、dormant 基础设施与重启试验配方

负结果回滚但基础设施全保留（flags 关闭时零开销，复刻 CHUNK_CONTEXT_PREFIX 处置方式）：
- model_service /vector_query|/vector_get|/vector_write 支持可选 `collection` 字段（白名单 main|sections），sections 用 `<kb>_sections` 命名 collection 同一 persist 目录
- section_index.py：`--rebuild` 全量 / `--stats` 统计；写入侧挂钩（index_file 后增量重建、delete_source/purge 同步清理，均 SECTION_INDEX_ENABLED 门控）
- 2272 节索引已建好留档（247 文件）

重启试验配方（若未来再试）：
1. `python section_index.py --rebuild`（关闭期间写入的文档不产 section，必须先全量刷）
2. SECTION_BOOST 校准到 RRF 量级再试：**≤0.02**（只破平局、不压制语义分），或改为乘性衰减（δ × 节排名衰减）
3. 重启 model_service 使服务端新代码生效 → benchmark A/B 定去留

## 五、关联

- 前例负优化回滚：CHUNK_CONTEXT_PREFIX（2026-09-04，MRR 0.9457→0.8301，见 rag-kb-mcp-build-guide.md）
- 本库结构利用全景：MarkdownHeader 两阶段切分（结构进切分与 metadata）→ 本次补齐输出侧与兜底侧 → 排序侧两试皆负，"结构当排序信号"在本库点查场景证伪、在寻址/展示场景成立

---

## 六、CC 群审查与当日加固（2026-09-08）

群模式拉 CC（reviewer 旗舰档）审查本轮 9 文件改动：**通过（0 阻断 / 4 建议级）**，报告 `pi-handoff/report-20260908-stair-review.md`。建议级当日全修 + 回归全等：

- P1 写入侧闭环缺口：merge_sources / move_source 不清旧 source 的 sections、rebuild_all 清不掉孤儿——已补三处清理（均 flag 门控零开销）；
- P2 `_delete_sections` 吞错后仍 add，节数变少时 uuid5 尾部残留——改为失败返回 -1 且调用方跳过 add；
- P3 ENABLE_HYBRID_SEARCH=False 降级路径下 sections 信号静默失效——抽 `_query_section_keys` 两条召回路径共用；
- P4 build_outline 把缩进代码块内 `# 注释` 误认标题——改匹配原始行、限 ≤3 空格缩进（ATX 规范）。

审查环境经验（CC 自记备忘）：readonly 审查档 F: 盘只放行只读工具、文件写入全拦且中文用户名路径在 PowerShell 校验层被编码损坏——审查报告由会话回复交付、ZCode 代存；运行类验证列待代跑清单交 ZCode 终审执行。