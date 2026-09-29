---
title: MCUI 行按钮隐藏（prepareCommand 机制）
category: 技术-.NET
module: McUI
factory: 通用
tags: [McUI, prepareCommand, 行按钮隐藏, Grid, DeleteFlag, 覆盖写法, 踩坑]
status: active
updated: 2026-08-29
---
# MCUI 行按钮隐藏（prepareCommand 机制）

> MCUI 框架的 Grid 行操作列（修改/删除/恢复）如何按行隐藏按钮。记录框架机制 + 各页面的覆盖写法。
>
> 一句话：行按钮显隐全靠一个客户端回调 `prepareCommand`，框架按 XML 的 `<DeleteFlag>` 自动生成默认实现，各页面在自己的 `.js` 里重声明同名函数即可覆盖。

## 一、核心机制：prepareCommand 回调

MCUI Grid 用 Ext.NET 的 `ImageCommandColumn`，列里声明 `<PrepareCommand Fn="prepareCommand" />`。渲染每一行的按钮前，框架回调 `prepareCommand(grid, command, record, row)`，在函数里设置 `command.hidden = true; command.hideMode = 'display';` 即可隐藏该行该按钮。

**三个 command 名（固定）**：
- `Edit` — 修改
- `Delete` — 删除
- `Recover` — 恢复

**隐藏按钮的标准写法**：
```js
var prepareCommand = function (grid, command, record, row) {
    // 按命令名隐藏
    if (command.command === 'Delete') {
        command.hidden = true;
        command.hideMode = 'display';   // 'display'=不占位; 'visibility'=占位但不可见
    }
    // 按行数据隐藏（如某状态字段为某值时隐藏修改按钮）
    if (record.get('STATUS') === 'CLOSED' && command.command === 'Edit') {
        command.hidden = true;
        command.hideMode = 'display';
    }
};
```

关键点：
- `command.hidden = true` —— 隐藏该行此按钮
- `command.hideMode = 'display'` —— 隐藏方式（display 不占位，visibility 占位留白）
- `record.get("字段名")` —— 读取当前行字段值，据此做条件隐藏
- `command.command` —— 当前正在渲染的按钮名（Edit/Delete/Recover）

## 二、框架自动生成的默认 prepareCommand（按 DeleteFlag 配置）

模板页 `McUI\Crud.aspx.cs` 的 `IniFormJs()` 读取页面 XML 配置 `<DeleteFlag Value="DELETE_FLAG"/>`，据此生成默认 JS：

### 情况 A：未配置 DeleteFlag（物理删除，无软删除）
- 无条件隐藏 `Recover` 按钮（物理删除不需要恢复）
```js
var prepareCommand = function (grid, command, record, row) {
    if (command.command == 'Recover') {
        command.hidden = true;
        command.hideMode = 'display';
    }
};
```

### 情况 B：配置了 DeleteFlag（软删除，支持历史查询/恢复）
- **正常行（flag=0）**：隐藏 Recover，显示 Edit/Delete
- **已删行（flag=1）**：隐藏 Edit/Delete，显示 Recover，且行底变红
```js
var prepareCommand = function (grid, command, record, row) {
    if (record.get('DELETE_FLAG') == 0 && command.command == 'Recover') {
        command.hidden = true; command.hideMode = 'display';
    }
    if (record.get('DELETE_FLAG') == 1 && command.command != 'Recover') {
        command.hidden = true; command.hideMode = 'display';
    }
};
var setRowClass = function (record, rowIndex, rowParams, store) {
    if (record.get('DELETE_FLAG') == '1') { return 'x-grid-row-deleted'; }
};
```

> 配置里 `<DeleteFlag Value="XXX"/>` 的 Value 就是 JS 里的 `record.get('XXX')` 字段名。默认 `DELETE_FLAG`。

## 三、页面如何覆盖默认实现（重声明同名函数）

各页面在自己的 `@McUI\Crud<Name>.js` 里重新声明 `var prepareCommand = function(...){...}`。因为页面 `.js` 在框架内联 JS 之后加载，后声明的同名函数覆盖框架默认实现（JS 函数覆盖）。

### 步骤
1. 页面 XML（`Plugins\<X>\McUI\@McUI\Crud<Name>.xml`）声明 JS 文件：
```xml
<WebPage Title="...">
    <JavaScripts>
        <JavaScript FileUrl="../Plugins/<X>/McUI/@McUI/Crud<Name>.js" />
    </JavaScripts>
</WebPage>
```
2. 在 `Crud<Name>.js` 里重声明 `prepareCommand`。

### 实例 1：无条件隐藏某些按钮（如只读页、不要恢复功能）
`Mould\CrudHiddenRecover.js`：
```js
var prepareCommand = function (grid, command, record, row) {
    if (command.command == 'Recover') { command.hidden = true; }
};
```

`Quality\CrudECStandInfo.js` —— 隐藏 Delete 和 Recover（只保留修改）：
```js
var prepareCommand = function (grid, command, record, row) {
    if (command.command == 'Recover' || command.command == 'Delete') {
        command.hidden = true;
        command.hideMode = 'display';
    }
}
```

`Molding\CrudBpmMoldingProduction.js` —— 全隐藏（纯只读 Grid）：
```js
var prepareCommand = function (grid, command, record, row) {
    if (command.command == 'Recover') { command.hidden = true; command.hideMode = 'display'; }
    if (command.command == 'Delete')  { command.hidden = true; }
    if (command.command == 'Edit')    { command.hidden = true; }
};
```

### 实例 2：按行数据/状态隐藏（核心场景）
`Mould\CrudTbEquipFactory.js` —— 用业务字段 `DelFlag` 控制（最干净的写法，可作模板复制）：
```js
var prepareCommand = function (grid, command, record, row) {
    if (record.get("DelFlag") == 0 && command.command == 'Recover') {
        command.hidden = true;
        command.hideMode = 'display';
    }
    if (record.get("DelFlag") == 1 && command.command != 'Recover') {
        command.hidden = true;
        command.hideMode = 'display';
    }
};
```

## 四、配套：行底色（setRowClass）

隐藏按钮的同时常给行加底色标记状态。`<GetRowClass Fn="setRowClass"/>` 配合：

```js
var setRowClass = function (record, rowIndex, rowParams, store) {
    if (record.get('DELETE_FLAG') == '1') { return 'x-grid-row-deleted'; }
    // 其它可用样式类: x-grid-row-lightpurple, x-grid-row-lightblue
};
```

CSS 定义在 `resources\css\extExtra.css`：
```css
.x-grid-row-deleted .x-grid-cell { background-color: #ff5f5f !important; }   /* 红 */
```

## 五、旧式写法：prepareToolbar（按索引隐藏，不推荐）

早期页面用 `CommandColumn` + `<PrepareToolbar Fn="prepareToolbar"/>`，按 toolbar items 索引隐藏。脆弱（依赖按钮位置顺序），新页面用 `prepareCommand`（按 command 名）替代。

`Curing\Plugins\Main\SysMenu\SetPageMenu.aspx`：
```js
var prepareToolbar = function (grid, toolbar, rowIndex, record) {
    if (record.get("DELETE_FLAG") == "1") {
        toolbar.items.getAt(0).hide();
        toolbar.items.getAt(1).hide();
        toolbar.items.getAt(2).hide();
        toolbar.items.getAt(3).hide();
    } else {
        toolbar.items.getAt(4).hide();
    }
};
```

## 六、速查表

| 需求 | 写法 |
|---|---|
| 隐藏某按钮（所有行） | `if (command.command === 'Delete'){ command.hidden=true; command.hideMode='display'; }` |
| 按状态隐藏某按钮 | `if (record.get('字段')==='值' && command.command==='Edit'){ command.hidden=true; ... }` |
| 已删行只显示恢复 | 框架 DeleteFlag 默认实现（见二B） |
| 给行加底色 | `setRowClass` 返回 CSS 类名 |
| command 名 | Edit / Delete / Recover |
| 覆盖框架默认 | 页面 `.js` 重声明 `var prepareCommand = ...` |

## 七、关键文件索引

| 用途 | 文件 |
|---|---|
| 模板列定义（列+按钮+PrepareCommand+GetRowClass） | `<子系统>\Wongoing.<X>.WebSite\McUI\Crud.aspx` |
| 框架默认 prepareCommand 生成逻辑 | `McUI\Crud.aspx.cs` 的 `IniFormJs()` |
| 各页面覆盖实现 | `Plugins\<X>\McUI\@McUI\Crud<Name>.js` |
| 行底色 CSS | `resources\css\extExtra.css`（`.x-grid-row-deleted` 等） |
| 框架服务端（Page.cs/UiHelper.cs） | `<X>\Frame\Wongoing.McUI\` |

## 八、关联

- MCUI 框架整体架构与 CRUD 流程：见 `main-mcui-config-framework.md`
- MCUI 页面扩展指南：见 `mcui-crud-page-extension-guide.md`
- 按钮权限（权限类 `__` 绑定 ActionName）：见 `button-permission.md`、`main-mcui-config-framework.md` 六章
- 本机制只控制「某行是否显示某按钮」；「某按钮全局是否有权限」由权限类 `__` 控制（两者正交：权限决定按钮存不存在，prepareCommand 决定该行渲不渲染）
