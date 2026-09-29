---
title: 班次下拉转精确时间范围（日期+班次→DateTime）实现模式
category: 技术-.NET
module: 通用
factory: 通用
tags: [班次, SSB_SHIFT, 时间范围, ApplyShiftDate, 跨天, DAY_FLAG, 报表查询, 复刻手册]
status: active
updated: 2026-08-29
---
# 班次下拉转精确时间范围（日期+班次→DateTime）实现模式

> 报表"日期+班次"条件的正解：把所选日期 + SSB_SHIFT 的 START_TIME/STOP_TIME 拼成精确 DateTime（ApplyShiftDate 方法可直接照搬，DayFlag=1 时结束日 +1），用产出表实际时间戳（如 END_TIME）做 WHERE 过滤，替代 SHIFT_DATE+SHIFT_ID 字符串字典序比较。含未选班次时 [当日 08:00, 次日 08:00) 兜底、各车间产出表时间字段对照、口径切换对夜班归属日的影响与已有实现索引。

## 一、适用场景

报表查询页有"日期 + 班次"组合条件时，把**所选日期 + 所选班次的 START_TIME/STOP_TIME**拼成精确的 `DateTime` 时间范围，用产出表的**实际时间戳字段**（如 `END_TIME`）做 WHERE 过滤，而不是用"班次日 + 班次代码"做字符串字典序比较。

适用所有车间（密炼/半钢/成型/硫化）的产出/检测报表。班次主数据详见 `shift-value-source.md`。

## 二、班次主数据关键字段（SSB_SHIFT）

| 属性 | 列 | 类型 | 说明 |
|------|-----|------|------|
| `ShiftCode` | SHIFT_CODE | string | 班次代码（业务值，如 `1`/`3`，下拉的 ValueField） |
| `ShiftName` | SHIFT_NAME | string | 班次名称（白班/夜班，下拉的 DisplayField） |
| `StartTime` | START_TIME | string | 班次开始时间，存 **`HH:mm:ss`**（如 `08:00:00`），由 Ext.NET TimeField `Format="HH:mm:ss"` 入库 |
| `StopTime` | STOP_TIME | string | 班次结束时间，同上 |
| `DayFlag` | DAY_FLAG | int? | **是否跨天**：`1`=跨天（夜班），`0`/null=当天 |

实体：`Wongoing.Main.Entity.BasicEntity.SsbShift`；Manager：`Wongoing.Main.Business.Implements.SsbShiftManager`（`GetEntityList(new SsbShift { DeleteFlag = 0 })` 取全量）。

## 三、核心方法：ApplyShiftDate（可直接照搬）

源自 Quality `RepairRecords.aspx.cs` / `ReportFqScrapInfo.aspx.cs`（两处逐字相同），已验证。

```csharp
/// <summary>
/// 将班次时间（StartTime/StopTime 字符串 HH:mm:ss）拼到指定日期上，返回精确 DateTime。
/// 开始时间 = 基准日期 + 班次开始时间；
/// 结束时间 = 基准日期 + 班次结束时间，若 DayFlag=1（班次跨天）则结束日期 +1。
/// </summary>
private DateTime ApplyShiftDate(DateTime baseDate, SsbShift shift, bool isStart)
{
    string timeStr = isStart ? shift.StartTime : shift.StopTime;
    TimeSpan ts = string.IsNullOrEmpty(timeStr) ? TimeSpan.Zero : TimeSpan.Parse(timeStr);
    DateTime result = baseDate.Date.Add(ts);
    if (!isStart && (shift.DayFlag ?? 0) == 1)
    {
        // 班次跨天（DayFlag=1），结束日期 +1
        result = result.AddDays(1);
    }
    return result;
}
```

### 调用上下文（含兜底规则）

```csharp
DateTime beginDate = Convert.ToDateTime(txtBeginDate.RawText);
DateTime endDate   = Convert.ToDateTime(txtEndDate.RawText);
IList<SsbShift> shiftList = shiftManager.GetEntityList(new SsbShift { DeleteFlag = 0 });

// 开始：开始日 + 开始班次 StartTime；未选班次默认 当日 08:00
DateTime beginTime = beginDate.AddHours(8);
string beginShiftCode = txtBeginShift.Value == null ? null : txtBeginShift.Value.ToString();
if (!string.IsNullOrWhiteSpace(beginShiftCode))
{
    SsbShift s = shiftList.FirstOrDefault(x => x.ShiftCode == beginShiftCode);
    if (s != null) beginTime = ApplyShiftDate(beginDate, s, isStart: true);
}

// 结束：结束日 + 结束班次 StopTime（DayFlag=1 则 +1 天）；未选班次默认 次日 08:00
DateTime endTime = endDate.AddDays(1).AddHours(8);
string endShiftCode = txtEndShift.Value == null ? null : txtEndShift.Value.ToString();
if (!string.IsNullOrWhiteSpace(endShiftCode))
{
    SsbShift s = shiftList.FirstOrDefault(x => x.ShiftCode == endShiftCode);
    if (s != null) endTime = ApplyShiftDate(endDate, s, isStart: false);
}

param["BEGIN_TIME"] = beginTime;
param["END_TIME"]   = endTime;
```

> **兜底规则**：未选班次时区间为 [开始日 08:00, 结束日次日 08:00)，覆盖整自然日 + 次日早班交界。这是 Quality / Curing 现网采用的默认。

## 四、跨天处理的三种思路（按需选用）

| 思路 | 写法 | 来源 | 说明 |
|---|---|---|---|
| **按 DAY_FLAG=1（推荐）** | `if (!isStart && (DayFlag??0)==1) result.AddDays(1)` | Quality `ApplyShiftDate` / Equip `BuildShiftRange` | 语义清晰，依赖班次主数据 DAY_FLAG 正确 |
| 结束<=开始则 +1（兜底） | `if (Shiftend <= Shiftstart) Shiftend.AddDays(1)` | Main `ShiftManager.aspx.cs:672` | 不依赖 DAY_FLAG，鲁棒，但会掩盖主数据配错 |
| DAY_FLAG 作日期偏移 | `Shiftdt.AddDays(DayFlag??0)` | Main `ShiftManager.aspx.cs:667` | DAY_FLAG 此处语义是"相对班次日的偏移天数"（0/-1/+1） |

> ⚠️ 主数据前提：夜班的 `DAY_FLAG` 必须配成 1，否则夜班结束时间会算少一天。改造前先 `SELECT SHIFT_CODE,SHIFT_NAME,START_TIME,STOP_TIME,DAY_FLAG FROM SSB_SHIFT` 核对。

## 五、SQL 改造模式（iBATIS mapper）

### 改造前：SHIFT_DATE + SHIFT_ID 字符串字典序比较（旧口径）

```xml
<isNotEmpty property="BEGIN_SHIFT" prepend="AND">
    <![CDATA[CONVERT(varchar(100), t.SHIFT_DATE,23) + t.SHIFT_ID >= #BEGIN_DATE# + #BEGIN_SHIFT#]]>
</isNotEmpty>
<isEmpty property="BEGIN_SHIFT" prepend="AND">
    <![CDATA[t.SHIFT_DATE >= #BEGIN_DATE#]]>
</isEmpty>
<!-- END 同理 -->
```
- 按"班次所属自然日 + 班次代码"字典序比较；夜班跨天产出按 SHIFT_DATE（班次起始日）归属。

### 改造后：按实际时间戳过滤（新口径）

```xml
<isNotEmpty property="BEGIN_TIME" prepend="AND">
    <![CDATA[t.END_TIME >= #BEGIN_TIME#]]>
</isNotEmpty>
<isNotEmpty property="END_TIME" prepend="AND">
    <![CDATA[t.END_TIME <= #END_TIME#]]>
</isNotEmpty>
```
- `BEGIN_TIME`/`END_TIME` 为 .cs 算出的 DateTime，iBATIS 自动参数化。
- 用哪个时间字段按业务定：硫化产出 `CPP_CURING_PRODUCTION.END_TIME`（完成时间）；其他车间见下表。

### 各车间产出表时间字段对照（改 SQL 时据此替换）

| 车间 | 产出表 | 可用时间戳字段 |
|---|---|---|
| 01密炼 | MENS.dbo 相关表 | RESTART_EQU_DATETIME 等 |
| 02半钢 | HPP_SEMIS_PRODUCTION | BEGIN_TIME/END_TIME |
| 03成型 | BPM_PRODUCTION | BEGIN_TIME/END_TIME |
| 04硫化 | CPP_CURING_PRODUCTION | **BEGIN_TIME / END_TIME / REAL_END_TIME** |

## 六、口径切换的影响（必须告知业务）

从"SHIFT_DATE 归属"切到"END_TIME 归属"后，**夜班跨天产出的归属日会变**：
- 旧：夜班产出记在班次起始日（SHIFT_DATE）。
- 新：夜班产出按实际完成时间（END_TIME，可能落在次日）归属。

同一查询条件的结果集可能与改造前不完全一致 —— 这是切换口径的预期结果，不是 bug。上线前建议用同一组条件对比前后数据。

## 七、已有实现索引（复用参考）

| 位置 | 做法 | 备注 |
|---|---|---|
| Quality `RepairRecords.aspx.cs:155-171` | `ApplyShiftDate` + 当日8:00/次日8:00 兜底 | **最干净，首选照搬** |
| Quality `ReportFqScrapInfo.aspx.cs:257-273` | 同上（逐字副本） | |
| Equip `EquipEfficiencyCard.aspx.cs:89-134` | `BuildShiftRange` + `ParseTimeSpan` | 另一套封装 |
| Main `ShiftManager.aspx.cs:663-673` | `.Date.Add(TimeSpan.Parse)` + 结束<=开始则+1 | 班次维护页内部用 |
| Curing `ProduceAnalyseReport.aspx.cs` | 2026-07 改造，照搬 Quality，7 张报表共用 WHERE | 本模式的硫化落地实例 |

## 八、下拉 UI 说明

下拉 ComboBox **不需要**改成拼接显示（仍 `DisplayField=ShiftName`）。时间拼接只在 .cs 后端做，对前端透明。如确需下拉显示「白班(08:00-20:00)」，参考 `extnet-query-form-compound-control-layout.md`，需在数据源加计算列 + 改 DisplayField（项目无现成范例，需自实现）。
