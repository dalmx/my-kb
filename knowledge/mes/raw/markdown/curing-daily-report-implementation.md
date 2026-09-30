---
title: 硫化工程日报（表单式填报看板）实现方案
category: 业务-通用
module: Curing
factory: 通用
tags: [硫化日报, 表单式填报, 看板, Batch, CuringDailyReport, 手工录入, 班次拆分, 实现方案]
status: active
updated: 2026-08-29
---
# 硫化工程日报（表单式填报看板）实现方案

> 项目：Batch（硫化）｜编号：SQ-PK01 样式-1
> 页面：`Plugins/Batch/Report/CuringDailyReport.aspx(.cs)`
> 适用：需要"查询自动取数 + 手工录入 + 按班次拆分"的**表单式日报/看板**（非 GridPanel 报表）。

## 一、与标准报表的本质区别

| 维度 | 标准 GridPanel 报表 | 本方案（表单式填报看板） |
|---|---|---|
| 布局 | Store + GridPanel 列表 | TableLayout/HTML 表格卡片分区 |
| 数据载体 | 行列单元格（DataIndex） | `cell_xxx` 只读格 + `txt_xxx` 输入框 |
| 数据流 | PageProxy 分页 → GridPanel | DirectMethod → `X.AddScript` 注入 JS 填格子 |
| 取数 | 实时查 iBATIS statementId | **定时任务写快照表**，页面读快照 |
| 手输 | 一般无 | 出勤/签字/记录，落库同表 |

## 二、长表快照机制（核心设计）

### 表结构 `CPP_DAILY_REPORT_DATA`
长表（FIELD_KEY 区分字段），数值用 `VAL_DAY/VAL_NIGHT/VAL_TOTAL`，文本用 `VAL_TEXT`：
```sql
CREATE TABLE CPP_DAILY_REPORT_DATA (
    OBJID BIGINT IDENTITY(1,1) PRIMARY KEY,
    REPORT_DATE DATE NOT NULL,
    FIELD_KEY VARCHAR(50) NOT NULL,
    VAL_DAY INT DEFAULT 0,               -- 早班值
    VAL_NIGHT INT DEFAULT 0,             -- 夜班值
    VAL_TOTAL INT DEFAULT 0,             -- 合计值
    VAL_TEXT NVARCHAR(MAX),              -- 文本值（明细/签字/记录）
    SOURCE_TYPE CHAR(1) DEFAULT '1',     -- '1'=自动 '2'=手输
    RECORD_USER_ID VARCHAR(20) DEFAULT '0',
    GENERATE_TIME DATETIME DEFAULT GETDATE()
);
```

## 三、存储过程 + 三个定时任务

`Proc_CuringDailyReport` 用 `@Shift` 参数区分三种调用，**日期归属不同**：

| 调用 | 执行时机 | @Report | 记录内容 |
|---|---|---|---|
| `EXEC ... NULL,'D'` | 当天20:05 | **今天** | 待测品/待修品早班快照 |
| `EXEC ... NULL,'N'` | 次日08:05 | **昨天** | 待测品/待修品夜班快照（跨天！） |
| `EXEC ...` | 次日08:10 | **昨天** | 目标/实绩/各工序/废品明细 |

### 夜班跨天日期归属（重点）
```sql
IF @Shift = 'D'
    SET @Report = ISNULL(@ReportDate, @Today);                    -- 早班=今天
ELSE IF @Shift = 'N'
    SET @Report = ISNULL(@ReportDate, DATEADD(DAY, -1, @Today));  -- 夜班=昨天（跨天！）
ELSE
    SET @Report = ISNULL(@ReportDate, DATEADD(DAY, -1, @Today));  -- 每日=昨天
```

### DELETE 白名单保护手输项
```sql
DELETE FROM CPP_DAILY_REPORT_DATA
 WHERE REPORT_DATE = @Report
   AND FIELD_KEY IN ('goal','act','greenstock','c1chk',...);  -- 只列自动项
```

## 四、班次拆分（工厂一天 8:00~次日8:00）

```sql
DECLARE @DayStart  = DATEADD(HOUR, 8,  @Report);          -- 当日8:00
DECLARE @DayEnd    = DATEADD(HOUR, 8,  DATEADD(DAY,1,@Report)); -- 次日8:00
DECLARE @NoonStart = DATEADD(HOUR, 12, @DayStart);        -- 当日20:00
```

### 一次查询出多指标（CROSS JOIN 避免重复扫表）
```sql
INSERT INTO ... SELECT @Report,
    CASE n.n WHEN 1 THEN 'c1chk' WHEN 2 THEN 'c1bad' END,
    ...
FROM FQF_FCHECK_INFO CROSS JOIN (VALUES (1),(2)) n(n)
WHERE RECORD_TIME >= @DayStart AND RECORD_TIME < @DayEnd GROUP BY n.n;
```

## 五、STRING_AGG 明细拼接（坑：8000字节限制）

```sql
SELECT STRING_AGG(CAST(CONCAT(g.code,'-',g.DEFECT_NAME,'-',g.NUM) AS VARCHAR(MAX)), '<br />')
       WITHIN GROUP (ORDER BY g.NUM DESC)
```

## 六、签字/出勤跨天继承

```sql
INSERT INTO CPP_DAILY_REPORT_DATA (...)
SELECT @Report, d.FIELD_KEY, ..., '2', d.RECORD_USER_ID, @Now
FROM CPP_DAILY_REPORT_DATA d
WHERE d.REPORT_DATE = DATEADD(DAY,-1,@Report)
  AND d.FIELD_KEY IN ('kz','xz','dleader','nleader','att')
  AND NOT EXISTS(...);
```

## 七、前端数据注入（DirectMethod + AddScript）

```csharp
sb.Append("clearAll();");
sb.Append("applyReportData({...});");
sb.Append("applyRecordData({...});");
sb.Append("setTimeout(function(){calcTotals(); bindInputFocus();}, 50);");
X.AddScript(sb.ToString());
```

## 八、数据来源对照（硫化质检系列表）

| FIELD_KEY | 含义 | 来源表 | 备注 |
|---|---|---|---|
| goal | 加硫目标 | CPP_CURING_PLAN_DETAIL + CPP_CURING_PLAN | SHIFT_CODE 01/03 |
| act | 加硫实绩 | **CPP_CURING_PRODUCTION** | 按 END_TIME COUNT（不从计划表取） |
| greenstock | 生胎在库 | BPM_MOLDING_ART_AND_* | LOCATION LIKE 'C-ST%'，快照 |
| c1chk/c1bad | 一检检查数/外观不良 | FQF_FCHECK_INFO | c1bad: GRADE<>'1' |
| c1scrap | 一检废品数量 | FQS_SCRAP_INFO + FQD_DEFECT_INFO | WORK_PROCESS_ID='9' |
| c3chk | 二检检查数 | FQF_FCHECK_INFO_TWO | |
| rep | 修理量 | FQR_REPAIR_RECORDS | |
| c2chk/c2rep/c2ng | 仕上检查数/REP/NG | FQB_BALANCE_INFO + FQB_UFCHECK_INFO | DB_Mark/UF_Mark 统一别名Mark去重 |
| wait_d/n | 待测品(班次快照) | CPP_CURING_PRODUCTION + FQF + FQB | 实时存量 |
| **repwait_d/n** | **待修品(班次快照)** | **SPP_TYRE_STATE** | **TYRE_STATE='04'**，实时存量 |
| scrap2_d/n | 硫化废品明细 | FQS_SCRAP_INFO(WP='9') | 代码-缺陷名-数量 |
| scrap3_d/n | 仕上废品明细 | FQB_UFCHECK_INFO (UF_Mark NOT IN 1,2) | 代码-数量 |
| scrap4_d/n | 外观不良明细 | FQF_FCHECK_INFO(WP='4') | 代码-缺陷名-数量 |

> 待修品用 `SPP_TYRE_STATE`（状态字典表）取值，比原来"一检不合格+5表NOT EXISTS"简洁可靠。

## 九、新建实体四件套 + csproj 注册

为快照表建 Entity/Service/Manager/BasicMapper（4项目6文件），**必须注册到各 .csproj**：
- Mapper XML 用 `<EmbeddedResource>`（不是 Compile）
- BasicMapper 和 BusinessMapper 文件名**统一**（都叫 CppDailyReportData.xml）

## 十、单字段保存 + 浮动保存按钮

### 编辑时输入框下方出现保存按钮
- 后台 `SaveSingle(fieldKey, valDay, valNight, valText)` 只存一个字段
- 前端 `_currentEdit` 记录当前聚焦框，`_inputMap` 映射 id→FIELD_KEY
- 按钮绝对定位跟随输入框（`getBoundingClientRect`，appendChild 到 body）

### 编辑取消/恢复（cancelEdit = 恢复原值 + el.blur + 隐藏按钮）
- **点击其他区域**：mousedown 监听
- **滚动**：监听 window + .cdr-panel + .x-panel-body（Ext.NET Panel AutoScroll 滚动在内部div不冒泡到window）
- **⚠️ 不用 blur 自动取消**：误触发导致按钮自己消失

## 十一、编辑权限控制（V_SSP_USER_ALL_ACTION）

```xml
<!-- BusinessMapper -->
<select id="CheckEditPermission@CuringDailyReport" parameterClass="map" resultClass="int">
  SELECT COUNT(1) FROM V_SSP_USER_ALL_ACTION WHERE USER_ID = #UserId# AND ACTION_ID = 49452
</select>
```
```csharp
bool canEdit = mgr.GetIntByStatement("CheckEditPermission@CuringDailyReport", p) > 0;
X.AddScript("_canEdit = " + (canEdit ? "true" : "false") + ";");
if (!canEdit) X.AddScript("disableAllInputs();");
```

## 十二、合计口径特殊逻辑（前端 calcTotals）

| 字段 | 合计公式 |
|---|---|
| 待测品 | `wait_t = wait_n`（**只取夜班**） |
| 待修品 | `repwait_t = repwait_d + c1bad_n - rep_n`（早待修 + 夜一检外观不良 - 夜修理量） |
| 其他 | 早+夜 |

> ⚠️ 文本明细字段（scrap4）不能 parseFloat，待修品公式用 `c1bad_n`（数值）。

## 十三、踩坑速查

| 坑 | 正解 |
|---|---|
| OPTION (RECOMPILE) 语法错误 | 不能跟在变量赋值SELECT后、不能放END后 |
| SQL 注释用 `//` 报错 | 用 `--` |
| UNION 字段别名不统一 | DB_Mark/UF_Mark 都 AS Mark |
| blur 导致保存按钮消失 | 改用 mousedown + scroll |
| 权限查询放 BasicMapper 找不到 | 放 BusinessMapper |
| 加硫实绩从计划表不准 | 改用 CPP_CURING_PRODUCTION 按 END_TIME COUNT |
| Mapper XML 命名不统一 | BasicMapper 和 BusinessMapper 同名 |
| 切换日期残留数据 | 注入前先 clearAll() |
| 待修品用多表NOT EXISTS复杂 | 改用 SPP_TYRE_STATE WHERE TYRE_STATE='04' |
