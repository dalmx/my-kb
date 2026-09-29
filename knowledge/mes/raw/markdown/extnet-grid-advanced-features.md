---
title: Ext.NET GridPanel 高级特性完整指南
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [GridPanel, 高级特性, Locking_Grid, 锁定列, 冻结列, 表头分组, Infinite_Scrolling, 无限滚动, Spreadsheet, FilterHeader, ComponentColumn, RowExpander]
updated: 2026-09-17
status: active
---

# Ext.NET GridPanel 高级特性完整指南

> 本文档从 Ext.NET 4.7.1 官方示例库 `Examples/GridPanel/` 提炼 Grid 的高级特性：锁定列、无限滚动、电子表格选区、表头筛选、组件列、行展开。补强已有 `extnet-grid-complete-guide.md`。
>
> 适用：Ext.NET 4.x + Triton 主题。

---

## 一、Locking_Grid 锁定列（冻结窗格）

通过 **Column 的 `Locked="true"`** 实现，Grid 自动把锁定列拆到左侧固定区。

```aspx
<ext:GridPanel runat="server" Title="锁定列" Width="600" Height="350">
    <Store>...</Store>
    <ColumnModel>
        <Columns>
            <ext:RowNumbererColumn runat="server" />
            <!-- 锁定列：钉在左侧 -->
            <ext:Column runat="server" Text="公司" DataIndex="company"
                Width="200" Locked="true" />
            <!-- 不可锁定：永远在滚动区 -->
            <ext:Column runat="server" Text="价格" DataIndex="price"
                Width="125" Lockable="false" />
            <ext:Column runat="server" Text="涨跌" DataIndex="change" Width="125" />
        </Columns>
    </ColumnModel>
</ext:GridPanel>
```

| 属性 | 作用 |
|------|------|
| `Locked="true"` | 钉在左侧锁定区 |
| `Lockable="false"` | 禁止用户切换锁定状态 |

> 只支持**左侧锁定**；至少一列未锁定。可与无限滚动、分组、编辑叠加。

### 1.1 与表头分组（嵌套列）共存——2026-09-17 实证结论 ⚠️

ExtJS locked grid 是**两个独立 grid**（LockedView + NormalView 各有 header container），分组列头**不能横跨锁定/滚动两区**。在 Sencha 官方示例页（ExtJS 7.9 examples，classic Lockable 机制 6.x→7.x 一致）动态实验，四种做法的实测行为：

| 做法 | 实测行为 |
|------|---------|
| 组内子列声明式 `locked: true`（初始化配置） | **被 ExtJS 静默忽略**——锁定区只收顶层列的 locked 标志，嵌套组内子列原样留在滚动区，无报错无效果 |
| 运行时 API `grid.lock(子列)` | 子列被**拔出分组**变锁定区顶层列，**组头丢失**（表头层级破坏） |
| ✅ **整组锁定**：组列本身 `Locked="true"` | 正常生效——全部子列随组进锁定区，组头完整渲染（**项目首选**，写法最简） |
| ✅ **拆同名组**：锁定边界两侧各放一个同名组 | 正常渲染——锁定区组头 + 滚动区组头各显示一次（仅当需要"锁到组内某列"时用） |

**写法 A：整组锁定（首选）**——要锁定的分组列整体加 Locked，子列不动：

```aspx
<ext:Column runat="server" Text="成型" Locked="true">
    <Columns>
        <ext:Column runat="server" Text="生产机台" ... />
        ...该组全部子列...
    </Columns>
</ext:Column>
```

**写法 B：拆同名组**——确需锁定边界切在某分组内部时，两侧各放一个同名组（锁定区组整体 `Locked="true"`）：

```aspx
<!-- 锁定区组 -->
<ext:Column runat="server" Text="成型" Locked="true">
    <Columns>
        <ext:Column runat="server" Text="生产机台" ... />
        ...要锁定的前几个子列...
    </Columns>
</ext:Column>
<!-- 滚动区组：同名，装剩余子列 -->
<ext:Column runat="server" Text="成型">
    <Columns>
        <ext:Column runat="server" Text="G/T重量" ... />
        ...其余子列...
    </Columns>
</ext:Column>
```

> 实证样例：Quality 成型合格率波动追踪（MoldingQualifiedRate.aspx）最终采用**写法 A 整组锁定**（检测时间 + 整个"成型"组 8 子列）；初版曾按"锁到成型下生产时间"用写法 B 拆组（渲染验证通过），用户验收改为整组——两种写法均合法，整组优先。

### 1.2 C# 动态列（reconfigure）场景

列由后置代码 `grid.ColumnModel.Columns.Add(new Ext.Net.Column {...})` 动态构建再 `grid.Render()` 的页面，直接加 `Locked = true` 即可，与既有 `grid.Render()` 流程兼容（Quality 硫化/成型机别合格率两页实证落地）：

```csharp
grid.ColumnModel.Columns.Add(new Ext.Net.Column
{
    Text = "OE/RE",
    DataIndex = "OERE",
    Width = 70,
    Align = ColumnAlign.Center,
    Locked = true
});
```

### 1.3 McUI 框架 xml 列定义

McUI 的 `<GridColumn>` 节点支持 `Locked="true"`（先例：ReportQualityDetailInfo.xml 的 ID、TYRE_NO 列）：

```xml
<GridColumn ColumnName="TYRE_NO" Width="120" Locked="true"></GridColumn>
```

### 1.4 项目落地惯例

- "锁定列到 XX" = **从第一列（含 RowNumbererColumn/ImageCommandColumn 操作列）到 XX 列全部加 `Locked="true"`**，前导连续；跨页批量实施见 [[quality-locked-columns-implementation]]。
- 目标列落在表头分组内时，**默认整组锁定**（用户 2026-09-17 验收口径），拆同名组仅当用户明确要"锁到组内某列为止"时用。
- 页面若已有单元格 Tooltip（Delegate 写法），锁定列会让 DataIndex 式 Delegate 失效，须改 Column ID 写法并从 `view.LockedView` 取行（详见 `extnet-grid-tooltip-delegate.md` 第八节）。
- 锁定列会改变 celldblclick 事件 `cellIndex` 的语义（区域内序号而非全列序号）：若事件处理里按 `store.model.getFields()[cellIndex]` 反查列名，锁定**恰好是前 N 列**时序号不变、行为保持；否则需改用 `column.dataIndex`。

---

## 二、Infinite_Scrolling 无限滚动（虚拟滚动）

用 **Buffered Store** 按需远程拉取，垂直滚动时只渲染可视区行。

```aspx
<ext:GridPanel runat="server" Width="500" Height="500" DisableSelection="true">
    <Store>
        <ext:Store runat="server"
            Buffered="true"
            PageSize="200"
            LeadingBufferZone="10"
            TrailingBufferZone="10"
            OnReadData="Store_ReadData">
            <Proxy>
                <ext:PageProxy>
                    <Reader><ext:JsonReader RootProperty="data" /></Reader>
                </ext:PageProxy>
            </Proxy>
            <Model>...</Model>
        </ext:Store>
    </Store>
    <ColumnModel>...</ColumnModel>
    <ViewConfig TrackOver="false" />
</ext:GridPanel>
```

```csharp
protected void Store_ReadData(object sender, StoreReadDataEventArgs e)
{
    var data = LoadData(e.Start, e.Limit);
    ((Store)sender).Data = data;
    e.Total = 50000;   // 关键：回写总条数，否则滚动条长度不对
}
```

| Store 属性 | 作用 |
|-----------|------|
| `Buffered="true"` | 启用虚拟滚动 |
| `PageSize="200"` | 每页拉取条数（建议 100~200） |
| `LeadingBufferZone` / `TrailingBufferZone` | 向前/向后预渲染行数 |
| `RemoteSort="true"` | 排序交服务端 |

> 自 ExtJS 6 起 BufferedRenderer 默认开启，所有 Grid 自动虚拟渲染。数据 < 5 万行无需远程分页；超大数据量才用 `Buffered="true"`。

---

## 三、Spreadsheet 电子表格选区

用 **`SpreadsheetSelectionModel`** 替换默认选区模型，支持 Excel 风格单元格/行/列选区、Ctrl+C 复制。

```aspx
<ext:GridPanel runat="server" ColumnLines="true" Height="400">
    <Store>...</Store>
    <SelectionModel>
        <ext:SpreadsheetSelectionModel runat="server"
            ColumnSelect="true"
            CheckboxSelect="true"
            PruneRemoved="false"
            Extensible="Y" />
    </SelectionModel>
    <ColumnModel>...</ColumnModel>
    <Plugins>
        <ext:Clipboard runat="server" />
        <ext:SelectionReplicator runat="server" />
    </Plugins>
</ext:GridPanel>
```

| 配置 | 作用 |
|------|------|
| `ColumnSelect="true"` | 允许点列头选整列 |
| `CheckboxSelect="true"` | 左上角全选框 |
| `PruneRemoved="false"` | 翻页保留已选（与 Buffered 搭配） |
| `Extensible="Y"` | 选区可拖拽扩展（`Y`/`X`/`both`/`null`） |
| `ext:Clipboard` 插件 | 启用 Ctrl+C/X/V 剪贴板 |
| `ext:SelectionReplicator` | 拖拽填充柄复制 |

**提交选区到服务端**：

```aspx
<ext:Button runat="server" Text="提交">
    <DirectEvents>
        <Click OnEvent="Submit">
            <ExtraParams>
                <ext:Parameter Name="Values"
                    Value="App.SSM1.getSubmitData({excludeId:true})"
                    Mode="Raw" Encode="true" />
            </ExtraParams>
        </Click>
    </DirectEvents>
</ext:Button>
```

---

## 四、FilterHeader 表头筛选

`FilterHeader` 是插件，挂上后每列头下方自动出现筛选输入框。

```aspx
<ext:GridPanel runat="server">
    <Store>...</Store>
    <ColumnModel>...</ColumnModel>
    <Plugins>
        <ext:FilterHeader runat="server" />
    </Plugins>
</ext:GridPanel>
```

**操作符语法**（在筛选框输入）：

| 类型 | 操作符 |
|------|--------|
| 字符串 | `=`等于、`+`开头、`-`结尾、`*`包含、`!`不包含 |
| 数字 | `>` `<` `>=` `<=` 或具体值；区间 `>50<70` |
| 日期 | `>` `<` 或具体值 |
| 布尔 | `1`/`0`/`true`/`false` |

**远程筛选**：

```aspx
<ext:FilterHeader runat="server" Remote="true" />
```

```csharp
protected void Store_ReadData(object sender, StoreReadDataEventArgs e)
{
    FilterHeaderConditions fhc = new FilterHeaderConditions(e.Parameters["filterheader"]);
    foreach (FilterHeaderCondition c in fhc.Conditions)
    {
        // c.DataIndex / c.Type / c.Operator / c.Value<T>()
    }
}
```

---

## 五、ComponentColumn 组件列（单元格内放控件）

特殊列，`<Component>` 子标签放任意控件，渲染到每个单元格。

### 静态展示型

```aspx
<ext:ComponentColumn runat="server" Flex="1" Text="进度">
    <Component>
        <ext:ProgressBar runat="server" />
    </Component>
    <Listeners>
        <Bind Handler="cmp.setValue(record.get('Percentage'));" />
    </Listeners>
</ext:ComponentColumn>
```

`Bind` 事件参数：`cmp`（组件）、`record`（行记录）。

### 编辑型

```aspx
<ext:ComponentColumn runat="server" Editor="true" DataIndex="Count" Text="数量">
    <Component>
        <ext:NumberField runat="server" />
    </Component>
</ext:ComponentColumn>
```

`Editor="true"` + `DataIndex` → 组件值与字段双向绑定。

### 悬停编辑型

```aspx
<ext:ComponentColumn runat="server" Editor="true" OverOnly="true"
    DataIndex="Status" PinEvents="expand" UnpinEvents="collapse">
    <Component><ext:ComboBox runat="server">...</ext:ComboBox></Component>
</ext:ComponentColumn>
```

| 属性 | 作用 |
|------|------|
| `Editor="true"` | 编辑模式 |
| `OverOnly="true"` | 鼠标悬停才显示组件 |
| `PinEvents` / `UnpinEvents` | 用控件事件钉住组件（防移出消失） |

---

## 六、RowExpander 行展开

插件，给每行加展开箭头，展开显示详情。

### 本地模板（最常用）

```aspx
<ext:GridPanel runat="server">
    <Store>...</Store>
    <ColumnModel>...</ColumnModel>
    <Plugins>
        <ext:RowExpander runat="server">
            <Template runat="server">
                <Html>
                    <p><b>公司：</b> {company}</p>
                    <p><b>简介：</b> {desc}</p>
                </Html>
            </Template>
        </ext:RowExpander>
    </Plugins>
</ext:GridPanel>
```

`{字段名}` 取本行 record 数据（XTemplate 语法）。

### 远程数据（DirectMethod）

```aspx
<ext:RowExpander runat="server">
    <Loader runat="server" Mode="Data" DirectMethod="#{DirectMethods}.GetDetail">
        <LoadMask ShowMask="true" />
        <Params>
            <ext:Parameter Name="id" Value="this.record.getId()" Mode="Raw" />
        </Params>
    </Loader>
    <Template runat="server">
        <Html>详情：{detail}（{time}）</Html>
    </Template>
</ext:RowExpander>
```

```csharp
[DirectMethod]
public object GetDetail(Dictionary<string, string> parameters)
{
    int id = Convert.ToInt32(parameters["id"]);
    return new { detail = GetDetailText(id), DateTime.Now.ToString() };
}
```

### 远程组件（展开内嵌子 Grid）

```aspx
<ext:RowExpander runat="server">
    <Loader runat="server" DirectMethod="#{DirectMethods}.GetGrid" Mode="Component">
        <Params>
            <ext:Parameter Name="id" Value="this.record.getId()" Mode="Raw" />
        </Params>
    </Loader>
</ext:RowExpander>
```

```csharp
[DirectMethod]
public string GetGrid(Dictionary<string, string> parameters)
{
    int id = Convert.ToInt32(parameters["id"]);
    var grid = new GridPanel { ... };
    return ComponentLoader.ToConfig(grid);
}
```

---

## 七、特性速查对照表

| 特性 | 宿主 | 关键标签 | 适用场景 |
|------|------|---------|---------|
| 锁定列 | Column | `Locked="true"` | 宽表保留主键列 |
| 无限滚动 | Store | `Buffered="true"` | 万行级日志/流水 |
| 电子表格选区 | SelectionModel | `SpreadsheetSelectionModel` | 复制粘贴到 Excel |
| 表头筛选 | Plugins | `FilterHeader` | 报表列筛选 |
| 组件列 | ColumnModel | `ComponentColumn` | 行内进度条/操作按钮 |
| 行展开 | Plugins | `RowExpander` | 主从表/详情折叠 |

---

## 八、踩坑要点

### 坑1：无限滚动必须回写 e.Total

```csharp
e.Total = 50000;   // 不写则滚动条长度为 0
```

### 坑2：Spreadsheet + Buffered 要 PruneRemoved="false"

否则翻页时已选记录被清除。

### 坑3：FilterHeader 远程模式要配 PageProxy + OnReadData

本地模式直接过滤前端数据；远程模式 Store 必须有 `OnReadData`，从 `e.Parameters["filterheader"]` 解析。

### 坑4：RowExpander 远程组件的限制

嵌套 Grid 无斑马线、无 hover 跟踪、父子不能同时用选区、必须 `EnableColumnHide="false"`、无自动高度。

### 坑5：ComponentColumn 编辑型要配 DataIndex

```aspx
<ext:ComponentColumn Editor="true" DataIndex="字段名">   <!-- 必须有 DataIndex -->
```

### 坑6：锁定列只支持左侧

ExtJS 6 的 locking 只支持左侧锁定。要"右侧固定"，把想固定的列设 `Locked="true"` 排在 Columns 最前。

### 坑7：分组表头内的子列锁定会静默失效（2026-09-17 实证）⚠️

锁定 grid 内部是两个独立 header container，**分组列头不能横跨锁定/滚动两区**：

- 组内子列写声明式 `Locked="true"` → ExtJS 初始化时**静默忽略**（无报错、不锁定）；
- 运行时 `grid.lock(子列)` → 子列被拔出分组、组头丢失。

**正确做法（二选一）**：①**组列整体 `Locked="true"`**（首选，全部子列随组进锁定区）；②锁定边界必须切在组内时，**拆成两个同名组**放在边界两侧，锁定区组整体 Locked（见 1.1 节两种写法与实证样例）。

### 坑8：锁定列与单元格 Tooltip Delegate 冲突

锁定列会让 DataIndex 式 Delegate 取不到（ExtJS 整体小写化 + 锁定区取数路径变化），须改 Column ID 写法并从 `view.LockedView` 查行——详见 `extnet-grid-tooltip-delegate.md` 第八节。

---

## 九、FilterHeader matchAnywhere：筛选框直接输入即模糊（生产同款）

第四节 FilterHeader 默认字符串语义要操作符前缀（`=`等于、`*`包含等）。**要"用户直接输入文字就模糊包含匹配"**，挂一段自定义行为 JS——Quality 子系统 5 个生产页在用（MoldingQualifiedRate / FixStockQuery / QualityStockQueryByTime / TyreCheckQueryNew / SetUserFormAction，另有 TireFlowRecord），写法逐字照抄：

```js
Ext.net.FilterHeader.behaviour.addBehaviour("string", {
    name: "matchAnywhere",
    is: function (value) {
        return true;
    },
    getValue: function (value) {
        return { value: value, valid: value.length >= 0 };
    },
    match: function (recordValue, matchValue) {
        if (matchValue.length == 0) {
            return true;
        }
        if (recordValue != null) {
            try {
                regexp = new RegExp(matchValue, 'gi');
                if (recordValue.match(regexp)) {
                    return true;
                }
            } catch (e) { }
        }
        return false;
    }
});
```

要点：
- 放页面 head 的 `<script type="text/javascript">` 里（ResourceManager 之后、首次用前）；`is: return true` 使所有字符串筛选走本行为，**覆盖默认操作符语义**——挂了之后 `=`/`*` 前缀按普通字符处理（正则里 `*` 开头会 catch 掉返回 false），验收口径要写"直接输入片段"而不是操作符语法。
- 匹配是 RegExp `'gi'`（大小写不敏感），支持正则（如 `^UF` 只匹配开头）。
- 场景选型：查询条件要模糊→SQL LIKE（注意 `'%%'` 全表扫）；**查询后的结果集内模糊→FilterHeader+matchAnywhere（纯前端，推荐默认）**——追溯/台账类页面"胎号精确查 + 页内模糊筛"就是这套组合（[[tire-flow-record-implementation]]）。

---

## 十、关联文档

| 文档 | 关系 |
|------|------|
| `extnet-grid-complete-guide.md` | GridPanel 基础（列系统/事件/合计行） |
| `extnet-store-databinding-guide.md` | Store（无限滚动的数据基础） |
| `extnet-editor-and-loaders-guide.md` | Loaders（RowExpander 远程加载） |
| `extnet-pagination-guide.md` | 分页（与无限滚动对比） |
| `extnet-grid-tooltip-delegate.md` | 锁定列场景的 Tooltip Delegate 取数（第八节） |
| `quality-locked-columns-implementation.md` | Quality 9 报表页锁定列批量实施记录 |

## 十一、参考来源

- `Examples/GridPanel/Locking_Grid/`（锁定列；含 GroupingSummary_with_group_headers——但官方仅演示"锁普通列+组整体不锁"，未覆盖组内部分锁定）
- `Examples/GridPanel/Infinite_Scrolling/`（无限滚动）
- `Examples/GridPanel/Spreadsheet/`（电子表格选区）
- `Examples/GridPanel/FilterHeader/`（表头筛选）
- `Examples/GridPanel/ComponentColumn/`（组件列）
- `Examples/GridPanel/RowExpander/`（行展开）
- Sencha 官方在线示例 `examples.sencha.com` locking-grp-summary-grp-hdrs-grid（2026-09-17 动态实验：组内子列锁定四种做法实证）
