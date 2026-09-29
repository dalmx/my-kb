---
title: SQL Server 多维汇总（WITH CUBE / GROUPING SETS / GROUPING）+ 获取服务器IP
category: 技术-数据库
module: 通用
factory: 通用
tags: [SQL Server, WITH CUBE, GROUPING SETS, GROUPING, WITH ROLLUP, 多维汇总, 小计, 总计, sys.dm_exec_connections, 服务器IP, 语法速查]
status: active
updated: 2026-08-29
---
# SQL Server 多维汇总（WITH CUBE / GROUPING SETS / GROUPING）+ 获取服务器IP

> WITH CUBE / WITH ROLLUP / GROUPING SETS 三种多维汇总方式对比（2^N 全交叉 vs 层级链 vs 自定义组合），GROUPING() 函数标记总计行避免与业务 NULL 误判，附 HPP_PLAN 设备×班次汇总项目实例；文末附 sys.dm_exec_connections 取当前会话服务器 IP 的运维片段。

## 一、场景

报表需要**一次查询同时输出**：明细分组、各维度小计、全局总计。例如按"设备 × 班次"统计计划产量，同时给出：每个设备各班次明细、每个设备合计、每个班次合计、总计。

三种方式：
- `WITH CUBE`：自动生成所有维度的交叉组合 + 总计。
- `WITH ROLLUP`：仅按层级生成子总计（设备→班次→总计）。
- `GROUPING SETS`：自定义要哪些分组组合（最灵活）。

## 二、项目实例：设备×班次计划产量汇总

```sql
select
    case when grouping(t1.EQUIP_ID) = 1 then 'Total' else t1.EQUIP_ID end EQUIP_CODE,
    case when grouping(t1.SHIFT_ID) = 1 then 'Total' else 'S' + t1.SHIFT_ID end SHIFT_CODE,
    sum(t2.PLAN_AMOUNT) PLAN_AMOUNT
from HPP_PLAN t1 with(nolock)
inner join HPP_PLAN_DETAIL t2 with(nolock) on t1.PLAN_ID = t2.PLAN_ID
where t1.PLAN_DATE = convert(varchar(10), '2025-07-22', 120)
group by t1.EQUIP_ID, t1.SHIFT_ID with cube
```

输出行类型：
| EQUIP_CODE | SHIFT_CODE | 含义 |
|------------|------------|------|
| E001 | S1 | 设备E001、班次1 的明细 |
| E001 | S2 | 设备E001、班次2 的明细 |
| E001 | Total | 设备E001 的子总计（所有班次汇总） |
| E002 | S1 / S2 / Total | ... |
| Total | S1 | 班次1 的子总计（所有设备汇总） |
| Total | S2 | 班次2 的子总计（所有设备汇总） |
| Total | Total | 全局总计 |

## 三、WITH CUBE — 全交叉汇总

```sql
group by t1.EQUIP_ID, t1.SHIFT_ID with cube
```

生成**所有可能的分组组合**：N 个分组列 → 2^N 种组合。
- 2 列 → 4 种：`(设备,班次)`、`(设备)`、`(班次)`、`()总计`
- 自动包含每个维度的子计和总计

> 类比：CUBE 是"全排列式汇总"，每个维度独立小计 + 总计。

## 四、WITH ROLLUP — 层级式汇总

```sql
group by t1.EQUIP_ID, t1.SHIFT_ID with rollup
```

仅按**列的顺序层级**生成子总计：
- `(设备,班次)` 明细
- `(设备)` 每个设备的合计
- `()` 总计

**不生成** `(班次)` 的独立小计（班次是更深层级，不会向上单独汇总）。

| 对比 | WITH CUBE | WITH ROLLUP |
|------|-----------|-------------|
| 组合数 | 2^N（全交叉） | N+1（层级链） |
| 班次独立小计 | ✅ 有 | ❌ 无 |
| 适用 | 各维度独立汇总 | 有明确层级（年→月→日） |

## 五、GROUPING SETS — 自定义组合（最灵活）

精确指定要哪些分组，不多不少：

```sql
group by grouping sets (
    (t1.EQUIP_ID, t1.SHIFT_ID),  -- 常规分组（明细）
    (t1.EQUIP_ID),               -- 仅按设备汇总
    (t1.SHIFT_ID),               -- 仅按班次汇总
    ()                           -- 全局总计
)
```

- 想要哪些组合就列哪些，括号内是分组列，`()` 是总计。
- 等价于上面的 `WITH CUBE`，但可按需精简（如只要明细+总计，去掉中间两个）。
- 推荐：需求明确时用 GROUPING SETS，比 CUBE 更可控、性能更好。

## 六、GROUPING() 函数 — 标记总计行

```sql
case when grouping(t1.EQUIP_ID) = 1 then 'Total' else t1.EQUIP_ID end
```

- `GROUPING(列)` 返回 `1` 表示**该列在当前行被聚合**（即这是该维度的总计行），`0` 表示正常分组值。
- 用途：总计行原列值为 NULL，用 GROUPING 判断后替换成 `'Total'` 等可读文本，避免显示 NULL。

> ⚠️ 不能直接 `case when EQUIP_ID is null then 'Total'`——因为业务数据本身可能就有 NULL 值，会误判。GROUPING() 专门区分"聚合产生的 NULL"和"数据本身的 NULL"。

## 七、三种方式对照

| 方式 | 组合 | 灵活度 | 典型场景 |
|------|------|--------|----------|
| `WITH CUBE` | 全交叉（2^N） | 低（全要） | 需要所有维度小计 |
| `WITH ROLLUP` | 层级链（N+1） | 低（按顺序） | 年/月/日层级报表 |
| `GROUPING SETS` | 自定义 | **高** | 精确控制要哪些汇总 |

## 八、性能注意

- CUBE 生成行数最多（2^N 种组合），数据量大时可能影响性能。
- 仅需特定维度总计时，优先用 GROUPING SETS 或 ROLLUP，减少无用组合。
- 配合 `with(nolock)` 减少锁等待（报表查询常用，接受脏读换取并发）。

---

## 九、获取服务器 IP

```sql
select local_net_address
from sys.dm_exec_connections
where session_id = @@SPID
```

- `@@SPID`：当前会话的进程 ID。
- `sys.dm_exec_connections`：当前连接的动态管理视图，`local_net_address` 是服务器端监听 IP。
- 用途：在存储过程/触发器里获取当前连接的服务器 IP，用于多服务器环境判断、日志记录。

> 返回的是**当前会话所连接的服务器 IP**，适合在 SQL 内部获取运行环境信息。

## 十、关联

- SQL Server 性能排查（含 CROSS APPLY 取 SQL 文本）：见 `sql-server-performance-troubleshooting.md`
- APPLY / MERGE 语法：见 `sql-outer-apply-cross-apply.md`、`sql-merge-into-upsert.md`
- 前端合计行（Summary Feature + SummaryType）：见 `extnet-grid-complete-guide.md`
- DataTable.Compute 求合计（C# 端）：见 `extnet-export-i18n-error.md`
