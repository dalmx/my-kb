---
title: Ext.NET Desktop 桌面进阶开发（菜单树侧栏 + 自定义快捷方式 + 窗口弹窗 + TaskBar 修复）
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, Desktop, 桌面框架, 菜单树, 侧滑面板, 自定义快捷方式, 图标选择器, CreateWindow, TaskBar, 登录模式, 避坑]
status: active
platform: Ext.NET v4.7.1 + Triton 主题 + ASP.NET WebSite (.NET 4.8)
updated: 2026-08-29
---
# Ext.NET Desktop 桌面进阶开发（菜单树侧栏 + 自定义快捷方式 + 窗口弹窗 + TaskBar 修复）

> 本文沉淀 Wongoing.Main.WebSite 的 Desktop.aspx 二期开发经验：右侧菜单树侧栏（鼠标滑入滑出）、用户自定义桌面快捷方式（动态添加/图标选择器/删除/持久化）、菜单点击桌面内弹窗（进任务栏 + 层叠不重叠）、TaskBar 跳动根治、登录页经典/桌面模式切换。
>
> 前置阅读：`extnet-desktop-migration-guide.md`（基础架构/拖拽/壁纸/右键菜单）、`extnet-desktop-framework-guide.md`（模块加载/避坑/看板）。

---

## 一、右侧菜单树侧栏（官方 Slide panel 方案）

### 1.1 不要把 Desktop 放进 BorderLayout

**核心结论**：Ext.NET 官方示例 `Examples/Desktop/Introduction/Overview/Desktop.aspx` 里，`<ext:Desktop>` 始终**顶层独立铺满**（直接挂在 body 下，与 ResourceManager 同级），**没有任何 BorderLayout/Region 包裹**。

- 全仓（官方示例 + Main 项目）无任何"Desktop 嵌套进 BorderLayout"的先例。
- 根因：`Ext.ux.desktop.Desktop` 默认 `renderTo:body`，taskbar 用固定定位，套进 BorderLayout 的受管布局容器会破坏渲染/任务栏定位。

### 1.2 官方右侧栏方案：浮动 Panel + alignTo + MouseDistanceSensor

桌面需要侧边栏时，用**与 Desktop 平级的浮动 Panel**（不是 BorderLayout 子项），参照官方 `Overview/Desktop.aspx` 第 314-333 行的 Slide panel：

```aspx
<!-- 与 <ext:Desktop> 平级（不是它的子项）-->
<ext:Panel ID="winMenu" runat="server" Title="功能菜单"
    Width="230" Floating="true" Shadow="false" Hidden="true" Layout="FitLayout">
    <Items>
        <ext:TreeList ID="menuTreePanel" runat="server" ExpanderOnly="false">
            <Store>
                <ext:TreeStore ID="menuTreeStore" runat="server" OnReadData="GetUserPageGroup">
                    <Root><ext:Node NodeID="Root" Expanded="true" /></Root>
                    <Listeners><BeforeLoad Fn="dtNodeLoad" /></Listeners>
                </ext:TreeStore>
            </Store>
            <Listeners><ItemClick Fn="dtLoadPage" /></Listeners>
        </ext:TreeList>
    </Items>
    <!-- 桌面 ready 后初始化（对齐右边缘）-->
    <MessageBusListeners>
        <ext:MessageBusListener Name="App.Desktop.ready" Fn="initMenuPanel" />
    </MessageBusListeners>
    <!-- 鼠标滑入滑出 -->
    <Plugins>
        <ext:MouseDistanceSensor runat="server" Opacity="false" Threshold="25">
            <Listeners>
                <Near Handler="this.component.el.alignTo(Ext.net.Desktop.desktop.body, 'tr-tr', [0, 0], true);" />
                <Far  Handler="this.component.el.alignTo(Ext.net.Desktop.desktop.body, 'tl-tr', [0, 0], true);" />
            </Listeners>
        </ext:MouseDistanceSensor>
    </Plugins>
</ext:Panel>
```

### 1.3 关键机制

- **对齐目标用 `Ext.net.Desktop.desktop.body`**（已排除任务栏），比手算视口尺寸精确。
- `tr-tr`：面板右上角对齐桌面右上角 → **贴右内侧显示**。
- `tl-tr`：面板左上角对齐桌面右上角 → **整个面板藏到右边缘外**（默认隐藏态）。
- Desktop 的 `<Ready BroadcastOnBus="App.Desktop.ready" />`（**纯广播，不能同时设 Handler**——坑5）触发初始化。
- ResourceManager 的 `WindowResize` 也广播 `App.Desktop.ready`，让侧栏 resize 时重新对齐。

### 1.4 initMenuPanel（仿官方 initSlidePanel）

```js
var initMenuPanel = function () {
    var desk = Ext.net.Desktop && Ext.net.Desktop.desktop;
    if (!desk || !desk.body) { return; }
    this.setHeight(desk.body.getHeight());
    if (!this.windowListen) {
        this.windowListen = true;
        this.show();
        this.el.alignTo(desk.body, 'tl-tr', [0, 0]);   // 初始藏右外
        Ext.on('resize', initMenuPanel, this);
        Ext.defer(initMenuTreeContextMenu, 300);        // 显示后绑右键
    } else {
        this.el.alignTo(desk.body, 'tl-tr', [0, 0]);   // resize 重新对齐
    }
};
```

> ⚠️ `initMenuPanel` 用 `this`（MessageBusListener 在 Panel 作用域执行，this = Panel）。

### 1.5 菜单树数据移植自 MainFrame

- TreeStore 的 `OnReadData="GetUserPageGroup"` 加载一级；`BeforeLoad Fn="dtNodeLoad"` 懒加载子级（调 DirectMethod `NodeLoad`）。
- **不复用 MainFrame 的 `Session["UserPageList"]`**——Desktop 不是 MainFrame 的 iframe 子页，无法保证 MainFrame 已先执行。用独立 key（如 `DtUserMenuLevels`）在 Desktop 的 Page_Load 自行查 `GetUserPageList`。
- `IniTreeNode`（实体→Node）、`GetUserPageGroup`、`NodeLoad` 照搬 MainFrame.aspx.cs，`this.Data.User.UserId` 来自基类。

### 1.6 菜单树节点右键（TreeList 无 ItemContextMenu 事件）

**关键坑**：`Ext.Net.TreeList` 的 Listeners **只有 `ItemClick` 和 `SelectionChange`**，没有 `ItemContextMenu`（那是 `TreePanel` 的）。在 aspx 配 `<ItemContextMenu>` 会报编译错误。

**解法**：用 document 事件委托（捕获阶段）：

```js
document.addEventListener('contextmenu', function (e) {
    var itemEl = Ext.get(e.target).up('.x-treelist-item');
    if (!itemEl) { return; }   // 不在菜单树节点上 → 放行
    e.preventDefault(); e.stopPropagation();
    var info = resolveTreeRecord(tree, e.target);   // DOM 反查 record
    if (!info) { return; }
    // 区分节点类型：父节点直接展开，叶子弹菜单
    if (info.data.leaf !== true) { info.record.expand(); return; }
    showMenuItemContextMenu(tree, info.record, info.data, e);
}, true);
```

- 事件委托绑在 document 上，子节点懒加载展开时自动覆盖（无需重新绑定）。
- `resolveTreeRecord` 从 `.x-treelist-item` 的 `data-recordid` 调 `store.getById` 反查，失败按文本遍历兜底。

---

## 二、用户自定义桌面快捷方式（运行时动态添加）

### 2.1 Ext.NET 没有客户端 addShortcut API

- 官方无客户端 `App.Desktop1.addShortcut(...)`；服务端 `Desktop.AddModule(DesktopModule)` 要回发且会注册 StartMenu/TaskBar（过度设计）。
- **解法**：纯客户端 DOM 方案——按 Ext.NET ShortcutTpl 结构手动创建元素，与原生快捷方式 DOM 完全一致，复用现有拖拽/网格吸附/右键菜单。

### 2.2 addDesktopShortcut 实现

```js
var addDesktopShortcut = function (id, text, iconCls, url, iconUnicode, iconColor) {
    var fullId = id + '-shortcut';
    // ... 去重：已存在则更新文字/图标，不重建
    var sc = document.createElement('div');
    sc.className = 'ux-desktop-shortcut';
    sc.id = fullId;
    sc.appendChild(renderIcon(id, iconUnicode, iconColor));  // 见 2.3
    var textDiv = document.createElement('div');
    textDiv.className = 'ux-desktop-shortcut-text';
    textDiv.innerHTML = text;
    sc.appendChild(textDiv);
    // 挂到现有快捷方式容器（找不到挂桌面 body）
    var container = document.querySelector('.ux-desktop-shortcut')?.parentNode || ...;
    container.appendChild(sc);
    // 初始位置：localStorage 已存 > 自动找空格
    // ... 双击/单击打开、拖拽绑定（bindShortcutBehavior）
    bindShortcutBehavior(sc);   // ← 复用原生拖拽 + 右键
};
```

### 2.3 动态图标用 ::after 伪元素（与原生一致）

原生图标用 `.sc-xxx::after { content:"\f0ce" }`。动态图标同样用 `::after`，但 content 运行时才知道，需**动态注入 CSS 规则**：

```js
var ensureCustIconStyle = function (cls, unicode, color) {
    try {
        // unicode 字符转 CSS 转义形式 \<hex>（关键！直接拼字符会破坏 CSS 解析）
        var hex = unicode.charCodeAt(0).toString(16);
        while (hex.length < 4) hex = '0' + hex;
        var css = '.' + cls + '{background-color:' + color + '}'
                + '.' + cls + '::after{content:"\\' + hex + '"}';
        // 注入/更新 <style id="cust-icon-styles">
    } catch (e) { /* 失败不影响拖拽等核心功能 */ }
};
```

> ⚠️ **必须用 `\<hex>` 转义形式**（如 `\f015`），不能直接把 unicode 字符拼进 `content:""`，某些控制字符会破坏 CSS 解析导致整段样式失效。

### 2.4 持久化（localStorage 列表）

```js
// 列表：sc_cust_<工号> = [{id,text,iconCls,url,iconUnicode,iconColor}, ...]
// 位置：sc_pos_<工号>_<id>-shortcut（与原生同款）
// 自定义名：sc_name_<工号>_<id>-shortcut
// 页面加载时 restoreCustShortcuts() 重建所有自定义图标
```

### 2.5 图标选择器（FontAwesome 自选图标+颜色）

参考 `http://www.wapadd.cn/icons/awesome/index.htm`（FontAwesome 4.x 图标库），内置图标+颜色数据，弹出选择窗口：

```js
var _faIcons = [ {u:'\uf015', n:'首页'}, ... ];  // {unicode, 中文名}
var _faColors = ['#2d6ca2', ...];
var pickIcon = function (callback) {
    // Ext.Window：预览区 + 颜色板 + 图标网格
    // 选中后 callback({ unicode, color })
};
```

- 预览用 `win.el.down('#icpPreview')`（限定当前 win 内查找，避免连续打开匹配到旧 Window 残留）。
- Window `closeAction: 'destroy'`，确定前先捕获 ret 再 destroy 再 callback。
- CSS content 用 `\<hex>` 转义（同 2.3）。

### 2.6 右键自定义图标：打开/重命名/删除

- **打开**：直接调 `sc._custOpen()`（不要用 `sc.click()`，自定义图标的打开逻辑绑在 dblclick + 延迟 click 上，`click()` 不触发）。
- **重命名**：改 textEl.innerHTML + `setCustomScName` + `updateCustShortcutName`（同步 localStorage 列表的 text，否则刷新丢失）。
- **删除**：`removeCustShortcut`（清 DOM + 列表 + 位置 + 名称）。

---

## 三、桌面内弹窗（菜单点击打开，进任务栏）

### 3.1 必须用服务端 CreateWindow（保证任务栏标签）

**客户端 `Ext.create('Ext.window.Window') + desk.addWindow(win)` 不可靠**——窗口可能不进桌面窗口管理器，任务栏无标签。

**正确做法**：服务端 DirectMethod 用 `Desktop.GetInstance().CreateWindow`：

```csharp
[DirectMethod]
public void OpenMenuWindow(string id, string title, string url)
{
    int step = 24;
    int idx = System.Threading.Interlocked.Increment(ref _winCascadeIndex) - 1;
    int offset = (idx % 8) * step;   // 层叠偏移，避免重叠

    Desktop.GetInstance().CreateWindow(new Window
    {
        ID = "menuWin_" + id,
        Title = title,
        Width = Unit.Pixel(1000), Height = Unit.Pixel(620),
        X = 40 + offset, Y = 30 + offset,   // 层叠位置
        Maximizable = true, Minimizable = true,
        CloseAction = CloseAction.Destroy,
        ConstrainHeader = true,
        Layout = "Fit",
        Loader = new ComponentLoader
        {
            Url = url, Mode = LoadMode.Frame,   // iframe 加载
            LoadMask = { ShowMask = true, Msg = "加载 " + title + "..." }
        }
    });
}
```

### 3.2 关键点

- `[DirectMethod]` **不要加 `ShowMask = true`**——会全屏遮罩，看起来像"整体闪一下"。
- `Layout = "Fit"` 是 **string**，不是 `LayoutType.Fit` 枚举（编译错误 CS0029）。
- `Unit.Pixel(...)` 需要 `using System.Web.UI.WebControls;`。
- 客户端去重：`Ext.getCmp('menuWin_' + id)` 已存在则激活，否则调 DirectMethod。
- 打开 url 仿 main.js 的 `loadPage`：`javascript:` 协议 `eval`，普通 url 追加 `isSysMenu=1`。

### 3.3 多窗口层叠不重叠

服务端静态计数器 `_winCascadeIndex`，每个新窗口 `X/Y += 24`，开满 8 个回绕。`ConstrainHeader=true` 防止偏出视口。

---

## 四、TaskBar（任务栏）跳动根治

### 4.1 症状

首次打开窗口时底部任务栏"跳一下"（高度突变），底部有白线。

### 4.2 根因（浏览器实测确认）

Ext.NET Desktop 的 TaskBar **没有内建高度**，完全靠子项内容撑高：

- TaskBar 是水平 Toolbar，items = [StartButton][QuickStart子toolbar][windowbar flex:1][Tray子toolbar]
- **windowbar 空态内层 `.x-box-target` 只有 1px**！加窗口按钮时撑到正常高度 → 跳动。
- QuickStart 空（Width=0）高度塌陷 0px；Tray+TrayClock 只有 16px。
- 官方靠 QuickStart 按钮 + TrayClock 撑住高度，所以不跳。

### 4.3 修复（CSS，不用固定 height 避免与 ExtJS 布局引擎冲突）

```css
/* 所有子 toolbar 统一最小高度 */
.ux-taskbar .x-toolbar, .ux-desktop-windowbar {
    min-height: 30px !important;
    background-image: none !important;
    border: 0 !important;
}
/* 关键：内层 box-target 空态也预留高度（实测空态只有 1px） */
.ux-desktop-windowbar .x-box-target,
.ux-taskbar .x-toolbar .x-box-target {
    min-height: 28px !important;
}
/* 时钟撑到行高 */
.ux-desktop-trayclock {
    line-height: 30px !important;
    min-height: 30px !important;
}
/* 去掉顶部白线（边框）*/
.ux-taskbar { background-color: #2d6ca2 !important; border: none !important; }
```

### 4.4 配合：TrayClock 必须显示撑高度

- TaskBar 配 `TrayWidth="120"`（非零）+ `<TrayClock runat="server" TimeFormat="H:i" />`。
- **不要在 JS 里隐藏 TrayClock**（之前隐藏它导致没东西撑高度）。
- 右下角显示时钟，既实用又撑住 TaskBar 标准高度。

### 4.5 为什么 CSS 固定 height 会失败

`height: 40px !important` 会被 ExtJS 布局引擎用 JS 设内联 style 覆盖，且会产生 1px 间隙（白线）。**用 `min-height` 而非 `height`**，不与布局引擎打架。

---

## 五、登录页经典/桌面模式选择

### 5.1 改 Login.aspx（普通 ASP.NET 控件，非 Ext.NET）

在帐套 DropDownList 行后加模式选择行 + 隐藏域：

```aspx
<tr>
    <th>模 式<br />Mode</th>
    <td class="mode-cell">
        <label class="mode-opt"><input type="radio" name="uiMode" value="classic" checked />经典模式</label>
        <label class="mode-opt"><input type="radio" name="uiMode" value="desktop" />桌面模式</label>
    </td>
</tr>
<!-- 隐藏域接收选中值 -->
<asp:HiddenField ID="hfUiMode" runat="server" Value="classic" />
```

### 5.2 JS 记忆（localStorage）

```js
// window.onload：恢复上次选择
var savedMode = window.localStorage.getItem('wongoingUiMode') || 'classic';
// btnSubmitClientClick：写入隐藏域 + 存 localStorage
document.getElementById('<%= hfUiMode.ClientID %>').value = mode;
window.localStorage.setItem('wongoingUiMode', mode);
```

### 5.3 Login.aspx.cs 跳转分支

```csharp
string uiMode = (this.hfUiMode.Value ?? "classic").Trim().ToLower();
if (uiMode == "desktop") {
    Response.Redirect("Desktop/Desktop.aspx");   // 注意子目录路径
} else {
    Response.Redirect("MainFrame.aspx");
}
```

### 5.4 Desktop.aspx 已自包含，可直接跳转

- Desktop 自己 Page_Load 调 `LoadUserMenuLevels()` 查权限（独立 Session key），不依赖 MainFrame 的 `Session["UserPageList"]`。
- 两个页面都继承 `Wongoing.Web.UI.Page`，登录态校验一致（AuthenticationModule 统一处理）。
- 跳 Desktop 用相对路径 `Desktop/Desktop.aspx`（Desktop 在子目录）。

---

## 六、关键避坑汇总

| # | 问题 | 根因 | 解法 |
|---|---|---|---|
| 1 | Desktop 放进 BorderLayout 后渲染异常 | Ext.ux.desktop.Desktop 默认 renderTo:body + taskbar 固定定位 | 用平级浮动 Panel 做侧栏，官方无嵌套先例 |
| 2 | TreeList 配 `<ItemContextMenu>` 编译报错 | TreeList 只有 ItemClick/SelectionChange | document 事件委托（捕获阶段 contextmenu） |
| 3 | 客户端 addWindow 窗口不进任务栏 | addWindow 不可靠 | 服务端 `Desktop.GetInstance().CreateWindow` |
| 4 | 弹窗"整体闪一下" | `[DirectMethod(ShowMask=true)]` 全屏遮罩 | 去掉 ShowMask |
| 5 | TaskBar 首窗口跳动 | windowbar 内层 .x-box-target 空态仅 1px | CSS min-height 给 box-target 也设 |
| 6 | TaskBar 底部白线 | 子 toolbar 默认 border-top | `.ux-taskbar .x-toolbar { border:0 }` |
| 7 | CSS 固定 TaskBar height 失败 | ExtJS 布局引擎 JS 设内联 style 覆盖 | 用 min-height 不用 height |
| 8 | 自定义图标 ::after content 失效 | 直接拼 unicode 字符破坏 CSS 解析 | 用 `\<hex>` 转义形式 |
| 9 | Node.AppendChild 编译错误 | Ext.Net.Node 无 AppendChild（只有根节点有） | 中间节点用 `Children.Add`，根用 `GetRootNode().AppendChild` |
| 10 | Layout=LayoutType.Fit 编译错误 | Window.Layout 是 string | `Layout = "Fit"` |
| 11 | JS `_faIcons` 写 `'\xf1c0'` 异常 | `\x` 只接受2位hex | 统一 `\ufxxx` |
| 12 | 图标选择器连续打开预览不刷新 | `Ext.get('icpPreview')` 全局匹配到旧 Window | `win.el.down('#icpPreview')` 限当前 win |
| 13 | 搜索菜单深层命中显示不出 | 只加载一级再过滤 | 查命中+祖先 menu_level，递归组装完整树 |
| 14 | TreeList 右键弹不出菜单 | 绑定时 Panel 还没 show（浮动 Hidden） | 绑定放 initMenuPanel 的 show 之后 |
| 15 | 自定义图标拖不动 | initShortcutDrag 因无图标提前 return，全局监听未注册 | 全局监听无条件注册，初始图标绑定改可选 |

---

## 七、关联文档

| 文档 | 关系 |
|------|------|
| `extnet-desktop-migration-guide.md` | 基础架构/拖拽/网格吸附/壁纸/右键菜单（一期） |
| `extnet-desktop-framework-guide.md` | 模块加载/避坑/看板/TableLayout |
| `extnet-tree-guide.md` | TreePanel/TreeList 树控件（菜单树数据加载） |
| `extnet-page-skeleton.md` | BorderLayout/Viewport（MainFrame 经典模式骨架） |
| `extnet-event-mechanisms.md` | DirectMethod/Listeners/MessageBus |

---

## 八、关键代码位置索引（Wongoing.Main.WebSite Desktop.aspx）

| 功能 | 函数/位置 | 说明 |
|------|----------|------|
| 菜单侧栏初始化 | `initMenuPanel` | 仿官方 initSlidePanel，对齐桌面右边缘 |
| 菜单树懒加载 | `dtNodeLoad` | 调 DirectMethod NodeLoad |
| 菜单点击打开 | `dtLoadPage` | 仿 main.js loadPage，isSysMenu + eval |
| 菜单树右键 | `initMenuTreeContextMenu` | document 事件委托，父节点展开/叶子弹菜单 |
| 菜单搜索 | `filterMenu` + `MenuFilter`(cs) | 命中+祖先链递归组装 |
| 自定义图标创建 | `addDesktopShortcut` | DOM 方式，::after 伪元素图标 |
| 图标样式注入 | `ensureCustIconStyle` | 动态 CSS，content 用 \<hex> 转义 |
| 图标选择器 | `pickIcon` + `_faIcons`/`_faColors` | FontAwesome 图标+颜色自选 |
| 拖拽单元素绑定 | `bindShortcutBehavior` | 初始+动态图标共用 |
| 排列图标 | `arrangeAllShortcuts` | 列优先网格重排 |
| 窗口弹窗(cs) | `OpenMenuWindow` | Desktop.GetInstance().CreateWindow |
| TaskBar 修复 | desktop.css min-height | box-target 空态预留高度 |
| 登录模式 | Login.aspx + Login.aspx.cs | 经典/桌面 radio + 跳转分支 |
