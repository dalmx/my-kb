---
category: 技术-.NET
date: 2026-06-30
factory: 通用
module: Ext.NET
platform: Ext.NET v4.7.1 + ECharts + ASP.NET WebSite (.NET 4.8)
related:
- tab-trend-chart-template.md
- chart-table-report-template.md
- plan-cpk-analysis-page-analysis.md
source: Wongoing.Semi.WebSite Plugins/Semi/Storage/SemiReturnRubberInOutStat.aspx
  返回胶出入库统计趋势图开发
status: active
tags: [Ext.NET, ECharts, TabPanel, 踩坑, markLine, scale, Resize监听, 折叠重绘, y轴余量, 负值]
title: Ext.NET TabPanel + ECharts 趋势图不显示踩坑集（隐藏Tab/尺寸0/重复init/编译错误/控制限出轴）
updated: 2026-08-31
---

# Ext.NET TabPanel + ECharts 趋势图不显示踩坑集（隐藏Tab/尺寸0/重复init/编译错误/控制限出轴）

> 在已有"汇总表格+明细"报表里用 TabPanel 新增"趋势图"Tab（ECharts 折线图），图表死活不显示。记录排查过程与根因，多个独立问题逐一击破。2026-08-26 增补坑6/坑7 并**修正坑3的原结论**；2026-08-31 **修正坑6的余量写法**（乘法余量在负值下限值时方向相反，换按跨度加余量，来自 Molding BeltDrumSpliceCpk 负值 LCL 实证）。

参照正面范例：`Plugins/Semi/Technology/SemiCPKReport.aspx`（5个Tab图表，稳定运行）。

## 一、坑1（致命）：echarts 在隐藏 Tab 里画图，切过去内容不刷新

**现象**：默认激活 Tab1（汇总表），趋势图在 Tab2。查询后日志显示 `setOption` 执行成功、数据有值（`times:2 in:2`），但切到趋势图 Tab 仍是空白。

**根因**：echarts 在 `display:none`/隐藏的容器里 init+setOption 后，canvas 是画了，但容器从隐藏变可见时，**echarts 不会自动重绘/刷新**，内容停留在隐藏状态的渲染结果（不可见）。

**错误写法**（Tab 切换时只 resize，不重绘）：
```js
var tabSummaryChange = function (tabPanel, newCard) {
    if (newCard.id == 'pnlTrend') { pnlTrendResize(); }  // ❌ 只 resize 没用
}
```

**正确写法**（每次画图 dispose 旧实例彻底重绘 + Tab 切换延迟 resize）：
```js
var DrawTrend = function () {
    divTrendResize();
    var el = document.getElementById('divTrend');
    if (!el) { return; }
    if (chartTrend) { chartTrend.dispose(); }   // ✅ 销毁旧实例,彻底重绘
    chartTrend = echarts.init(el, 'light');
    chartTrend.setOption(buildOption());
    divTrendResize();
    chartTrend.resize();
}

// Tab 切换:延迟执行确保 pnlTrend 布局完成、宽高就绪
var tabSummaryChange = function (tabPanel, newCard) {
    if (newCard.id == 'pnlTrend') {
        Ext.defer(function () {
            if (chartTrend) { divTrendResize(); chartTrend.resize(); }
            else { DrawTrend(); }
        }, 50);
    }
}
```

> 关键：**`dispose()` + 重新 `init()`** 比 `if(!chartTrend)` 懒初始化更可靠。懒初始化在隐藏 Tab 场景会缓存一个"坏"的实例状态。

## 二、坑2：echarts.init 时 div 尺寸为 0，canvas 是 0×0

**现象**：echarts 实例创建成功，但图不显示（canvas 宽高为 0）。

**根因**：echarts.init 读取 div 当前尺寸生成 canvas。若 div 是 0×0，canvas 也是 0×0，什么也画不出来。

**错误写法**（div 用百分比，在 Ext Fit 布局下无效）：
```html
<div id="divTrend" style="width: 100%; height: 100%; min-height: 300px;"></div>
```
> ⚠️ Ext.NET 的 Fit/AutoScroll 布局**只管理 Ext 子组件**，不管原生 HTML div。`height:100%` 的参照是父容器内容区，而原生 div 的父是 Ext Panel 的 body，百分比参照链断裂，结果为 0。

**正确写法**（div 给固定初始尺寸，resize 时再 JS 设尺寸）：
```html
<div id="divTrend" style="width: 850px; height: 260px;" />
```
```js
// resize 时用 pnlTrend 自身宽高(切到该Tab时它可见,有真实尺寸)重设div
var divTrendResize = function () {
    var width = App.pnlTrend.getWidth() - 10;
    var height = App.pnlTrend.getHeight() - 10;
    if (width > 0 && height > 0) { $('#divTrend').width(width); $('#divTrend').height(height); }
}
```

## 三、坑3：Resize 监听写法（2026-08-26 修正原结论）

**原结论曾记载 `this.on('resize', fn)` 是正确写法——是误判，实证（Molding BeltDrumSpliceCpk）它是错的**：

```xml
<!-- ❌ 错误：Handler 在每次 Resize 事件里执行 this.on(...)，即每次都再注册一个新监听 -->
<!--    → 监听器无限叠加（泄漏），且注册的函数当次事件不执行（要等下一次） -->
<Listeners><Resize Handler="this.on('resize', divTrendResize);"></Resize></Listeners>
```

正解是**直接调用**（`Fn` 绑定或 `Handler="fn();"` 等价，都在每次 Resize 事件触发时执行）：

```xml
<Listeners><Resize Handler="divTrendResize();"></Resize></Listeners>
```

并且 fn 里改完 div 宽高后**必须调 `echarts.getInstanceByDom(el).resize()`**——只设 div 宽高不动 echarts 实例，图不会重排（CPK 页"折叠后图表没重绘"的根因之一）：

```js
var fitChartDiv = function (id) {
    var el = $('#' + id);
    if (el.length === 0) return;
    el.width(App.pnlTrend.getWidth() - 10).height(App.pnlTrend.getHeight() - 10);
    var chart = echarts.getInstanceByDom(el[0]);
    if (chart) chart.resize();
};
```

## 四、坑4（致命）：不要假设未验证的 C# 工具类，导致 CS0234 编译错误

**现象**：`CS0234: 命名空间"Wongoing.Utility"中不存在类型或命名空间名"Json"`

**根因**：为让 DirectMethod 返回 JSON 给前端画图，凭记忆假设了 `Wongoing.Utility.Json.JsonHelper.DataTableToJson(data)` 这个工具类存在，实际项目里根本没有这个命名空间/类。

**教训**：
1. **引用任何工具类/方法前，必须先在项目里 grep 验证它真实存在**（项目 .cs 文件可能是加密的，grep 读不出文本——这种情况下更不能假设，应改用不依赖未知类的方案）。
2. **Store 绑定方式更稳妥**：本项目 DirectMethod + Ext.NET Store 绑定（`Store.DataSource = data; Store.DataBind();`）是已验证可用的，前端从 `App.Store.data.items` 取数即可，不必走 JSON 序列化。
   ```csharp
   [DirectMethod(Timeout = 300000)]
   public void GetTrendData(string materialCode)   // void, 不返回 JSON
   {
       var param = BuildDateParam();
       if (!string.IsNullOrEmpty(materialCode)) param["MATERIAL_CODE"] = materialCode;
       DataTable data = productionManager.GetDataTableByStatement("...@HppSemisProduction", param);
       StoreTrend.DataSource = data;
       StoreTrend.DataBind();
   }
   ```

> 排查口诀：**遇到 CS0234/CS0103（类型或命名空间不存在），先怀疑是不是凭记忆写了个不存在的类**，去项目里验证；无法验证就用最朴素的 Store 绑定方案。

## 五、坑5：ext:Store 的放置位置

`<ext:Store>` 是数据组件不是可视化组件，**必须放在 form 顶层**（`<ext:ResourceManager>` 之后、`<ext:Viewport>` 之前），**不能放进 VBoxLayout/TabPanel 的 Items**（否则渲染异常）。

## 六、坑6：`scale:true` 自适应只算系列数据，markLine 控制限被挤出坐标轴（2026-08-26 增补；2026-08-31 修正余量写法）

**现象**：均值控制图"没有显示均值上下限"——统计表里 均值控制上限 8.000 / 下限 6.000 都有值，图上却看不到线。

**根因**：y 轴 `scale: true` 的自适应只计算**系列数据**（组均值 7.6~7.78），**不含 markLine 的 UCL/LCL**（8/6）——限值线落在轴范围外。用户维护的自定义控制限与数据集中范围差距大时必现。

**正解**：y 轴 max/min 显式计算并**把 UCL/LCL 并入**（InitAgv 已算好 data.max/min 含限值），再留余量。

⚠️ **2026-08-31 反例修正——余量不能用乘法**。本文原正解写的 `min * 0.98` 在 **min 为负值时方向相反**：用户维护 均值UCL=0.5 / 均值LCL=-0.5 时，`Math.floor(-0.5*0.98*100)/100 = -0.49`，轴下界反而抬到 LCL 线(-0.5)之上，负值 LCL 的 markLine 照样出轴不显示（正值数据下这个 bug 被掩盖了整整五天）。**余量必须按跨度加**：

```js
// 坐标轴边界=极值 + 按跨度加余量（零跨度时按绝对值兜底，全零给 1）
function axisBound(maxVal, minVal, padRatio) {
    var span = maxVal - minVal;
    var pad = span > 0 ? span * padRatio : (Math.abs(maxVal) > 0 ? Math.abs(maxVal) * padRatio : 1);
    return { max: maxVal + pad, min: minVal - pad };
}
// 用法：InitAgv 等已把 UCL/LCL 并入 data.max/min
var bound = axisBound(data.max, data.min, 0.02);
yAxis: { type: 'value', max: bound.max, min: bound.min, splitNumber: 10 }
```

两个衍生要点（同日实证）：
- **能力图（直方图+正态曲线）的坑在 x 轴**：五条竖标线（LSL/LCL/均值/UCL/USL）是 markLine，x 轴 `scale:true` 只贴合直方图/正态曲线范围——x 轴 min/max 同样要把五个标线值并进来（`Math.max(data.max, usl, ucl, average)` / `Math.min(data.min, lsl, lcl, average)`）再 axisBound。
- 运行图不受此坑影响——它的 UCL/LCL 是**系列**（uclData/lclData 数组），axis 自适应天然包含系列极值。

## 七、坑7：折叠/展开（West 侧栏、限值 FieldSet、查询区）后的图表重绘要分批 defer（2026-08-26 增补）

折叠/展开带动画，动画期间容器尺寸是**中间态**——单次 100ms defer 拿到的不是最终尺寸，图会按错误尺寸定格。分批覆盖：

```js
var onToggle = function () {
    Ext.defer(resizeAllCharts, 120);
    Ext.defer(resizeAllCharts, 400);
    Ext.defer(resizeAllCharts, 700);
};
```

挂在 West 面板与 FieldSet 的 `<Collapse>/<Expand>` 上。配合坑3 的 fitChartDiv（div 尺寸 + chart.resize 一步到位）双保险。

## 八、排查方法论：用 console.log 逐行定位中断点

echarts 不显示时，别瞎猜，在 DrawTrend 关键环节加日志定位中断点：
```js
console.log('[Trend] DrawTrend called');        // 没输出 → 函数没被调用
console.log('div:', el, 'size:', el.offsetWidth + 'x' + el.offsetHeight);  // 0x0 → 坑2
console.log('chart:', c);                       // null → init 失败
console.log('items:', App.StoreTrend.data.items.length);  // 0 → 后端没数据
```
日志在哪一行中断，问题就在中断点的下一行代码。**修复后记得清理日志**。

## 九、最终可用模式总结

| 要点 | 做法 |
|---|---|
| div 初始尺寸 | 固定 px（如 850×260），不用 100% |
| Resize 监听 | `<Resize Handler="divXxxResize();" />` 直接调用；fn 内设 div 尺寸后调 `chart.resize()`（❌ 不用 `this.on('resize', fn)` 叠加写法） |
| 画图 | `dispose()` 旧实例 → `echarts.init` → `setOption` → resize |
| Tab 切换 | `Ext.defer(..., 50)` 延迟 resize，确保布局完成 |
| 控制限可见 | 轴 max/min 把 UCL/LCL（能力图 x 轴含五条标线值）并入，**余量按跨度加**（❌ 乘法余量负值反向；❌ 不能只靠 scale:true） |
| 折叠/展开重绘 | 分批 defer（120/400/700ms）覆盖动画期 |
| 后端取数 | Store 绑定（void DirectMethod），不用未验证的 JSON 工具类 |
| Store 位置 | form 顶层，不放布局 Items |
| 单击行 | 刷明细+刷趋势数据（不切Tab） |
| 双击行 | 刷趋势数据 + `setActiveTab` 切到趋势Tab + DrawTrend |

## 十、关联

- TabPanel.setActiveTab 客户端切换标签页：见 `extnet-tabpanel-setactivetab.md`
- TabPanel + 趋势图报表模板：见 `tab-trend-chart-template.md`
- 定时器（setInterval/setTimeout/defer）：见 `js-setinterval-settimeout.md`
- CPK 页实证（坑3/6/7 来源）：Molding `Plugins/Molding/Report/BeltDrumSpliceCpk.aspx`；Semi 侧 CPK 页面结构见 [[plan-cpk-analysis-page-analysis]]

## 十一、坑8：echarts v4 markLine label 无 offset，上下偏移用换行实现（2026-08-26 增补）

**现象**：控制图横线右侧的标值要求"上限偏上/中间居中/下限偏下"，写了 `label: { position: 'end', offset: [0, -10] }` 偏移无效（值仍压在线上）。

**根因**：项目 echarts 为 4.1——`label.offset` 是 **v5+** 属性（v4 静默忽略）；且 v4.1 构建的 markLine 标签 position 枚举只有 start/middle/end，没有 insideEndTop/insideEndBottom。检索验证方式：`grep -c "insideEndTop" echarts.min.js` 为 0。

**v4 解法**：label 文本块垂直居中于线端，用空行挪位——

```js
{ name: 'UCL', yAxis: ucl, label: { formatter: 'UCL=' + ucl.toFixed(3) + '\n', position: 'end' } },  // 尾空行→值抬到线上方
{ name: 'CL',  yAxis: cl,  label: { formatter: 'CL=' + cl.toFixed(3),          position: 'end' } },  // 居中
{ name: 'LCL', yAxis: lcl, label: { formatter: '\nLCL=' + lcl.toFixed(3),      position: 'end' } }   // 前置空行→值压到线下方
```

一个空行约挪 12px（字号行高），"略微偏移"场景正好；需要更大偏移加多个 `\n`。v5 项目直接用 `offset: [0, ∓10]` 即可。