---
title: 两类记录合并展示报表（UNION ALL + 单表类型列）
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, 报表模板, UNION ALL, DataTable合并, 命名空间冲突, ComboBox取值, 类型过滤, 踩坑]
updated: 2026-08-29
status: active
---
# 两类记录合并展示报表（UNION ALL + 单表类型列）

> 把两类来源不同的记录（如"出库明细"+"出厂记录"）合并到同一个 GridPanel，用「类型」列区分，支持按类型下拉过滤 + 客户端分页 + 导出全量。核心决策：合并一律在 SQL 层做 UNION ALL + TYPE 列（C# 端 typeof(object) 列手工合并会丢列类型、前端显示空白）；类型过滤须套最外层子查询；附 DataView 二义性、ComboBox.Value 是 object 等编译期踩坑与 BuildParam"空则不传"模式。

适用场景：业务上两类记录字段大致相同、需要在一张表里对照查看。

## 一、整体方案选型

| 方案 | 做法 | 问题 |
|------|------|------|
| ❌ C# 手工合并 DataTable | 两个查询各返回 DataTable，C# 新建 `typeof(object)` 列拼装 | **重量/日期列类型丢失，前端显示空白**（见踩坑1） |
| ✅ SQL UNION ALL 合并 | 一个 statement 用 UNION ALL 合并两分支，新增 TYPE 列 | 列类型由数据库决定，前端正常显示 |

**结论：合并一律在 SQL 层做 UNION ALL，不要在 C# 端用 object 列拼装。**

## 二、SQL：UNION ALL 合并 + TYPE 列 + 外层过滤

### 2.1 基本结构

```xml
<select id="SelectXxx@HppSemisProduction" parameterClass="map" resultClass="row">
    SELECT * FROM (
        SELECT ROW_NUMBER() OVER (ORDER BY y.OUT_TIME) AS ID,
               y.TYPE, y.MATERIAL_NAME, y.REAL_WEIGHT, ...
        FROM (
            -- 分支1：混合出库
            SELECT '混合出库' AS TYPE,
                   t2.Mater_name AS MATERIAL_NAME, t1.RealWeight AS REAL_WEIGHT, ...
            FROM 表1 t1
            LEFT JOIN ...
            WHERE t1.BarCode LIKE 'R%'
            <isNotEmpty prepend="AND" property="BEGIN_DATE"><![CDATA[ t1.InTime >= #BEGIN_DATE# ]]></isNotEmpty>
            UNION ALL
            -- 分支2：出厂
            SELECT '出厂' AS TYPE,
                   t2.MATERIAL_NAME AS MATERIAL_NAME, t1.WEIGHT AS REAL_WEIGHT,
                   NULL AS STOCK_NAME, NULL AS STOCK_PLACE_NO, ...   -- 缺失列用 NULL 占位
            FROM 表2 t1
            LEFT JOIN ...
            WHERE t1.BARCODE LIKE 'R%'
            <isNotEmpty prepend="AND" property="BEGIN_DATE"><![CDATA[ t1.RECORD_TIME >= #BEGIN_DATE# ]]></isNotEmpty>
        ) y
    ) z
    <dynamic prepend="WHERE">
        <isNotEmpty prepend="AND" property="TYPE"><![CDATA[ z.TYPE = #TYPE# ]]></isNotEmpty>
    </dynamic>
    ORDER BY z.OUT_TIME
</select>
```

### 2.2 关键要点

1. **两分支列数、列顺序、列类型必须一致**。分支2缺失的列（如库房/库位）用 `NULL AS 列名` 占位。
2. **TYPE 列写死在每分支 SELECT 列表里**（`'混合出库'` / `'出厂'`）。
3. **序号 ID**：在外层用 `ROW_NUMBER() OVER (ORDER BY 时间字段)` 生成，统一排序后编号，不要让两分支各自编号。
4. **类型过滤放最外层**：因为 TYPE 区分在 UNION 内部，必须再套一层 `z` 子查询，在 `z` 上加 `<isNotEmpty property="TYPE">` 过滤。直接在 UNION 分支里过滤会重复且混乱。
5. **iBATIS 的 `<isNotEmpty>` 在 UNION 分支内同样生效**：每个分支都能带自己的 BEGIN_DATE/END_DATE/MATERIAL_NAME/BARCODE 动态条件。

> **与 `semi-return-rubber-ratio-report.md` 的区别**：那篇是 CTE + UNION ALL 带合计行，ORDER BY 受限要用 SORT_FLAG；本篇是纯明细合并，外层直接 `ORDER BY 时间` 即可。

## 三、前端：查询区类型下拉框（FieldTrigger 清空）

用户要在查询时就按类型过滤（不是表格列头筛选）。下拉框需要能"清空=查全部"：

```aspx
<ext:ComboBox ID="cmb_type" runat="server" FieldLabel="类型" LabelAlign="Right" Editable="false">
    <Items>
        <ext:ListItem Text="混合出库" Value="混合出库" />
        <ext:ListItem Text="出厂" Value="出厂" />
    </Items>
    <Triggers>
        <ext:FieldTrigger Icon="Clear" />
    </Triggers>
    <Listeners>
        <TriggerClick Handler="if (index == 0) this.clearValue();" />
    </Listeners>
</ext:ComboBox>
```

要点：
- **不要设默认"全部"选项**。用户要的是"可清空"，不是"固定选全部"。
- **清空按钮用 FieldTrigger + TriggerClick**（见 `extnet-event-mechanisms.md`）：`<Triggers><ext:FieldTrigger Icon="Clear" /></Triggers>` + `<TriggerClick Handler="this.clearValue();" />`。
- ❌ 不要用 `Clearable="true"` 属性——当前 Ext.NET 版本不支持，编译报错。
- 清空后 `SelectedItem.Value` 为空 → C# 端不传 TYPE 参数 → SQL 的 `<isNotEmpty>` 不生效 → 查全部。

## 四、前端：客户端分页（Store PageSize + PagingToolbar）

本报表选型**客户端分页**（数据量可能大 + 需导出全量：Session 缓存全量，翻页内存切片，导出读 Session）。

Store 写法要点：`PageSize="50"` 但**不加 PageProxy/RemotePaging**；每页条数 ComboBox `Editable="true" ForceSelection="false"` 且 `<SelectedItems>` 默认值与 Store PageSize 一致；Change 里 `pageSize = parseInt(...)` 后 `moveFirst()` 回首页。

完整实现（Store/PagingToolbar/刷新按钮接管/每页条数手输）见 [extnet-pagination-guide.md](extnet-pagination-guide.md) 方案一；导出全量不受分页影响（直接读 Session）。

## 五、踩坑清单

### 踩坑1：C# 用 typeof(object) 列手工合并 DataTable → 重量/日期前端空白

**现象**：两个查询分别返回 DataTable，C# 新建 `new DataColumn("REAL_WEIGHT", typeof(object))` 拼装合并后绑定 Store，前端"出库重量""出库时间"列显示为空。

**根因**：`typeof(object)` 列丢失了原始的数值/日期类型，Ext.NET Store 的 ModelField 无法正确解析，渲染为空。

**解决**：**合并逻辑放 SQL 层做 UNION ALL**，列类型由数据库决定，C# 端 `GetData()` 只做单次查询 + 直接 `DataBind`，不做手工合并。

### 踩坑2：DataView 命名空间二义性 CS0104

**现象**：在 aspx.cs 里 `using System.Data;` + `using Ext.Net;` 同时存在时，写 `DataView dv = ...` 报：
```text
CS0104: "DataView"是"System.Data.DataView"和"Ext.Net.DataView"之间的不明确的引用
```

**根因**：`System.Data` 和 `Ext.Net` 都有 `DataView` 类型。

**解决**：用完全限定名 `System.Data.DataView`。`DataTable`/`DataRow` 无此问题（Ext.Net 无同名类型）。

### 踩坑3：ComboBox.Value 是 object，不能直接传给 string.IsNullOrWhiteSpace → CS1502

**现象**：`if (!string.IsNullOrWhiteSpace(cmb_type.Value))` 报：
```text
CS1502: 与"string.IsNullOrWhiteSpace(string)"最匹配的重载方法具有一些无效参数
```

**根因**：Ext.NET 的 `ComboBox.Value` 是 `object` 类型，不是 `string`。

**解决**：用 `SelectedItem.Value`（string 类型）并判空：
```csharp
string typeVal = cmb_type.SelectedItem != null ? cmb_type.SelectedItem.Value : string.Empty;
if (!string.IsNullOrWhiteSpace(typeVal))
    p["TYPE"] = typeVal;
```
> `consumption-output-report.md` 的"踩坑3"只提到 Value 可能返回显示文本，本篇补充了它的**类型是 object** 这一编译期问题。

## 六、BuildParam 模式（可选参数统一处理）

```csharp
private Dictionary<string, object> BuildParam()
{
    var p = new Dictionary<string, object>();
    if (!string.IsNullOrWhiteSpace(txtbegindate.RawText))
        p["BEGIN_DATE"] = txtbegindate.RawText;
    if (!string.IsNullOrWhiteSpace(txtenddate.RawText))
    {
        string end = txtenddate.RawText;
        if (end.Length <= 10) end = end + " 23:59:59";
        p["END_DATE"] = end;
    }
    if (!string.IsNullOrWhiteSpace(txt_material_name.Text))
        p["MATERIAL_NAME"] = txt_material_name.Text;
    if (!string.IsNullOrWhiteSpace(txt_barcode.Text))
        p["BARCODE"] = txt_barcode.Text;
    // 类型：空值不传 → SQL <isNotEmpty> 不生效 → 查全部
    string typeVal = cmb_type.SelectedItem != null ? cmb_type.SelectedItem.Value : string.Empty;
    if (!string.IsNullOrWhiteSpace(typeVal))
        p["TYPE"] = typeVal;
    return p;
}
```

所有查询条件"空则不传"，配合 SQL 的 `<isNotEmpty prepend="AND">`，天然实现"不填=不过滤"。

## 七、关联文档

| 文档 | 内容 |
|------|------|
| `semi-return-rubber-ratio-report.md` | CTE+UNION ALL 带合计行，ORDER BY 限制与 SORT_FLAG 解法 |
| `extnet-event-mechanisms.md` | FieldTrigger + TriggerClick 清空触发器原始写法 |
| `extnet-combobox-properties.md` | ComboBox 属性速查、clearValue 客户端方法 |
| `extnet-pagination-guide.md` | 客户端分页完整指南、每页条数 ForceSelection 踩坑 |
| `extnet-pagination-guide.md` | 服务端分页(Session缓存)方案，ServerMapping 失效坑 |
| `standard-report-template.md` | 标准报表页面模板 |
| `consumption-output-report.md` | ComboBox Value 取值坑(SelectedItem.Value) |
