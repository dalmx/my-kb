---
title: 一检工序作业日报（表单抬头 + GridPanel 混合）实现方案
category: 业务-通用
module: Batch
factory: 通用
tags: [一检日报, 表单抬头, GridPanel, 混合型日报, Batch, FirstInspectionDailyReport, 实现方案]
status: active
updated: 2026-08-29
---
# 一检工序作业日报（表单抬头 + GridPanel 混合）实现方案

> 项目：Batch ｜ 编号：SQ-PL01 样式-1
> 页面：`Plugins/Batch/Report/FirstInspectionDailyReport.aspx(.cs)`
> 适用：需要「纸表式抬头/页脚 + GridPanel 自动取数主体」的**混合型日报**（非纯表单、非纯查询报表）。
> 同系列参考：`curing-daily-report-implementation.md`（SQ-PK01 硫化工程日报，纯表单式）。

## 一、与硫化日报（SQ-PK01）的关键差异

| 维度 | 硫化日报（CuringDailyReport） | 一检日报（FirstInspectionDailyReport） |
|---|---|---|
| 主体 | HTML 表格固定格子（cell_xxx） | **GridPanel**（一行一规格，变长） |
| 数据载体 | 长表 FIELD_KEY 字段级 | H/D 行混存一张表（ROW_TYPE 区分） |
| 快照表结构 | CPP_DAILY_REPORT_DATA（字段级长表） | **CPP_FCHECK_DAILY_DATA**（H行抬头 + D行规格数据） |
| 取数来源 | CuringDailyReport 存储过程多源聚合 | 照搬 Quality `Proc_FcheckkEquipDifference` 的不良/废品口径 |
| 周期号 | 无 | **查 tb_EQ_SET_DOT_RULES** 按报表日期取 SERIAL_CODE |

## 二、H/D 行混存一张快照表（核心设计）

一张 `CPP_FCHECK_DAILY_DATA` 表，用 `ROW_TYPE` 区分两类行：

| ROW_TYPE | 含义 | 每行内容 | 来源 |
|---|---|---|---|
| 'H' | 抬头行 | 作业员/班长/周数/仕样周数/检测总数（每班每天1行） | 存储过程写周期号+作业员+检测总数，班长继承，页面手填其余 |
| 'D' | 数据行 | 规格/不良合计/不良明细/废品合计/废品明细/合计（每班每规格1行） | 存储过程自动聚合 |

**唯一索引**：`(REPORT_DATE, SHIFT_ID, ROW_TYPE, MATERIAL_NAME)`
- H 行 MATERIAL_NAME 为 NULL，D 行为规格名，靠 ROW_TYPE 区分不冲突

**存储过程的 H/D 行处理顺序**：
1. DELETE 当日当班的 D 行（**不删 H 行**，保留手填的作业员/班长）
2. 写 H 行：周期号 + 作业员（自动取值）+ 班长（继承）+ 检测总数
3. INSERT 各规格的 D 行（不良+废品 FULL JOIN 聚合）

> ⚠️ H 行的作业员每次重算覆盖，班长仅在为空时继承上次，手填的班长/周数不会被覆盖。

## 三、取数口径（严格照 Quality Proc_FcheckkEquipDifference）

**关键：不良和废品的口径不同，时间字段不同！**

| 项 | 不良（FQF_FCHECK_INFO） | 废品（FQS_SCRAP_INFO） |
|---|---|---|
| 时间字段 | **SHIFT_DATE**（varchar） | **RECORD_TIME**（DateTime） |
| DELETE_FLAG=0 | ❌ **不加** | ✅ **加** |
| GRADE 处理 | 不良数=COUNT(1)-SUM(GRADE=1)，**不在 WHERE 预过滤** | 不涉及 |
| 规格名来源 | INNER JOIN SBM_MATERIAL.MATERIAL_NAME（ON MATERIALID=MATERIAL_CODE） | 自带 MATERIALNAME（不 JOIN） |
| 缺陷名来源 | LEFT JOIN FQD_DEFECT_INFO（WORK_PROCESS_ID='4'） | LEFT JOIN FQD_DEFECT_INFO（WORK_PROCESS_ID='9'） |

**班次区分**：纯按时间窗（不碰 SHIFT_ID）——早班=当日8:00~20:00，夜班=当日20:00~次日8:00。SHIFT_ID 字段取值不确定，不要用它过滤。

** GRADE 比较用数值**：`GRADE = 1`（无引号），不是 `GRADE = '1'`。源表 GRADE 是数值列，加引号会隐式转换。

## 四、周期号（周数/仕样周数）—— 查 tb_EQ_SET_DOT_RULES

**周期号 = SERIAL_CODE，不是按日期算 ISO 周数**。查询规则：
```sql
SELECT TOP 1 SERIAL_CODE
  FROM dbo.tb_EQ_SET_DOT_RULES WITH(NOLOCK)
 WHERE CAST(STR_DATE AS DATE) <= CAST(@Report AS DATE)    -- 用报表日期，不是 GETDATE()！
   AND CAST(END_DATE AS DATE) >= CAST(@Report AS DATE)
 ORDER BY SERIAL_CODE DESC
```

> ⚠️ **必须用 @Report（报表日期），不能用 GETDATE()**：班次结束跑存储过程时 GETDATE() 是执行时刻，但周期号应该是统计日期当天生效的。

存储过程把周期号写入 H 行的 WEEK_NO/SAMPLE_WEEK_NO（周数和仕样周数都填同一个 SERIAL_CODE）。

## 五、作业员自动取值（按人员去重拼接姓名）

**需求**：作业员不是手填，而是从当班一检记录自动取——按 RECORD_USER_ID 去重后拼接所有检验员姓名（**不按机台分组**，只取人员名称）。

**SQL 实现**（存储过程写入 H 行 OPERATOR 字段）：
```sql
DECLARE @Operators NVARCHAR(MAX);
;WITH t1 AS (
    -- 每个 RECORD_USER_ID 取首条记录去重
    SELECT RECORD_USER_ID,
           ROW_NUMBER() OVER (PARTITION BY RECORD_USER_ID ORDER BY SHIFT_DATE) AS id
      FROM FQF_FCHECK_INFO WITH(NOLOCK)
     WHERE SHIFT_DATE >= @BeginTime AND SHIFT_DATE < @EndTime
)
SELECT @Operators = STRING_AGG(t3.real_name, ',') WITHIN GROUP (ORDER BY t3.real_name)
  FROM t1
  LEFT JOIN SSB_USER t3 WITH(NOLOCK) ON t3.work_barcode = t1.RECORD_USER_ID
 WHERE t1.id = 1 AND t3.real_name IS NOT NULL;
```

**要点**：
- `ROW_NUMBER() OVER (PARTITION BY RECORD_USER_ID)` → 每个检验员只取首条记录（去重），`t1.id = 1` 过滤
- 直接 `STRING_AGG(real_name, ',')` 拼接所有姓名，按姓名排序（**不分机台段**，纯人员名单）
- 字段长度：OPERATOR 改成 `NVARCHAR(MAX)`（拼接结果常超 50 字符）
- 结果示例：「唐传,陈之保,高磊,柯贤江,孙家煌」

> 演进记录：初版按机台段(J1xx/J2xx)分组拼接（`equip_range:operators`），后简化为只取人员名称，去掉机台段分组和 CPP_CURING_PRODUCTION JOIN。

## 六、班长自动继承（上次同班次）

```sql
DECLARE @PrevLeader NVARCHAR(50);
SELECT TOP 1 @PrevLeader = LEADER
  FROM CPP_FCHECK_DAILY_DATA WITH(NOLOCK)
 WHERE SHIFT_ID = @ShiftCode AND ROW_TYPE = 'H' AND LEADER IS NOT NULL AND LEADER <> ''
 ORDER BY REPORT_DATE DESC;
```

**H 行更新策略**（关键）：
- 作业员（OPERATOR）：每次重算覆盖（`ISNULL(@Operators, OPERATOR)`）
- 班长（LEADER）：**仅在为空时继承**（`ISNULL(NULLIF(LEADER,''), ISNULL(@PrevLeader, LEADER))`）——本次已手填则保留，为空才用上次的
- 周期号（WEEK_NO）：每次更新（`ISNULL(@SerialCode, WEEK_NO)`）

## 七、检测总数（CHECK_QTY）—— 按胎号去重

**口径**：时间范围内 `FQF_FCHECK_INFO` **按胎号(TYRE_NO)去重**的数量（一条胎多条检验记录只算一次），存 H 行 CHECK_QTY。
```sql
DECLARE @CheckTotal INT = 0;
SELECT @CheckTotal = COUNT(DISTINCT TYRE_NO) FROM FQF_FCHECK_INFO WITH(NOLOCK)
 WHERE SHIFT_DATE >= @BeginTime AND SHIFT_DATE < @EndTime;
```
- 快照表加 `CHECK_QTY INT DEFAULT 0`（H 行字段）
- 页面总计 table 加「检测总数」列，从 H 行读取

> ⚠️ **必须 COUNT(DISTINCT TYRE_NO)，不能用 COUNT(1)**：一条胎可能有多条检验记录（不同缺陷），COUNT(1) 会重复计。检测总数是"检测了多少条胎"。

## 八、STRING_AGG 内存授予优化（重要）

**踩坑**：原写法在 INSERT 的子查询内部用**相关子查询**做 STRING_AGG（`WHERE tt1.MATERIALID = t1.MATERIALID`），优化器对"不定长字符串拼接后的中间结果"悲观估算，内存授予虚高（知识库 `sql-server-performance-troubleshooting.md` 实战案例：250MB→8MB 的同类坑）。

**优化方案**（参照实战案例"明细先落临时表"）：先按(规格,缺陷名)聚合落临时表，再在小临时表上做 STRING_AGG：
```sql
-- 明细先落临时表（行数确定、字段定长、自动统计信息）
SELECT t2.MATERIAL_NAME, ISNULL(t3.DEFECT_NAME,'未定义不良') AS DEFECT_NAME, COUNT(1) AS NUM
  INTO #BadDetail FROM FQF_FCHECK_INFO t1 ... GROUP BY t2.MATERIAL_NAME, ISNULL(t3.DEFECT_NAME,'未定义不良');
-- 最终 INSERT 在小临时表上做 STRING_AGG
SELECT MATERIAL_NAME,
       STRING_AGG(CAST(CONCAT(DEFECT_NAME,'-',NUM) AS VARCHAR(MAX)),', ') WITHIN GROUP (ORDER BY NUM DESC)
  FROM #BadDetail GROUP BY MATERIAL_NAME;
```

> ⚠️ **任何 STRING_AGG 都不要放在相关子查询里**。先物化到临时表，再在小表上聚合。

## 九、布局：表单抬头 + GridPanel + HTML 总计（踩坑：GridPanel 不能放 Content）

```xml
<ext:Panel ID="plCenter" Region="Center" Layout="VBoxLayout">
  <LayoutConfig><ext:VBoxLayoutConfig Align="Stretch" /></LayoutConfig>
  <Items>
    <ext:Panel ID="panelHeader"><Content>...抬头 HTML...</Content></ext:Panel>
    <ext:GridPanel ID="gridMain" Flex="1">...Store/ColumnModel...</ext:GridPanel>
    <ext:Panel ID="panelFooter"><Content>...总计 table + 规则 + 保管期限...</Content></ext:Panel>
  </Items>
</ext:Panel>
```

> ⚠️ **GridPanel 不能放在 Panel 的 `<Content>` 里**——Content 只放静态 HTML，放 Ext 服务端控件会出错。GridPanel 必须在 `<Items>` 里。

## 十、明细列换行 + 其他列垂直居中（踩坑：TdCls 类名）

**坑：TdCls 和 .x-grid-cell-DataIndex 都不生效**：Ext.NET 实际生成的列类名是 `x-grid-cell-gridcolumn-1015`（自动 ID），不是 DataIndex 名。

**正确方案：Renderer 内联样式 + 全局 CSS**
```xml
<ext:Column Text="不良明细" DataIndex="BAD_DETAIL" Align="Left">
  <Renderer Handler="return value == null ? '' : '<div style=\"text-align:left;\">' + ('' + value).split(',').map(function(s){return '<span style=\"display:inline-block;white-space:nowrap;margin-right:6px;\">'+s+'</span>';}).join('') + '</div>';" />
</ext:Column>
```
```css
.x-grid-cell-inner { text-overflow: clip !important; overflow: visible !important; white-space: normal !important; }
.x-grid-row .x-grid-cell { vertical-align: middle !important; }
```

## 十一、作业员流式换行（contenteditable div，踩坑重重）

**需求**：作业员流式排列——每个机台段作为整体，一行排到末尾才换行，整段不被拆断。且**只读 + 带滚动条 + 不撑高布局**。

**textarea 方案失败**：textarea 是纯文本，无法用 inline-block 包裹每段；`word-break:keep-all` 对视觉软换行不可靠。

**正确方案：contenteditable div + inline-block span**
```html
<div id="txtOperator" class="cdr-input-multiline" contenteditable="false"></div>
```
```css
.cdr-input-multiline { height: 34px; box-sizing: border-box; overflow-y: auto; word-break: keep-all; }
.cdr-input-multiline .fitem { display: inline-block; white-space: nowrap; margin-right: 8px; }
```
```javascript
// applyHeaderData 回填：按分号拆段，每段 span 包裹
el.innerHTML = ('' + v).split(/[；;]/).filter(s=>s.trim())
    .map(s => '<span class="fitem">'+s.trim()+'</span>').join('');
// Save 保存：取 innerText 转回分号分隔
var op = (el.innerText||el.textContent||'').replace(/[\r\n\s]+/g,';').replace(/;+/g,';').replace(/^;|;$/g,'');
```

**踩坑**：
- contenteditable=false 禁止编辑后，**点击仍触发保存按钮** → bindInputFocus 选择器不要包含 div（只用 `input[id^="txt"], textarea[id^="txt"]`）
- div 设 max-height 不生效（td 会撑高）→ 改用固定 `height` + `box-sizing:border-box`
- showSaveBtn/cancelEdit 用 `el.value` 对 div 无效 → div 用 innerHTML 存/恢复

## 十二、权限定义（ActionId 是序号不是 ACTION_ID）

```csharp
public class __ : Wongoing.Web.UI.___
{
    public __()
    {
        查询 = new PageAction() { ActionId = 1, ActionName = "btnSearch" };  // 页面内序号
        编辑 = new PageAction() { ActionId = 2, ActionName = "btnSave" };
    }
}
private const int EditActionId = 49464;  // 真正的权限校验值（查 V_SSP_USER_ALL_ACTION）
```

## 十三、GridPanel 按合计倒序排序

Store 的 Model 上不能加 Sorters（Model 无此属性），要在 **Store** 上加：
```xml
<ext:Store ID="storeMain" runat="server" PageSize="200">
    <Model>...</Model>
    <Sorters><ext:DataSorter Property="TOTAL_QTY" Direction="DESC" /></Sorters>
</ext:Store>
```

## 十四、SQL/Ext.NET 踩坑速查

| 坑 | 正解 |
|---|---|
| `OPTION (RECOMPILE)` 报语法错误 | 必须紧跟它作用的 DML 语句末尾（WHERE 后、分号前），不能孤悬在 DROP/END 之间 |
| GRADE='1' 查不到数据 | GRADE 是数值列，用 `GRADE = 1`（无引号） |
| 周期号查 GETDATE() 不对 | 用 @Report（报表日期），班次跨天时 GETDATE() 不是统计日 |
| 两个合计都为0的规格占行 | INSERT 的 WHERE 加 `AND (ISNULL(BAD_QTY,0)+ISNULL(SCRAP_QTY,0)) > 0` |
| 不良重复计废品胎 | 不良子查询加 `NOT EXISTS (SELECT 1 FROM #ScrapAll WHERE TYRE_NO=t1.TYRE_NO)` |
| 检测总数重复计胎 | 用 `COUNT(DISTINCT TYRE_NO)`，不能用 `COUNT(1)` |
| STRING_AGG 内存授予虚高 | 不放相关子查询，先物化到临时表再聚合 |
| `cmbShift.SelectedIndex = 0` 报错 | ComboBox 无 SelectedIndex，用 `<SelectedItems><ext:ListItem Value="D" /></SelectedItems>` |
| `DefaultMargins` 属性不存在 | 改用各子 Panel 的 `MarginSpec="0 0 8 0"` |
| 每页条数默认值触发空查询 | `<SelectedItems>` 设默认值，但不要配 `<Change>` 监听；首屏由 Page_Load 加载 |
| Model 不支持 Sorters | 在 Store 上加 Sorters，不是 Model |
| contenteditable div 点击仍弹保存按钮 | bindInputFocus 选择器排除 div，只用 input/textarea |

## 十五、SQL 优化检查结论（对照知识库 11 条原则）

| 原则 | 结论 |
|---|---|
| 1. 缩小范围 | ✅ 都带时间窗 |
| 2. 字段禁函数（SARGable） | ⚠️ 周期号 `CAST(STR_DATE AS DATE)` 字段套函数，但 `tb_EQ_SET_DOT_RULES` 数据量极小（几十条），全表扫描无影响，且与现网 Mould 项目写法一致，**不改** |
| 3. 控制 JOIN | ✅ 不良 2 表、废品 1 表 |
| 4. 禁 SELECT * / count(字段) | ✅ 用 COUNT(1)；检测总数用 COUNT(DISTINCT TYRE_NO) |
| 5. 隐式类型转换 | ✅ GRADE=1（数值）、WORK_PROCESS_ID='4'（string，已核对实体）|
| 7/9. 参数嗅探 | ✅ 末尾 OPTION (RECOMPILE) |
| STRING_AGG 内存授予 | ⚠️ 已优化（改临时表）|

> 经验：小表（如配置表 tb_EQ_SET_DOT_RULES）的字段套函数可接受，不用为它建索引或改写。大表（FQF_FCHECK_INFO）的 STRING_AGG 必须物化到临时表。

## 十六、文件清单（新建）

- 实体四件套：`CppFcheckDailyData.cs` + Data/Business 的 Interface/Implements + BasicMapper/CppFcheckDailyData.xml
- BusinessMapper/CppFcheckDailyData.xml（查D行/查H行/UpsertH行/权限校验）
- 页面：`FirstInspectionDailyReport.aspx(.cs)`
- SQL：`resources/xls/Proc_FcheckDailyReport.sql`（含建表DDL + 存储过程）
