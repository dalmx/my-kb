---
title: 仕上工序作业日报（UF均匀性检测）实现方案与踩坑
category: 业务-通用
module: Batch
factory: 通用
tags: [仕上日报,UF均匀性,FQB_UFCHECK_INFO,OE/REP,再测,停机记录,集合化,iBATIS,BasicMapper生成器,Batch,FinishingDailyReport,踩坑]
status: active
updated: 2026-09-04
---
# 仕上工序作业日报（UF均匀性检测）实现方案与踩坑

> 项目：Batch ｜ 编号：SQ-PP01 样式-1
> 页面：`Plugins/Batch/Report/FinishingDailyReport.aspx(.cs)`
> 快照表：`CPP_FINISH_DAILY_DATA`（H/D 两类行，维度=日期×班别×UF机台）
> 同系列参考：[[first-inspection-daily-report-implementation]]（SQ-PL01 一检日报）、[[curing-daily-report-implementation]]（SQ-PK01 硫化日报）
> **本文重点在后半的「踩坑」——新增实体/iBATIS/集合化等通用经验，适用于整个 MES 项目族。**

## 一、最终页面布局

```text
查询区：日期 | 班别 | UF机台(ComboBox，MINOR_TYPE_ID='1401') | 说明
抬头：作业员(手填) | 班长(手填)
D 行 GridPanel（双层表头）：
   规格 | 一次检查数 | 合格数[OE|REP] | 再测数[OE|REP] | 再测NG数及原因(只显原因) | REP保留数(=再测NG数) | 备注(可编辑)
中间 KPI：一次检查合计[自动] | UF再测合格数[自动] | 接班时待测数[手填] | 交班时待测数[手填]
S 行 停机记录 GridPanel（只读，直查 SBE_EQUIP_STOP_RECORD）：序号|开始|停止|原因|时长
页脚：保管期限 20 年
```

## 二、快照表 CPP_FINISH_DAILY_DATA

维度 = 报表日期 × 班别 × UF机台(EQUIP_CODE)；两类行：

| ROW_TYPE | 粒度 | 字段 |
|----------|------|------|
| H | 每班每天每机台1行 | OPERATOR/LEADER/HANDOVER_PENDING_QTY/HANDOFF_PENDING_QTY(手填)；UF_RETEST_PASS_QTY(自动) |
| D | 每班每机台每规格1行 | MATERIAL_NAME / FIRST_CHECK_QTY / QUALIFIED_OE·REP / RETEST_OE·REP / RETEST_NG_QTY / RETEST_NG_DETAIL / REMARK(手填) |

> 停机记录**不入快照表**，页面直接查 `SBE_EQUIP_STOP_RECORD`（变长、只读）。
> 唯一索引 `(REPORT_DATE, SHIFT_ID, EQUIP_CODE, ROW_TYPE, MATERIAL_NAME)`；H 行 MATERIAL_NAME 占位 `'~~'`。建表 DDL 在 `Proc_FinishDailyReport.sql` 文件末尾注释块，**用户连库执行**。

## 三、存储过程 Proc_FinishDailyReport（集合化，无游标）

签名：`@ReportDate` + `@Shift` 两参，**不传机台**——一次调用遍历所有 UF 机台。

核心思路：**机台作 `GROUP BY` 维度，不是循环变量**。一次过数据，所有机台一起算完。

```text
1. 算班次时间窗（工厂日 8:00~次日8:00；早班记今天/夜班记昨天）
2. DELETE 当日当班所有机台的 D 行（H 行保留手填）
3. 物化 #FinishTest（rn 历史累计 + 带 EQUIP_CODE + OE/REP class）
4. #LastRec（每胎最后一条记录，带 EQUIP_CODE）
5. #NgDefect / #NgDetailAgg（再测NG原因 UNPIVOT，按 机台×规格 聚合）
6. D 行 INSERT：GROUP BY EQUIP_CODE, LEFT(Barcode,5)，一次插入所有机台所有规格
7. H 行集合化 upsert：SBE_EQUIP 机台清单 LEFT JOIN #HUfRetest → UPDATE 已存在 + INSERT 缺失（无数据机台也建行）
8. 各步末尾 OPTION (RECOMPILE)；清理临时表
```

口径（已锁定）：
- **rn 历史累计**：子查询锁本时段(EQUIP_CODE∈UF机台 AND 时间窗 AND Barcode LIKE 'S%')出现的 Barcode → 外层取 `FQB_UFCHECK_INFO` **全部历史**记录按 RecordTime ASC 编号 rn → 过滤回本时段。rn=1 首测，rn≥2 再测（跨班次不误判）。
- 一次检查数 = `COUNT(*) WHERE rn=1`
- 合格数OE/REP = `COUNT(*) WHERE rn=1 AND UF_Mark IN(1,2) AND class`
- 再测数OE/REP = `COUNT(DISTINCT Barcode) WHERE rn≥2 AND class`
- 再测NG数 = 每胎 `rn=max` 那条 `UF_Mark NOT IN(1,2)`，合计
- 再测NG原因 = 参考 `Proc_PB_GenerateDailyData.sql` @r17c10：UNPIVOT 各 Class 列、object>2、每胎1条、去Class后缀、按(机台,规格) STRING_AGG
- OE/REP 分类：`TYRE_CLASS_VALUE='OE'` 归 OE；REP/OER/空 归 REP（默认 REP）

调用（SQL Agent 作业，2~3 个就够，每个一次调用遍历所有机台）：
```sql
EXEC Proc_FinishDailyReport NULL, 'D'   -- 早班 20:05
EXEC Proc_FinishDailyReport NULL, 'N'   -- 夜班次日 08:05
```

## 四、文件清单（新建）

| 文件 | 说明 |
|------|------|
| `Entity/BasicEntity/CppFinishDailyData.cs` | 实体 |
| Data `ICppFinishDailyDataService` + `CppFinishDailyDataService`；Business `ICppFinishDailyDataManager` + `CppFinishDailyDataManager` | 三件套样板 |
| `Mapper/BasicMapper/CppFinishDailyData.xml` | **必须用代码生成器产出**（见踩坑1） |
| `Mapper/BusinessMapper/CppFinishDailyData.xml` | 业务语句：SelectFinishDailyData/Header/StopRecord、GetFinishEquipList、UpsertFinishDailyHeader、CheckEditPermission |
| `WebSite/resources/xls/Proc_FinishDailyReport.sql` | 建表 DDL + 存储过程 |
| `Plugins/Batch/Report/FinishingDailyReport.aspx(.cs)` | 页面 |
| csproj | 4 个类库工程各加 `<Compile>`/`<EmbeddedResource>`（WebSite 是文件型站点，aspx 不用加） |
| 权限 ACTION_ID | **49505**（一检49464 / 二检49479 / 硫化49452 / 仕上49505） |

## 五、踩坑（核心沉淀，适用于整个 MES 项目族）

### 坑1 ⭐ BasicMapper 必须用代码生成器产出，绝不手写（最严重）

手写 BasicMapper 会用自造 statement ID（`GetList`/`GetModel`）和 `parameterClass`，不符合 Wongoing `BaseManager/BaseService`（DbAccess 预编译 dll）期望的框架契约（标准 `<sql id="includeSelect/Where/Insert/Update/Delete">` 积木 + `GetEntityList`/`GetByObjId`/`UpdateByObjId`/`Insert(parameterMap)` 等 ID）。

**后果**：iBATIS 加载该 mapper 时构建失败，报误导性的 `Object reference should not be equal to null when resolving type name: XXX. Cause: A type alias for this type is not registered.`，**连累整站所有 iBATIS 查询全崩**（一个 mapper 加载失败 → 整个 SqlMapper 配置构建失败）。

**正解**：
- BasicMapper **永远用 IDE 代码生成器产出**（菜单/工具按表生成实体+四层+mapper）
- 自己只在 **BusinessMapper** 加业务 `<select>/<insert>`，保留生成器的标准结构不动
- entity 的增删改用框架方法：`mgr.UpdateByObjId(entity, objid)` / `mgr.Insert(entity)`（BasicMapper 的 `includeUpdate` 用 `<isNotNull>` 动态拼，只更新实体非空字段，按 OBJID）——**别自己写业务 update 语句**

### 坑2 ⭐ 新增实体后 iBATIS 加载不到：四层整体重新生成 + 回收应用池

新增一个实体（跨 Entity/Data/Business/Mapper 四层）后，光重新编译某个工程不够，运行时仍报「type alias not registered」。原因：增量编译导致各层 dll 不一致（Mapper.dll 嵌的 XML 引用了新类型，但 Entity/上下游没同步），iBATIS 配置构建时类型解析失败。

**正解**：用生成器**四层整体重新生成**（Entity+Data+Business+Mapper），再回收 IIS 应用池。验证：`findstr`/反射确认运行用的 `Wongoing.Batch.Entity.dll` 含新类型、`Wongoing.Batch.Mapper.dll` 含嵌入 XML。
> 这是 create-report 技能里那条「改了 .cs/dll 不生效 → 重启 IIS 应用池」的根因——运行中的 w3wp 持有旧 dll，回收才换。

### 坑3 iBATIS mapper 是程序集嵌入资源扫描加载，SqlMap.config 无 sqlMaps 清单

`SqlMapBatch.config` / `SqlMap.config` 里**没有** `<sqlMaps>` 列表，mapper XML 作为 EmbeddedResource 由 DbAccess 在应用启动时扫描程序集加载。所以新增 mapper 必须：① 在 csproj 注册为 `<EmbeddedResource>`；② Mapper 工程重新编译（嵌入资源是编译期打进 dll 的）；③ 回收应用池（启动时才扫描）。

### 坑4 FQB 系列表字段是 PascalCase，与 SBE_EQUIP.EQUIP_CODE 不同名

`FQB_UFCHECK_INFO` / `FQB_BALANCE_INFO` 字段是 `Barcode`/`RecordTime`/`UF_Mark`/`DB_Mark`/`EquipCode`（PascalCase），而 `SBE_EQUIP` 是 `EQUIP_CODE`（UPPER_SNAKE）。现有代码几乎只引用 Barcode/RecordTime/UF_Mark，**机台字段 EquipCode 从未被引用过**（探查时全库无命中）。

**正解**：读 `FQB_UFCHECK_INFO` 时 `EquipCode AS EQUIP_CODE` 别名，下游临时表/快照表统一用 `EQUIP_CODE`，避免几十处全改。

### 坑5 ⭐ T-SQL UNPIVOT 在 CTE 里别用「别名.列」

```sql
-- ❌ 报错：multi-part identifier "n.Barcode" could not be bound
DefectRaw AS (
    SELECT n.Barcode, ... FROM NgLatest n UNPIVOT (...) unpvt ...
)
-- ✅ 正解：不加别名，用未限定列名（UNPIVOT 后携带列 Barcode 直接可用）
DefectRaw AS (
    SELECT Barcode, ... FROM NgLatest UNPIVOT (...) unpvt ...
)
```
原因：UNPIVOT 把源表打散重组，给源表起别名再 `别名.列` 引用绑不上。参考 `Proc_PB_GenerateDailyData.sql` @r17c10 写法。

### 坑6 ⭐ 集合化优于游标（多机台/多规格用 GROUP BY 维度）

对「所有 UF 机台」生成日报，**不要用 WHILE 游标逐台循环**，把机台变成 `GROUP BY EQUIP_CODE` 的分组维度，一次过数据算完（rn 的 PARTITION 用 Barcode 全局——一条胎只在一台机测）。
集合化 upsert（H 行）：`UPDATE 已存在` + `INSERT NOT EXISTS 缺失` 两语句，不要 `IF EXISTS` 循环。

### 坑7 停机原因 JOIN 要带 MAJOR_TYPE_ID 作用域

`SBE_EQUIP_STOP_REASON` 的原因编号会**跨设备大类重码**，直接 `STOP_REASON_ID = EQUIP_STOP_REASON_CODE` 会串号。要 JOIN `SBE_EQUIP B ON r.EQUIP_CODE = B.EQUIP_CODE`，原因匹配加作用域：
```sql
LEFT JOIN SBE_EQUIP_STOP_REASON rs
  ON r.STOP_REASON_ID = rs.EQUIP_STOP_REASON_CODE
  AND rs.REMARK LIKE '%'+B.MAJOR_TYPE_ID+'%'
```
（注：`CppCuringProduction.xml:516-519` 用的是 `RES_SURE_REASON` 优先于 STOP_REASON_ID 的写法；按数据现状二选一。本表用 STOP_REASON_ID 直连 + MAJOR_TYPE_ID 作用域。）

### 坑8 再测识别必须用历史累计 rn，不能在班次窗口内编号

「再测」= 一条胎历史上测过多次。若只在班次时间窗内 `ROW_NUMBER`，上班测过的胎本班第一次会被误判为首测。**正确**：子查询锁本时段出现的 Barcode → 外层取该 Barcode 在 `FQB_UFCHECK_INFO` 的**全部历史**记录按时间正序编号 → 过滤回本时段。rn=1 才是真首测。

### 坑9 手填输入框保存后要清 _currentEdit，否则点别处回滚成旧值

浮动保存按钮机制（照一检日报）：focus 输入框时 `_currentEdit = {inputId, originalValue(旧值)}`；保存成功后**必须 `_currentEdit = null`**。否则点别处触发 `cancelEdit()`，它会 `el.value = originalValue`（**回滚成旧值**），用户看到"刚录入的文字消失了，要点查询才回来"。

### 坑10 Ext.NET 控件细节

- **ComboBox 绑定**：用 `<Store>` + `DisplayField/ValueField` + 服务端 `store.DataSource=dt; store.DataBind()`（规范做法），不要 `Items.Add`（参考 `extnet-query-control-upgrade.md`）
- **双层表头**：父 `<ext:Column Text="合格数">` 不带 DataIndex，内嵌 `<Columns>` 放 OE/REP 子列
- **Grid 单元格编辑**：列加 `<Editor><ext:TextField/></Editor>` + Grid 加 `<Plugins><ext:CellEditing>`（BeforeEdit 校验权限、Edit 触发保存）；保存用框架 `mgr.UpdateByObjId(entity, objid)`
- **集合标签内禁放 HTML 注释**：`<Items>`/`<Columns>`/`<Fields>` 内放 `<%-- --%>` 会报错
- **iBATIS `<` `>` `&`**：SQL 含这些必须包 `<![CDATA[ ]]>`；`<dynamic prepend="AND">` 每个子元素带 `prepend="AND"`、CDATA 内不写 AND

### 坑11 日期归属：班次跨天，早班记今天/夜班记昨天

夜班（20:00~次日8:00）跨天，SQL Agent 在次日 08:05 调用时 `GETDATE()` 是次日，但统计属前一天。所以 proc 里 `@Report` 按 `@Shift` 决定：早班=今天，夜班/每日=昨天（`DATEADD(DAY,-1,@Today)`）。**不能直接用 GETDATE() 算周期号/归属日**。

## 六、SQL 优化原则落实（对照知识库 sql-server-performance-troubleshooting.md）

| 原则 | 落实 |
|------|------|
| 集合化禁游标 | 机台作 GROUP BY 维度（坑6）|
| 缩小范围 | 时间窗 + `EQUIP_CODE IN (UF机台子查询)` 收窄 |
| SARGable | RecordTime 裸用走索引，函数全在变量侧（`DATEADD(HOUR,8,@Report)`）|
| STRING_AGG 不放相关子查询 | 再测NG原因先物化 `#NgDefect`→`#NgDetailAgg` 小临时表再聚合（避免内存授予虚高）|
| 防参数嗅探 | 各 INSERT/聚合末尾 `OPTION (RECOMPILE)` |
| 聚合忽略 NULL 警告 | `COUNT(DISTINCT CASE WHEN...)` 会触发「聚合消除 Null」警告，**属正常**，结果正确；要静默可 `SET ANSI_WARNINGS OFF`（注意截断/除零副作用）|

---

**总结**：新增 MES 报表的稳妥流程——① 用生成器产出四层（实体+Data+Business+BasicMapper）；② 只在 BusinessMapper 写业务 SQL；③ 存储过程集合化（GROUP BY 维度，禁游标）；④ 改完四层整体重新生成 + 回收应用池；⑤ 权限申请新 ACTION_ID 配菜单。本表的 ACTION_ID=49505。
