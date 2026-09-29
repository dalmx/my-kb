---
title: Ext.NET Desktop 桌面框架与看板开发（架构 + 避坑 + TableLayout 看板）
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, Desktop, 桌面框架, 避坑, TableLayout, 看板, 行列合并, 斜线表头, 汉化, MessageBus, TaskManager, MouseDistanceSensor, 复刻手册]
status: active
platform: Ext.NET v4.7.1 + ASP.NET WebSite (.NET 4.8)
updated: 2026-08-29
---
# Ext.NET Desktop 桌面框架与看板开发（架构 + 避坑 + TableLayout 看板）

> 合并说明： 本文由三篇同题文档（架构分析 / 接入避坑 / 看板开发）合并而成，涵盖：桌面框架架构、模块加载、接入 WebSite 的 5 个坑、TableLayout 看板开发（行列合并/斜线表头/汉化）。

---

## 一、Desktop 桌面框架架构分析

## 二、目录结构

```text
Overview/
├── Default.aspx              登录页（Window 弹窗，跳转 Desktop.aspx）
├── Desktop.aspx              桌面主页面（承载 ext:Desktop）
├── modules/                  动态加载的用户控件（.ascx）
│   ├── AccordionWindow.ascx    手风琴 + TreePanel（在线用户树）
│   ├── GridWindow.ascx         GridPanel + ArrayReader（公司股价表）
│   ├── SystemStatus.ascx       Cartesian/Polar Chart + TaskManager 实时刷新
│   ├── TabWindow.ascx          TabPanel 多标签页
│   └── WhatsNew.ascx           静态公告窗口
└── resources/
    ├── desktop.css             各快捷方式图标 IconCls 定义
    ├── logo.png / powered.png  桌面水印
    ├── cmd.png / *48x48.png    快捷方式/工具栏图标
    └── wallpapers/Blue.jpg     桌面壁纸
```

## 三、Desktop 控件结构

`<ext:Desktop>` 由以下子节点构成：

| 节点 | 作用 |
|---|---|
| `<Modules>` | **静态注册**的桌面模块集合 |
| `<DesktopConfig>` | 壁纸、快捷方式默认图标、桌面右键菜单、桌面 Content |
| `<StartMenu>` | 开始菜单：标题、图标、`<ToolConfig>`（Settings/Logout） |
| `<TaskBar>` | 任务栏：`<QuickStart>`（平铺/层叠）、`<Tray>`（语言切换） |
| `<Listeners><Ready BroadcastOnBus="App.Desktop.ready"/>` | 桌面就绪后向 MessageBus 发布事件 |

### 窗口管理
- **平铺/层叠**：`Ext.net.Desktop.desktop.tileWindows()` / `cascadeWindows()`
- **动态创建窗口**：`Desktop.GetInstance().CreateWindow(new Window{...})`
- **关闭行为**：`CloseAction="Destroy"` 销毁而非隐藏，避免实例堆积

## 四、模块加载机制（核心）

Ext.NET Desktop 有三种模块注册方式：

### 3.1 静态模块（`<Modules>`）
直接在 `<ext:Desktop><Modules>` 中声明 `<ext:DesktopModule>`。带窗口的模块可 `AutoRun="true"` 自动打开。

### 3.2 用户控件模块（.ascx）
每个 `.ascx` 用 `<ext:DesktopModuleProxy><Module ModuleID="...">` 包装。两种挂载方式：
1. **声明式静态挂载**：`<mod:AccordionWindow runat="server" />`
2. **运行时动态挂载**：`LoadControl("modules/Xxx.ascx")` → `FindControl<DesktopModuleProxy>` → `RegisterModule()`

### 3.3 代码构造模块
```csharp
Desktop.GetInstance().RemoveModule("add-module");  // 先移除同名避免重复
DesktopModuleProxy control = ControlUtils.FindControl<DesktopModuleProxy>(
    this.LoadControl("modules/TabWindow.ascx"));
control.RegisterModule();  // 注册到桌面，无需页面刷新
```

## 五、实时刷新机制（SystemStatus）

```xml
<ext:TaskManager><Tasks>
  <ext:Task TaskID="updateCharts" Interval="2000" WaitPreviousRequest="true" AutoRun="false">
    <DirectEvents><Update OnEvent="UpdateTask"/></DirectEvents>
  </ext:Task>
</Tasks></ext:TaskManager>
```

- 窗口 `AfterRender` 时 `TaskManager1.startTask('updateCharts')`
- 每 2 秒触发服务端，`WaitPreviousRequest="true"` 避免请求堆积
- Pass 计数器节流：`pass % 3 == 0` 才刷新 Memory，`pass % 2 == 0` 才刷新 Process
- `LastCore1/LastCore2/Pass` 存 `Session`，保证刷新间数值连续
- Store 放 `<Bin>` 避免参与页面控件树

## 六、MessageBus 事件总线

- `Desktop.Listeners.Ready BroadcastOnBus="App.Desktop.ready"` → 桌面就绪广播
- `ResourceManager.WindowResize` → `Ext.net.Bus.publish('App.Desktop.ready')` → 窗口 resize 广播
- 订阅方用 `<MessageBusListeners>` 响应（如悬浮工具栏重新定位）

## 七、侧滑面板（MouseDistanceSensor）

```xml
<ext:Panel Floating="true" Hidden="true">
  <Plugins>
    <ext:MouseDistanceSensor Threshold="25" Opacity="false">
      <Listeners>
        <Near Handler="...alignTo('tr-tr'...)"/>  <!-- 鼠标靠近：滑入 -->
        <Far  Handler="...alignTo('tl-tr'...)"/>  <!-- 鼠标远离：滑出 -->
      </Listeners>
    </ext:MouseDistanceSensor>
  </Plugins>
</ext:Panel>
```

## 八、主题适配（9 种主题）

`Page_Load` 中按 `ResourceManager.Theme` switch，针对 9 种主题调整尺寸。要点：**所有像素尺寸集中在此 switch**，markup 只写一套基准值。

## 九、关键复用结论

| 场景 | 推荐做法 |
|---|---|
| 新增桌面业务窗口 | 写 `.ascx` + `<ext:DesktopModuleProxy>`，Desktop.aspx 末尾静态挂载 |
| 按需延迟加载模块 | `LoadControl` → `FindControl<DesktopModuleProxy>` → `RegisterModule()` |
| 完全代码生成模块 | `new DesktopModule{...}` + `Desktop1.AddModule(m)` |
| 实时数据刷新 | `<Bin>` Store + TaskManager + `WaitPreviousRequest=true` + Pass 节流 |
| 全局布局联动 | MessageBus 发布 `App.Xxx.ready`，订阅方 `<MessageBusListeners>` |
| 关闭窗口 | 一律 `CloseAction="Destroy"` |

---

## 十、接入 WebSite 的避坑指南

> 在 `Wongoing.Batch.WebSite` 中用 `<ext:Desktop>` 控件做桌面页面时踩的 5 个坑。适用于 Ext.NET v4.7.1 + Triton 主题。

## 十一、坑 1：Renderer 的 Handler 不能内嵌转义引号

**错误**（XML 解析报"与任何属性都不匹配"）：
```aspx
<Renderer Handler="return '<span style=\"color:red\">'+value+'</span>';" />
```
XML 不认反斜杠转义，内层 `"` 截断属性。

**正确**：抽成全局 JS 函数用 `Fn` 引用：
```aspx
<Renderer Fn="statusRenderer" />
```

## 十二、坑 2：Store 的 Data 不能写成子元素

**错误**（报"与 System.Object 内的任何属性都不匹配"）：
```aspx
<ext:Store runat="server"><Data><![CDATA[...]]></Data></ext:Store>
```

**正确**：`Data` 是属性，用服务端属性绑定 + ArrayReader：
```aspx
<ext:Store runat="server" Data="<%# MyData %>" AutoDataBind="true">
```

## 十三、坑 3：Container 的 Html 不能写成子元素

**错误**（报"必须声明为特性"）：`<ext:Container><Html>...</Html></ext:Container>`

**正确**：用 `<Content>` 子元素：`<ext:Container><Content>...</Content></ext:Container>`

## 十四、坑 4：Desktop Shortcut 的 Name 必须用英文（核心坑）

**症状**：shortcut 的 `Name` 用中文时，图标全部堆叠在 (0,0) 重叠，可能报 `Invalid Element "id"`。

**根因**：Ext.NET 用 `Name` 生成 shortcut 的 DOM id（`Name + "-shortcut"`）。中文 Name → 非法 DOM id。

**解法**：Name 用英文，渲染后用 JS 把文本替换成中文：
```js
var renameShortcuts = function () {
    var map = { 'Grid':'批次台账', 'Notepad':'记事本', 'Welcome':'欢迎' };
    Ext.select('.ux-desktop-shortcut-text').each(function (el) {
        var t = Ext.String.trim(el.dom.innerHTML);
        if (map[t]) { el.dom.innerHTML = map[t]; }
    });
};
// 挂在 DocumentReady，延迟 300ms 等渲染
Ext.defer(renameShortcuts, 300);
```

## 十五、坑 5：Desktop.Ready 不能同时设 Handler 和 BroadcastOnBus

**错误**（报 `Cannot read properties of undefined (reading 'scope')`）：
```aspx
<Ready Handler="myFunc();" BroadcastOnBus="App.Desktop.ready" />
```

**正确**：职责拆分——Ready 只广播，业务逻辑挂 ResourceManager.DocumentReady。

## 十六、快捷方式排列机制

- **只设 `SortIndex`**（不设 X/Y）→ Ext.NET 自动按 SortIndex 纵向排列（约 90px 间隔）。**前提 Name 是合法英文**。
- **推荐**：Name 英文 + 只设 SortIndex。

## 十七、真实 class 名对照（v4.7.1）

| 用途 | 真实 class |
|---|---|
| shortcut 容器 | `ux-desktop-shortcut`（**不是** `x-desktop-shortcut`）|
| 图标 | `ux-desktop-shortcut-icon` + IconCls 值 |
| 文本 | `ux-desktop-shortcut-text` |

## 十八、接入 WebSite 的最小步骤

1. aspx 放 `Plugins/Batch/Desktop/`（WebSite 项目首次访问自动编译）
2. `<%@ Page Language="C#" %>` + 内联 `<script runat="server">`
3. 资源放同目录 `resources/`
4. 登出跳 `~/Plugins/Main/Login.aspx`
5. 在 `SSP_PAGE_MENU` 配菜单 + 权限

---

## 十九、TableLayout 看板开发实战

> 在 Desktop 窗口里用 `Panel` + `TableLayout` 做"类 Excel"看板（行/列合并、斜线表头、竖排分组标签、汉化）。

## 二十、关键技术点

### 9.1 TableLayout 的 ColSpan / RowSpan

Ext.NET TableLayout 子控件支持 ColSpan 和 RowSpan（渲染成 `<td colspan/rowspan>`）：

```csharp
private static Ext.Net.Label MakeCell(string text, string cellCls, int colSpan, int rowSpan)
{
    var label = new Ext.Net.Label { Text = text, ColSpan = colSpan, CellCls = cellCls };
    if (rowSpan > 1) { label.RowSpan = rowSpan; }
    return label;
}
```

⚠️ `Ext.Net.Label` **没有 Encode 属性**（报 CS0117）。要放 HTML 用 `Ext.Net.Component`（有 Html 属性，不编码）。

### 9.2 斜线表头（CSS linear-gradient，非 SVG）

SVG 在 TableLayout 格子里会因 `preserveAspectRatio="none"` 拉伸变形。最终方案用 CSS `linear-gradient`：

```css
.kb-head-split {
    background-image: linear-gradient(
        to top right,
        transparent calc(50% - 0.75px),
        #fff calc(50% - 0.75px),
        #fff calc(50% + 0.75px),
        transparent calc(50% + 0.75px)
    );
}
.kb-split-tr { position: absolute; top: 0; right: 1px; }
.kb-split-bl { position: absolute; bottom: 0; left: 1px; }
```

### 9.3 分组标签竖排（writing-mode）

```css
.kb-group {
    writing-mode: vertical-rl;           /* 竖排 */
    text-orientation: upright;            /* 中文字符正立（关键）*/
    letter-spacing: 6px;
}
```

### 9.4 Ext.NET 内置菜单汉化

用 `MenuManager` 拦截 `beforeshow` 事件替换英文菜单项：
```js
var menuMap = {
    'Restore': '还原', 'Minimize': '最小化', 'Maximize': '最大化',
    'Close': '关闭', 'Close All': '关闭所有', 'Tile': '平铺', 'Cascade': '层叠'
};
Ext.util.Observable.capture(Ext.menu.MenuManager, 'beforeshow', function (menu) {
    menu.items.each(function (item) {
        if (item.text && menuMap[item.text]) { item.setText(menuMap[item.text]); }
    });
    return true;
});
```

## 二十一、踩坑记录

| # | 问题 | 根因 | 解法 |
|---|---|---|---|
| 1 | Window 的 `<Content>` 里 `<%=%>` 不执行 | Ext.NET 把 Content 序列化成 JS 配置 | 改用 `Html="<%# 属性 %>" AutoDataBind="true"` |
| 2 | `Ext.Net.Label.Encode` 报 CS0117 | Label 没有 Encode 属性 | 用 `Ext.Net.Component`（有 Html 属性） |
| 3 | SVG 斜线"画出去了" | `preserveAspectRatio="none"` 拉伸变形 | 改用 CSS linear-gradient |
| 4 | 分组标签竖排中文侧躺 | 缺 `text-orientation: upright` | 加 `text-orientation: upright` |
| 5 | GridPanel 循环生成 31 列失败 | `<ext:Column DataIndex="D<%=d%>">` 解析阶段拿不到值 | 改用 TableLayout + 服务端循环 |

## 二十二、经验总结

| 场景 | 推荐方案 |
|---|---|
| 表格行列合并 | TableLayout + `ColSpan`/`RowSpan` |
| 放 HTML 到单元格 | `Ext.Net.Component`（有 Html 属性，Label 没有 Encode）|
| 斜线表头 | CSS `linear-gradient`（不用 SVG）|
| 竖排中文 | `writing-mode: vertical-rl` + `text-orientation: upright` |
| 内置菜单汉化 | `Ext.menu.MenuManager` 的 `beforeshow` 拦截 |
| 大量重复单元格 | 服务端循环 `items.Add()`，不在标记里 `<%for%>` |

## 二十三、关联

- 页面骨架与布局容器：见 `extnet-page-skeleton.md`
- Renderer 基本写法（Fn vs Handler）：见 `extnet-grid-complete-guide.md`
- 事件机制（DirectMethod / Listeners）：见 `extnet-event-mechanisms.md`
- 定时器（setInterval / TaskManager）：见 `js-setinterval-settimeout.md`
