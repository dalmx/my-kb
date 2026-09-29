---
title: GridPanel 单元格悬浮提示（ToolTip + Delegate）
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, ToolTip, GridPanel, Delegate, 单元格悬浮提示, 锁定列, LockedColumn, 踩坑]
status: active
updated: 2026-08-29
---
# GridPanel 单元格悬浮提示（ToolTip + Delegate）

> 单元格动态 Tooltip 三要素：Target 绑 Grid 视图元素（={#{grid}.getView().el} 表达式语法）、Delegate 限定触发单元格（推荐 .x-grid-cell-<ColumnID>——DataIndex 写法会被 ExtJS 整体小写化且锁定列取不到）、onShow 由 triggerElement 反查 record/column 动态填内容。默认即自动关闭模式（勿乱加 AutoHide/Closable/Draggable），锁定列场景改用 view.LockedView 查行。

## 一、场景

GridPanel 中某列内容较长（如备注、描述），列宽有限被截断，用户需要 **鼠标悬浮到单元格时弹出提示框显示完整内容**。

与按钮简单的 `ToolTip="文本"` 不同，单元格 Tooltip 需要：
- 指定触发区域（哪个 Grid 的哪些单元格）
- 动态获取当前单元格的数据并填入提示框

---

## 二、用法

### 2.1 aspx：声明 ToolTip

```xml
<ext:ToolTip
    runat="server"
    Target="={#{pnlSF}.getView().el}"
    Delegate=".x-grid-cell-remark">
    <Listeners>
        <Show Handler="onShow(this, #{pnlSF});" />
    </Listeners>
</ext:ToolTip>
```

> 上图为**自动关闭模式（推荐）**：不写 `AutoHide`/`Closable`/`Draggable`，鼠标移开自动消失。
> 若需"常驻、手动关闭"模式，见 [第五节·两种行为模式](#五两种行为模式自动关闭--常驻)。

### 2.2 JS：Show 时取单元格数据

```javascript
var onShow = function (toolTip, grid) {
    var view = grid.getView(),
        store = grid.getStore(),
        record = view.getRecord(view.findItemByChild(toolTip.triggerElement)),
        column = view.getHeaderByCell(toolTip.triggerElement),
        data = record.get(column.dataIndex);

    toolTip.update(data);
};
```

---

## 三、核心三要素

单元格动态 Tooltip 必须同时具备：

| 要素 | 作用 | 写法 |
|------|------|------|
| `Target` | 绑定到哪个 Grid 的视图元素 | `Target="={#{pnlSF}.getView().el}"` |
| `Delegate` | 只在哪些单元格上触发 | CSS 选择器，见 [第四节](#四delegate--限定触发元素) |
| `onShow` | 显示时取数据填内容 | `<Show Handler="onShow(this, #{pnlSF});" />` |

---

## 四、Delegate — 限定触发元素

CSS 选择器，**只在该选择器匹配的元素上才触发 Tooltip**。

#### 写法 A：按 Column 的 ID（推荐，锁定列必用）

```xml
<!-- 先给列配 ID -->
<ext:Column ID="show_name" runat="server" Text="菜单名称" DataIndex="SHOW_NAME" Width="80" />

<!-- Delegate = .x-grid-cell- + Column的ID -->
Delegate=".x-grid-cell-show_name"
```

- `.x-grid-cell-` 是固定前缀（死的），后面跟 **Column 的 ID**（不是 DataIndex）。
- 多个列用逗号隔开：`Delegate=".x-grid-cell-show_name, .x-grid-cell-remark"`
- **锁定列（Locked 列）场景必须用 Column ID 写法**，用 DataIndex 可能取不到。

#### 写法 B：按 DataIndex（无锁定列时可用）

```xml
Delegate=".x-grid-cell-remark"
```

- class 名由 ExtJS 自动生成，规则是 `x-grid-cell-<DataIndex小写>`：
  - 列 `DataIndex="remark"` → 单元格 class 含 `x-grid-cell-remark`
  - 列 `DataIndex="EquipName"` → 单元格 class 含 `x-grid-cell-equipname`（注意小写）

> ⚠️ **大写 DataIndex 的坑（实战）**：ExtJS 生成 class 时会把名称**整体小写化**。若列 `DataIndex="BACKGROUND"`（全大写）且未配 ID，实际生成的 class 是 `x-grid-cell-background`（全小写）。此时 Delegate 若写 `.x-grid-cell-BACKGROUND`（大写原样）**匹配不上、悬浮不触发**。
> **最稳做法**：给列加一个全小写 ID，Delegate 用这个 ID，大小写一致不会错。例：
> ```xml
> <ext:Column ID="background" runat="server" Text="背景" DataIndex="BACKGROUND" Width="200"/>
> <!-- Delegate 用 ID（全小写），而非 DataIndex -->
> Delegate=".x-grid-cell-background"
> ```

#### 写法 C：所有列都触发

```xml
Delegate=".x-grid-cell"
```

- 不限定具体列，Grid 内任意单元格悬浮都触发 Tooltip。

> 经验：优先用 **Column ID 写法**，它对锁定列/普通列都兼容，最稳。DataIndex 写法在无锁定列时也可用，但大小写容易出错。

---

## 五、两种行为模式（自动关闭 / 常驻）

Ext.NET ToolTip 通过三个属性控制显示行为：

| 属性 | 作用 | 自动关闭模式 | 常驻模式 |
|------|------|:---:|:---:|
| `AutoHide` | 鼠标移开是否自动消失 | `true`（默认，可省略） | `false` |
| `Closable` | 显示右上角 × 关闭按钮 | `false`（默认，可省略） | `true` |
| `Draggable` | 提示框可拖动 | `false`（默认，可省略） | `true` |

### 5.1 自动关闭模式（推荐，最常用）

**不写**这三个属性，全部走默认值，鼠标移开单元格即自动消失：

```xml
<ext:ToolTip runat="server"
    Target="={#{pnlSF}.getView().el}"
    Delegate=".x-grid-cell-background">
    <Listeners>
        <Show Handler="onShow(this, #{pnlSF});" />
    </Listeners>
</ext:ToolTip>
```

- 适用：备注、背景、描述等长文本列，用户只是想瞄一眼完整内容。
- 实战范例：`TyreCheckQueryNew.aspx` 背景列、`SetPageMenu.aspx` 多列。

### 5.2 常驻模式（需手动关闭）

```xml
<ext:ToolTip runat="server"
    Target="={#{pnlSF}.getView().el}"
    Delegate=".x-grid-cell-remark"
    Closable="true"
    Draggable="true"
    AutoHide="false">
    <Listeners>
        <Show Handler="onShow(this, #{pnlSF});" />
    </Listeners>
</ext:ToolTip>
```

- 适用：内容非常长、用户需要拖开提示框对照看的情况。
- ⚠️ `AutoHide="false"` 必须配合 `Closable="true"`，否则提示框不会消失、一直挡屏。

### 5.3 实战对照

| 页面 | 模式 | 写法 |
|------|------|------|
| `SetPageMenu.aspx` | 自动关闭 | 不设 AutoHide/Closable/Draggable |
| `TyreCheckQueryNew.aspx`（改后） | 自动关闭 | 不设 AutoHide/Closable/Draggable |

> 常见误用：把"自动关闭模式"的列误加了 `AutoHide="false" Closable="true" Draggable="true"`，导致提示框变成需手动关闭的常驻窗口，用户体验变差。**默认就是自动关闭，无需额外配置。**

---

## 六、onShow 函数逐行解析

```javascript
var onShow = function (toolTip, grid) {
    var view = grid.getView(),                          // Grid 视图对象
        store = grid.getStore(),                       // Store（本例未用到，可省）
        // 从触发元素找到所属行记录
        record = view.getRecord(view.findItemByChild(toolTip.triggerElement)),
        // 从触发元素找到所属列
        column = view.getHeaderByCell(toolTip.triggerElement),
        // 取该行该列的字段值
        data = record.get(column.dataIndex);

    toolTip.update(data);   // 把数据填入提示框
};
```

| 调用 | 作用 |
|------|------|
| `toolTip.triggerElement` | 触发 Tooltip 的具体 DOM 元素（被悬浮的单元格） |
| `view.findItemByChild(el)` | 由单元格 DOM 向上找到所属行（row）元素 |
| `view.getRecord(rowEl)` | 由行元素找到对应的数据 record |
| `view.getHeaderByCell(el)` | 由单元格 DOM 找到对应列（Column）对象 |
| `record.get(column.dataIndex)` | 取该列字段在 record 中的值 |
| `toolTip.update(data)` | 更新 Tooltip 内容（支持 HTML） |

> 这套 API 是 ExtJS 的"由 DOM 反查数据"模式：triggerElement（DOM）→ record/column（数据层），实现动态内容。

---

## 七、完整最小示例（可直接复制）

列定义 + ModelField + ToolTip 三件套，给"背景"列加自动关闭的悬浮提示：

```xml
<!-- 1. Store Model 里要有该字段 -->
<ext:ModelField Name="BACKGROUND" />

<!-- 2. 给列配一个全小写 ID -->
<ext:Column ID="background" runat="server" Text="背景" DataIndex="BACKGROUND" Width="200"/>

<!-- 3. ToolTip：Delegate 用 Column ID，自动关闭模式 -->
<ext:ToolTip runat="server"
    Target="={#{pnlSF}.getView().el}"
    Delegate=".x-grid-cell-background">
    <Listeners>
        <Show Handler="onShow(this, #{pnlSF});" />
    </Listeners>
</ext:ToolTip>
```

```javascript
// 4. onShow 函数（与 GridPanel ID 对应）
var onShow = function (toolTip, grid) {
    var view = grid.getView(),
        record = view.getRecord(view.findItemByChild(toolTip.triggerElement)),
        column = view.getHeaderByCell(toolTip.triggerElement),
        data = record.get(column.dataIndex);
    toolTip.update(data);
};
```

---

## 八、锁定列（Locked Column）场景 ⚠️

当 GridPanel 含锁定列（`Locked="true"`）时，视图会被拆成 **LockedView（锁定区）** 和 **NormalView（滚动区）** 两部分。此时 `view.findItemByChild(...)` 可能取不到锁定区的行元素，需改用 `view.LockedView`：

```javascript
var onShow = function (toolTip, grid) {
    var view = grid.getView(),
        // 锁定列在 LockedView，普通列在 NormalView，优先从 LockedView 找
        record = view.getRecord(view.LockedView.findItemByChild(toolTip.triggerElement)),
        column = view.getHeaderByCell(toolTip.triggerElement),
        data = record.get(column.dataIndex);

    toolTip.update(data);
};
```

> 若不确定悬浮的是锁定区还是滚动区，可兼容判断：
> ```javascript
> var itemView = view.LockedView || view;
> var record = view.getRecord(itemView.findItemByChild(toolTip.triggerElement));
> ```
> 但通常 Delegate 已限定了具体列，知道它在哪个区，直接用对应的 view 即可。

**锁定列场景的 Delegate 必须用 Column ID 写法**（见上文写法 A），不要用 DataIndex 写法。

---

## 九、注意

- **Delegate 推荐用 Column ID 写法**：`.x-grid-cell-<Column的ID>`，对锁定列/普通列都兼容，且大小写可控。DataIndex 写法（`.x-grid-cell-<dataindex小写>`）在无锁定列时可用，但大写 DataIndex 会转小写，易出错。
- **默认就是自动关闭**：不设 `AutoHide`/`Closable`/`Draggable` 时，鼠标移开即自动隐藏；除非确需"常驻手动关闭"，否则不要乱加这三个属性。
- `toolTip.update(data)` 支持 HTML，可做富文本提示（如换行、着色）：
  ```javascript
  toolTip.update('<div style="white-space:pre-wrap">' + data + '</div>');
  ```
- `Target` 用 `={...}` 表达式语法，不要写成普通字符串 `"pnlSF"`，否则取不到视图元素。
- 若只需简单提示固定文本（非动态取单元格值），按钮等控件直接用 `ToolTip="文本"` 属性即可，无需此方案。

---

## 十、关联

- GridPanel 完整用法：见 `extnet-grid-complete-guide.md`
- 单元格双击弹窗（另一种单元格交互）：见 `dynamic-column-popup-report-template.md`
- 按钮 ToolTip 简单用法：见 `standard-report-template.md`
- 列名大小写相关坑：见 `extnet-grid-columname-case.md`
