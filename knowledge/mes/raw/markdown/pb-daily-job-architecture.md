---
title: 生产实绩看板每日数据生成作业（架构 + 存储模式 + 优化套路）
category: 技术-数据库
module: 通用
factory: 通用
tags: [生产实绩看板, ProductionBoard, 试作胎, 胎号第6位Z, CPP_CURING_PRODUCTION, BPM_PRODUCTION, SUBSTRING, 口径, SSP_PB_CELL_DATA, Proc_PB_GenerateDailyData]
updated: 2026-09-16
status: active
---

# 生产实绩看板每日数据生成作业（架构 + 存储模式 + 优化套路）

> 看板页面（`ProductionBoard.aspx`，31×31 网格，446+ 单元格）的数据来源有两种：
> - **导入格**：用户双击手填
> - **查询格**：SQL Server Agent Job 每天定时跑存储过程 `Proc_PB_GenerateDailyData`，从业务表聚合算值写入 `SSP_PB_CELL_DATA`
>
> 本文沉淀这套每日作业的**整体架构、存储模式设计、SQL 优化套路**。单元格编辑/底色/前端回填的踩坑见 `extnet-tablelayout-cell-edit-pitfalls.md`。

---

## 一、数据表结构：SSP_PB_CELL_DATA

| 字段 | 类型 | 说明 |
|------|------|------|
| OBJID | 主键 | 自增 |
| DATA_DATE | DATE | **看板日期**（维护时看板选的日期） |
| FIELD_KEY | NVARCHAR(20) | 字段标识 `rXcY`（行X列Y，与 Excel 配置表一致） |
| ROT_DATE | DATE | **实际业务日期**（单值格=看板日期；轮询格=上周/本周对应日；月份格=月份1号） |
| CELL_VALUE | NVARCHAR(100) | 单元格值（统一字符串，前端按需转数字/拼接） |
| SOURCE_TYPE | NVARCHAR(10) | `'导入'` / `'查询'`（前端按此刷底色：导入=蓝、查询=绿、只读=灰） |
| RECORD_USER_ID | NVARCHAR(20) | **`'0'`=作业自动生成；用户工号=用户手填/修改** |
| RECORD_TIME | DATETIME | 记录时间 |
| DELETE_FLAG | INT | 删除标记（0） |

### 1.1 RECORD_USER_ID 区分作业 vs 用户（关键约定）

作业重跑当天数据时，只删 `RECORD_USER_ID='0'` 的，用户当天手填/修改的（`RECORD_USER_ID!='0'`）**保留不覆盖**：

```sql
DELETE FROM SSP_PB_CELL_DATA
 WHERE DATA_DATE = @Today
   AND RECORD_USER_ID = '0';   -- 只清作业生成的，用户数据保留
```

写入时再用 `WHERE NOT EXISTS` 排除当天已有记录（双保险，防撞唯一约束）：

```sql
IF NOT EXISTS(SELECT 1 FROM SSP_PB_CELL_DATA WHERE FIELD_KEY='rXcY' AND ROT_DATE=@Today)
INSERT INTO SSP_PB_CELL_DATA (...) SELECT ...;
```

> ⚠️ **踩坑**：早期版本 DELETE 只删 `RECORD_USER_ID='0'`，但 INSERT 没有 NOT EXISTS，用户已维护的 key 又被作业覆盖，还撞唯一约束。**DELETE + NOT EXISTS 双保险是正解**。

---

## 二、三类单元格的存储策略（ROT_DATE 是核心）

| 类型 | 范围 | ROT_DATE | 查询方式 |
|------|------|----------|----------|
| **单值格** | 列 ≤ 16 | = 看板日期 | 按 FIELD_KEY 取最近一条（`GetLatestByKey`，不限 ROT_DATE） |
| **轮询格** | 行 ≤ 23 且列 17-31 | = KeyToRotDate 算出的实际日期 | 按实际日期查（`GetByRotDate` 或行号+日期） |
| **月份格** | 行 25-31，列 15/19/23/25-31 | = 月份1号 | 按 FIELD_KEY + ROT_DATE(月份1号) 精确查 |

### 2.1 为什么用 ROT_DATE 而不是 DATA_DATE

看板是**滚动窗口**（本周一~本周日 + 上周一~上周日），同一格子在不同看板日期下代表**不同的实际日期**。

- 如果用 DATA_DATE 关联值：换看板日期时，值不会自动"跟着日期走"，要做窗口平移搬数据，容易错。
- 用 ROT_DATE（实际业务日期）关联：**值绑在绝对日期上，看板查询时按实际日期匹配到对应列**，切换看板日期时值自动出现在正确位置，不用搬数据。

```text
7/13 填 r1c25（本周一=7/13）= 123 → 存 ROT_DATE=7/13
7/20 看板：
  r1c17 = 上周一 = 7/13 → 按 ROT_DATE=7/13 查 → 123 ✅
  r1c25 = 本周一 = 7/20 → 按 ROT_DATE=7/20 查 → 空（没填过7/20）
```

### 2.2 月份格与看板日期解耦

右下角月份区域（12 个月统计）的值**不随看板日期变化**，每个月固定显示该月数据。所以 ROT_DATE 取**月份1号**：

```sql
DECLARE @MonthFirst DATE = DATEADD(MONTH, DATEDIFF(MONTH, 0, @Today), 0);  -- 当月1号
DECLARE @MonthNext  DATE = DATEADD(MONTH, DATEDIFF(MONTH, 0, @Today) + 1, 0);  -- 下月1号（不含）

-- 当月数据每天覆盖更新（INSERT + UPDATE）
IF NOT EXISTS(SELECT 1 FROM SSP_PB_CELL_DATA WHERE FIELD_KEY=@KeyProd AND ROT_DATE=@MonthFirst)
    INSERT ... SELECT @KeyProd, @Today, @MonthFirst, ...;
ELSE
    UPDATE SSP_PB_CELL_DATA SET CELL_VALUE=..., RECORD_TIME=@Now
     WHERE FIELD_KEY=@KeyProd AND ROT_DATE=@MonthFirst;
```

> 月份格用 **INSERT + UPDATE**（不是 DELETE + INSERT），因为历史月份的数据不能被当月作业清掉，且同一个月的记录要原地更新。历史月份通过单独的初始化脚本 `Init_HistoryMonths.sql` 一次性回填。

---

## 三、作业存储过程骨架（ALTER PROCEDURE 模式）

便于反复执行修改：**先 CREATE 空壳，再 ALTER 覆盖**，避免 DROP 重建丢失权限。

```sql
USE [MES]
GO

-- 不存在时建空壳
IF OBJECT_ID('Proc_PB_GenerateDailyData', 'P') IS NULL
    EXEC('CREATE PROCEDURE Proc_PB_GenerateDailyData AS');
GO

ALTER PROCEDURE Proc_PB_GenerateDailyData
    @BoardDate DATE = NULL    -- 可选传入，默认取前一天（与看板默认日期一致）
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @Today DATE = ISNULL(@BoardDate, DATEADD(DAY, -1, CAST(GETDATE() AS DATE)));
    DECLARE @Now   DATETIME = GETDATE();
    -- ... 后续逻辑
END
```

> ⚠️ 每个 `GO` 之间是独立批次，`ALTER` 必须单独成批。改完直接 F5 全执行就能更新过程定义。

---

## 四、日期/时间变量（班次界定）

工厂班次按 **8:00 ~ 次日 8:00** 算"一天"，不能用自然日 0:00：

```sql
-- 周几算法（不受 SET LANGUAGE / @@DATEFIRST 影响）
DECLARE @DayOfWeek INT = (DATEPART(dw, @Today) + @@DATEFIRST - 1) % 7;
IF @DayOfWeek = 0 SET @DayOfWeek = 7;   -- 转成 1=周一...7=周日
DECLARE @ThisMonday DATE = DATEADD(DAY, 1 - @DayOfWeek, @Today);
DECLARE @LastMonday DATE = DATEADD(DAY, -7, @ThisMonday);

-- "一天" = @Today 的 8:00 ~ 次日 8:00
DECLARE @DayStart DATETIME = DATEADD(HOUR, 8, CAST(@Today AS DATETIME));
DECLARE @DayEnd   DATETIME = DATEADD(HOUR, 8, DATEADD(DAY, 1, CAST(@Today AS DATETIME)));
-- "本月累计"起始 = @Today 所在月的1号 8:00
DECLARE @MonthStart DATETIME = DATEADD(HOUR, 8, DATEADD(MONTH, DATEDIFF(MONTH, 0, @Today), 0));
```

> 关键：**WHERE 字段上不能套函数**（`CONVERT(date, END_TIME)=@Today` 会让索引失效），用 `END_TIME >= @DayStart AND END_TIME < @DayEnd` 范围查。例外：试作胎过滤 `SUBSTRING(胎号,6,1)<>'Z'` 属残余过滤（见十一），驱动谓词仍是时间范围，无损性能。

---

## 五、单值格滚动继承（CROSS APPLY TOP 1）

单值格（导入格）每天从前一天同 key 的值**滚动继承**，只向前找，找不到留空：

```sql
INSERT INTO SSP_PB_CELL_DATA (FIELD_KEY, DATA_DATE, ROT_DATE, CELL_VALUE, SOURCE_TYPE, RECORD_USER_ID, RECORD_TIME, DELETE_FLAG)
SELECT k.FIELD_KEY, @Today, @Today, h.CELL_VALUE, '导入', '0', @Now, 0
  FROM @ImportKeys k
 CROSS APPLY (
     SELECT TOP 1 CELL_VALUE
       FROM SSP_PB_CELL_DATA WITH(NOLOCK)
      WHERE FIELD_KEY = k.FIELD_KEY
        AND ROT_DATE < @Today              -- 只向前（按实际日期）
        AND CELL_VALUE IS NOT NULL
        AND CELL_VALUE <> ''
      ORDER BY ROT_DATE DESC, RECORD_TIME DESC
 ) h
 WHERE NOT EXISTS(                          -- 排除当天已存在的（用户已维护不覆盖）
     SELECT 1 FROM SSP_PB_CELL_DATA WITH(NOLOCK)
      WHERE FIELD_KEY = k.FIELD_KEY AND ROT_DATE = @Today
 );
```

要点：
- `CROSS APPLY` + `TOP 1 ORDER BY ROT_DATE DESC`：取前一天最近一条非空值
- `ROT_DATE < @Today`：只向前继承（补历史数据时不会拿后一天的值）
- 用户改过的值（`RECORD_USER_ID!='0'`）也会被继承（不区分记录人）
- `WHERE NOT EXISTS`：排除当天已存在的 key，避免撞唯一约束、不覆盖用户已维护

---

## 六、查询格聚合临时表复用（最重要的优化套路）

**核心原则**：多个查询单元格如果查同一张业务表，**先聚合到一张临时表，多个 INSERT 共用**，不要每个格子各查一次。

### 6.1 反面教材（每个格子各查一次）

```sql
-- ❌ r6c7 查一次 CPP_CURING_PRODUCTION
INSERT ... SELECT 'r6c7', ... FROM CPP_CURING_PRODUCTION WHERE END_TIME >= @DayStart ...;
-- ❌ r17 又查一次 CPP_CURING_PRODUCTION（同样的条件）
INSERT ... SELECT 'r17', ... FROM CPP_CURING_PRODUCTION WHERE END_TIME >= @DayStart ...;
-- ❌ 月累计再查一次
```

### 6.2 正解：临时表 + 多格共用

```sql
-- 一次查出当天+月累计的废品数、硫化生产数、月均日产
DECLARE @ScrapStats TABLE (
    ScrapCount INT, ProdCount INT,
    ScrapCountMonth INT, ProdCountMonth INT,
    MonthAvgDaily DECIMAL(18,1)
);
INSERT INTO @ScrapStats (ScrapCount, ProdCount, ScrapCountMonth, ProdCountMonth, MonthAvgDaily)
SELECT
    (SELECT ISNULL(COUNT(DISTINCT TYRE_NO), 0) FROM (
        SELECT TYRE_NO FROM FQS_SCRAP_INFO WITH(NOLOCK)
         WHERE RECORD_TIME >= @DayStart AND RECORD_TIME < @DayEnd
         UNION ALL
         SELECT BARCODE FROM FQM_TIRE_MOVE_RECORD WITH(NOLOCK)
         WHERE RECORD_TIME >= @DayStart AND RECORD_TIME < @DayEnd AND DELETE_FLAG=0 AND DEST=4
    ) S),
    (SELECT ISNULL(COUNT(1), 0) FROM CPP_CURING_PRODUCTION WITH(NOLOCK)
      WHERE END_TIME >= @DayStart AND END_TIME < @DayEnd
        AND SUBSTRING(TYRE_NO, 6, 1) <> 'Z'),   -- 试作胎排除，见十一
    -- 月累计（同样带 Z 过滤）...
    0;  -- MonthAvgDaily 占位
UPDATE @ScrapStats SET MonthAvgDaily = CASE WHEN DAY(@Today)=0 THEN 0
    ELSE CAST(ROUND(ProdCountMonth*1.0/DAY(@Today), 1) AS DECIMAL(18,1)) END;

-- 多个格子共用 @ScrapStats
INSERT ... SELECT 'r6c7', ..., CAST(ScrapCount AS NVARCHAR(100)), ... FROM @ScrapStats;
INSERT ... SELECT 'r6c9', ..., CAST(ProdCount AS NVARCHAR(50))+'<br/>/<br/>'+CAST(ScrapCount AS NVARCHAR(50)), ... FROM @ScrapStats;
INSERT ... SELECT 'r17', ..., CAST(ProdCount AS NVARCHAR(100)), ... FROM @ScrapStats;  -- r17 复用硫化产量
```

### 6.3 复用 checklist（每加一段新 SQL 都自检）

| 业务表 | 已聚合到哪个临时表 | 哪些格子共用 | 试作胎过滤 |
|--------|------------------|------------|-----------|
| `CPP_CURING_PRODUCTION` | @ScrapStats.ProdCount（当天）/ ProdCountMonth（月） | r6c9, r6c10(分子), r17, r27c18/r27c21, 月份区 | ✅ 已排除（见十一） |
| `BPM_PRODUCTION` | @r18Prod 变量 | r18 成型产量 | ✅ 已排除（GREEN_TYRE_NO） |
| `FQS_SCRAP_INFO + FQM_TIRE_MOVE_RECORD` | @ScrapStats.ScrapCount / ScrapCountMonth | r6c7, r6c9, r6c10(分母) | ❌ 含试作（拍板保留） |
| `SBE_EQUIP_STOP_RECORD` | @StopStats（按 STOP_REASON_ID 分类） | r2c4, r4c6, r6c6 | 不适用 |
| `FQF_FCHECK_INFO` | @FcheckStats（FcheckMonth CTE） | r9, r10, r6c11, r6c13, r6c14 | ❌ 含试作（拍板保留） |
| `FQB_BALANCE_INFO + FQB_UFCHECK_INFO` | @BalanceStats（UNION 后 ROW_NUMBER 去重） | r13, r14, r15 | ❌ 含试作（拍板保留） |
| `CPP_TYRE_INBOUND_RECORD` | @InboundStats / @InboundMonth | r5/r6/r7, r8, r30c18/r30c21, r31c18/r31c21 | ❌ 含试作（拍板保留） |
| `CPP_TYRE_OUTBOUND_RECORD` | @OutboundStats | r20, r22, r24c20/r24c29, r24c23/r24c31 | ❌ 含试作（拍板保留） |
| `CPP_CURING_PLAN / CPP_CURING_MONTH_PLAN` | @MonthStats / @OrderStats | 月份区操业天数, r24c17/r24c26 | 不适用 |

> ⚠️ 每写一段新 SQL，**先 grep 一下业务表名**，看是否已经在某个临时表查过了，能复用就 `FROM @已有临时表`，不要再 `FROM 业务表`。

---

## 七、字符串值差异计算（PATINDEX 提取数字）

看板很多格子存的是**带单位的字符串**（如 `"本149366"`、`"20 天"`、`"8786.2 本/日"`），算"目标-实绩"差异时要从字符串里**提取数字**：

```sql
-- PATINDEX 找第一个数字位置，SUBSTRING 提取
DECLARE @s NVARCHAR(100) = '本149366';
DECLARE @start INT = PATINDEX('%[0-9]%', @s);              -- 第一个数字位置
DECLARE @numStr NVARCHAR(50) = SUBSTRING(@s, @start, 50);  -- 从该位置截到末尾
-- @numStr 还可能含小数点，用 LIKE '%[^0-9.]%' 截断
DECLARE @end INT = PATINDEX('%[^0-9.]%', @numStr);
IF @end > 0 SET @numStr = LEFT(@numStr, @end - 1);
DECLARE @num DECIMAL(18,1) = CAST(@numStr AS DECIMAL(18,1));
```

差异格子（`r28c18`、`r31c18` 等）= 目标格子值 - 实绩格子值，结果 CAST 回字符串再带单位写回。

> ⚠️ 设计建议：**如果格子值要参与计算，存纯数字字符串，单位用相邻只读格显示**，避免 PATINDEX 提取的脆弱性。本次因为是改造既有看板（值已带单位），才用 PATINDEX 兜底。

---

## 八、轮询格不生成（纯手填）

轮询格（行 ≤ 23 且列 17-31）**作业不生成数据**，原因：
- 轮询格值绑在用户维护时的**实际日期**（ROT_DATE），由 `KeyToRotDate` 算出
- 作业不知道用户想在哪天填什么值
- 看板查询时按实际日期匹配到对应列，用户填过就有，没填过就空

```sql
-- 存储过程里轮询格区域：不生成
-- 轮询格不在此处理（纯手填，值绑在用户维护时的实际日期上，看板按实际日期匹配）
```

查询格里的"轮询查询格"（如 r17/r18 双周轮询硫化/成型产量、r9/r10 双周轮询检查数）是**例外**：这些格子虽然是轮询位置，但值由作业从业务表算出，存 `FIELD_KEY='r'+行号` + `ROT_DATE=实际日期`。

> 注意：**r17 有两套 key**——行号 key `r17`（双周轮询位，硫化产量）、`r17c3~r17c9`（单周轮询位，二检合格且入库）、`r17c10`（UFDB 报废明细普通格），同名不同格，改 SQL 时别混。

---

## 九、调用与重跑

- **定时调用**：SQL Server Agent Job 每天定时 `EXEC Proc_PB_GenerateDailyData`（不传参，默认取前一天）
- **手动补历史**：`EXEC Proc_PB_GenerateDailyData '2026-07-15'` 传入指定日期
- **历史月份初始化**：单独脚本 `Init_HistoryMonths.sql`，循环当年 1 月~当前月-1，每个月算 ProdCount/WorkDays/AvgDaily 写入（ROT_DATE=月份1号）

---

## 十、关联文档

- `extnet-tablelayout-cell-edit-pitfalls.md` — 单元格编辑/DirectMethod 存库/底色刷/前端回填/滚动窗口 KeyToRotDate 的踩坑
- `extnet-desktop-framework-guide.md` — 看板 TableLayout 基础（ColSpan/RowSpan/斜线表头）
- `extnet-directmethod-and-data.md` — DirectMethod 数据访问三件套（SaveCell 后端落库）
- `sql-server-performance-troubleshooting.md` — SQL 优化原则（范围查、无函数、控 JOIN、count(1)）
- `sql-outer-apply-cross-apply.md` — CROSS APPLY 用法（单值格继承）
- `sql-merge-into-upsert.md` — INSERT+UPDATE / MERGE UPSERT 模式（月份格覆盖更新）

---

## 十一、试作胎排除口径（2026-09-16 定稿）

**判定规则（用户口径）**：胎号第 6 位 = `'Z'` 即试作胎，`SUBSTRING(胎号, 6, 1) = 'Z'`（与 Quality 月别合格率趋势页 MonthlyPassRateTrend 的排除条件同源）。硫化表字段 `TYRE_NO`、成型表 `GREEN_TYRE_NO`，同一位同规则。

**最终改动范围（用户多轮收口拍板）：只改硫化 + 成型的产量**，共 3 处物理查询，其余全部保持原样：

| 物理查询 | 表.字段 | 生效格子（自动继承） |
|---------|---------|---------------------|
| @ScrapStats.ProdCount 当天硫化生产数 | CPP_CURING_PRODUCTION.TYRE_NO | r6c9（分子侧）、r17（双周轮询列，硫化产量） |
| @ScrapStats.ProdCountMonth 月累计硫化生产数 | 同上 | r6c10（分子侧）、r27c18/r27c21（当月产量/日均）、月份区当月实绩格（r26~r31 行的 c25/c29 列，按当月动态定位，如 2026-09 = r28c29） |
| @r18Prod 成型产量 | BPM_PRODUCTION.GREEN_TYRE_NO | r18（双周轮询列，成型产量） |

**明确不改（2026-09-16 用户逐项拍板，后续勿再扩展）**：
- **出货**：r20/r22、r24c20/r24c29（月累计发货）、r24c23/r24c31（剩余发货）——@OutboundStats 保持含试作
- **入库**：r5/r6/r7、r8（入库差异）、r30c18/r30c21、r31c18/r31c21——保持含试作
- **检查数**：一检 r9/r10（含继承格 r6c11/r6c13/r6c14 良品率）、平衡 r13/r14/r15——曾计划改，最终取消
- **r17c3~r17c9 二检合格且入库**：条件含状态08（入库），随"入库不改"一并不改
- **r23 成品在库**（tb_WMS_RealTimeStorge 聚合快照无胎号列）、**r7c6 生胎在库**（按库位计数）——物理上无法过滤

**已知口径不对称（用户确认保留）**：r6c9/r6c10 PPM 格分子（生产数）去试作、分母（废品数）含试作；r14c3~c9 待测品①、r9c11 一检不良明细、r11/r9c7/r14c10/r17c10 报废类均含试作。若试作胎走报废流程会放大 PPM；后续要对称时在废品侧加同款过滤即可（FQS_SCRAP_INFO.TYRE_NO / FQM_TIRE_MOVE_RECORD.BARCODE）。

**SQL 写法**：过滤加在时间范围谓词之后作残余过滤（`AND SUBSTRING(TYRE_NO,6,1) <> 'Z'`），驱动谓词仍是分区对齐的 END_TIME 范围查，非 SARGable 但无损性能；`'Z'` 字面量对 varchar 列无隐式转换。

**存量与部署**：文件 `resources/xls/Proc_PB_GenerateDailyData.sql` 为 CREATE 空壳 + ALTER 模式，SSMS F5 全执行即更新过程定义；当天立即生效 `EXEC Proc_PB_GenerateDailyData '日期'`。历史 r17/r18 轮询格与历史月份格仍是旧口径（含试作），当月格由每日作业自动 UPDATE 成新口径；历史要对齐需按日期循环重跑（作业开头 DELETE 只清 RECORD_USER_ID='0'，用户手填值保留）。

**演变记录**：最初只改加硫/成型 → 用户扩到"所有工序产量 + 检查数统一改" → 逐项收窄（出货不改、入库不改、检查数不改）→ 最终定稿只改硫化 + 成型产量。以本节为准。