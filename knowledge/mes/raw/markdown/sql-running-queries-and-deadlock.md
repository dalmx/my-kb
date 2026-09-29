---
title: SQL Server 查询正在执行的语句 + 阻塞/死锁排查
category: 技术-数据库
module: 通用
factory: 通用
tags: [SQL Server, sys.dm_exec_requests, sysprocesses, 阻塞, blocking, 死锁, deadlock, DBCC INPUTBUFFER, system_health, 运维, 排障]
status: active
updated: 2026-08-28
---
# SQL Server 查询正在执行的语句 + 阻塞/死锁排查

> 四板斧排障：sys.dm_exec_requests 实时看正在执行的慢 SQL（CROSS APPLY 取 SQL 文本）；sysprocesses 阻塞链看谁阻塞谁（附 DMV 替代写法与废弃警示）；DBCC INPUTBUFFER 按 SPID 反查最后执行的语句；system_health 扩展事件查历史死锁 XML 报告（事后定责）。

## 一、查询正在执行的语句（按耗时降序）

```sql
SELECT 
    r.session_id,
    r.start_time,
    r.status,
    r.cpu_time,
    r.total_elapsed_time,
    r.reads,
    r.writes,
    r.logical_reads,
    r.blocking_session_id,   -- 被谁阻塞（0=无阻塞）
    s.text AS sql_text       -- 正在执行的 SQL 文本
FROM sys.dm_exec_requests r
CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) s
ORDER BY r.total_elapsed_time DESC;   -- 按执行时间降序
```

### 字段说明

| 字段 | 含义 |
|------|------|
| `session_id` | 会话 ID（SPID） |
| `start_time` | 请求开始时间 |
| `status` | running / suspended / runnable 等 |
| `cpu_time` | 累计 CPU 时间（ms） |
| `total_elapsed_time` | 总耗时（ms），排序依据 |
| `reads / writes / logical_reads` | 物理/写/逻辑读次数，定位 IO 大的语句 |
| `blocking_session_id` | 阻塞它的会话 ID；0 表示无阻塞 |
| `sql_text` | 通过 CROSS APPLY 取出完整 SQL |

> 用途：定位当前最耗时的 SQL，快速找到慢查询/长事务。

## 二、查询阻塞关系（谁阻塞谁）

```sql
select 
    A.SPID as 被阻塞进程,
    a.CMD AS 正在执行的操作,
    b.SPID AS 阻塞进程号,
    b.CMD AS 阻塞进程正在执行的操作
from master..sysprocesses a, master..sysprocesses b
where a.blocked <> 0          -- 被阻塞的进程
  and a.blocked = b.SPID      -- 它的 blocked 字段 = 阻塞者的 SPID
```

- `sysprocesses.blocked`：若该进程被阻塞，这里存阻塞者的 SPID；未被阻塞为 0。
- `a.blocked <> 0` 筛出所有被阻塞的进程，`a.blocked = b.SPID` 关联到阻塞者。
- 一眼看出"A 被 B 卡住，B 正在执行什么操作"。

> 与手册的 `sp_who_lock` 互补：`sp_who_lock` 侧重死锁，这条 `sysprocesses` 写法侧重一般阻塞链。

> ⚠️ **废弃警示（2026-08-28 补）**：`master..sysprocesses` 是 SQL Server 2005 起保留的向后兼容视图，官方标记为 deprecated，未来版本可能移除。新环境优先用 DMV 写法：
> ```sql
> select r.session_id as 被阻塞会话,
>        r.blocking_session_id as 阻塞会话,
>        r.status, r.wait_type, r.wait_time, r.command
> from sys.dm_exec_requests r
> where r.blocking_session_id <> 0
> ```
> `blocking_session_id` 即阻塞者（-2=孤儿事务、-3=延迟恢复等特殊值见官方文档）。本文 sysprocesses 写法保留供旧库环境参考。

## 三、查看某会话最后执行的语句（DBCC INPUTBUFFER）

```sql
DBCC INPUTBUFFER (402)   -- 402 = session_id
```

- 返回该会话**最后执行的语句**（event 类型 + 参数 + 语句文本）。
- 当 `sys.dm_exec_requests` 里没有该会话（已执行完）时，用 INPUTBUFFER 看历史最后一条。
- 比跨会话查 sql_handle 更直接，常用于"已知 SPID 反查它在干什么"。

## 四、查询死锁历史记录（system_health 扩展事件）

死锁发生时 SQL Server 自动记录到 `system_health` 扩展事件（.xel 文件）。以下查询读取历史死锁报告：

```sql
DECLARE @xelfilepath NVARCHAR(260)
SELECT @xelfilepath = dosdlc.path
FROM sys.dm_os_server_diagnostics_log_configurations AS dosdlc;
SELECT @xelfilepath = @xelfilepath + N'system_health_*.xel'

DROP TABLE IF EXISTS #TempTable;   -- 兼容多次执行
SELECT CONVERT(XML, event_data) AS EventData
INTO #TempTable
FROM sys.fn_xe_file_target_read_file(@xelfilepath, NULL, NULL, NULL)
WHERE object_name = 'xml_deadlock_report';

SELECT 
    EventData.value('(event/@timestamp)[1]', 'datetime2(7)') AS UtcTime,
    CONVERT(DATETIME, SWITCHOFFSET(
        CONVERT(DATETIMEOFFSET, EventData.value('(event/@timestamp)[1]', 'VARCHAR(50)')),
        DATENAME(TzOffset, SYSDATETIMEOFFSET()))) AS LocalTime,
    EventData.query('event/data/value/deadlock') AS XmlDeadlockReport
FROM #TempTable
ORDER BY UtcTime DESC;
```

### 说明

| 部分 | 作用 |
|------|------|
| `sys.dm_os_server_diagnostics_log_configurations` | 取 system_health 日志目录路径 |
| `sys.fn_xe_file_target_read_file` | 读取 .xel 扩展事件文件 |
| `object_name = 'xml_deadlock_report'` | 只取死锁事件 |
| `CONVERT(XML, event_data)` | 事件数据转 XML，便于 XQuery |
| `SWITCHOFFSET(...)` | UTC 时间转本地时间 |
| `XmlDeadlockReport` | 死锁详情 XML（含 victim process、双方语句、锁资源） |

> 用途：死锁是瞬时发生的，事后排查时 `sp_who_lock`/`sysprocesses` 可能已无记录，system_health 保留历史死锁，是事后定责的关键。

## 五、与现有性能排查手册的分工

| 工具 | 时机 | 见文档 |
|------|------|--------|
| `sys.dm_exec_requests`（本文一） | 实时看正在执行的慢 SQL | 本文 |
| `sysprocesses` 阻塞链（本文二，deprecated） | 实时看谁阻塞谁 | 本文 |
| `DBCC INPUTBUFFER`（本文三） | 按 SPID 反查最后语句 | 本文 |
| `system_health` 死锁报告（本文四） | **事后**查历史死锁 | 本文 |
| `sp_who_lock` | 实时死锁 | `sql-server-performance-troubleshooting.md` |
| 按 SPID 查死锁语句（CROSS APPLY sql_text） | 已知死锁 SPID 定位 SQL | `sql-server-performance-troubleshooting.md` |
| 批量 kill 锁 | 极端情况批量终止 | `sql-server-performance-troubleshooting.md` |

## 六、关联

- SQL Server 性能排查手册（sp_who_lock / kill 锁）：见 `sql-server-performance-troubleshooting.md`
- 游标使用：见 `sql-cursor-usage.md`
- FOR XML PATH 列转行 / 分页查询：见 `sql-xml-path-and-paging.md`
- 按关键词查找存储过程：见 `sql-search-procedure-by-keyword.md`
