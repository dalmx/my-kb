---
title: Ext.NET Editor 行内编辑与 Loaders 组件加载完整指南
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Editor, 行内编辑, HtmlEditor, 富文本, Loaders, ComponentLoader, DirectMethod, HttpHandler, WebService, 懒加载]
status: active
updated: 2026-08-29
---
# Ext.NET Editor 行内编辑与 Loaders 组件加载完整指南

> 本文档从 Ext.NET 4.7.1 官方示例库 `Examples/Editor/`（2 示例）+ `Examples/Loaders/`（4 示例）提炼。覆盖行内编辑器、富文本编辑器、组件懒加载。目标是让 AI/开发者读完即可在任意 Ext.NET WebForms 项目复现。
>
> 适用：Ext.NET 4.x + Triton 主题。

---

# 第一部分：Editor 行内编辑器

## 一、Editor 核心认知

`<ext:Editor>` 是**包装器**：本身不含输入控件，通过 `<Field>` 嵌入表单字段（TextField/TextArea/ComboBox/HtmlEditor），点击/双击目标元素时弹出该字段编辑。

> ⚠️ **重要**：`ext:Editor`（行内编辑包装器）≠ `ext:HtmlEditor`（独立富文本控件）。

### 最小用法（绑定到 Label）

```aspx
<ext:Label ID="Label1" runat="server" Text="点击编辑" Cls="editable">
    <Editor>
        <ext:Editor runat="server" Shadow="false" Alignment="tl-tl?">
            <Field>
                <ext:TextField runat="server" Width="300" />
            </Field>
        </ext:Editor>
    </Editor>
</ext:Label>
```

## 二、Editor 核心属性

| 属性 | 作用 | 常用值 |
|------|------|--------|
| `Alignment` | 对齐方式 | `tl-tl?`（左上对左上）/ `l-l`（左对左） |
| `ActivateEvent` | 触发事件 | `click`(默认) / `dblclick` |
| `UpdateEl` | 完成后回写到目标 DOM | `true`(默认) / `false`(Ajax 模式) |
| `Shadow` | 阴影 | `false` |
| `AutoSize` | 自动尺寸 | `true` |
| `AllowBlur` | 允许失焦完成 | `false`（强制点 Save） |
| `IgnoreNoChange` | 值未变也算完成 | `true` |
| `Target` | 外部目标控件 ID | 非 Label 元素时用 |
| `UseHtml` | 值当 HTML 处理 | `true` |
| `HtmlDecode` | 取值时 HTML 解码 | `true` |

精细对齐/尺寸配置：

```aspx
<ext:Editor runat="server" AutoSize="true">
    <AutoSizeConfig Width="BoundEl" Height="BoundEl" />
    <AlignmentConfig ElementAnchor="TopLeft" TargetAnchor="BottomLeft" />
</ext:Editor>
```

## 三、Editor 事件

| 事件 | 参数 | 用途 |
|------|------|------|
| `StartEdit` | editor | 编辑开始（如调高度） |
| `BeforeComplete` | (editor, value, startValue) | return false 阻止完成 |
| `Complete` | (editor, value, startValue) | 完成时触发 |

## 四、客户端 API

```javascript
App.Editor1.startEdit(element);     // 在指定元素上启动编辑
App.Editor1.completeEdit();         // 提交（触发 Complete）
App.Editor1.cancelEdit();           // 取消
App.Editor1.setValue(v);            // 读写值
App.Editor1.getValue();
App.Editor1.retarget(elements);     // 重新指定目标（一个 Editor 服务多个元素）
```

## 五、Ajax 提交模式（UpdateEl="false"）

阻止直接改 DOM，改用 DirectEvent 把新值回传服务端：

```aspx
<ext:Editor runat="server" UpdateEl="false" Alignment="tl-tl?">
    <AutoSizeConfig Width="BoundEl" />
    <Field><ext:TextField runat="server" /></Field>
    <DirectEvents>
        <Complete OnEvent="CompleteEdit">
            <ExtraParams>
                <ext:Parameter Name="value" Value="value" Mode="Raw" />
            </ExtraParams>
        </Complete>
    </DirectEvents>
</ext:Editor>
```

```csharp
protected void CompleteEdit(object sender, DirectEventArgs e)
{
    string newValue = e.ExtraParams["value"];
    // 保存到数据库...
}
```

## 六、共享 Editor（delegate 选择器）

页面级放一个 Editor，通过 delegate 让多个元素共用：

```aspx
<ext:Editor ID="Editor1" runat="server" Shadow="false" Offsets="0,5" Alignment="l-l">
    <Field><ext:TextField runat="server" Width="95" /></Field>
</ext:Editor>

<ext:FormPanel runat="server">
    <Listeners>
        <AfterRender Handler="
            this.body.on('dblclick', function(e, t){
                App.Editor1.startEdit(t);
            }, null, {delegate: 'label.x-form-item-label'});" />
    </Listeners>
</ext:FormPanel>
```

---

# 第二部分：HtmlEditor 富文本控件

## 七、基本声明

```aspx
<ext:HtmlEditor ID="HtmlEditor1" runat="server"
    Height="300" Width="600"
    EnableColors="true"
    EnableFont="true"
    EnableFontSize="true"
    EnableFormat="true"
    EnableAlignments="true"
    EnableLists="true"
    EnableLinks="true"
    EnableSourceEdit="true" />
```

## 八、工具栏开关属性

| 属性 | 控制的按钮 |
|------|-----------|
| `EnableColors` | 前景色/背景色 |
| `EnableFont` | 字体下拉 |
| `EnableFontSize` | 字号下拉 |
| `EnableFormat` | 加粗/斜体/下划线 |
| `EnableAlignments` | 左/中/右对齐 |
| `EnableLists` | 项目符号/编号列表 |
| `EnableLinks` | 插入超链接 |
| `EnableSourceEdit` | 源码编辑切换 |

任一设为 `false` 即隐藏对应按钮。

## 九、取值/赋值

- **服务端**：`Text` 属性（HTML 字符串）
- **客户端**：`getValue()` / `setValue(html)`

```javascript
var html = App.HtmlEditor1.getValue();
App.HtmlEditor1.setValue("<p>新内容</p>");
```

## 十、在 FormPanel 中提交

```aspx
<ext:FormPanel ID="fp" runat="server">
    <Items>
        <ext:TextField runat="server" FieldLabel="标题" Name="Title" />
        <ext:HtmlEditor runat="server" FieldLabel="正文" Name="Body" Height="300" />
    </Items>
    <Buttons>
        <ext:Button runat="server" Text="保存" OnDirectClick="Save" />
    </Buttons>
</ext:FormPanel>
```

```csharp
protected void Save(object sender, DirectEventArgs e)
{
    string title = this.Request["Title"];
    string body = this.Request["Body"];   // HtmlEditor 的 HTML 内容
}
```

---

# 第三部分：Loaders 组件加载

## 十一、ComponentLoader 的 Mode

| Mode | 含义 | 服务端返回 |
|------|------|-----------|
| `Component` | 加载 Ext.NET 组件插入容器 | 组件配置 JSON（`ComponentLoader.ToConfig`） |
| `Data` | 加载数据配合 `<Tpl>` 渲染 | JSON 对象数组 |
| `Frame` | iframe 加载完整页面 | HTML 页面 |
| `Html` | 返回内容当 HTML 塞入 | HTML 字符串 |
| `Script` | 加载执行脚本 | JS |

## 十二、Loader 关键属性

| 属性 | 作用 | 默认 |
|------|------|------|
| `Url` | 加载地址（ashx/asmx） | — |
| `DirectMethod` | 用页面 DirectMethod 加载（与 Url 二选一） | — |
| `Mode` | 见上表 | `Html` |
| `AutoLoad` | 页面加载后自动请求 | `true` |
| `RemoveAll` | 加载前清空原 items | `true` |
| `LoadMask.ShowMask` | 加载遮罩 | — |
| `Params` | 附加请求参数 | — |
| `AjaxOptions.Json` | WebService 时设 `true` | `false` |

## 十三、三种加载源

### 方式 1：DirectMethod（页面内 C# 方法）

```aspx
<ext:Panel runat="server" Title="加载组件" Layout="AccordionLayout">
    <Loader runat="server" DirectMethod="#{DirectMethods}.Items" Mode="Component">
        <LoadMask ShowMask="true" />
    </Loader>
</ext:Panel>
```

```csharp
[DirectMethod]
public string Items()
{
    return ComponentLoader.ToConfig(new List<AbstractComponent> {
        new Panel { Title = "项 1", Icon = Icon.UserBrown },
        new Panel { Title = "项 2", Icon = Icon.UserGray }
    });
}

// 加载 UserControl
[DirectMethod]
public static string UserControl()
{
    return ComponentLoader.ToConfig("~/Controls/Items.ascx");
}

// 带参数
[DirectMethod]
public static string AddTab(string parameters)
{
    var prms = JSON.Deserialize<Dictionary<string, string>>(parameters);
    return ComponentLoader.ToConfig(new Panel {
        Title = prms["name"],
        Html = "服务器时间：" + DateTime.Now.ToLongTimeString()
    });
}
```

带参 + 手动触发 + 增量加 Tab：

```aspx
<ext:TabPanel runat="server">
    <Loader runat="server" AutoLoad="false" RemoveAll="false"
        DirectMethod="#{DirectMethods}.AddTab" Mode="Component">
        <Params>
            <ext:Parameter Name="name" Value="Ext.Date.format(new Date(),'h:i:s')" Mode="Raw" />
        </Params>
    </Loader>
    <Buttons>
        <ext:Button runat="server" Text="加 Tab">
            <Listeners>
                <Click Handler="this.up('panel').load({callback:function(){
                    this.setActiveTab(this.items.getCount()-1);}, scope:this.up('panel')});" />
            </Listeners>
        </ext:Button>
    </Buttons>
</ext:TabPanel>
```

### 方式 2：HttpHandler（.ashx）

```aspx
<ext:Panel runat="server" Layout="AccordionLayout">
    <Loader runat="server" Url="ComponentHandler.ashx" Mode="Component" />
</ext:Panel>
```

```csharp
public class ComponentHandler : IHttpHandler
{
    public void ProcessRequest(HttpContext context)
    {
        context.Response.ContentType = "application/json";
        // Render 直接输出到 Response（不要 return）
        ComponentLoader.Render(new List<AbstractComponent> {
            new Panel { Title = "项 1" },
            new Panel { Title = "项 2" }
        });
    }
    public bool IsReusable => false;
}
```

### 方式 3：JSON WebService（.asmx）

```aspx
<ext:Panel runat="server" Layout="AccordionLayout">
    <Loader runat="server" Url="ComponentService.asmx/Items" Mode="Component">
        <AjaxOptions Json="true" />   <!-- 必须加 -->
    </Loader>
</ext:Panel>
```

```csharp
[ScriptService]   // 关键：允许 AJAX 调用
public class ComponentService : WebService
{
    [WebMethod]
    public string Items()
    {
        return ComponentLoader.ToConfig(new List<AbstractComponent> {
            new Panel { Title = "项 1" }
        });
    }
}
```

asmx 三要素：类标 `[ScriptService]`、方法标 `[WebMethod]`、返回 string（`ToConfig`）。

## 十四、返回方式速查

| 场景 | DirectMethod | HttpHandler | WebService |
|------|-------------|-------------|------------|
| **组件(Component)** | `return ToConfig(...)` | `ComponentLoader.Render(...)` | `[WebMethod] return ToConfig(...)` |
| **数据(Data)** | `return 集合对象` | `JSON.Serialize` + `GZipAndSend` | `[WebMethod] return 集合` |
| **Html** | 返回 HTML 字符串 | `Response.Write(html)` | 返回 string |
| 客户端配置 | `DirectMethod="#{DirectMethods}.X"` | `Url="X.ashx"` | `Url="X.asmx/M"` + `AjaxOptions Json="true"` |

## 十五、Mode="Data" 数据加载

返回对象数组，由容器 `<Tpl>` 模板渲染：

```aspx
<ext:Panel runat="server" BodyPadding="10">
    <Tpl runat="server">
        <Html>
            <tpl for="."><p>{FirstName} - {LastName}</p></tpl>
        </Html>
    </Tpl>
    <Loader DirectMethod="#{DirectMethods}.GetData" Mode="Data">
        <LoadMask ShowMask="true" />
    </Loader>
</ext:Panel>
```

```csharp
[DirectMethod]
public List<object> GetData(string parameters)
{
    return new List<object> {
        new { FirstName = "张", LastName = "三" },
        new { FirstName = "李", LastName = "四" }
    };
}
```

> Data 模式下 DirectMethod **直接返回集合对象**（框架自动序列化），不用 `ToConfig`。

---

## 十六、踩坑要点

### 坑1：Editor ≠ HtmlEditor

- `ext:Editor`：行内编辑包装器（要嵌 `<Field>`）
- `ext:HtmlEditor`：独立富文本控件
- Overview 示例标题有误导性，主体演示的是 Editor

### 坑2：HtmlEditor 当 Editor 的 Field 要补 getRawValue

把 HtmlEditor 作为 Editor 的 Field 时，必须补一个空实现，否则 Editor 取值报错：

```aspx
<ext:HtmlEditor runat="server">
    <CustomConfig>
        <ext:ConfigItem Name="getRawValue" Value="function(){return '';}" Mode="Raw" />
    </CustomConfig>
</ext:HtmlEditor>
```

且 HtmlEditor 的 iframe/textarea 不自动撑满，要在 `StartEdit` 里手工算高度。

### 坑3：DirectMethod 用 ToConfig(return)，HttpHandler 用 Render(输出)

```csharp
// ✅ DirectMethod：return 字符串
[DirectMethod] public string X() { return ComponentLoader.ToConfig(items); }

// ✅ HttpHandler：直接写 Response（不 return）
public void ProcessRequest(...) { ComponentLoader.Render(items); }

// ❌ 混用会导致数据格式错误
```

### 坑4：asmx 必须配 AjaxOptions Json="true"

WebService 加载不加 `<AjaxOptions Json="true" />`，Loader 不会按 JSON 协议调用，返回错误。

### 坑5：TabPanel 增量加 Tab 要 RemoveAll="false"

```aspx
<Loader RemoveAll="false" ... />   <!-- 否则新加载清掉已有 Tab -->
```

### 坑6：Data 模式返回集合不用 ToConfig

Data 模式的 DirectMethod 直接 `return 集合对象`，再包一层 `ToConfig` 会把数据当组件解析，报错。

### 坑7：#{DirectMethods}.方法名 区分大小写

`#{DirectMethods}` 是页面 DirectMethod 代理 token，方法名必须与 `[DirectMethod]` 方法完全一致（大小写敏感）。

---

## 十七、关联文档

| 文档 | 关系 |
|------|------|
| `extnet-event-mechanisms.md` | 事件机制（DirectMethod 原理） |
| `extnet-directmethod-and-data.md` | DirectMethod 与数据访问 |
| `extnet-window-guide.md` | Window Loader 加载远程内容 |
| `extnet-tabpanel-setactivetab.md` | TabPanel（Loader 增量加 Tab） |
| `extnet-form-extra-widgets.md` | 表单控件（HtmlEditor 详细用法） |

## 十八、参考来源

- 官方示例库：`Examples/Editor/Basic/`（Overview / FormPanel_Labels）
- 官方示例库：`Examples/Loaders/`
  - `Component/Direct_Method/`：DirectMethod 加载组件
  - `Component/Http_Handler/`：HttpHandler 加载
  - `Component/JSON_WebService/`：asmx 加载
  - `Data/Overview/`：Data 模式数据加载
