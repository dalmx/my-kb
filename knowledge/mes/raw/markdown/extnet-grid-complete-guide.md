---
title: Ext.NET GridPanel 列系统完整指南
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, GridPanel, ColumnModel, Renderer, SummaryRow, FilterHeader, ImageCommandColumn, 复刻手册]
status: active
updated: 2026-08-29
---
# Ext.NET GridPanel 列系统完整指南

> Semi MES 项目 64 个页面中 60 个用 GridPanel。本文覆盖列类型、Renderer、合计行（SummaryRow）、列过滤（FilterHeader）、行命令列、行底色等全部通用用法。分页相关见 `extnet-pagination-guide.md`，本文不重复。

## 一、列类型清单（项目实际使用的 5 种）

| 列类型 | 用途 | 出现页面数 |
|--------|------|----------|
| `RowNumbererColumn` | 自动行号 | 几乎全部 |
| `Column` | 普通文本列 | 全部 |
| `DateColumn` | 日期格式化 | 16 |
| `CheckColumn` | 布尔勾选展示 | 5 |
| `ImageCommandColumn` | 操作列（编辑/删除按钮） | 14 |

> ⚠️ **本项目未使用** `SummaryColumn`/`ComponentColumn`/`NumberColumn`/`ImageColumn`。合计行用 Feature 而非列类型实现（见第三节）。

## 二、普通列与 DateColumn

```aspx
<ext:Column DataIndex="MATERIAL_CODE" Text="物料代码" Width="120" Align="Center" />
<ext:Column DataIndex="MATERIAL_NAME" Text="物料描述" Flex="1" />

<ext:DateColumn DataIndex="PRODUCE_DATE" Text="生产日期" Width="120" Format="yyyy-MM-dd" Align="Center" />
```

要点：
- `Width` 固定像素，`Flex="1"` 按比例占剩余宽度。二选一。
- `Align="Center"` / `"Right"` / `"Left"`（默认）。
- `DataIndex` 必须与 Store Model 的 `ModelField Name` 完全一致（区分大小写）。
- DateColumn 的 `Format` 与 DateField 一致（如 `yyyy-MM-dd`、`yyyy-MM`）。

## 三、Renderer（单元格自定义渲染）

**两种写法，Fn 引用优先（避免 XML 转义问题）。**

### 方式 A：Fn 引用外部 JS 函数（推荐）
```aspx
<ext:Column DataIndex="STATUS" Text="状态" Width="100">
    <Renderer Fn="statusRenderer" />
</ext:Column>
```
```js
// 放在页面内联 <script> 块
var statusRenderer = function (value) {
    if (value == 0) return '<span style="color:green">正常</span>';
    if (value == 1) return '<span style="color:red">已删除</span>';
    return value;
};
```

### 方式 B：Handler 内联（⚠️ 不能用转义引号）
```aspx
<Renderer Handler="return value == 0 ? '正常' : '禁用';" />
```
> ⚠️ Handler 内**不能用 `\"` 转义引号**——XML 解析器不认反斜杠转义，会报"与 Ext.Net.Column 内的任何属性都不匹配"。需要复杂逻辑时抽成全局 JS 函数用 `Fn` 引用。详见 `extnet-desktop-framework-guide.md` 坑1。

## 四、合计行（Summary Feature）

用 `<Features>` 下的 `Summary` 插件 + 列上设 `SummaryType`，**不是用 SummaryColumn 列类型**。

```aspx
<ext:GridPanel ID="pnlList" runat="server" Region="Center">
    <Store>...</Store>
    <ColumnModel runat="server">
        <Columns>
            <ext:RowNumbererColumn Width="45" />
            <ext:Column DataIndex="MATERIAL_NAME" Text="物料描述" Flex="1" />
            <ext:Column DataIndex="TOTAL_WEIGHT" Text="重量" SummaryType="Sum" />
            <ext:Column DataIndex="TOTAL_COUNT" Text="数量" SummaryType="Sum" />
        </Columns>
    </ColumnModel>
    <Features>
        <ext:Summary ID="Summary" runat="server" Dock="Top" />
    </Features>
</ext:GridPanel>
```

要点：
- `SummaryType="Sum"` 对数值列求和。
- `Dock="Top"` 合计行显示在表头下方（顶部），不设则显示在底部。
- 合计行单元格可用 `SummaryRenderer` 自定义显示格式。

代表页面：`Plugins/Semi/Material/SemisRawMaterial.aspx`。

## 五、列过滤（FilterHeader）

在 GridPanel 加 FilterHeader 插件，每个列头自动出现搜索框，前端过滤：

```aspx
<ext:GridPanel ID="pnlList" runat="server" Region="Center">
    ...
    <Plugins>
        <ext:FilterHeader runat="server" />
    </Plugins>
</ext:GridPanel>
```

代表页面：`Plugins/Semi/Material/SemisRawMaterial.aspx`。纯前端过滤，不请求服务器。

## 六、行命令列（ImageCommandColumn）

操作列放编辑/删除等按钮，配合 `PrepareCommand` 做行级动态显隐。

```aspx
<ext:ImageCommandColumn Width="160" Text="操作" Align="Center">
    <Commands>
        <ext:ImageCommand IconCls="fa fa-pencil color-info" CommandName="Edit" Text="修改" />
        <ext:ImageCommand IconCls="fa fa-trash color-danger" CommandName="Delete" Text="删除" />
    </Commands>
    <PrepareCommand Fn="prepareCommand" />
    <Listeners>
        <Command Handler="return commandcolumn_click(command, record);" />
    </Listeners>
</ext:ImageCommandColumn>
```

### PrepareCommand：按行数据动态隐藏命令按钮

```js
var prepareCommand = function (grid, command, record, row) {
    // 已删除记录只显示"恢复"，不显示"删除"
    if (record.get("DELETE_FLAG") == 1 && command.command != 'Recover') {
        command.hidden = true;
        command.hideMode = 'display';
    }
    // 已开单的记录不能编辑
    if (record.get("BILL_FLAG") > 2 && command.command == 'Edit') {
        command.hidden = true;
        command.hideMode = 'display';
    }
};
```

### Command 事件处理：前端分发到 DirectMethod

```js
var commandcolumn_click = function (command, record) {
    if (command == 'Edit') {
        App.direct.commandcolumn_direct_edit(record.get("ObjID"), {
            success: function () { },
            failure: function (msg) { Ext.Msg.alert('错误', msg); }
        });
    } else if (command == 'Delete') {
        commandcolumn_click_confirm(record.get("ObjID"));
    }
};

// 删除二次确认
var commandcolumn_click_confirm = function (objId) {
    Ext.Msg.confirm('确认', '确定删除吗？', function (btn) {
        if (btn == 'yes') {
            App.direct.commandcolumn_direct_delete(objId, {
                success: function (result) { Ext.Msg.alert('操作', result); pageToolBar.doRefresh(); },
                failure: function (msg) { Ext.Msg.alert('错误', msg); }
            });
        }
    });
};
```

代表页面：`Plugins/Semi/BasicInfo/CurdMaterial.aspx`。

## 七、行底色 / 行样式（GetRowClass）

给特定行加 CSS 类（如已删除行灰显、过期行高亮）：

```aspx
<ext:GridPanel ID="pnlList" runat="server" Region="Center">
    <View>
        <ext:GridView EnableTextSelection="true">
            <GetRowClass Fn="SetRowClass" />
        </ext:GridView>
    </View>
</ext:GridPanel>
```
```js
var SetRowClass = function (record, rowIndex, rowParams, store) {
    if (record.get("DELETE_FLAG") == 1) {
        return "x-grid-row-deleted";   // 灰显已删除行
    }
    return "";
};
```

CSS：
```css
.x-grid-row-deleted .x-grid-cell { color: #ccc; text-decoration: line-through; }
```

### ⚠️ 踩坑：`SetRowClass is not defined`

**现象**：把 `SetRowClass` 放在外部 `*.js` 文件、用 `var fn = function(){}` 声明，页面加载报 `SetRowClass is not defined`。

**原因**：Ext.Net 在 `ResourceManager` 构建阶段按**函数名查找**解析 `Fn="SetRowClass"`，此时外部 JS 的全局 `var` 赋值可能尚未对其解析器可见。

**解决**：把 `SetRowClass` 放在 `.aspx` 的内联 `<script>` 块里。详见 `extnet-row-highlight-expiry.md` 坑1。

## 八、分页工具栏（PagingToolbar）

```aspx
<BottomBar>
    <ext:PagingToolbar ID="pageToolBar" runat="server">
        <Plugins><ext:ProgressBarPager runat="server" /></Plugins>
    </ext:PagingToolbar>
</BottomBar>
```

- Store 设 `PageSize="100"`（本项目多为 100，部分 50/20）。
- `ProgressBarPager` 插件提供进度条式拖拽翻页。
- JS 里刷新：`App.pageToolBar.doRefresh();`
- 客户端分页 vs 服务端分页的区别见 `extnet-pagination-guide.md`。

## 九、完整 GridPanel 示例（含全部要素）

```aspx
<ext:GridPanel ID="pnlList" runat="server" Region="Center" Cls="border-top">
    <Store>
        <ext:Store ID="store" runat="server" PageSize="100">
            <Proxy><ext:PageProxy DirectFn="App.direct.GridPanelBindData" /></Proxy>
            <Model>
                <ext:Model ID="model" runat="server">
                    <Fields>
                        <ext:ModelField Name="ObjID" />
                        <ext:ModelField Name="MATERIAL_CODE" />
                        <ext:ModelField Name="MATERIAL_NAME" />
                        <ext:ModelField Name="TOTAL_WEIGHT" />
                        <ext:ModelField Name="DELETE_FLAG" />
                    </Fields>
                </ext:Model>
            </Model>
        </ext:Store>
    </Store>
    <ColumnModel runat="server">
        <Columns>
            <ext:RowNumbererColumn Width="45" />
            <ext:Column DataIndex="MATERIAL_CODE" Text="物料代码" Width="120" />
            <ext:Column DataIndex="MATERIAL_NAME" Text="物料描述" Flex="1" />
            <ext:Column DataIndex="TOTAL_WEIGHT" Text="重量" SummaryType="Sum" Width="100" Align="Right" />
            <ext:ImageCommandColumn Width="160" Text="操作" Align="Center">
                <Commands>
                    <ext:ImageCommand IconCls="fa fa-pencil color-info" CommandName="Edit" Text="修改" />
                    <ext:ImageCommand IconCls="fa fa-trash color-danger" CommandName="Delete" Text="删除" />
                </Commands>
                <PrepareCommand Fn="prepareCommand" />
                <Listeners><Command Handler="return commandcolumn_click(command, record);" /></Listeners>
            </ext:ImageCommandColumn>
        </Columns>
    </ColumnModel>
    <Features>
        <ext:Summary ID="Summary" runat="server" Dock="Top" />
    </Features>
    <View>
        <ext:GridView EnableTextSelection="true">
            <GetRowClass Fn="SetRowClass" />
        </ext:GridView>
    </View>
    <Plugins>
        <ext:FilterHeader runat="server" />
    </Plugins>
    <BottomBar>
        <ext:PagingToolbar ID="pageToolBar" runat="server">
            <Plugins><ext:ProgressBarPager runat="server" /></Plugins>
        </ext:PagingToolbar>
    </BottomBar>
</ext:GridPanel>
```

## 十、关联文档

| 文档 | 关系 |
|------|------|
| `extnet-page-skeleton.md` | GridPanel 在标准骨架中的位置 |
| `extnet-directmethod-and-data.md` | `GridPanelBindData` DirectMethod 的服务端写法 |
| `extnet-pagination-guide.md` | RemotePaging 概念辨析 |
| `extnet-pagination-guide.md` | 服务端分页 + Session 缓存方案 |
| `extnet-pagination-guide.md` | 客户端分页方案 |
| `extnet-row-highlight-expiry.md` | GetRowClass 行底色实战 + 踩坑 |
| `extnet-desktop-framework-guide.md` | Renderer Handler 转义引号坑 |
| `button-permission.md` | PrepareCommand 动态权限控制 |
| `extnet-grid-tooltip-delegate.md` | 单元格悬浮提示（ToolTip + Delegate） |


## 十一、补充关联（反向链接）

| 文档 | 说明 |
|------|------|
| `extnet-dataview-card-grid.md` | DataView 卡片网格可视化页面 |
| `extnet-grid-editor-combobox-renderer.md` | 编辑列 ComboBox 显示 value 的坑 |
| `extnet-grid-columname-case.md` | 列名大小写不匹配显示空 |
| `extnet-grid-datecolumn-pitfall.md` | 时间列 DateColumn 显示空白 |
| `extnet-gridview-enabletextselection.md` | GridView 文字可选 |
| `extnet-summary-row-decimal-precision.md` | 合计行小数精度踩坑 |
| `extnet-tablelayout-cell-edit-pitfalls.md` | TableLayout 单元格可编辑 + 存库 |
