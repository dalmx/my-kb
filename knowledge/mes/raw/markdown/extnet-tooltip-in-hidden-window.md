---
title: 隐藏 Window 内 Grid 的单元格悬浮失效（ToolTip 绑定空目标）
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, ToolTip, GridPanel, Window, 隐藏窗口, Hidden, 延迟创建, 踩坑, 悬浮提示]
status: active
updated: 2026-08-29
---
# 隐藏 Window 内 Grid 的单元格悬浮失效（ToolTip 绑定空目标）

> Target="={#{grid}.getView().el}" 在页面加载时立即求值，隐藏 Window（Hidden="true"）里的 Grid 视图尚未渲染 DOM，ToolTip 绑到空目标 → 悬浮永远不触发。解法：窗口 show() 之后再调初始化函数，用 JS Ext.create('Ext.tip.ToolTip') 延迟创建并绑定（标志位防重复创建），delegate 用 .x-grid-cell-<列ID全小写>、多列逗号分隔；可见 Grid 才能用静态 ToolTip。

## 一、场景

GridPanel 放在**初始隐藏的 Window**（`Hidden="true"`，点击按钮才 `.show()`）里，给它的某列加单元格悬浮提示。按常规写法（见 `extnet-grid-tooltip-delegate.md`）声明 `<ext:ToolTip Target="={#{grid}.getView().el}" ...>`，结果**悬浮完全无反应**。

典型页：`TyreLockAndUnLock.aspx` 的"日志明细"弹窗 `winDetail`（`Hidden="true"`），内含 `pnlDetail` 网格，给"备注""操作明细"两列加悬浮。

---

## 二、根因

`Target="={#{pnlDetail}.getView().el}"` 这个 `={...}` 表达式在**页面构建/加载时立即求值**。此时 `winDetail` 还隐藏着，`pnlDetail` 的视图元素**尚未渲染到 DOM**，`getView().el` 为空 → ToolTip 绑定到一个不存在的目标 → 永远不触发。

> 对比：范例 `SetPageMenu.aspx` 的 `pnlList` 是**直接放在 Viewport 里、页面加载就可见**的，所以 `getView().el` 求值时已存在，静态 ToolTip 能生效。**可见的 Grid 才能用静态 ToolTip；隐藏 Window 里的 Grid 不能。**

尝试过的无效改法：
- 把 ToolTip 从 Window 的 `<Items>` 移到 `<form>` 顶层（与 Viewport 平级）—— 仍无效，求值时机没变。
- 把 Target 改成 `={#{winDetail}.body}` —— 隐藏 Window 的 body 同样未渲染，无效。

---

## 三、解法：JS 在窗口 show() 之后延迟创建 ToolTip

核心思路：**等 Window 显示、Grid 视图渲染完成后，再用 JS 创建 ToolTip 并绑定**。此时 `getView().el` 一定存在。

### 3.1 触发时机：在 show() 之后调用初始化

```js
var commandcolumn_direct_history = function (record) {
    App.direct.commandcolumn_direct_history(record.data.GREEN_TYRE_NO, record.data.TYRE_NO, {
        success: function (result) {
            if (result != "") {
                Ext.Msg.alert('操作', result);
            } else {
                App.winDetail.show();          // 1. 先显示窗口（Grid 视图此时渲染）
                initDetailRemarkToolTip();      // 2. 再绑定悬浮
            }
        },
        failure: function (errorMsg) { Ext.Msg.alert('操作', errorMsg); }
    });
};
```

### 3.2 初始化函数（用标志位保证只创建一次）

```js
var detailRemarkTipInited = false;
var initDetailRemarkToolTip = function () {
    if (detailRemarkTipInited) { return; }          // 防止重复创建
    var view = App.pnlDetail.getView();
    if (!view || !view.el) { return; }              // 双保险：视图没渲染就跳过
    detailRemarkTipInited = true;

    Ext.create('Ext.tip.ToolTip', {
        target: view.el,
        // 多列用逗号分隔，同时覆盖"备注"和"操作明细"两列
        delegate: '.x-grid-cell-colRemark, .x-grid-cell-colLogContent',
        listeners: {
            show: function (tip) {
                var column = view.getHeaderByCell(tip.triggerElement),
                    record = view.getRecord(view.findItemByChild(tip.triggerElement));
                if (record && column) {
                    var data = record.get(column.dataIndex);
                    // white-space:pre-wrap 保留 TextArea 录入的换行
                    tip.update('<div style="white-space:pre-wrap">' + (data || '') + '</div>');
                }
            }
        }
    });
};
```

### 3.3 列定义要有全小写 ID（Delegate 选择器用）

```aspx
<ext:Column ID="colRemark" runat="server" Text="备注" DataIndex="REMARK" Width="200" />
<ext:Column ID="colLogContent" runat="server" Text="操作明细" DataIndex="LOG_CONTENT" Width="250" />
```

> 与静态 ToolTip 一致，Delegate 用 `.x-grid-cell-<列ID全小写>`。多列共享一个 ToolTip 时用逗号分隔 selector。

---

## 四、要点速查

| 点 | 说明 |
|----|------|
| 静态 `<ext:ToolTip>` 适用条件 | 目标 Grid **页面加载即可见**（直接在 Viewport 里） |
| 隐藏 Window 内 Grid | 必须用 **JS 延迟创建** `Ext.create('Ext.tip.ToolTip', ...)` |
| 创建时机 | `App.winXxx.show()` **之后**调用初始化函数 |
| 防重复 | 用 `xxxInited` 标志位，第二次调用直接 return |
| 多列共用一个 Tip | `delegate: '.x-grid-cell-a, .x-grid-cell-b'`（逗号分隔） |
| 取数据 API | `view.getHeaderByCell(tip.triggerElement)` 取列、`view.getRecord(view.findItemByChild(...))` 取行记录、`record.get(column.dataIndex)` 取值 |
| 保留换行 | `tip.update('<div style="white-space:pre-wrap">' + data + '</div>')` |

---

## 五、关联

- 常规（可见 Grid）悬浮写法：见 `extnet-grid-tooltip-delegate.md`
- 列名/列 ID 大小写坑：见 `extnet-grid-columname-case.md`
- 弹窗标准结构：见 `extnet-page-skeleton.md` 第四节
