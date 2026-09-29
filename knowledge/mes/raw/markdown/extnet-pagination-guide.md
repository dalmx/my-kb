---
title: Ext.NET 分页完全指南（前端分页 / Session 缓存切片 / 框架内存分页）
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, 分页, 前端分页, 客户端分页, loadData, 服务端分页, Session缓存, RemotePaging, PageProxy, 内存分页, PageResult, GetPageDataByReader, DirectMethod, ServerMapping, PagingToolbar]
updated: 2026-08-29
status: active
---

# Ext.NET 分页完全指南（前端分页 / Session 缓存切片 / 框架内存分页）

> 2026-08-23 合并：原《Ext.NET 分页完整方案》（框架内存分页）+《客户端分页方案》+《服务端分页踩坑》三篇合一。
> 三种方案覆盖全部场景，先按速查表选型：

| 场景特征 | 推荐方案 |
|---|---|
| 数据量可控（几千行内）、需导出全量、快速落地 | **方案一** 前端分页（loadData 全量，浏览器切片） |
| 数据源是存储过程、存储过程本身快、需导出全量 | **方案二** 服务端 Session 缓存切片（PageProxy + DirectMethod） |
| 单条内联 SELECT、走框架、并发量较大 | **方案三** 框架内存分页（GetPageDataByReader） |

## 一、客户端前端分页（loadData 全量）

### 一、何时用前端分页
| 方案 | 数据传输 | 后端复杂度 | 适用场景 | 参考文档 |
|------|----------|-----------|----------|----------|
| **前端分页（本文）** | 一次性全量 | 最低，无需 DirectMethod 翻页 | 数据量可控（几千行内）、需支持导出全量、快速落地 | 本文 |
| 服务端真分页 | 仅当前页 | 中，需 PageProxy + DirectMethod 切片 | 数据量大、不想全量传输 | 方案二 |
| 后端内存分页 | 仅当前页 | 中，框架 `GetPageDataByReader` | 单条 SELECT、走框架 | 方案三 |
**决策建议**：默认优先前端分页（简单）。当单次查询结果可能超过 1~2 万行，或首次加载明显变慢（几十秒）、触发请求长度限制（4MB）时，再切服务端真分页。
---

### 二、完整实现

#### 1. aspx —— Store 配置（关键：不加 Proxy、不加 RemotePaging）

```aspx
<ext:Store ID="storeUF" runat="server" AutoLoad="false" PageSize="100">
    <!-- 注意：没有 <Proxy><ext:PageProxy .../></Proxy>，也没有 RemotePaging="true" -->
    <Model>
        <ext:Model ID="mdlUF" runat="server">
            <Fields>
                <!-- DataSource 路径下 ServerMapping 自动生效 -->
                <ext:ModelField Name="CheckID" ServerMapping="ID" />
                <ext:ModelField Name="Barcode" />
                ...
            </Fields>
        </ext:Model>
    </Model>
</ext:Store>
```

> **ServerMapping 在前端分页下天然生效**：`DataSource` 绑定路径会按 `ServerMapping` 把数据源列 `ID` 映射成 Model 字段 `CheckID`。这与服务端分页（PageProxy DirectFn）下 ServerMapping 失效正好相反（见 方案二）。

#### 2. aspx —— GridPanel + PagingToolbar

```aspx
<ext:GridPanel ID="pnlUF" runat="server" Header="false">
    <Store><ext:Store .../></Store>
    <ColumnModel>...</ColumnModel>
    <BottomBar>
        <ext:PagingToolbar ID="pageToolBarUF" runat="server" DisplayInfo="true">
            <Listeners>
                <AfterRender Handler="bindRefresh(this);" />   <%-- 接管刷新按钮，见踩坑一 --%>
            </Listeners>
            <Items>
                <ext:Label runat="server" Text="每页条数：" />
                <ext:ComboBox ID="cmbPageSizeUF" runat="server" Width="80" Editable="true" ForceSelection="false">
                    <Items>
                        <ext:ListItem Text="50" />
                        <ext:ListItem Text="100" />
                        <ext:ListItem Text="200" />
                        <ext:ListItem Text="500" />
                    </Items>
                    <SelectedItems><ext:ListItem Text="100" /></SelectedItems>
                    <Listeners>
                        <Change Fn="applyPageSize" />   <%-- 见踩坑三 --%>
                    </Listeners>
                </ext:ComboBox>
            </Items>
        </ext:PagingToolbar>
    </BottomBar>
</ext:GridPanel>
```

#### 3. aspx —— JS（查询入口 + 刷新接管 + 每页条数）

```javascript
// 统一查询入口：调后端 SearchData（按顶部下拉框的类型查询并绑定）
var doSearch = function () {
    App.direct.SearchData({
        eventMask: { showMask: true, target: 'customtarget', customTarget: 'tabPanel' },
        failure: function (error) { Ext.Msg.alert('提示', error.errorMessage || '查询失败'); }
    });
};

// 查询按钮
var Search = function () {
    // ...设置活动 Tab...
    doSearch();
};

// ★ 踩坑一：前端分页下 Store 无 Proxy，刷新按钮默认触发 store.load()（空 load）。
//   在工具栏渲染后接管刷新按钮，改为重新查询。
var bindRefresh = function (toolbar) {
    var btn = toolbar.child('#refresh');
    if (btn) {
        btn.setHandler(function () { doSearch(); });
    }
};

// ★ 踩坑三：每页条数支持手输任意正整数
var applyPageSize = function (combo) {
    var raw = combo.getValue();
    var size = parseInt(raw, 10);
    if (isNaN(size) || size < 1) {            // 非数字或非法，忽略
        return;
    }
    var store = combo.id === 'cmbPageSizeUF' ? App.storeUF : App.storeDB;
    store.pageSize = size;
    store.loadPage(1);   // 前端分页下 loadPage 用内存数据重新切片，不会查库
};
```

#### 4. aspx.cs —— 查询并绑定（无翻页 DirectMethod）

```csharp
[DirectMethod]
public void SearchData()
{
    try
    {
        DataTable dt = QueryData();                 // 一次性查全量
        Session["UniformityCommonData_" + (_checkType ?? "UF")] = dt;   // 缓存供导出复用

        // 前端分页：全量绑给 Store，PageSize + PagingToolbar 在浏览器端切片
        if (_checkType == "DB")
        {
            storeDB.DataSource = dt;
            storeDB.DataBind();
        }
        else
        {
            storeUF.DataSource = dt;
            storeUF.DataBind();
        }
    }
    catch (Exception ex)
    {
        X.Msg.Alert("提示", ex.Message).Show();
    }
}
```

> 不需要 `GridPanelBindData(action, extraParams)` 这类翻页 DirectMethod；不需要 `StoreRequestParameters`；不需要内存切片循环。导出直接用缓存的 `DataTable` 全量渲染。

---

### 三、踩坑记录

#### 踩坑一（头号）：刷新按钮「点了没反应」

**现象**：前端分页下，PagingToolbar 自带的刷新按钮 ↻ 点击后数据不刷新，甚至清空。

**根因**：前端分页的 Store 没有 `Proxy`。刷新按钮默认行为是 `store.load()`，但没有数据源可加载 → 空 load → 清空当前页。

**❌ 失败方案：用 Store 的 `BeforeLoad` 全局拦截**
```javascript
// 反例 —— 会破坏正常的数据绑定！
var onStoreBeforeLoad = function (store) {
    doSearch();
    return false;
};
// <ext:Store ...><Listeners><BeforeLoad Fn="onStoreBeforeLoad" /></Listeners></ext:Store>
```
**为什么失败**：`BeforeLoad` 是全局拦截，会误伤 `DataBind()` 后的数据加载流程，导致**查询也查不出数据**（服务端绑定被前端拦截取消）。本次 `ReportTyreUniformityCommon` 改造中，加上 `BeforeLoad` 后查询直接失效，去掉即恢复——这是最典型的回归陷阱。

**✅ 正确方案：只接管刷新按钮本身，不动 Store 加载机制**
```javascript
var bindRefresh = function (toolbar) {
    var btn = toolbar.child('#refresh');      // ExtJS PagingToolbar 刷新按钮 itemId 固定为 #refresh
    if (btn) {
        btn.setHandler(function () { doSearch(); });
    }
};
// PagingToolbar 加 <AfterRender Handler="bindRefresh(this);" />
```
**关键点**：`btn.setHandler(fn)` 只改写刷新按钮的点击行为，不触碰翻页、改每页条数、服务端绑定等正常流程。

#### 踩坑二：`X.Msg.Alert(...).Show()` 在 DirectMethod 里

`X.Msg.Alert(msg).Show()` 在 `[DirectMethod]` 的 catch 里可用（会下发客户端脚本弹框）。但要确保 DirectMethod 返回类型是 `void` 而非 `object`——若返回 `object` 且内部抛异常，前端 `failure` 回调才会拿到错误。

#### 踩坑三：每页条数下拉框「不能手输数字」

**默认现象**：`Editable="true"` 的 ComboBox 手输非列表项时，值会被清空。

**根因**：Ext.NET ComboBox 默认 `ForceSelection=true`，会强制清空非列表项的输入。

**✅ 方案**：
```aspx
<ext:ComboBox ... Editable="true" ForceSelection="false">
```
配合 JS 校验，支持手输任意正整数：
```javascript
var applyPageSize = function (combo) {
    var size = parseInt(combo.getValue(), 10);
    if (isNaN(size) || size < 1) return;   // 非数字/非法，忽略不报错
    store.pageSize = size;
    store.loadPage(1);
};
```
> 注意：改每页条数后应 `loadPage(1)` 回到第一页（当前页码可能超出新总页数）。若想停留当前页，参考 方案三 用 `pageToolBar.doRefresh()`。

---

### 四、落地页参考

| 文件 | 说明 |
|------|------|
| `Plugins/Quality/ReportAnalyse/ReportTyreUniformityCommon.aspx(.cs)` | 本次前端分页方案落地页（含刷新按钮接管、每页条数手输、多 Tab 的 UF/DB 两个 Grid） |

---

### 五、关联文档

| 文档 | 关系 |
|------|------|
| 方案二 | **服务端真分页**方案（PageProxy DirectFn + Session 缓存切片），本文是它的轻量替代；两者 ServerMapping 行为相反 |
| 方案三 | **分页完整方案**（RemotePaging 概念 + 后端内存分页 + PageProxy DirectMethod），含每页条数 ComboBox |

---

### 六、一句话总结

前端分页 = **Store 不加 Proxy + 后端 `DataSource`/`DataBind()` 绑全量 + `PageSize`/`PagingToolbar` 浏览器切片**。
两个必做动作：① `AfterRender` 里 `child('#refresh').setHandler(doSearch)` 接管刷新按钮；② 每页条数 ComboBox 加 `ForceSelection="false"` 才能手输。
一个禁忌：**不要用 Store 的 `BeforeLoad` 全局拦截去实现刷新**——会连带破坏正常的数据绑定。

## 二、服务端 Session 缓存切片（PageProxy + DirectMethod）

### 改造步骤（Session 缓存 + 服务端分页，不改 SQL/mapper）
适用于「存储过程本身快，但要支持导出全量」的场景。把全量结果存 Session，翻页时从内存切片；导出时直接用 Session 全量。
#### 1. 前端 aspx —— Store 改成服务端分页
给 Store 加 `RemotePaging="true"` 和 `PageProxy` 代理：
```aspx
<ext:Store ID="storeUF" runat="server" AutoLoad="false" PageSize="100" RemotePaging="true">
    <Proxy>
    </Proxy>
    <Model> ... </Model>
</ext:Store>
```
`PagingToolbar`（在 `<BottomBar>` 里）无需改动，它会自动驱动 PageProxy。
#### 2. 前端 aspx —— 查询按钮改写
不再调旧的 `App.direct.SearchData()`。改为：先调 `RefreshCache` 刷新缓存，成功后 `loadPage(1)` 触发 PageProxy 取第一页。
```javascript
var Search = function () {
    var checkType = App.comb_CheckType.getValue() || 'UF';
    var grid = checkType === 'DB' ? App.pnlDB : App.pnlUF;
    App.tabPanel.setActiveTab(checkType === 'DB' ? 'tabDB' : 'tabUF');
    App.direct.RefreshCache({
        eventMask: { showMask: true, target: 'customtarget', customTarget: 'tabPanel' },
        success: function (result) {
            if (result && result !== '') { Ext.Msg.alert('提示', result); return; }
            grid.getStore().loadPage(1);   // 触发 PageProxy → GridPanelBindData
        },
        failure: function (error) { Ext.Msg.alert('提示', error.errorMessage || '查询失败'); }
    });
};
```
#### 3. 后端 aspx.cs —— 翻页入口 DirectMethod（关键）
返回 `{ data, total }` 匿名对象。Ext.Net 约定签名固定为 `(string action, Dictionary<string,object> extraParams)`。
```csharp
[DirectMethod]
public object GridPanelBindData(string action, Dictionary<string, object> extraParams)
{
    StoreRequestParameters prms = new StoreRequestParameters(extraParams);
    DataTable all = GetCurrentCache();   // 从 Session 取全量
    int total = (all == null) ? 0 : all.Rows.Count;
    if (all == null || total == 0)
        return new { data = new DataTable(), total = 0 };
    int page = prms.Page < 1 ? 1 : prms.Page;
    int limit = prms.Limit <= 0 ? 100 : prms.Limit;
    int start = (page - 1) * limit;
    DataTable pageTable = all.Clone();
    for (int i = start; i < start + limit && i < total; i++)
        pageTable.ImportRow(all.Rows[i]);
    return new { data = pageTable, total };
}
```
> `StoreRequestParameters` 来自 `Ext.Net` 命名空间；`prms.Page` / `prms.Limit` 是前端分页工具栏传来的页码与每页条数。
#### 4. 后端 aspx.cs —— 刷新缓存 DirectMethod + 辅助方法
```csharp
public string RefreshCache()
    try
    {
        DataTable dt = QueryData();
        Session["UniformityCommonData_" + (_checkType ?? "UF")] = dt;
        return "";
    }
    catch (Exception ex) { return ex.Message; }
private DataTable GetCurrentCache()
    return Session["UniformityCommonData_" + _checkType] as DataTable;
```
> 用业务类型（UF/DB）作 Session key 后缀，多类数据互不覆盖。Session 超时（web.config 已配 30 分钟）后自动回收。
#### 5. 后端 aspx.cs —— 导出用缓存全量
```csharp
protected void btnExport_Click(object sender, EventArgs e)
    DataTable dt = GetCurrentCache();
    if (dt == null) dt = QueryData();   // 缓存为空则回退重新查询
    if (dt == null || dt.Rows.Count == 0) return;
    // GenerateHtmlTable 不变，从全量 DataTable 渲染
```
---

### ⚠️ 头号踩坑：ServerMapping 在 PageProxy 路径下失效

**这是改造后最容易出的 bug：改完分页，首列（或某些列）变成空白。**

#### 现象
某些列改完分页后不显示数据，改回 `DataBind()` 又正常。

#### 根因
Model 字段若用了 `ServerMapping` 做列重命名：

```aspx
<ext:ModelField Name="CheckID" ServerMapping="ID" />
```

- **`DataSource` 绑定路径**：服务端会按 `ServerMapping` 把数据源列 `ID` 映射成 Model 字段 `CheckID`，前端正常取到。
- **`PageProxy` DirectFn 路径**：数据由 DirectFn 返回的 JSON 驱动，**前端直接用 Model 的 `Name`（`CheckID`）从 JSON 对象取值，`ServerMapping` 不再生效**。而 JSON 里实际是 `ID` 列 → 取不到 → 列空白。

#### 解决
在 DirectMethod 切片返回前，把数据源列名改成与 Model `Name` 一致：

```csharp
// 在 return 之前
if (pageTable.Columns.Contains("ID") && !pageTable.Columns.Contains("CheckID"))
{
    pageTable.Columns["ID"].ColumnName = "CheckID";
}
```

> 排查口诀：**哪列空白，就查那列的 Model `Name` 与存储过程返回的实际列名是否一致**；用了 `ServerMapping` 的列一定要在 DirectMethod 里手动对齐列名。其余 Model `Name` 与列名本就一致的列不受影响。

---

### 替代方案：框架内置 `GetPageDataByReader`（数据库分页）

如果场景是**单条内联 SELECT**（非存储过程）且**不需要导出全量**，可直接用框架的数据库分页，更省内存：

```csharp
[DirectMethod]
public object GridPanelBindData(string action, Dictionary<string, object> extraParams)
{
    StoreRequestParameters prms = new StoreRequestParameters(extraParams);
    var pageResult = new PageResult();
    pageResult.PageIndex = prms.Page;
    pageResult.PageSize  = prms.Limit;
    pageResult.OrderString = "T1.RECORD_TIME DESC";   // ROW_NUMBER 分页必需
    pageResult.StatementId = "GetBcheckInfo";          // mapper 里的 <select id="...">
    pageResult.ParameterObject = filterParams;         // Dictionary<string,object>
    pageResult = manager.GetPageDataByReader(pageResult);

    DataTable data = pageResult.ResultDataSet.Tables[0];
    return new { data, total = pageResult.RecordCount };
}
```

#### 两种方案对比

| 维度 | Session 缓存分页 | GetPageDataByReader（DB 分页） |
|------|------------------|-------------------------------|
| 数据源 | 任意（含存储过程） | 仅内联 SELECT mapper 语句 |
| 改 SQL | 不需要 | 不需要 |
| 导出全量 | 直接用缓存 | 需另写全量查询 |
| 服务器内存 | 每用户缓存一份 | 无压力 |
| 分页效率 | 内存切片，极快 | 每页查库（ROW_NUMBER） |
| ServerMapping 坑 | 需手动对齐列名 | 同样需注意 |

> 选型：**有「导出全量」需求 / 数据源是存储过程** → Session 缓存方案；**纯内联查询、无导出全量、并发量大** → GetPageDataByReader 方案。

---

### 代码库参考页面

- `Plugins/Quality/FakeReport/TyreCheckQueryNew.aspx(.cs)` —— `RemoteSort=true RemotePaging=true` + `PageProxy DirectFn="App.direct.GridBindData"`，标准模板。
- `Plugins/Quality/Bcheck/FqbBalanceInfo.aspx.cs` —— `GetPageDataByReader` 数据库分页范例（`.cs` 为 UTF-16 编码，需用对应编码读取）。
- `Plugins/Quality/ReportAnalyse/ReportTyreUniformityCommon.aspx(.cs)` —— 本次 Session 缓存方案落地页（含 ServerMapping 踩坑修复）。

> 约 30 个页面已用 `PageProxy DirectFn` 模式（遍历 `Plugins/` 下 `*.aspx` 搜 `PageProxy` 即可）。

---

### 部署注意

- 改动 `.cs` 是代码文件，**必须重新编译/重新发布站点**才生效；`.aspx` 改动随请求自动生效。
- 测试点：① 查询只加载第一页 100 行、翻页正常；② 导出是全量；③ `total` 与分页工具栏页码正确；④ 用了 `ServerMapping` 的列能正常显示。

### 编码规范提醒

- 本项目为 .NET Framework 4.8 WebForms，默认 **C# 5 兼容语法**：不要用字符串内插 `$""`、空条件 `?.`、表达式体成员。
- `PageResult` 类型来自 `Wongoing.Web.UI.Entity`（`using Wongoing.Web.UI.Entity;`）；`StoreRequestParameters` / `DirectMethod` 来自 `Ext.Net`。

## 三、框架内存分页（GetPageDataByReader / PageResult）

> 本文合并自 方案三（概念辨析）和 方案三（完整实现范例），涵盖分页模式选择、前后端实现、内存分页原理。

### 一、RemotePaging 属性 — 两种模式

`RemotePaging` 是 Ext.NET Store 组件的属性，控制分页数据的获取方式。

| 属性值 | 模式 | 说明 |
|--------|------|------|
| `true` | **远程分页** | 每次翻页时向服务器请求该页数据，服务器只返回当前页记录 |
| `false` | **本地分页** | 一次性加载全部数据到前端，由前端 JS 进行分页 |

```text
远程分页(true):  第1页→服务器返回第1页(50条); 翻页→服务器返回对应页(50条)
本地分页(false): 第1页→服务器返回全部(10000条)→前端显示第1页(50条); 翻页→无请求,前端切换
```

#### 项目实际情况：后端内存分页

本项目采用**后端内存分页**模式：
```text
用户翻页 → 请求服务器 → 后端查询全部数据 → 后端内存过滤当前页 → 返回当前页数据
```
- 前端行为类似"远程分页"（每次翻页请求服务器）
- 后端行为类似"本地分页"（查询全部后在应用层过滤）

> 对于本项目，应**移除 `RemotePaging="false"`**（或设为 `true`），让 Store 默认使用远程分页模式，配合 PageProxy 正常工作。

### 二、前端实现（aspx）

#### 2.1 Store 配置

```xml
<ext:Store ID="store" runat="server" PageSize="20">
    <Proxy>
        <ext:PageProxy DirectFn="App.direct.GridPanelBindData" />
    </Proxy>
    <Model>
        <ext:Model ID="model" runat="server">
            <Fields>
                <ext:ModelField Name="OBJID" />
                <ext:ModelField Name="USER_NAME" />
                <!-- 其他字段... -->
            </Fields>
        </ext:Model>
    </Model>
</ext:Store>
```

**关键属性：**
- `PageSize="20"` — 默认每页显示 20 条
- `DirectFn="App.direct.GridPanelBindData"` — 指定后端数据请求方法

#### 2.2 分页工具栏

```xml
<ext:PagingToolbar ID="pageToolBar" runat="server">
    <Items>
        <ext:Label Text="每页条数" />
        <ext:ComboBox ID="ComboBox2" Width="70" Editable="false">
            <Items>
                <ext:ListItem Text="10" />
                <ext:ListItem Text="20" />
                <ext:ListItem Text="30" />
                <ext:ListItem Text="50" />
            </Items>
            <SelectedItems>
                <ext:ListItem Value="20" />
            </SelectedItems>
            <Listeners>
                <Change Handler="#{pnlList}.store.pageSize = parseInt(this.getValue(), 10); #{pageToolBar}.doRefresh();" />
            </Listeners>
        </ext:ComboBox>
    </Items>
    <Plugins>
        <ext:ProgressBarPager runat="server" />
    </Plugins>
</ext:PagingToolbar>
```

#### 2.3 JavaScript 刷新函数

```javascript
// 查询刷新 - 重置到第1页
var pnlListFresh = function () {
    App.hidden_delete_flag.setValue("0");
    App.store.currentPage = 1;
    App.pageToolBar.doRefresh();
    return false;
}

// 历史查询刷新
var pnlHistoryListFresh = function () {
    App.hidden_delete_flag.setValue("");
    App.store.currentPage = 1;
    App.pageToolBar.doRefresh();
    return false;
}
```

### 三、后端实现（PageProxy 翻页 DirectMethod）

#### 3.1 DirectMethod 数据绑定方法

这是分页专用的 DirectMethod 签名（必须接 `action` 和 `extraParams`）：

```csharp
[DirectMethod]
public object GridPanelBindData(string action, Dictionary<string, object> extraParams)
{
    // 1. 解析分页参数
    StoreRequestParameters prms = new StoreRequestParameters(extraParams);
    var pageResult = new PageResult();
    pageResult.PageIndex = prms.Page;    // 当前页码（0基）
    pageResult.PageSize = prms.Limit;    // 每页条数

    // 2. 执行查询
    pageResult = GridPanelBindData(pageResult);

    // 3. 返回数据（必须返回 data + total）
    var data = pageResult.ResultDataSet.Tables[0];
    var total = pageResult.RecordCount;
    return new { data, total };
}
```

#### 3.2 私有查询方法

```csharp
private PageResult GridPanelBindData(PageResult pageResult)
{
    // 1. 构建查询参数
    var pageParams = new Dictionary<string, string>();
    if (!string.IsNullOrEmpty(txt_work_barcode.Text))
        pageParams.Add("WORK_BARCODE", txt_work_barcode.Text.TrimEnd().TrimStart());
    if (!string.IsNullOrEmpty(txt_user_name.Text))
        pageParams.Add("USER_NAME", txt_user_name.Text.TrimEnd().TrimStart());
    if (!string.IsNullOrEmpty(hidden_txt_dept.Text))
        pageParams.Add("DEPT_ID", hidden_txt_dept.Text);
    if (!string.IsNullOrEmpty(hidden_delete_flag.Text))
        pageParams.Add("DELETE_FLAG", hidden_delete_flag.Text);
    if (!string.IsNullOrEmpty(txt_real_name.Text))
        pageParams.Add("REAL_NAME", txt_real_name.Text);

    // 2. 设置查询配置
    pageResult.ParameterObject = pageParams;
    pageResult.StatementId = "GetAllUserList";
    pageResult.OrderString = "T1.OBJID ASC";

    // 3. 调用 Manager 执行分页查询
    return userManager.GetPageDataByReader(pageResult);
}
```

#### 3.3 导出功能（不分页）

```csharp
protected void btnExportSubmit_Click(object sender, DirectEventArgs e)
{
    var pageResult = new PageResult();
    pageResult.PageIndex = 0;  // 0 表示不分页
    pageResult.PageSize = 0;   // 0 表示不分页

    pageResult = GridPanelBindData(pageResult);
    // ... Excel 导出逻辑
}
```

### 四、核心类：PageResult

**文件位置：** `Frame\Wongoing.DbAccess\DbHelper\PageResult.cs`

```csharp
public class PageResult
{
    // 输入参数
    public string StatementId { get; set; }      // SQL语句ID
    public string OrderString { get; set; }      // 排序字段
    public object ParameterObject { get; set; }  // 查询条件
    public int PageIndex { get; set; }           // 当前页码 (从1开始)
    public int PageSize { get; set; }            // 每页条数
    public string TotalFields { get; set; }      // 合计字段

    // 输出结果
    public int RecordCount { get; set; }         // 总记录数
    public int PageCount { get; }                // 总页数 (计算属性)
    public DataSet ResultDataSet { get; set; }   // 查询结果数据
}
```

### 五、数据层实现 — 内存分页原理（BaseService.cs）

**文件位置：** `Frame\Wongoing.DbAccess\BaseService.cs`

```csharp
private PageResult getPageDataByReader(PageResult pageResult)
{
    // 1. 构建参数
    string stmtId = pageResult.StatementId ?? "GetPageDataByReader";
    Hashtable param = new Hashtable(2);
    param["where"] = pageResult.ParameterObject;
    if (!string.IsNullOrWhiteSpace(pageResult.OrderString))
        param["OrderString"] = pageResult.OrderString;

    // 2. 执行查询获取 DataReader
    using (IDataReader reader = this.GetDataReaderByStatement(stmtId, param))
    {
        // 3. 计算分页起始位置
        int begin = pageResult.PageSize * (pageResult.PageIndex - 1) + 1;
        int count = 0;      // 总记录数
        int pageSize = 0;   // 当前页已添加记录数

        // 4. 创建结果表
        DataTable table = new DataTable();
        for (int i = 0; i < reader.FieldCount; i++)
        {
            DataColumn col = new DataColumn(reader.GetName(i), reader.GetFieldType(i));
            table.Columns.Add(col);
        }

        // 5. 遍历所有数据，内存分页（核心！）
        while (reader.Read())
        {
            count++;
            if (isAddRowForPageData(pageResult.PageSize, count, pageResult.PageIndex, pageSize))
            {
                DataRow row = table.NewRow();
                for (int i = 0; i < reader.FieldCount; i++)
                    this.dbReaderToRow(reader, row, i);
                table.Rows.Add(row);
                pageSize++;
            }
        }

        // 6. 返回结果
        reader.Close();
        pageResult.ResultDataSet = new DataSet();
        pageResult.ResultDataSet.Tables.Add(table);
        pageResult.RecordCount = count;
    }
    return pageResult;
}

// 判断当前行是否属于当前页
private bool isAddRowForPageData(int setPageSize, int totalCount, int thisPageIndex, int thisPageSize)
{
    if (setPageSize <= 0) return true;  // PageSize=0 表示不分页
    int begin = setPageSize * (thisPageIndex - 1) + 1;
    if (totalCount >= begin && thisPageSize < setPageSize)
        return true;
    return false;
}
```

#### 内存分页特点

1. **查询全部数据** — SQL 不带 ROW_NUMBER 或 LIMIT/OFFSET
2. **应用层过滤** — 遍历全部记录，只保留当前页数据
3. **统计总数** — 同时统计总记录数

| 优点 | 缺点 |
|------|------|
| 实现简单，SQL 编写方便 | 大数据量时性能较差 |
| 支持复杂查询和关联 | 每次分页都要查询全部数据 |

> 特殊用法：`PageIndex = 0, PageSize = 0` 表示不分页，查询全部数据（用于导出）。

### 六、SQL 映射（SsbUser.xml 范例）

**文件位置：** `P.Main\Wongoing.Main.Mapper\BusinessMapper\SsbUser.xml`

```xml
<select id="GetAllUserList" parameterClass="map" resultClass="row">
    SELECT T1.OBJID, T1.USER_NAME, T1.REAL_NAME, T2.SEX_NAME AS SEX,
           T1.TELEPHONE, T1.WORK_BARCODE, T3.DEPT_NAME AS DEPT_ID,
           T4.WORK_NAME AS WORK_ID, T5.SHIFT_NAME AS SHIFT_ID,
           T6.CLASS_NAME AS CLASS_ID, T7.WORKSHOP_NAME AS WORKSHOP_ID,
           T8.YES_NO_NAME AS IS_EMPLOYEE, loginprohibited as LENPWD,
           T1.DELETE_FLAG, T1.LANG, T1.MATERSTOCKALARM
    FROM SSB_USER T1 with(nolock)
    LEFT JOIN SSB_SEX       T2 with(nolock) ON T1.SEX = T2.SEX_CODE
    LEFT JOIN SSB_DEPT      T3 with(nolock) ON T1.DEPT_ID = T3.DEPT_CODE
    LEFT JOIN SSB_WORK      T4 with(nolock) ON T1.WORK_ID = T4.WORK_CODE
    LEFT JOIN SSB_SHIFT     T5 with(nolock) ON T1.SHIFT_ID = T5.SHIFT_CODE
    LEFT JOIN SSB_CLASS     T6 with(nolock) ON T1.CLASS_ID = T6.CLASS_CODE
    LEFT JOIN SSB_WORKSHOP  T7 with(nolock) ON T1.WORKSHOP_ID = T7.WORKSHOP_CODE
    LEFT JOIN SSB_YES_NO    T8 with(nolock) ON T1.IS_EMPLOYEE = T8.OBJID
    <dynamic prepend="WHERE">
        <isNotNull property="where.USER_NAME" prepend="AND">
            T1.USER_NAME like '%'+#where.USER_NAME#+'%'
        </isNotNull>
        <isNotNull property="where.WORK_BARCODE" prepend="AND">
            T1.WORK_BARCODE like '%'+#where.WORK_BARCODE#+'%'
        </isNotNull>
        <isNotNull property="where.DEPT_ID" prepend="AND">
            T1.DEPT_ID = #where.DEPT_ID#
        </isNotNull>
        <isNotNull property="where.DELETE_FLAG" prepend="AND">
            T1.DELETE_FLAG = #where.DELETE_FLAG#
        </isNotNull>
        <isNotNull property="where.REAL_NAME" prepend="AND">
            T1.REAL_NAME like '%'+#where.REAL_NAME#+'%'
        </isNotNull>
    </dynamic>
    <isNotNull property="OrderString" prepend="">
        ORDER BY $OrderString$
    </isNotNull>
</select>
```

> 注意：SQL 不带分页语法（无 ROW_NUMBER/OFFSET），分页由 C# 端 `getPageDataByReader` 遍历 DataReader 实现。

### 七、数据流程

```text
用户点击分页
    ↓
Ext.NET Store 发送请求
    ↓
PageProxy 调用 DirectMethod GridPanelBindData(action, extraParams)
    ↓
解析 StoreRequestParameters (Page, Limit)
    ↓
构建 PageResult 对象
    ↓
userManager.GetPageDataByReader(pageResult)
    ↓
BaseService.getPageDataByReader(pageResult)
    ↓
执行 SQL 查询 (StatementId)
    ↓
遍历 DataReader，内存分页
    ↓
返回 PageResult (含 data 和 total)
    ↓
前端 Store 绑定数据，更新 UI
```

### 八、关键文件清单

| 文件路径 | 说明 |
|---------|------|
| `Plugins/Main/SysUser/UserInfo.aspx(.cs)` | 完整范例页面（前端+后端） |
| `Wongoing.Main.Mapper/BusinessMapper/SsbUser.xml` | SQL 映射范例 |
| `Frame/Wongoing.DbAccess/DbHelper/PageResult.cs` | 分页实体类 |
| `Frame/Wongoing.DbAccess/BaseService.cs` | 分页实现核心类 |
| `Frame/Wongoing.DbAccess/BaseManager.cs` | 业务层基类（GetPageDataByReader） |

### 九、关联

- DirectMethod 与数据访问三件套：见 `extnet-directmethod-and-data.md`
- GridPanel 完整用法（含分页工具栏）：见 `extnet-grid-complete-guide.md`
- 动态列 Grid（也用 PageProxy 分页）：见 `dynamic-column-grid.md`
- 客户端分页 / 服务端分页踩坑：见 方案一、方案二

