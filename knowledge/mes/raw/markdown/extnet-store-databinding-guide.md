---
title: Ext.NET Store 与数据绑定完整指南
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Store, Model, Proxy, AjaxProxy, PageProxy, JsonReader, 数据绑定, ViewModel, 双向绑定, Formulas, 级联]
status: active
updated: 2026-08-29
---
# Ext.NET Store 与数据绑定完整指南

> 本文档从 Ext.NET 4.7.1 官方示例库 `Examples/Data_Binding/`（13 示例）+ `GridPanel/` 分页排序示例提炼，覆盖 Store/Model/Proxy/Reader、数据填充、ViewModel 双向绑定、级联。目标是让 AI/开发者读完即可在任意 Ext.NET WebForms 项目复现。
>
> 适用：Ext.NET 4.x + Triton 主题。底层是 ExtJS 的 `Ext.data.Store`。

---

## 一、Store 基础结构

Store 是 GridPanel/ComboBox/Chart/TreeView 等**所有数据控件的数据容器**。核心层级：

```text
Store
 └── Model
      └── Fields (多个 ModelField)
```

### 最小写法

```aspx
<ext:Store ID="Store1" runat="server">
    <Model>
        <ext:Model runat="server">
            <Fields>
                <ext:ModelField Name="company" />
                <ext:ModelField Name="price" Type="Float" />
                <ext:ModelField Name="lastChange" Type="Date" DateFormat="M/d hh:mmtt" />
            </Fields>
        </ext:Model>
    </Model>
</ext:Store>
```

### ModelField 的 Type

| Type | 作用 |
|------|------|
| `String`（默认，可省略） | 字符串 |
| `Int` | 整数 |
| `Float` | 浮点（货币、百分比常用） |
| `Date` | 日期，配合 `DateFormat` 解析字符串（如 `yyyy-MM-dd`） |
| `Boolean` | 布尔 |

---

## 二、Store 的三种持有方式

### 方式 A：内联持有（最常用）

数据控件通过 `<Store>` 子标签直接持有：

```aspx
<ext:GridPanel runat="server">
    <Store>
        <ext:Store ID="Store1" runat="server">
            <Model>...</Model>
        </ext:Store>
    </Store>
    ...
</ext:GridPanel>
```

### 方式 B：页面级独立 Store

Store 声明在页面顶层，多个控件通过 `StoreID` 引用：

```aspx
<ext:Store ID="SharedStore" runat="server">...</ext:Store>

<ext:GridPanel runat="server" StoreID="SharedStore">...</ext:GridPanel>
<ext:ComboBox runat="server" StoreID="SharedStore" />
```

### 方式 C：ViewModel 内 Store（高级绑定）

Store 声明在 ViewModel 中，通过 `BindString="{storeName}"` 引用。

---

## 三、数据填充方式

### 方式 1：DataSource（服务端 Page_Load 赋值）— 最经典

```csharp
protected void Page_Load(object sender, EventArgs e)
{
    if (!X.IsAjaxRequest)   // 关键：非 Ajax 才赋值
    {
        this.Store1.DataSource = new List<object>
        {
            new { company = "3m Co", price = 71.72, lastChange = "9/1 12:00am" },
            new { company = "Alcoa", price = 29.01, lastChange = "9/1 12:00am" }
        };
    }
}
```

赋值对象数组时，列顺序须与 `<ModelField>` 声明顺序一致；赋匿名对象时按字段名匹配。

### 方式 2：Data 属性绑定（声明式）

```aspx
<ext:Store runat="server" Data="<%# MyData %>" AutoDataBind="true">
```

### 方式 3：远程 Proxy（按需加载）— 见下节

---

## 四、Proxy 代理（远程加载）详解

### 4.1 AjaxProxy —— 任意 URL 远程读取（最通用）

```aspx
<ext:Store runat="server" AutoLoad="true">
    <Proxy>
        <ext:AjaxProxy Url="~/Handlers/Data.ashx">
            <ActionMethods Read="POST" />
            <Reader>
                <ext:JsonReader RootProperty="data" TotalProperty="total" />
            </Reader>
        </ext:AjaxProxy>
    </Proxy>
    <Model>...</Model>
</ext:Store>
```

- `AutoLoad="true"`：Store 创建后自动发起请求
- `Url`：接口地址（json 文件、REST 接口、ashx 均可）
- 读 XML 用 `<ext:XmlReader Record="Item" />`

### 4.2 PageProxy + OnReadData —— 服务端事件分页排序

```aspx
<ext:Store ID="Store1" runat="server" RemoteSort="true" PageSize="20"
    OnReadData="Store1_ReadData">
    <Proxy>
        <ext:PageProxy />
    </Proxy>
    <Model>...</Model>
</ext:Store>
```

```csharp
protected void Store1_ReadData(object sender, StoreReadDataEventArgs e)
{
    // e.Start / e.Limit / e.Sort 是客户端传来的分页排序参数
    var data = GetData(e.Start, e.Limit, e.Sort);
    this.Store1.DataSource = data;
    this.Store1.DataBind();
    (this.Store1.Proxy[0] as PageProxy).Total = GetTotalCount();  // 回写总数
}
```

### 4.3 PageProxy + DirectFn —— DirectMethod（推荐）

性能最好、代码集中，支持服务端分页排序：

```aspx
<ext:Store ID="Store1" runat="server" RemoteSort="true" PageSize="20">
    <Proxy>
        <ext:PageProxy DirectFn="App.direct.BindData" />
    </Proxy>
    <Model>...</Model>
</ext:Store>
```

```csharp
[DirectMethod]
public object BindData(string action, Dictionary<string, object> extraParams)
{
    StoreRequestParameters prms = new StoreRequestParameters(extraParams);
    // prms.Start / prms.Limit / prms.Sort
    int total;
    var data = GetData(prms.Start, prms.Limit, prms.Sort, out total);
    return new { data, total };   // 关键：返回 { data, total }
}
```

### 三种 Proxy 对比

| Proxy | 数据来源 | 适用场景 |
|-------|---------|---------|
| **AjaxProxy** | 任意 URL（json/xml/ashx） | 纯前端拉数据、REST 接口 |
| **PageProxy + OnReadData** | 服务端事件 | 已有 ObjectDataSource/SqlDataSource |
| **PageProxy + DirectFn** | `[DirectMethod]` C# 方法 | **推荐**：服务端分页排序，代码集中 |

---

## 五、Reader 读取器

决定 Proxy 拉回数据如何映射成 ModelField：

| Reader | 用途 | 关键属性 |
|--------|------|---------|
| `JsonReader`（AjaxProxy 默认） | 读 JSON | `RootProperty`/`TotalProperty`/`MessageProperty` |
| `XmlReader` | 读 XML | `Record`（记录节点名） |
| `ArrayReader` | 读二维数组 | 按位置映射 |

```aspx
<ext:JsonReader RootProperty="data" TotalProperty="total"
    MessageProperty="msg" SuccessProperty="success" />
```

- **RootProperty**：记录数组的 JSON 字段名
- **TotalProperty**：总条数字段名（供分页栏）
- **MessageProperty**：错误消息字段名

> DirectMethod 返回 `new { data, total }` 时，Ext.NET 自动识别这两个字段，通常无需显式写 Reader。

---

## 六、Store 关键配置属性

| 属性 | 作用 |
|------|------|
| `AutoLoad="true"` | 创建后自动 load（远程必备） |
| `PageSize="20"` | 每页条数（配 PagingToolbar） |
| `RemoteSort="true"` | 排序交服务端 |
| `RemoteFilter="true"` | 过滤交服务端 |
| `RemotePaging="true"` | 分页交服务端 |
| `ReloadOnClearSorters="true"` | 清空排序器时自动重载 |

默认排序：

```aspx
<ext:Store runat="server">
    <Sorters>
        <ext:DataSorter Property="CreateDate" Direction="DESC" />
    </Sorters>
</ext:Store>
```

---

## 七、Store 客户端方法（JS）

```javascript
var store = App.Store1;

store.load();                       // 重新拉取（走 Proxy）
store.reload();                     // 等价 load，保留参数
store.loadPage(2);                  // 跳到第 2 页
store.loadData([{name:'a'}, {name:'b'}]);  // 本地灌数据（不走 Proxy）

store.add(rec);                     // 新增记录
store.remove(record);              // 删除记录
store.removeAt(0);

store.commitChanges();              // 提交所有增删改（清脏标记）
store.rejectChanges();              // 回滚所有未提交改动

store.filter('country', 'USA');     // 过滤
store.clearFilter();
store.sort('age', 'ASC');

store.getTotalCount();              // 总条数
store.getCount();                   // 当前页条数
store.findRecord('id', 5);          // 查记录
```

**增删改记录分离**：

```javascript
store.getNewRecords();      // 新增的
store.getUpdatedRecords();  // 修改的
store.getRemovedRecords();  // 删除的
```

---

## 八、Store 服务端方法（C#）

```csharp
this.Store1.DataSource = data;       // 赋值
this.Store1.DataBind();              // 触发绑定（PageProxy OnReadData 必调）

this.Store1.LoadData(data);          // 直接灌数据（绕过 Proxy）
this.Store1.LoadData(data, total);   // 带总数的灌数据

// 解析 DirectMethod 入参
var prms = new StoreRequestParameters(extraParams);
// prms.Start / prms.Limit / prms.Sort

// 获取脏数据提交数据库
var modified = Store1.GetChangedRecords();
```

---

## 九、ViewModel 数据绑定（双向绑定）

> 这是 ExtJS 5+ 的 MVVM 特性，独立于 Store 数据填充。用于**控件属性**绑定到 ViewModel 字段。

### 9.1 单向绑定

```aspx
<ext:Panel runat="server"
    ViewModel="<%# MyModel.Model %>"
    AutoDataBind="true">
    <Bind>
        <ext:Parameter Name="title" Value="{title}" />
        <ext:Parameter Name="html" Value="内容：{title}" />
    </Bind>
</ext:Panel>
```

- `ViewModel="<%# ... %>"`：注入 ViewModel（`#` 是绑定表达式，必须 `AutoDataBind="true"`）
- `<Bind>`：绑定多个属性，`{字段名}` 引用 VM 值
- `BindString="{字段}"`：单属性简写

### 9.2 双向绑定（表单字段 ↔ VM）

```aspx
<ext:Panel runat="server" ViewModel="<%# MyModel.Model %>" AutoDataBind="true">
    <Bind><ext:Parameter Name="title" Value="{title}" /></Bind>
    <Items>
        <ext:TextField runat="server" FieldLabel="标题" BindString="{title}" />
    </Items>
</ext:Panel>
```

TextField 改值 → VM 更新 → Panel title 同步，反向亦然。

### 9.3 组件状态绑定（Reference + 表达式）

```aspx
<ext:Panel runat="server" ReferenceHolder="true">
    <Items>
        <ext:Checkbox runat="server" Reference="isAdmin" />
        <ext:TextField runat="server">
            <Bind><ext:Parameter Name="disabled" Value="{!isAdmin.checked}" /></Bind>
        </ext:TextField>
    </Items>
</ext:Panel>
```

- `ReferenceHolder="true"`：容器开启引用持有
- `Reference="isAdmin"`：把控件注册为 VM 可引用名
- `{!isAdmin.checked}`：支持表达式（`!`/`&&`/`||`），绑定子属性

### 9.4 动态修改 VM（JS）

```javascript
this.up('panel').getViewModel().set('title', '新标题');
```

---

## 十、Formulas 公式字段（计算属性）

```csharp
public static object Model = new {
    data = new { x = 10 },
    formulas = new {
        twice = new JFunction("return get('x') * 2;", "get"),
        quad  = new JFunction("return get('twice') * 2;", "get")
    }
};
```

```aspx
<ext:NumberField runat="server" FieldLabel="X" BindString="{x}" />
<ext:DisplayField runat="server" BindString="{x}*2={twice} / {x}*4={quad}" />
```

- `JFunction(函数体, "get")`：`get('字段名')` 读取 VM 值
- 公式可互相依赖（`quad` 依赖 `twice`），框架自动排序

---

## 十一、级联 ComboBox（声明式）

无需手写 JS，纯声明式级联：

```aspx
<ext:Panel runat="server" ReferenceHolder="true">
    <Items>
        <ext:ComboBox runat="server" FieldLabel="国家"
            Reference="country" Publishes="value">
            <Items>
                <ext:ListItem Text="中国" />
                <ext:ListItem Text="美国" />
            </Items>
        </ext:ComboBox>

        <ext:ComboBox runat="server" FieldLabel="省份"
            DisplayField="name" ValueField="code" QueryMode="Remote">
            <Bind>
                <ext:Parameter Name="visible" Value="{country.value}" />
                <ext:Parameter Name="filters"
                    Value="{property:'country', value:'{country.value}'}" Mode="Raw" />
            </Bind>
            <Store>
                <ext:Store runat="server" AutoLoad="true">
                    <Proxy><ext:AjaxProxy Url="provinces.json" /></Proxy>
                    <Model><ext:Model runat="server"><Fields>
                        <ext:ModelField Name="code" />
                        <ext:ModelField Name="name" />
                        <ext:ModelField Name="country" />
                    </Fields></ext:Model></Model>
                </ext:Store>
            </Store>
        </ext:ComboBox>
    </Items>
</ext:Panel>
```

核心机制：
- `Reference="country"` + `Publishes="value"`：把上级 ComboBox 的值发布到 VM
- 子级 `<Bind>` filters：上级值作为过滤器
- `{country.value}` 为 null 时过滤器失效（隐藏子级）

---

## 十二、踩坑要点

### 坑1：DataSource 赋值必须判断 IsAjaxRequest

```csharp
if (!X.IsAjaxRequest)   // 必须加，否则每次 DirectEvent 都重新覆盖数据
{
    this.Store1.DataSource = data;
}
```

### 坑2：AjaxProxy 不加 AutoLoad 不自动加载

远程 Store 必须 `AutoLoad="true"`，否则要手动调用 `store.load()` 才会取数。

### 坑3：PageProxy 必须回写 Total

服务端分页时必须 `(Proxy[0] as PageProxy).Total = 总数`，否则分页栏总数显示 0。

### 坑4：DirectMethod 返回 {data, total} 而非纯数组

```csharp
return new { data, total };   // ✅ 正确
return dataList;              // ❌ 分页栏拿不到总数
```

### 坑5：ViewModel 绑定用 # 不是 =

`ViewModel="<%# ... %>"` 是数据绑定表达式（`#`），不是 `<%= %>`（Response.Write）。必须配 `AutoDataBind="true"` 才在 PreRender 求值。

### 坑6：ModelField 名大小写敏感

`ModelField Name="Data1"` 与 Column 的 `DataIndex="Data1"` 必须大小写完全一致。

### 坑7：Bind filters 的 Mode="Raw"

级联 ComboBox 的 filters 绑定值是对象字面量，必须 `Mode="Raw"`，否则被当字符串。

---

## 十三、关联文档

| 文档 | 关系 |
|------|------|
| `extnet-grid-complete-guide.md` | GridPanel（Store 是 Grid 的数据源） |
| `extnet-chart-guide.md` | Chart 图表（Store 是 Chart 的数据源） |
| `extnet-directmethod-and-data.md` | DirectMethod 与数据访问 |
| `extnet-pagination-guide.md` | 分页（PageProxy + PagingToolbar） |
| `extnet-combobox-properties.md` | ComboBox（Store 是下拉数据源） |
| `extnet-tree-guide.md` | TreePanel（TreeStore 用法） |

## 十四、参考来源

- 官方示例库：`Examples/Data_Binding/Basic/`（13 示例）
  - `Hello_World/`：ViewModel 单向绑定
  - `Dynamic/`：`getViewModel().set()` 动态更新
  - `Formulas/`：JFunction 公式字段
  - `Two_Way/`：双向绑定
  - `Model_Validation/`：Model + Validators + links
  - `Chained_Combos/`：级联 ComboBox（Reference/Publishes/bind filter）
  - `Chaining_Stores/`：Source 链式 Store
  - `Component_State/`：组件状态绑定
- `GridPanel/ArrayGrid/Simple/`：DataSource + ModelField Type
- `GridPanel/Paging_and_Sorting/Page/`：PageProxy + OnReadData
- `GridPanel/Paging_and_Sorting/DirectMethod/`：PageProxy DirectFn
