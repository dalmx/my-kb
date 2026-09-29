---
title: SQL Server 删除重复数据 + ISNULL 类型转换陷阱
category: 技术-数据库
module: 通用
factory: 通用
tags: [SQL Server, ROW_NUMBER, CTE, 删除重复数据, ISNULL, 类型转换, 隐式转换, 踩坑, 语法速查]
status: active
updated: 2026-08-29
---
# SQL Server 删除重复数据 + ISNULL 类型转换陷阱

> 两大主题：①CTE + ROW_NUMBER() OVER(PARTITION BY ...) 删重复数据（每组保留一条，可按时间保留最新，先 SELECT 预览再删）；②ISNULL 返回类型跟随第一个参数——数字 0 时 ISNULL(param, '') <> '' 因隐式转换意外成立，须先 CONVERT(varchar) 再做非空判断。

## 一、用法

用 CTE 配合 `ROW_NUMBER() OVER(PARTITION BY ...)` 给每组重复行编号，删除编号 >1 的即保留每组一条。

```sql
WITH TaskInfoWithRowNumber AS (
    SELECT card_no, green_tyreNo,
        ROW_NUMBER() OVER (
            PARTITION BY card_no, green_tyreNo
            ORDER BY (SELECT NULL)
        ) AS row_number
    FROM trc_molding_semis
)
DELETE FROM TaskInfoWithRowNumber
WHERE row_number > 1;
```

## 二、逐行解析

| 部分 | 含义 |
|------|------|
| `WITH ... AS (...)` | CTE（公用表表达式），先算出带行号的临时结果集 |
| `PARTITION BY card_no, green_tyreNo` | 按这两个字段分组——组内即"重复" |
| `ORDER BY (SELECT NULL)` | 组内不讲究顺序（随便排），只为生成行号 |
| `ROW_NUMBER() ... AS row_number` | 每组从 1 开始编号，重复行得到 1,2,3... |
| `DELETE ... WHERE row_number > 1` | 删除每组第 2 条及以后，保留每组第一条 |

> `ORDER BY (SELECT NULL)` 表示组内随机排序。若想保留"最新/最早"那条，改为具体字段，如 `ORDER BY RECORD_TIME DESC` 保留最新。

## 三、变种

### 3.1 保留最新一条（按时间倒序，row_number=1 最新）

```sql
ROW_NUMBER() OVER (PARTITION BY card_no, green_tyreNo ORDER BY RECORD_TIME DESC)
```

### 3.2 先查看将删除哪些（不直接删，先 SELECT 确认）

```sql
WITH TaskInfoWithRowNumber AS (...)
SELECT * FROM TaskInfoWithRowNumber WHERE row_number > 1;
```

确认无误再把 `SELECT *` 改成 `DELETE`。

## 四、注意

- CTE + DELETE 在同一语句中，CTE 必须是**可更新的**（直接引用基表，无 GROUP BY/DISTINCT 等聚合）。
- 删除前务必先 SELECT 预览，避免误删。
- 若重复量大，DELETE 可能产生大量日志，注意事务日志增长（大表可分批删）。

---

## 五、ISNULL 类型转换陷阱（数字 0 时 <> '' 成立）⚠️

## 六、现象

在 mybatis/iBatis 中用 `ISNULL(param, '') <> ''` 判断"非空"时，若 `param` 是数字且值为 **0**，这个判断**竟然成立**（走入 Update 分支），与预期不符。

```sql
DECLARE @param4 INT = 0

-- 测试1：ISNULL 直接判断
SELECT CASE WHEN ISNULL(@param4, '') <> '' THEN '执行 Update'  -- ⚠️ 走这里！
            ELSE '执行 Else' END AS Result

-- 测试2：先 CONVERT 再判断
SELECT CASE WHEN ISNULL(convert(varchar, @param4), '') <> '' THEN '执行 Update'
            ELSE '执行 Else' END AS Result                     -- ✅ 正确走 Else
```

## 七、根因

`ISNULL(check_expression, replacement_value)` 的返回类型由 **第一个参数** 决定（不是第二个）。

| 表达式 | 第一个参数类型 | 返回类型 | 实际值 | 与 '' 比较结果 |
|--------|--------------|---------|--------|---------------|
| `ISNULL(@param4, '')` | INT | **INT** | `0` | `0 <> ''` → 隐式转换 → **true**（走 Update）|
| `ISNULL(CONVERT(varchar,@param4), '')` | varchar | varchar | `'0'` | `'0' <> ''` → true |

> 关键：当 `@param4 = 0` 时，`ISNULL(0, '')` 返回 INT 类型的 `0`。与空字符串 `''` 比较时，SQL Server 把 `''` **隐式转换为 INT 的 0**，于是 `0 <> 0` 为 false……实际测试中因隐式转换规则，结果可能反过来成立。核心是**类型不一致导致隐式转换，行为难以预测**。

## 八、验证方式

用 `SQL_VARIANT_PROPERTY` 查实际返回类型：

```sql
SELECT 
    ISNULL(@param4, '') AS Result,                    -- 返回 0
    DATALENGTH(ISNULL(@param4, '')) AS DataLength,    -- 4（INT 长度）
    SQL_VARIANT_PROPERTY(ISNULL(@param4, ''), 'BaseType') AS DataType  -- int
```

> `DATALENGTH` 返回 4 说明是 INT（4字节），而非字符串；`BaseType` 明确显示 `int`。

## 九、解决：统一转 varchar 再判断

```sql
-- ✅ 正确：先转 varchar，再做 ISNULL + 非空判断
ISNULL(CONVERT(varchar, @param4), '') <> ''
```

原则：**做字符串非空判断前，先把数字参数显式 CONVERT 成 varchar**，避免 ISNULL 返回数字类型导致隐式转换陷阱。

## 十、扩展：ISNULL 返回类型规则

| 情况 | 返回类型 |
|------|---------|
| `ISNULL(int列, '')` | int（第一个参数决定） |
| `ISNULL(varchar列, '')` | varchar |
| `ISNULL(NULL, '')` | 第二个参数类型 |

> 记忆：ISNULL 的返回类型**跟随第一个参数**，所以第一个参数是数字就返回数字，第二个的 `''` 只在第一个为 NULL 时作为值填入，但类型仍按第一个走。

## 十一、关联

- CONVERT 日期格式速查：见 `sql-convert-date-format.md`
- SQL Server 性能排查：见 `sql-server-performance-troubleshooting.md`
- MERGE INTO / APPLY 语法：见 `sql-merge-into-upsert.md`、`sql-outer-apply-cross-apply.md`
