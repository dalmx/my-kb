---
title: TabPanel 表格+趋势图联动模板（ECharts 单Y轴多折线 + 点击行联动）
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, ECharts, TabPanel, 趋势图, 联动]
status: active
source: Wongoing.Semi.WebSite Plugins/Semi/Storage/SemiReturnRubberInOutStat.aspx 返回胶出入库统计
platform: Ext.NET v4.7.1 + ASP.NET WebSite (.NET 4.8) + ECharts
date: 2026-06-30
related: [chart-table-report-template.md, summary-detail-report-template.md]
updated: 2026-08-29
---
# TabPanel 表格+趋势图联动模板（ECharts 单Y轴多折线 + 点击行联动）

> 在已有"汇总表格 + 明细"报表的汇总区，用 `TabPanel` 把原汇总 GridPanel 包起来，新增一个"趋势图"Tab，用 ECharts 多折线展示随时间变化的趋势；点选汇总行后趋势图联动切换为该行（物料/分组）的曲线，不点选时默认展示合计总数。

与 [chart-table-report-template.md](chart-table-report-template.md)（图表+表格上下分割）的区别：本模板是 **Tab 切换**，且强调 **点击表格行联动图表** 与 **单 Y 轴多指标对比**。

## 一、布局结构

```text
┌─────────────────────────────────────────────┐
│ Toolbar: [查询] [导出...]                    │  ← North TopBar
├─────────────────────────────────────────────┤
│ FormPanel (日期/物料查询条件)                │  ← North Body
├─────────────────────────────────────────────┤
│ TabPanel ID="tabSummary"  (Flex="1")         │  ← Center 上半 VBoxLayout
│  ├─ Tab1 "出入库汇总" : GridPanel pnlSummary │     原汇总表格，内容不变
│  └─ Tab2 "出入库趋势图" : Panel pnlTrend      │
│        └─ <div id="divTrend">  (ECharts)     │
├──────────── BoxSplitter ─────────────────────┤
│ pnlDetail (明细, Flex="1")                   │  ← Center 下半，不变
└─────────────────────────────────────────────┘
```

## 二、关键实现

### 2.1 head 引入 ECharts
```aspx
<script src="../../../resources/js/echarts.min.js"></script>
```
库路径确认：`Wongoing.Semi.WebSite/resources/js/echarts.min.js`（项目已自带，无需新增依赖）。

### 2.2 趋势数据 Store（放 form 顶层，非布局 Item）
> ⚠️ `<ext:Store>` 是数据组件不是可视化组件，必须放在 `<ext:ResourceManager>` 之后、`<ext:Viewport>` 之前的 form 顶层，**不能放进 VBoxLayout/TabPanel 的 Items**（否则渲染异常）。
```aspx
<ext:Store ID="StoreTrend" runat="server">
    <Model><ext:Model ID="modelTrend" runat="server"><Fields>
        <ext:ModelField Name="TREND_TIME" />
        <ext:ModelField Name="INWEIGHT" />
        <ext:ModelField Name="OUTWEIGHT" />
        <ext:ModelField Name="STOCKWEIGHT" />
    </Fields></ext:Model></Model>
</ext:Store>
```

### 2.3 TabPanel 包裹原 GridPanel + 趋势 Tab
```aspx
<ext:TabPanel ID="tabSummary" runat="server" Flex="1" Border="false" Layout="Fit">
    <Listeners><TabChange Fn="tabSummaryChange" /></Listeners>
    <Items>
        <%-- Tab1：原汇总表格（内容不变，只是搬进 TabPanel） --%>
        <ext:GridPanel ID="pnlSummary" runat="server" Title="出入库汇总" Header="true" Flex="1">
            ...
            <SelectionModel>
                <ext:RowSelectionModel Mode="Single">
                    <Listeners><Select Fn="SummarySelect" /></Listeners>
                </ext:RowSelectionModel>
            </SelectionModel>
        </ext:GridPanel>

        <%-- Tab2：趋势图 --%>
        <ext:Panel ID="pnlTrend" runat="server" Title="出入库趋势图" Header="false" Layout="Fit" Border="false">
            <Content>
                <div id="divTrend" style="width: 100%; height: 100%; min-height: 300px;"></div>
            </Content>
            <Listeners><Resize Fn="pnlTrendResize" /></Listeners>
        </ext:Panel>
    </Items>
</ext:TabPanel>
```

### 2.4 ECharts 脚本（单 Y 轴多折线 + dataZoom）
```js
var chartTrend;
var optionTrend = {
    title: { text: '返回胶出入库趋势（每小时）' },
    tooltip: { trigger: 'axis' },
    legend: { data: ['入库重量', '出库重量', '库存结存'] },
    toolbox: { feature: { dataZoom: { yAxisIndex: 'none' }, restore: {}, saveAsImage: {} } },
    dataZoom: [{ type: 'slider' }, { type: 'inside' }],
    grid: { left: 60, right: 30, top: 70, bottom: 70 },
    xAxis: { type: 'category', data: [] },
    yAxis: { type: 'value', name: '重量(kg)' },     // 单Y轴：多指标同量纲时
    series: [
        { name: '入库重量', type: 'line', smooth: true, itemStyle: { color: '#017F7E' }, data: [] },
        { name: '出库重量', type: 'line', smooth: true, itemStyle: { color: '#d9534f' }, data: [] },
        { name: '库存结存', type: 'line', smooth: true, itemStyle: { color: '#f4c414' }, data: [] }
    ]
};

// 懒初始化（div 在 pnlTrend 渲染后才有，不能页面加载时直接 init）
var initChartTrend = function () {
    var el = document.getElementById('divTrend');
    if (!el) { return null; }
    if (!chartTrend) { chartTrend = echarts.init(el, 'light'); }
    return chartTrend;
};

// 从隐藏 Store 取数 → 填 option → setOption(true 清空重绘) → resize
var DrawTrend = function () {
    var c = initChartTrend();
    if (!c) { return; }
    var items = App.StoreTrend.data.items;
    var times = [], inArr = [], outArr = [], stockArr = [];
    for (var i = 0; i < items.length; i++) {
        var d = items[i].data;
        times.push(d.TREND_TIME);
        inArr.push(d.INWEIGHT); outArr.push(d.OUTWEIGHT); stockArr.push(d.STOCKWEIGHT);
    }
    optionTrend.xAxis.data = times;
    optionTrend.series[0].data = inArr;
    optionTrend.series[1].data = outArr;
    optionTrend.series[2].data = stockArr;
    c.setOption(optionTrend, true);
    pnlTrendResize();
};

// 自适应：隐藏 Tab 时跳过（尺寸为0），可见时重算 div 宽高并 resize
var pnlTrendResize = function () {
    if (!chartTrend) { return; }
    if (!App.pnlTrend || !App.pnlTrend.isVisible()) { return; }
    var w = App.pnlTrend.getWidth() - 10, h = App.pnlTrend.getHeight() - 10;
    if (w > 0 && h > 0) { $('#divTrend').width(w); $('#divTrend').height(h); chartTrend.resize(); }
};

// 切到趋势 Tab 时 init + resize（解决隐藏 div 尺寸为0导致图不显示）
var tabSummaryChange = function (tabPanel, newCard) {
    if (newCard.id == 'pnlTrend') { initChartTrend(); pnlTrendResize(); }
};
```

### 2.5 联动：默认合计 / 点行切单物料
```js
// 查询成功 → 刷合计趋势（materialCode 传空）
App.direct.GetStatisticsData({
    success: function () {
        App.direct.GetTrendData('', { success: function () { DrawTrend(); } });
    }, eventMask: { ... }
});

// 点汇总行 → 刷明细 + 刷该物料趋势
var SummarySelect = function (item, record, index) {
    var materialcode = record.data.MATERIAL_CODE;
    App.direct.GetDetails(materialcode, { ... });
    App.direct.GetTrendData(materialcode, { success: function () { DrawTrend(); } });
};
```

## 三、后端 DirectMethod（C# 约束：禁用 ?. ?? $""）
```csharp
[DirectMethod(Timeout = 300000)]
public void GetTrendData(string materialCode)   // 空=全部合计，非空=选中物料
{
    try
    {
        var param = BuildDateParam();
        if (!string.IsNullOrEmpty(materialCode))
            param["MATERIAL_CODE"] = materialCode;
        DataTable data = productionManager.GetDataTableByStatement(
            "SelectReturnRubberInOutTrend@HppSemisProduction", param);
        StoreTrend.DataSource = data;
        StoreTrend.DataBind();
    }
    catch (Exception ex)
    {
        X.Msg.Show(new MessageBoxConfig { Title = "错误", Message = ex.Message, Icon = MessageBox.Icon.ERROR, Buttons = MessageBox.Button.OK });
    }
}
```
- 趋势图复用现有"查询"权限（ActionId），**不新增按钮/PageAction**。

## 四、按小时归集的 SQL 口径（流量 vs 结存对齐）

业务场景：库存是**整点结存快照**，入库/出库是**流量记录**，需要按小时对齐。

**核心规则**：`[H:00,(H+1):00)` 时段内的流量归到**下一整点 (H+1):00**，与 (H+1):00 的结存快照天然对齐。
> 例：11:30 的入库量归到 12:00 点 → 12:00 点同时有"12点结存快照 + 11~12点进出量"，三者对齐。

**归集到下一整点的 SQL**：
```sql
DATEADD(hour, DATEDIFF(hour, 0, 记录时间) + 1, 0)  -- 11:30→12:00, 11:59→12:00, 12:00→13:00
```

**对齐方式**：以库存整点为主表（LEFT JOIN 入/出库），保证库存线连续；缺失流量补 0。
```sql
;WITH instock AS (
    SELECT DATEADD(hour, DATEDIFF(hour,0,RECORD_TIME)+1,0) AS TREND_TIME,
           SUM(ISNULL(REAL_WEIGHT,0)) AS INWEIGHT
    FROM HPP_RETURN_RUBBER WHERE 1=1 <日期/物料条件>
    GROUP BY DATEADD(hour, DATEDIFF(hour,0,RECORD_TIME)+1,0)
),
outstock AS ( ... 同上，对 MENS..PPM_MJRubStockIn.InTime ... ),
inventory AS (
    SELECT INVENTORY_TIME AS TREND_TIME, SUM(ISNULL(NUM,0)) AS STOCKWEIGHT
    FROM HPP_RETURN_RUBBER_INVENTORY_TREND WHERE 1=1 <日期/物料条件>
    GROUP BY INVENTORY_TIME
)
SELECT CONVERT(varchar(16), v.TREND_TIME, 120) AS TREND_TIME,  -- 输出 yyyy-MM-dd HH:mm 给 X 轴
       ISNULL(i.INWEIGHT,0) AS INWEIGHT, ISNULL(o.OUTWEIGHT,0) AS OUTWEIGHT, v.STOCKWEIGHT
FROM inventory v                                       -- 库存整点为基准轴主表
LEFT JOIN instock  i ON v.TREND_TIME = i.TREND_TIME
LEFT JOIN outstock o ON v.TREND_TIME = o.TREND_TIME
ORDER BY v.TREND_TIME
```

## 五、踩坑/经验

| 问题 | 解法 |
|---|---|
| 趋势 Tab 隐藏时 div 尺寸为 0，切过去图不显示 | `TabChange` 监听：切到 pnlTrend 时 `initChartTrend()` + `pnlTrendResize()` |
| 页面加载时直接 `echarts.init(div)` 报错 | div 在 Panel 渲染后才存在 → **懒初始化**（initChartTrend 内判断 `if(!chartTrend)`） |
| `<ext:Store>` 放进布局 Items 渲染异常 | Store 必须放 form 顶层（ResourceManager 之后、Viewport 之前） |
| 多指标量纲不同（如数量 vs 重量） | 改双 Y 轴：`yAxis:[{...},{...}]`，对应 series 加 `yAxisIndex:1`。本例 NUM 即重量 kg，故用单轴 |
| 库存快照非整点或频率不一致 | 对快照时间也"归到整点"再对齐；或改用"三源时间并集"补齐 |
| 大日期范围按小时点数过多 | 依赖 `dataZoom`(slider+inside) 缩放；DirectMethod `Timeout=300000` 防超时 |
| 量纲/数值列方向 | 流量(入/出库)=该时段 SUM；结存(库存)=时点值取快照，不要 SUM 累加 |

## 六、文件清单（参考）
- 视图：`Plugins/Semi/Storage/SemiReturnRubberInOutStat.aspx`
- 代码：`Plugins/Semi/Storage/SemiReturnRubberInOutStat.aspx.cs`
- SQL：`Wongoing.Semi.Mapper/BusinessMapper/HppSemisProduction.xml`（`SelectReturnRubberInOutTrend@HppSemisProduction`）
