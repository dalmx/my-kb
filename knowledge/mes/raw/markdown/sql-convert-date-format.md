---
title: SQL Server CONVERT() 日期格式转换（style 速查表）
category: 技术-数据库
module: 通用
factory: 通用
tags: [SQL Server, CONVERT, CAST, 日期格式, style, 格式化, 语法速查]
status: active
updated: 2026-08-29
---
# SQL Server CONVERT() 日期格式转换（style 速查表）

> CONVERT() 日期/时间转字符串的 style 参数速查表（0~131 全量对照），附项目高频写法：yyyy-MM-dd HH:mm:ss 用 120（19 位）、只取日期用 120/23（10 位）、ISO 紧凑格式用 112，以及日期比较去时间部分的统一格式技巧。

## 一、定义

`CONVERT()` 是把日期/时间转换为新数据类型（通常是字符串）的通用函数，可通过 `style` 参数控制输出格式。

## 二、语法

```text
CONVERT(data_type(length), expression, style)
```

| 参数 | 说明 |
|------|------|
| `data_type(length)` | 目标数据类型（带可选长度），如 `varchar(10)`、`varchar(19)` |
| `expression` | 要转换的值（日期/时间字段） |
| `style` | 日期/时间输出格式代码（见下表） |

> 与 `CAST(expression AS data_type)` 区别：CAST 不支持 style，无法控制日期格式细节；需要格式化输出用 CONVERT。

## 三、style 速查表（datetime → 字符）

| style (yy) | style (yyyy) | 输入/输出格式 | 标准 |
|------------|--------------|--------------|------|
| - | 0 或 100 | `mon dd yyyy hh:miAM` | Default |
| 1 | 101 | `mm/dd/yyyy` | USA |
| 2 | 102 | `yyyy.mm.dd` | ANSI |
| 3 | 103 | `dd/mm/yyyy` | British/French |
| 4 | 104 | `dd.mm.yyyy` | German |
| 5 | 105 | `dd-mm-yyyy` | Italian |
| 6 | 106 | `dd mon yyyy` | — |
| 7 | 107 | `Mon dd, yyyy` | — |
| 8 | 108 | `hh:mm:ss` | — |
| - | 9 或 109 | `mon dd yyyy hh:mi:ss:mmmAM` | Default+毫秒 |
| 10 | 110 | `mm-dd-yyyy` | USA |
| 11 | 111 | `yyyy/mm/dd` | Japan |
| 12 | 112 | `yyyymmdd` | ISO |
| - | 13 或 113 | `dd mon yyyy hh:mi:ss:mmm(24h)` | — |
| 14 | 114 | `hh:mi:ss:mmm(24h)` | — |
| - | 20 或 120 | `yyyy-mm-dd hh:mi:ss(24h)` | ODBC 规范 |
| - | 21 或 121 | `yyyy-mm-dd hh:mi:ss.mmm(24h)` | ODBC 规范+毫秒 |
| - | 126 | `yyyy-mm-ddThh:mi:ss.mmm` | ISO8601 |
| - | 130 | `dd mon yyyy hh:mi:ss:mmmAM` | Hijiri |
| - | 131 | `dd/mm/yyyy hh:mi:ss:mmmAM` | Hijiri |
| 23 | - | `yyyy-mm-dd` | XTDQGDB/常用 |

## 四、项目常用示例

```sql
-- 项目高频用法：转为 yyyy-MM-dd HH:mm:ss（19位）
CONVERT(varchar(19), GETDATE(), 120)        -- 2025-07-22 14:30:00

-- 只取日期部分 yyyy-MM-dd（10位）
CONVERT(varchar(10), GETDATE(), 120)        -- 2025-07-22
CONVERT(varchar(10), GETDATE(), 23)         -- 2025-07-22（另一种写法）

-- ISO 紧凑格式
CONVERT(varchar(8), GETDATE(), 112)         -- 20250722

-- 比较时统一格式（避免时间部分干扰日期比较）
WHERE t1.PLAN_DATE = CONVERT(varchar(10), '2025-07-22', 120)
```

## 五、常见场景

| 场景 | style | 示例输出 |
|------|-------|---------|
| 日期比较去时间 | 120 / 23 | `2025-07-22` |
| 显示完整时间 | 120 | `2025-07-22 14:30:00` |
| 批次/流水号拼日期 | 112 | `20250722` |
| 中文报表日期 | 23 | `2025-07-22` |

## 六、注意

- style 带"世纪"用 4 位 yyyy（如 120），不带"世纪"用 2 位 yy（如 20，输出 `25-07-22`）。日常用 4 位 yyyy 形式。
- `length` 决定截取长度：`CONVERT(varchar(10), ..., 120)` 取前 10 位（即只留日期）；想要完整带时间用 `varchar(19)`。
- ISO8601（126）带 `T` 分隔符，适合系统间传输；人读用 120。

## 七、关联

- ISNULL 类型转换陷阱：见 `sql-delete-duplicate-and-isnull-pitfall.md`
- SQL Server 性能排查：见 `sql-server-performance-troubleshooting.md`
