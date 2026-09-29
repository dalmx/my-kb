---
title: Ext.NET Chart 图表控件完整指南
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Chart, 图表, CartesianChart, PolarChart, 柱状图, 饼图, 折线图, 雷达图, 仪表盘]
updated: 2026-08-29
status: active
---
# Ext.NET Chart 图表控件完整指南

> 本文档从 Ext.NET 4.7.1 官方示例库 `Examples/Chart/`（57 个示例）提炼，覆盖柱/条/折线/饼/雷达/仪表盘/面积/散点/金融等全图表类型。目标是让 AI/开发者读完即可在任意 Ext.NET WebForms 项目复现图表用法。
>
> 适用：Ext.NET 4.x + Triton 主题。底层是 ExtJS 5/6 的 `Ext.chart` 包。

---

## 一、心智模型：三个层级

Ext.NET Chart 的核心是**三段式结构**，所有图表都逃不出这个框架：

```text
CartesianChart / PolarChart   ← ① 容器（决定坐标系：直角 vs 极坐标）
   ├── Store + Model           ← ② 数据（字段定义）
   ├── Axes (坐标轴集合)         ← ② 刻度系统（直角图必需）
   └── Series (系列集合)        ← ③ 图形（柱/线/饼...，绑定字段）
```

**关键认知**：
- **CartesianChart（笛卡尔/直角坐标系）**：柱状图、条形图、折线图、面积图、散点图。有明确的 X/Y 轴。
- **PolarChart（极坐标系）**：饼图、雷达图、仪表盘。圆形布局。
- 图表本身不存数据，数据全在 `<Store>` 里；Series 只通过 `XField`/`YField`/`AngleField` 等声明"用哪个字段画"。

---

## 二、图表容器选择

| 容器控件 | 坐标系 | 适用图表 | 是否需要 `<Axes>` |
|---------|--------|---------|------------------|
| `<ext:CartesianChart>` | 直角坐标（X-Y） | 柱/条/线/面积/散点/烛台 | **必需** |
| `<ext:PolarChart>` | 极坐标（圆） | 饼/雷达/仪表盘 | 饼图可省略；雷达/仪表盘需要 |

### 容器通用属性

| 属性 | 作用 | 常用值 |
|------|------|--------|
| `Width` / `Height` | 图表尺寸 | 数值（px） |
| `InsetPadding` | 内边距（四周统一） | `40`（数值） |
| `InsetPaddingSpec` | 内边距（分别指定） | `"10 40 40 40"`（上右下左） |
| `InnerPadding` | 内容区内边距（饼图常用） | `20` |
| `FlipXY` | **交换 X/Y 轴**（柱状图↔条形图） | `true` 时竖柱变横条 |
| `Shadow` | 阴影 | `true`（饼图常用） |
| `StyleSpec` | 内联样式 | `"background:#fff;"` |
| `Flex` | 在 HBox/VBox 布局中弹性伸缩 | `1`（多图并排时） |

> **柱状图 vs 条形图**：两者都用 `BarSeries`，区别只在容器 `FlipXY`。`FlipXY="false"`（默认）= 竖向柱状；`FlipXY="true"` = 横向条形。

### 容器子元素集合

| 子集合 | 作用 |
|--------|------|
| `<Store>` | 数据源 |
| `<Axes>` | 坐标轴（Cartesian 必需） |
| `<Series>` | 图形系列 |
| `<LegendConfig>` | 图例配置 |
| `<Interactions>` | 交互（缩放/旋转/高亮） |
| `<Items>` | 浮层 Sprite（标题文字、水印等） |
| `<AnimationConfig>` | 动画（Duration/Easing） |

---

## 三、数据绑定（Store + Model）

所有图表的**第一段**都是 Store；ModelField 名即 Series 的 xField/yField 引用名。填充方式三种：**内联静态**（`GetStore().DataSource = List<object>` + `Page_Load` 里非 Ajax 时赋值）、**Data 属性声明式**（`Data="<%# MyData %>" AutoDataBind="true"`）、**AjaxProxy 远程**——三种方式的完整写法见 [extnet-store-databinding-guide.md](extnet-store-databinding-guide.md) 三/四章。

图表特有的两点：
- 后端刷新必须 `GetStore().DataSource = data; GetStore().DataBind();`——`DataBind()` 触发图表重绘
- 数值字段声明 `Type="Float"`，否则 Series 求值可能按字符串处理

## 四、坐标轴 Axes（直角图核心）

直角图**必须声明 Axes**，否则无法定位数据点。每个轴有 `Position` 决定它画在哪条边。

### 轴类型速查

| 轴控件 | 作用 | 典型 Position |
|--------|------|--------------|
| `<ext:NumericAxis>` | 数值轴（连续数字） | `Left` / `Bottom` / `Gauge` / `Radial` |
| `<ext:CategoryAxis>` | 类别轴（离散标签：月份、名称） | `Bottom` / `Left` / `Angular` |
| `<ext:TimeAxis>` | 时间轴（按日期连续） | `Bottom` |
| 数值轴在 PolarChart | `Position="Radial"`（雷达半径）/ `"Angular"`（饼/雷达角度）/ `"Gauge"`（仪表盘） | — |

### 轴通用属性

| 属性 | 作用 |
|------|------|
| `Fields="Data1"` | 绑定的字段（可多个用逗号：`"Data1,Data2"`） |
| `Position="Left"` | 位置：`Left`/`Right`/`Top`/`Bottom`/`Radial`/`Angular`/`Gauge` |
| `Grid="true"` | 显示网格线 |
| `Minimum="0"` / `Maximum="100"` | 手动设范围（不设则自动） |
| `MajorTickSteps="10"` | 主刻度步数 |
| `AdjustByMajorUnit="true"` | 按主刻度自动调整范围 |

### 轴标签格式化（`<Renderer>`）

每个轴可挂 `<Renderer>`，用 JS 格式化刻度文字：

```aspx
<ext:NumericAxis Position="Left" Fields="Data1" Grid="true" Minimum="0" Maximum="100">
    <Renderer Handler="return label.toFixed(0) + '%';" />
</ext:NumericAxis>
```

- `label` 是当前刻度值
- `layoutContext.renderer(label)` 是默认格式化器（保留单位）

### 轴标签旋转

类别轴标签太长会重叠，用 `<Label>` 的 `RotationDegrees` 旋转：

```aspx
<ext:CategoryAxis Position="Bottom" Fields="Month" Grid="true">
    <Label RotationDegrees="-45" />
</ext:CategoryAxis>
```

### 多 Y 轴（双纵轴）

不同量纲的数据可分别挂左右两个 NumericAxis，每个轴绑不同 Field：

```aspx
<Axes>
    <ext:NumericAxis Position="Left" Fields="Data1" Grid="true" />
    <ext:NumericAxis Position="Right" Fields="Data2" Grid="true" />
    <ext:CategoryAxis Position="Bottom" Fields="Month" />
</Axes>
```

> Series 要用 `YAxis` 属性指明用左轴还是右轴（如 `YAxis="Right"`）。

---

## 五、各图表类型 Series 写法

### 1. 柱状图 / 条形图（BarSeries）

最常用的统计图。**柱 vs 条由容器 `FlipXY` 决定**。

```aspx
<ext:CartesianChart ID="Chart1" runat="server" FlipXY="false" InsetPadding="40" Height="500">
    <Store>...</Store>
    <Axes>
        <ext:NumericAxis Position="Left" Fields="Data1" Grid="true" />
        <ext:CategoryAxis Position="Bottom" Fields="Name" Grid="true" />
    </Axes>
    <Series>
        <ext:BarSeries XField="Name" YField="Data1">
            <Tooltip runat="server" TrackMouse="true">
                <Renderer Handler="toolTip.setHtml(record.get('Name') + ': ' + record.get('Data1'));" />
            </Tooltip>
        </ext:BarSeries>
    </Series>
</ext:CartesianChart>
```

**堆叠柱状图**（多字段叠加）：`YField` 写多个字段，加 `Stacked="true"`，`Titles` 给每个字段命名（图例显示）：

```aspx
<ext:BarSeries XField="Month"
    YField="Data1,Data2,Data3,Data4"
    Stacked="true"
    Titles="IE,Firefox,Chrome,Safari">
    <Tooltip runat="server" TrackMouse="true">
        <Renderer Handler="var s = context.series.getTitle()[Ext.Array.indexOf(context.series.getYField(), context.field)]; toolTip.setHtml(s + ': ' + record.get(context.field));" />
    </Tooltip>
</ext:BarSeries>
```

**100% 堆叠**（归一化）：`Stacked="true"` + `Stacked100="true"`，每列总和归一为 100%。

**样式与高亮**：

```aspx
<ext:BarSeries XField="Name" YField="Data1">
    <StyleSpec>
        <ext:SeriesSprite Opacity="0.8" MinGapWidth="10" />
    </StyleSpec>
    <HighlightConfig>
        <ext:Sprite FillStyle="rgba(249,204,157,1)" StrokeStyle="black" LineWidth="2" />
    </HighlightConfig>
</ext:BarSeries>
```

### 2. 折线图（LineSeries）

趋势分析首选。

```aspx
<ext:CartesianChart ID="Chart1" runat="server" InsetPadding="40">
    <Store>...</Store>
    <Interactions>
        <ext:PanZoomInteraction ZoomOnPanGesture="true" />
    </Interactions>
    <Axes>
        <ext:NumericAxis Position="Left" Fields="Data1" Grid="true" Minimum="0" Maximum="24" />
        <ext:CategoryAxis Position="Bottom" Fields="Month" Grid="true" />
    </Axes>
    <Series>
        <ext:LineSeries XField="Month" YField="Data1">
            <Tooltip runat="server" TrackMouse="true">
                <Renderer Handler="toolTip.setHtml(record.get('Month') + ': ' + record.get('Data1') + '%');" />
            </Tooltip>
        </ext:LineSeries>
    </Series>
</ext:CartesianChart>
```

**折线图变体**（改 Series 控件即可）：

| Series 控件 | 效果 |
|------------|------|
| `<ext:LineSeries>` | 普通折线 |
| 用 `<StyleSpec>` 加 `StrokeStyle`/`LineWidth` | 自定义线颜色/粗细 |
| `<ext:ScatterSeries>` | 散点（不连线） |

**数据点标记（Markers）**：

```aspx
<ext:LineSeries XField="Month" YField="Data1">
    <Marker>
        <ext:CircleSprite Radius="4" FillStyle="blue" />
    </Marker>
    <StyleSpec>
        <ext:SeriesSprite StrokeStyle="blue" LineWidth="2" />
    </StyleSpec>
</ext:LineSeries>
```

**平滑曲线（Spline）**：使用样条曲线 Series（如 `<ext:LineSeries>` 配合 smooth 配置）。

### 3. 饼图（PieSeries）— PolarChart

```aspx
<ext:PolarChart ID="Chart1" runat="server" Shadow="true" InsetPadding="60" InnerPadding="20">
    <LegendConfig runat="server" Dock="Right" />
    <Store>...</Store>
    <Interactions>
        <ext:ItemHighlightInteraction />
        <ext:RotateInteraction />
    </Interactions>
    <Series>
        <ext:PieSeries AngleField="Data1" ShowInLegend="true" Donut="0" HighlightMargin="20">
            <Label Field="Name" Display="Rotate" FontSize="18" />
            <Tooltip runat="server" TrackMouse="true" Width="140" Height="28">
                <Renderer Handler="toolTip.setTitle(record.get('Name') + ': ' + record.get('Data1'));" />
            </Tooltip>
        </ext:PieSeries>
    </Series>
</ext:PolarChart>
```

**关键属性**：
- `AngleField="Data1"`：决定扇区角度大小的字段
- `Donut="0"`：环形圈宽比例，`0` = 实心饼，`35` = 环形图（甜甜圈）
- `ShowInLegend="true"`：显示图例
- `HighlightMargin="20"`：高亮时扇区外推距离
- `<Label Field="Name">`：扇区上的标签字段，`Display="Rotate"` 旋转显示

**动态切换饼/环**（客户端 JS）：
```javascript
App.Chart1.series[0].setDonum(pressed ? 35 : false);
App.Chart1.redraw();
```

### 4. 雷达图（RadarSeries）— PolarChart

多维度对比（如能力评估、品质多维分析）。

```aspx
<ext:PolarChart ID="Chart1" runat="server" InsetPaddingSpec="40 40 60 40">
    <Store>...</Store>
    <Interactions>
        <ext:RotateInteraction />
    </Interactions>
    <Axes>
        <ext:NumericAxis Position="Radial" Fields="data1" Grid="true" Minimum="0" Maximum="25" MajorTickSteps="4">
            <Renderer Handler="return label + '%';" />
        </ext:NumericAxis>
        <ext:CategoryAxis Position="Angular" Grid="true" />
    </Axes>
    <Series>
        <ext:RadarSeries AngleField="month" RadiusField="data1">
            <StyleSpec><ext:Sprite Opacity="0.80" /></StyleSpec>
            <HighlightConfig>
                <ext:Sprite FillStyle="#000" LineWidth="2" StrokeStyle="#fff" />
            </HighlightConfig>
            <Tooltip runat="server" TrackMouse="true">
                <Renderer Handler="toolTip.setHtml(record.get('month') + ': ' + record.get('data1') + '%');" />
            </Tooltip>
        </ext:RadarSeries>
    </Series>
</ext:PolarChart>
```

> 雷达图用 **两个轴**：`Position="Radial"`（半径方向的数值轴）+ `Position="Angular"`（角度方向的类别轴）。`AngleField` 是类别，`RadiusField` 是数值。

### 5. 仪表盘（GaugeSeries）— PolarChart

KPI 指标盘、OEE 仪表。

```aspx
<ext:PolarChart ID="Chart1" runat="server" StyleSpec="background:#fff;" InsetPadding="25" Flex="1">
    <Store>...</Store>
    <Axes>
        <ext:NumericAxis Position="Gauge" Minimum="0" Maximum="100" MajorTickSteps="10" Margin="-10" />
    </Axes>
    <Series>
        <ext:GaugeSeries AngleField="Data1" Donut="30" Colors="#82B525,#ddd" TotalAngleDegrees="180" />
    </Series>
</ext:PolarChart>
```

**关键属性**：
- `Position="Gauge"`：专用于仪表盘的轴位置
- `Donut="30"`：环宽，`0` 实心，数值越大环越细
- `Colors="#82B525,#ddd"`：`颜色1` 是数值色（前景），`颜色2` 是背景色（灰圈）
- `TotalAngleDegrees="180"`：仪表盘张开角度，`180` = 半圆，`240` 更大

**动画**：仪表盘动画效果明显，可设 `<AnimationConfig Easing="BounceOut" Duration="500" />`。

### 6. 面积图（AreaSeries）

累积趋势。

```aspx
<Series>
    <ext:AreaSeries XField="Name" YField="Data1,Data2" Stacked="true" Titles="A,B" />
</Series>
```

### 7. 散点图 / 气泡图（ScatterSeries）

相关性分析。

```aspx
<Series>
    <ext:ScatterSeries XField="Data1" YField="Data2">
        <Marker>
            <ext:CircleSprite Radius="5" FillStyle="blue" />
        </Marker>
    </ext:ScatterSeries>
</Series>
```

> 注意散点图 X 轴是**数值**（不是类别），两个轴都用 NumericAxis。

### 8. 金融图：K线（CandlestickSeries）/ OHLC

股价、统计分布。需配合 TimeAxis。

```aspx
<ext:CartesianChart runat="server">
    <Axes>
        <ext:NumericAxis Position="Left" Fields="Add OID,High,Low,Close" />
        <ext:TimeAxis Position="Bottom" Fields="Date" DateFormat="ea,0" />
    </Axes>
    <Series>
        <ext:CandlestickSeries
            OpenField="Open" HighField="High" LowField="Low" CloseField="Close"
            DateField="Time" />
        <ext:OhlcSeries ... />  <!-- OHLC 替代写法 -->
    </Series>
</ext:CartesianChart>
```

---

## 六、图例 LegendConfig

```aspx
<ext:PolarChart runat="server">
    <LegendConfig runat="server" Dock="Right" />
    ...
</ext:PolarChart>
```

| `Dock` 值 | 位置 |
|-----------|------|
| `Right` | 右侧（默认） |
| `Bottom` | 底部 |
| `Left` / `Top` | 左/上 |

Series 设 `ShowInLegend="true"` 才会出现在图例。点击图例项可临时隐藏该系列。

---

## 七、交互 Interactions

```aspx
<Interactions>
    <ext:PanZoomInteraction ZoomOnPanGesture="true" />   <!-- 平移缩放 -->
    <ext:ItemHighlightInteraction />                       <!-- 鼠标高亮 -->
    <ext:RotateInteraction />                              <!-- 旋转（饼/雷达） -->
    <ext:CrossZoomInteraction />                           <!-- 框选缩放 -->
</Interactions>
```

| 交互控件 | 作用 |
|---------|------|
| `PanZoomInteraction` | 折线/柱图缩放平移 |
| `ItemHighlightInteraction` | 鼠标悬停高亮单项 |
| `RotateInteraction` | 饼图/雷达图旋转（拖拽） |
| `CrossZoomInteraction` | 框选区域放大 |
| `ItemInfoInteraction` | 点击显示详情 |

---

## 八、Tooltip（悬浮提示）

几乎每个 Series 都该加 Tooltip，让用户看到精确数值。

```aspx
<ext:BarSeries XField="Name" YField="Data1">
    <Tooltip runat="server" TrackMouse="true" Width="120" Height="40">
        <Renderer Handler="toolTip.setHtml(record.get('Name') + ': ' + record.get('Data1'));" />
    </Tooltip>
</ext:BarSeries>
```

**Renderer 参数**：
- `toolTip`：提示框对象，调 `.setHtml(html)` 设内容 或 `.setTitle(title)`
- `record`：当前数据记录，`.get('字段名')` 取值
- `context`：上下文，含 `context.series`、`context.field`（堆叠场景判断当前是哪个字段）

---

## 九、标题与水印（Sprite）

图表没有内置 Title 属性，标题用 `<Items>` 里的 `TextSprite` 实现：

```aspx
<ext:CartesianChart runat="server">
    <Items>
        <ext:TextSprite Text="月度产量统计" FontSize="22" Width="100" Height="30" X="40" Y="20" />
        <ext:TextSprite Text="单位：吨" FontSize="10" X="12" Y="480" />
    </Items>
    ...
</ext:CartesianChart>
```

`X`/`Y` 是相对图表左上角的像素坐标。

---

## 十、下载图表为图片 / 打印预览

Ext.NET 图表内置两个客户端方法：

```javascript
// 下载为图片
chart.download();

// 打印预览
chart.preview();
```

调用方式（按钮 Handler）：

```aspx
<ext:Button runat="server" Text="导出图片" Handler="this.up('panel').down('chart').download();" />
<ext:Button runat="server" Text="打印预览" Handler="this.up('panel').down('chart').preview();" />
```

> `this.up('panel').down('chart')` 会向上找到父 Panel，再向下找到 chart 组件（兼容 CartesianChart/PolarChart，因为它们都是 `chart` xtype）。

---

## 十一、实时数据刷新（Live Chart）

监控看板场景：定时追加新数据点。

**服务端**：用 `Store.LoadData(data, append)` 第二个参数 `true` 表示追加而非替换：

```csharp
protected void GetNewData(object sender, DirectEventArgs e)
{
    DataItem data = GenerateNewPoint();
    // append=true，新数据加到末尾
    this.Chart1.GetStore().LoadData(new DataItem[] { data }, true);
}
```

**前端定时触发**（用 TaskManager 或 setInterval）：

```aspx
<ext:TaskManager runat="server">
    <Tasks>
        <ext:Task Interval="2000" AutoRun="true">
            <DirectEvents>
                <Update OnEvent="GetNewData" />
            </DirectEvents>
        </ext:Task>
    </Tasks>
</ext:TaskManager>
```

**滚动效果**：数据超出范围时，手动调整 TimeAxis 范围：

```csharp
TimeAxis timeAxis = (TimeAxis)Chart1.Axes[1];
if (data.Date > endDate)
{
    timeAxis.SetToDate(data.Date);
    timeAxis.SetFromDate(DateUnit.Day, 1);
}
```

---

## 十二、完整最小可运行示例（柱状图）

可直接复制到任意 `.aspx` 验证：

```aspx
<%@ Page Language="C#" %>

<script runat="server">
    protected void Page_Load(object sender, EventArgs e)
    {
        if (!X.IsAjaxRequest)
        {
            this.Chart1.GetStore().DataSource = new List<object>
            {
                new { Name = "1月", Data1 = 120 },
                new { Name = "2月", Data1 = 190 },
                new { Name = "3月", Data1 = 150 },
                new { Name = "4月", Data1 = 210 },
                new { Name = "5月", Data1 = 180 }
            };
        }
    }
</script>

<!DOCTYPE html>
<html>
<head runat="server">
    <title>柱状图示例</title>
</head>
<body>
    <form runat="server">
        <ext:ResourceManager runat="server" />

        <ext:Panel runat="server" Width="800" Height="500" Layout="FitLayout">
            <Items>
                <ext:CartesianChart ID="Chart1" runat="server" FlipXY="false" InsetPadding="40">
                    <AnimationConfig Duration="500" Easing="EaseOut" />
                    <Axes>
                        <ext:NumericAxis Position="Left" Fields="Data1" Grid="true">
                            <Renderer Handler="return label.toFixed(0);" />
                        </ext:NumericAxis>
                        <ext:CategoryAxis Position="Bottom" Fields="Name" Grid="true" />
                    </Axes>
                    <Series>
                        <ext:BarSeries XField="Name" YField="Data1">
                            <StyleSpec>
                                <ext:SeriesSprite Opacity="0.8" />
                            </StyleSpec>
                            <Tooltip runat="server" TrackMouse="true">
                                <Renderer Handler="toolTip.setHtml(record.get('Name') + ': ' + record.get('Data1') + ' 吨');" />
                            </Tooltip>
                        </ext:BarSeries>
                    </Series>
                </ext:CartesianChart>
            </Items>
        </ext:Panel>
    </form>
</body>
</html>
```

---

## 十三、踩坑要点

### 坑1：CartesianChart 不写 Axes 不显示

柱/线/面积图**必须**声明至少两个轴（一个数值轴 + 一个类别轴），否则数据无法定位，图表空白。PolarChart 的饼图可省略 Axes。

### 坑2：BarSeries 的 FlipXY 在容器上而非 Series 上

`FlipXY` 是 `CartesianChart` 的属性，不是 `BarSeries` 的。写错位置无效。

### 坑3：堆叠图的 YField 逗号分隔，对应字段必须在 Model 中都声明

```aspx
YField="Data1,Data2,Data3"   <!-- Model 里必须有 Data1/Data2/Data3 三个 ModelField -->
Titles="A,B,C"               <!-- Titles 数量要和 YField 一致 -->
```

### 坑4：Tooltip Renderer 里取值用 record.get()

```javascript
// ✅ 正确
toolTip.setHtml(record.get('Name'));

// ❌ 错误（record.Name 是 undefined）
toolTip.setHtml(record.Name);
```

### 坑5：饼图 Tooltip 计算百分比要自己算

饼图扇区大小由 `AngleField` 数值决定，Tooltip 显示百分比需手动算：

```javascript
var tipRenderer = function (toolTip, record, context) {
    var total = 0;
    App.Chart1.getStore().each(function (rec) { total += rec.get('Data1'); });
    toolTip.setTitle(record.get('Name') + ': ' + Math.round(record.get('Data1') / total * 100) + '%');
};
```

### 坑6：图表必须有高度

Chart 没有默认高度，在 FitLayout 的 Panel 里可撑满；单独使用时**必须设 Height 或在弹性布局里设 Flex**，否则高度 0 不显示。

### 坑7：Store 字段名大小写敏感

`ModelField Name="Data1"` 与 Series 的 `YField="Data1"` 必须大小写完全一致。数据源对象的属性名也要一致（匿名对象属性 `Data1` 而非 `data1`）。

### 坑8：TimeAxis 需要 Date 类型字段

时间轴的 ModelField 必须 `Type="Date"`，且数据源提供 `DateTime` 类型，否则时间轴无法正确排列：

```aspx
<ext:ModelField Name="Date" Type="Date" />
```

---

## 十四、图表类型速选决策表

| 需求场景 | 推荐图表 | 容器 | 核心 Series |
|---------|---------|------|------------|
| 数量对比（如各月产量） | 柱状图 | CartesianChart | `BarSeries` + `FlipXY="false"` |
| 排名对比（横向更易读） | 条形图 | CartesianChart | `BarSeries` + `FlipXY="true"` |
| 构成占比（如不良类型分布） | 饼图 | PolarChart | `PieSeries` |
| 构成占比 + 标签多 | 环形图 | PolarChart | `PieSeries Donut="35"` |
| 趋势变化（如产能趋势） | 折线图 | CartesianChart | `LineSeries` |
| 多维评估（如品质雷达） | 雷达图 | PolarChart | `RadarSeries` |
| KPI 指标（如 OEE 达成率） | 仪表盘 | PolarChart | `GaugeSeries` |
| 累积总量（如库存累积） | 面积图 | CartesianChart | `AreaSeries` |
| 相关性分析 | 散点图 | CartesianChart | `ScatterSeries` |
| 多系列叠加对比 | 堆叠柱 | CartesianChart | `BarSeries Stacked="true"` |
| 实时监控 | 实时折线 | CartesianChart | `LineSeries` + TaskManager |

---

## 十五、关联文档

| 文档 | 关系 |
|------|------|
| `extnet-grid-complete-guide.md` | GridPanel 表格（图表常与表格搭配做报表） |
| `extnet-store-databinding-guide.md` | Store/Model 数据绑定原理（图表数据基础） |
| `extnet-page-skeleton.md` | BorderLayout 页面骨架（图表常嵌在 Center 区） |
| `tab-trend-chart-template.md` | 趋势图报表模板（Chart 实际应用场景） |
| `chart-table-report-template.md` | 图表+表格组合报表模板 |
| `extnet-toolbar-menu-guide.md` | 工具栏（图表刷新/导出按钮载体） |

## 十六、参考来源

- 官方示例库：`Examples/Chart/`（57 个示例）
  - 柱/条：`Bar/`、`Column/`（Basic/Stacked/Stacked_100/3D/Renderer/Mixed）
  - 折线：`Line/`（Basic/Markers/Spline/Multiple_Axes/CrossZoom）
  - 饼：`Pie/`（Basic/3D/Renderer）
  - 雷达：`Radar/`（Basic/Fill/MultiAxis）
  - 仪表盘：`Gauge/`（Basic_1/Basic_2）
  - 面积：`Area/`、散点：`Scatter/`、金融：`Financial/`
  - 实时：`Live/`（Animated/Updates）
  - 杂项：`Misc/`（Theme/ToolTips/Download/Reload）
  - 组合：`Combination/`（Dashboard/Pareto/Infographic）
