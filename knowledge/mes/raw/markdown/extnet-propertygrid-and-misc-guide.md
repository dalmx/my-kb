---
title: Ext.NET PropertyGrid / Portal / TaskManager / MessageBus / Associations / MultiUpload 完整指南
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [PropertyGrid, 属性表, Portal, 门户, TaskManager, MessageBus, 消息总线, Associations, HasMany, HasOne, MultiUpload]
status: active
updated: 2026-08-29
---
# Ext.NET PropertyGrid / Portal / TaskManager / MessageBus / Associations / MultiUpload 完整指南

> 本文档从 Ext.NET 4.7.1 官方示例库提炼，覆盖属性表、门户布局、任务管理器、消息总线、模型关联、多文件上传。目标是让 AI/开发者读完即可复现。
>
> 适用：Ext.NET 4.x + Triton 主题。

---

## 一、PropertyGrid 属性表

`<ext:PropertyGrid>` 是带"名-值"两列、每行内嵌编辑器的特殊 GridPanel，适合做配置编辑界面。

### 1.1 基础用法

```aspx
<ext:PropertyGrid ID="pg1" runat="server" Width="300" SortableColumns="false">
    <Source>
        <!-- 字符串 -->
        <ext:PropertyGridParameter Name="(name)" Value="配置项" />
        <!-- 布尔值（必须 Mode="Raw"） -->
        <ext:PropertyGridParameter Name="enabled" Value="false" Mode="Raw" />
        <!-- 内置数字编辑器 -->
        <ext:PropertyGridParameter Name="count" Value="10" EditorType="Number" />
    </Source>
</ext:PropertyGrid>
```

### 1.2 自定义编辑器

```aspx
<ext:PropertyGridParameter Name="color" Value="Red">
    <Editor>
        <ext:ComboBox runat="server" ForceSelection="true">
            <Items>
                <ext:ListItem Text="Red" />
                <ext:ListItem Text="Green" />
                <ext:ListItem Text="Blue" />
            </Items>
        </ext:ComboBox>
    </Editor>
</ext:PropertyGridParameter>

<!-- 日期编辑器 -->
<ext:PropertyGridParameter Name="date" Value="2026-01-01">
    <Editor><ext:DateField runat="server" Format="yyyy-MM-dd" /></Editor>
</ext:PropertyGridParameter>
```

### 1.3 服务端读取/增删

```csharp
// 读取
foreach (PropertyGridParameter p in this.pg1.Source)
{
    var name = p.Name;
    var value = p.Value;
}

// 按名取
string val = this.pg1.Source["count"].Value;

// 动态增删
this.pg1.AddProperty(new PropertyGridParameter { Name = "newProp", Value = "1" });
this.pg1.RemoveProperty("newProp");
```

| 要素 | 作用 |
|------|------|
| `Mode="Raw"` | 值按 JS 字面量解析（布尔/数字），否则当字符串 |
| `EditorType="Number"` | 内置数字编辑器 |
| `<Editor>` | 自定义编辑器控件 |
| `DisplayName` | 显示名（默认同 Name） |

---

## 二、Portal 门户布局

`<ext:Portal>` 是看板/仪表盘布局，小面板可在列间拖拽。

### 2.1 三层结构

```aspx
<ext:Portal runat="server" Border="false">
    <Items>
        <ext:PortalColumn runat="server" ColumnWidth=".33">
            <Items>
                <ext:Portlet ID="p1" runat="server" Title="面板1" />
            </Items>
        </ext:PortalColumn>
        <ext:PortalColumn runat="server" ColumnWidth=".33">
            <Items>
                <ext:Portlet ID="p2" runat="server" Title="面板2" />
                <ext:Portlet ID="p3" runat="server" Title="面板3" />
            </Items>
        </ext:PortalColumn>
        <ext:PortalColumn runat="server" ColumnWidth=".34">
            <Items>
                <ext:Portlet ID="p4" runat="server" Title="面板4" />
            </Items>
        </ext:PortalColumn>
    </Items>
</ext:Portal>
```

| 层级 | 控件 | 说明 |
|------|------|------|
| 容器 | `ext:Portal` | 默认 ColumnLayout |
| 列 | `ext:PortalColumn` | `ColumnWidth` 控制宽度占比 |
| 卡片 | `ext:Portlet` | 可拖拽、可关闭的面板 |

> 拖拽列间移动是 Portlet **内置行为**，无需额外配置。

### 2.2 Portlet 高级

```aspx
<ext:Portlet runat="server" Title="内容" CloseAction="Hide" BodyPadding="5">
    <Loader runat="server" Url="~/DetailPage.aspx" Mode="Frame">
        <LoadMask ShowMask="true" />
    </Loader>
</ext:Portlet>
```

`CloseAction="Hide"` 关闭时隐藏而非销毁（可监听 Hide 持久化布局状态）。

---

## 三、TaskManager 任务管理器

`<ext:TaskManager>` 是定时任务调度器，分客户端任务和服务端任务。

### 3.1 客户端任务（纯前端定时）

```aspx
<ext:TaskManager ID="tm1" runat="server">
    <Tasks>
        <ext:Task Interval="1000" AutoRun="true"
            OnStart="App.BtnStart.setDisabled(true);"
            OnStop="App.BtnStart.setDisabled(false);">
            <Listeners>
                <Update Handler="App.Label1.setText(Ext.Date.format(new Date(),'H:i:s'));" />
            </Listeners>
        </ext:Task>
    </Tasks>
</ext:TaskManager>
```

### 3.2 服务端任务（定时回调服务端）

```aspx
<ext:Task TaskID="refresh" Interval="5000" AutoRun="true">
    <DirectEvents>
        <Update OnEvent="RefreshData">
            <EventMask ShowMask="true" />
        </Update>
    </DirectEvents>
</ext:Task>
```

```csharp
protected void RefreshData(object sender, DirectEventArgs e)
{
    App.Label1.Text = DateTime.Now.ToString("HH:mm:ss");
}
```

### 3.3 控制方法（JS）

```javascript
App.tm1.startAll();                  // 启动全部
App.tm1.stopAll();                   // 停止全部
App.tm1.startTask('refresh');        // 按 TaskID 启动
App.tm1.stopTask('refresh');
App.tm1.startTask(0);                // 按索引启动
```

| 属性 | 作用 |
|------|------|
| `Interval` | 间隔（毫秒） |
| `AutoRun` | 是否自动运行（默认 true） |
| `TaskID` | 任务标识（供 startTask/stopTask） |
| `OnStart`/`OnStop` | 生命周期回调（JS 字符串） |

### 3.4 轮询服务器进度

```csharp
protected void StartLongAction(object sender, DirectEventArgs e)
{
    this.Session["Progress"] = 0;
    ThreadPool.QueueUserWorkItem(LongRunningTask);  // 后台线程
    this.ResourceManager1.AddScript("{0}.startTask('poll');", this.tm1.ClientID);
}

protected void Poll(object sender, DirectEventArgs e)
{
    object progress = this.Session["Progress"];
    if (progress != null)
    {
        X.Js.Call("updateProgress", progress);
    }
    else
    {
        this.ResourceManager1.AddScript("{0}.stopTask('poll');", this.tm1.ClientID);  // 完成停止轮询
        X.Msg.Notify("完成", "任务结束").Show();
    }
}
```

---

## 四、MessageBus 消息总线

基于发布/订阅模式，用点分主题（如 `App.event1`），支持通配符 `*`。

### 4.1 发布消息

```aspx
<!-- 1. 声明式广播（最简） -->
<ext:Button runat="server" Text="发布">
    <Listeners>
        <Click BroadcastOnBus="App.event1" />
    </Listeners>
</ext:Button>
```

```javascript
// 2. JS 手动发布
Ext.net.Bus.publish('App.event1', { msg: '数据', id: 1 });
```

```csharp
// 3. 服务端发布
MessageBus.Default.Publish("App.event1", "来自服务端");
```

### 4.2 订阅消息

```aspx
<ext:Panel runat="server" Title="监听器">
    <MessageBusListeners>
        <!-- 固定主题 -->
        <ext:MessageBusListener Name="App.event1"
            Handler="this.body.createChild({html: data.msg, tag:'p'});" />
        <!-- 通配符 -->
        <ext:MessageBusListener Name="App.*"
            Handler="console.log('收到：' + name);" />
    </MessageBusListeners>
</ext:Panel>
```

回调参数：`name`（主题名）、`data`（数据对象）。

### 4.3 订阅触发服务端方法

```aspx
<ext:Panel runat="server">
    <MessageBusDirectEvents>
        <ext:MessageBusDirectEvent Name="App.save" OnEvent="SaveData">
            <ExtraParams>
                <ext:Parameter Name="data" Value="data" Mode="Raw" />
            </ExtraParams>
        </ext:MessageBusDirectEvent>
    </MessageBusDirectEvents>
</ext:Panel>
```

```csharp
protected void SaveData(object sender, DirectEventArgs e)
{
    string data = e.ExtraParams["data"];
}
```

### 4.4 跨用户控件通信

约定主题前缀实现解耦：
- 控件向外发：`FromUserControl.*`
- 向控件发：`ToUserControl1.*`

> 适合多个 UserControl 之间不直接引用、通过消息通信的场景。

---

## 五、Associations 模型关联

### 5.1 HasMany（一对多）

```aspx
<!-- 子模型 -->
<ext:Model runat="server" Name="Product" IDProperty="Id">
    <Fields>
        <ext:ModelField Name="Id" Type="Int" />
        <ext:ModelField Name="Name" />
    </Fields>
</ext:Model>

<!-- 父模型（含关联） -->
<ext:Store ID="s1" runat="server">
    <Model>
        <ext:Model runat="server" Name="User" IDProperty="Id">
            <Fields>
                <ext:ModelField Name="Id" Type="Int" />
                <ext:ModelField Name="Name" />
            </Fields>
            <Associations>
                <ext:HasManyAssociation Model="Product" Name="products" AssociationKey="Products" />
            </Associations>
        </ext:Model>
    </Model>
</ext:Store>
```

C# 数据（子集嵌在父对象内）：

```csharp
public class User {
    public int Id { get; set; }
    public string Name { get; set; }
    public List<Product> Products { get; set; }   // 属性名 == AssociationKey
}
```

使用：`record.products()` 返回子 Store 绑定到子 Grid：

```javascript
App.Grid1.getSelection()[0].products()  // 返回关联子 Store
```

### 5.2 HasOne（一对一）

```aspx
<ext:Model runat="server" Name="Address" IDProperty="Id">
    <Fields>
        <ext:ModelField Name="Id" Type="Int" />
        <ext:ModelField Name="Street" />
        <ext:ModelField Name="City" />
    </Fields>
</ext:Model>

<ext:Model runat="server" Name="Person" IDProperty="Id">
    <Fields>
        <ext:ModelField Name="Id" Type="Int" />
        <ext:ModelField Name="Name" />
    </Fields>
    <Associations>
        <ext:HasOneAssociation Model="Address" AssociationKey="Address" />
    </Associations>
</ext:Model>
```

访问器是异步回调：`record.getAddress(callback)`：

```javascript
record.getAddress(function (address) {
    App.FormPanel1.getForm().loadRecord(address);
});
```

### 5.3 懒加载（按需分请求）

大数据量场景，每展开一级发一次请求：

```aspx
<ext:HasManyAssociation Model="Order" AutoLoad="true"
    PrimaryKey="Id" ForeignKey="CustomerId" />
<Proxy>
    <ext:PageProxy DirectFn="App.direct.GetOrders" />
</Proxy>
```

```csharp
[DirectMethod]
public object GetOrders(string action, Dictionary<string, object> extraParams)
{
    var prms = new StoreRequestParameters(extraParams);
    int customerId = Convert.ToInt32(prms.Filter[0].Value);  // 框架传入外键过滤
    return this.Orders.Where(o => o.CustomerId == customerId);
}
```

| 关联类型 | 访问器 | 返回 |
|---------|--------|------|
| HasMany | `record.<Name>()` | 子 Store（同步） |
| HasOne | `record.get<Key>(callback)` | 子记录（异步回调） |

---

## 六、MultiUpload 多文件上传

> ⚠️ 基于 SwfUpload（Flash），现代浏览器已禁用 Flash，**生产环境建议改用 HTML5 方案**（见 `extnet-file-upload-guide.md`、`multi-file-upload-pitfalls.md`）。

### 6.1 基础用法

```aspx
<ext:MultiUpload ID="mu1" runat="server"
    OnFileUpload="mu1_FileUpload"
    AutoStartUpload="true"
    FileDropAnywhere="true"
    FileSizeLimit="15 MB"
    FileTypes="*.*"
    FileTypesDescription="All Files"
    FileUploadLimit="100">
    <Listeners>
        <UploadStart Handler="Ext.Msg.wait('上传中...');" />
        <UploadComplete Handler="Ext.Msg.hide();" />
        <UploadError Fn="uploadError" />
    </Listeners>
</ext:MultiUpload>
```

```csharp
protected void mu1_FileUpload(object sender, FileUploadEventArgs e)
{
    // e.FileName 取文件名
    X.Msg.Notify("完成", "已上传：" + e.FileName).Show();
}
```

### 6.2 Grid 列表式上传（带进度）

```aspx
<ext:Column runat="server" Text="文件名" DataIndex="name" />
<ext:Column runat="server" Text="大小" DataIndex="size">
    <Renderer Format="FileSize" />
</ext:Column>
<ext:ProgressBarColumn runat="server" Text="进度" DataIndex="progress" />
```

### 6.3 控制方法（JS）

```javascript
App.mu1.startUpload();        // 开始上传队列
App.mu1.abortUpload(id);      // 取消单条
App.mu1.abortAllUploads();    // 取消全部
App.mu1.removeUpload(id);     // 移除单条
App.mu1.removeAllUploads();   // 清空队列
```

| Listener | 形参 | 时机 |
|---------|------|------|
| `FileSelected` | (item, file) | 选中文件（return false 拒绝） |
| `UploadStart` | (file) | 单文件开始 |
| `UploadProgress` | (file, bytesComplete, bytesTotal) | 进度变化 |
| `UploadComplete` | (file) | 单文件完成 |

---

## 七、踩坑要点

### 坑1：PropertyGrid 布尔值必须 Mode="Raw"

```aspx
<ext:PropertyGridParameter Name="flag" Value="true" Mode="Raw" />     <!-- ✅ 布尔 -->
<ext:PropertyGridParameter Name="flag" Value="true" />                 <!-- ❌ 字符串 -->
```

### 坑2：Portlet 拖拽是内置的

Portal 的 Portlet 列间拖拽**无需配 DragDrop 插件**，直接放 PortalColumn 即可。

### 坑3：TaskManager 服务端任务用 DirectEvents

客户端任务用 `<Listeners><Update>`，服务端任务用 `<DirectEvents><Update OnEvent>`，两者不能混。

### 坑4：MessageBus 通配符只在末段

`App.*` 匹配 `App.event1`/`App.event2`，但 `*.event1` 这种通配符在中间的不支持。

### 坑5：HasMany 的 AssociationKey 必须与 C# 属性名一致

```csharp
public List<Product> Products { get; set; }   // 属性名 Products
```
```aspx
AssociationKey="Products"   <!-- 必须与上面一致 -->
```

### 坑6：MultiUpload 已过时

MultiUpload 基于 Flash，现代浏览器不支持。生产环境用 `<ext:FileUploadField>` + HTML5 方案。

---

## 八、关联文档

| 文档 | 关系 |
|------|------|
| `extnet-store-databinding-guide.md` | Store（Associations 的数据基础） |
| `extnet-grid-complete-guide.md` | GridPanel（主从表用 HasMany） |
| `extnet-file-upload-guide.md` | 文件上传（替代 MultiUpload 的 HTML5 方案） |
| `multi-file-upload-pitfalls.md` | 多文件上传踩坑 |
| `extnet-desktop-framework-guide.md` | Desktop（Portal 看板类似） |

## 九、参考来源

- `Examples/PropertyGrid/Basic/`
- `Examples/Portal/Basic/`
- `Examples/TaskManager/Basic/`
- `Examples/MessageBus/Basic/`
- `Examples/Associations/`（HasMany / HasOne）
- `Examples/MultiUpload/Basic/`
