---
title: GridPanel 行底色标黄标红（有效期/预警日期判定）+ 后端日期格式化方案
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, GridPanel, GetRowClass, 行高亮, 标黄, 标红, 有效期, 预警日期, DateColumn, 日期格式化, 踩坑]
updated: 2026-08-29
status: active
---
# GridPanel 行底色标黄标红（有效期/预警日期判定）+ 后端日期格式化方案

> EquipManage 检定机构页行标色：GetRowClass（今天取 0 点、先判到期再判预警）配 row-expired/row-alarm 两个 CSS 类（须 !important）。日期列绕开 DateColumn 解析坑 = 后端 FormatDate 成 yyyy-MM-dd 字符串再改回原列名。扩展：目录树整条链路标色（MergeColor 双路合并——自身递归含子目录状态 + 子节点颜色向上取最严重）与 EnableTextSelection 可复制。

## 一、适用场景

EquipManage 项目检定机构管理页面：根据检定机构的有效期/预警日期，对行标色提示。

## 二、标色规则

| 条件 | 颜色 | CSS 类 |
|---|---|---|
| 有效期 < 今天（到期） | 红 | `row-expired` |
| 预警日期 ≤ 今天 < 有效期（预警期） | 黄 | `row-alarm` |

## 三、CSS（aspx head 内联）

```css
<style type="text/css">
    .row-expired .x-grid-cell { background-color: #ffcccc !important; }  /*到期红*/
    .row-alarm .x-grid-cell { background-color: #fff3cd !important; }    /*预警黄*/
</style>
```

> `!important` 必须加，否则被 Ext 默认样式覆盖。

## 四、GetRowClass 函数（前端 JS）

```javascript
var setRowClass = function (record, rowIndex, rowParams, store) {
    try {
        var today = new Date(new Date().toDateString()); //今天0点（去掉时分秒）
        var valid = record.data.VALID_DATE ? new Date(record.data.VALID_DATE) : null;
        var alarm = record.data.ALARM_DATE ? new Date(record.data.ALARM_DATE) : null;
        if (valid && valid < today) return 'row-expired';      //到期红
        if (alarm && alarm <= today && (!valid || valid >= today)) return 'row-alarm'; //预警黄
    } catch (e) { }
    return '';
};
```

**关键点**：
- `new Date().toDateString()` 取今天 0 点，避免时分秒干扰日期比较
- **先判到期再判预警**（有效期已过优先级最高）
- 函数声明在 aspx 内联 `<script>`，不能放外部 JS（Ext.NET 构建阶段按函数名查找，外部 JS 可能未就绪）

## 五、GridPanel 绑定

```xml
<ext:GridPanel ID="gridPanelMain" runat="server" Region="Center">
    ...
    <View>
        <ext:GridView ID="gvRows" runat="server">
            <GetRowClass Fn="setRowClass" />
        </ext:GridView>
    </View>
    ...
</ext:GridPanel>
```

## 六、日期列显示：后端格式化字符串（绕开 DateColumn 坑）

### 踩坑：DateColumn 显示异常
Ext.NET `DateColumn` 依赖前端 `ModelField` 把后端 datetime 字符串解析成 JS Date 对象。但手动 `store.Data = DataTable` 绑定或 PageProxy 返回的 datetime 字符串格式不固定（`2026-08-04T16:08:26` / `7/14/2026 8:30:00 AM` / `2026-08-04 16:08:26`），`DateColumn.Format` 解析失败 → 显示空白或异常。

详见 `extnet-grid-datecolumn-pitfall.md`。

### 正解：后端格式化成字符串 + 前端普通 Column

**后台**（GridPanelBindData 返回前格式化）：
```csharp
//日期列格式化为字符串，规避 DateColumn 前端解析不一致
data.Columns.Add("VALID_DATE_STR", typeof(string));
data.Columns.Add("ALARM_DATE_STR", typeof(string));
data.Columns.Add("RECORD_TIME_STR", typeof(string));
foreach (DataRow row in data.Rows)
{
    row["VALID_DATE_STR"] = FormatDate(row["VALID_DATE"], "yyyy-MM-dd");
    row["ALARM_DATE_STR"] = FormatDate(row["ALARM_DATE"], "yyyy-MM-dd");
    row["RECORD_TIME_STR"] = FormatDate(row["RECORD_TIME"], "yyyy-MM-dd HH:mm:ss");
}
data.Columns.Remove("VALID_DATE");
data.Columns.Remove("ALARM_DATE");
data.Columns.Remove("RECORD_TIME");
data.Columns["VALID_DATE_STR"].ColumnName = "VALID_DATE";   //改回原名，与前端 ModelField 对齐
data.Columns["ALARM_DATE_STR"].ColumnName = "ALARM_DATE";
data.Columns["RECORD_TIME_STR"].ColumnName = "RECORD_TIME";

//日期格式化辅助
private static string FormatDate(object val, string fmt)
{
    if (val == null || val == DBNull.Value || string.IsNullOrEmpty(val.ToString())) return "";
    DateTime dt;
    return DateTime.TryParse(val.ToString(), out dt) ? dt.ToString(fmt) : val.ToString();
}
```

**前台**：用普通 `Column`，不用 `DateColumn`：
```xml
<ext:Column runat="server" DataIndex="VALID_DATE" Text="有效期" Width="130" />
<ext:Column runat="server" DataIndex="ALARM_DATE" Text="预警日期" Width="130" />
<ext:Column runat="server" DataIndex="RECORD_TIME" Text="记录时间" Width="160" />
```

### GetRowClass 注意：格式化后的字符串日期仍能被 new Date() 正确解析
`yyyy-MM-dd` 格式是 JS `new Date("2026-08-04")` 能解析的标准格式，所以 GetRowClass 里 `new Date(record.data.VALID_DATE)` 不受影响。

## 七、参考页面

- `Plugins/EquipManage/Measure/BusCheckDeptManage.aspx(.cs)` — 检定机构管理（标色+日期格式化）

## 八、关联文档

- `extnet-row-highlight-expiry.md` — 行底色条件高亮（GetRowClass 基础）
- `extnet-grid-datecolumn-pitfall.md` — DateColumn 显示空白踩坑详解

---

## 九、目录树整条链路标色（子级文件状态向上传递到所有父级目录）

场景：BusManageFile 文件管理页，左侧目录树（TreePanel）按目录下文件的有效期/预警日期标色。要求**只要子级链路上有到期/预警文件，整条路径上所有父级目录都标色**（到期优先于预警）。

### 后台三件套（BusManageFile.aspx.cs）

**1. 节点颜色 = 自身文件状态 与 所有子节点状态 合并**（InitLevelTree/CreateNode 里，子节点构建完后再算父节点颜色）：
```csharp
string nodeColor = MergeColor(GetCataColor(item.ObjId.GetValueOrDefault(), lstAll), GetChildrenMaxColor(temp));
if (!string.IsNullOrEmpty(nodeColor))
    temp.CustomAttributes.Add(new ConfigItem("color", nodeColor, ParameterMode.Value));
```

**2. 递归查目录及其所有子目录下文件的状态**：
```csharp
private string GetCataColor(int cataId, List<BusFileCatalog> lstAll)
{
    var cataIds = new HashSet<int> { cataId };
    CollectChildCataIds(cataId, lstAll, cataIds);   //递归收集子目录
    foreach (var cid in cataIds)
    {
        var files = FileManager.GetEntityList(new BusManageFile { CataId = cid });
        // 遍历文件：ValidDate < 今天 → hasExpired；AlarmDate ≤ 今天 < ValidDate → hasAlarm
    }
    if (hasExpired) return "red";
    if (hasAlarm) return "yellow";
    return "";
}
```

**3. 颜色合并（red > yellow > 空）**：`MergeColor(a, b)` 取最严重；`GetChildrenMaxColor(node)` 遍历 Node.Children 的 CustomAttributes 里名为 color 的项取最大。

> ⚠️ 注意：如果只给"直接挂文件的目录"标色而不向上合并，父级分类目录不变色——必须用 MergeColor(GetCataColor(自身含子目录递归), GetChildrenMaxColor(子节点颜色)) 双路合并。

### 前端：TreeColumn + Renderer 着色

TreePanel 必须显式声明 ColumnModel（默认渲染无 Renderer 可挂）：
```xml
<ext:TreePanel ID="treePanel1" ...>
    <ColumnModel>
        <Columns>
            <ext:TreeColumn runat="server" Text="目录" DataIndex="text" Flex="1">
                <Renderer Fn="applyCataColor" />
            </ext:TreeColumn>
        </Columns>
    </ColumnModel>
```
```javascript
var applyCataColor = function (value, metaData, record) {
    var color = record.get('color');
    if (color === 'red') metaData.style = 'color:#cc0000;font-weight:bold;';
    else if (color === 'yellow') metaData.style = 'color:#cc9900;font-weight:bold;';
    return value;
};
```

### 刷新时机
上传文件（UploadFileClick 成功后）和删除文件（DeleteFile）都要调 `InitLevelTree()` 重建树，否则颜色不更新。

参考：`Plugins/EquipManage/Business/FileManager/BusManageFile.aspx(.cs)`、知识库 `extnet-tree-guide.md` 第十章（TreeColumn 条件着色基础）。

## 十、表格单元格内容可复制（EnableTextSelection）

Ext.NET GridPanel 默认禁止文字选取，查出来的内容无法复制。给 GridView 加 `EnableTextSelection="true"` 即可：

```xml
<View>
    <ext:GridView ID="gvMain" runat="server" EnableTextSelection="true">
        <GetRowClass Fn="setRowClass" />
    </ext:GridView>
</View>
```

主表和明细表都要加。注意：与 GetRowClass 行标色可共存，互不影响。