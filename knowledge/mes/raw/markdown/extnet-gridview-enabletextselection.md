---
title: GridView.EnableTextSelection — 控制表格文字可选
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, GridPanel, GridView, EnableTextSelection, 属性速查]
status: active
updated: 2026-08-29
---
# GridView.EnableTextSelection — 控制表格文字可选

> ext:GridView 的 EnableTextSelection 控制 GridPanel 单元格文字能否被鼠标拖选复制（默认 false——ExtJS 为避免与行选择冲突而禁用）。报表/明细页需要复制数值、单号时，在 <View> 的 GridView 上显式设 true；可与 GetRowClass 行底色高亮共存互不影响。

## 一、作用

`EnableTextSelection` 是 `ext:GridView` 的布尔属性，控制 **GridPanel 单元格内的文字能否被鼠标选中（高亮 / 复制）**。

- `true`：允许用户用鼠标拖选单元格文字，可复制。
- `false`（默认）：表格文字不可选中，鼠标拖动只会进行行/单元格选择，无法选中文字。

> ExtJS 的 Grid 默认禁用文字选中，是为了避免与行选择（RowSelectionModel）冲突。需要让用户复制单元格内容时，必须显式开启。

## 二、用法

属性配置在 `<View>` 节点下的 `ext:GridView` 上，位置一般在 `ColumnModel` 之后、`SelectionModel` 之前。

```xml
<ext:GridPanel ID="GridPanel1" runat="server">
    <Store>...</Store>
    <ColumnModel>...</ColumnModel>
    <View>
        <ext:GridView ID="GridView2" runat="server" EnableTextSelection="true" />
    </View>
    <SelectionModel>
        <ext:RowSelectionModel Mode="Single" />
    </SelectionModel>
</ext:GridPanel>
```

## 三、典型场景

- 报表类页面：用户需要选中、复制单元格中的数值/编号到别处。
- 明细查询页：需要复制单号、批次号等文本字段。

## 四、注意

- 开启后与 `RowSelectionModel` 共存正常，鼠标在文字上拖动选文字、在行头点击选行，互不影响。
- 若整行仍要底色高亮（如过期预警），可同时配合 `GetRowClass` 使用，二者不冲突：

```xml
<View>
    <ext:GridView ID="GridViewDetail" runat="server" EnableTextSelection="true">
        <GetRowClass Fn="setRowClass" />
    </ext:GridView>
</View>
```

## 五、关联

- 行底色高亮 + EnableTextSelection 组合：见 `extnet-row-highlight-expiry.md`
- GridPanel 完整用法：见 `extnet-grid-complete-guide.md`
