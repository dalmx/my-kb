---
title: SQL Server APPLY（CROSS APPLY / OUTER APPLY）用法与类比
category: 技术-数据库
module: 通用
factory: 通用
tags: [SQL Server, OUTER APPLY, CROSS APPLY, 表值函数, JOIN, 关联子查询, 语法速查]
status: active
updated: 2026-08-29
---
# SQL Server APPLY（CROSS APPLY / OUTER APPLY）用法与类比

> APPLY 运算符对左表每行执行一次右侧子查询/表值函数（右侧可引用左侧列，JOIN 做不到）：CROSS APPLY 类比 INNER JOIN（只留有匹配行）、OUTER APPLY 类比 LEFT JOIN（无匹配填 NULL）。经典用法是每行取 TOP N（如每个员工最新一条订单）与表值函数传参。

## 一、作用

APPLY 运算符允许**对左侧表的每一行，执行一次右侧的子查询/表值函数**，并把结果与左行关联。与 JOIN 的区别在于：**右侧可以引用左侧的列**（即关联子查询），JOIN 的右侧不能引用左侧。

两种形式：
- `CROSS APPLY`：只返回左侧表中在右侧有匹配结果的行（类似 INNER JOIN）。
- `OUTER APPLY`：返回左侧所有行，右侧无匹配时用 NULL 填充（类似 LEFT JOIN）。

## 二、基本语法

### 形式 1：右侧是子查询

```sql
SELECT 列名
FROM 左侧表名
OUTER APPLY (
    右侧子查询（可引用左侧表.列名）
) AS 别名
```

### 形式 2：右侧是表值函数

```sql
SELECT 列名
FROM 左侧表名
OUTER APPLY 表值函数(左侧表.列名) AS 别名
```

> 关键：右侧子查询/函数的参数可以引用左侧当前行的列，这是 JOIN 做不到的。

## 三、两种形式的对比

| 运算符 | 左侧行保留 | 右侧无匹配时 | 类比 |
|--------|-----------|-------------|------|
| `CROSS APPLY` | 仅保留有匹配的行 | 左侧行被丢弃 | **INNER JOIN** |
| `OUTER APPLY` | 全部保留 | 右侧列填 NULL | **LEFT OUTER JOIN** |

用一个类比来理解：
- **CROSS APPLY** 就像 INNER JOIN：必须"门当户对"，两边都有数据才留下。
- **OUTER APPLY** 就像 LEFT OUTER JOIN：以左表为主，左表数据全保留，右表没有就用 NULL 补齐。

## 四、示例

### 4.1 子查询形式 — 取每个员工最新一条订单

```sql
SELECT e.EmpName, o.OrderID, o.OrderDate
FROM Employee e
OUTER APPLY (
    SELECT TOP 1 OrderID, OrderDate
    FROM Orders
    WHERE Orders.EmpID = e.EmpID
    ORDER BY OrderDate DESC
) o
```

- 每个员工取最新一条订单；没订单的员工也会出现，订单列为 NULL。
- 若改 `CROSS APPLY`，没订单的员工不会出现。

### 4.2 表值函数形式 — 按物料编码查库存

```sql
SELECT m.MATERIAL_NAME, s.STOCK_QTY
FROM MATERIAL m
OUTER APPLY dbo.fn_GetStock(m.MATERIAL_CODE) s
```

- `fn_GetStock` 是表值函数，参数引用了左表当前行的 `MATERIAL_CODE`。
- 每行物料传入函数，得到库存量；无库存返回 NULL。

### 4.3 CROSS APPLY 取有匹配的行

```sql
SELECT d.DeptName, e.EmpName
FROM Department d
CROSS APPLY (
    SELECT EmpName FROM Employee WHERE Employee.DeptID = d.DeptID
) e
```

- 只返回有员工的部门；空部门被过滤掉。

## 五、APPLY 与 JOIN 的区别

| 维度 | JOIN | APPLY |
|------|------|-------|
| 右侧能否引用左侧列 | 不能（关联条件在 ON 里） | **能**（右侧子查询参数可引用左行） |
| 右侧形式 | 表/视图 | 子查询 / 表值函数 |
| 每行执行次数 | 一次性匹配 | **左表每行执行一次**右侧 |
| 典型场景 | 两表等值/范围关联 | 每行需 TOP N、标量聚合、函数调用 |

> JOIN 是"两个集合做条件连接"；APPLY 是"左表每行喂给右侧查询/函数，收集结果"。当右侧需要"按左行动态计算"时（如每行取 TOP 1、调用表值函数），用 APPLY。

## 六、注意

- **性能**：APPLY 对左表每行执行一次右侧查询，左表数据量大时可能慢。确保右侧查询有合适索引（特别是关联左表列的索引）。
- **APPLY 是 SQL Server 独有**（Oracle 用 LATERAL，PostgreSQL 也支持 LATERAL），迁移时注意兼容性。
- `OUTER APPLY` 的 NULL 填充行为与 `LEFT JOIN` 一致；若业务要求"必须有匹配"，用 `CROSS APPLY`。
- 配合 `TOP N` + `ORDER BY` 是 APPLY 的经典用法（分组取每组前 N 条），比窗口函数 `ROW_NUMBER() OVER(PARTITION BY...)` 更直观。

## 七、关联

- SQL Server 性能排查与优化：见 `sql-server-performance-troubleshooting.md`
- InfluxDB 时序数据查询：见 `semi-influxdb-timeseries.md`
- UNION ALL 的 ORDER BY 坑：见 `semi-return-rubber-ratio-report.md`（如有）
- 多维汇总（WITH CUBE / GROUPING SETS）：见 `sql-grouping-cube-rollup-serverip.md`
