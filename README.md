# my-kb — 本地优先的个人 RAG 知识库（MCP 服务 + 133 篇 .NET/MES 开发知识）

一套"给 AI 编程助手读的个人知识库"：Markdown 文档 + 混合检索（向量 + BM25 + 精排），以 **MCP server** 形式对外提供服务，接入 ZCode / Claude Code / Cursor 等任何支持 stdio MCP 的客户端后，AI 就能在干活时自动检索你的知识沉淀。

本仓库同时附带一套实战沉淀的 **133 篇 .NET MES 开发知识文档**（Ext.NET 4.7、SQL Server、iBATIS、C#、NPOI、RAG 工程实践等），开箱即可作为你自己的第一个知识库内容。

## 架构与特性

```
knowledge/<kb>/raw/markdown/*.md   ← 知识文档（frontmatter 元数据）
        │
        ▼  indexer（分块 1500/重叠 300 + 章节索引）
┌─────────────────────────────┐
│ Chroma 向量库（Qwen3-Embedding-0.6B fp16）
│ BM25 索引（jieba 分词）        │  ← 混合召回
└───────────┬─────────────────┘
            ▼  RRF 融合 → bge-reranker-base 精排 → MMR 去冗余
    server.py（MCP stdio，23 个工具）
            ▲
            │ HTTP 复用（单实例加载，多会话共享）
    model_service.py（embedding + reranker 共享服务，自动拉起）
```

- **混合检索**：向量语义召回 + BM25 关键词召回，RRF 融合后 reranker 精排，检索质量实测 46 条评测集 **MRR 0.9457**（`my-kb/benchmark_eval.py` 可复现）
- **Agentic RAG 设计**：`search_knowledge_multi` 多查询变体融合（跨越"口语→专有名词"鸿沟）；低置信时目录浏览兜底（`get_categories` + `list_sources` 文件名全量无盲区）；`report_mismatch` 高分误报回写缺口日志；`get_search_gaps` 缺口统一视图驱动补文档
- **知识治理**：frontmatter 校验（`validate_frontmatter`）、章节级大纲（`get_outline`）、文档生命周期（active / deprecated / archived）、删除走 trash 回收站 + changelog.jsonl 审计、命中统计（`get_hit_stats`）支撑淘汰决策、断链检查（`check_broken_links`）
- **共享模型服务**：stdio MCP 每个会话各起一个进程，model_service 让多会话经 HTTP 复用同一份模型显存/内存，冷启动 180s → 2.6s
- **零 LLM 原则**：检索链路不调任何大模型 API，全部本地推理，断网可用

23 个 MCP 工具一览：`search_knowledge` `search_knowledge_multi` `get_source` `get_outline` `get_related` `list_sources` `get_categories` `save_markdown` `append_section` `index_file` `reindex_all` `rebuild_index_async` `validate_frontmatter` `check_broken_links` `delete_source` `merge_sources` `move_source` `report_mismatch` `get_search_gaps` `get_hit_stats` `get_orphans` `get_knowledge_info`

## 目录结构

```
├── README.md
├── requirements.txt          # 版本锁定的依赖清单
├── my-kb/                    # RAG 服务代码
│   ├── server.py             # MCP server 入口（stdio）
│   ├── model_service.py      # 共享模型服务（embedding+reranker，自动拉起）
│   ├── indexer.py            # 文档分块与索引
│   ├── retriever.py          # 混合检索 + 融合 + 精排
│   ├── bm25_manager.py       # BM25 索引管理
│   ├── config.py             # 全部配置（模型/分块/阈值）
│   ├── benchmark_eval.py     # 检索质量评测（含 46 条评测集）
│   └── ...
├── knowledge/mes/            # 知识库（单库制）
│   ├── metadata.json
│   └── raw/markdown/*.md     # 133 篇知识文档
└── scripts/
    └── process_knowledge.py  # 文档入库预处理
```

## 快速开始

环境：Python 3.11+（实测 3.11），Windows / Linux 均可。

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 首次建索引（133 篇文档，向量 + BM25）
cd my-kb
python -c "from indexer import index_all_files; index_all_files()"

# 3. 接入 MCP 客户端（以 ZCode / Claude Code 风格配置为例）
```

```json
{
  "mcpServers": {
    "my-kb": {
      "command": "python",
      "args": ["<仓库路径>/my-kb/server.py"]
    }
  }
}
```

首次启动会自动从 HuggingFace 下载模型（Qwen/Qwen3-Embedding-0.6B + BAAI/bge-reranker-base，共约 2GB）。国内网络建议设镜像：`HF_ENDPOINT=https://hf-mirror.com`（Windows 下可直接双击 `my-kb/start.bat`）。

接好后对 AI 说"检索一下 XXX"，它就会调 `search_knowledge` 了。写新文档用 `save_markdown`（frontmatter 需要 `title / category / module / tags`，详见 `config.py`）。

## 附带知识文档说明

133 篇文档来自真实 .NET MES 项目开发沉淀，主要内容：

- **Ext.NET 4.7**：官方 563 示例的分类导读、各控件实战指南（Grid/Chart/Calendar/FieldSet…）、页面骨架与样式规范、导出/iBATIS 整合模式
- **SQL Server**：性能排查与优化原则、建表设计原则、编号生成 SQL 的坑
- **.NET / C#**：NPOI Excel 导出兼容性、csproj 增量编译、批次编辑安全规则等
- **RAG / AI 工具**：agent 技能生态调研、代码审查工具接入、决策模型评估等

> **脱敏声明**：公开版已按关键词筛选剔除所有含雇主、客户及其项目线标识的文档（约一半篇幅留在私有库），保留通用技术内容；文档间个别 `[[wikilink]]` 指向未收录的私有库文档，属预期现象。

## 已知限制与设计取舍

- 单库制（`knowledge/mes/`），多库未做 UI，代码已按 kb_id 参数化
- 检索链路零 LLM：查询不改写、不摘要，靠调用方（AI）自主多变体检索
- Qwen3-Reranker 实测为负优化（打分二元极化，MRR 反降 3pt），已回滚用 bge-reranker-base，详见 `config.py` 注释
- Windows 实测环境：某终端安全软件会拖慢进程冷启动（首启慢属正常，后续共享服务常驻）
