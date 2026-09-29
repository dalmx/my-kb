---
title: Ext.NET 事件机制对比：DirectMethod vs DirectEvents vs Listeners
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, DirectMethod, DirectEvents, Listeners, 事件机制, 对比, 复刻手册]
status: active
updated: 2026-08-29
---
# Ext.NET 事件机制对比：DirectMethod vs DirectEvents vs Listeners

> Semi 项目三种事件写法并存，分工明确但极易混淆。本文系统对比三者差异、适用场景、典型写法，帮助快速判断"该用哪个"。项目统计：DirectEvents 出现 28 个文件，Listeners 出现 61 个文件，DirectMethod 几乎每个 `.aspx.cs` 都有。

## 一、三者速查对比表

| 维度 | DirectMethod | DirectEvents | Listeners |
|------|-------------|--------------|-----------|
| **执行位置** | 服务端（C#） | 服务端（C#） | 客户端（JS） |
| **触发方式** | JS 主动调 `App.direct.方法名` | 标签声明 `<Click OnEvent="方法名">` | 标签声明 `Handler="JS代码"` 或 `Fn="函数名"` |
| **通信方式** | AJAX（带回调） | PostBack/AJAX（声明式） | 纯前端（不走服务器） |
| **适合场景** | 增删改、复杂业务逻辑、需要 C# 数据 | 表单提交、按钮触发刷新、需要 PostBack 生命周期 | UI 交互、校验、跳转、清空、回车搜索 |
| **参数传递** | 方法参数直接传 | `<ExtraParams>` 声明 | 无（纯前端） |
| **回调** | success/failure | success/failure（在标签里配） | 无（同步执行） |
| **性能** | 每次一次 AJAX | 每次一次 AJAX | 无网络开销 |
| **项目使用** | 每个 `.aspx.cs` 必有 | 28/64 页面 | 61/64 页面 |

## 二、DirectMethod（JS 主动调 C#）

### 本质
C# 方法标 `[DirectMethod]` 特性，暴露为前端可调的 `App.direct.方法名`。前端 JS 通过 AJAX 调用，可传参、可带 success/failure 回调。

### 前端调用
```js
var pnlListFresh = function () {
    App.direct.GetStatisticsData({
        success: function () { },
        failure: function (errorMsg) {
            Ext.Msg.alert('错误', errorMsg);
        },
        eventMask: { showMask: true, target: 'customtarget', customTarget: 'mainTabPanel' }
    });
};
```

### 后端定义
```csharp
[DirectMethod]   // 或 [Ext.Net.DirectMethod()]
public void GetStatisticsData()
{
    try {
        var data = hppSemisProductionManager.GetDataTableByStatement("MyQuery@HppSemisProduction", param);
        store.DataSource = data;
        store.DataBind();
    }
    catch (Exception ex) {
        X.Msg.Show(new MessageBoxConfig { ... }); return;
    }
}
```

### 带参数调用
```js
// 传单个参数
App.direct.commandcolumn_direct_delete(objId, {
    success: function (result) { Ext.Msg.alert('操作', result); pageToolBar.doRefresh(); },
    failure: function (msg) { Ext.Msg.alert('错误', msg); }
});
```

### 什么时候用 DirectMethod？
- ✅ 增删改操作（需要执行 C# 业务逻辑）
- ✅ 复杂查询后刷新表格
- ✅ 需要从 JS 动态传参到 C#（参数值在运行时才确定）
- ❌ 不适合纯 UI 操作（如清空输入框、跳转页面）

> 详见 `extnet-directmethod-and-data.md`。

## 三、DirectEvents（标签声明绑定 C# 事件）

### 本质
在 aspx 标签里声明 `<DirectEvents><事件名 OnEvent="C#方法名">`，当事件触发时自动以 PostBack/AJAX 方式调用 C# 方法。参数通过 `<ExtraParams>` 传递。

### 前端声明
```aspx
<ext:Button ID="btn_add" runat="server" Text="添加" Hidden="true">
    <DirectEvents>
        <Click OnEvent="btn_add_Click"></Click>
    </DirectEvents>
</ext:Button>

<!-- 带 ExtraParams -->
<ext:Button ID="btnExport" runat="server" Text="导出">
    <DirectEvents>
        <Click OnEvent="btnExportSubmit_Click">
            <ExtraParams>
                <ext:Parameter Name="Values" Value="#{pnlList}.getRowsValues({ selectedOnly : true })"
                               Mode="Raw" Encode="true" />
            </ExtraParams>
        </Click>
    </DirectEvents>
</ext:Button>
```

### 后端定义
```csharp
protected void btn_add_Click(object sender, DirectEventArgs e)
{
    winAdd.Show();   // 打开编辑窗
}

protected void btnExportSubmit_Click(object sender, DirectEventArgs e)
{
    string json = e.ExtraParams["Values"];
    Dictionary<string, string>[] rows = JSON.Deserialize<Dictionary<string, string>[]>(json);
    // 导出逻辑...
}
```

### 什么时候用 DirectEvents？
- ✅ 按钮点击触发提交/刷新（声明式，代码简洁）
- ✅ 需要传选中行/表单值到后台（配合 `getRowsValues` / `getForm().getValues()`）
- ✅ 需要 PostBack 生命周期（服务端控件状态保持）
- ❌ 不适合参数在 JS 里动态计算的复杂逻辑（用 DirectMethod 更灵活）

### DirectEvents vs DirectMethod 的传值差异

| | DirectEvents | DirectMethod |
|--|-------------|--------------|
| 前端取值 | `<ExtraParams Value="#{控件ID}.方法()">` | `App.direct.方法(参数)` |
| 后端接值 | `e.ExtraParams["键"]`（字符串） | 方法参数（强类型） |

## 四、Listeners（纯客户端 JS）

### 本质
在 aspx 标签里声明 `<Listeners><事件名 Handler="JS代码" />` 或 `Fn="函数名"`，触发时执行纯前端 JS，不走服务器。

### 写法 A：Handler 内联
```aspx
<!-- 回车搜索 -->
<ext:TextField ID="txt_search" runat="server" FieldLabel="搜索" EmptyText="输入后回车">
    <Listeners>
        <SpecialKey Handler="if (e.getKey() === Ext.EventObject.ENTER) { Search(); return false; }" />
    </Listeners>
</ext:TextField>

<!-- 关闭弹窗 -->
<ext:Button runat="server" Text="取消">
    <Listeners><Click Handler="#{winAdd}.close();" /></Listeners>
</ext:Button>

<!-- 查询按钮触发刷新 -->
<ext:Button ID="btn_search" runat="server" Text="<%$Resources:Semi,查询 %>">
    <Listeners><Click Fn="pnlListFresh" /></Listeners>
</ext:Button>
```

### 写法 B：Fn 引用外部函数
```aspx
<ext:Button ID="btn_search" runat="server" Text="查询">
    <Listeners><Click Fn="pnlListFresh" /></Listeners>
</ext:Button>
```
```js
var pnlListFresh = function () {
    App.direct.GetStatisticsData({ ... });   // 再通过 DirectMethod 调后台
};
```

> 注意：`Fn="pnlListFresh"` 引用的函数通常内部再调 `App.direct.xxx`——这是"前端事件 → 转发到服务端"的常见链路。

### 常用 Listeners 事件

| 控件 | 事件 | 用途 |
|------|------|------|
| TextField | `SpecialKey` | 回车触发搜索 |
| Button | `Click` | 触发 JS / 转发 DirectMethod |
| GridPanel Column | `Command` | 行命令点击 |
| Window | `Close` | 窗口关闭后回调 |
| Store | `BeforeLoad` | 加载前注入参数（⚠️ 慎用，会破坏正常绑定，见 `extnet-pagination-guide.md`） |
| Field | `TriggerClick` | 清空触发器点击 |
| ComboBox | `Select` | 选中后联动 |
| 任意控件 | `AfterRender` | 渲染后初始化 |

### 清空触发器（FieldTrigger + TriggerClick）
```aspx
<ext:ComboBox ID="cbb_size" runat="server" FieldLabel="规格" ValueField="SizeCode" DisplayField="SizeName">
    <Triggers><ext:FieldTrigger Icon="Clear" /></Triggers>
    <Listeners>
        <TriggerClick Handler="if (index == 0) this.clearValue();" />
    </Listeners>
</ext:ComboBox>
```

### 什么时候用 Listeners？
- ✅ 纯 UI 交互（清空、关闭、跳转、显隐）
- ✅ 回车搜索、焦点控制
- ✅ 行命令分发（先 JS 判断，再转发 DirectMethod）
- ❌ 不适合需要 C# 数据的操作（改用 DirectMethod/DirectEvents）

## 五、典型组合链路

### 链路 A：查询按钮 → DirectMethod（最常见）
```text
按钮 Click Listener → JS 函数 → App.direct.DirectMethod → C# 查询绑 Store
```
```aspx
<ext:Button ID="btn_search"><Listeners><Click Fn="pnlListFresh" /></Listeners></ext:Button>
```
```js
var pnlListFresh = function () {
    App.direct.GetStatisticsData({ success: function(){}, failure: function(msg){ Ext.Msg.alert('错误', msg); } });
};
```

### 链路 B：导出按钮 → DirectEvents（带 ExtraParams）
```text
按钮 Click DirectEvents → C# 事件方法（读 Session/ExtraParams）→ 导出 Excel
```
```aspx
<ext:Button ID="btnExport"><DirectEvents><Click OnEvent="btnExportSubmit_Click"></Click></DirectEvents></ext:Button>
```

### 链路 C：行命令 → Listener 分发 → DirectMethod
```text
ImageCommandColumn Command Listener → JS 判断 command 名 → App.direct.DirectMethod
```
```aspx
<ext:ImageCommandColumn>
    <Listeners><Command Handler="return commandcolumn_click(command, record);" /></Listeners>
</ext:ImageCommandColumn>
```
```js
var commandcolumn_click = function (command, record) {
    if (command == 'Edit') {
        App.direct.commandcolumn_direct_edit(record.get("ObjID"), { ... });
    }
};
```

### 链路 D：表单提交 → DirectEvents（传表单值）
```text
按钮 Click DirectEvents → ExtraParams 取表单 getValues → C# 反序列化
```
```aspx
<ext:Button ID="BtnAddSave">
    <DirectEvents><Click OnEvent="BtnAddSave_Click">
        <ExtraParams>
            <ext:Parameter Name="values" Mode="Raw" Encode="false"
                           Value="#{fp_newArea}.getForm().getValues()" />
        </ExtraParams>
    </Click></DirectEvents>
</ext:Button>
```

## 六、决策流程图

```text
需要执行 C# 业务逻辑？
├─ 是 → 参数在运行时动态确定？
│       ├─ 是 → 用 DirectMethod（JS 调 App.direct.xxx）
│       └─ 否 → 用 DirectEvents（标签声明 OnEvent）
└─ 否（纯 UI） → 用 Listeners（Handler/Fn）
```

## 七、关联文档

| 文档 | 关系 |
|------|------|
| `extnet-directmethod-and-data.md` | DirectMethod 的三种返回值 + ExtraParams 详解 |
| `extnet-page-skeleton.md` | 按钮事件在标准骨架中的位置 |
| `extnet-grid-complete-guide.md` | 行命令 Command Listener 的用法 |
| `extnet-export-i18n-error.md` | DirectEvents 导出按钮 + ExtraParams |
| `extnet-pagination-guide.md` | Listeners BeforeLoad 的坑（慎用） |
| `extnet-row-highlight-expiry.md` | Fn 引用函数位置的坑 |
| `extnet-desktop-framework-guide.md` | Handler 内联引号转义的坑 |
