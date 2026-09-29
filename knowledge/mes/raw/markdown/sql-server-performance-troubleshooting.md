---
category: 技术-数据库
factory: 通用
module: 通用
status: active
tags:
- SQL Server
- 性能优化
- 存储过程
- 动态SQL
- 日期范围
- 覆盖索引
- INCLUDE
- sp_helpindex
- sys.index_columns
- 冗余索引
- 隐式转换
- SARGable
- varchar日期
- 索引判定
- expert-sql审查
title: SQL Server 性能排查与优化操作手册
updated: '2026-09-03'
---

# SQL Server 性能排查与优化操作手册

> SQL Server 性能排查与优化操作手册：慢查询定位、内存授予、临时表、执行计划等主题的排查路径与优化手段，适用系统卡顿/接口变慢/慢查询/高 CPU 场景。

## 一、适用范围
本手册适用于以下场景：
- 系统运维
- 系统卡顿
- 接口响应变慢
- SQL 执行缓慢
> 日常运维成本远低于故障处理成本，请每月做好日常运维和检查工作！
---

## 二、性能检查

### 1. 查询数据库 CPU 占用高的语句

```sql
SELECT TOP 10 
    s.session_id AS spid,
    r.status,
    r.command,
    r.cpu_time,
    r.logical_reads,
    r.reads,
    r.writes,
    r.total_elapsed_time / (1000 * 60) AS elapsed_min,
    SUBSTRING(st.text,
        (r.statement_start_offset / 2) + 1,
        ((CASE r.statement_end_offset
            WHEN -1 THEN DATALENGTH(st.text)
            ELSE r.statement_end_offset
        END - r.statement_start_offset) / 2) + 1
    ) AS running_sql,
    st.text AS batch_sql,
    s.login_name,
    s.host_name,
    s.program_name,
    r.open_transaction_count
FROM sys.dm_exec_sessions s
JOIN sys.dm_exec_requests r 
    ON r.session_id = s.session_id
CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) st
WHERE s.session_id <> @@SPID
ORDER BY r.cpu_time DESC;
```

**说明**：实时查询 CPU 占用最高的语句，对占用高的语句进行优化，故障情况下考虑暂停相关业务。

---

### 2. 数据库慢 SQL 查询

```sql
SELECT TOP 100
    ST.text AS '执行的SQL语句',
    QS.execution_count AS '执行次数',
    QS.total_elapsed_time AS '耗时',
    QS.total_logical_reads AS '逻辑读取次数',
    QS.total_logical_writes AS '逻辑写入次数',
    QS.total_physical_reads AS '物理读取次数',
    QS.creation_time AS '执行时间',
    QS.*
FROM sys.dm_exec_query_stats QS
CROSS APPLY sys.dm_exec_sql_text(QS.sql_handle) ST
WHERE QS.creation_time > '2026-01-12 18:40:00'  -- 可调整时间范围
ORDER BY total_elapsed_time DESC
```

**说明**：查询指定时间范围内，执行时间最长的语句。除关注总执行时间外，还要关注执行次数和平均每次执行时间。对慢 SQL 进行优化；如果 SQL 不慢，只是执行次数多，要检查作业、接口、服务等调用频率，对不合理的执行频率进行调整。

---

### 3. 死锁查询

```sql
Exec sp_who_lock
```

**说明**：查询当前正在死锁的语句，查询结果为实时状态。有些死锁可能是瞬时的，下次查询就消失了，这种不用关心，重点关注多次查询后频繁存在死锁的表和语句。

> 如果系统出现故障，极端情况下可以执行以下语句生成 kill 语句并复制到新窗口执行，批量杀死锁。但因为中止进程，会有风险造成业务数据不一致。

```sql
SELECT 'kill '+Convert(varchar(10),request_session_id) spid,
       OBJECT_NAME(resource_associated_entity_id) tableName
FROM sys.dm_tran_locks
WHERE resource_type='OBJECT'
```

---

### 4. 根据 SPID 查询死锁语句

```sql
SELECT 
    req.session_id AS [SPID],
    req.status,
    req.command,
    SUBSTRING(txt.text, (req.statement_start_offset/2)+1, 
        ((CASE req.statement_end_offset 
            WHEN -1 THEN DATALENGTH(txt.text)
            ELSE req.statement_end_offset 
        END - req.statement_start_offset)/2) + 1) AS [正在执行的SQL],
    txt.text AS [完整批处理文本],
    req.cpu_time,
    req.reads,
    req.writes,
    req.start_time
FROM sys.dm_exec_requests req
CROSS APPLY sys.dm_exec_sql_text(req.sql_handle) AS txt
WHERE req.session_id = @YourSPID;  -- 在此处替换为你要查询的实际SPID
```

**说明**：根据查出的死锁 SPID 查询死锁语句。如果第三部分杀死锁后，死锁仍然反复出现，可以根据 SPID 查到具体 SQL 进行优化。

---

## 三、语句优化原则

### 1. 尽量缩小数据查询范围

- **（1）** 对于业务数据，尽量添加时间范围条件，非必要情况下，不能查询全表。例如，查询未硫化胎胚，不能直接 `BPM_PRODUCTION` 和 `CPP_CURING_PRODUTION` 全表作对比，推荐方式：`BPM_PRODUCTION` 增加是否硫化字段，或者 `BPM_PRODUCTION` 和 `CPP_CURING_PRODUTION` 只对比最近半个月的差异。
- **（2）** 对于多个大表之间 join 的，如果没有胎号等数据约束性极强的关联字段，可以先根据状态或时间，缩小单表数据范围后再做 join。

### 2. 禁止字段上有函数处理

```sql
-- ❌ 错误示例
WHERE CONVERT(date, create_time) = '2026-01-01'

-- ✅ 正确示例
WHERE create_time >= '2026-01-01'
-- 或
WHERE create_time >= DATEADD(day, 1, '2026-01-01')
-- 或
WHERE create_time >= DATEADD(day, 1, @start_date)
```

### 3. 控制 join 表的数量

没有必要 join 的表不要 join，一个表能取到的字段就不要从两个表取。

### 4. 禁止 select * 或 count(字段)

手写的 SQL 语句，Select 要指明字段；统计行数时用 `count(1)` 或 `count(*)`，不要用 `count(字段名)`。`count(字段名)` 的语义是统计该字段**非 NULL** 的行数：可用的索引比 `count(*)` 少（要求索引覆盖该列），通常更慢；且多数业务场景要的是总行数而非非 NULL 行数——语义与性能双重偏差。（2026-08-28 勘误：原文"会全表扫描"表述过重——优化器也可选该列最窄的非聚集索引，并非必然全表扫；规范导向不变。）

### 5. 隐式类型转换

有些语句手动执行感觉并不慢，但实际占用资源较高。除了执行次数多以外，还有可能传入参数发生了隐式类型转换。比如我们手写的语句查询条件 `where state='1'`，state 的字段类型是 varchar，手动执行没问题；但是程序里面如果给这个条件赋值是 int 类型，那么就会发生隐式类型转换，有可能造成性能变差。

### 6. 执行计划

低性能语句可以通过 SSMS 的执行计划查看索引使用情况，可以结合提示的索引建议和已有的索引，合理地创建索引。

---

## 四、索引优化原则

### 1. 索引不是越多越好

数据库每次增删改都会维护索引，索引越多，增删改的速度越慢，而且索引和数据一样会占用存储空间。所以索引在满足需要的前提下，数量要尽量控制，能复用的尽量复用。

### 2. 哪些字段需要建索引

- **（1）** 数据量在一万以内的表通常不需要建索引，大数据量和高频查询的表需要建索引；
- **（2）** `where`、`order by`、`join` 的字段通常可以建索引，但不是所有都需要建；
- **（3）** 给选择性高的列建索引。比如查询条件是 `record_time + equipCode + deleteFlag`，那么 `record_time` 一定要建索引，`DeleteFlag` 不需要建索引，`equipCode` 根据实际情况，如果 `record_time` 已经能过滤绝大部分数据，那么 `equipCode` 可以不建。

### 3. 索引复用

例如，有复合索引 `(tyreNo, Deleteflag)`，那么查询条件是 `tyreNo + Deleteflag` 或 `tyreNo` 都会走这个索引，所以当只有 `tyreNo` 一个查询条件时，没有必要再单独建 `tyreNo` 的索引。但是根据最左原则，只有 `Deleteflag` 条件时不会走该索引。

> 因此根据执行计划的建议创建索引时，如果新索引能够覆盖旧的索引，需要及时把旧索引删除。

### 4. 高区分度字段建索引

不管是单独索引还是复合索引，建立时要根据数据分布特征，选择高区分度的字段建立索引。例如，一个表的 `deleteFlag` 字段，如果绝大部分值都是 0，极个别是 1，查询条件只有 `DeleteFlag=0`，那么单独建一个 `DeleteFlag` 字段的索引通常是没有效果的，依然会全表扫描。

### 5. 定时重新组织索引

索引建立之后不是一劳永逸，随着数据的增删改，索引会产生大量碎片，造成索引失效，所以需要定期重新组织索引。SQL Server 有相应的维护计划，可以每周或每月执行一次。重新组织索引不会锁表，不会对业务产生影响。对于数据量极大的表，如果重新组织索引没有效果，可以重新生成索引，但是重新生成索引可能会锁表。


## 五、补充关联（反向链接）

| 文档 | 说明 |
|------|------|
| `sql-partition-and-log-shrink.md` | 表分区 + 日志收缩（DBA 运维） |
| `pb-daily-job-architecture.md` | 生产实绩看板每日数据生成作业（Agent Job） |

---

## 六、语句优化原则（补充）

> 以下几条是对前述「语句优化原则 1~6」的补充，均为业界公认但在本手册此前未明确写出的要点。检索自业界最佳实践（Brent Ozar / Microsoft Learn / SQLShack / Red Gate Simple Talk 等），并结合本系统业务表（如 `BPM_PRODUCTION`、`CPP_CURING_PRODUCTION`）的常见查询场景整理。

### 7. 参数嗅探（Parameter Sniffing）

存储过程第一次执行时，SQL Server 会用**当时的参数值**（被"嗅探"）生成执行计划并缓存。之后无论传什么参数，都复用这个计划。当不同参数对应的数据量差异很大时（如某机台只有 10 条、另一机台有 10 万条），针对小数据量生成的计划跑大数据量会很慢，反之亦然。

**典型场景**：带多个可选查询条件、用 `ISNULL(@param,'') = '' OR 字段 = @param` 兼容写法的存储过程（本系统报表查询大多如此）。

**判断方法**：
- 同一存储过程，有时快有时慢，且与参数取值相关；
- 执行计划缓存中该存储过程有多个版本（`sys.dm_exec_query_stats` 中 `query_hash` 相同但 `plan_hash` 不同）；
- 用 `sp_recompile` 或 `OPTION (RECOMPILE)` 重编译后变快 → 基本可确认是参数嗅探。

### 8. 覆盖索引与 INCLUDE 列（消除 Key Lookup）

「索引优化原则」讲了**哪些字段建索引**，但没讲如何让索引"覆盖"查询、避免回表。这是从「能走索引」到「真正快」的关键一跃。

**Key Lookup（键查找）**：非聚集索引找到了行定位，但 SELECT / JOIN 还需要索引里没有的列，于是**再次回聚集索引（或堆）取数据**。一次查询里成千上万次 Key Lookup，是执行计划里最常见的隐性性能杀手。

**覆盖索引**：把查询需要的所有列都放进非聚集索引，消除回表。用 `INCLUDE` 列实现：

```sql
-- 假设高频查询：WHERE GREEN_TYRE_NO = ? 需要 SELECT GREEN_TYRE_NO, MATERIAL_CODE, REAL_WEIGHT
-- ❌ 普通索引：只支持 SEEK，SELECT 其他列仍要 Key Lookup
CREATE NONCLUSTERED INDEX IX_BPM_GREEN_TYRE_NO ON BPM_PRODUCTION(GREEN_TYRE_NO);

-- ✅ 覆盖索引：把 SELECT 需要的列放 INCLUDE，消除 Key Lookup
CREATE NONCLUSTERED INDEX IX_BPM_GREEN_TYRE_NO ON BPM_PRODUCTION(GREEN_TYRE_NO)
    INCLUDE (MATERIAL_CODE, REAL_WEIGHT, SHIFT_DATE);
```

**Key 列 vs INCLUDE 列的区别**（Brent Ozar 的说法：两者叶子页占用空间一样，区别在"作用"）：
- **Key 列（索引键列）**：参与排序、可用于 SEEK / WHERE / ORDER BY。建在最左前缀。
- **INCLUDE 列（包含列）**：仅存于叶子页，不参与排序，只为"覆盖"查询、避免回表。把只 SELECT 不过滤的列放这里。

**判断是否有 Key Lookup**：执行计划里出现 `Key Lookup`（聚集索引表）或 `RID Lookup`（堆表）算子，且成本占比高 → 用 INCLUDE 列消除。

### 9. 参数嗅探的三种解法

针对第 7 条参数嗅探，有三种主流应对方式，各有取舍：

| 方式 | 做法 | 优点 | 缺点 |
|---|---|---|---|
| **`OPTION (RECOMPILE)`** | 每次执行都重新编译计划 | 永远用当前参数的最优计划 | 每次编译有 CPU 开销；高频小查询不建议 |
| **本地变量** | 把参数赋给 `DECLARE` 的局部变量后再用 | 不嗅探，用"通用"平均计划；稳定 | 对任何一组参数都不一定最优 |
| **`OPTION (OPTIMIZE FOR UNKNOWN)`** | 提示优化器按"未知"处理 | 等价本地变量效果，写法更明确 | 同上 |

**选择建议**：
- 数据量分布均匀、参数差异不大 → **不用处理**，默认计划复用即可。
- 参数对应数据量差异极大、查询又不那么高频 → 加 `OPTION (RECOMPILE)`。
- 查询非常高频、不想要每次编译开销 → 用**本地变量**或 `OPTIMIZE FOR UNKNOWN` 换稳定。

```sql
-- 本地变量法示例（本项目兼容写法可改造成这样，避免嗅探）
DECLARE @gt varchar(20) = @GREEN_TYRE_NO;
... WHERE (@gt IS NULL OR GREEN_TYRE_NO = @gt) OPTION (OPTIMIZE FOR UNKNOWN);
```

### 10. `ISNULL(@param,'') = '' OR 字段 = @param` 对索引的影响

本系统报表查询大量使用这种"参数为空则不过滤"的兼容写法。需要清楚它的代价：

- **这种写法本身是 SARGable 的**（OR 的两个分支，优化器一般能识别"参数为空走全表、参数非空走索引"）。但它**依赖参数嗅探**：第一次传空值 → 计划走全表扫描并缓存 → 后续传具体值也用全表扫描计划 → 变慢。这正是第 7 条参数嗅探的高发地带。
- **更稳妥的等价写法**：把"是否过滤"拆开，让非空时能明确走索引。

```sql
-- 依赖嗅探（可能慢）
WHERE (ISNULL(@GREEN_TYRE_NO,'') = '' OR GREEN_TYRE_NO LIKE @GREEN_TYRE_NO + '%')

-- 配合 OPTION (RECOMPILE)，每次按实际参数选计划
WHERE (ISNULL(@GREEN_TYRE_NO,'') = '' OR GREEN_TYRE_NO LIKE @GREEN_TYRE_NO + '%')
OPTION (RECOMPILE);
```

> 经验：报表类查询（参数组合多变、单次查询不算极高频）加 `OPTION (RECOMPILE)` 往往利大于弊。

### 11. 统计信息（Statistics）陈旧

索引篇讲了"定时重组索引"，但**统计信息**是另一个独立维度。统计信息记录列值分布，优化器据此估算行数、选执行计划。统计信息陈旧 → 估算行数严重偏差 → 选错索引 / 选错 JOIN 类型（本该 Hash Join 却用 Nested Loop）。

**现象**：执行计划里 `Estimated Number of Rows`（估算行数）与 `Actual Number of Rows`（实际行数）差一个数量级以上。

**处理**：
- 手动更新：`UPDATE STATISTICS BPM_PRODUCTION;`（单表）或 `EXEC sp_updatestats;`（全库）；
- 自动维护：数据库默认开启"自动更新统计信息"，但大数据量时触发阈值高，可配合维护计划定期更新；
- 与重组索引一起做：重建索引会自动更新统计信息，重组索引**不会**，需单独 `UPDATE STATISTICS`。

---

**关联阅读**：
- 语句优化原则 1~6：见本手册同章节前文；
- SARGable 谓词（对应第 2 条"禁止字段套函数"的业界术语）：查询条件要能让优化器利用索引；
- 参数嗅探的底层机制（计划缓存与复用）：见 [Microsoft Learn - 查询处理架构指南](https://learn.microsoft.com/en-us/sql/relational-databases/query-processing-architecture-guide)。

---

## 七、实战案例：STRING_AGG 多层派生表导致内存授予虚高（实测 250MB → 8MB）

> 本案例展示了「授予_MB 远大于 实际使用_MB」的典型根因与治本方案。问题不在参数嗅探、不在统计信息，而在 **SQL 结构本身**——多层派生表（subquery）内嵌 STRING_AGG，优化器对"不定长字符串拼接后的中间结果"悲观估算，导致内存授予虚高约 30 倍。

> 📌 **版本前提（2026-08-28 补）**：`STRING_AGG` 需 SQL Server **2017+**（`DROP TABLE IF EXISTS` 需 2016+）。MES 项目族各库版本可能不统一，使用前先 `select @@version` 确认；低版本库用 `FOR XML PATH('')` 替代聚合拼接。

### 1. 现象

某报表查询（`Ppt_Lot` 为驱动，4 个 LEFT JOIN 子查询分别按物料类别聚合 NP 胶/粉剂/返回胶/橡胶，每个子查询内部都用 STRING_AGG 拼接）执行计划异常：

| 指标 | 值 |
|------|-----|
| GrantedMemory（实际授予） | 255,584 KB ≈ **250 MB** |
| MaxUsedMemory（实际使用） | 23,648 KB ≈ 23 MB |
| SerialDesiredMemory（优化器想要） | 142,472 KB ≈ 139 MB |
| 浪费倍数 | 授予 ≈ 实际使用的 **10.8 倍** |

实例并发查询时，单条查询吃 250MB 授予，直接放大 buffer pool 压力。

### 2. 排查过程与误区（重要）

> ⚠️ 本案例排查中走过的弯路，可作为排错时的「先排除」清单。

- **误区一：以为是参数嗅探**。原查询已有 `OPTION (RECOMPILE)`，且无 `ISNULL(@p,'')='' OR 字段=@p` 兼容写法，非嗅探问题。
- **误区二：以为是隐式类型转换**。执行计划确实报 `CONVERT_IMPLICIT`（`char` 字段 `Mkind_code` 用了数字字面量 `IN (3,4,5)`）。改成字符串 `IN ('3','4','5')` 后，警告消失、估算行数从 11 万降到 1280，**但 SerialDesiredMemory 纹丝不动（仍 139MB）**。说明转换警告虽真实存在，却不是授予虚高的主因。
- **误区三：以为是统计信息陈旧**。执行 `UPDATE STATISTICS` 涉及的所有表，SerialDesiredMemory 仍不变。说明统计信息无问题。
- **关键判据**：连续两轮（改转换、更新统计）SerialDesiredMemory 都不动，说明**根因是结构性的**，不是数据/估算层面的。

### 3. 真正根因

4 个子查询都是**派生表（subquery）**，内部直接 STRING_AGG：

```text
外层 FROM Ppt_Lot pt
  LEFT JOIN (子查询 np：STRING_AGG)   -- 里面又 FROM Ppt_Lot 全量
  LEFT JOIN (子查询 fj：STRING_AGG)   -- 同上
  LEFT JOIN (子查询 re：STRING_AGG)   -- 同上
  LEFT JOIN (子查询 xj：STRING_AGG)   -- 同上
```

问题：
1. **派生表不物化**，优化器要估算"STRING_AGG 后这个派生表有几行、每行字符串多长" → 它估不准 → 悲观预留大量内存；
2. **STRING_AGG 输出长度不可预测**，优化器只能按保守上界给授予；
3. 4 层叠加，每层保守估算的偏差被放大。

统计信息和参数嗅探都救不了这种"结构性的字符串聚合估算困难"。

### 4. 治本方案：明细先落临时表，再做 STRING_AGG

把每个子查询拆成两步——**先 SELECT INTO 临时表（行数确定、字段定长、自动生成统计信息），再在临时表上做 STRING_AGG**：

```sql
/* 0. 驱动集 */
SELECT Plan_Id, Serial_Id, Barcode, Mater_Name, Start_Datetime, RECORD_TIME, BWB_TIME
INTO   #Lot
FROM   mens.dbo.Ppt_Lot
WHERE  Start_Datetime BETWEEN @StartTime AND @EndTime
  AND  Equip_Code = @EquipCode;

/* 1~4. 每类物料明细各落一个临时表（示例：NP 胶）*/
SELECT DISTINCT PT.Plan_Id AS plan_id, pw2.mater_name AS NP_name,
       pb2.Prod_Time AS NP_prod_time,
       CONVERT(varchar(20), pb2.Barcode_start) + '-' + CONVERT(varchar(20), pb2.Barcode_end) AS NP_BT
INTO   #NPDetail
FROM   #Lot pt
JOIN (...) PW2 ON pt.Barcode = pw2.Barcode
JOIN (...) pb2 ON PT.Plan_Id = PB2.planid AND ...;
-- #FJDetail / #REDetail / #XJDetail 同理

/* 5. 最终输出：在小临时表上做 STRING_AGG */
SELECT PT.Mater_Name AS 胶料号码, COUNT(pt.mater_name) AS bt数量, ...
FROM #Lot pt
LEFT JOIN (
    SELECT plan_id,
           STRING_AGG(NP_name,'|') AS NP_name,
           STRING_AGG(CONVERT(CHAR(10),NP_prod_time,120),'|') AS NP_prod_time,
           STRING_AGG(NP_BT,'|') AS NP_BT
    FROM #NPDetail GROUP BY plan_id
) np ON PT.Plan_Id = np.plan_id
-- 其余三类同理
GROUP BY pt.Plan_Id, PT.Mater_Name
ORDER BY 开始时间
OPTION (RECOMPILE);

DROP TABLE #NPDetail; DROP TABLE #FJDetail; DROP TABLE #REDetail; DROP TABLE #XJDetail; DROP TABLE #Lot;
```

**为什么有效**：
- 临时表是物化的，行数确定、字段定长，优化器看到的就是"小表按 plan_id 分组"；
- 临时表自动生成统计信息，估算有据；
- STRING_AGG 的输入从"全表 JOIN 后的不可预测中间结果"变成"确定的小临时表"。

### 5. 实测效果

| 指标 | 优化前 | 方案 A 后（最终 SELECT 根节点） | 变化 |
|------|--------|-------------------------------|------|
| GrantedMemory | 250 MB | **8 MB** | **↓ 97%** |
| MaxUsedMemory | 23 MB | **0.05 MB（48 KB）** | ↓ ~99.8% |
| SerialDesiredMemory | 139 MB | 同步坍缩 | — |

授予从 250MB 砍到 8MB，实际使用仅 48KB。单条查询不再构成实例内存压力。

### 6. 排查方法论（可复用）

遇到「授予 ≫ 实际使用」、且改参数嗅探/统计信息/隐式转换都无效时：

1. **用实际执行计划（Ctrl+M + F5）**，不要用估计计划——临时表统计信息、实际行数只有实际计划才真实；
2. **注意多根节点**：含 `SELECT INTO` 的脚本每条语句各画一个根节点，**只有最终输出的 SELECT 根节点才看授予**，建临时表的节点不用看；
3. **找最粗箭头 / Sort / Hash Match 节点**，定位是哪个算子在撑大授予；
4. **判断根因是否结构性**：连续改两轮（转换、统计）授予不动 → 大概率是结构（多层派生表 / 嵌套聚合）→ 走"物化临时表"方案。

### 7. 关联

- 「授予_MB 远大于 实际使用_MB」的解读方向：见本文档「内存占用高的语句查询」一节；
- 隐式类型转换（本案例的副因）：见「语句优化原则 5」；
- 参数嗅探（本案例的排除项）：见「语句优化原则 7、9」；
- `OPTION (RECOMPILE)` 的适用：见「语句优化原则 9」。

---


## 八、实战案例：索引清单先行——CuringPlanExecute 覆盖索引补一列（2026-09-03）

> 拟建索引 DDL 前，先用固定 SQL 拿到相关表的**现有索引清单（键列+INCLUDE 列）与行数基线**。本案例最初凭行数提的两条 CREATE INDEX，拿到清单后一条改判"重建现有索引+追加一个 INCLUDE 列"、一条直接取消——只看行数就出 DDL 必然建重复索引。

### 8.1 案例背景

计划执行页 `Plugins/Curing/ProductPlan/CuringPlanExecute`（Curing）查询升级日期范围后对 `SelectExecutePlan@CppCuringPlan` 体检：主链路表均万行级（CPP_CURING_PLAN 1.5 万、CPP_CURING_PLAN_DETAIL 3 万）无需任何动作；热点有二：`d` 子查询每次执行对 BPM_PRODUCTION（100.8 万行）扫 `RECORD_TIME > GETDATE()-200` 窗口聚合，二维码分支对 CPP_CURING_PRODUCTION（99.5 万行）做 `TYRE_NO LIKE 'xxx%'`。

### 8.2 排查用 SQL（交用户执行，遵守连库禁令）

```sql
-- 行数基线（万行以内表直接跳过索引话题）
SELECT t.name, SUM(p.rows) AS row_cnt
FROM sys.tables t JOIN sys.partitions p ON t.object_id = p.object_id AND p.index_id IN (0,1)
WHERE t.name IN ('CPP_CURING_PLAN','CPP_CURING_PRODUCTION','BPM_PRODUCTION')
GROUP BY t.name;
```

```sql
-- 现有索引清单（键列 + INCLUDE 列，判断复用/缺口）
SELECT t.name AS table_name, i.name AS index_name,
       STUFF((SELECT ','+c.name FROM sys.index_columns ic
              JOIN sys.columns c ON ic.object_id=c.object_id AND ic.column_id=c.column_id
              WHERE ic.object_id=i.object_id AND ic.index_id=i.index_id AND ic.is_included_column=0
              ORDER BY ic.key_ordinal FOR XML PATH('')),1,1,'') AS key_cols,
       STUFF((SELECT ','+c.name FROM sys.index_columns ic
              JOIN sys.columns c ON ic.object_id=c.object_id AND ic.column_id=c.column_id
              WHERE ic.object_id=i.object_id AND ic.index_id=i.index_id AND ic.is_included_column=1
              FOR XML PATH('')),1,1,'') AS include_cols
FROM sys.tables t JOIN sys.indexes i ON t.object_id=i.object_id
WHERE t.name IN ('CPP_CURING_PLAN','CPP_CURING_PRODUCTION','BPM_PRODUCTION');
```

### 8.3 清单实查后的翻案

| 拟建 DDL | 实查后改判 | 依据 |
|------|-----------|------|
| BPM_PRODUCTION (RECORD_TIME) INCLUDE 4 列 | **重建现有 IX_BPM_PROD_RECORDTIME，仅追加 IS_CONSUMED** | 已有同键索引 INCLUDE 11 列，覆盖子查询所需全部列唯独缺 IS_CONSUMED → 200 天窗口每行 RID Lookup 回 HEAP；新建则与之重复 |
| CPP_CURING_PRODUCTION (TYRE_NO) INCLUDE (PLAN_DETAIL_ID) | **取消** | 已有 INDEX_TYRE_NO (TYRE_NO) INCLUDE 7 列，前缀 LIKE 直接受益；缺 PLAN_DETAIL_ID 但单次命中 1-2 行回表可忽略 |
| CPP_CURING_PLAN 日期索引 | 无需 | 已有 INDEX_PLAN_INFO (PLAN_DATE,SHIFT_CODE,EQUIP_CODE)；且仅 1.5 万行（万行以内通常不建） |

```sql
-- 补一列的重建 DDL（索引复用实例，待用户执行）
DROP INDEX IX_BPM_PROD_RECORDTIME ON dbo.BPM_PRODUCTION;
CREATE NONCLUSTERED INDEX IX_BPM_PROD_RECORDTIME
ON dbo.BPM_PRODUCTION (RECORD_TIME)
INCLUDE (OBJID, DELETE_FLAG, GREEN_TYRE_NO, MATERIAL_CODE, TYRE_MATERIAL_NAME, EQUIP_ID,
         SHIFT_CODE, CLASS_CODE, BEGIN_TIME, MOLD_OPER, IS_LOCK, IS_CONSUMED)
WITH (FILLFACTOR = 90, ONLINE = ON);   -- Standard 版去掉 ONLINE，选低峰建
```

要点：**覆盖索引缺一个残留谓词列 = 整窗逐行回表**；往现有 INCLUDE 追加一列即闭环，不新建重复索引（对应「四、索引优化原则 3 索引复用」）。`ISNULL(IS_CONSUMED,'0')='0'` 虽非 SARG，该列进索引后只是索引内残留过滤，无需改写 SQL。

### 8.4 顺手项：删中转临时表

原语句"CTE → into 临时表 → 再 select 回来"三段式，合并为对 CTE 单次 SELECT 直出（`row_number()` 内联到输出列第二位，列名列序不变），省一次 tempdb 写+读回。适用于千行级报表语句；更大结果集先权衡。注意 mapper 里临时表必须写 `##`（iBATIS 字面量转义，DB 端是本地 `#` 表），详见 extnet-query-control-upgrade.md 第九章。

### 8.5 关联

- 本文档「四、索引优化原则」「语句优化原则 8 覆盖索引」
- extnet-query-control-upgrade.md 第七章/第八章：本页日期范围四件套与 Curing 落地

---

---

## 八、实战案例：计划执行日期范围改造的索引与类型判定（2026-09-03）

> 成型「计划执行」页（MoldingPlanExecute）查询从单日改日期范围时，对存储过程 `PROC_BPM_SELECT_EXECUTE_PLAN` 做 expert-sql 审查 + 用户连库核实索引/列类型的完整判定实录。已上线验证通过。改造套路见 `extnet-query-control-upgrade.md` 第八/九章，本节沉淀**SQL 侧判定经验**。

### 8.1 sp_helpindex 看不到 INCLUDE 列——判覆盖索引必须用 sys.index_columns

`sp_helpindex` 第三列只显示**键列**，INCLUDE 列完全不显示。本例两个同以 PLAN_DATE 打头的索引：`INDEX_PLAN_INFO(PLAN_DATE,SHIFT_CODE,EQUIP_CODE)` 键列三枚无 INCLUDE；`IX_BPM_MOLDING_PLAN_DATE(PLAN_DATE)` 表面像被前者前缀覆盖（冗余），sys.index_columns 一查实为 **INCLUDE(PLAN_ID,EQUIP_CODE,SHIFT_CODE,REMARK) 的覆盖索引**——是范围查询的零回表驱动索引，必须保留。**判冗余前先查 INCLUDE，否则误删覆盖索引**：

```sql
SELECT i.name AS index_name, c.name AS column_name, ic.is_included_column
FROM sys.indexes i
JOIN sys.index_columns ic ON i.object_id=ic.object_id AND i.index_id=ic.index_id
JOIN sys.columns c ON ic.object_id=c.object_id AND ic.column_id=c.column_id
WHERE i.object_id=OBJECT_ID('dbo.表名') AND i.name IN ('索引A','索引B')
ORDER BY i.name, ic.is_included_column;
```

### 8.2 冗余索引的三种判定模式（本例实证）

| 模式 | 本例 | 处置 |
|------|------|------|
| 同列纯重复 | `INDEX_PIANID(PLAN_ID)` 与新建分区对齐 `IX_..._PLANID(PLAN_ID)` | 删旧的（留分区对齐 PS_* 上的） |
| 与唯一主键完全重复 | `IX_BPM_PRODUCTION_GREEN_TYRE_NO` 而 GREEN_TYRE_NO 本身就是非聚集唯一主键 | 删（等值 Seek 走主键索引即可） |
| 前缀覆盖假象 | 见 8.1——键列被覆盖但带 INCLUDE | **不删**，覆盖索引与复合键索引职责不同 |

**覆盖索引 vs 复合键索引不互冗余**：INCLUDE 列只能"陪读"（消除回表），不能参与 Seek；SHIFT_CODE/EQUIP_CODE 放键列（三列等值精确 Seek）与放 INCLUDE（日期范围内叶级过滤）服务不同访问模式，两者共存是常态。

### 8.3 varchar 存 yyyy-MM-dd 的日期列：范围比较安全

`BPM_MOLDING_PLAN.PLAN_DATE` 是 `varchar(10)` 存 `yyyy-MM-dd`——ISO 格式字符串**字典序=时间序**，`>= 开始 AND <= 结束` 结果正确、列上无函数、SARGable 可走索引范围 Seek。此类列做日期范围改造**不需要 CAST 成 date**（CAST 反而破坏 SARGable）；前提是存量数据格式严格统一（既有单日等值查询正常即是佐证）。

### 8.4 bigint=bigint 的 join 去掉 convert 恢复 SARGable

原二维码分支 `convert(varchar,t2.OBJID) = (select PLAN_DETAIL_ID from BPM_PRODUCTION where GREEN_TYRE_NO=...)`——sys.columns 核实两侧均为 **bigint** 后，`convert(varchar)` 纯属多余且令明细表只能全表扫；去掉后 `t2.OBJID = (子查询)` 直接走 OBJID 唯一索引。GREEN_TYRE_NO 为该表唯一主键 → 标量子查询必单行，`=` 无多行报错风险。**函数包列先查两侧真实类型再定去留**。

### 8.5 varchar 列 = date 列的 join：小维度表不必动

`PLAN_DATE(varchar) = SSB_SHIFT_TIME.ShiftDT(date)` 按类型优先级逐行隐转 varchar 侧，但班次时间表是每天每班一条的小维度表，逐行转换代价可忽略——为工作正常的 join 动刀不值。隐转的实际危害在大表扫描/join 场景，小维度表上"知道即可不处理"。

### 8.6 审查流程教训（呼应本文档既有原则）

- SQL 重交付（含 proc 改造）默认 expert-sql 审查：本次 byte 级核验抓出转写多一个引号的 P0（ALTER 必编译失败 + 8 参数传旧 proc 连锁 8144），详 `extnet-query-control-upgrade.md` §九
- 手打/复写 proc 体后必须与原始导出件 difflib 逐行 diff，偏差逐条对应"有意改动清单"