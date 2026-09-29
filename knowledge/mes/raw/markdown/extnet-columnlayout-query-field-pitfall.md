---
title: ColumnLayout 查询条件区新增字段导致列错位踩坑
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, ColumnLayout, 布局, 踩坑]
updated: 2026-08-29
status: active
---
# ColumnLayout 查询条件区新增字段导致列错位踩坑

> Ext.NET 报表页面查询条件区 FormPanel + ColumnLayout（一行 4 列 Container）布局下，新增查询字段引发列错位的现象、原因与修法。

## 一、场景
报表页面查询条件区用 `FormPanel + ColumnLayout`，每个 `ext:Container`（`Layout=FormLayout`、`ColumnWidth=".25"`，即一行 4 列）承载若干查询字段。
典型页：`MonthlyPassRateTrend.aspx`（月别合格率趋势）。

当需求要求"把某个新增字段放到某字段正下方"（例：给硫化工程增加「左右模」下拉框，并放在「机台」下方）时，**直接新增一个独立 `Container` 会破坏列布局**。

## 二、错误写法（列错位、换行对不齐）
新增字段单独放进一个新 Container，同时又保留原来每字段各占一列的容器：
```xml
<ext:Container ID="container4" ... ColumnWidth=".25">
    <Items>
        <ext:ComboBox ID="txt_equip_id" FieldLabel="机台" .../>   <!-- 独占一列 -->
    </Items>
</ext:Container>
<ext:Container ID="container_equip_position" ... ColumnWidth=".25">  <!-- ❌ 多占一列 -->
    <Items>
        <ext:ComboBox ID="txt_equip_position" FieldLabel="左右模" .../>
    </Items>
</ext:Container>
```
后果：第一行 4 列排满后，新增字段被挤到第二行最左列（月份下方），不在机台下方；且原第二行字段（合格次数、项目）若仍各自独占一列，会出现列数参差、整体换行错位。

## 三、正确写法（同列内 FormLayout 垂直堆叠）
**把新增字段加进目标字段所在的同一 Container**，FormLayout 内多控件天然上下堆叠。
关键是同时把"第二行"的字段合并进对应列，形成整齐的 4×2 矩阵：
```xml
<ext:Container ID="container1" ... ColumnWidth=".25">
    <Items>
        <ext:DateField   ID="txt_year_month" FieldLabel="月份"     .../>
        <ext:ComboBox    ID="txt_pass_count" FieldLabel="合格次数" .../>   <!-- 合并进本列 -->
    </Items>
</ext:Container>
<ext:Container ID="container2" ... ColumnWidth=".25">
    <Items>
        <ext:TextField   ID="txt_material_name" FieldLabel="规格代码" .../>
        <ext:ComboBox    ID="txt_metric_type"   FieldLabel="项目"    .../>   <!-- 合并进本列 -->
    </Items>
</ext:Container>
<ext:Container ID="container3" ... ColumnWidth=".25">
    <Items>
        <ext:ComboBox ID="txt_process_type" FieldLabel="工程" .../>          <!-- 单字段 -->
    </Items>
</ext:Container>
<ext:Container ID="container4" ... ColumnWidth=".25">
    <Items>
        <ext:ComboBox ID="txt_equip_id"       FieldLabel="机台"   .../>
        <ext:ComboBox ID="txt_equip_position" FieldLabel="左右模" .../>       <!-- ✅ 紧贴机台下方 -->
    </Items>
</ext:Container>
```
渲染结果：4 列 × 2 行，左右模自然落在机台正下方。

## 四、关键点
- `FormLayout` 容器内放多个表单控件，会自动**垂直堆叠**（自上而下），无需额外布局。
- 一个 `Container` 占几"格高"由其内部控件数决定，**不影响其它列宽度**（列宽只由 `ColumnWidth` 决定）。
- 不要为了"对齐"而拆出独立 Container；对齐靠的是把同列字段收进同一个 FormLayout 容器。
- `ColumnWidth=".25"` = 4 列布局；若每列控件数不同，列宽仍对齐，但视觉高度不齐，属正常。

## 五、关联
- 本踩坑来源于 `MonthlyPassRateTrend.aspx` 增加「左右模(L/R)」过滤条件的需求。
- 左右模数据来源 `CPP_CURING_PRODUCTION.EQUIP_POSITION`（值 `'L'`/`'R'`），仅硫化工程有该列；成型(`BPM_PRODUCTION`)无此列。
- 页面详细 SQL/后台透传逻辑见 `monthly-pass-rate-trend.md`。
