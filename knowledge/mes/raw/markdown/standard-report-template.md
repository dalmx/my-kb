---
title: 标准报表页面模板（完整版）
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, 报表模板, 标准模板]
updated: 2026-08-29
status: active
---
# 标准报表页面模板（完整版）

> **报表模板族基座**：本篇保持完整自包含；[chart-table](chart-table-report-template.md)（图表+数据表）、[summary-detail](summary-detail-report-template.md)（汇总+明细）、[dynamic-column-popup](dynamic-column-popup-report-template.md)（动态列+弹窗）为差异式变体，只列各自差异代码。（落地页 2026-08-23 双项目树验证存在）

## 一、布局结构

```text
┌─────────────────────────────────────────────────┐
│ [Toolbar]  [查询] [导出] [隐藏▲]                 │  ← Region="North" TopBar
├─────────────────────────────────────────────────┤
│  字段1[____]  字段2[____]  字段3[▼____]  字段4[▼____]  │  ← FormPanel ColumnLayout (4列×25%)
│  字段5[____]  字段6[____]  ...                    │
├─────────────────────────────────────────────────┤
│  # │ 列1 │ 列2 │ 列3 │ 列4 │ ...               │  ← GridPanel Region="Center"
│  1 │ ... │ ... │ ... │ ... │                    │
│  ────────────────────────────────────────────    │
│  [分页: < 1 2 3 4 5 >]                          │  ← PagingToolbar
└─────────────────────────────────────────────────┘
```

## 二、文件结构

每个报表由2个文件组成：
- `ReportName.aspx` — 页面UI（Ext.NET控件）
- `ReportName.aspx.cs` — 代码逻辑（C# code-behind）

## 三、参考文件
- `P.Quality/Wongoing.Quality.WebSite/Plugins/Quality/QualityQtyReport.aspx`
- `P.Quality/Wongoing.Quality.WebSite/Plugins/Quality/QualityQtyReport.aspx.cs`

## 四、ASPX模板代码

```aspx
<%@ Page Language="C#" AutoEventWireup="true" CodeFile="ReportName.aspx.cs" Inherits="Plugins_Quality_ReportName" %>

<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head runat="server">
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
    <title>报表标题</title>
    <link href="../../../resources/css/extExtra.css" rel="stylesheet" />
    <script src="../../../resources/js/default.js"></script>
    <script src="../../../resources/js/jquery-1.7.1.js"></script>
    <style type="text/css">
        .x-grid-row-summary .x-grid-cell-inner {
            font-weight: bold;
            font-size: 15px;
            background-color: #f1f2f4;
        }
    </style>
    <script type="text/javascript">
        var viewportAfterRender = function () {
            var curDate = new Date();
            App.txt_begin_date.setValue(new Date(curDate.setDate(curDate.getDate())));
            App.txt_end_date.setValue(new Date(curDate.setDate(curDate.getDate())));
        }

        var pnlListFresh = function () {
            App.direct.GetStatisticsData({
                success: function () { },
                eventMask: {
                    showMask: true,
                    target: 'customtarget',
                    customTarget: 'pnlGrid',
                }
            });
        }
    </script>
</head>
<body>
    <form id="form1" runat="server">
        <ext:ResourceManager ID="resourceManager" runat="server" />
        <asp:Button ID="btnExportSubmit" Style="display: none" runat="server" Text="Button"
            OnClick="btnExportSubmit_Click" />
        <ext:Hidden ID="exportData" runat="server" />
        <ext:Viewport ID="vwMain" runat="server" Layout="BorderLayout">
            <Items>
                <!-- ===== North: 工具栏 + 查询条件 ===== -->
                <ext:Panel ID="pnlNorth" runat="server" Region="North" Header="false">
                    <TopBar>
                        <ext:Toolbar runat="server">
                            <Items>
                                <ext:Button runat="server" IconCls="fa fa-search fabtn color-info" Text="查询" ID="btnSearch" ToolTip="点击进行查询">
                                    <Listeners>
                                        <Click Fn="pnlListFresh" />
                                    </Listeners>
                                </ext:Button>
                                <ext:ToolbarSeparator />
                                <ext:Button runat="server" IconCls="fa fa-file-excel-o fabtn color-success" Text="导出" ID="btnExport" ToolTip="导出到Excel">
                                    <Listeners>
                                        <Click Handler="$('#btnExportSubmit').click();" />
                                    </Listeners>
                                </ext:Button>
                                <ext:ToolbarSeparator />
                                <ext:Button runat="server" ID="btnPnlQuery" Cls="btnPnlQuery" Border="false"
                                    IconCls="fa fa-angle-double-up fabtn color-inverse" ToolTip="隐藏查询">
                                    <Listeners>
                                        <Click Handler="ShowHideQuery(#{btnPnlQuery},#{pnlQuery});" />
                                    </Listeners>
                                </ext:Button>
                            </Items>
                        </ext:Toolbar>
                    </TopBar>
                    <Items>
                        <ext:Panel ID="pnlQuery" runat="server" Header="false">
                            <Items>
                                <ext:FormPanel ID="container_top" runat="server" Layout="ColumnLayout" AutoHeight="true"
                                    Collapsible="false" Cls="border-top">
                                    <Items>
                                        <ext:Container ID="container1" runat="server" Layout="FormLayout" ColumnWidth=".25">
                                            <Items>
                                                <ext:DateField ID="txt_begin_date" runat="server" FieldLabel="开始日期" AllowBlank="false" LabelAlign="Right" Format="yyyy-MM-dd" />
                                                <ext:ComboBox ID="cbx_field1" runat="server" FieldLabel="下拉框1" LabelAlign="Right" Editable="false">
                                                    <Items>
                                                        <ext:ListItem Value="1" Text="选项1" />
                                                    </Items>
                                                    <Triggers>
                                                        <ext:FieldTrigger Icon="Clear" />
                                                    </Triggers>
                                                    <Listeners>
                                                        <TriggerClick Handler="if (index == 0) this.clearValue();" />
                                                    </Listeners>
                                                </ext:ComboBox>
                                            </Items>
                                        </ext:Container>
                                        <ext:Container ID="container2" runat="server" Layout="FormLayout" ColumnWidth=".25">
                                            <Items>
                                                <ext:DateField ID="txt_end_date" runat="server" FieldLabel="结束日期" AllowBlank="false" LabelAlign="Right" Format="yyyy-MM-dd" />
                                            </Items>
                                        </ext:Container>
                                        <ext:Container ID="container3" runat="server" Layout="FormLayout" ColumnWidth=".25">
                                            <Items>
                                                <!-- 更多查询字段 -->
                                            </Items>
                                        </ext:Container>
                                        <ext:Container ID="container4" runat="server" Layout="FormLayout" ColumnWidth=".25">
                                            <Items>
                                                <!-- 更多查询字段 -->
                                            </Items>
                                        </ext:Container>
                                    </Items>
                                </ext:FormPanel>
                            </Items>
                        </ext:Panel>
                    </Items>
                </ext:Panel>

                <!-- ===== Center: 数据Grid ===== -->
                <ext:GridPanel ID="pnlGrid" runat="server" Region="Center" Cls="border-top" ColumnLines="true"
                    Header="true" Title="报表标题">
                    <Store>
                        <ext:Store ID="gridStore" runat="server">
                            <Model>
                                <ext:Model ID="model" runat="server">
                                    <!-- 动态列模式：Model留空，由code-behind填充 -->
                                    <!-- 固定列模式：在此定义Fields -->
                                </ext:Model>
                            </Model>
                        </ext:Store>
                    </Store>
                    <View>
                        <ext:GridView ID="gvRows" runat="server" EnableTextSelection="true" />
                    </View>
                    <SelectionModel>
                        <ext:RowSelectionModel Mode="Single" />
                    </SelectionModel>
                    <BottomBar>
                        <ext:PagingToolbar ID="pageToolBar" runat="server" RefreshHandler="App.direct.GridPanelBindData();" />
                    </BottomBar>
                </ext:GridPanel>
            </Items>
            <Listeners>
                <AfterRender Fn="viewportAfterRender" />
            </Listeners>
        </ext:Viewport>
    </form>
</body>
</html>
```

## 五、Code-Behind模板代码（C# 5兼容）

```csharp
using System;
using System.Collections.Generic;
using System.Data;
using System.Web;
using System.Web.UI;
using System.Web.UI.WebControls;
using Ext.Net;
using Wongoing.Quality.Business.Implements;
using Wongoing.Quality.Business.Interface;
using Wongoing.Quality.Entity.BasicEntity;

public partial class Plugins_Quality_ReportName : Wongoing.Web.UI.Page
{
    private IFqfFcheckInfoManager manage = new FqfFcheckInfoManager();

    #region 权限定义
    protected __ _ = new __();
    public class __ : Wongoing.Web.UI.___
    {
        public __()
        {
            查询 = new PageAction() { ActionId = 1, ActionName = "btnSearch" };
            导出 = new PageAction() { ActionId = 2, ActionName = "btnExport" };
        }
        public PageAction 查询 { get; private set; }
        public PageAction 导出 { get; private set; }
    }
    #endregion

    protected void Page_Load(object sender, EventArgs e)
    {
        if (!X.IsAjaxRequest)
        {
            // 初始化下拉框数据源
        }
    }

    [DirectMethod(Timeout = 180000)]
    public void GetStatisticsData()
    {
        try
        {
            var param = new Dictionary<string, object>() {
                { "BEGIN_DATE", txt_begin_date.RawText },
                { "END_DATE", txt_end_date.RawText }
            };
            DataTable data = manage.GetDataTableByStatement("StatementName@EntityName", param);
            Session["ReportData"] = data;
            ChangeModels(data);
        }
        catch (Exception ex)
        {
            X.Msg.Show(new MessageBoxConfig
            {
                Title = "错误",
                Message = ex.Message,
                Icon = MessageBox.Icon.ERROR,
                Buttons = MessageBox.Button.OK
            });
        }
    }

    private void ChangeModels(DataTable dt)
    {
        Store store = this.gridStore;
        GridPanel grid = this.pnlGrid;
        store.Reader.Clear();
        grid.ColumnModel.Columns.RemoveRange(0, grid.ColumnModel.Columns.Count);
        store.Model.Clear();

        Model model = new Model();
        for (int i = 0; i < dt.Columns.Count; i++)
        {
            model.Fields.Add(new ModelField(new ModelField.Config
            {
                Name = "col" + i.ToString(),
                Mapping = dt.Columns[i].ColumnName,
                ServerMapping = dt.Columns[i].ColumnName
            }));
            grid.ColumnModel.Columns.Add(new Column
            {
                Text = dt.Columns[i].ColumnName,
                DataIndex = "col" + i.ToString(),
                Width = 100,
                Sortable = true
            });
        }
        store.Model.Add(model);
        store.DataSource = dt;
        store.DataBind();
        grid.Render();
    }

    protected void btnExportSubmit_Click(object sender, EventArgs e)
    {
        DataTable dt = (DataTable)Session["ReportData"];
        string sname = "报表名称";
        dt.TableName = sname;
        new Wongoing.Utility.Excel.ExcelDownload().ExcelFileDown(dt, sname);
    }
}
```

## 六、关键模式说明

### 两种列模式
1. **固定列**：ASPX中预定义Fields和Columns，适合列固定的报表
2. **动态列**：由`ChangeModels()`根据DataTable自动生成，适合交叉统计报表

### 数据查询
- `manage.GetDataTableByStatement("StatementName@EntityName", param)`
- StatementName = BusinessMapper XML中的select id
- param = Dictionary<string, object>

### 导出流程
1. 查询时DataTable存入Session
2. JS触发隐藏asp:Button
3. code-behind从Session取数据，`ExcelDownload().ExcelFileDown()`导出

### 查询面板折叠
- `ShowHideQuery(btn, panel)` 定义在default.js

### C#语法约束
- 禁止使用 ?.、??、$"" 等C# 6.0+语法
- 使用传统null检查和string.Format
