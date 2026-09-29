---
title: GetDataTableByStatement 用法与 ImageCommandColumn 行内操作列
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, GetDataTableByStatement, ImageCommandColumn, iBATIS]
updated: 2026-08-29
status: active
---
# GetDataTableByStatement 用法与 ImageCommandColumn 行内操作列

> ImageCommandColumn 行内操作列完整写法：Commands 定义编辑/删除按钮（IconCls + CommandName + ToolTip），PrepareCommand 按数据状态动态隐藏按钮，JS commandcolumn_click 处理 Command 事件（Ext.Msg.confirm 二次确认后调 DirectMethod）；CommandName 必须与后台权限类 ActionName 一致（区别于工具栏按钮用 ID 作 ActionName）。

## 一、ImageCommandColumn — 行内操作按钮

每行末尾显示编辑、删除等操作按钮。

### aspx 写法

```aspx
<ext:ImageCommandColumn ID="colAction" runat="server" Width="120" Text="操作" Align="Center">
    <Commands>
        <ext:ImageCommand IconCls="fa fa-pencil color-info" CommandName="Edit" Text="编辑">
            <ToolTip Text="修改记录" />
        </ext:ImageCommand>
        <ext:ImageCommand IconCls="fa fa-times-circle color-danger" CommandName="Delete" Text="删除">
            <ToolTip Text="删除记录" />
        </ext:ImageCommand>
    </Commands>
    <PrepareCommand Fn="prepareCommand" />
    <Listeners>
        <Command Handler="return commandcolumn_click(command, record);" />
    </Listeners>
</ext:ImageCommandColumn>
```

### JS 处理函数

```javascript
var commandcolumn_click = function (command, record) {
    var planId = record.get("PlanId");
    if (command == 'Edit') {
        // 编辑逻辑
    } else if (command == 'Delete') {
        Ext.Msg.confirm("确认", "确定删除？", function (btn) {
            if (btn == "yes") {
                App.direct.DeleteRecord(planId);
            }
        });
    }
};
```

### 动态控制按钮显隐（PrepareCommand）

```javascript
var prepareCommand = function (grid, command, record, row) {
    // 已完成记录隐藏编辑按钮
    if (command.command == 'Edit' && record.get("PlanState") == '1') {
        command.hidden = true;
        command.hideMode = 'display';
    }
};
```

### 权限对齐

操作列按钮的 `CommandName` 必须与后台权限类 `ActionName` 一致：

| 按钮 | CommandName | 后台 ActionName |
|------|-------------|-----------------|
| 编辑 | `"Edit"` | `编辑 = new PageAction() { ActionName = "Edit" }` |
| 删除 | `"Delete"` | `删除 = new PageAction() { ActionName = "Delete" }` |

区别于工具栏按钮用 `btnSearch`、`btnExport` 等 `ID` 作为 `ActionName`。
