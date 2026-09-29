---
title: Ext.NET DragDrop 拖拽完整指南
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [DragDrop, 拖拽, GridDragDrop, TreeViewDragDrop, DropZone, DDProxy, 行重排序]
status: active
updated: 2026-08-29
---
# Ext.NET DragDrop 拖拽完整指南

> 本文档从 Ext.NET 4.7.1 官方示例库 `Examples/DragDrop/`（20 示例）提炼，覆盖 Grid/Tree/Panel/DOM 间拖拽。目标是让 AI/开发者读完即可在任意 Ext.NET WebForms 项目复现。
>
> 适用：Ext.NET 4.x + Triton 主题。

---

## 一、拖拽核心概念

### 1.1 两大场景

| 场景 | 使用的 API | 说明 |
|------|-----------|------|
| **纯 DOM 拖拽** | `DDProxy`（拖源）+ `DropZone`/`DropTarget`（放目标） | 手动指定 DOM 元素，自己写回调移动 |
| **组件级拖拽** | 插件：`GridDragDrop`/`TreeViewDragDrop`/`DraggablePanelConfig` | 组件自带，自动处理数据移动 |

### 1.2 ddGroup（拖放组）—— 最关键匹配规则

拖源和放目标的 **Group 必须同名**才能匹配。

**双向拖拽**用交叉组名：

| 拖源 A | 放目标 B |
|--------|----------|
| `DragGroup=X, DropGroup=Y` | `DragGroup=Y, DropGroup=X` |

---

## 二、Panel 拖拽

### 2.1 浮动面板（最简）

```aspx
<ext:Panel runat="server" Title="拖我" Width="200" Height="150"
    Floating="true" Draggable="true" X="50" Y="50" />
```

`Floating="true"` + `Draggable="true"` 即可，无需 JS。

### 2.2 拖到指定容器

```aspx
<ext:Panel runat="server" Title="可拖面板">
    <DraggablePanelConfig runat="server" Group="panelDD">
        <StartDrag Handler="Ext.select('.dropable').addCls('x-drop-marker');" />
        <EndDrag Handler="Ext.select('.dropable').removeCls('x-drop-marker');
            Ext.panel.DD.prototype.endDrag.apply(this, arguments);" />
    </DraggablePanelConfig>
</ext:Panel>

<!-- 目标容器 -->
<ext:DropTarget runat="server" Target="${.dropable}" Group="panelDD" OverClass="invite">
    <NotifyDrop Handler="var cmp = Ext.getCmp(this.el.dom.id);
        cmp.add(data.panel);
        Ext.defer(data.panel.updateLayout, 1, data.panel);" />
</ext:DropTarget>
```

- `Target="${.dropable}"`：CSS 选择器匹配目标
- `OverClass`：悬停高亮样式
- `NotifyDrop`：`data.panel` 是被拖面板

---

## 三、Grid 拖拽（最常用）

核心：`GridPanel > View > Plugins > ext:GridDragDrop`。

### 3.1 Grid 行重排序（最简）

```aspx
<ext:GridPanel runat="server" Title="行重排序" Width="400" Height="300">
    <Store>...</Store>
    <ColumnModel>...</ColumnModel>
    <View>
        <ext:GridView runat="server">
            <Plugins>
                <ext:GridDragDrop runat="server" DragText="拖拽调整顺序" />
            </Plugins>
        </ext:GridView>
    </View>
</ext:GridPanel>
```

单 Grid 内部拖动调换行顺序，**无需配 Group**。

### 3.2 Grid 之间拖拽行（双向）

```aspx
<ext:GridPanel ID="Grid1" runat="server" Title="左">
    <View>
        <ext:GridView runat="server">
            <Plugins>
                <ext:GridDragDrop runat="server"
                    DragGroup="firstDDG" DropGroup="secondDDG" />
            </Plugins>
        </ext:GridView>
    </View>
</ext:GridPanel>

<ext:GridPanel ID="Grid2" runat="server" Title="右">
    <View>
        <ext:GridView runat="server">
            <Plugins>
                <ext:GridDragDrop runat="server"
                    DragGroup="secondDDG" DropGroup="firstDDG" />
            </Plugins>
        </ext:GridView>
    </View>
</ext:GridPanel>
```

**关键**：DragGroup/DropGroup 交叉，实现双向。

### 3.3 拖拽事件

挂在 `GridView` 的 `<Listeners>`：

```aspx
<ext:GridView runat="server">
    <Plugins><ext:GridDragDrop runat="server" DragGroup="g1" DropGroup="g2" /></Plugins>
    <Listeners>
        <Drop Handler="var dropOn = overModel ? ' ' + dropPosition + ' ' + overModel.get('Name') : '';
            Ext.Msg.alert('提示', '拖入 ' + data.records[0].get('Name') + dropOn);" />
        <BeforeDrop Fn="beforeDrop" />
    </Listeners>
</ext:GridView>
```

| 事件 | 参数 | 用途 |
|------|------|------|
| `BeforeDrop` | `(node, data, overModel, dropPosition, dropFn)` | 放行前可改数据，return true 继续 |
| `Drop` | `(data, overModel, dropPosition)` | drop 后回调 |

参数说明：
- `data.records`：被拖的记录数组
- `overModel`：悬停的目标行（空视图为 null）
- `dropPosition`：`"before"` / `"after"` / `"append"`

### 3.4 drop 时转换数据（Grid→Tree）

`BeforeDrop` 里改写 `data.records` 把记录转成目标格式，并从源 store 删除：

```javascript
var beforeDrop = function (node, data, overModel, dropPosition, dropFn) {
    var records = data.records;
    data.records = [];
    for (var i = 0; i < records.length; i++) {
        var rec = records[i];
        data.records.push({
            text: rec.get("company"),
            leaf: true,
            price: rec.get("price")
        });
        rec.store.remove(rec);   // 从源 store 删除
    }
    return true;
};
```

---

## 四、Tree 拖拽

核心：`TreePanel > View > Plugins > ext:TreeViewDragDrop`。

```aspx
<ext:TreePanel runat="server" Title="树" AutoScroll="true">
    <Root>
        <ext:Node Text="根" Expanded="true" AllowDrag="false">
            <Children>
                <ext:Node Text="文件夹" AllowDrag="false">
                    <Children>
                        <ext:Node Text="子项" Leaf="true" />
                    </Children>
                </ext:Node>
            </Children>
        </ext:Node>
    </Root>
    <View>
        <ext:TreeView runat="server">
            <Plugins>
                <ext:TreeViewDragDrop runat="server" DragGroup="tree2grid" DropGroup="grid2tree" />
            </Plugins>
        </ext:TreeView>
    </View>
</ext:TreePanel>
```

- 节点 `AllowDrag="false"` 单独禁止某节点被拖
- 父子节点间移动是默认行为

**简写**（旧式）：`<ext:TreePanel runat="server" EnableDrag="true" DDGroup="xxx">`

---

## 五、拖到任意 DOM 元素

拖源插件（设 DragGroup）+ `ext:DropTarget`（同 Group + NotifyDrop）：

```aspx
<!-- 拖源：Tree 只拖不放 -->
<ext:TreePanel runat="server">
    <View>
        <ext:TreeView runat="server">
            <Plugins>
                <ext:TreeViewDragDrop runat="server" EnableDrop="false" DragGroup="tree2div" />
            </Plugins>
        </ext:TreeView>
    </View>
</ext:TreePanel>

<!-- 普通 div 目标 -->
<div id="drop-target" style="border:1px solid silver; height:140px; padding:8px;">拖到这里</div>

<!-- DropTarget 把 div 变成放目标 -->
<ext:DropTarget runat="server" Target="drop-target" Group="tree2div">
    <NotifyDrop Fn="notifyDrop" />
</ext:DropTarget>
```

```javascript
var notifyDrop = function (dd, e, data) {
    var rec = data.records[0];
    Ext.get("drop-target").update(
        "<li>text: " + rec.get('text') + "</li>" +
        "<li>leaf: " + rec.get('leaf') + "</li>"
    );
    return true;   // 返回 true 表示成功
};
```

> `EnableDrop="false"` 表示这个 View 自己不接受拖入（只作拖源）。

---

## 六、纯 DOM 拖拽（DDProxy）

不用 Grid/Tree、直接操作任意 div：

```aspx
<!-- 每个可拖元素一个 DDProxy -->
<ext:DDProxy runat="server" Target="item1" Group="group">
    <StartDrag Fn="startDrag" />
    <OnDragOver Fn="onDragOver" />
    <EndDrag Fn="endDrag" />
</ext:DDProxy>

<!-- 容器 DropZone -->
<ext:DropZone runat="server" Target="container" Group="group" />
```

```javascript
var startDrag = function (x, y) {
    var dragEl = Ext.get(this.getDragEl());  // 跟随鼠标的幽灵元素
    var el = Ext.get(this.getEl());          // 原始元素
    dragEl.update(el.dom.innerHTML);         // 复制内容到幽灵
};

var onDragOver = function (e, targetId) {
    Ext.get(targetId).addCls('dd-over');     // 高亮
    this.lastTarget = Ext.get(targetId);
};

var endDrag = function () {
    if (this.lastTarget) {
        Ext.get(this.lastTarget).appendChild(Ext.get(this.getEl()));  // 移动 DOM
    }
};
```

DDProxy 事件：`StartDrag` / `OnDragEnter` / `OnDragOver` / `OnDragOut` / `EndDrag`。

---

## 七、DragTracker（框选）

非传统拖放，用于鼠标框选区域（如多选）：

```aspx
<ext:DragTracker runat="server"
    ConstrainTo="={#{Panel1}.body}"
    Target="={#{Panel1}.body}">
    <Listeners>
        <DragStart Fn="startTrack" />
        <Drag Fn="dragTrack" />
        <DragEnd Fn="endTrack" />
    </Listeners>
</ext:DragTracker>
```

拖动中用 `this.dragRegion.intersect(element.getRegion())` 判断元素是否落在选择框内。

---

## 八、DragGroup/DropGroup 配置对照表

| 场景 | 拖源 A | 放目标 B | 双向 |
|------|--------|----------|------|
| Grid↔Grid | `DragGroup=X, DropGroup=Y` | `DragGroup=Y, DropGroup=X` | 是 |
| Grid→Tree 单向 | Grid: `DragGroup=g2t` | Tree: `DropGroup=g2t` | 否 |
| Tree→div | Tree: `DragGroup=t2d, EnableDrop=false` | DropTarget: `Group=t2d` | 否 |
| 纯 DOM | DDProxy: `Group=g` | DropZone: `Group=g` | 否 |

---

## 九、踩坑要点

### 坑1：Grid 行重排序无需 Group

单 Grid 内部拖动调换顺序，直接挂 `GridDragDrop` 插件即可，不配 Group。

### 坑2：双向拖拽必须交叉组名

Grid↔Grid 双向拖拽，A 的 DragGroup 必须等于 B 的 DropGroup，反之亦然。两边都写 `DragGroup=X DropGroup=X` 会导致自己拖给自己。

### 坑3：GridDragDrop 挂在 View 的 Plugins 上

```aspx
<!-- ✅ 正确位置：GridView.Plugins -->
<ext:GridView runat="server">
    <Plugins><ext:GridDragDrop runat="server" ... /></Plugins>
</ext:GridView>

<!-- ❌ 错误：挂到 GridPanel 上 -->
<ext:GridPanel runat="server">
    <Plugins><ext:GridDragDrop /></Plugins>   <!-- 无效 -->
</ext:GridPanel>
```

### 坑4：BeforeDrop 改数据后要 return true

`BeforeDrop` 里改写 `data.records` 后必须 `return true` 才继续 drop，否则被取消。

### 坑5：DropTarget 的 Target 是 DOM id 不是控件 ID

`<ext:DropTarget Target="drop-target">` 的 Target 是**客户端 DOM 元素 id**（普通 div 的 id），不是 Ext.NET 控件的 ID。引用 Ext.NET 控件元素用 `={#{控件}.body}` 语法。

### 坑6：Tree 节点 AllowDrag 单独控制

Tree 默认所有节点可拖，要固定根节点/某些节点不被拖，单独设 `AllowDrag="false"`。

---

## 十、关联文档

| 文档 | 关系 |
|------|------|
| `extnet-grid-complete-guide.md` | GridPanel（Grid 拖拽基础） |
| `extnet-tree-guide.md` | TreePanel（Tree 拖拽基础） |
| `extnet-store-databinding-guide.md` | Store（拖拽本质是 Store 记录移动） |

## 十一、参考来源

- 官方示例库：`Examples/DragDrop/`（20 示例）
  - `Basic/Dom/`：DDProxy 基础 DOM 拖拽
  - `Basic/Example1~3/`：DDProxy 完整回调
  - `Panel/Draggable_Panel/`、`Dropable_Panel/`：面板拖拽
  - `Grid/Grid_to_Grid/`：Grid 间拖拽（最常用）
  - `Grid/Rows_Reordering/`：Grid 行重排序
  - `Grid/Grid_to_Tree/`：Grid→Tree（BeforeDrop 转换）
  - `Tree/Tree_to_Div/`：Tree→div
  - `Advanced/Checkbox_Selector/`：DragTracker 框选
