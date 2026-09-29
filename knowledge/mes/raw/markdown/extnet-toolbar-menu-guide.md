---
title: Ext.NET Toolbar / Menu / Breadcrumb / StatusBar 完整指南
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Toolbar, 工具栏, Menu, 菜单, ContextMenu, Breadcrumb, StatusBar]
updated: 2026-08-23
status: active
---
# Ext.NET Toolbar / Menu / Breadcrumb / StatusBar 完整指南

> 本文档从 Ext.NET 4.7.1 官方示例库 `Examples/Toolbar/`（18 个示例）提炼，覆盖工具栏、菜单（下拉/上下文/水平）、面包屑导航、状态栏、工具栏插件。目标是让 AI/开发者读完即可在任意 Ext.NET WebForms 项目复现。
>
> 适用：Ext.NET 4.x + Triton 主题。底层是 ExtJS 的 `Ext.toolbar.Toolbar` / `Ext.menu.Menu`。

---

## 一、Toolbar 工具栏

Toolbar 是容器控件的**配件**，通过四个栏位嵌入 Panel/Window/GridPanel/FormPanel 等：

### 1.1 四个栏位嵌入方式

| 栏位 | 写法 | 位置 |
|------|------|------|
| 顶栏 | `<TopBar><ext:Toolbar>...</ext:Toolbar></TopBar>` | 顶部（最常用） |
| 底栏 | `<BottomBar><ext:StatusBar>...</ext:StatusBar></BottomBar>` | 底部 |
| 左栏 | `<LeftBar>...</LeftBar>` | 左侧（竖向） |
| 右栏 | `<RightBar>...</RightBar>` | 右侧（竖向） |

典型用法：

```aspx
<ext:Panel runat="server" Title="带工具栏的面板" Width="700" Height="300">
    <TopBar>
        <ext:Toolbar runat="server">
            <Items>
                <ext:Button runat="server" Icon="Add" Text="新增" OnDirectClick="AddItem" />
                <ext:Button runat="server" Icon="Delete" Text="删除" />
            </Items>
        </ext:Toolbar>
    </TopBar>
</ext:Panel>
```

Toolbar 也可作为独立控件直接放页面（通过 `Width` 控制宽度），但**绝大多数场景是作为容器配件**。

### 1.2 Toolbar 内部项（Items）

Toolbar 的 `<Items>` 可放任意组件，但有几类**专用布局项**：

| 控件 | 作用 | 写法 |
|------|------|------|
| `ext:ToolbarFill` | 占满剩余宽度，把后续项推到最右 | `<ext:ToolbarFill runat="server" />` |
| `ext:ToolbarSpacer` | 固定小间距 | `<ext:ToolbarSpacer runat="server" />` |
| `ext:ToolbarSeparator` | 竖向分隔线 | `<ext:ToolbarSeparator runat="server" />` |
| `ext:ToolbarTextItem` | 纯文本标签 | `<ext:ToolbarTextItem runat="server" Text="共 100 条" />` |
| `ext:Button`/`SplitButton` | 按钮 | 见 buttons-guide |
| `ext:TextField`/`ComboBox`/`DateField` | 表单控件 | 直接放入即可 |
| `ext:ButtonGroup` | 按钮分组 | 见 1.5 |

**经典布局**（左对齐操作按钮 + 右对齐信息）：

```aspx
<ext:Toolbar runat="server">
    <Items>
        <ext:Button runat="server" Text="新增" Icon="Add" />
        <ext:Button runat="server" Text="删除" Icon="Delete" />
        <ext:ToolbarFill runat="server" />              <!-- 推到最右 -->
        <ext:ToolbarTextItem runat="server" Text="合计：" />
        <ext:ToolbarTextItem ID="TotalText" runat="server" Text="0" />
    </Items>
</ext:Toolbar>
```

> `ToolbarFill` 与 `ToolbarSpacer` 区别：Fill 是 `flex:1` 撑满剩余空间；Spacer 是固定的小间距。

### 1.3 Flat 扁平工具栏

加 `Flat="true"` 去掉背景边框，嵌入无边框区域时更协调：

```aspx
<ext:Toolbar runat="server" Flat="true">
    <Items>...</Items>
</ext:Toolbar>
```

### 1.4 溢出处理 EnableOverflow

工具栏宽度不足时，超出项自动收入右侧溢出菜单（≫）：

```aspx
<ext:Toolbar runat="server" EnableOverflow="true">
    <Items>
        <!-- 多个按钮，窄屏时自动折进溢出菜单 -->
    </Items>
</ext:Toolbar>
```

### 1.5 ButtonGroup 按钮组（Ribbon 风格）

Toolbar 的 `<Items>` 里可直接放 `ext:ButtonGroup`（带标题的按钮分组，Office Ribbon 风格；Columns 列数 / RowSpan 跨行 / Defaults 批量默认属性 / HeaderPosition 标题位置）。

完整写法与属性详解见 [extnet-buttons-guide.md](extnet-buttons-guide.md) 第四章。

### 1.6 多工具栏切换（Toolbar Switcher）

在同一栏位放多个 Toolbar，通过 JS `hide()`/`show()` 切换：

```aspx
<ext:Toolbar ID="EuropeToolbar" runat="server" Flat="true" Flex="1">
    <Items>...</Items>
</ext:Toolbar>
<ext:Toolbar ID="AsiaToolbar" runat="server" Flat="true"
    HideMode="Offsets" Hidden="true" Flex="1">
    <Items>...</Items>
</ext:Toolbar>
```

```javascript
var switchToolbar = function (toolbar) {
    Ext.select('.toolbar-switch').each(function (t) {
        Ext.getCmp(t.dom.id).hide();
    });
    toolbar.show();
};
```

> 要点：隐藏的子工具栏用 `HideMode="Offsets"` + `Flex="1"`，让隐藏时仍占位，切换不抖动。

---

## 二、Menu 菜单

### 2.1 菜单容器两种写法

**写法 A：作为 Button/SplitButton 的 `<Menu>` 子元素**（最常用，点击自动展开）：

```aspx
<ext:Button runat="server" Text="操作">
    <Menu>
        <ext:Menu runat="server">
            <Items>
                <ext:MenuItem runat="server" Text="新增" Icon="Add" />
                <ext:MenuItem runat="server" Text="删除" Icon="Delete" />
            </Items>
        </ext:Menu>
    </Menu>
</ext:Button>
```

- `Button`：点击按钮主体即展开菜单
- `SplitButton`：点主体执行 Click，点箭头才展开菜单

**写法 B：独立 `ext:Menu` 控件**（用于右键菜单、动态加载、多控件复用）：

```aspx
<ext:Menu ID="ContextMenu" runat="server">
    <Items>...</Items>
</ext:Menu>
```

### 2.2 菜单项类型

| 控件 | 用途 | 关键属性 |
|------|------|----------|
| `ext:MenuItem` | 普通菜单项 | `Text`/`Icon`/`IconCls`/`Handler`/`Disabled`/`HideOnClick` |
| `ext:MenuSeparator` | 分隔线 | 自闭合 `<ext:MenuSeparator />` |
| `ext:CheckMenuItem` | 复选菜单项 | `Checked`/`CheckHandler`/`Group`(同名→单选) |
| `ext:DateMenu` | 日期选择菜单 | 内含 `<Picker>`，监听 `Select` |
| `ext:ColorMenu` | 颜色选择菜单 | 监听 `Select`，参数 `color` |

**菜单项点击事件三种写法**：

```aspx
<!-- 1. 客户端 Handler 内联 -->
<ext:MenuItem runat="server" Text="新增" Handler="addItem();" />

<!-- 2. Listeners -->
<ext:MenuItem runat="server" Text="编辑">
    <Listeners><Click Handler="editItem();" /></Listeners>
</ext:MenuItem>

<!-- 3. DirectEvents（服务端回调） -->
<ext:MenuItem runat="server" Text="删除">
    <DirectEvents>
        <Click OnEvent="DeleteItem">
            <EventMask ShowMask="true" />
            <ExtraParams>
                <ext:Parameter Name="id" Value="App.HiddenId.getValue()" Mode="Raw" />
            </ExtraParams>
        </Click>
    </DirectEvents>
</ext:MenuItem>
```

**复选菜单项**：

```aspx
<ext:CheckMenuItem runat="server" Checked="true" Text="显示合计行" CheckHandler="onItemCheck" />
```

**单选菜单项**（同名 Group 互斥）：

```aspx
<ext:Menu runat="server">
    <Items>
        <ext:CheckMenuItem runat="server" Text="主题A" Checked="true" Group="theme" CheckHandler="onItemCheck" />
        <ext:CheckMenuItem runat="server" Text="主题B" Group="theme" CheckHandler="onItemCheck" />
    </Items>
</ext:Menu>
```

```javascript
var onItemCheck = function (item, checked) {
    Ext.Msg.alert('选择', item.text + ' : ' + checked);
};
```

### 2.3 菜单内嵌任意控件

Menu 的 `<Items>` 可放任何组件（TextField/DateField/ComboBox/GridPanel/Panel/TabPanel 等）。**嵌套控件要加 `Focusable="false"`** 防止抢焦点导致菜单自动隐藏：

```aspx
<ext:Menu runat="server" EnableKeyNav="false">
    <Items>
        <ext:MenuItem runat="server" Icon="NoteEdit" Text="查找" />
        <ext:TextField runat="server" Width="200" MarginSpec="0 0 2 30" Focusable="false" />
        <ext:MenuSeparator runat="server" />
        <ext:ComboBox runat="server" Width="200" Editable="false" MarginSpec="0 0 2 30" Focusable="false">
            <Items>
                <ext:ListItem Text="选项1" />
                <ext:ListItem Text="选项2" />
            </Items>
        </ext:ComboBox>
    </Items>
</ext:Menu>
```

> `MarginSpec="0 0 2 30"` 控制缩进（左 30px），让嵌套控件与菜单项对齐。

### 2.4 动态添加菜单项

**方式 1：服务端 C# 操作 Items 集合**：

```csharp
protected void Page_Load(object sender, EventArgs e)
{
    var item = new Ext.Net.MenuItem { Text = "动态项", Handler = "onItemClick" };
    MenuButton.Menu.Primary.Items.Add(item);

    // 超长菜单自动滚动
    var scrollingMenu = new Ext.Net.Menu { MaxHeight = 250 };
    for (int i = 0; i < 50; i++)
    {
        scrollingMenu.Items.Add(new Ext.Net.MenuItem { Text = "项 " + (i + 1), Width = 100 });
    }
    ScrollingButton.Menu.Add(scrollingMenu);
}
```

**方式 2：ComponentLoader + DirectMethod 懒加载**（点击展开才请求）：

```aspx
<ext:Button runat="server" Text="文件">
    <Menu>
        <ext:Menu runat="server" TagString="file">
            <Items>
                <ext:MenuItem runat="server" IconCls="x-loading-indicator"
                    Text="加载中..." Focusable="false" HideOnClick="false" />
            </Items>
            <Loader Mode="Component" DirectMethod="#{DirectMethods}.LoadMenuItems" RemoveAll="true">
                <Params>
                    <ext:Parameter Name="tag" Value="this.tag" Mode="Raw" />
                </Params>
            </Loader>
        </ext:Menu>
    </Menu>
</ext:Button>
```

```csharp
[DirectMethod]
public string LoadMenuItems(Dictionary<string, string> parameters)
{
    string tag = parameters["tag"];
    var items = new List<Ext.Net.MenuItem>();
    items.Add(new Ext.Net.MenuItem("新建") { Icon = Icon.New });
    items.Add(new Ext.Net.MenuItem("打开") { Icon = Icon.Folder });
    return ComponentLoader.ToConfig(items);  // 关键：序列化为客户端配置
}
```

> 要点：`Loader Mode="Component"` + `DirectMethod` 指向 `[DirectMethod]` 方法，`RemoveAll="true"` 加载前清空占位项。服务端必须 `return ComponentLoader.ToConfig(items)`。

### 2.5 水平菜单（导航条）

让 Menu 横向排列，作独立导航：

```aspx
<ext:Menu runat="server" Floating="false" Layout="HBoxLayout" ShowSeparator="false">
    <Defaults>
        <ext:Parameter Name="MenuAlign" Value="tl-bl?" Mode="Value" />
    </Defaults>
    <Items>
        <ext:MenuItem runat="server" Text="文件" Icon="BulletBlue">
            <Menu><ext:Menu runat="server"><Items>
                <ext:MenuItem Text="新建" />
            </Items></ext:Menu></Menu>
        </ext:MenuItem>
    </Items>
</ext:Menu>
```

> `Floating="false"` + `Layout="HBoxLayout"` 让菜单横向；子菜单对齐用 `MenuAlign="tl-bl?"`。

---

## 三、ContextMenu 右键菜单

把独立 `ext:Menu` 通过目标控件的 `ContextMenuID` 属性绑定：

```aspx
<ext:Menu ID="GridContextMenu" runat="server">
    <Items>
        <ext:MenuItem runat="server" Text="编辑" Icon="PageWhiteEdit" />
        <ext:MenuItem runat="server" Text="删除" Icon="Delete" />
    </Items>
</ext:Menu>

<ext:GridPanel runat="server" ContextMenuID="GridContextMenu">
    ...
</ext:GridPanel>
```

> 同一 Menu 可被多个控件通过 `ContextMenuID` 复用。判断右键来源用 `menu.lastTargetIn(component)`。

---

## 四、Breadcrumb 面包屑导航

绑定 TreeStore，根据树结构显示路径，点击跳转：

```aspx
<ext:Panel runat="server" Title="面包屑" Height="400">
    <TopBar>
        <ext:Breadcrumb ID="Breadcrumb1" runat="server"
            ShowIcons="true"
            OverflowHandler="Scroller"
            Selection="/部门A/班组1/">
            <Store>
                <ext:TreeStore ID="TreeStore1" runat="server" />
            </Store>
            <DirectEvents>
                <SelectionChange OnEvent="OnSelectionChange" />
            </DirectEvents>
        </ext:Breadcrumb>
    </TopBar>
</ext:Panel>
```

服务端构造树：

```csharp
protected void Page_Load(object sender, EventArgs e)
{
    var root = new Ext.Net.Node { Text = "根", NodeID = "/", Expanded = true };
    root.Children.Add(new Ext.Net.Node { Text = "部门A", NodeID = "/部门A/", Leaf = false });
    this.TreeStore1.Root.Add(root);
}

protected void OnSelectionChange(object sender, DirectEventArgs e)
{
    // Breadcrumb1.Selection 返回当前选中节点的 id 路径
    this.Panel1.Html = "选中：" + Breadcrumb1.Selection;
    this.Panel1.Body.Highlight();
}
```

| 属性 | 作用 |
|------|------|
| `ShowIcons="true"` | 显示节点图标 |
| `OverflowHandler="Scroller"` | 路径过长用滚动条（而非溢出菜单） |
| `Selection` | 设置/读取当前选中路径（节点 id 组成） |

> Breadcrumb 通常放 `<TopBar>`，数据源是 `TreeStore`（不是普通 Store）。

---

## 五、StatusBar 状态栏

`ext:StatusBar` 是增强版 Toolbar，专用于底部状态显示。

### 5.1 基础用法

```aspx
<ext:Panel runat="server" Title="状态栏示例" Width="500" Height="200">
    <BottomBar>
        <ext:StatusBar ID="StatusBar1" runat="server" DefaultText="就绪" StatusAlign="Right">
            <Items>
                <ext:ToolbarTextItem runat="server" Text="| " />
                <ext:Button runat="server" Text="操作" />
            </Items>
        </ext:StatusBar>
    </BottomBar>
</ext:Panel>
```

| 属性 | 作用 |
|------|------|
| `DefaultText` | 初始状态文本 |
| `StatusAlign="Right"` | 状态文本右对齐（默认左） |

### 5.2 文本/图标/忙状态

**客户端 JS**：

```javascript
App.StatusBar1.showBusy();                              // 忙碌图标 + 默认文本
App.StatusBar1.showBusy('正在保存...');                  // 忙碌 + 自定义文本
App.StatusBar1.setStatus({ text: '已保存', iconCls: 'x-status-saved' });
App.StatusBar1.clearStatus();                           // 清除状态
```

**服务端 C#**：

```csharp
protected void Save(object sender, DirectEventArgs e)
{
    var config = new StatusBarStatusConfig
    {
        Text = "已保存于 " + DateTime.Now.ToLongTimeString(),
        IconCls = "x-status-saved"
    };
    this.StatusBar1.SetStatus(config);
}
```

**配合 DirectEvent 显示忙状态**（请求前 showBusy，完成后恢复）：

```aspx
<ext:Button runat="server" Text="保存">
    <DirectEvents>
        <Click OnEvent="Save"
               Before="el.disable();#{StatusBar1}.showBusy('保存中...');"
               Complete="el.enable();">
            <EventMask MinDelay="1000" />
        </Click>
    </DirectEvents>
</ext:Button>
```

> 自定义图标靠 CSS + `IconCls`，通过 `CtCls` 挂到 StatusBar。

### 5.3 ValidationStatus 表单校验联动

让 StatusBar 自动同步 FormPanel 校验状态：

```aspx
<ext:StatusBar ID="FormStatusBar" runat="server" DefaultText="就绪">
    <Plugins>
        <ext:ValidationStatus runat="server"
            FormPanelID="MyForm"
            ValidIcon="Accept"
            ErrorIcon="Exclamation" />
    </Plugins>
</ext:StatusBar>
```

> 表单无效时显示错误，点错误项可聚焦到对应字段。

---

## 六、Toolbar Plugins 插件

### BoxReorderer（拖拽重排序）

让工具栏按钮可拖拽换位：

```aspx
<ext:Toolbar runat="server">
    <Plugins>
        <ext:BoxReorderer runat="server" DefaultReorderable="true">
            <Listeners>
                <Drop Handler="var order = [];
                    container.items.each(function(item){ order.push(item.text); });
                    App.Label1.setText(order.join(', '));" />
            </Listeners>
        </ext:BoxReorderer>
    </Plugins>
    <Items>
        <ext:Button runat="server" Text="A" />
        <ext:Button runat="server" Text="B" Reorderable="false" />  <!-- 排除某项 -->
        <ext:Button runat="server" Text="C" />
    </Items>
</ext:Toolbar>
```

| 配置 | 作用 |
|------|------|
| `DefaultReorderable="true"` | 所有子项默认可拖 |
| 子项 `Reorderable="false"` | 单独禁用某项 |
| `Drop` 事件 | 拖拽完成回调，`container.items` 是排序后集合 |

---

## 七、踩坑要点

### 坑1：ToolbarFill vs ToolbarSpacer 混淆

`ToolbarFill` 是 `flex:1` 撑满剩余宽度（推后续项到最右）；`ToolbarSpacer` 只是固定小间距。要"左操作右信息"布局用 Fill。

### 坑2：菜单内嵌控件必须 Focusable="false"

Menu 内放 TextField/ComboBox 等，不加 `Focusable="false"` 会导致控件获得焦点时菜单自动隐藏（菜单检测到焦点离开就关闭）。

### 坑3：CheckMenuItem 单选必须同名 Group

多个 CheckMenuItem 要单选互斥，必须设**相同**的 `Group` 值，否则各自独立成为复选项。

### 坑4：DirectMethod 懒加载菜单必须 ToConfig

服务端 `[DirectMethod]` 返回菜单项时，必须用 `ComponentLoader.ToConfig(items)` 序列化，直接 return 对象无效。

### 坑5：水平菜单的 Floating="false"

普通 Menu 默认 `Floating="true"`（浮动的，点击触发）。做横向导航条要设 `Floating="false"` 才能脱离浮动模式正常布局。

### 坑6：StatusBar 的 SetStatus 用 StatusBarStatusConfig

服务端设置状态用 `SetStatus(new StatusBarStatusConfig{...})`，不是直接赋 Text 属性。

---

## 八、关联文档

| 文档 | 关系 |
|------|------|
| `extnet-buttons-guide.md` | 按钮控件（工具栏内的核心元素） |
| `extnet-page-skeleton.md` | 页面骨架（工具栏是页面标配） |
| `extnet-window-guide.md` | 窗口（窗口顶部/底部工具栏） |
| `extnet-grid-complete-guide.md` | GridPanel（表格顶部工具栏、分页栏） |
| `extnet-tree-guide.md` | TreePanel（面包屑常与树联动） |

## 九、参考来源

- 官方示例库：`Examples/Toolbar/`（18 个示例）
  - `Menu/Overview/`：菜单项类型 + 三种事件写法
  - `Menu/Toolbar_with_Menus/`：工具栏内嵌菜单 + 动态添加
  - `Menu/Horizontal_Menu/`：水平导航菜单
  - `Menu/Context_Menu/`：右键菜单
  - `Menu/Controls_In_Menu/`：菜单内嵌任意控件
  - `Menu/Dynamic_Items/`：DirectMethod 懒加载菜单
  - `Menu/Flat_Toolbar/`：扁平工具栏
  - `Menu/Toolbar_ButtonGroup/`：Ribbon 按钮组
  - `Menu/Toolbar_Overflow/`：溢出处理
  - `Menu/Toolbar_Switcher/`：多工具栏切换
  - `Breadcrumb/Overview/`：面包屑导航
  - `StatusBar/Overview/`、`Advanced/`：状态栏 + ValidationStatus
  - `Plugins/ToolbarReorderable/`：拖拽重排序
