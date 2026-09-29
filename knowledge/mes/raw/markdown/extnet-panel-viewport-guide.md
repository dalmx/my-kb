---
title: Ext.NET Panel 面板与 Viewport 视口完整指南
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Panel, 面板, Viewport, 视口, BorderLayout, ComponentLoader, Loader, 延迟加载, BodyMask, 遮罩, Tools]
updated: 2026-08-23
status: active
---
# Ext.NET Panel 面板与 Viewport 视口完整指南

> 本文档从 Ext.NET 4.7.1 官方示例库 `Examples/Panel/`（7 示例）+ `Examples/Viewport/`（2 示例）提炼，补强已有页面骨架文档。目标是让 AI/开发者读完即可复现面板、Loader 延迟加载、遮罩、Viewport 主框架。
>
> 适用：Ext.NET 4.x + Triton 主题。

---

## 一、Panel 核心属性

```aspx
<ext:Panel runat="server"
    Title="标题"
    Icon="Application"
    Width="350"
    Height="200"
    BodyPadding="5"
    Border="false"
    Frame="true"
    Collapsible="true"
    Closable="true"
    Html="内容">
</ext:Panel>
```

| 属性 | 作用 |
|------|------|
| `Title` / `Icon` | 标题文字/图标 |
| `Width` / `Height` | 尺寸（px） |
| `BodyPadding` | 内容区内边距 |
| `Border` / `BodyBorder` | 整体边框 / 内容区边框 |
| `Frame="true"` | 圆角边框外观 |
| `Collapsible` | 可折叠（标题栏折叠箭头） |
| `Closable` | 可关闭 |
| `Split="true"` | BorderLayout 里可拖拽分隔条 |

---

## 二、四种填内容方式

### 1. Html（纯字符串）

```aspx
<ext:Panel ID="p1" runat="server" Html="<h1>直接 HTML</h1>" />
<!-- 后台：this.p1.Html = DateTime.Now.ToString(); -->
```

### 2. Content（任意 HTML/ASP.NET 控件）

```aspx
<ext:Panel runat="server">
    <Content>
        <%= DateTime.Now %>
        <p>任意 HTML</p>
    </Content>
</ext:Panel>
```

### 3. Items（Ext.NET 子控件，配合 Layout）

```aspx
<ext:Panel runat="server" Layout="Fit">
    <Items>
        <ext:TabPanel runat="server">...</ext:TabPanel>
    </Items>
</ext:Panel>
```

### 4. contentEl（搬移已有 DOM）

```aspx
<ext:Panel runat="server">
    <CustomConfig>
        <ext:ConfigItem Name="contentEl" Value="myDiv" Mode="Value" />
    </CustomConfig>
</ext:Panel>
<div id="myDiv" class="x-hidden">...</div>
```

---

## 三、工具按钮 Tools（标题栏右侧图标）

```aspx
<ext:Panel runat="server" Title="带工具按钮">
    <Tools>
        <ext:Tool Type="Gear" Tooltip="设置">
            <Listeners><Click Handler="App.direct.OpenSettings();" /></Listeners>
        </ext:Tool>
        <ext:Tool Type="Refresh">
            <DirectEvents>
                <Click OnEvent="ToolRefresh_Click">
                    <EventMask ShowMask="true" />
                </Click>
            </DirectEvents>
        </ext:Tool>
        <ext:Tool Type="Maximize" Handler="this.ownerCt.maximize();" />
    </Tools>
</ext:Panel>
```

`Type` 取 `ToolType` 枚举：`Collapse/Expand/Close/Minimize/Maximize/Restore/Refresh/Save/Gear/Help/Print/Search/Pin/Unpin/Toggle` 等。

---

## 四、TopBar/BottomBar/Buttons/DockedItems

> Toolbar 本身的完整用法（栏位/布局项/溢出）见 [extnet-toolbar-menu-guide.md](extnet-toolbar-menu-guide.md) 一章；本节只讲 Panel 侧的挂载方式。

```aspx
<ext:Panel runat="server" Title="工具栏">
    <TopBar>
        <ext:Toolbar runat="server">
            <Items>
                <ext:Button runat="server" Text="新增" />
                <ext:ToolbarFill runat="server" />
                <ext:ToolbarTextItem runat="server" Text="合计" />
            </Items>
        </ext:Toolbar>
    </TopBar>
    <Buttons>
        <ext:Button runat="server" Text="保存" OnDirectClick="Save" />
    </Buttons>
</ext:Panel>
```

`DockedItems` 是通用写法：

```aspx
<DockedItems>
    <ext:Toolbar runat="server" Dock="Top">...</ext:Toolbar>
    <ext:Toolbar runat="server" Dock="Bottom">...</ext:Toolbar>
</DockedItems>
```

---

## 五、ComponentLoader（异步加载外部页）

第四种填内容方式：加载另一个页面的内容。

### 三种 Mode

```aspx
<!-- Mode="Html"：取子页 body 内 HTML 注入（脚本会执行） -->
<ext:Panel runat="server" Title="合并模式">
    <Loader runat="server" Url="Child.aspx" Mode="Html">
        <LoadMask ShowMask="true" />
    </Loader>
</ext:Panel>

<!-- Mode="Frame"：iframe 加载完整子页（最安全） -->
<ext:Panel runat="server" Title="框架模式">
    <Loader runat="server" Url="Child.aspx" Mode="Frame">
        <LoadMask ShowMask="true" />
    </Loader>
</ext:Panel>
```

### Loader 关键属性

| 属性 | 作用 |
|------|------|
| `Url` | 加载地址 |
| `Mode` | `Html`/`Frame`/`Component`/`Data` |
| `TriggerEvent` | 触发事件：`render`/`show`/`expand`/`activate` |
| `AutoLoad` | 是否自动加载（默认 true） |
| `ReloadOnEvent` | 触发事件每次都重载 |
| `DisableCaching` | 加时间戳防缓存 |
| `TriggerControl` | 触发控件（默认面板自身） |

### 延迟加载模式

```aspx
<!-- show 时加载 -->
<ext:Panel runat="server" Title="展开加载">
    <Loader runat="server" Url="Child.aspx" Mode="Frame" TriggerEvent="show">
        <LoadMask ShowMask="true" />
    </Loader>
</ext:Panel>

<!-- 手动触发 -->
<ext:Panel ID="p2" runat="server" Title="手动加载">
    <Loader runat="server" Url="Child.aspx" Mode="Frame"
        AutoLoad="false" ManuallyTriggered="true">
        <LoadMask ShowMask="true" />
    </Loader>
    <TopBar>
        <ext:Toolbar runat="server"><Items>
            <ext:Button runat="server" Text="加载">
                <Listeners><Click Handler="App.p2.reload();" /></Listeners>
            </ext:Button>
        </Items></ext:Toolbar>
    </TopBar>
</ext:Panel>
```

### 后台动态加载

```csharp
this.p2.LoadContent("Child.aspx", true);              // (url, disableCaching)
this.p2.LoadContent(new ComponentLoader { Url="Child.aspx", Mode=LoadMode.Frame });
```

### iframe 间通信

```javascript
// 子页访问父页另一 iframe 面板
parent.App.Panel2.getBody().App.TextField1.setValue(value);
```

---

## 六、BodyMask 遮罩

### 标准 LoadMask

```aspx
<ext:Panel runat="server">
    <Loader runat="server" Url="Child.aspx" Mode="Frame">
        <LoadMask ShowMask="true" Msg="加载中..." />
    </Loader>
</ext:Panel>
```

### 自定义遮罩

```aspx
<ext:Panel ID="p3" runat="server">
    <Loader runat="server" Url="Child.aspx" Mode="Frame">
        <Listeners>
            <BeforeLoad Handler="Ext.get('myMask').removeCls('x-hidden-display');" />
            <Load Handler="Ext.get('myMask').addCls('x-hidden-display');" />
        </Listeners>
    </Loader>
</ext:Panel>
<div id="myMask" class="x-hidden-display">自定义加载...</div>
```

---

## 七、Viewport（自动撑满窗口）

`<ext:Viewport>` 自动占满浏览器视口，随窗口缩放，几乎总是配合 `BorderLayout` 做主框架。

```aspx
<ext:Viewport runat="server" Layout="BorderLayout">
    <Items>
        <ext:Panel runat="server" Region="North" Height="60" Html="顶部" />

        <ext:Panel runat="server" Region="West" Width="220" Split="true"
            Collapsible="true" Title="导航" Layout="AccordionLayout">
            <Items>
                <ext:Panel runat="server" Title="菜单1" />
                <ext:Panel runat="server" Title="菜单2" />
            </Items>
        </ext:Panel>

        <ext:TabPanel runat="server" Region="Center">
            <Items>
                <ext:Panel runat="server" Title="首页" Html="主体" />
            </Items>
        </ext:TabPanel>

        <ext:Panel runat="server" Region="South" Height="30" Html="底部" />
    </Items>
</ext:Viewport>
```

### Panel vs Viewport

| 维度 | Panel | Viewport |
|------|-------|----------|
| 尺寸 | 需显式 Width/Height | 自动 100% 撑满视口 |
| 位置 | 可任意子节点 | 页面顶层根容器 |
| 典型用途 | 卡片/子面板/弹窗 | 后台主框架（BorderLayout） |

---

## 八、踩坑要点

### 坑1：Loader Html 模式的子页 ResourceManager ID 要一致

Html 模式合并子页脚本时，子页的 `<ext:ResourceManager>` 的 **ID 必须与父页一致**，否则脚本注入冲突。

### 坑2：BorderLayout 的 Center 区域必须有且仅有一个

```aspx
Region="Center"   <!-- 一个页面只能有一个 Center -->
```

其他区域（North/South/East/West）可省略，Center 不可省。

### 坑3：TriggerControl 引用别的控件要用 #{}

```aspx
<Loader TriggerControl="#{ParentPanel}" TriggerEvent="Activate" />
```

### 坑4：Viewport 不放 form

Viewport 通常不放 `<form runat="server">`，所以页面有它时 ASP.NET PostBack 失效——用 DirectEvent/DirectMethod 走 AJAX。

### 坑5：Frame 模式跨域加载受 X-Frame-Options 限制

iframe 加载外部网站，若对方设 `X-Frame-Options: DENY`，会加载空白。同源页面无此问题。

---

## 九、关联文档

| 文档 | 关系 |
|------|------|
| `extnet-page-skeleton.md` | 页面骨架（Viewport/BorderLayout 主框架） |
| `extnet-window-guide.md` | Window（Window 是浮动 Panel） |
| `extnet-editor-and-loaders-guide.md` | Loaders（ComponentLoader 详解） |
| `extnet-toolbar-menu-guide.md` | 工具栏（TopBar/BottomBar） |

## 十、参考来源

- `Examples/Panel/Basic/`（Loader / Loader_Html_Mode / Deferred_Loading / IFrame_Communication）
- `Examples/Panel/BodyMask/`（Standard_Mask / Custom_Mask）
- `Examples/Panel/Miscellaneous/Bubble_Panel/`（自定义 UI）
- `Examples/Viewport/Basic/`（Built_in_Markup / Built_in_CodeBehind）
