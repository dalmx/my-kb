---
title: 知识库全量审查与工具链修复报告（2026-08-29）
category: 部署运维
module: 通用
factory: 通用
tags: [知识库, 全量审查, 代码修复, 断链, SPC系数, 引用三形态, BM25失效, 结构债, 批次清理, C8写入门槛]
updated: 2026-08-29
status: active
---
# 知识库全量审查与工具链修复报告（2026-08-29）

> 承接 [kb-audit-report-2026-08-28.md](kb-audit-report-2026-08-28.md)（双领域抽查体检），本篇为 CC 旗舰成员对 225 篇全量结构扫描 + 非 SQL/Ext.NET 领域内容抽查 + my-kb 服务端代码审查，发现阻断级 4+6 条当日全部修复并验证；含存量结构债第一批清理计划。

## 一、审查方法与覆盖面

- 结构合规扫描 225/225 全量（CC 沙箱禁 python，用 Grep 正则计数 + 编排方代跑其检查脚本 `kb_audit_scan.py` 复核，数字吻合：225 篇/tags 块式 15/updated 缺 76/wikilink 196 完全一致）
- 引用完整性约 1100 处，新扫出第三种引用形态（Markdown 链接——方括号文本 + 圆括号目标文件，mould 系密集使用）是既往巡检盲区
- 内容抽查 11 篇（业务-通用×5/业务-模具×2/部署运维×2/技术-.NET×1/技术-数据库×1）：优×5/良×5/有问题×1
- 量化断言抽验 4/4 精确（Ext.NET 37 分类/133/28/61 例全对），本地路径断言 3/3 存在

## 二、阻断级发现与修复（10 条当日闭环）

| 编号 | 位置 | 问题 | 修复 |
|---|---|---|---|
| B1/B2 | style-checklist:119/137、nginx-iis:46 | wikilink 断链（目标已并入/不存在） | 改指 extnet-pagination-guide、measure-attachment-full-solution（第七节 500MB 三层配置），附勘误注 |
| B3/B4 | cpk-spc-calculation-formulas.md:58-63/:92/:127-131 | SPC 修偏系数命名系统性错误：1.693/2.059/2.326 全是 d2 在 n=3/4/5 取值却标成 d3/d4/d5；GetCP"固定 5 个/组"却用 2.704（实为 d2 在 n=7 的值） | 数表与正文全改 d2 并附勘误注；2.704 为源码事实不改数字，加"与分组规则矛盾疑笔误"警示 |
| C1-C3 | graph_tools.py | 引用替换/断链巡检/引用图只认反引号形态，wikilink 与 md 链接不在覆盖内（每次 move/merge 制造新断链且巡检永远查不出） | 三形态统一提取器 `extract_all_references`/`replace_references` 三处接入 |
| C4 | server.py delete_source | 删向量块后不失效 BM25，已删文档仍可召回 | 删除成功后调 `invalidate(kb_id)` |
| C5 | preprocessing.py build_where_filter | tags 多标签只取第一个，违背"命中任一"契约 | `$contains` + `$or` 组装（Chroma 同层限制用 `$and` 包裹），配套 retriever `_match_where` 递归求值器（否则 BM25 通道滤光结果）；终审补单标签扁平化保持历史形态 |
| C6 | server.py merge_sources | 不校验直接拼接落盘 + 先删源后写 target | 先过 validate_doc_format 零副作用中止、先写 target 后删源、`build_merged_document` 单 H1 统一（合并说明用纯文本防自引用断链） |

捎带修复：C9（save_markdown 只扫 frontmatter 区段，正文 `updated:` 示例不再误判）、C10（delete/move 自动补 .md 后缀）、C14（Windows 大小写-only 改名两步走）。

## 三、验证记录

- 自测脚本 `pi-handoff/workspace/test_kb_fixes.py`（约 30 用例，临时目录 fixture + FakeVectorstore，不碰真实库）代跑 **27/27 PASS**
- 运行时（服务重启后实测）：三形态断链巡检生效，全库真断链归零（报出 4 条均为占位符示例文本误报——三 x 点 md 与双方括号 wikilink 字样，见 kb-metadata-spec §九豁免）；双标签 `$or` 过滤在真实 Chroma 上正常命中
- 知识库改动 3 篇已重索引；批量清理前全量备份 `pi-handoff/workspace/backup-20260829/`

## 四、遗留与批次计划（已拍板）

- **C8 写入门槛扩到 9 条**（已批准）：validate_doc_format 补 H1==title、H1 后摘要、章节中文序号、代码围栏语言四项硬校验；append_section 对存量债两项豁免（只拦新增内容）
- **第一批存量清理**（进行中）：S2 无摘要 47 篇 / S4 H1≠title 29 篇 / S5 tags 块式 15 篇 / S6 缺 factory 2 篇 / S7 updated 补全 76 篇 / S8 编号特殊伤 4 类 / S9 合并自引用 5 篇 / S10 表述瑕疵 5 处
- **第二批**：S3 裸围栏补语言标注（约 169 篇，量大单列）
- 明确不做维持：C7/C11/C13/C15（见审查报告 §八）；检索层置信度对题性校验另行任务（上次体检已知盲区）
- 完整证据链：`pi-handoff/report-20260828-kbaudit-cc.md`（审查）、`pi-handoff/report-20260828-kbfix-cc.md`（修复）
