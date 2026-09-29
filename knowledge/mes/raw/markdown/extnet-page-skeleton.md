---
title: Ext.NET 页面标准骨架与布局容器组合
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, 页面骨架, BorderLayout, 布局容器, Viewport, 复刻手册, 分割条, Split, Splitter]
status: active
updated: '2026-09-23'
---
# Ext.NET 页面标准骨架与布局容器组合

> 部材/半制品（Semi）MES 项目中所有报表、CRUD 页面共用的"起手式"。64 个页面统计：BorderLayout 61/64、FormLayout 56/64、ColumnLayout 53/64、FitLayout 32/64、VBoxLayout 25/64、HBoxLayout 24/64。本文给出可照搬的完整骨架与各布局用法，目标是"换数据源即可复刻一个新页面"。

## 一、标准页面骨架（四段式 BorderLayout）

所有页面统一为 **Viewport(BorderLayout) = North(Toolbar + 查询 FormPanel) + Center(GridPanel) + 隐藏 Window**。这是最常见的"查询→列表→编辑"结构。

```text
Viewport (Layout="BorderLayout")
├─ Panel Region="North" AutoHeight="true"            ← 顶部区
│   ├─ TopBar > Toolbar                                ← 操作按钮（增删改查导出）
│   └─ Items > Panel > FormPanel(Layout="ColumnLayout")  ← 查询条件表单
│        ├─ Container Layout="FormLayout" ColumnWidth=".25"  ← 字段列1
│        ├─ Container Layout="FormLayout" ColumnWidth=".25"  ← 字段列2
│        └─ ...
├─ GridPanel Region="Center"                           ← 主数据列表
│   └─ BottomBar > PagingToolbar                        ← 分页
└─ Window Hidden="true" Modal="true" Layout="FitLayout" ← 弹窗编辑窗
```

### 完整最小骨架（可直接复制改造）

```aspx
<%@ Page Language="C#" AutoEventWireup="true" CodeBehind="MyPage.aspx.cs" Inherits="Plugins_Semi_Report_MyPage" %>
<%@ Register Assembly="Ext.Net" Namespace="Ext.Net" TagPrefix="ext" %>

<!DOCTYPE html>
<html>
<head runat="server"><title>我的页面</title></head>
<body>
<ext:ResourceManager ID="resourceManager" runat="server" />
<ext:Viewport ID="vwUnit" runat="server" Layout="BorderLayout">
  <Items>
    <%-- ===== North：工具栏 + 查询条件 ===== --%>
    <ext:Panel ID="pnlUnitTitle" runat="server" Region="North" AutoHeight="true">
      <TopBar>
        <ext:Toolbar runat="server" ID="barUnit">
          <Items>
            <ext:Button ID="btn_search" runat="server" Text="<%$Resources:Semi,查询 %>">
              <Listeners><Click Fn="pnlListFresh" /></Listeners>
            </ext:Button>
            <ext:Button ID="btnExport" runat="server" Text="<%$Resources:Semi,导出 %>" Hidden="true">
              <DirectEvents><Click OnEvent="btnExportSubmit_Click"></Click></DirectEvents>
            </ext:Button>
          </Items>
        </ext:Toolbar>
      </TopBar>
      <Items>
        <ext:Panel ID="pnlUnitQuery" runat="server" AutoHeight="true">
          <Items>
            <ext:FormPanel ID="container_top" runat="server" Layout="ColumnLayout" AutoHeight="true" Cls="border-top">
              <Items>
                <ext:Container Layout="FormLayout" ColumnWidth=".25">
                  <Items>
                    <ext:DateField ID="txt_Start_day" runat="server" FieldLabel="开始日期" LabelAlign="Right" AllowBlank="false" Type="Date" Format="yyyy-MM-dd" />
                  </Items>
                </ext:Container>
                <ext:Container Layout="FormLayout" ColumnWidth=".25">
                  <Items>
                    <ext:DateField ID="txt_End_day" runat="server" FieldLabel="结束日期" LabelAlign="Right" AllowBlank="false" Type="Date" Format="yyyy-MM-dd" />
                  </Items>
                </ext:Container>
                <ext:Container Layout="FormLayout" ColumnWidth=".25">
                  <Items>
                    <ext:ComboBox ID="cbxGroup" runat="server" FieldLabel="班组" LabelAlign="Right" Editable="false" />
                  </Items>
                </ext:Container>
              </Items>
            </ext:FormPanel>
          </Items>
        </ext:Panel>
      </Items>
    </ext:Panel>

    <%-- ===== Center：主数据列表 ===== --%>
    <ext:GridPanel ID="pnlList" runat="server" Region="Center" Cls="border-top">
      <Store>
        <ext:Store ID="store" runat="server" PageSize="100">
          <Proxy><ext:PageProxy DirectFn="App.direct.GridPanelBindData" /></Proxy>
          <Model>
            <ext:Model ID="model" runat="server">
              <Fields>
                <ext:ModelField Name="ObjID" />
                <ext:ModelField Name="MATERIAL_CODE" />
              </Fields>
            </ext:Model>
          </Model>
        </ext:Store>
      </Store>
      <ColumnModel runat="server">
        <Columns>
          <ext:RowNumbererColumn Width="45" />
          <ext:Column DataIndex="MATERIAL_CODE" Text="物料代码" Width="120" />
        </Columns>
      </ColumnModel>
      <BottomBar>
        <ext:PagingToolbar ID="pageToolBar" runat="server">
          <Plugins><ext:ProgressBarPager runat="server" /></Plugins>
        </ext:PagingToolbar>
      </BottomBar>
    </ext:GridPanel>

    <%-- ===== 隐藏编辑窗（按需） ===== --%>
    <ext:Window ID="winAdd" runat="server" Title="编辑" Width="480" Height="300"
        Resizable="true" Hidden="true" Modal="true" Layout="FitLayout">
      <Items>
        <ext:FormPanel Layout="ColumnLayout" BodyPadding="10">...表单字段...</ext:FormPanel>
      </Items>
    </ext:Window>
  </Items>
</ext:Viewport>
</body>
</html>
```

**复刻步骤**：
1. 复制本骨架，改 `CodeBehind` / `Inherits` 为你的类名。
2. 在 FormPanel 的 Container 里加查询字段（DateField/ComboBox/TextField）。
3. GridPanel 的 Store Model 加你的字段。
4. ColumnModel 加对应列。
5. 后台实现 `GridPanelBindData` DirectMethod（见《extnet-directmethod-and-data.md》）。

## 二、各布局容器详解与适用场景

| 布局 | 用途 | 项目使用率 | 关键属性 |
|------|------|----------|---------|
| **BorderLayout** | 整页分区（North/South/East/West/Center） | 95% | `Region` 必须在子项上设；Center 区自动撑满 |
| **ColumnLayout** | 查询表单多列横排 | 83% | 子项设 `ColumnWidth=".25"`（4等分）或固定 `Width` |
| **FormLayout** | 单列内字段带 Label 对齐 | 88% | 嵌在 Container 里，与 ColumnLayout 配合 |
| **FitLayout** | 单子项撑满（Window 内放一个 FormPanel） | 50% | 只渲染第一个子项 |
| **VBoxLayout** | 垂直堆叠多面板 | 39% | 子项用 `Flex="1"` 按比例分配高度 |
| **HBoxLayout** | 水平并排多面板 | 38% | 子项用 `Flex="1"` 按比例分配宽度 |

### 关键组合模式

**① 查询表单四等分（最常见）**：ColumnLayout + 多个 Container(FormLayout, ColumnWidth=".25")
```aspx
<ext:FormPanel Layout="ColumnLayout" AutoHeight="true">
  <Items>
    <ext:Container Layout="FormLayout" ColumnWidth=".25"><Items>字段1</Items></ext:Container>
    <ext:Container Layout="FormLayout" ColumnWidth=".25"><Items>字段2</Items></ext:Container>
    <ext:Container Layout="FormLayout" ColumnWidth=".25"><Items>字段3</Items></ext:Container>
    <ext:Container Layout="FormLayout" ColumnWidth=".25"><Items>字段4</Items></ext:Container>
  </Items>
</ext:FormPanel>
```
> `ColumnWidth` 是 0~1 的小数表示占比，4 列就是 .25。也可用固定像素 `Width="200"`。

**② Center 区上下双面板**（如汇总+明细）：Center 区 Panel 用 VBoxLayout
```aspx
<ext:Panel Region="Center" Layout="VBoxLayout">
  <LayoutConfig><ext:VBoxLayoutConfig Align="Stretch" /></LayoutConfig>
  <Items>
    <ext:GridPanel ID="gridSummary" runat="server" Flex="1" Title="汇总" />
    <ext:GridPanel ID="gridDetail" runat="server" Flex="2" Title="明细" />
  </Items>
</ext:Panel>
```
代表页面：`Plugins/Semi/BasicInfo/MaterStockTime.aspx`。

**③ Center 区左右并排**：HBoxLayout
```aspx
<ext:Panel Region="Center" Layout="HBoxLayout">
  <LayoutConfig><ext:HBoxLayoutConfig Align="Stretch" /></LayoutConfig>
  <Items>
    <ext:GridPanel ID="gridLeft" runat="server" Flex="1" />
    <ext:GridPanel ID="gridRight" runat="server" Flex="1" />
  </Items>
</ext:Panel>
```

**④ TabPanel 作 Center 区**：每个 Tab 是一个 Panel（可再嵌 BorderLayout + GridPanel）
```aspx
<ext:TabPanel ID="mainTabPanel" runat="server" Region="Center" Cls="ui-tab-bar">
  <Items>
    <ext:Panel ID="pnlTab1" runat="server" Title="明细" Layout="BorderLayout">
      <Items><ext:GridPanel runat="server" Region="Center">...</ext:GridPanel></Items>
    </ext:Panel>
  </Items>
</ext:TabPanel>
```
代表页面：`Plugins/Semi/Produce/SemiProduceMaterial.aspx`。

**⑤ 上下分区+可拖分割条**（参考图/明细双区，用户自调占比）：区 Panel 用 BorderLayout，上区 North 设 `Split="true" Collapsible="true"`
```aspx
<ext:Panel runat="server" Layout="BorderLayout">
  <Items>
    <ext:Panel ID="pnlImg" runat="server" Region="North" Height="560" Hidden="true"
        Border="false" AutoScroll="true" Split="true" Collapsible="true" />
    <ext:GridPanel ID="grid" runat="server" Region="Center">...</ext:GridPanel>
  </Items>
</ext:Panel>
```
> 分割条可拖拽调上区高度、双击折叠/展开 North；上区 Hidden 时分割条自动隐去（show/hide 联动即可，无分割条单独管理）。**别在 VBox/HBox 里裸塞 ext:Splitter——官方示例库 0 例的自创写法；可拖分割条的正路就是 BorderLayout Region+Split**（同 Viewport West `Split="true"` 先例，见 [[extnet-panel-viewport-guide]]）。代表页面：`Plugins/Molding/Report/MoldShiftInspection.aspx`（安全器示意图区，2026-09-23）。

## 三、ResourceManager 配置

**项目实践：用最简形式即可，无需 Theme/IDMode 定制。**

```aspx
<ext:ResourceManager ID="resourceManager" runat="server" />
```

- 7 种写法，前两种占绝大多数：`ID="resourceManager"`（35 页）、`ID="ResourceManager1"`（10 页）。
- `Theme` 全项目未显式设置（随版本默认）。
- 仅 2 个页面用 `Locale="client"` 做客户端本地化：`<ext:ResourceManager runat="server" Locale="client" />`。
- `IDMode` / `RenderStyles` / `ScriptMode` 全项目均未配置。

**复刻结论**：每个页面放一行 `<ext:ResourceManager runat="server" />` 在 body 第一个元素即可。

## 四、Window 弹窗模式

统一用**模态 Window**（不是 Dialog 风格），服务端 `.Show()` / `.Close()` 控制：

```aspx
<ext:Window ID="winAdd" runat="server" Title="编辑" Width="480" Height="300"
    Resizable="true" Hidden="true" Modal="true" Closable="true" Layout="FitLayout">
  <Items>
    <ext:FormPanel Layout="ColumnLayout" BodyPadding="10">
      <Items>...表单字段...</Items>
    </ext:FormPanel>
  </Items>
  <Buttons>
    <ext:Button ID="btnModifySave" runat="server" Text="保存" UI="Primary">
      <DirectEvents><Click OnEvent="btnModifySave_Click"></Click></DirectEvents>
    </ext:Button>
    <ext:Button ID="btnModifyCancel" runat="server" Text="取消" UI="Danger">
      <Listeners><Click Handler="#{winAdd}.close();" /></Listeners>
    </ext:Button>
  </Buttons>
</ext:Window>
```

要点：
- `Hidden="true"` 初始隐藏，`Modal="true"` 蒙层锁定背景。
- `UI="Primary"`（蓝色）/ `UI="Danger"`（红色）控制按钮颜色风格。
- 关闭行为：前端 `#{winAdd}.close()`，服务端 `winAdd.Close()`。

代表页面：`Plugins/Semi/BasicInfo/CurdMaterial.aspx`。

## 五、参考页面索引

| 页面（相对 WebSite 根） | 特点 |
|------------------------|------|
| `Plugins/Semi/BasicInfo/CurdMaterial.aspx` | 最标准 CRUD 骨架（Toolbar+查询+Grid+编辑窗） |
| `Plugins/Semi/BasicInfo/MaterStockTime.aspx` | VBoxLayout 上下双面板 |
| `Plugins/Semi/Produce/SemiProduceMaterial.aspx` | TabPanel 多 Tab 嵌套 |
| `Plugins/Semi/Report/SemisProductionClass.aspx` | 纯报表（查询+Grid+导出） |
| `Plugins/Molding/Report/MoldShiftInspection.aspx` | Tab 内 BorderLayout 上下分区+可拖分割条（组合模式⑤，安全器示意图） |

## 六、关联文档

| 文档 | 关系 |
|------|------|
| `extnet-grid-complete-guide.md` | GridPanel 列系统/事件/合计行的详细用法 |
| `extnet-directmethod-and-data.md` | 后台 DirectMethod + 数据访问的完整写法 |
| `extnet-event-mechanisms.md` | DirectMethod/DirectEvents/Listeners 三者对比 |
| `extnet-export-i18n-error.md` | 导出/资源化/错误处理 |
| `button-permission.md` | 按钮权限（Hidden 默认 + PageAction 字典） |
| `summary-detail-report-template.md` | 汇总+明细报表模板（本骨架的变体应用） |
| `molding-inspection-web-pages.md` | 组合模式⑤ 的实证页面（安全器示意图+lazy 分幅加载） |


## 七、补充关联（反向链接）

| 文档 | 说明 |
|------|------|
| `extnet-tree-guide.md` | TreePanel 树状图开发 |
| `extnet-tabpanel-setactivetab.md` | TabPanel 客户端切换标签页 |
| `extnet-query-form-compound-control-layout.md` | 查询表单复合控件布局 |
| `extnet-tooltip-in-hidden-window.md` | 隐藏 Window 内悬浮失效 |
| `extnet-dataview-card-grid.md` | DataView 卡片网格 |
| `mcui-crud-page-extension-guide.md` | McUI 配置驱动 CRUD 扩展 |
| [[extnet-new-page-style-checklist]] | 新增页面样式对齐交付清单（css/jquery引用、fa图标映射、ui-tab-bar、操作列/导入窗按需标配） |
