---
title: TabPanel.setActiveTab — 客户端主动切换/指定展示标签页
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, TabPanel, setActiveTab, 客户端API, 属性速查]
status: active
updated: 2026-08-29
---
# TabPanel.setActiveTab — 客户端主动切换/指定展示标签页

> setActiveTab() 是 TabPanel 的客户端方法，在 JS 里主动激活某标签页（默认停非首 Tab、行/按钮联动切 Tab、切过去触发 ECharts resize 重绘）。参数传索引（从 0 起）或子项 ID 字符串（更稳，不随 Tab 顺序调整错位）；会触发 TabChange 事件，内嵌需可见才渲染的组件时配合 defer + resize 防空白。

## 一、作用

`setActiveTab()` 是 `ext:TabPanel` 的客户端方法，用于 **在 JS 中主动激活（切到）某个标签页**，而无需用户点击 Tab 头。

典型用途：
- 页面加载后默认停在某个非首个 Tab。
- 业务联动：选中某行 / 某按钮点击后，自动切到对应明细 Tab。
- Tab 内嵌 ECharts 等需延迟渲染的组件时，切过去再触发 resize / 重绘。

## 二、用法

通过 `App.<TabPanel的ID>.setActiveTab(...)` 调用，参数可以是 **索引（从 0 开始）** 或 **子项 ID**。

```javascript
// 按索引激活：1 = 第二个标签页
App.pnlLineDetail1.setActiveTab(1);

// 按 子项 ID 激活（更稳健，不依赖顺序）
App.pnlLineDetail1.setActiveTab('pnlTrend');
```

对应 aspx：

```xml
<ext:TabPanel ID="pnlLineDetail1" runat="server" Flex="1" Border="false" Layout="Fit">
    <Items>
        <ext:GridPanel ID="tabGrid"    runat="server" Title="明细表格" />
        <ext:Panel      ID="pnlTrend"  runat="server" Title="趋势图" />
    </Items>
</ext:TabPanel>
```

上面 `setActiveTab(1)` 即把「趋势图」Tab 切到前台。

## 三、注意

- **索引从 0 开始**：`setActiveTab(0)` 是第一个 Tab，`setActiveTab(1)` 是第二个。
- 用 **ID 字符串** 比用索引更稳：Tab 顺序调整后不会错位。
- `setActiveTab` 会触发 TabPanel 的 `TabChange` 事件；若该 Tab 内有 ECharts 等需在可见时才渲染的组件，配合 `TabChange` 监听里做 `defer` + `resize`，避免空白。
- 隐藏 Tab 切换时，若组件已初始化但宽高为 0，需在切换后 `Ext.defer(fn, 50)` 再 resize。

## 四、关联

- Tab 切换 + ECharts 不显示的坑：见 `extnet-tabpanel-echarts-not-display.md`
- TabChange 联动显示筛选框 / 刷新明细：见 `extnet-row-highlight-expiry.md`
- TabPanel + 趋势图模板：见 `tab-trend-chart-template.md`
