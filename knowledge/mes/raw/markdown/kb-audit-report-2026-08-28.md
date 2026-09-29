---
status: active
title: 知识库双领域抽查体检报告（2026-08-28）
category: 部署运维
module: 通用
factory: 通用
tags: [知识库, 体检, 抽查, 质量评估, SQL Server, Ext.NET, 缺口清单, 检索置信度, 补库路线图]
updated: 2026-08-29
---

# 知识库双领域抽查体检报告（2026-08-28）

> 由 expert-sql / expert-extnet 两个专家成员（多 agent 群模式，群 kbcheck）并行抽查各自领域知识库质量：SQL 域发现 4 处硬伤+6 篇缺口+1 个检索层盲区；Ext.NET 域体系四层健全、65 条示例路径 64 真 1 假（98.5%）。发现当日已修复 5 处（含版本注），剩余缺口按批次补库，本报告即补库路线图。

## 一、体检方法

- 每域：2-4 篇核心文档通读（对照领域专业知识+官方源码实证）+ 3 个真实业务问题检索实测（记录置信度与命中）+ 缺口清单
- 证据链：群时间线 `group-kbcheck.events.jsonl` + 两份成员报告（member-kbcheck-*.last.txt 对应 Pi session 全文）

## 二、SQL 域结论（sql-server-performance-troubleshooting / table-design / running-queries 等）

### 已修复（2026-08-28 当日，均附勘误注记）

| # | 问题 | 修复 |
|---|------|------|
| 1 | 性能手册"`count(字段名)` 会全表扫描"机制解释错误 | 改为准确语义（统计非 NULL 行、可用索引少、通常更慢），规范导向保留 |
| 2 | 死锁文档 `master..sysprocesses` 无废弃警示 | 加 deprecated 警示 + `sys.dm_exec_requests.blocking_session_id` DMV 替代写法，分工表同步标注 |
| 3 | 建表文档"严禁 uniqueidentifier 做主键"过强 | 精确为"避免随机 GUID（NEWID）做聚集索引键；NEWSEQUENTIALID/非聚集主键为正当方案" |
| 4 | STRING_AGG 等特性版本前提缺失 | 性能手册案例处补版本注（STRING_AGG 2017+、DROP TABLE IF EXISTS 2016+、先 @@version 确认） |

### 待补缺口（6 篇，按优先级）

1. **执行计划入门解读**——现有 12 篇性能文档共同引用"看执行计划/Key Lookup/估算行数"却无一篇教读，是共同前置知识（**第一批起草中**）
2. Query Store 查询存储（2016+）——参数嗅探/计划回退的现代化利器
3. 实例级等待事件（dm_os_wait_stats：PAGEIOLATCH/WRITELOG/CXPACKET）——"系统卡但找不到慢 SQL"的第二维度
4. 锁与隔离级别（RCSI、NOLOCK 脏读风险）——死锁文档只教查不教防
5. tempdb 诊断——"明细落临时表"方案的配套监控
6. 批量找全库隐式转换的 DMV 脚本（从计划缓存捞 CONVERT_IMPLICIT）

### 检索层系统性盲区（重要）

口语问法"存储过程有时快有时慢"召回到 0.69 的**不对题**结果，却因 ≥0.5 被标"✅高置信直接采用"——既误导采用又进不了缺口日志（只记 <0.3）。术语化改写后 top1=1.00，说明知识在库、是"最后一步召回+置信度标注"问题。**建议**：置信度档位引入对题性校验，或缺口日志采样阈值上调观察。

## 三、Ext.NET 域结论

### 体系判定：结构最规范的一档

- 四层齐全无断链：场景路由 → 目录层（36 篇 catalog 探测全在）→ 指南层 → 样式清单；交叉引用 [[wikilink]] 无断链
- 65 条示例路径对照官方 4.7.1 本地源码：**64 真 1 假（98.5%）**；4 篇精读全部"优"（Locked 约束/Buffered Store 滚动条/FilterHeader 服务端解析等断言逐条核实为真）

### 已修复

| # | 问题 | 修复 |
|---|------|------|
| 5 | 场景路由"悬浮全文"指向不存在的 `ToolTips/GridPanel_Cell_Tooltip` | 改指向库内 [[extnet-grid-tooltip-delegate]]，注明勘误 |

### 待补缺口（按价值排序）

1. **《级联下拉专篇》**——现散在 Form 目录行+store-databinding 第十一节+样式清单三处；整合"远程 DirectEvents/本地 filters/表格内级联/声明式绑定"四种选型+"联动值进查询 where 三处同步"坑（**第一批起草中**）
2. DirectMethod/DirectEvent 通信专篇（返回值序列化/ExtraParams/IsDirectMethodCall）
3. master 新增 4 例补 GitHub raw 直链（减少检索-拉取两跳）
4. Form 校验/多列布局指南

### 检索实测

3 问中 2 问一步到位（列锁定 1.00、报表起步 0.92）；"下拉联动"口语首轮命中相邻主题（输入过滤），**专有名词改写 + multi 变体策略实测有效**——印证库里沉淀的检索方法论。

## 四、补库批次计划

- **第一批（进行中）**：执行计划入门（SQL#1）+ 级联下拉专篇（Ext#1）——expert 成员起草 → ZCode 终审（源码钉事实）→ 用户拍板入库
- 第二批：Query Store + DirectMethod 专篇
- 第三批：等待事件/锁隔离/tempdb/隐式转换批量脚本 + raw 直链/Form 布局
- 并行跟进：检索层置信度对题性校验（改 my-kb 服务端，另行任务）

## 五、待人工确认

1. 分类定稿：本报告归 部署运维/通用（知识库自身的体检与维护记录，与既有 KB 运维文档同域）
2. 检索层盲区的修复方案（对题性校验怎么加）需单独评估 my-kb 服务端改动，未含在本报告
3. 各缺口文档入库时建议互相引用本报告的缺口编号
