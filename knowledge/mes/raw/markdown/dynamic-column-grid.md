---
title: 动态列 GridPanel 实现指南
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, GridPanel, 动态列, 重建列模型, ColumnModel, ColumnAlign, CS0103, CS0246, CS0266, 官方示例, 踩坑, GetRowClass, 零列空白]
status: active
updated: '2026-09-19'
---
# 动态列 GridPanel 实现指南

> 按 DataTable 动态生成 GridPanel 列的完整套路：ChangeModels 后台先清空再重建 Model/Columns（ModelField 的 Name 必须与列名一致，改后 store.DataBind() + grid.Render()），支持分组列、Renderer（Fn / Handler 两种方式）、按 _AVG/_SIG/_PassRate 后缀自动生成检测项分组列，含总计行样式、条件高亮格式化函数与弹窗动态 Grid 变体。权威官方示例：`Examples/GridPanel/ColumnModel/Change_Models`（运行时换列模型）、`ColumnModel/Reconfigure`。

## 一、概述

在Quality项目中，经常需要根据存储过程返回的数据动态生成GridPanel的列。本文档介绍如何实现动态列显示功能。

## 二、核心实现步骤

### 1. 前端GridPanel定义

```aspx
<ext:GridPanel ID="pnlMain" runat="server" Region="Center">
    <Store>
        <ext:Store ID="storeMain" runat="server" AutoLoad="false" PageSize="100">
            <Model>
                <ext:Model ID="model" runat="server">
                </ext:Model>
            </Model>
        </ext:Store>
    </Store>
    <ColumnModel>
        <Columns>
        </Columns>
    </ColumnModel>
    <SelectionModel>
        <ext:RowSelectionModel runat="server" Mode="Single" />
    </SelectionModel>
</ext:GridPanel>
```

**关键点**：Model和Columns初始为空，由后台动态填充。

### 2. 后台动态构建方法

```csharp
private void ChangeModels(DataTable dt)
{
    Store store = this.storeMain;
    GridPanel grid = this.pnlMain;

    // 1. 清空现有配置
    store.Reader.Clear();
    store.Model.Clear();
    grid.ColumnModel.Columns.RemoveRange(0, grid.ColumnModel.Columns.Count);

    // 2. 创建新的Model
    Model model = new Model();

    // 3. 添加ModelField
    foreach (DataColumn col in dt.Columns)
    {
        model.Fields.Add(new ModelField(new ModelField.Config
        {
            Name = col.ColumnName,
            Mapping = col.ColumnName,
            ServerMapping = col.ColumnName
        }));
    }

    // 4. 添加列
    foreach (DataColumn col in dt.Columns)
    {
        grid.ColumnModel.Columns.Add(new Ext.Net.Column
        {
            Text = col.ColumnName,
            DataIndex = col.ColumnName,
            Width = 80,
            Align = ColumnAlign.Center
        });
    }

    // 5. 添加Model到Store
    store.Model.Add(model);

    // 6. 绑定数据
    store.DataSource = dt;
    store.DataBind();

    // 7. 渲染Grid
    grid.Render();
}
```

### 3. 分组列实现

```csharp
// 创建分组列
var groupColumn = new Ext.Net.Column { Text = "合格" };

// 添加子列
groupColumn.Columns.Add(new Ext.Net.Column
{
    Text = "检查数量",
    DataIndex = "CheckCount",
    Width = 70,
    Align = ColumnAlign.Center
});

groupColumn.Columns.Add(new Ext.Net.Column
{
    Text = "合格率",
    DataIndex = "PassRate",
    Width = 65,
    Align = ColumnAlign.Center,
    Renderer = new Renderer { Fn = "formatPassRate" }
});

// 添加到Grid
grid.ColumnModel.Columns.Add(groupColumn);
```

### 4. 带Renderer的列

```csharp
// 使用前端JavaScript函数作为Renderer
grid.ColumnModel.Columns.Add(new Ext.Net.Column
{
    Text = "合格率",
    DataIndex = "PassRate",
    Width = 65,
    Align = ColumnAlign.Center,
    Renderer = new Renderer { Fn = "formatPassRate" }
});

// 使用Handler方式（可传参数）
grid.ColumnModel.Columns.Add(new Ext.Net.Column
{
    Text = "RFV_PassRate",
    DataIndex = "RFV_PassRate",
    Renderer = new Renderer { 
        Handler = "return formatItemPassRateByField(value, metadata, record, 'RFV_PassRate');" 
    }
});
```

### 5. 动态检测项列

```csharp
// 提取检测项前缀（以_AVG结尾的列）
var checkItemPrefixes = new List<string>();
foreach (DataColumn col in dt.Columns)
{
    if (col.ColumnName.EndsWith("_AVG"))
    {
        string prefix = col.ColumnName.Substring(0, col.ColumnName.Length - 4);
        checkItemPrefixes.Add(prefix);
    }
}

// 为每个检测项创建分组列
foreach (string prefix in checkItemPrefixes)
{
    bool hasSIG = dt.Columns.Contains(prefix + "_SIG");

    var itemColumn = new Ext.Net.Column { Text = prefix };

    // AVG列
    itemColumn.Columns.Add(new Ext.Net.Column
    {
        Text = "AVG",
        DataIndex = prefix + "_AVG",
        Width = 55,
        Align = ColumnAlign.Center,
        Renderer = new Renderer { Fn = "formatDecimal" }
    });

    // SIG列（如果存在）
    if (hasSIG)
    {
        itemColumn.Columns.Add(new Ext.Net.Column
        {
            Text = "SIG",
            DataIndex = prefix + "_SIG",
            Width = 55,
            Align = ColumnAlign.Center
        });
    }

    // PassRate列
    if (dt.Columns.Contains(prefix + "_PassRate"))
    {
        itemColumn.Columns.Add(new Ext.Net.Column
        {
            Text = "PassRate",
            DataIndex = prefix + "_PassRate",
            Width = 60,
            Align = ColumnAlign.Center
        });
    }

    grid.ColumnModel.Columns.Add(itemColumn);
}
```

## 三、前端格式化函数

### 基础格式化

```javascript
// 保留两位小数
var formatDecimal = function (value) {
    if (value == null || value === '') return '';
    return parseFloat(value).toFixed(2);
};

// 百分比
var formatPassRate = function (value) {
    if (value == null || value === '') return '';
    return parseFloat(value).toFixed(2) + '%';
};
```

### 带条件高亮的格式化

```javascript
// 值超过阈值时字体标红
var formatConAvg = function (value, metadata) {
    if (value == null || value === '') return '';
    var numValue = parseFloat(value);
    if (isNaN(numValue)) return value;
    if (numValue > 2 || numValue < -2) {
        metadata.style = 'color: red; font-weight: bold;';
    }
    return numValue.toFixed(2);
};

// 合格率低于阈值时背景高亮
var formatPassRateHighlight = function (value, metadata, record) {
    if (value == null || value === '') return '';
    var maxValue = getGroupMaxPassRate(record.store, record.get('OERE'), record.get('MaterialCode'));
    if (shouldHighlight(value, maxValue)) {
        metadata.tdCls = 'highlight-red';
    }
    return parseFloat(value).toFixed(2) + '%';
};
```

## 四、行样式控制

```javascript
// 总计行特殊样式
var getRowClass = function (record) {
    if (record.get('RowType') == 'TOTAL') {
        return 'total-row';
    }
    return '';
};
```

```aspx
<ext:GridView runat="server" StripeRows="true" TrackOver="true">
    <GetRowClass Fn="getRowClass" />
</ext:GridView>
```

**⚠️ GetRowClass 必须是 `<ext:GridView>` 的直接子元素**（2026-09-19 Curing 实证）：包进 `<Listeners><GetRowClass .../></Listeners>` 报分析器错误「类型 Ext.Net.GridViewListeners 不具有名为 GetRowClass 的公共属性」。返回的类名挂在行内层 `tr` 上（`tr class="total-row x-grid-row"`），DOM 取证要查 `node.querySelector('tr').className` 而非外层 wrapper div。

```css
.x-grid-row .total-row {
    background-color: #e8f4f8 !important;
    font-weight: bold;
}

.highlight-red {
    background-color: #ff6666 !important;
}
```

## 五、清空Grid方法

```csharp
private void ClearGrid()
{
    Store store = this.storeMain;
    GridPanel grid = this.pnlMain;

    store.Reader.Clear();
    store.Model.Clear();
    grid.ColumnModel.Columns.RemoveRange(0, grid.ColumnModel.Columns.Count);

    Model model = new Model();
    store.Model.Add(model);

    store.DataSource = new DataTable();
    store.DataBind();
    grid.Render();
}
```

## 六、弹窗中的动态Grid

```csharp
[DirectMethod]
public string ShowDetailPopup(string param)
{
    DataSet ds = GetData(param);
    BindPopupGrid(ds);
    winDetail.Show();
    return "";
}

private void BindPopupGrid(DataSet ds)
{
    Store store = storeDetail;
    GridPanel grid = gridDetail;

    // 清空现有配置
    store.Reader.Clear();
    store.Model.Clear();
    grid.ColumnModel.Columns.RemoveRange(0, grid.ColumnModel.Columns.Count);

    if (ds == null || ds.Tables.Count == 0) return;

    DataTable dt = ds.Tables[0];
    Model mdl = new Model();

    foreach (DataColumn col in dt.Columns)
    {
        mdl.Fields.Add(new ModelField(new ModelField.Config
        {
            Name = col.ColumnName,
            Mapping = col.ColumnName
        }));

        grid.ColumnModel.Columns.Add(new Ext.Net.Column
        {
            Text = col.ColumnName,
            DataIndex = col.ColumnName,
            Width = 80,
            Align = ColumnAlign.Center
        });
    }

    store.Model.Add(mdl);
    store.DataSource = dt;
    store.DataBind();
    grid.Render();
}
```

## 七、注意事项

1. **必须清空现有配置**：在重新绑定前必须清空Model和Columns，否则会重复添加
2. **Model字段必须匹配**：ModelField的Name必须与DataTable列名一致
3. **Renderer函数**：前端格式化函数必须在script标签中定义
4. **Render调用**：动态修改后需要调用grid.Render()刷新界面
5. **DataBind**：必须调用store.DataBind()绑定数据
6. **⚠️ aspx 里的 ColumnModel/Model 没有 code-behind 字段（2026-09-04 实证）**：`<ext:ColumnModel ID="colModel">`、`<ext:Model ID="modelMain">` 是属性级元素（非控件），Website 模式（@Page CodeFile 无 designer 文件）下 ASP.NET 动态生成的 partial **不会**为它们生成字段——code-behind 直接引用 `colModel`/`modelMain` 编译报 **CS0103 当前上下文中不存在名称**。Store/GridPanel/ComboBox 等真控件才有字段。正解：经控件字段访问 `gridMain.ColumnModel.Columns`、`storeMain.Model`（本文所有示例即此写法，勿照抄 aspx 里的 ID 直接引用）
7. **⚠️ Ext.NET 4.7.1 无 `Ext.Net.ColumnModel` 公开类型（2026-09-04 实证）**：想声明局部变量 `ColumnModel cm = grid.ColumnModel;` 报 **CS0246**（反射确认 dll 里只有 Ext.Net.ColumnBase/ColumnAlign，无 ColumnModel 类型）。正解：`var cm = gridMain.ColumnModel;`
8. **⚠️ 列的 Align 是 `ColumnAlign` 不是 `Alignment`（2026-09-04 实证）**：`Column.Align = Alignment.Center` 报 **CS0266 无法隐式转换**。列/RowNumbererColumn 的对齐用 `ColumnAlign.Center`；`Alignment` 枚举是别的控件（如 DrawText）用的
9. **编译验证捷径（无 MSBuild/VS 时）**：用 `C:\Windows\Microsoft.NET\Framework64\v4.0.30319\aspnet_compiler.exe -v / -p <网站根> -u -f <临时输出目录>` 全站预编译，可完整验证 Website 项目（CodeFile 动态编译页面）的 aspx 标记解析 + code-behind 编译，且 v4.0.30319 的 csc 正是 C#5 编译器，顺带验证 C#5 合规。验证完删除临时输出目录即可
10. **⚠️ 「Store 有数、视图空白」= 四步不全的典型症状（2026-09-19 Curing MonthlyProductionPlan 实证，designer P1 打回）**：偷懒写法 `model1.Fields.Clear()+Add` + `ColumnModel.Columns.Clear()+Add` + `DataBind()`（漏 Reader.Clear / RemoveRange / 整体替换 Model / grid.Render）后——分页条显示"共 N 条"、`record.data` 可读（数据真进 Store 了），但 `getView().getNodes()=0`、`headerCt.getGridColumns().length=0`，主表区纯空白无列头。此时改 aspx 补空 `<ColumnModel ID>` 没用（见第 6 条）。正解=严格按第二节 1~7 步全做；排查用 DOM 三查：viewNodes / headerCols / tr.className，**不要依赖截图视觉判断**（视觉模型误报过相反结论）

## 八、相关文件示例

| 文件 | 说明 |
|------|------|
| MoldingEquipDifference.aspx.cs | 成型机差异分析，完整动态列实现 |
| CheckEquipDifference.aspx.cs | 设备差异分析，带高亮功能 |
| DBCheckEquipDifference.aspx.cs | DB检测差异分析 |
| Batch 项目 SemisDailyReport.aspx.cs（2026-09-04） | 11 版式动态多级表头（机台类型切换重建列模型，分组嵌套列 + 行号列 + Renderer） |
| Curing 项目 MonthlyProductionPlan.aspx.cs（2026-09-19） | 固定列+动态版本列混合（版本列按实际版本号集合生成）；第 10 条症状的实证页；页面全貌见 [[monthly-production-plan-report]] |
