---
title: Ext.NET Window 弹窗与 Toast 完整指南
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Window, 弹窗, Modal, Toast, Loader, 编辑窗]
status: active
updated: 2026-08-29
---
# Ext.NET Window 弹窗与 Toast 完整指南

> 本文档从 Ext.NET 4.7.1 官方示例库 `Examples/Window/`（6 个示例）提炼，覆盖弹窗的显示/隐藏、模态、约束、加载远程内容、Toast 提示等。目标是让 AI/开发者读完即可在任意 Ext.NET WebForms 项目复现 Window 用法。
>
> 适用：Ext.NET 4.x + Triton 主题。底层是 ExtJS 的 `Ext.window.Window`。

---

## 一、Window 核心认知

`<ext:Window>` 是浮动面板，用于弹窗（对话框、编辑窗、确认窗、向导）。它本质是 `Panel` 的子类，**继承了 Panel 的所有特性**（标题栏、工具栏、布局、按钮栏），额外增加：

- 浮动（默认脱离文档流，浮在最上层）
- 可拖拽（`Draggable`）
- 可缩放（`Resizable`）
- 模态遮罩（`Modal`）
- 最大/小化、关闭按钮

### 最小可用示例

```aspx
<ext:Window
    ID="Window1"
    runat="server"
    Title="编辑信息"
    Icon="ApplicationEdit"
    Width="500"
    Height="350"
    Hidden="true"
    Modal="true"
    BodyPadding="10">
    <Items>
        <!-- 窗口内容控件 -->
    </Items>
</ext:Window>
```

> **关键约定**：实际项目中 Window 几乎总是 `Hidden="true"`（页面加载时隐藏），由按钮事件触发 `.show()` 显示。

---

## 二、核心属性速查

### 显示与位置

| 属性 | 作用 | 常用值 |
|------|------|--------|
| `Hidden="true"` | 初始隐藏（必设，否则页面加载就弹出） | `true` |
| `Modal="true"` | 模态遮罩（灰背景，禁止点击外部） | `true` |
| `X` / `Y` | 初始位置（像素坐标） | `250` / `100` |
| `CenterOnLoad` / `Center()` | 居中显示 | — |
| `Constrain="true"` | 约束在父容器范围内拖动 | `true` |
| `ConstrainHeader="true"` | 仅约束标题栏不超出（窗口主体可溢出） | `true` |

### 尺寸与外观

| 属性 | 作用 |
|------|------|
| `Width` / `Height` | 宽高（px） |
| `MinWidth` / `MaxWidth` | 最小/最大宽（配合 Resizable） |
| `BodyPadding="10"` | 内容区内边距 |
| `BodyStyle="background:#fff;"` | 内容区样式 |
| `Plain="true"` | 朴素样式（无内边框/背景透明感） |
| `HeaderPosition` | 标题栏位置：`Top`(默认)/`Bottom`/`Left`/`Right` |

### 标题栏按钮

| 属性 | 作用 | 默认 |
|------|------|------|
| `Closable` | 显示关闭按钮(×) | `true` |
| `Collapsible` | 显示折叠按钮 | `false` |
| `Maximizable` | 显示最大化按钮 | `false` |
| `Minimizable` | 显示最小化按钮 | `false` |
| `Resizable` | 允许拖拽缩放 | `true` |
| `Draggable` | 允许拖拽移动 | `true` |

---

## 三、显示 / 隐藏的多种方式

这是 Window 最重要的操作，有**客户端**和**服务端**两条路径。

### 客户端 JS（推荐，无回发，最快）

```javascript
// 显示
App.Window1.show();            // 简单显示
App.Window1.show(triggerEl);   // 显示并锚定到触发元素（动画从该元素展开）

// 隐藏
App.Window1.hide();
```

按钮触发（Listener）：

```aspx
<ext:Button runat="server" Text="打开">
    <Listeners>
        <Click Handler="App.Window1.show();" />
    </Listeners>
</ext:Button>
```

按钮触发（OnClientClick，最简）：

```aspx
<ext:Button runat="server" Text="打开" OnClientClick="App.Window1.show();" />
```

### 服务端 C#（需回发，适合需要先准备数据的场景）

```csharp
// 显示
protected void OpenWindow(object sender, DirectEventArgs e)
{
    // 先准备数据...
    this.Window1.Show();
}

// 隐藏
this.Window1.Hide();
```

```aspx
<ext:Button runat="server" Text="打开" OnDirectClick="OpenWindow" />
```

### 关闭 vs 隐藏（重要区别）

Window 有两种"消失"行为，取决于 `CloseAction`：

| `CloseAction` | 行为 | 典型场景 |
|--------------|------|---------|
| `Hide`（默认） | 隐藏，DOM 保留，可再 show | **编辑窗**（反复打开关闭，保留状态） |
| `Destroy` | 销毁，DOM 移除 | 一次性窗（每次新建） |

> **实际项目几乎都用 `CloseAction="Hide"`**（默认即可），配合 `.show()`/`.hide()` 复用窗口。如果用 Destroy，每次 show 前需重新创建。

### ASP.NET 原生按钮触发

```aspx
<asp:Button runat="server" Text="打开"
    OnClientClick="App.Window1.show();return false;" />
```

> 注意 `return false;` 阻止 ASP.NET Button 的回发。Ext.NET Button 默认不回发，无需此处理。

---

## 四、模态遮罩 Modal

```aspx
<ext:Window runat="server" Modal="true" ...>
```

- `Modal="true"`：弹出时背后出现半透明灰色遮罩，**阻止用户点击页面其他区域**
- 强制用户先处理弹窗（如确认对话框、必填表单）

**典型编辑窗完整配置**：

```aspx
<ext:Window
    ID="WinEdit"
    runat="server"
    Title="编辑"
    Width="600"
    Height="400"
    Hidden="true"
    Modal="true"
    Closable="true"
    CloseAction="Hide"
    BodyPadding="15"
    Layout="FitLayout">
    <Items>
        <ext:FormPanel runat="server" BodyPadding="10">
            <Items>
                <ext:TextField runat="server" FieldLabel="名称" AllowBlank="false" />
                <ext:TextArea runat="server" FieldLabel="备注" />
            </Items>
            <Buttons>
                <ext:Button runat="server" Text="保存" Icon="Disk" OnDirectClick="Save" />
                <ext:Button runat="server" Text="取消" OnClientClick="App.WinEdit.hide();" />
            </Buttons>
        </ext:FormPanel>
    </Items>
</ext:Window>
```

---

## 五、窗口事件 Listeners / DirectEvents

```aspx
<ext:Window runat="server" Hidden="true">
    <Listeners>
        <Show Handler="console.log('打开了');" />
        <Hide Handler="console.log('隐藏了');" />
        <BeforeClose Handler="return confirm('确认关闭？');" />
    </Listeners>
    <DirectEvents>
        <Show OnEvent="WindowShow" />   <!-- 服务端事件 -->
    </DirectEvents>
</ext:Window>
```

| 事件 | 触发时机 |
|------|---------|
| `Show` | 窗口显示后 |
| `Hide` | 窗口隐藏后 |
| `BeforeShow` | 显示前（return false 可取消） |
| `BeforeClose` | 关闭前（return false 可取消，常做"未保存确认"） |
| `Close` | 关闭后 |
| `Resize` | 缩放后 |
| `Maximize` / `Minimize` | 最大化/最小化 |

**服务端打开后加载数据的常见模式**：

```aspx
<ext:Window runat="server" Hidden="true" Modal="true">
    <DirectEvents>
        <Show OnEvent="LoadEditData" Before="return #{HiddenId}.getValue() != '';">
            <ExtraParams>
                <ext:Parameter Name="id" Value="App.HiddenId.getValue()" Mode="Raw" />
            </ExtraParams>
        </Show>
    </DirectEvents>
</ext:Window>
```

---

## 六、加载远程内容（Loader）

让窗口内容来自另一个页面/URL，无需手写内容。

### 方式 A：声明式 Loader（加载 iframe）

```aspx
<ext:Window
    ID="Window1"
    runat="server"
    Title="详情"
    Width="800"
    Height="600"
    Hidden="true"
    Modal="true">
    <Loader
        Url="~/DetailPage.aspx"
        Mode="Frame"
        AutoLoad="false"
        LoadMask-ShowMask="true" />
</ext:Window>
```

- `Mode="Frame"`：用 iframe 加载（完整页面，最稳）
- `Mode="Component"`：加载 Ext.NET 组件片段
- `Mode="Html"`：加载 HTML 片段
- `AutoLoad="false"`：不自动加载，需手动 `.load()` 触发

**带参数动态加载**：

```javascript
App.Window1.load({
    url: 'DetailPage.aspx',
    params: { id: recordId },
    mode: 'frame'
});
```

### 方式 B：服务端动态创建窗口 + Loader

```csharp
protected void Page_Load(object sender, EventArgs e)
{
    Window win = new Window
    {
        ID = "Window1",
        Title = "外部页面",
        Width = Unit.Pixel(1000),
        Height = Unit.Pixel(600),
        Modal = true,
        Hidden = true,
        Collapsible = true,
        Maximizable = true,
        Loader = new ComponentLoader
        {
            Url = "http://example.com",
            Mode = LoadMode.Frame,
            LoadMask = { ShowMask = true }
        }
    };
    this.Form.Controls.Add(win);
}
```

### 方式 C：服务端设置 Loader URL 后显示

```csharp
protected void OpenWithUrl(object sender, DirectEventArgs e)
{
    string id = e.ExtraParams["id"];
    this.Window1.Loader.Url = "~/Detail.aspx?id=" + id;
    this.Window1.Loader.Reload();  // 重新加载
    this.Window1.Show();
}
```

---

## 七、约束与嵌套窗口

### 约束在容器内（Constrain）

```aspx
<ext:Window runat="server" Constrain="true" ...>
```

- `Constrain="true"`：窗口拖动时**整体**不超出指定边界
- `ConstrainHeader="true"`：仅**标题栏**不超出（窗口主体可部分移出边界，更宽松）

### 嵌套窗口（子窗口跟随父窗口层级）

Window 可作为另一 Window 的 Items 子元素。子窗口的 z-index 相对父窗口管理，父窗口被遮挡时子窗口一起遮挡：

```aspx
<ext:Window runat="server" Title="父窗口" Width="400" Height="200">
    <Items>
        <ext:Window runat="server" Title="子窗口" Width="200" Height="100"
            Constrain="true" />
    </Items>
</ext:Window>
```

> MES 项目中"主表→明细→明细的明细"三层弹窗可用此模式，避免子窗口乱飞。

---

## 八、标题栏位置 HeaderPosition

默认标题栏在顶部，可改到其他边（少见但有需求）：

```aspx
<ext:Window runat="server" HeaderPosition="Left" ... />   <!-- 左侧竖标题 -->
<ext:Window runat="server" HeaderPosition="Bottom" ... /> <!-- 底部 -->
<ext:Window runat="server" HeaderPosition="Right" ... />  <!-- 右侧 -->
```

---

## 九、按钮栏 Buttons

Window 底部按钮栏（保存/取消最常见）：

```aspx
<ext:Window runat="server" ...>
    <Buttons>
        <ext:Button runat="server" Text="保存" Icon="Disk" OnDirectClick="SaveData">
            <Listeners>
                <Click Handler="if (!#{FormPanel1}.getForm().isValid()) { return false; }" />
            </Listeners>
        </ext:Button>
        <ext:Button runat="server" Text="取消" OnClientClick="#{Window1}.hide();" />
    </Buttons>
</ext:Window>
```

> 约定：**取消按钮用客户端 `hide()`**（无回发，快），**保存按钮用 DirectEvent**（需提交数据）。

---

## 十、Toast 轻提示

Toast 是短暂浮动提示（类似 Android Toast），非阻塞，自动消失。适合"保存成功""操作完成"等反馈。

### 客户端（最简）

```javascript
Ext.toast('操作成功');                    // 最简
Ext.toast('保存成功', '提示');            // 带标题
Ext.toast({ html: '内容', title: '标题', align: 'tr' });  // 配置对象
```

### 服务端 C#

```csharp
X.Toast("保存成功");                                        // 最简
X.Toast("操作完成", "提示", ToastAlign.Bottom);            // 带位置
X.Toast(new { html = "数据已更新", title = "成功", align = "tr", autoCloseDelay = 3000 });  // 配置对象
X.Toast(new Toast { Title = "成功", Html = "完成", Align = ToastAlign.Right });  // Toast 对象
```

### Toast 配置属性

| 属性 | 作用 | 默认 |
|------|------|------|
| `align` / `Align` | 位置：`tr`(右上)/`tl`(左上)/`br`(右下)/`bl`(左下)/`t`/`b`/`l`/`r`/`c`(居中) | `br` |
| `autoClose` / `AutoClose` | 自动关闭 | `true` |
| `autoCloseDelay` / `AutoCloseDelay` | 自动关闭延迟(ms) | `2500` |
| `stickWhileHover` / `StickWhileHover` | 鼠标悬停时保持显示 | `true` |
| `closeOnMouseDown` / `CloseOnMouseDown` | 鼠标按下即关闭 | `false` |
| `anchor` / `Anchor` | 锚定到某元素 ID（贴着该元素显示） | — |
| `title` / `Title` | 标题 | — |
| `html` / `Html` | 内容 HTML | — |
| `width` / `Width` | 宽度 | `null` |

### 声明式 Toast（页面加载即显示）

```aspx
<ext:Toast runat="server" Title="欢迎" Html="页面已加载" Align="tr" />
```

### ToastAlign 枚举（服务端）

| 枚举值 | 对应位置 |
|--------|---------|
| `Top` (`t`) | 顶部居中 |
| `Bottom` (`b`) | 底部居中 |
| `Left` (`l`) | 左侧居中 |
| `Right` (`r`) | 右侧居中 |
| `TopRight` (`tr`) | 右上（最常用） |
| `TopLeft` (`tl`) | 左上 |
| `BottomRight` (`br`) | 右下（默认） |
| `BottomLeft` (`bl`) | 左下 |
| `Center` (`c`) | 正中 |

---

## 十一、踩坑要点

### 坑1：忘设 Hidden="true"，页面加载就弹出

```aspx
<!-- ❌ 页面打开就有个窗口飘在那 -->
<ext:Window runat="server" Title="编辑" />

<!-- ✅ 默认隐藏 -->
<ext:Window runat="server" Title="编辑" Hidden="true" />
```

### 坑2：服务端 .Show() 不生效——AutoRender

动态创建的 Window 要设 `AutoRender="false"` 并在适当时机 `Render()`，否则 `.Show()` 找不到控件：

```csharp
Window win = new Window { ID = "W1", AutoRender = false, Hidden = true };
this.Form.Controls.Add(win);
win.Render();  // 显式渲染
win.Show();
```

声明式（写在 aspx 里）的 Window 无此问题。

### 坑3：Modal 窗口内控件延迟渲染

`Hidden="true"` 的窗口内部控件是**懒渲染**的，窗口首次 `show()` 前内部控件可能未创建。在窗口内做 `AfterRender` 初始化（如 FileUploadField 设 multiple）会失败——改用窗口的 `<Show>` 事件。详见 `multi-file-upload-pitfalls.md`。

### 坑4：编辑窗复用——打开前要清空旧数据

`CloseAction="Hide"` 的窗口反复打开会**残留上次数据**。每次 show 前要重置表单：

```javascript
// 客户端重置
App.FormPanel1.getForm().reset();
// 或服务端
this.FormPanel1.Reset();
```

### 坑5：Loader 加载 iframe 页面的 Session/Cookie 问题

`Mode="Frame"` 是 iframe，与父页面同源时共享 Session；跨域加载外部网站受 X-Frame-Options 限制，可能加载空白。

### 坑6：窗口内控件的客户端引用

窗口内控件同样通过 `App.控件ID` 访问，但窗口 `Hidden` 时控件可能未渲染。用 `App.Window1.show(function(){ /* 窗口渲染后的回调 */ })` 确保内部控件就绪。

### 坑7：BeforeClose 的 return false 阻止关闭

```aspx
<BeforeClose Handler="return confirm('有未保存修改，确认关闭？');" />
```

`confirm` 返回 `false` 时关闭被取消——但 Ext.NET 的 confirm 是异步的，需用 Ext.Msg.confirm 回调模式，不能直接 return。正确做法见 `extnet-export-i18n-error.md` 的错误处理模式。

---

## 十二、窗口操作速查

| 操作 | 客户端 JS | 服务端 C# |
|------|----------|----------|
| 显示 | `App.W1.show()` | `this.W1.Show()` |
| 隐藏 | `App.W1.hide()` | `this.W1.Hide()` |
| 关闭(销毁) | `App.W1.close()` | `this.W1.Close()` |
| 居中 | `App.W1.center()` | `this.W1.Center()` |
| 最大化 | `App.W1.maximize()` | `this.W1.Maximize()` |
| 最小化 | `App.W1.minimize()` | `this.W1.Minimize()` |
| 折叠 | `App.W1.collapse()` | `this.W1.Collapse()` |
| 重置位置 | `App.W1.toFront()` | `this.W1.ToFront()` |

---

## 十三、关联文档

| 文档 | 关系 |
|------|------|
| `extnet-page-skeleton.md` | 页面骨架（编辑窗是 CRUD 页核心组件） |
| `main-crud-page-pattern.md` | CRUD 页模式（编辑窗标准用法） |
| `multi-file-upload-pitfalls.md` | Hidden Window 内控件延迟渲染的坑 |
| `extnet-tooltip-in-hidden-window.md` | Hidden Window 内 Tooltip 失效 |
| `extnet-export-i18n-error.md` | 错误提示（Toast/Msg 用法） |
| `extnet-buttons-guide.md` | 按钮控件（窗口内按钮栏） |
| `extnet-form-validation-complete.md` | 表单校验（编辑窗内表单） |

## 十四、参考来源

- 官方示例库：`Examples/Window/`（6 个示例）
  - `Basic/Hello_World/`：最小弹窗 + 客户端/服务端 show
  - `Basic/Show/`：6 种触发 show 的方式（PostBack/Listener/DirectEvent/ASP.NET Button）
  - `Basic/Window_Variations/`：约束、嵌套、HeaderPosition
  - `Basic/Load_External_Website/`：Loader 加载外部页面（动态创建窗口）
  - `Toast/Overview/`：Toast 客户端/服务端各种用法
  - `Toast/Playground/`：Toast 配置演练
