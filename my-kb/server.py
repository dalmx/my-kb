#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""知识库 MCP Server — 模块化路由入口

逻辑分散到各专业模块：
  config.py         配置常量 + 全局状态
  utils.py          通用工具
  models.py         模型管理（embeddings/reranker/vectorstore）
  preprocessing.py  文档预处理（frontmatter/分块/元数据）
  indexer.py        索引管理
  retriever.py      检索引擎（四层检索 pipeline）
  graph_tools.py    文档图分析（断链/孤岛/引用）
"""

import asyncio
import re
import json
import datetime
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool, TextContent, PaginatedRequestParams, CallToolRequestParams,
    ListToolsResult, CallToolResult,
)

from config import (
    KB_ROOT, DEFAULT_KB_ID, ALLOWED_KB_IDS, DEFAULT_SEARCH_KB_IDS,
    MODEL_NAME, CHUNK_SIZE, CHUNK_OVERLAP, GAP_LOG_PATH, GAP_LOG_ENABLED,
    TRASH_KEEP_VERSIONS, TRASH_MAX_AGE_DAYS,
    _async_tasks, _info_cache,
)
from utils import log, validate_kb_id, is_safe_filename, kb_markdown_dir, file_lock
from models import preload, get_vectorstore, get_reranker, WarmupBusyError
from preprocessing import (
    parse_frontmatter, build_chunk_metadata, infer_title_from_h1, validate_doc_format,
    frontmatter_segment, build_merged_document,
)
from indexer import (
    index_file as _index_file, index_all_files as _index_all_files,
    purge_orphan_sources, sync_rebuild,
)
from retriever import get_retriever
from hit_stats import format_hit_stats
from graph_tools import (
    check_broken_links as _check_broken_links, get_orphans as _get_orphans,
    update_references, scan_md_files, all_kb_md_filenames, get_related_docs,
    build_outline as _build_outline,
)

server = Server("my-kb")


# ============================================================================
# 工具定义（MCP 对外契约 — name/schema/description 不变）
# ============================================================================

async def list_tools():
    return [
        Tool(
            name="search_knowledge",
            description=(
                "搜索知识库，返回相关内容。可按 kb_id/category/module/tags 过滤；不指定 kb_id 时默认检索 mes 库（当前为单库部署，见 config.py ALLOWED_KB_IDS）。四层检索（向量+BM25 混合召回 RRF 融合→规则加权→cross-encoder 精排→MMR 同源去冗余）。\n"
                "使用策略（Agentic RAG）：\n"
                "1) 返回头部有【置信度】判定：✅高(top1≥0.5)直接采用；⚠️中(0.3~0.5)核对内容，必要时改写重试；❌低(<0.3)按其建议重试\n"
                "2) 用户口语/模糊提问命中低/中置信时：把查询改写为 2-5 个变体（口语原句+专有名词+同义词）改用 search_knowledge_multi 重试\n"
                "3) 重试仍❌低时，目录浏览兜底分辨\"没搜到 vs 真缺失\"：get_categories 看分类树 → list_sources 全量扫文件名（清单无盲区，能回答\"库里到底有没有\"）。有对题文件名→get_outline 展开其章节目录，按对题章节标题反写查询再检索一次；确实没有→才是真缺失\n"
                "4) 复杂多跳问题（如'A 报表用了 B 文档的什么方案'）先拆解成子问题分别检索再综合\n"
                "5) 结果行首有 ⚠️已废弃 或 ⏳信息较旧 标记时，注意核对是否已有更新版方案\n"
                "6) 低置信且经目录浏览确认知识缺失时，用 save_markdown 沉淀新文档补全知识库"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索查询（含专有名词效果最佳）"},
                    "n_results": {"type": "integer", "default": 5, "description": "返回结果数量"},
                    "kb_id": {"type": "string", "description": "指定单个知识库；不传则检索默认库 mes（单库部署）"},
                    "category": {"type": "string", "description": "按分类过滤（如 技术-.NET / 技术-数据库 / 业务-通用 / 部署运维）"},
                    "module": {"type": "string", "description": "按模块过滤：技术类=技术栈（Ext.NET/McUI/iBATIS/C#/通用），业务类=子系统（Main/Semi/Curing/Batch/Mould/Quality/通用）"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "按标签过滤（命中任一即可）"},
                    "factory": {"type": "string", "description": "按工厂/项目线过滤（自定义开放枚举，见 config.py 说明）"}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="search_knowledge_multi",
            description=(
                "多查询融合检索（Agentic RAG）。传入多个查询变体（口语原句+专有名词+同义词），"
                "服务端对每个查询独立召回后做跨查询 RRF 融合，再用各自查询配对 reranker 精排。"
                "适用场景：用户用口语/模糊描述时，改写出含专有名词的查询变体一起检索，"
                "跨越'口语→专有名词'的语义鸿沟。比 search_knowledge 单查询召回率更高。\n"
                "使用策略：\n"
                "1) 用户口语提问时优先用本工具：变体=口语原句+专有名词变体（控件/表/存储过程名）+同义词，共 2-5 个\n"
                "2) 返回头部【置信度】❌低时：检查变体是否含正确专有名词，补充同义词变体重试；或放宽 category/module/tags 过滤\n"
                "3) 变体重试仍❌低时：get_categories + list_sources 目录浏览兜底分辨\"没搜到 vs 真缺失\"（文件名全量无盲区）——有对题文件名→get_outline 展开章节目录，按对题章节标题反写查询再检索；确实没有→确认缺失，走 save_markdown 补文档\n"
                "4) 多跳问题拆成子问题分组调用，最后综合各次结果\n"
                "5) 结果行首 ⚠️已废弃 / ⏳信息较旧 标记时注意核对更新版方案"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "queries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "查询变体数组（2-5个）：原始口语查询 + 改写的专有名词查询 + 同义词查询"
                    },
                    "n_results": {"type": "integer", "default": 5, "description": "返回结果数量"},
                    "kb_id": {"type": "string", "description": "指定单个知识库；不传则检索默认库 mes（单库部署）"},
                    "category": {"type": "string", "description": "按分类过滤"},
                    "module": {"type": "string", "description": "按模块过滤"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "按标签过滤"},
                    "factory": {"type": "string", "description": "按工厂/项目线过滤（自定义开放枚举，见 config.py 说明）"}
                },
                "required": ["queries"]
            }
        ),
        Tool(
            name="get_outline",
            description=(
                "展开指定文档的章节目录（h1/h2/h3 标题树 + 摘要），文档结构寻址用。"
                "低置信兜底的 coarse-to-fine：list_sources 找到对题文件名后，"
                "用本工具展开目录定位具体章节，再按章节标题反写查询（含章节专有名词）重新检索，"
                "或 get_source 读全文直取该节。跨所有库定位文件。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "文档文件名（可不含 .md 后缀）"}
                },
                "required": ["source"]
            }
        ),
        Tool(
            name="get_related",
            description=(
                "引用图导航：查询指定文档的关联文档（出链=本文引用的、入链=引用本文的、同模块近邻），"
                "跨所有库检索，同时识别反引号 .md 和 [[wikilink]] 两种引用。\n"
                "使用策略（Agentic RAG 多跳检索）：search_knowledge 命中文档后，"
                "若需要上下游/关联知识（如'A 方案参考的 B 文档'、'同模块还有哪些实现'），"
                "用本工具展开关联文档，再用 get_source 取全文；"
                "标注 ⚠️已废弃 的关联文档注意核对替代方案，⚠️未找到 表示断链。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "文档文件名（可不含 .md 后缀）"}
                },
                "required": ["source"]
            }
        ),
        Tool(
            name="get_search_gaps",
            description=(
                "查看检索缺口日志：低置信（top1<0.3）检索的自动记录。\n"
                "用途（知识库自我改进闭环）：回顾近期检索失败的查询，识别知识缺失，"
                "用 save_markdown 补文档填缺口后，下次同类查询即可命中。"
                "返回最近 N 条 + 重复≥2次的高频缺口查询（优先补）。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 50, "description": "返回最近多少条（上限 500）"}
                }
            }
        ),
        Tool(
            name="report_mismatch",
            description=(
                "调用方误报回写：检索结果标了 ✅高置信（或⚠️中置信）但内容实际不对题时，"
                "把该查询报告进缺口日志（type=mismatch，与 top1<0.3 自动记录同文件同视图）。\n"
                "解决盲区：高置信误报分数高、不触发自动记录，只有读过内容的调用方能发现。\n"
                "报告后继续走既有兜底流程（变体重试/目录浏览），不因已报告而跳过；"
                "同一查询同一会话只报一次。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "当时的检索查询文本"},
                    "reason": {"type": "string", "description": "为什么不对题（一句话，供补文档时参考）"},
                    "top1": {"type": "number", "description": "当时返回的 top1 分数（如 0.69），用于统计误报分数分布"},
                    "source": {"type": "string", "description": "命中的不对题文档文件名（可不含 .md）"}
                },
                "required": ["query", "reason"]
            }
        ),
        Tool(
            name="get_hit_stats",
            description=(
                "查看按 source 命中统计：检索结果呈现过哪些文档、累计次数与最近命中时间，"
                "以及零命中文档清单。\n"
                "用途（知识库淘汰决策数据源）：零命中文档配合 get_orphans 的淘汰候选"
                "（零命中+孤岛+较旧）定位无用文档。计数刚开始时零命中仅供参考，"
                "淘汰决策始终留人工。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "top_limit": {"type": "integer", "default": 20, "description": "高命中 Top N（默认 20）"}
                }
            }
        ),
        Tool(
            name="get_knowledge_info",
            description="获取知识库统计信息（块数/唯一文件数/分类统计，60秒缓存）。可指定 kb_id；不传则汇总默认库。",
            inputSchema={
                "type": "object",
                "properties": {"kb_id": {"type": "string", "description": "指定单个知识库；不传则汇总默认库"}}
            }
        ),
        Tool(
            name="list_sources",
            description="列出知识库中所有数据来源文件。可指定 kb_id；不传则合并默认库。",
            inputSchema={
                "type": "object",
                "properties": {"kb_id": {"type": "string", "description": "指定单个知识库；不传则合并默认库"}}
            }
        ),
        Tool(
            name="save_markdown",
            description=(
                "保存markdown文件到指定知识库的raw/markdown目录中，默认自动索引。"
                "文档必须严格符合知识库格式规范，否则会被拒绝写入。"
                "格式要求（9 条硬校验）：\n"
                "1. 必须有 YAML frontmatter（--- 开头和闭合），含 title/category/module/tags 四个必填字段\n"
                "2. category 必须是二段式命名：技术-XXX / 业务-XXX / 部署运维 / 未分类（如 技术-.NET、业务-模具，可新增分类）\n"
                "3. tags 至少 3 个（行内数组式 [A, B, C]），含关键词+口语同义词\n"
                "4. 正文 H1 标题与 title 完全一致（strip 后比较）\n"
                "5. H1 后两行内有 > 引用摘要（一两句概括，向量分块首块的语义锚点）\n"
                "6. ## 章节标题用中文序号（## 一、## 二、…，首字符为中文数字；全文无 ## 章节的短文不强制）\n"
                "7. 代码开栏围栏必须标注语言（```python / ```sql / ```aspx；闭合行裸 ``` 属正常）\n"
                "8. updated（可选）：YYYY-MM-DD 最后确认有效日期，缺省自动填今天\n"
                "9. status（可选）：active/deprecated/archived（缺省 active；旧方案被新文档取代时标 deprecated 并在正文注明替代文档）"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "文件名（不含路径，需包含.md后缀）"},
                    "content": {"type": "string", "description": "Markdown文件内容（可含首部 YAML frontmatter 写元数据）"},
                    "kb_id": {"type": "string", "default": "mes", "description": "知识库ID"},
                    "category": {"type": "string", "description": "分类（如 技术-.NET / 技术-数据库 / 业务-通用 / 部署运维），缺省读 frontmatter"},
                    "module": {"type": "string", "description": "模块（如 Ext.NET / 功能实现 / 通用 / 部材），缺省读 frontmatter"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "标签列表"},
                    "auto_index": {"type": "boolean", "default": True, "description": "True=保存后自动索引（默认）；False=仅保存不索引"}
                },
                "required": ["filename", "content"]
            }
        ),
        Tool(
            name="delete_source",
            description="删除知识库中指定的来源文件。默认同时删除向量数据库分块和原始文件；keep_file=True 时仅删除向量库索引、保留原始文件。",
            inputSchema={
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "要删除的来源文件名"},
                    "kb_id": {"type": "string", "default": "mes", "description": "知识库ID"},
                    "keep_file": {"type": "boolean", "default": False, "description": "True=仅删除向量库索引保留原始文件；False=同时删除原始文件（默认）"}
                },
                "required": ["source"]
            }
        ),
        Tool(
            name="index_file",
            description="将指定的文件添加到向量数据库中进行索引（先删后加）。元数据通过参数或 frontmatter 提供，分块使用 MarkdownHeader 两阶段切分。",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "要索引的文件名"},
                    "kb_id": {"type": "string", "default": "mes", "description": "知识库ID"},
                    "chunk_size": {"type": "integer", "default": 1500, "description": "文档分块大小，默认1500字符"},
                    "chunk_overlap": {"type": "integer", "default": 300, "description": "分块重叠大小，默认300字符"},
                    "category": {"type": "string", "description": "分类，缺省读 frontmatter"},
                    "module": {"type": "string", "description": "模块，缺省读 frontmatter"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "标签列表"}
                },
                "required": ["filename"]
            }
        ),
        Tool(
            name="index_all_files",
            description="索引知识库raw目录下所有未索引的文件。force=True 时强制重建（先清理脏数据再全量重建）。",
            inputSchema={
                "type": "object",
                "properties": {
                    "kb_id": {"type": "string", "default": "mes", "description": "知识库ID"},
                    "category": {"type": "string", "description": "默认分类"},
                    "module": {"type": "string", "description": "默认模块"},
                    "force": {"type": "boolean", "default": False, "description": "True=强制重建（先删后加）；False=仅索引新文件"}
                }
            }
        ),
        Tool(
            name="reindex_all",
            description="强制重建知识库所有文件的索引（先删后加）。等价于 index_all_files(force=True)。大库可能超时，建议改用 rebuild_index_async。",
            inputSchema={
                "type": "object",
                "properties": {"kb_id": {"type": "string", "default": "mes", "description": "知识库ID"}}
            }
        ),
        Tool(
            name="rebuild_index_async",
            description="异步重建知识库索引（不阻塞、不超时）。立即返回'已开始'，后台分批处理，进度输出到 stderr 日志。",
            inputSchema={
                "type": "object",
                "properties": {
                    "kb_id": {"type": "string", "default": "mes", "description": "知识库ID"},
                    "force": {"type": "boolean", "default": True, "description": "True=强制重建；False=仅索引新文件"}
                }
            }
        ),
        Tool(
            name="move_source",
            description="重命名知识库中的文件，并自动更新所有其他文件中对旧文件名的引用，然后重建索引。",
            inputSchema={
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "旧文件名"},
                    "new_name": {"type": "string", "description": "新文件名"},
                    "kb_id": {"type": "string", "default": "mes", "description": "知识库ID"},
                    "update_references": {"type": "boolean", "default": True, "description": "True=自动更新引用（默认）"},
                    "reindex": {"type": "boolean", "default": True, "description": "True=改名后自动重建索引（默认）"}
                },
                "required": ["source", "new_name"]
            }
        ),
        Tool(
            name="check_broken_links",
            description="检查知识库中的断链（引用了不存在的 .md 文件）。区分跨库引用（正常）和真缺失（需修复）。",
            inputSchema={
                "type": "object",
                "properties": {"kb_id": {"type": "string", "description": "检查指定库；不传则检查所有默认库"}}
            }
        ),
        Tool(
            name="validate_frontmatter",
            description="批量校验知识库文件的 YAML frontmatter 完整性（title/category/module/tags）。可自动修复缺失的 title。",
            inputSchema={
                "type": "object",
                "properties": {
                    "kb_id": {"type": "string", "description": "校验指定库；不传则校验所有默认库"},
                    "fix": {"type": "boolean", "default": False, "description": "True=自动补全缺失的 title；False=仅报告"}
                }
            }
        ),
        Tool(
            name="get_categories",
            description="查看知识库的分类体系结构：category → module → 文件数 的层级统计树。",
            inputSchema={
                "type": "object",
                "properties": {"kb_id": {"type": "string", "description": "查看指定库；不传则汇总所有默认库"}}
            }
        ),
        Tool(
            name="get_orphans",
            description=(
                "查找知识库中的孤岛文档（没有被任何其他文档引用）和枢纽文档（被高频引用≥3次），"
                "并结合检索命中统计列出淘汰候选（孤岛+零命中，信息较旧者优先）。"
                "淘汰候选仅供人工复核，最终删除/归档决策留用户。"
            ),
            inputSchema={
                "type": "object",
                "properties": {"kb_id": {"type": "string", "default": "mes", "description": "知识库ID"}}
            }
        ),
        Tool(
            name="merge_sources",
            description="合并多个文档为一个目标文档：写入合并内容、更新引用、删除旧文件及其索引、索引目标文件。",
            inputSchema={
                "type": "object",
                "properties": {
                    "sources": {"type": "array", "items": {"type": "string"}, "description": "待合并的旧文件名列表"},
                    "target": {"type": "string", "description": "合并后的目标文件名"},
                    "kb_id": {"type": "string", "default": "mes", "description": "知识库ID"},
                    "content": {"type": "string", "description": "合并后的完整内容。不传则按 sources 顺序拼接正文。"}
                },
                "required": ["sources", "target"]
            }
        ),
        Tool(
            name="get_source",
            description="按文件名读取知识库中某篇文档的完整内容（含 frontmatter）。",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "文件名"},
                    "kb_id": {"type": "string", "default": "mes", "description": "知识库ID"}
                },
                "required": ["filename"]
            }
        ),
        Tool(
            name="append_section",
            description=(
                "向已有 markdown 文件追加一节内容（正文末尾、frontmatter 之后）。"
                "保留原 frontmatter；追加后自动重建索引。"
                "追加内容必须是规范的 Markdown 章节（## 中文序号标题 + 正文，代码围栏标语言），"
                "写回前会做格式校验——存量文档的 H1 与 title 不一致、缺摘要两项不拦（追加不应被历史债卡死），"
                "但追加内容自身的章节序号与围栏语言必须合规。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "目标文件名（必须已存在）"},
                    "content": {"type": "string", "description": "要追加的内容（纯正文，不含frontmatter）"},
                    "kb_id": {"type": "string", "default": "mes", "description": "知识库ID"},
                    "separator": {"type": "string", "default": "---", "description": "追加内容与原正文之间的分隔"},
                    "reindex": {"type": "boolean", "default": True, "description": "True=追加后自动重建索引"},
                    "category": {"type": "string", "description": "（可选）同时更新 frontmatter 的 category"},
                    "module": {"type": "string", "description": "（可选）同时更新 frontmatter 的 module"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "（可选）同时更新 frontmatter 的 tags"}
                },
                "required": ["filename", "content"]
            }
        ),
    ]


# ── mcp 2.x 显式注册（替代 1.x @server.list_tools() 装饰器；工具表内容零改动）──
async def _on_list_tools(ctx, params):
    return ListToolsResult(tools=await list_tools())


server.add_request_handler("tools/list", PaginatedRequestParams, _on_list_tools)


# ============================================================================
# 工具路由（call_tool — 委托给各模块）
# ============================================================================

def _trash_file(kb_id, filename):
    """删除/覆盖前把原文件移入回收站（knowledge/{kb}/raw/trash/，时间戳前缀）。

    返回 (ok, info) 元组：ok=False 时调用方必须中止删除/覆盖（fail-safe），
    info 为失败原因或回收落点路径；原文件不存在视为无需回收（ok=True, info=""）。
    2026-10-09 P0 接线 + 修正旧 docstring 的"返回 False"错误契约（元组解包使用）。
    """
    import shutil
    src = kb_markdown_dir(kb_id) / filename
    if not src.exists():
        return True, ""
    trash_dir = kb_markdown_dir(kb_id).parent / "trash"
    try:
        trash_dir.mkdir(parents=True, exist_ok=True)
        # 微秒级时间戳：同秒多次覆盖也各占一版（shutil.move 撞名会静默 copy2 覆盖旧回收件）
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S%f")
        dst = trash_dir / ("%s_%s" % (ts, filename))
        shutil.move(str(src), str(dst))
        _trash_retention(trash_dir, filename)
        return True, str(dst)
    except Exception as e:
        return False, str(e)


def _trash_retention(trash_dir, filename,
                     keep=TRASH_KEEP_VERSIONS, max_age_days=TRASH_MAX_AGE_DAYS):
    """回收站保留策略：同一原文件（<时间戳>_<filename> 精确匹配）最多留最近 keep 版，
    超过 max_age_days 的旧件清理。清理失败静默——回收站整理不阻断主流程。

    版本归属用 ^\\d{8}_\\d{6}\\d{0,6}_ 前缀 + 全名精确匹配（deepseek 审查④：朴素
    "*_filename" glob 会把 a_x.md 的回收件误记为 x.md 的版本致误删）。"""
    try:
        import re as _re
        import time as _t
        pat = _re.compile(r"^\d{8}_\d{6}\d{0,6}_" + _re.escape(filename) + r"$")
        entries = sorted((p for p in trash_dir.iterdir() if p.is_file() and pat.match(p.name)),
                         key=lambda p: (p.stat().st_mtime, p.name), reverse=True)
        for p in entries[keep:]:
            p.unlink(missing_ok=True)
        cutoff = _t.time() - max_age_days * 86400
        for p in trash_dir.iterdir():
            try:
                if p.is_file() and p.stat().st_mtime < cutoff:
                    p.unlink(missing_ok=True)
            except OSError:
                pass
    except Exception:
        pass


def _audit(kb_id, tool, detail):
    """写操作审计（2026-09-29）：追加 knowledge/{kb}/changelog.jsonl；失败不阻断主流程。
    2026-09-30 追加自动 git commit：写库即入版本控制，防基线断档。"""
    try:
        rec = {"ts": datetime.datetime.now().isoformat(timespec="seconds"),
               "tool": tool, "kb": kb_id, "detail": detail}
        p = kb_markdown_dir(kb_id).parent / "changelog.jsonl"
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + chr(10))
    except Exception:
        pass
    _git_autocommit(detail)


def _git_autocommit(detail):
    """写操作后自动提交 git 基线（F:/rag）。
    add 范围限 knowledge/（vectordb/log/lock 已被 .gitignore 排除）；
    任何失败静默——多会话并发 commit 撞 index.lock 属预期，下次写库自然补上，
    周五体检周报另有未提交提醒兜底。"""
    try:
        import subprocess
        root = str(KB_ROOT.parent)
        subprocess.run(["git", "add", "-A", "knowledge/"], cwd=root,
                       timeout=30, capture_output=True)
        subprocess.run(["git", "commit", "-m", "kb-write: %s" % detail[:120], "--quiet"],
                       cwd=root, timeout=30, capture_output=True)
    except Exception:
        pass


async def call_tool(name: str, arguments: dict):
    try:
        # ── 检索 ──
        if name == "search_knowledge":
            query = str(arguments.get("query") or "").strip()
            if not query:
                return [TextContent(type="text", text="错误: query 不能为空")]
            retriever = get_retriever()
            result_text, _ = retriever.search(
                query=query,
                n_results=arguments.get("n_results", 5),
                kb_id=arguments.get("kb_id"),
                category=arguments.get("category"),
                module=arguments.get("module"),
                tags=arguments.get("tags"),
                factory=arguments.get("factory"),
            )
            return [TextContent(type="text", text=result_text)]

        # ── 多查询融合检索（Agentic RAG）──
        elif name == "search_knowledge_multi":
            retriever = get_retriever()
            queries = arguments.get("queries", [])
            if not queries or len(queries) < 2:
                return [TextContent(type="text", text="错误: queries 至少需要 2 个查询变体")]
            if len(queries) > 5:
                return [TextContent(type="text", text="错误: queries 变体最多 5 个（描述契约 2-5 个），超出请合并同义变体")]
            result_text, _ = retriever.search_multi(
                queries=queries,
                n_results=arguments.get("n_results", 5),
                kb_id=arguments.get("kb_id"),
                category=arguments.get("category"),
                module=arguments.get("module"),
                tags=arguments.get("tags"),
                factory=arguments.get("factory"),
            )
            return [TextContent(type="text", text=result_text)]

        # ── 文档目录展开（结构寻址兜底层）──
        elif name == "get_outline":
            source = arguments.get("source", "")
            if not source:
                return [TextContent(type="text", text="错误: source 文件名不能为空")]
            if not is_safe_filename(source):
                return [TextContent(type="text", text="错误: 文件名包含非法字符")]
            result_text = _build_outline(source)
            return [TextContent(type="text", text=result_text)]

        # ── 引用图导航（Agentic RAG 多跳检索入口）──
        elif name == "get_related":
            source = arguments.get("source", "")
            if not source:
                return [TextContent(type="text", text="错误: source 文件名不能为空")]
            if not is_safe_filename(source):
                return [TextContent(type="text", text="错误: 文件名包含非法字符")]
            result_text = get_related_docs(source)
            return [TextContent(type="text", text=result_text)]

        # ── 检索缺口日志（Agentic RAG 自我改进闭环）──
        elif name == "get_search_gaps":
            try:
                limit = max(1, min(int(arguments.get("limit", 50)), 500))
            except (TypeError, ValueError):
                limit = 50
            if not GAP_LOG_PATH.exists():
                return [TextContent(type="text", text="缺口日志为空（尚无低置信检索记录）")]
            entries = []
            try:
                with open(GAP_LOG_PATH, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entries.append(json.loads(line))
                        except ValueError:
                            continue
            except Exception as e:
                return [TextContent(type="text", text=f"错误: 读取缺口日志失败 - {e}")]
            if not entries:
                return [TextContent(type="text", text="缺口日志为空（尚无低置信检索记录）")]

            mm_count = sum(1 for e in entries if e.get("type") == "mismatch")
            lines = [
                f"检索缺口日志共 {len(entries)} 条"
                f"（自动低置信 {len(entries) - mm_count} + 🚩误报报告 {mm_count}），"
                f"最近 {min(limit, len(entries))} 条（新→旧）:"
            ]
            for e in reversed(entries[-limit:]):
                qs = " / ".join(e.get("queries", []))
                if e.get("type") == "mismatch":
                    t1 = e.get("top1")
                    t1_s = f"{t1}" if isinstance(t1, (int, float)) else "未记"
                    src_s = f" 命中:{e['source']}" if e.get("source") else ""
                    lines.append(
                        f"  [{e.get('ts', '?')}] 🚩误报报告 top1={t1_s} | {qs}{src_s}"
                        f" | 原因: {e.get('reason', '?')}"
                    )
                else:
                    filters = e.get("filters") or {}
                    f_s = f" 过滤:{filters}" if filters else ""
                    lines.append(f"  [{e.get('ts', '?')}] top1={e.get('top1', '?')} | {qs}{f_s}")

            # 高频缺口查询（重复≥2 次的优先补文档；自动记录与误报报告按查询文本合并计数）
            from collections import Counter
            q_counter = Counter(tuple(e.get("queries", [])) for e in entries)
            repeats = [(list(q), n) for q, n in q_counter.most_common(10) if n >= 2]
            if repeats:
                lines.append("\n高频缺口查询（重复≥2次，优先用 save_markdown 补文档）:")
                for q, n in repeats:
                    lines.append(f"  ×{n}  {' / '.join(q)}")

            lines.append(
                "\n闭环建议: 🚩误报报告=已人工核实不对题，最优先补文档；"
                "高频自动缺口确认属实后补文档；补完后同类查询应命中高置信。"
            )
            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "report_mismatch":
            query = str(arguments.get("query") or "").strip()
            reason = str(arguments.get("reason") or "").strip()
            if not query or not reason:
                return [TextContent(type="text", text="错误: query 与 reason 均必填")]
            if not GAP_LOG_ENABLED:
                return [TextContent(type="text", text="缺口日志已停用（GAP_LOG_ENABLED=False），未记录")]
            entry = {
                "ts": datetime.datetime.now().isoformat(timespec="seconds"),
                "queries": [query],
                "top1": round(float(arguments["top1"]), 4)
                if isinstance(arguments.get("top1"), (int, float)) else None,
                "type": "mismatch",
                "reason": reason,
            }
            src = str(arguments.get("source") or "").strip()
            if src:
                entry["source"] = src
            try:
                with file_lock(GAP_LOG_PATH.with_suffix(".lock"), timeout=10):
                    with open(GAP_LOG_PATH, "a", encoding="utf-8") as f:
                        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                log(f"误报报告已记录: {query[:80]}")
                return [TextContent(
                    type="text",
                    text=f"已记录误报报告（get_search_gaps 可见，标 🚩）: {query[:80]}"
                )]
            except Exception as e:
                return [TextContent(type="text", text=f"错误: 写入缺口日志失败 - {e}")]

        # ── 统计信息 ──
        elif name == "get_knowledge_info":
            import time
            kb_id = arguments.get("kb_id")
            if kb_id:
                validate_kb_id(kb_id)
                target_kbs = [kb_id]
            else:
                target_kbs = [k for k in DEFAULT_SEARCH_KB_IDS if k in ALLOWED_KB_IDS]

            lines = [f"知识库信息（共 {len(target_kbs)} 个库）:", f"- 嵌入模型: {MODEL_NAME}"]
            for cur_kb in target_kbs:
                now = time.time()
                cache_entry = _info_cache.get(cur_kb)
                if cache_entry and (now - cache_entry[0]) < 60:
                    results = cache_entry[1]
                else:
                    vs = get_vectorstore(cur_kb)
                    results = vs.get()
                    _info_cache[cur_kb] = (now, results)

                doc_count = len(results.get("documents", []))
                metadatas = results.get("metadatas", [])
                cat_by_file = {}
                for m in metadatas:
                    if not m:
                        continue
                    src = m.get("source", "")
                    cat = m.get("category", "未分类")
                    if src and src not in cat_by_file:
                        cat_by_file[src] = cat
                cat_counts = {}
                for cat in cat_by_file.values():
                    cat_counts[cat] = cat_counts.get(cat, 0) + 1

                lines.append(f"\n[{cur_kb}]")
                lines.append(f"- 文档块数量: {doc_count}")
                lines.append(f"- 唯一文件数: {len(cat_by_file)}")
                lines.append(f"- 分类统计:")
                for cat in sorted(cat_counts.keys()):
                    lines.append(f"    {cat}: {cat_counts[cat]} 个文件")
            return [TextContent(type="text", text="\n".join(lines))]

        # ── 列出来源 ──
        elif name == "list_sources":
            kb_id = arguments.get("kb_id")
            if kb_id:
                validate_kb_id(kb_id)
                target_kbs = [kb_id]
            else:
                target_kbs = [k for k in DEFAULT_SEARCH_KB_IDS if k in ALLOWED_KB_IDS]
            lines = []
            for cur_kb in target_kbs:
                vs = get_vectorstore(cur_kb)
                results = vs.get()
                sources = {m.get("source") for m in results.get("metadatas", []) if m and "source" in m}
                lines.append(f"[{cur_kb}]")
                if sources:
                    lines.extend(f"- {s}" for s in sorted(sources))
                else:
                    lines.append("(空)")
            return [TextContent(type="text", text="\n".join(lines))]

        # ── 保存 markdown ──
        elif name == "save_markdown":
            filename = arguments.get("filename", "")
            content = arguments.get("content", "")
            kb_id = arguments.get("kb_id", DEFAULT_KB_ID)
            category = arguments.get("category")
            module = arguments.get("module")
            tags = arguments.get("tags")
            auto_index = arguments.get("auto_index", True)
            validate_kb_id(kb_id)

            if not filename:
                return [TextContent(type="text", text="错误: 文件名不能为空")]
            if not filename.endswith(".md"):
                filename = filename + ".md"
            if not is_safe_filename(filename):
                return [TextContent(type="text", text="错误: 文件名包含非法字符")]

            # 格式校验：阻止不规范的文档被写入（防止 frontmatter 缺失/不闭合等问题）
            ok, errors = validate_doc_format(content)
            if not ok:
                err_msg = "文档格式校验未通过，已拒绝写入。请修正以下问题：\n"
                err_msg += "\n".join(f"  - {e}" for e in errors)
                return [TextContent(type="text", text=err_msg)]

            # 自动填充生命周期字段：updated 缺省补今天（已填不覆盖），status 缺省补 active
            # 只在 frontmatter 区段内检测（正文示例里出现的 updated:/status: 不算已填）
            today = datetime.date.today().isoformat()
            fm_block = frontmatter_segment(content)
            if not re.search(r'^updated\s*:', fm_block, re.M):
                content = re.sub(r'^---\s*\n', f'---\nupdated: {today}\n', content, count=1)
            if not re.search(r'^status\s*:', fm_block, re.M):
                content = re.sub(r'^---\s*\n', '---\nstatus: active\n', content, count=1)

            save_dir = kb_markdown_dir(kb_id)
            save_dir.mkdir(parents=True, exist_ok=True)
            save_path = save_dir / filename
            # 覆盖保护（P0 2026-10-09）：旧版先入回收站，失败则中止写入（原文件不动）
            # P2：trash+写盘包进 KB 级 markdown 写锁，防并发写交错
            with file_lock(save_dir.parent / "markdown_write.lock"):
                if save_path.exists():
                    ok_t, info_t = _trash_file(kb_id, filename)
                    if not ok_t:
                        return [TextContent(type="text", text=f"错误: 旧版移入回收站失败，已中止写入（原文件未动）: {info_t}")]
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(content)
            _audit(kb_id, "save_markdown", filename)

            meta_summary = f"category={category or '(读frontmatter)'} module={module or '(读frontmatter)'}"
            result = f"文件已保存: {save_path} | {meta_summary}"

            if auto_index:
                index_args = {"filename": filename, "kb_id": kb_id}
                if category: index_args["category"] = category
                if module: index_args["module"] = module
                if tags: index_args["tags"] = tags
                success, msg = _index_file(**index_args)
                result += "\n" + msg
            return [TextContent(type="text", text=result)]

        # ── 删除来源 ──
        elif name == "delete_source":
            source = arguments.get("source", "")
            kb_id = arguments.get("kb_id", DEFAULT_KB_ID)
            keep_file = arguments.get("keep_file", False)
            validate_kb_id(kb_id)
            vectorstore = get_vectorstore(kb_id)

            if not source:
                return [TextContent(type="text", text="错误: 来源文件名不能为空")]
            if not is_safe_filename(source):
                return [TextContent(type="text", text="错误: 来源文件名包含非法字符")]
            # 与 get_source 行为对齐：少打 .md 后缀不报"不存在"
            if not source.endswith(".md"):
                source = source + ".md"

            # fail-safe 前置（P0 2026-10-09）：需删原文件时先移入回收站，失败则整个删除
            # 中止（向量块与原文件均不动）；成功则文件已在回收站，后续仅清向量块
            trash_dst = ""
            if not keep_file:
                with file_lock(kb_markdown_dir(kb_id).parent / "markdown_write.lock"):
                    ok_t, trash_dst = _trash_file(kb_id, source)
                    if not ok_t:
                        return [TextContent(type="text", text=f"错误: 原文件移入回收站失败，已中止删除（向量块与原文件均未动）: {trash_dst}")]

            deleted_count = 0
            vec_del_failed = False
            try:
                # S7：where 精确拉取，免全量 get（本地/远程同构）
                results = vectorstore.get(where={"source": source})
                ids_to_delete = list(results.get("ids", []))
                if ids_to_delete:
                    vectorstore.delete(ids=ids_to_delete)
                    deleted_count = len(ids_to_delete)
                    log(f"从向量库 {kb_id} 删除 {deleted_count} 个文档块")
            except Exception as e:
                vec_del_failed = True
                log(f"删除向量数据时出错: {e}")

            # 删向量块成功后失效 BM25 索引（bm25_manager 自述契约），
            # 否则已删文档仍可经 BM25 通道召回出脏结果
            if deleted_count > 0:
                try:
                    from bm25_manager import invalidate
                    invalidate(kb_id)
                except Exception:
                    pass
                # sections 章节粗索引同步清理（SECTION_INDEX_ENABLED 门控）
                try:
                    from section_index import delete_source_sections
                    delete_source_sections(kb_id, source)
                except Exception:
                    pass

            file_deleted = bool(trash_dst)
            if deleted_count > 0 or file_deleted:
                _audit(kb_id, "delete_source", source + (" (keep_file)" if keep_file else ""))
                msg = f"删除成功 (库 {kb_id}):\n"
                if deleted_count > 0:
                    msg += f"- 从向量库删除 {deleted_count} 个文档块\n"
                if file_deleted:
                    msg += f"- 原文件已入回收站: {trash_dst}"
                if keep_file and not file_deleted:
                    msg += f"- 原始文件已保留（keep_file=True）"
                if vec_del_failed:
                    msg += "\n⚠️ 向量块清理失败（原文件已入回收站；残留脏块可在下次 index_all_files(force=True) 时由 purge_orphan_sources 清理）"
                return [TextContent(type="text", text=msg)]
            else:
                return [TextContent(type="text", text=f"未找到来源文件: {source}")]

        # ── 索引单个文件 ──
        elif name == "index_file":
            filename = arguments.get("filename", "")
            kb_id = arguments.get("kb_id", DEFAULT_KB_ID)
            success, msg = _index_file(
                filename=filename,
                kb_id=kb_id,
                category=arguments.get("category"),
                module=arguments.get("module"),
                tags=arguments.get("tags"),
            )
            # 直接改文件后经此入口索引的不走写入校验，这里补一道
            # 告警不阻断（存量豁免文档如 glossary 依赖此通道重索引）
            probe_name = filename if filename.endswith(".md") else filename + ".md"
            probe_path = kb_markdown_dir(kb_id) / probe_name
            if probe_path.exists():
                try:
                    content = probe_path.read_text(encoding="utf-8")
                    ok, errors = validate_doc_format(content)
                    if not ok:
                        msg += "\n\n⚠️ 格式告警（已索引，不阻断，建议修复后重新索引）："
                        msg += "".join(f"\n- {e}" for e in errors)
                except Exception as e:
                    log(f"index_file 格式告警检查失败 {probe_name}: {e}")
            _audit(kb_id, "index_file", filename)
            return [TextContent(type="text", text=msg)]

        # ── 批量索引 ──
        elif name == "index_all_files":
            indexed_count, failed, mode_label = _index_all_files(
                kb_id=arguments.get("kb_id", DEFAULT_KB_ID),
                category=arguments.get("category"),
                module=arguments.get("module"),
                force=arguments.get("force", False),
            )
            _audit(arguments.get("kb_id", DEFAULT_KB_ID), "index_all_files",
                   "%s %d force=%s" % (mode_label, indexed_count, arguments.get("force", False)))
            result = f"索引完成:\n- {mode_label}文件数: {indexed_count}\n- 失败: {len(failed)}"
            if failed:
                result += "\n\n失败详情:\n" + "\n".join(f"- {f}" for f in failed)
            return [TextContent(type="text", text=result)]

        # ── 强制重建 ──
        elif name == "reindex_all":
            indexed_count, failed, mode_label = _index_all_files(
                kb_id=arguments.get("kb_id", DEFAULT_KB_ID),
                force=True,
            )
            _audit(arguments.get("kb_id", DEFAULT_KB_ID), "reindex_all", "重建 %d" % indexed_count)
            result = f"重建完成:\n- {mode_label}文件数: {indexed_count}\n- 失败: {len(failed)}"
            if failed:
                result += "\n\n失败详情:\n" + "\n".join(f"- {f}" for f in failed)
            return [TextContent(type="text", text=result)]

        # ── 异步重建 ──
        elif name == "rebuild_index_async":
            kb_id = arguments.get("kb_id", DEFAULT_KB_ID)
            force = arguments.get("force", True)
            validate_kb_id(kb_id)
            task_key = f"_rebuild_{kb_id}"
            if task_key in _async_tasks and not _async_tasks[task_key].done():
                return [TextContent(type="text", text=f"库 {kb_id} 的后台重建任务已在运行中，请等待完成")]

            async def _do_rebuild():
                try:
                    import asyncio
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, sync_rebuild, kb_id, force)
                except Exception as e:
                    log(f"[异步重建] 出错: {e}")
                finally:
                    _async_tasks.pop(task_key, None)

            _async_tasks[task_key] = asyncio.create_task(_do_rebuild())
            _audit(kb_id, "rebuild_index_async", "force=%s" % force)
            return [TextContent(type="text", text=f"异步重建已启动（库 {kb_id}）。后台处理中，进度输出到 stderr 日志。")]

        # ── 重命名 ──
        elif name == "move_source":
            source = arguments.get("source", "")
            new_name = arguments.get("new_name", "")
            kb_id = arguments.get("kb_id", DEFAULT_KB_ID)
            update_refs = arguments.get("update_references", True)
            reindex_flag = arguments.get("reindex", True)
            validate_kb_id(kb_id)

            if not source or not new_name:
                return [TextContent(type="text", text="错误: source 和 new_name 不能为空")]
            if not is_safe_filename(source):
                return [TextContent(type="text", text="错误: 源文件名包含非法字符")]
            if not is_safe_filename(new_name):
                return [TextContent(type="text", text="错误: 新文件名包含非法字符")]
            # 与 get_source 行为对齐：少打 .md 后缀不报"不存在"
            if not source.endswith(".md"):
                source = source + ".md"
            if not new_name.endswith(".md"):
                new_name = new_name + ".md"

            old_path = kb_markdown_dir(kb_id) / source
            new_path = kb_markdown_dir(kb_id) / new_name
            if not old_path.exists():
                return [TextContent(type="text", text=f"错误: 源文件不存在: {source}")]
            # 仅大小写差异的改名（Windows 文件系统大小写不敏感）：目标"已存在"即源文件自身，
            # 不能拦死；直接 rename 在 Windows 上也不生效，走两步改名（先临时名再目标名）
            case_only_rename = (source != new_name and source.lower() == new_name.lower())
            if new_path.exists() and old_path != new_path and not case_only_rename:
                return [TextContent(type="text", text=f"错误: 目标文件已存在: {new_name}")]

            # P2：rename + 引用批量改写包进 markdown 写锁（update_references 自身不加锁，靠调用方持有）
            ref_changed = 0
            with file_lock(kb_markdown_dir(kb_id).parent / "markdown_write.lock"):
                if case_only_rename:
                    tmp_path = kb_markdown_dir(kb_id) / (new_name + ".tmp_rename")
                    old_path.rename(tmp_path)
                    tmp_path.rename(new_path)
                else:
                    old_path.rename(new_path)
                log(f"重命名: {source} → {new_name}")

                if update_refs:
                    ref_changed = update_references(kb_id, source, new_name)

            index_msg = ""
            if reindex_flag:
                # 删旧索引（P1-3：where 精确拉取免全量 get；失败必 log，不再静默）
                try:
                    vs = get_vectorstore(kb_id)
                    results = vs.get(where={"source": source})
                    old_ids = list(results.get("ids", []))
                    if old_ids:
                        vs.delete(ids=old_ids)
                except Exception as e:
                    log(f"move_source 删旧索引失败 {source}（旧名残留可经 index_all_files(force=True) 清理）: {e}")
                # P1（CC 审查 20260908）：旧名 sections 同步清理（新名由 _index_file 挂钩重建；门控）
                try:
                    from section_index import delete_source_sections
                    delete_source_sections(kb_id, source)
                except Exception:
                    pass
                success, index_msg = _index_file(filename=new_name, kb_id=kb_id)

            _audit(kb_id, "move_source", f"{source} -> {new_name}")
            msg = f"重命名成功（库 {kb_id}）:\n- {source} → {new_name}"
            if update_refs:
                msg += f"\n- 更新引用: {ref_changed} 个文件"
            if reindex_flag and index_msg:
                msg += f"\n- {index_msg}"
            return [TextContent(type="text", text=msg)]

        # ── 断链检查 ──
        elif name == "check_broken_links":
            kb_id = arguments.get("kb_id")
            if kb_id:
                validate_kb_id(kb_id)
                target_kbs = [kb_id]
            else:
                target_kbs = [k for k in DEFAULT_SEARCH_KB_IDS if k in ALLOWED_KB_IDS]
            result = _check_broken_links(target_kbs)
            return [TextContent(type="text", text=result)]

        # ── frontmatter 校验 ──
        elif name == "validate_frontmatter":
            kb_id = arguments.get("kb_id")
            fix = arguments.get("fix", False)
            if kb_id:
                validate_kb_id(kb_id)
                target_kbs = [kb_id]
            else:
                target_kbs = [k for k in DEFAULT_SEARCH_KB_IDS if k in ALLOWED_KB_IDS]

            required_fields = ["title", "category", "module", "tags"]
            issues = []
            fixed = []

            for cur_kb in target_kbs:
                for md_file in scan_md_files(cur_kb):
                    try:
                        with open(md_file, "r", encoding="utf-8") as f:
                            content = f.read()
                    except Exception:
                        continue
                    fm, body = parse_frontmatter(content)
                    missing = [fld for fld in required_fields if fld not in fm or not fm[fld]]
                    if missing:
                        issues.append((cur_kb, md_file.name, missing))
                        if fix and "title" in missing:
                            title = infer_title_from_h1(body, md_file.name)
                            if title and title != md_file.name:
                                # F2（P2 r2）：RMW 包 markdown 写锁，锁内重读复核防 TOCTOU
                                with file_lock(md_file.parent.parent / "markdown_write.lock"):
                                    content_now = md_file.read_text(encoding="utf-8")
                                    fm_now, _ = parse_frontmatter(content_now)
                                    if fm_now.get("title"):
                                        continue  # 并发方已补，跳过
                                    if content_now.startswith("---"):
                                        new_content = "---\ntitle: " + title + "\n" + content_now[3:]
                                    else:
                                        new_content = f"---\ntitle: {title}\n---\n\n{content_now}"
                                    with open(md_file, "w", encoding="utf-8") as f:
                                        f.write(new_content)
                                fixed.append((cur_kb, md_file.name, title))
                                _audit(cur_kb, "validate_frontmatter_fix", md_file.name)
                                # P1-3：fix 改盘后立即重索引，防向量库 title 元数据陈旧
                                try:
                                    ok_ix, msg_ix = _index_file(filename=md_file.name, kb_id=cur_kb)
                                    if not ok_ix:
                                        log(f"validate_frontmatter fix 后重索引未成功 {md_file.name}: {msg_ix}")
                                except Exception as e:
                                    log(f"validate_frontmatter fix 后重索引失败 {md_file.name}: {e}")

            total_files = sum(len(scan_md_files(k)) for k in target_kbs)
            lines = [f"Frontmatter 校验报告 (检查 {total_files} 个文件):"]
            if issues:
                lines.append(f"\n缺失字段 ({len(issues)} 个文件):")
                for kb, fn, missing in sorted(issues):
                    lines.append(f"  [{kb}] {fn}: 缺 {', '.join(missing)}")
            else:
                lines.append("\n全部文件的 frontmatter 完整，无缺失。")
            if fix and fixed:
                lines.append(f"\n已自动修复 title ({len(fixed)} 个文件):")
                for kb, fn, title in fixed:
                    lines.append(f"  [{kb}] {fn} → title: {title}")
            return [TextContent(type="text", text="\n".join(lines))]

        # ── 分类体系 ──
        elif name == "get_categories":
            kb_id = arguments.get("kb_id")
            if kb_id:
                validate_kb_id(kb_id)
                target_kbs = [kb_id]
            else:
                target_kbs = [k for k in DEFAULT_SEARCH_KB_IDS if k in ALLOWED_KB_IDS]

            lines = []
            for cur_kb in target_kbs:
                vs = get_vectorstore(cur_kb)
                results = vs.get()
                cat_tree = {}
                for m in results.get("metadatas", []):
                    if not m:
                        continue
                    cat = m.get("category", "未分类")
                    mod = m.get("module", "通用")
                    src = m.get("source", "未知")
                    cat_tree.setdefault(cat, {}).setdefault(mod, set()).add(src)

                total_files = set()
                for sub in cat_tree.values():
                    for srcs in sub.values():
                        total_files |= srcs
                lines.append(f"\n[{cur_kb}] 分类体系 ({len(total_files)} 个唯一文件):")
                for cat in sorted(cat_tree.keys()):
                    cat_files = set()
                    for srcs in cat_tree[cat].values():
                        cat_files |= srcs
                    lines.append(f"  {cat} ({len(cat_files)} 文件)")
                    for mod in sorted(cat_tree[cat].keys()):
                        lines.append(f"    {mod} ({len(cat_tree[cat][mod])} 文件)")
            return [TextContent(type="text", text="\n".join(lines))]

        # ── 命中统计（Agentic RAG 淘汰决策数据源）──
        elif name == "get_hit_stats":
            try:
                top_limit = max(1, min(int(arguments.get("top_limit", 20)), 100))
            except (TypeError, ValueError):
                top_limit = 20
            result_text = format_hit_stats(top_limit)
            return [TextContent(type="text", text=result_text)]

        # ── 孤岛分析 ──
        elif name == "get_orphans":
            kb_id = arguments.get("kb_id", DEFAULT_KB_ID)
            validate_kb_id(kb_id)
            result = _get_orphans(kb_id)
            return [TextContent(type="text", text=result)]

        # ── 合并文档 ──
        elif name == "merge_sources":
            sources = arguments.get("sources", [])
            target = arguments.get("target", "")
            kb_id = arguments.get("kb_id", DEFAULT_KB_ID)
            content = arguments.get("content")
            validate_kb_id(kb_id)

            if not sources or not target:
                return [TextContent(type="text", text="错误: sources 和 target 不能为空")]
            if not is_safe_filename(target):
                return [TextContent(type="text", text="错误: 目标文件名包含非法字符")]
            # P0 2026-10-09：sources 逐项路径安全校验（此前仅 target 校验，越界可删库外文件）
            bad_src = next((s for s in sources if not is_safe_filename(s)), None)
            if bad_src is not None:
                return [TextContent(type="text", text=f"错误: sources 含非法文件名: {bad_src}")]
            if not target.endswith(".md"):
                target = target + ".md"

            md_dir = kb_markdown_dir(kb_id)
            target_path = md_dir / target

            if content:
                final_content = content
            else:
                # 拼接路径：剥各源 frontmatter 与 H1，统一为 target 的 title（消除多 H1），
                # 文首摘要注明合并来源；frontmatter 基底优先 target 既有 fm，缺省用第一个源的 fm
                base_fm = {}
                if target_path.exists():
                    try:
                        with open(target_path, "r", encoding="utf-8") as f:
                            base_fm, _ = parse_frontmatter(f.read())
                    except Exception:
                        base_fm = {}
                merged_from = []
                bodies = []
                for src in sources:
                    if not src.endswith(".md"):
                        src = src + ".md"
                    src_path = md_dir / src
                    if not src_path.exists():
                        continue
                    try:
                        with open(src_path, "r", encoding="utf-8") as f:
                            fm, body = parse_frontmatter(f.read())
                    except Exception as e:
                        return [TextContent(type="text", text=f"错误: 读取源文件失败 {src}: {e}")]
                    if not base_fm:
                        base_fm = dict(fm)
                    merged_from.append(src)
                    bodies.append(body)
                if not bodies:
                    return [TextContent(type="text", text=f"错误: 未找到任何源文件（库 {kb_id}），未执行合并")]
                title = str(base_fm.get("title") or "").strip() or target[:-3]
                final_content = build_merged_document(bodies, title, merged_from, base_fm=base_fm)

            # 合并结果先过格式校验（与 save_markdown 同一门槛），不通过则中止：
            # target 未写入、sources 未删除
            ok, errors = validate_doc_format(final_content)
            dup_errors = [e for e in errors if "序号重复" in e]
            hard_errors = [e for e in errors if "序号重复" not in e]
            if hard_errors:
                err_msg = ("合并内容格式校验未通过，已中止合并（target 未写入、sources 未删除）。"
                           "请改用 content 参数提供修正后的完整内容。问题：\n")
                err_msg += "\n".join(f"  - {e}" for e in hard_errors)
                return [TextContent(type="text", text=err_msg)]
            # F1（P2 r2）：机械拼接同号章节导致的重号不中止合并（常见操作），
            # 成功消息附告警提示后续整理

            # 两阶段（P0 r2 修订，deepseek 审查③）：先回收站化（target 旧版 + 全部旧源），
            # 任一失败即中止——此时 target 未写入、引用未改，已回收的源在回收站可复原；
            # 全部成功后才写 target、改引用、清向量块、重建索引
            md_dir.mkdir(parents=True, exist_ok=True)
            # P2：两阶段 trash + 写 target + 引用更新全程持 markdown 写锁
            with file_lock(md_dir.parent / "markdown_write.lock"):
                if target_path.exists():
                    ok_t, info_t = _trash_file(kb_id, target)
                    if not ok_t:
                        return [TextContent(type="text", text=f"错误: 目标旧版 {target} 移入回收站失败，已中止合并（未做任何更改）: {info_t}")]
                trashed_sources = []
                for src in sources:
                    if not src.endswith(".md"):
                        src = src + ".md"
                    src_path = md_dir / src
                    if src_path.exists() and src_path != target_path:
                        ok_t, info_t = _trash_file(kb_id, src)
                        if not ok_t:
                            return [TextContent(type="text", text=f"错误: 源文件 {src} 移入回收站失败，已中止合并（target 未写入、引用未改，已回收的源可从回收站复原）: {info_t}")]
                        trashed_sources.append(src)

                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(final_content)

                ref_changed = 0
                for src in sources:
                    ref_changed += update_references(kb_id, src, target)

            vs = get_vectorstore(kb_id)
            deleted_files = len(trashed_sources)
            for src in sources:
                if not src.endswith(".md"):
                    src = src + ".md"
                try:
                    results = vs.get(where={"source": src})
                    old_ids = list(results.get("ids", []))
                    if old_ids:
                        vs.delete(ids=old_ids)
                except Exception as e:
                    log(f"merge_sources 删旧索引失败 {src}（残留可经 index_all_files(force=True) 清理）: {e}")
                # P1（CC 审查 20260908）：旧 source 的 sections 粗索引同步清理（门控）
                try:
                    from section_index import delete_source_sections
                    delete_source_sections(kb_id, src)
                except Exception:
                    pass

            # 删了旧块后失效 BM25（后续 _index_file 成功时也会再失效一次，幂等无妨）
            try:
                from bm25_manager import invalidate
                invalidate(kb_id)
            except Exception:
                pass

            success, index_msg = _index_file(filename=target, kb_id=kb_id)
            _audit(kb_id, "merge_sources", f"{len(sources)}源 -> {target}")
            msg = f"合并成功（库 {kb_id}）:\n- 合并 {len(sources)} 个文件 → {target}\n- 删除旧文件: {deleted_files}\n- 更新引用: {ref_changed} 处\n- 格式校验: 通过\n- {index_msg}"
            if dup_errors:
                msg += "\n⚠️ " + "；".join(dup_errors) + "（机械拼接所致，建议后续整理顺延编号）"
            return [TextContent(type="text", text=msg)]

        # ── 读取全文 ──
        elif name == "get_source":
            filename = arguments.get("filename", "")
            kb_id = arguments.get("kb_id", DEFAULT_KB_ID)
            validate_kb_id(kb_id)
            if not filename:
                return [TextContent(type="text", text="错误: 文件名不能为空")]
            if not is_safe_filename(filename):
                return [TextContent(type="text", text="错误: 文件名包含非法字符")]
            if not filename.endswith(".md"):
                filename = filename + ".md"
            file_path = kb_markdown_dir(kb_id) / filename
            if not file_path.exists():
                return [TextContent(type="text", text=f"错误: 文件不存在: {filename}")]
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return [TextContent(type="text", text=content)]

        # ── 追加章节 ──
        elif name == "append_section":
            filename = arguments.get("filename", "")
            content = arguments.get("content", "")
            kb_id = arguments.get("kb_id", DEFAULT_KB_ID)
            separator = arguments.get("separator", "---")
            reindex_flag = arguments.get("reindex", True)
            category = arguments.get("category")
            module = arguments.get("module")
            tags = arguments.get("tags")
            validate_kb_id(kb_id)

            if not filename:
                return [TextContent(type="text", text="错误: 文件名不能为空")]
            if not is_safe_filename(filename):
                return [TextContent(type="text", text="错误: 文件名包含非法字符")]
            file_path = kb_markdown_dir(kb_id) / filename
            if not file_path.exists():
                return [TextContent(type="text", text=f"错误: 文件不存在: {filename}")]

            # P2：读-改-写全程持 markdown 写锁，防并发追加互相覆盖丢更新
            # （手动持锁而非 with 包裹：块体免整体重缩进；try/finally 保证释放）
            _mdlock = file_lock(kb_markdown_dir(kb_id).parent / "markdown_write.lock")
            _mdlock.__enter__()
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    original = f.read()

                # 用 python-frontmatter 剥离 frontmatter（稳健）
                fm, body = parse_frontmatter(original)

                # F5（P2 r2）：追加内容自身的序号不得与既有章节重号
                # （for_append 豁免的是存量债；新引入的重号在此精准拦截）
                from preprocessing import h2_section_numbers
                _clash = set(h2_section_numbers(body)) & set(h2_section_numbers(content))
                if _clash:
                    return [TextContent(type="text", text=f"错误: 追加内容章节序号与既有章节重复: {', '.join(sorted(_clash))}（请顺延编号）")]

                # 可选更新 frontmatter 字段
                fm_changed = False
                if category is not None:
                    fm["category"] = category
                    fm_changed = True
                if module is not None:
                    fm["module"] = module
                    fm_changed = True
                if tags is not None:
                    fm["tags"] = tags
                    fm_changed = True

                # 内容有变更，刷新 updated 为今天（最后确认有效日期）
                fm["updated"] = datetime.date.today().isoformat()

                # 构造新内容
                import frontmatter as fm_lib
                post = fm_lib.Post(body, **fm)
                new_body = post.content
                if separator:
                    new_body = new_body.rstrip() + "\n\n" + separator + "\n\n" + content
                else:
                    new_body = new_body.rstrip() + "\n\n" + content

                # 写回（先序列化成字符串，成功后再写文件，防止异常清空原文件）
                post = fm_lib.Post(new_body, **fm)
                output = fm_lib.dumps(post)

                # 格式校验：for_append=True 豁免存量债（H1==title / H1 后摘要），
                # 追加内容自身的中文序号与围栏语言照常拦
                ok, errors = validate_doc_format(output, for_append=True)
                if not ok:
                    err_msg = f"追加后文档格式校验未通过，已拒绝写回（原文件未改动）。请修正：\n"
                    err_msg += "\n".join(f"  - {e}" for e in errors)
                    return [TextContent(type="text", text=err_msg)]

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(output)
            finally:
                _mdlock.__exit__(None, None, None)
            # F6（P2 r2）：审计（含 git 子进程）挪锁外，缩短持锁时长（与 save/move/merge 口径一致）
            _audit(kb_id, "append_section", "%s +%d chars" % (filename, len(content)))

            index_msg = ""
            if reindex_flag:
                success, index_msg = _index_file(filename=filename, kb_id=kb_id)

            fm_note = ""
            if fm_changed:
                changed = [k for k, v in {"category": category, "module": module, "tags": tags}.items() if v is not None]
                fm_note = f"\n- frontmatter 已更新: {', '.join(changed)}"
            return [TextContent(type="text", text=f"已追加内容（库 {kb_id}）:\n- 文件: {file_path}{fm_note}\n- 分隔: {repr(separator)}\n- {index_msg}")]

        return [TextContent(type="text", text=f"未知工具: {name}")]

    except WarmupBusyError as e:
        # 预热期快速失败：返回可读提示，不刷 traceback（2026-08-31，
        # 替代在 _load_lock 上排队到客户端 180s 超时）
        return [TextContent(type="text", text=f"⏳ {e}")]
    except Exception as e:
        import traceback
        return [TextContent(type="text", text=f"错误: {e}\n{traceback.format_exc()}")]


# ── mcp 2.x 显式注册（替代 1.x @server.call_tool() 装饰器；分发体内容零改动）──
async def _on_call_tool(ctx, params):
    return CallToolResult(content=await call_tool(params.name, params.arguments or {}))


server.add_request_handler("tools/call", CallToolRequestParams, _on_call_tool)


# ============================================================================
# 入口
# ============================================================================

async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    log("MCP Server 启动")
    # 后台线程预加载模型：stdio 立即握手，避免多会话同时启动时
    # 加载耗时超过客户端连接超时（ZCode 默认 30s）。
    # 首次工具调用若模型未就绪，会在懒加载锁上等待（加载只做一次）。
    import threading

    def _preload_guard():
        # preload 线程异常原本只打到 stderr（ZCode 不落盘，等于丢失）——
        # 2026-08-23 实测有会话进程 preload 静默死亡（卡 67MB），故捕获并落 runtime.log
        # 看门狗：preload 若挂死（当晚 py-spy 实测 numpy .pyd 被 AV/DLP 过滤驱动
        # 拦住 DLL 加载、线程冻结在 create_module/LoadLibrary 永不返回），
        # 240s 后全线程栈转储到 runtime.log 并退出进程——ZCode 重拉新进程自愈，
        # 好过进程活着但所有要向量库的调用在 _load_lock 上永远排队
        import faulthandler
        from config import RUNTIME_LOG
        try:
            dump_fh = open(RUNTIME_LOG, "a", encoding="utf-8")
        except Exception:
            dump_fh = None
        try:
            faulthandler.dump_traceback_later(240, exit=True, file=dump_fh)
            preload()
        except Exception:
            import traceback
            log(f"preload 线程异常: {traceback.format_exc(limit=6)}")
        finally:
            faulthandler.cancel_dump_traceback_later()
            if dump_fh is not None:
                dump_fh.close()

    threading.Thread(target=_preload_guard, daemon=True, name="model-preload").start()
    asyncio.run(main())