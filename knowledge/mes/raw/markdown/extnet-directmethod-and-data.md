---
title: Ext.NET DirectMethod 全风格 + 数据访问三件套
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, DirectMethod, 数据访问, GetDataTableByStatement, ExtraParams, Session缓存, Page_Load, 复刻手册]
status: active
updated: 2026-08-29
---
# Ext.NET DirectMethod 全风格 + 数据访问三件套

> 本文覆盖 Semi 项目后台与前台交互的全部标准写法：DirectMethod 的三种返回值风格、ExtraParams 参数传递、数据访问三件套（GetDataTableByStatement / GetDataSetByStatement / GetObjectByStatement+事务）、Session 缓存复用模式。分页回调的细节见分页系列文档，本文聚焦"调用约定"。

## 一、DirectMethod 三种返回值风格

### 风格 A：返回 string（成功返回空，失败返回错误消息）

```csharp
[DirectMethod]
public string LoadBillItem(string MaterialCode)
{
    try
    {
        var param = new Dictionary<string, object> {
            {"MaterialCode", MaterialCode}
        };
        var billdata = hppSemisProductionManager.GetDataTableByStatement("SemisProductionClassDetail@HppSemisProduction", param);
        if (billdata.Rows.Count > 0)
        {
            pnlMainStore.DataSource = billdata;
            pnlMainStore.DataBind();
        }
        return "";   // 空字符串表示成功
    }
    catch (Exception ex)
    {
        return ex.Message;   // 前端在 failure 回调里弹错
    }
}
```

### 风格 B：返回 void（直接绑 Store，异常用 X.Msg.Show 提示）

```csharp
[DirectMethod(Timeout = 180000)]   // 长超时（3分钟），适用于慢查询
public void GetStatisticsData()
{
    try
    {
        var param = new Dictionary<string, object> {
            {"Start_day", txt_Start_day.RawText.ToString()},
            {"End_day",   txt_End_day.RawText.ToString()}
        };
        var data = hppSemisProductionManager.GetDataTableByStatement("SemisProductionClass@HppSemisProduction", param);
        Session["seldata"] = data;
        storeBill.DataSource = data;
        storeBill.DataBind();
    }
    catch (Exception ex)
    {
        X.Msg.Show(new MessageBoxConfig {
            Title = GetGlobalResourceObject("Semi","错误").ToString(),
            Message = ex.Message,
            Icon = MessageBox.Icon.ERROR,
            Buttons = MessageBox.Button.OK
        });
        return;
    }
}
```

### 风格 C：返回 object（匿名对象序列化，用于传多表）

```csharp
[DirectMethod]
public object GetData()
{
    DataSet ds = planManager.GetDataSetByStatement("SelectPlanAnalyseByMaterial@HppPlan", param);
    var result = new {
        production = ds.Tables[0],
        summary    = ds.Tables[1]
    };
    return result;   // Ext.NET 自动序列化为 JSON
}
```

> 也可手动 `return JSON.Serialize(result);` 返回字符串。

### PageProxy 翻页回调（特殊签名）

这是分页专用的 DirectMethod 签名，与上面三种不同（必须接 `action` 和 `extraParams`）：

```csharp
[DirectMethod]
public object GridPanelBindData(string action, Dictionary<string, object> extraParams)
{
    StoreRequestParameters prms = new StoreRequestParameters(extraParams);
    var pageResult = new PageResult();
    pageResult.PageIndex = prms.Page;    // 当前页码（0基）
    pageResult.PageSize  = prms.Limit;   // 每页条数

    pageResult = GridPanelBindData(pageResult);   // 调业务逻辑

    var data  = pageResult.ResultDataSet.Tables[0];
    var total = pageResult.RecordCount;
    return new { data, total };   // 必须返回 data + total
}
```

## 二、前台调用 DirectMethod 的标准写法

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

要点：
- `App.direct.方法名({...})` —— 方法名与 C# 的 `[DirectMethod]` 方法名一致。
- `eventMask.showMask: true` 显示遮罩；`target: 'customtarget'` 指定遮罩范围（如某个 Panel 的 ID）。
- 传参直接写在方法名括号里：`App.direct.LoadBillItem("M001", {success:..., failure:...})`。

## 三、DirectEvents + ExtraParams（按钮声明式传值）

按钮 `<DirectEvents><Click>` 触发服务端事件方法，用 `<ExtraParams>` 传前端值：

```aspx
<ext:Button ID="BtnAddSave" runat="server" Text="确定">
    <DirectEvents>
        <Click OnEvent="BtnAddSave_Click">
            <ExtraParams>
                <ext:Parameter Name="values" Mode="Raw" Encode="false"
                               Value="#{fp_newArea}.getForm().getValues()" />
            </ExtraParams>
        </Click>
    </DirectEvents>
</ext:Button>
```

后台接收：

```csharp
protected void BtnAddSave_Click(object sender, DirectEventArgs e)
{
    string json = e.ExtraParams["values"];
    // 反序列化为字典数组或对象
    Dictionary<string, string>[] rows = JSON.Deserialize<Dictionary<string, string>[]>(json);
    // 也可以反序列化为单对象
    // var formValues = JSON.Deserialize<Dictionary<string, string>>(json);
}
```

### GridPanel 多选行传到后台

```aspx
<ext:Button ID="btnExport" runat="server" Text="导出选中">
    <DirectEvents>
        <Click OnEvent="btnExport_Click">
            <ExtraParams>
                <ext:Parameter Name="Values" Value="#{pnlList}.getRowsValues({ selectedOnly : true })"
                               Mode="Raw" Encode="true" />
            </ExtraParams>
        </Click>
    </DirectEvents>
</ext:Button>
```
```csharp
protected void btnExport_Click(object sender, DirectEventArgs e)
{
    string json = e.ExtraParams["Values"];
    Dictionary<string, string>[] rows = JSON.Deserialize<Dictionary<string, string>[]>(json);
    // rows[i]["ColumnName"] 取值
}
```

> `Encode="true"` 对 JSON 字符串做编码传输；`getRowsValues({ selectedOnly: true })` 只取选中行。详见 `chart-table-report-template.md`。

## 四、数据访问三件套

所有数据访问统一通过业务 Manager 接口，statement id 格式为 `"名称@Manager名"`。Manager 作为类字段声明：

```csharp
private IHppSemisProductionManager hppSemisProductionManager = new HppSemisProductionManager();
protected ISsbClassManager classManager = new SsbClassManager();
```

### 4.1 GetDataTableByStatement（单表查询，最常用）

```csharp
var param = new Dictionary<string, object> {
    {"Start_day", txt_Start_day.RawText.ToString()},
    {"End_day",   txt_End_day.RawText.ToString()},
    {"Class",     cbxGroup.Value.ToString()},
    {"MATERIAL_CODE", ""}
};
var data = hppSemisProductionManager.GetDataTableByStatement("SemisProductionClass@HppSemisProduction", param);
```

> 参数 Dictionary 的 key 必须与 iBATIS mapper XML 中的 `#PARAM#` 占位符一致。

### 4.2 GetDataSetByStatement（多表查询，返回多个 DataTable）

```csharp
DataSet ds = planManager.GetDataSetByStatement("SelectPlanAnalyseByMaterial@HppPlan", param);
DataTable production = ds.Tables[0];   // 第一张表
DataTable summary    = ds.Tables[1];   // 第二张表
Session["materialData"] = production;
Session["allData"]      = summary;
```

### 4.3 GetObjectByStatement + 事务（带输出参数的存储过程）

存储过程有 `MSG` 等输出参数回填结果时，必须用事务包起来：

```csharp
planManager.BeginTransaction();
var param = new Dictionary<string, string> {
    {"PLAN_DATE",   plan_date.RawText ?? ""},
    {"MODIFY_USER", Data.User.UserBarcode.ToString()},
    {"MSG", ""}                       // 输出参数，存储过程回填
};
planManager.GetObjectByStatement("AnalysePlan@HppPlan", param);

if (!string.IsNullOrWhiteSpace(param["MSG"]))
{
    planManager.RollbackTransaction();
    X.Msg.Alert("提示", param["MSG"]).Show();
    return;
}
planManager.CompleteTransaction();
```

### 4.4 下拉框数据源（Hashtable + where 子字典）

```csharp
var sbeEquipList = equipManager.GetDataTableByStatement("SelectSbeEquip@SbeEquip", new Hashtable {
    { "where", new Dictionary<string, string> { { "WORK_SHOP", "02" } } }
});
txtEquip.GetStore().DataSource = sbeEquipList;
txtEquip.GetStore().DataBind();   // ⚠️ Ext.NET 必须手动 DataBind()
```

### 4.5 实体列表查询（GetEntityList）

```csharp
var classList = classManager.GetEntityList(new SsbClass { DeleteFlag = 0 }, "OBJID");
foreach (var cl in classList)
    cbxGroup.Items.Add(new Ext.Net.ListItem(cl.ClassName, cl.ClassCode));
```

## 五、Session 缓存复用模式

**标准模式**：查询时把 param 和 data 都存 Session，导出时回读 param 重新查询（保证一致性，避免列名被改污染）。

### 查询时缓存

```csharp
[DirectMethod]
public void storeBill_ReadData()
{
    var param = new Dictionary<string, object> {
        {"Start_day", txt_Start_day.RawText.ToString()},
        {"End_day",   txt_End_day.RawText.ToString()}
    };
    Session["inspara"] = param;   // 缓存查询参数

    var data = hppSemisProductionManager.GetDataTableByStatement("SemisProductionClass@HppSemisProduction", param);
    if (data.Rows.Count > 0)
    {
        storeBill.DataSource = data;
        storeBill.DataBind();
        Session["seldata"] = data;   // 缓存结果（可选）
    }
}
```

### 导出时回读参数重新查（推荐）

```csharp
protected void btnExportSubmit_Click(object sender, EventArgs e)
{
    var selPara = (Dictionary<string, object>)Session["inspara"];
    var data = hppSemisProductionManager.GetDataTableByStatement("SemisProductionClass@HppSemisProduction", selPara);
    // 改列名 → ExcelFileDown（见 extnet-export-i18n-error.md）
}
```

> 也可以直接用缓存的 `Session["seldata"]`，但如果导出前对 DataTable 改了列名，下次再用会被污染。重新查最安全。

## 六、Page_Load 标准结构

```csharp
public partial class Plugins_Semi_Report_MyPage : Wongoing.Web.UI.Page
{
    private IHppSemisProductionManager hppSemisProductionManager = new HppSemisProductionManager();
    protected ISsbClassManager classManager = new SsbClassManager();

    protected void Page_Load(object sender, EventArgs e)
    {
        if (!X.IsAjaxRequest)   // ⚠️ Ext.NET AJAX 回发不进入此块
        {
            // 1) 默认日期
            this.txt_Start_day.SelectedDate = DateTime.Now;
            this.txt_End_day.SelectedDate   = DateTime.Now;
            // 2) 初始下拉绑定
            InitGroup();
        }
    }

    private void InitGroup()
    {
        var classList = classManager.GetEntityList(new SsbClass { DeleteFlag = 0 }, "OBJID");
        foreach (var cl in classList)
            cbxGroup.Items.Add(new Ext.Net.ListItem(cl.ClassName, cl.ClassCode));
    }
}
```

要点：
- **必须用 `!X.IsAjaxRequest`** 而不是 `!IsPostBack`——Ext.NET 的 DirectMethod/DirectEvents 是 AJAX 请求，会跳过 `!IsPostBack` 但也会跳过 `!X.IsAjaxRequest` 吗？不会。`X.IsAjaxRequest` 在 Ext.NET AJAX 请求时为 true，所以 `!X.IsAjaxRequest` 只在首次完整页面加载时进入。
- 首次加载绑定下拉时，部分场景额外加 `&& !IsPostBack` 双重判断。
- Ext.NET 绑定 Store **必须手动调 `DataBind()`**（`store.DataSource = dt; store.DataBind();`）。

## 七、完整后台代码骨架

```csharp
using System;
using System.Collections.Generic;
using System.Data;
using Ext.Net;

namespace Wongoing.Semi.WebSite
{
    public partial class Plugins_Semi_Report_MyPage : Wongoing.Web.UI.Page
    {
        #region 权限定义
        protected __ _ = new __();
        public class __ : Wongoing.Web.UI.___
        {
            public __()
            {
                查询 = new PageAction() { ActionId = 1, ActionName = "btn_search" };
                导出 = new PageAction() { ActionId = 2, ActionName = "btnExport" };
            }
            public PageAction 查询 { get; private set; }
            public PageAction 导出 { get; private set; }
        }
        #endregion

        private IHppSemisProductionManager hppSemisProductionManager = new HppSemisProductionManager();

        protected void Page_Load(object sender, EventArgs e)
        {
            if (!X.IsAjaxRequest)
            {
                this.txt_Start_day.SelectedDate = DateTime.Now;
                this.txt_End_day.SelectedDate = DateTime.Now;
            }
        }

        [DirectMethod]
        public object GridPanelBindData(string action, Dictionary<string, object> extraParams)
        {
            StoreRequestParameters prms = new StoreRequestParameters(extraParams);
            var param = new Dictionary<string, object> {
                {"Start_day", txt_Start_day.RawText.ToString()},
                {"End_day",   txt_End_day.RawText.ToString()}
            };
            Session["inspara"] = param;
            var data = hppSemisProductionManager.GetDataTableByStatement("MyQuery@HppSemisProduction", param);
            return new { data, total = data.Rows.Count };
        }

        protected void btnExportSubmit_Click(object sender, EventArgs e)
        {
            var selPara = (Dictionary<string, object>)Session["inspara"];
            var data = hppSemisProductionManager.GetDataTableByStatement("MyQuery@HppSemisProduction", selPara);
            // 改列名 + 导出（见 extnet-export-i18n-error.md）
        }
    }
}
```

## 八、关联文档

| 文档 | 关系 |
|------|------|
| `extnet-event-mechanisms.md` | DirectMethod / DirectEvents / Listeners 三者对比 |
| `extnet-export-i18n-error.md` | 导出/资源化/错误处理的详细写法 |
| `extnet-page-skeleton.md` | 前端骨架与 Store 配置 |
| `extnet-pagination-guide.md` | PageProxy 翻页 DirectMethod + Session 切片方案 |
| `extnet-pagination-guide.md` | 客户端分页（无翻页 DirectMethod） |
| `extnet-pagination-guide.md` | RemotePaging 概念辨析 |
| `button-permission.md` | 权限类 PageAction 定义 |
