---
category: 技术-.NET
factory: 通用
module: Ext.NET
status: active
tags: [Ext.NET, TreePanel, TreeColumn, 条纹行, StripeRows, CSS, ConfigItem, ComboBox, 踩坑]
title: Ext.NET TreePanel 树状图开发指南
updated: 2026-08-29
---

# Ext.NET TreePanel 树状图开发指南

> Ext.NET TreePanel 用于展示树形层级数据（BOM 结构树、部门组织树、菜单树、权限树等）。本文基于 Semi 项目 `BomReport.aspx`（TreeGrid 树表格）和 Main 项目（异步加载/复选框树）的真实用法，给出全部模式。目标是：照本文可在新项目快速复刻各类树控件。

## 一、使用场景与项目实例

| 场景 | 页面 | 树 ID | 数据来源 |
|------|------|-------|---------|
| **BOM 仕样书结构树**（TreeGrid） | `Plugins/Semi/Technology/BomReport.aspx` | `treeBom` | 后台递归构建全量 |
| 部门组织树（异步展开） | `Plugins/Main/BaseInfo/DeptInfo.aspx` | `treeDept` | BeforeLoad + DirectMethod 按需加载 |
| 菜单列表树（异步展开） | `Plugins/Main/SysMenu/SetPageMenu.aspx` | `treeDept` | BeforeLoad + DirectMethod |
| 权限树（带复选框） | `Plugins/Main/SysRole/SetOneRoleInfo.aspx` | `TreePanel1/2` | 后台构建 + CheckChange |
| 功能导航菜单（TreeList） | `Plugins/Main/MainFrame.aspx` | `mainTreePanel` | TreeStore.OnReadData |

> Semi 区目前只有 BomReport 一个真树。新增树建议直接拷贝 BomReport 的结构。

## 二、TreeGrid 树表格（BomReport 范例）— 最完整模式

TreePanel + ColumnModel 混合使用，第一列是树形列（TreeColumn），其余列是普通数据列。效果是一棵带多列数据的"树表格"。

### 2.1 前端声明

```aspx
<ext:TreePanel ID="treeBom" runat="server" Flex="2" Header="true" Title="BOM结构"
               RootVisible="false" UseArrows="true">
    <Store>
        <ext:TreeStore ID="TreeStore" runat="server">
            <Model>
                <ext:Model runat="server">
                    <Fields>
                        <ext:ModelField Name="nodeName" />          <%-- 树列显示文本 --%>
                        <ext:ModelField Name="nodeNum" />           <%-- 定额 --%>
                        <ext:ModelField Name="Width" />             <%-- 宽度 --%>
                        <ext:ModelField Name="CrossSectionalArea" /><%-- 断面积 --%>
                        <ext:ModelField Name="Volume" />            <%-- 体积 --%>
                        <ext:ModelField Name="WorkProcess" />       <%-- 工序 --%>
                        <!-- 更多字段... -->
                    </Fields>
                </ext:Model>
            </Model>
            <Root>
                <ext:Node NodeID="Root" Expanded="true" />          <%-- 虚拟根，RootVisible=false 隐藏 --%>
            </Root>
        </ext:TreeStore>
    </Store>
    <ColumnModel>
        <Columns>
            <ext:TreeColumn DataIndex="nodeName" Text="规格" Width="280" />   <%-- 树形列 --%>
            <ext:Column DataIndex="nodeNum" Text="定额" Width="160" />
            <ext:Column DataIndex="Width" Text="宽度" Width="100" />
            <ext:Column DataIndex="WorkProcess" Text="工序" Width="100" />
            <!-- 更多普通列... -->
        </Columns>
    </ColumnModel>
    <View>
        <ext:TreeView EnableTextSelection="true" />
    </View>
    <SelectionModel>
        <ext:TreeSelectionModel Mode="Single">
            <Listeners>
                <SelectionChange Fn="treeBomSelectionChange" />
            </Listeners>
        </ext:TreeSelectionModel>
    </SelectionModel>
</ext:TreePanel>
```

### 2.2 关键属性说明

| 属性 | 说明 |
|------|------|
| `RootVisible="false"` | 隐藏虚拟根节点（只显示子节点） |
| `UseArrows="true"` | 用箭头图标替代默认的 +/- 展开符号 |
| `Flex="2"` | 在 HBox/VBox 容器中按比例占宽 |
| `<ext:TreeColumn>` | 树形列——承载缩进+展开图标+显示文本，每棵树**有且仅有一个** TreeColumn |
| `<ext:TreeView EnableTextSelection="true">` | 允许选中树节点的文本 |
| `<ext:TreeSelectionModel Mode="Single">` | 单选模式 |

### 2.3 隐藏默认节点图标（可选美化）

```css
.x-tree-icon { display: none; }
```
放在页面 `<style>` 块中，隐藏每个节点左侧的默认文件夹/文件图标。

## 三、后台动态构建树节点

### 3.1 Node 对象属性

```csharp
Node n = new Node();
n.NodeID = "unique_id";           // 节点唯一标识（可选，默认自动生成）
n.Text = "显示文本";               // 显示文本（也可用 CustomAttributes 替代）
n.Icon = Icon.None;               // 图标（Icon.None = 无图标）
n.Leaf = true;                    // true=叶子节点（无展开箭头），false=有子节点
n.Expanded = true;                // true=默认展开，false=默认折叠
n.Checked = false;                // 复选框状态（null=无复选框，true/false=勾选状态）
```

### 3.2 CustomAttributes（节点自定义数据字段）

TreeGrid 的核心——把数据字段挂到节点上，对应前台 ModelField：

```csharp
n.CustomAttributes.Add(new ConfigItem {
    Name = "nodeName",
    Value = root.ParentName + "（" + root.ParentType + "）",
    Mode = ParameterMode.Value
});
n.CustomAttributes.Add(new ConfigItem {
    Name = "nodeNum",
    Value = item.ParentNum + item.ParentUnit + " : " + item.ChildNum + item.ChildUnit,
    Mode = ParameterMode.Value
});
```

> **BomReport 约定**：显示文本走 `CustomAttributes.nodeName` + `<ext:TreeColumn DataIndex="nodeName">`，而非 `n.Text`。这样可以在树列显示富文本（如"部件名（类型）"）。

### 3.3 递归构建 BOM 树（完整范例）

```csharp
[DirectMethod]
public void GetBomTree(string bomCode, string bomVersion, string tyreMaterialCode)
{
    // 1. 查询 BOM 数据（扁平列表）
    var bomList = bomManager.GetDataTableByStatement("SelectBomInfo@SbmBom", param);

    // 2. 清空旧树
    treeBom.GetRootNode().RemoveAll();

    // 3. 找到根节点（ParentCode 为顶层）
    var root = FindRoot(bomList);

    // 4. 构建根节点
    Node n = new Node();
    n.Icon = Icon.None;
    n.Leaf = !bomList.Any(b => b.ParentCode == root.ParentCode);
    n.Expanded = !n.Leaf;
    n.CustomAttributes.Add(new ConfigItem {
        Name = "nodeName",
        Value = root.ParentName + "（" + root.ParentType + "）",
        Mode = ParameterMode.Value
    });

    // 5. 递归挂子节点
    InitTree(n, bomList, root.ParentCode, root.WorkProcess, root.StationName);

    // 6. 挂到 TreeStore 的 Root 下
    treeBom.GetRootNode().AppendChild(n);
}

// 递归构建子节点
private void InitTree(Node parentNode, List<BomItem> bomList, string parentCode, string workProcess, string stationName)
{
    var children = bomList.Where(b => b.ParentCode == parentCode).ToList();
    foreach (var child in children)
    {
        Node childNode = IniNode(child, bomList);   // 构建单个节点（设CustomAttributes）
        parentNode.Children.Add(childNode);

        // 非叶子则递归
        if (!childNode.Leaf)
        {
            InitTree(childNode, bomList, child.ChildCode, child.WorkProcess, child.StationName);
        }
    }
}
```

### 3.4 核心 API 速查

| API | 用途 |
|-----|------|
| `treeBom.GetRootNode()` | 获取根节点 |
| `treeBom.GetRootNode().RemoveAll()` | 清空整棵树 |
| `treeBom.GetRootNode().AppendChild(node)` | 向根追加子节点 |
| `parentNode.Children.Add(childNode)` | 向某节点追加子节点 |
| `n.CustomAttributes.Add(new ConfigItem{...})` | 添加节点数据字段 |

## 四、异步按需加载树（远程加载）

适用于层级深、数据量大的树（部门树、菜单树）。用户展开某节点时才请求其子节点。

### 4.1 前端配置

```aspx
<ext:TreePanel ID="treeDept" runat="server" Region="West" Width="250" Title="部门"
               RootVisible="false" UseArrows="true">
    <Store>
        <ext:TreeStore ID="treeDeptStore" runat="server">
            <Proxy>
                <ext:PageProxy>
                    <RequestConfig Method="GET" Type="Load" />
                </ext:PageProxy>
            </Proxy>
            <Root>
                <ext:Node NodeID="root" Expanded="true" />
            </Root>
        </ext:TreeStore>
    </Store>
    <Listeners>
        <BeforeLoad Fn="treePanelDept" />              <%-- 拦截默认加载，自行调 DirectMethod --%>
        <ItemClick Handler="treeDeptClick(record)" />  <%-- 节点点击 --%>
    </Listeners>
</ext:TreePanel>
```

### 4.2 BeforeLoad 监听（核心）

```javascript
var treePanelDept = function (store, operation, options) {
    var node = operation.node;                    // 当前要加载的节点
    var nodeid = node.getId() || "";

    App.direct.treePanelDeptLoad(nodeid, {        // 调后台 DirectMethod 加载子节点
        success: function (result) {
            node.set('loading', false);
            node.set('loaded', true);
            var data = Ext.decode(result);        // result = JSON 字符串
            if (data != "") {
                node.appendChild(data, undefined, true);  // 附加子节点
                node.expand();
            }
        },
        failure: function (errorMsg) { Ext.Msg.alert('错误', errorMsg); }
    });
    return false;   // 阻止默认加载行为
};
```

> 本项目**不用** `<Loader><ext:TreeLoader DataUrl="xxx.ashx" /></Loader>` 声明式加载，而是用 `BeforeLoad` + DirectMethod + `node.appendChild(JSON)` 命令式加载。

### 4.3 后台 DirectMethod 返回格式

返回 Ext.tree 标准 Node JSON 数组：

```json
[
  {
    "id": "node_id",
    "text": "显示文本",
    "leaf": true,
    "expanded": false,
    "children": [],
    "nodeName": "...",
    "SHOW_NAME": "...",
    "OBJID": "..."
  }
]
```

每条含：`id`（节点ID）/ `text`（显示）/ `leaf`（叶子标志）/ `expanded` / `children`（子数组）+ 与 TreeStore ModelField 同名的自定义字段。前台 `node.appendChild(Ext.decode(result))` 直接消费。

## 五、复选框树（权限树）

### 5.1 声明

```aspx
<ext:TreePanel ID="TreePanel1" runat="server" MultiSelect="true" UseArrows="true"
               Title="权限分配">
    <Listeners>
        <CheckChange Fn="onTreeCheckChange" />
    </Listeners>
</ext:TreePanel>
```

### 5.2 节点设复选框

后台构建节点时设 `Checked` 属性：

```csharp
Node n = new Node();
n.Text = menuName;
n.Leaf = true;
n.Checked = hasPermission;   // true=勾选, false=未勾选, null=不显示复选框
```

> **注意**：复选框通过 `Node.Checked` + `<Listeners><CheckChange Fn="..."/>` 实现，**不用** `CheckboxSelectionModel`。

### 5.3 递归获取选中节点

```javascript
var getTreeSelectionModel = function (nodes) {
    var selected = [];
    for (var i = 0; i < nodes.length; i++) {
        if (nodes[i].data.checked) {
            selected.push(nodes[i].data.id);
        }
        if (nodes[i].childNodes && nodes[i].childNodes.length > 0) {
            selected = selected.concat(getTreeSelectionModel(nodes[i].childNodes));
        }
    }
    return selected;
};
```

## 六、树的事件汇总

| 事件 | 触发时机 | 用法 |
|------|---------|------|
| `SelectionChange` | 节点选中变化（TreeSelectionModel） | `<Listeners><SelectionChange Fn="..." /></Listeners>` |
| `ItemClick` | 节点点击 | `<Listeners><ItemClick Handler="fn(record)" />` |
| `Select` | 节点选中 | `<Listeners><Select Fn="..." />` |
| `BeforeLoad` | 节点加载前（异步拦截） | `<Listeners><BeforeLoad Fn="..." />` |
| `CheckChange` | 复选框状态变化 | `<Listeners><CheckChange Fn="..." />` |
| `ItemContextMenu` | 右键菜单 | 本项目未使用 |

### 节点选中事件处理（BomReport 范例）

```javascript
var treeBomSelectionChange = function (item, selected) {
    if (selected.length == 1) {
        var record = selected[0];
        // 取节点的自定义字段
        var nodeName = record.get('nodeName');
        var workProcess = record.get('WorkProcess');

        // 取子节点数据
        if (record.childNodes.length > 0) {
            var childWorkProcess = record.childNodes[0].data.WorkProcess;
        }

        // 调后台加载右侧详情
        App.direct.GetBomTech(bomCode, bomVersion, workProcess, materialCode, {
            success: function () { },
            failure: function (msg) { Ext.Msg.alert('错误', msg); }
        });
    }
};
```

## 七、TreeList（轻量级导航树）

`Plugins/Main/MainFrame.aspx` 用的是 `<ext:TreeList>`（不是 `TreePanel`），更轻量：

```aspx
<ext:TreePanel ID="mainTreePanel" runat="server" Layout="FitLayout">
    <Store>
        <ext:TreeStore runat="server" OnReadData="GetUserPageGroup">
            <Root><ext:Node NodeID="root" Expanded="true" /></Root>
            <Listeners><BeforeLoad Fn="nodeLoad" /></Listeners>
        </ext:TreeStore>
    </Store>
</ext:TreePanel>
```

> `OnReadData="GetUserPageGroup"` 是 code-behind 的事件处理器（非 DirectMethod），后台通过 `e` 参数返回数据。

## 八、刷新树

工具栏刷新按钮：

```aspx
<TopBar>
    <ext:Toolbar runat="server">
        <Items>
            <ext:Tool Type="Refresh" Handler="refreshTree(#{treeDept});" />
        </Items>
    </ext:Toolbar>
</TopBar>
```

```javascript
var refreshTree = function (tree) {
    App.direct.InitMenuTree({       // 调后台重新加载整棵树
        success: function () { },
        failure: function (msg) { Ext.Msg.alert('错误', msg); }
    });
};
```

## 九、完整复刻模板（BOM 树表格）

```aspx
<%-- 1. 布局：左侧树 + 右侧详情 --%>
<ext:Panel Region="Center" Layout="HBoxLayout">
    <LayoutConfig><ext:HBoxLayoutConfig Align="Stretch" /></LayoutConfig>
    <Items>
        <%-- 2. 左侧树 --%>
        <ext:TreePanel ID="treeBom" runat="server" Flex="1" Title="结构树"
                       RootVisible="false" UseArrows="true" Header="true">
            <Store>
                <ext:TreeStore ID="TreeStore" runat="server">
                    <Model>
                        <ext:Model runat="server">
                            <Fields>
                                <ext:ModelField Name="nodeName" />
                                <ext:ModelField Name="nodeNum" />
                                <ext:ModelField Name="WorkProcess" />
                            </Fields>
                        </ext:Model>
                    </Model>
                    <Root><ext:Node NodeID="Root" Expanded="true" /></Root>
                </ext:TreeStore>
            </Store>
            <ColumnModel>
                <Columns>
                    <ext:TreeColumn DataIndex="nodeName" Text="名称" Width="280" />
                    <ext:Column DataIndex="nodeNum" Text="定额" Width="160" />
                    <ext:Column DataIndex="WorkProcess" Text="工序" Flex="1" />
                </Columns>
            </ColumnModel>
            <SelectionModel>
                <ext:TreeSelectionModel Mode="Single">
                    <Listeners><SelectionChange Fn="treeNodeSelect" /></Listeners>
                </ext:TreeSelectionModel>
            </SelectionModel>
        </ext:TreePanel>

        <%-- 3. 右侧详情（选中节点后加载） --%>
        <ext:Panel ID="pnlDetail" runat="server" Flex="2" Title="详情" Header="true">
            <Items>
                <!-- 详情内容 -->
            </Items>
        </ext:Panel>
    </Items>
</ext:Panel>
```

## 十、TreeColumn 条件着色（Renderer 改变节点文字颜色）

树状展开图中，根据节点携带的特殊信息（如状态、标记字段），**动态改变节点文字颜色**，让特殊节点醒目显示。

典型用途：异常/停机节点标红、关键工序节点标蓝、已完成节点标灰。

### 10.1 aspx：TreeColumn 加 Renderer

```xml
<ext:TreeColumn runat="server" Text="No." DataIndex="text" Width="400">
    <Renderer Fn="applyConditionalColor" />
</ext:TreeColumn>
```

Model 需声明着色标记字段：

```xml
<ext:ModelField Name="color" />   <!-- 着色标记字段 -->
```

### 10.2 JS：Renderer 函数

```javascript
function applyConditionalColor(value, meta, record) {
    if (record.data.color == 1) {
        meta.style = "color:red;";
    }
    return value;   // 必须 return value，否则节点文字不显示
}
```

- `value`：单元格当前值（节点文本）。
- `meta`：单元格元数据，设 `meta.style` 改样式，或 `meta.tdCls` 加 CSS 类名。
- `record`：当前节点记录，`record.data.color` 取标记字段。

### 10.3 多色标记

```javascript
function applyConditionalColor(value, meta, record) {
    var color = record.data.color;
    if (color == 1) {
        meta.style = "color:red;";        // 异常 - 红
    } else if (color == 2) {
        meta.style = "color:#f4c414;";    // 警告 - 黄
    } else if (color == 3) {
        meta.style = "color:#337ab7;";    // 关键 - 蓝
    }
    return value;
}
```

### 10.4 后台传递 color 标记

```csharp
// CustomAttributes 方式（与本章前面节点构建风格一致）
node.CustomAttributes.Add(new ConfigItem("color", "1", ParameterMode.Value));
```

### 10.5 注意

- **color 字段必须在前台 Model 里声明 ModelField**，否则 `record.data.color` 取不到值。
- `meta.style` 会覆盖内联样式；需叠加用 `meta.style += "font-weight:bold;"`。
- TreeColumn **每棵树只有一个**（承载缩进+展开图标），给它加 Renderer 即影响主显示列。

### 10.6 与 GridPanel 行底色高亮的对比

| 维度 | TreeColumn Renderer | GridPanel GetRowClass |
|------|---------------------|----------------------|
| 作用对象 | 单列单元格（树形列文字） | 整行底色 |
| 配置位置 | Column 的 `<Renderer Fn="..."/>` | GridView 的 `<GetRowClass Fn="..."/>` |
| 着色方式 | `meta.style` / `meta.tdCls` | 返回 CSS 类名 |

> GridPanel 行底色高亮实战：见 `extnet-row-highlight-expiry.md`

## 十一、复刻注意事项

1. **TreeColumn 有且仅有一个**——它是承载树形缩进的列，多个 TreeColumn 会渲染异常
2. **RootVisible="false"** 配合虚拟根使用——用户只看到业务子节点，看不到虚拟根
3. **CustomAttributes + ModelField 对应**——后台 `ConfigItem.Name` 必须与前台 `ModelField Name` 完全一致
4. **异步加载用 BeforeLoad + DirectMethod**，不用 TreeLoader DataUrl（本项目风格）
5. **复选框用 Node.Checked + CheckChange**，不用 CheckboxSelectionModel
6. **清空树用 `GetRootNode().RemoveAll()`**，否则重新加载会叠加旧数据
7. **Leaf 判断**：`n.Leaf = !data.Any(b => b.ParentCode == item.Code)`（没有子数据就是叶子）
8. **CSS 隐藏图标**：`.x-tree-icon { display: none; }` 让树更简洁

## 十二、关联文档

| 文档 | 关系 |
|------|------|
| `semi-craft-technology.md` | BOM/仕样书的业务含义与数据结构 |
| `bom-report-attachment.md` | BOM 报表与 FTP 附件上传 |
| `extnet-page-skeleton.md` | 页面骨架（树在 HBoxLayout 中的位置） |
| `extnet-event-mechanisms.md` | DirectMethod / Listeners 事件机制 |
| `extnet-directmethod-and-data.md` | 后台数据访问（构建树的数据来源） |
| `extnet-row-highlight-expiry.md` | GridPanel 行底色高亮（GetRowClass 对比） |

---

## 十三、条件着色常见踩坑（实战排错）

> 来源：Batch 项目 `CustomTracing.aspx`（海关批次追溯）真实排障。现象：后端断点确认 `color=1`，前端节点不变红。根因不在渲染器，而在 CustomAttributes 的重复 Add。

### 13.1 坑一：重复 `CustomAttributes.Add` 同名键，后者覆盖前者（最易中招）

**错误代码**（两个 if 同时命中时，会往同一节点 Add 两个名为 `color` 的 ConfigItem）：

```csharp
if (!string.IsNullOrEmpty(colorlist))
{
    result.CustomAttributes.Add(new ConfigItem("color", 条件A命中 ? 1 : 0));
}
if (Hidden1_batchcode.Value != null && !string.IsNullOrEmpty(Hidden1_batchcode.Value.ToString()))
{
    result.CustomAttributes.Add(new ConfigItem("color", 条件B命中 ? 1 : 0));   // 又 Add 一次！
}
```

**根因**：`Node.CustomAttributes` 是 `List<ConfigItem>`，`Add` 不去重。`NodeCollection.ToJson()` 序列化时会输出两个同名 `"color"` 键到 JSON。浏览器 `JSON.parse` 遇到重复键**只保留最后一个**。结果：

- 断点看到第一处算出 `color=1`（你以为对了）；
- 实际发到前端的 JSON 是第二处的值，可能为 0；
- 前端渲染器拿到 0，自然不变红。

**排查方法**：F12 → Network → 找到加载该节点的 DirectMethod 响应，看 JSON 里该节点 `color` 字段实际值；或在 Renderer 里 `console.log(record.data.color)`。

**修复**：先算后只 Add 一次。两条规则「任一命中即标红」时用逻辑或合并：

```csharp
int color = 0;
if (!string.IsNullOrEmpty(colorlist) && colorlist.Contains(barcode))
    color = 1;
if (!string.IsNullOrEmpty(Hidden1_batchcode.Value?.ToString())
    && barcode.Contains(Hidden1_batchcode.Value.ToString().Trim()))
    color = 1;
result.CustomAttributes.Add(new ConfigItem("color", color));   // 只 Add 一次
```

> 若业务规则是「后者为准」，同样只 Add 一次，让第二段覆盖变量即可，绝不要 Add 两次。

### 13.2 坑二：前后端类型不一致（ModelField Type=String vs 后端传 int）

后端 `new ConfigItem("color", 1)`（C# int），序列化为 JSON 数字 `1`；但前台 Model 声明成 `Type="String"`，Ext.NET 按声明类型解析后 `record.data.color` 可能是字符串 `"1"`。

- 用 `== 1`（弱比较）通常能容忍 `"1" == 1`；
- 但一旦配合 `=== 1`（严格比较）或参与数值运算，`"1" === 1` 为 false，着色失效。

**修复**：前后端类型对齐。后端传 int 时，前台用 `Type="Int"`，渲染器用 `=== 1`。

```xml
<ext:ModelField Name="color" Type="Int"></ext:ModelField>
```

```javascript
function applyConditionalColor(value, meta, record) {
    if (record.data.color === 1) {        // 配合 Int 类型用严格比较
        meta.style = "color:red;";
    }
    return value;
}
```

### 13.3 排查清单（节点该变色却没变）

按顺序自查，多数情况命中前两条：

1. **CustomAttributes 是否重复 Add 同名键？** → 见 13.1，最常见根因。
2. **JSON 实际下发的值对吗？** → Network 看响应，别只信断点。
3. **前台 Model 是否声明了该 ModelField？** → 没声明则 `record.data.color` 为 undefined。
4. **前后端类型是否一致？** → 见 13.2，int/String 对齐。
5. **Renderer 是否挂在 TreeColumn 上？** → 挂到普通 Column 不影响树形列文字。
6. **是否被更高优先级样式盖住？** → 如行底色 `.x-grid-row-choose` 带 `!important`，或 `.x-grid-cell-inner` 背景。`meta.style` 是单元格 inline 样式，可能被行级 `!important` 背景压过；这种情况改用 `meta.tdCls` + 自定义 CSS 类，或在 CSS 里对文字色也加 `!important`。

---

## 十四、树表格条纹行（TreeView 无 StripeRows 的 CSS 方案，2026-08-27 Molding 实证）

> 来源：Molding `MoldProductionTrace.aspx`（成型生产追溯三级树）实测——CSS 第一版 `tr:nth-child(even)` 不生效，浏览器 DOM 实测定位根因后修正。

### 14.1 为什么不能直接用 StripeRows

`<ext:TreeView>` **没有 `StripeRows` 属性**（GridView 才有；经 Bin\Ext.Net.xml 成员清单证实，TreeView 仅暴露 Animate/RootVisible/ToggleOnClick/ToggleOnDblClick/XType），Ext.NET 也没给 TreePanel 提供 viewConfig 注入通道。

### 14.2 Ext 5.1 树表格的真实 DOM（关键，选择器写错的全因）

树表格**每一行是一个独立的 `<table><tbody><tr class="x-grid-row">`**，行与行不是同一个 tbody 里的兄弟——`tr:nth-child(even)` 永远只匹配"tbody 独生子"，一行都刷不出来。正确结构：

- 38 行数据 = 38 个 `<table>`，包在 38 个 `.x-grid-item` 容器 div 里；
- 全部 `.x-grid-item` **同级相邻**排在同一个 `.x-grid-item-container` 内（用 `.x-grid-item + .x-grid-item` 计数=行数-1 可验证）；
- 单元格 td 类名 `x-grid-cell`（树列额外带 `x-grid-cell-treecolumn`）。

### 14.3 正确 CSS（直接抄）

```css
/* TreePanel 挂 Cls="tree-stripe" */
.tree-stripe .x-grid-item:nth-child(even):not(.x-grid-item-selected):not(.x-grid-item-over) .x-grid-cell {
    background-color: #eef2f7;
}
```

- `:not(.x-grid-item-selected)` / `:not(.x-grid-item-over)`：保住主题选中色与悬停色（不加会被条纹色盖掉）；
- **颜色必须 ≥ #eef2f7 级别**：`#fafafa`（Ext 官方 alt 色）与白色仅差 2.5%，肉眼看不出，已实证被打回；#eef2f7（浅蓝灰）配项目冷色调主题。

### 14.4 验证手段：locator 计数探针（比截图可靠）

CSS 选择器本身可直接当 Playwright/Selenium 的 locator 计数：38 行×6 列时，用该选择器 count 应恰为 19×6=114（= 总单元格一半）。命中数对 = 规则生效，不受截图 JPEG 压缩、视觉模型误判影响。

### 14.5 同场景两个配套坑

1. **`new ConfigItem(name, value, ParameterMode.Value)` 第二参数必须 string**——本版本 Ext.NET 该构造签名是 `(string, string, ParameterMode)`，没有 `(string, object, ParameterMode)`；传 int 字面量（如 NodeType 的 0/1/2）报 **CS1502**。数值标记传 `"0"` 字符串，前台 ModelField 声明 `Type="Int"` 自动转数字，JS `record.get('NodeType') !== 2` 严格比较不受影响（与 13.2 前后端类型对齐同一主题的编译层兄弟坑）。
2. **ComboBox 默认选中第一项**用服务端 `cbx.Select(0)`（C# 方法、大写 S，Page_Load 绑完 Store 后调）；`ComboBox` 没有 `SelectedIndex` 属性（CS1061），也不需要前端 AfterRender `select(0)` 兜底。