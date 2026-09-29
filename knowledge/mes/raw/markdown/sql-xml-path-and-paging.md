---
title: SQL Server 列转行（FOR XML PATH）+ 临时表删除 + 分页（OFFSET FETCH）
category: 技术-数据库
module: 通用
factory: 通用
tags: [SQL Server, FOR XML PATH, STUFF, 列转行, 行拼接, 临时表, OBJECT_ID, OFFSET FETCH, 分页, 语法速查]
status: active
updated: 2026-08-29
---
# SQL Server 列转行（FOR XML PATH）+ 临时表删除 + 分页（OFFSET FETCH）

> 三件套：OBJECT_ID 判断临时表存在则 DROP（脚本可重复执行）；FOR XML PATH('') + TYPE + STUFF 把多行拼成一个字符串（列转行，加 TYPE 避免 XML 转义）；OFFSET FETCH 分页/分批处理（2012+，须先 ORDER BY，附与 ROW_NUMBER 方式的对比）。

## 一、临时表存在则删除（OBJECT_ID 判断）

```sql
If OBJECT_ID('TempDB..#JarTemp') Is Not Null
    Drop Table #JarTemp
```

- `OBJECT_ID('TempDB..#JarTemp')`：查 TempDB 里临时表 `#JarTemp` 的对象 ID，不存在返回 NULL。
- 模式：`'数据库名..表名'`（两个点省略 schema）。
- 用途：脚本可重复执行，避免"表已存在"报错。

> 永久表写法：`OBJECT_ID('dbo.表名')` 或 `OBJECT_ID('数据库名.dbo.表名')`。

## 二、列转行：把多行某列拼成一个字符串（FOR XML PATH + STUFF）

### 2.1 用法

```sql
SELECT STUFF((
    SELECT ',"' + GREEN_TYRE_NO + '"'
    FROM PSM_OUT_STOCK_DETAIL
    WHERE BILL_ID = '2001DN2024100060C'
    FOR XML PATH(''), TYPE
).value('.', 'NVARCHAR(MAX)'), 1, 1, '') AS LastNames;
```

结果示例：把多行 `GREEN_TYRE_NO` 拼成 `"胎号1","胎号2","胎号3"`。

### 2.2 逐段解析

| 部分 | 作用 |
|------|------|
| `SELECT ',"' + GREEN_TYRE_NO + '"'` | 每行拼成 `,"胎号"` 形式（带逗号前缀和引号） |
| `FOR XML PATH('')` | 把多行结果拼成单个字符串，PATH('') 不加行标签 |
| `TYPE` | 返回 XML 类型（避免特殊字符被转义） |
| `.value('.', 'NVARCHAR(MAX)')` | 从 XML 提取纯文本，支持长字符串 |
| `STUFF(..., 1, 1, '')` | 删除最开头那个多余的逗号（第1位起删1个字符） |

### 2.3 工作流程

1. 子查询每行产出 `,"胎号A"`、`,"胎号B"`、`,"胎号C"`
2. `FOR XML PATH('')` 拼成 `,"胎号A","胎号B","胎号C"`
3. `STUFF(...,1,1,'')` 去掉开头的逗号 → `"胎号A","胎号B","胎号C"`
4. 得到可直接用于 `IN (...)` 或前端展示的逗号分隔串

### 2.4 变种

```sql
-- 不带引号，纯逗号分隔
SELECT STUFF((
    SELECT ',' + GREEN_TYRE_NO
    FROM PSM_OUT_STOCK_DETAIL
    FOR XML PATH(''), TYPE
).value('.', 'NVARCHAR(MAX)'), 1, 1, '') AS TireList;
-- 结果：胎号A,胎号B,胎号C

-- 用于 IN 子句
WHERE GREEN_TYRE_NO IN (
    SELECT value FROM STRING_SPLIT(@TireList, ',')   -- SQL Server 2016+
)
```

### 2.5 注意

- 加 `TYPE` + `.value('.', 'NVARCHAR(MAX)')` 可避免 `<`、`>`、`&` 等字符被 XML 转义成 `&lt;` 等。
- 不加 `TYPE` 直接 `FOR XML PATH('')`，特殊字符会被转义，简单数据可用。
- `STUFF(字符串, 起始位置, 长度, 替换串)`：起始位置=1、长度=1、替换为空 = 删第一个字符。

## 三、分页查询（OFFSET FETCH，SQL Server 2012+）

### 3.1 语法

```sql
SELECT 列
FROM 表
WHERE 条件
ORDER BY 排序字段
OFFSET @Skip ROWS                  -- 跳过多少行
FETCH NEXT @Take ROWS ONLY;        -- 取多少行
```

### 3.2 项目实例：分批处理

```sql
DECLARE @BatchSize INT = 500
DECLARE @TotalCount INT = (SELECT COUNT(*) FROM YourTable WHERE [你的条件])
DECLARE @CurrentPosition INT = 1

WHILE @CurrentPosition <= @TotalCount
BEGIN
    SELECT *
    FROM YourTable
    WHERE [你的条件]
    ORDER BY [排序字段]
    OFFSET @CurrentPosition - 1 ROWS        -- 跳过已处理的
    FETCH NEXT @BatchSize ROWS ONLY          -- 每次取 500 行

    SET @CurrentPosition = @CurrentPosition + @BatchSize
END
```

### 3.3 要点

| 部分 | 说明 |
|------|------|
| `OFFSET n ROWS` | 跳过前 n 行（n 从 0 开始，0=不跳过） |
| `FETCH NEXT m ROWS ONLY` | 取接下来的 m 行 |
| **必须先 ORDER BY** | OFFSET/FETCH 依赖排序，无 ORDER BY 会报错 |
| 版本 | SQL Server 2012+ 支持；更早版本用 `ROW_NUMBER()` |

### 3.4 与 ROW_NUMBER 分页对比

| 方式 | 写法 | 版本 |
|------|------|------|
| `OFFSET FETCH` | `ORDER BY x OFFSET @Skip ROWS FETCH NEXT @Take ROWS ONLY` | 2012+ |
| `ROW_NUMBER()` | CTE 里 `ROW_NUMBER() OVER(ORDER BY x)` 再过滤 rn 范围 | 2005+ |

> 项目里 `PageResult` + `GetPageDataByReader` 分页用的是 iBatis SQL 层的 ROW_NUMBER 方式（见 extnet 分页文档）；纯 SQL 脚本分批处理可用更简洁的 OFFSET FETCH。

## 四、关联

- 游标使用（另一种逐行/分批处理）：见 `sql-cursor-usage.md`
- 查询正在执行的语句 / 死锁：见 `sql-running-queries-and-deadlock.md`
- 前端分页（PageProxy + DirectMethod）：见 `extnet-pagination-guide.md`
- SQL Server 性能排查：见 `sql-server-performance-troubleshooting.md`
