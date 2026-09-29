---
title: Ext.NET Button 按钮完整指南
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Button, 按钮, SplitButton, ImageButton, SegmentedButton, ButtonGroup, LoadingState]
status: active
updated: 2026-08-29
---
# Ext.NET Button 按钮完整指南

> 本文档从 Ext.NET 4.7.1 官方示例库 `Examples/Buttons/`（8 个示例）提炼，覆盖普通按钮、分裂按钮、图片按钮、超链接按钮、分段按钮、按钮组等。目标是让 AI/开发者读完即可在任意 Ext.NET WebForms 项目复现。
>
> 适用：Ext.NET 4.x + Triton 主题（Classic Toolkit）。

---

## 一、Button 核心属性

### 1.1 文本与图标

```aspx
<!-- 内置图标：用 Icon 枚举名（如 Add/Accept/Delete/Disk/PageWhiteEdit） -->
<ext:Button runat="server" Text="新增" Icon="Add" />

<!-- 自定义图标：用 CSS 类 -->
<style>.my-icon { background-image: url(arrow-down.png) !important; }</style>
<ext:Button runat="server" Text="下载" IconCls="my-icon" />

<!-- 图标位置：IconAlign = Left(默认) / Right / Top / Bottom -->
<ext:Button runat="server" Text="右图标" Icon="Accept" IconAlign="Right" />
<ext:Button runat="server" Text="顶部图标" Icon="Add" IconAlign="Top" Scale="Large" />
```

| 属性 | 作用 | 取值 |
|------|------|------|
| `Text` | 按钮文字 | 字符串 |
| `Icon` | 内置图标 | Icon 枚举（如 `Add`/`Delete`/`Disk`/`Accept`） |
| `IconCls` | 自定义图标 CSS 类 | CSS 类名 |
| `IconAlign` | 图标位置 | `Left`(默认) / `Right` / `Top` / `Bottom` |

### 1.2 尺寸

```aspx
<!-- Scale 枚举：Small / Medium / Large -->
<ext:Button runat="server" Text="大" Scale="Large" />
<ext:Button runat="server" Text="中" Scale="Medium" />
<ext:Button runat="server" Text="小" Scale="Small" />

<!-- 自定义精确尺寸 -->
<ext:Button runat="server" Text="自定义" Height="60" Width="120" />

<!-- 文本对齐（按钮需有宽度才看得出） -->
<ext:Button runat="server" Text="左对齐" TextAlign="Left" Width="200" />
```

| 属性 | 作用 | 取值 |
|------|------|------|
| `Scale` | 尺寸档位 | `Small`(默认) / `Medium` / `Large` |
| `Width` / `Height` | 精确尺寸 | 像素值 |
| `TextAlign` | 文字对齐 | `Left` / `Center`(默认) / `Right` |

### 1.3 状态

```aspx
<ext:Button runat="server" Text="禁用" Disabled="true" />
<ext:Button runat="server" Text="隐藏" Hidden="true" />

<!-- 可切换按下/弹起 -->
<ext:Button runat="server" Text="切换" EnableToggle="true" Pressed="true" />

<!-- 单选互斥：同一 ToggleGroup 内只能有一个按下 -->
<ext:Button runat="server" Text="视图1" EnableToggle="true" ToggleGroup="View" Pressed="true" />
<ext:Button runat="server" Text="视图2" EnableToggle="true" ToggleGroup="View" />
<ext:Button runat="server" Text="视图3" EnableToggle="true" ToggleGroup="View" />
```

| 属性 | 作用 |
|------|------|
| `Disabled="true"` | 禁用（灰显不可点） |
| `Hidden="true"` | 隐藏 |
| `EnableToggle="true"` | 开启按下/弹起切换 |
| `Pressed="true"` | 初始为按下状态 |
| `ToggleGroup="名称"` | 同名组内单选互斥 |

### 1.4 样式

```aspx
<!-- 扁平样式（无边框） -->
<ext:Button runat="server" Text="Flat" Icon="Accept" Flat="true" />

<!-- 自定义 CSS 类 -->
<ext:Button runat="server" Text="自定义" Cls="my-btn" />

<!-- 工具提示 -->
<ext:Button runat="server" Text="悬停看提示">
    <ToolTips>
        <ext:ToolTip runat="server" Title="提示标题" Html="提示内容" />
    </ToolTips>
</ext:Button>
```

> **重要**：Ext.NET 4.x (Classic Toolkit) 的 Button **没有** `UI="primary/danger"` 这类语义样式属性（那是 Modern Toolkit 写法）。Classic 按钮样式通过 `Cls`、`Flat`、`Scale` 控制。

---

## 二、Button 事件三种写法

这是 Button 最核心的知识，三种方式适用不同场景：

### 2.1 OnClientClick —— 纯客户端 JS（最轻量）

```aspx
<ext:Button runat="server" Text="客户端点击"
    OnClientClick="Ext.Msg.alert('提示', '点击了');" />
```

适用：纯前端逻辑、提示、跳转、表单校验拦截。**不触发服务端回发**。

### 2.2 Listeners Click —— 客户端 Listener

```aspx
<ext:Button runat="server" Text="Listener 点击">
    <Listeners>
        <Click Handler="alert('点击了');" />
    </Listeners>
</ext:Button>
```

适用：需要 Ext 事件参数（item/e）、与 Ext 事件链兼容的客户端逻辑。`Handler` 写 JS 语句。

### 2.3 OnDirectClick / DirectEvents Click —— 服务端 DirectEvent（AJAX 回传）

**简写形式**：

```aspx
<ext:Button runat="server" Text="保存" Icon="Disk" OnDirectClick="Save_Click" />
```

**完整形式**（带遮罩、额外参数、前置校验）：

```aspx
<ext:Button runat="server" Text="保存" Icon="Disk">
    <DirectEvents>
        <Click OnEvent="Save_Click"
               Before="return #{FormPanel1}.getForm().isValid();"
               Success="App.Window1.hide();">
            <EventMask ShowMask="true" Msg="保存中..." />
            <ExtraParams>
                <ext:Parameter Name="id" Value="App.HiddenId.getValue()" Mode="Raw" />
            </ExtraParams>
        </Click>
    </DirectEvents>
</ext:Button>
```

```csharp
protected void Save_Click(object sender, DirectEventArgs e)
{
    string id = e.ExtraParams["id"];   // 读取额外参数
    // ... 业务逻辑
    X.Msg.Notify("成功", "数据已保存").Show();
}
```

### 三种方式对比

| 写法 | 执行位置 | 是否回传服务端 | 典型场景 |
|------|---------|--------------|---------|
| `OnClientClick` | 浏览器 | 否 | 简单 JS 提示/跳转/校验拦截 |
| `<Listeners><Click>` | 浏览器 | 否 | 需 Ext 事件参数的客户端逻辑 |
| `OnDirectClick` / `<DirectEvents><Click>` | 浏览器→服务端 AJAX | 是 | 服务端数据/保存/刷新 |

> `OnDirectClick` 是 `DirectEvents.Click` 的快捷写法，二者等价；需要 `EventMask`/`ExtraParams`/`Before`/`Success` 配置时必须用完整 `DirectEvents` 形式。

---

## 三、Button 变体

### 3.1 带下拉菜单的按钮（Menu 子元素）

```aspx
<ext:Button runat="server" Text="操作" Icon="Application">
    <Menu>
        <ext:Menu runat="server">
            <Items>
                <ext:MenuItem runat="server" Text="新增" Icon="Add" />
                <ext:MenuSeparator runat="server" />
                <ext:MenuItem runat="server" Text="删除" Icon="Delete" />
            </Items>
        </ext:Menu>
    </Menu>
</ext:Button>
```

点击按钮主体即展开菜单。箭头位置由 `ArrowAlign` 控制（`Right` 默认 / `Bottom`）。

### 3.2 SplitButton（分裂按钮：主体和箭头分开）

```aspx
<ext:SplitButton runat="server" Text="导出" Icon="PageExcel">
    <Menu>
        <ext:Menu runat="server">
            <Items>
                <ext:MenuItem runat="server" Text="导出当前页" />
                <ext:MenuItem runat="server" Text="导出全部" />
            </Items>
        </ext:Menu>
    </Menu>
    <Listeners>
        <Click Handler="defaultExport();" />            <!-- 点主体 -->
        <ArrowClick Handler="this.showMenu();" />       <!-- 点箭头（默认展开菜单） -->
    </Listeners>
</ext:SplitButton>
```

- **主体**和**箭头**是两个独立区域：点主体触发 `Click`，点箭头展开菜单
- `Button` vs `SplitButton`：Button 点整个按钮都展开菜单；SplitButton 点主体执行动作、点箭头才展开

**SplitButton 自定义下拉面板**（非 Menu）：用 `<Bin>` 放浮动面板：

```aspx
<ext:SplitButton runat="server" Text="筛选">
    <Bin>
        <ext:Panel runat="server" Width="200" Floating="true" Title="筛选条件">
            <Items>
                <ext:TextField runat="server" FieldLabel="名称" />
            </Items>
        </ext:Panel>
    </Bin>
    <Listeners>
        <ArrowClick Handler="this.bin[0].show(); this.bin[0].alignTo(this.el);" />
    </Listeners>
</ext:SplitButton>
```

### 3.3 HyperlinkButton（超链接按钮）

样式为超链接的按钮，事件模型同 Button：

```aspx
<ext:HyperlinkButton runat="server" Text="点击" Icon="Accept">
    <DirectEvents>
        <Click OnEvent="DoSomething" />
    </DirectEvents>
</ext:HyperlinkButton>
```

> 要在点击时跳转，用 `OnClientClick="window.location='url'"`，或用纯 `<ext:Hyperlink>`（`<ext:Hyperlink runat="server" Text="链接" Href="url" />`）。HyperlinkButton 本质是按钮，不是 `<a>`。

### 3.4 ImageButton（图片按钮）

用图片渲染，支持四种状态图：

```aspx
<ext:ImageButton runat="server"
    ImageUrl="btn-normal.png"
    OverImageUrl="btn-hover.png"        <!-- 鼠标悬停 -->
    PressedImageUrl="btn-pressed.png"   <!-- 按下 -->
    DisabledImageUrl="btn-disabled.png"> <!-- 禁用 -->
    <DirectEvents>
        <Click OnEvent="Button_Click" />
    </DirectEvents>
</ext:ImageButton>
```

| 属性 | 作用 |
|------|------|
| `ImageUrl` | 默认状态图 |
| `OverImageUrl` | 悬停状态图 |
| `PressedImageUrl` | 按下状态图 |
| `DisabledImageUrl` | 禁用状态图 |

也支持 `EnableToggle`、`ToggleGroup`、`Menu` 等常规按钮特性。

### 3.5 SegmentedButton（分段/切换按钮组）

容器型控件，子按钮自动形成切换组：

```aspx
<!-- 1) 单选切换组（默认行为，Pressed 指定默认选中） -->
<ext:SegmentedButton runat="server">
    <Items>
        <ext:Button runat="server" Text="视图" />
        <ext:Button runat="server" Text="编辑" Pressed="true" />
        <ext:Button runat="server" Text="拆分" />
    </Items>
</ext:SegmentedButton>

<!-- 2) 多选：AllowMultiple + Values 预选（索引逗号分隔） -->
<ext:SegmentedButton runat="server" AllowMultiple="true" Values="0,2">
    <Items>
        <ext:Button runat="server" Text="A" />
        <ext:Button runat="server" Text="B" />
        <ext:Button runat="server" Text="C" />
    </Items>
</ext:SegmentedButton>

<!-- 3) 关闭切换（仅普通按钮排，不可按下） -->
<ext:SegmentedButton runat="server" AllowToggle="false">
    <Items>
        <ext:Button runat="server" Text="A" />
        <ext:Button runat="server" Text="B" />
    </Items>
</ext:SegmentedButton>

<!-- 4) 垂直排列 -->
<ext:SegmentedButton runat="server" Vertical="true">
    <Items>...</Items>
</ext:SegmentedButton>
```

| 属性 | 作用 |
|------|------|
| `AllowToggle` | 是否允许切换（默认 `true`） |
| `AllowMultiple` | 是否允许多选（默认 `false` 单选） |
| `Values="0,2"` | 预选索引（逗号分隔） |
| `Vertical` | 垂直排列 |

---

## 四、ButtonGroup 按钮组（Ribbon 风格）

`ButtonGroup` 是工具栏内的分组容器，必须放 `Toolbar.Items`：

```aspx
<ext:Toolbar runat="server">
    <Items>
        <ext:ButtonGroup runat="server" Title="编辑" Columns="3" HeaderPosition="Bottom">
            <Defaults>
                <ext:Parameter Name="scale" Value="medium" />
                <ext:Parameter Name="iconAlign" Value="top" />
            </Defaults>
            <Items>
                <!-- 大按钮跨 3 行（Ribbon 的主按钮） -->
                <ext:Button runat="server" Text="粘贴" IconCls="paste32"
                    Scale="Large" IconAlign="Top" RowSpan="3" Cls="x-btn-as-arrow" />
                <ext:Button runat="server" Text="复制" IconCls="copy16" />
                <ext:Button runat="server" Text="剪切" IconCls="cut16" />
            </Items>
        </ext:ButtonGroup>
    </Items>
</ext:Toolbar>
```

| 属性 | 作用 |
|------|------|
| `Title` | 组标题 |
| `Columns="3"` | 列数 |
| `HeaderPosition` | 标题位置：`Top`(默认) / `Bottom` |
| 子项 `RowSpan="3"` | 跨多行（做大按钮） |
| `<Defaults>` | 批量设子项默认属性 |

---

## 五、LoadingState 加载状态（防重复提交）

按钮点击 → 立即进入加载状态（禁用 + 显示加载文字）→ 服务端处理完自动恢复。**天然防重复提交**。

**写法 1：自动加载状态（最简）**：

```aspx
<ext:Button runat="server" Text="提交"
    AutoLoadingState="true"
    OnDirectClick="Submit_Click" />
```

**写法 2：自定义加载文字**：

```aspx
<ext:Button runat="server" Text="提交" OnDirectClick="Submit_Click">
    <LoadingState Text="处理中..." />
</ext:Button>
```

```csharp
protected void Submit_Click(object sender, DirectEventArgs e)
{
    System.Threading.Thread.Sleep(2000);  // 模拟耗时
    X.Msg.Notify("完成", "提交成功").Show();
}
```

> 必须配合 DirectEvent（`OnDirectClick`）。点击后按钮自动 disable 并显示加载文字，DirectEvent 返回后自动还原。比手写 `EventMask` + disable/enable 更简洁，是防重复提交的首选方案。

---

## 六、DefaultButton（容器默认按钮，回车触发）

在含输入框的容器（如 FormPanel）上设 `DefaultButton`，该容器内按回车触发指定按钮：

```aspx
<ext:FormPanel runat="server" Title="查询" DefaultButton="SearchBtn" BodyPadding="5">
    <Items>
        <ext:TextField runat="server" FieldLabel="关键字" />
    </Items>
    <Buttons>
        <ext:Button runat="server" Text="重置" />
        <ext:Button runat="server" ID="SearchBtn" Text="查询"
            OnDirectClick="Search_Click" />   <!-- 回车触发此按钮 -->
    </Buttons>
</ext:Panel>
```

`DefaultButton` 接受四种取值：

| 取值 | 含义 |
|------|------|
| （不设） | 默认取 `<Buttons>` 中**最后一个**按钮 |
| `"1"` | 按索引（0 基） |
| `"SearchBtn"` | 按控件 ID |
| `"button[text=查询]"` | 按 ComponentQuery 选择器 |

---

## 七、按钮控件速查

| 控件 | 标签 | 用途 |
|------|------|------|
| Button | `<ext:Button>` | 通用按钮 |
| SplitButton | `<ext:SplitButton>` | 主体与箭头分开点击 |
| CycleButton | `<ext:CycleButton>` | 循环切换菜单项 |
| HyperlinkButton | `<ext:HyperlinkButton>` | 链接样式按钮 |
| Hyperlink | `<ext:Hyperlink>` | 纯超链接 |
| ImageButton | `<ext:ImageButton>` | 图片按钮（4 状态图） |
| ButtonGroup | `<ext:ButtonGroup>` | 工具栏内分组容器 |
| SegmentedButton | `<ext:SegmentedButton>` | 分段切换组 |

**Button 公共属性速查**：`Text`、`Icon`、`IconCls`、`IconAlign`、`Scale`、`Width/Height`、`TextAlign`、`Disabled/Hidden/Pressed/EnableToggle/ToggleGroup`、`Flat`、`Cls`、`Href`、`ArrowAlign`、`RowSpan`、`AutoLoadingState`。

---

## 八、踩坑要点

### 坑1：Classic Toolkit 没有 UI 语义样式

Ext.NET 4.x Classic 的 Button **不支持** `UI="primary/danger/success"`（这是 Modern Toolkit 的写法）。要自定义颜色样式，用 `Cls` + CSS。

### 坑2：OnDirectClick vs DirectEvents.Click

`OnDirectClick` 是简写，等价于 `<DirectEvents><Click OnEvent="...">`。但**只有完整 DirectEvents 形式**才能配 `EventMask`/`ExtraParams`/`Before`/`Success`/`Complete`。需要这些配置时必须用完整形式。

### 坑3：直接 EventMask vs AutoLoadingState

`AutoLoadingState` 比 `EventMask ShowMask="true"` 更适合按钮防重复提交——它直接禁用按钮并改文字，而不是全屏遮罩。两者可共存但通常二选一。

### 坑4：HyperlinkButton 不是真正的链接

`HyperlinkButton` 视觉是链接但本质是按钮，没有 `NavigateUrl` 属性。要真跳转用 `OnClientClick="window.location='url'"` 或 `<ext:Hyperlink Href="url">`。

### 坑5：ImageButton 禁用状态需要 DisabledImageUrl

`ImageButton` 设 `Disabled="true"` 时，如果没有 `DisabledImageUrl`，按钮不会显示禁用图，仍显示默认图，容易误以为没禁用。四个状态图都要准备。

### 坑6：SegmentedButton 默认单选，多选要显式 AllowMultiple

`SegmentedButton` 默认 `AllowMultiple="false"`（单选互斥）。要多选必须显式设 `AllowMultiple="true"`，并用 `Values` 预选（注意 Values 是**索引**不是 ID）。

### 坑7：ButtonGroup 必须在 Toolbar 内

`ButtonGroup` 是为 Ribbon 工具栏设计的容器，**必须放在 `<ext:Toolbar>` 的 Items 内**，独立使用布局会异常。

---

## 九、关联文档

| 文档 | 关系 |
|------|------|
| `extnet-toolbar-menu-guide.md` | 工具栏与菜单（按钮是工具栏核心元素） |
| `button-permission.md` | 按钮权限（Hidden 默认 + PageAction 字典） |
| `extnet-window-guide.md` | 窗口（窗口按钮栏 Buttons） |
| `extnet-page-skeleton.md` | 页面骨架（按钮权限与布局） |
| `extnet-event-mechanisms.md` | 事件机制（DirectEvent/Listener 原理） |
| `extnet-export-i18n-error.md` | 按钮事件与错误处理 |

## 十、参考来源

- 官方示例库：`Examples/Buttons/`（8 个示例）
  - `Basic/Overview/`：C# 动态构造 Button.Config（Scale/IconAlign/TextAlign 全展示）
  - `Basic/Default_Button/`：DefaultButton 四种取值方式
  - `Basic/HyperlinkButton/`：超链接按钮
  - `Basic/ImageButton/`：图片按钮（4 状态图）
  - `Basic/LoadingState/`：加载状态防重复提交
  - `Basic/SegmentedButton/`：分段切换组
  - `Basic/Variations/`：13 种变体最全（Listener/DirectEvent/ToolTip/Toggle/Menu/SplitButton/CycleButton/Flat）
  - `ButtonGroup/Overview/`：ButtonGroup + Ribbon 风格
