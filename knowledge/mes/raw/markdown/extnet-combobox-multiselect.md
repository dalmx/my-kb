---
title: Ext.NET ComboBox 多选改造模式（机台多选 IN 查询）
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, ComboBox, MultiSelect, 多选下拉框, 机台多选, 机台下拉框, SelectedItems, iBATIS, 字面替换, IN查询, SemiPlanExecute, 计划执行, 踩坑]
updated: 2026-08-21
status: active
---
# Ext.NET ComboBox 多选改造模式（机台多选 IN 查询）

> 把查询条件里的单选 ComboBox（典型：机台）升级为多选，后端 SQL 从 `=` 精确匹配改为 `IN` 多值。
> 2026-08-21 在 SemiPlanExecute（计划执行）实战落地，沿用 ReturnProductOutput 惯例。
> **共 4 处联动改动，缺一处即报错或漏条件**；最大的坑是同一 Mapper 语句被多个调用方共用时必须全部同步（见第五节）。

---

## 一、改造清单（4 处联动）

| # | 文件 | 改动 | 漏改后果 |
|---|------|------|---------|
| 1 | `.aspx` | ComboBox 加 `MultiSelect="true"`；联动清空改 `clearValue()` | 多选不生效 / SelectedItems 混入空串 |
| 2 | `.aspx.cs` | 从 `SelectedItems` 拼成 `" in ('a','b') "` SQL 片段 | 传 `System.String[]` 或裸值，SQL 报错 |
| 3 | `.Mapper.xml` | 条件由 `#PARAM#` 改 `$PARAM$` 字面替换 | `IN` 语法不成立 |
| 4 | 同语句的**其他调用方** | 单选侧同步包成 `" in ('xxx') "` | 🔴 SQL 语法错误（最易漏） |

## 二、前端 aspx：MultiSelect + clearValue

ComboBox 标记只需加一个属性，其余（ValueField/DisplayField/Store/Triggers）与单选无异：

```aspx
<ext:ComboBox ID="cbbEquip" runat="server" FieldLabel="机台" LabelAlign="Right" ValueField="EquipCode"
    DisplayField="EquipName" QueryMode="Local" MatchFieldWidth="true" MultiSelect="true">
```

**坑：多选模式下清空必须用 `clearValue()`，不能用 `setValue("")`**——`setValue("")` 会留下一个空值项，`SelectedItems` 混入空字符串，后端拼出 `in ('')`：

```javascript
var EquipMajorTypeChange = function (item, newValue, oldValue) {
    App.cbbEquip.clearValue();   // ❌ 不要用 setValue("")
    App.direct.GetEquipByMajorType(newValue, { ... });
}
```

## 三、后台 cs：SelectedItems 拼 SQL 片段（DirectMethod 中同样可用）

字典里先置空，有选中再拼片段（沿用 ReturnProductOutput 写法）：

```csharp
var param = new Dictionary<string, object> {
    { "EQUIP_CODE",""},   // 先置空，走 isNotEmpty 跳过
    ...
};
// 机台多选：拼成 " in ('a','b') " 整段，Mapper 端 $EQUIP_CODE$ 字面替换
if (cbbEquip.SelectedItems.Count > 0)
{
    param["EQUIP_CODE"] = " in (" + string.Join(",", cbbEquip.SelectedItems.Select(item => "'" + item.Value.ToString() + "'").ToArray()) + ") ";
}
```

`SelectedItems` 在 **DirectMethod**（如 GetStatisticsData）里能拿到客户端最新多选状态——与 Store.ReadData 同为 AJAX 状态恢复机制，无需额外处理。

## 四、Mapper：`#PARAM#` → `$PARAM$` 字面替换

```xml
<isNotEmpty prepend="and" property="EQUIP_CODE">
    t1.EQUIP_ID $EQUIP_CODE$
</isNotEmpty>
```

`#...#` 是参数化占位（整个片段会被当普通字符串），`$...$` 才是把 `" in ('a','b') "` 原样嵌入 SQL。值来源于服务端绑定的机台字典（EquipCode），无用户自由输入，注入风险可控。

## 五、🔴 关键坑：同一 Mapper 语句被多个调用方共用时必须全部同步

`SelectExecutePlan@HppPlan` 同时被 `GetStatisticsData`（多选 cbbEquip）和 `GetTargetPlan`（单选 Adjust_Equip）调用。Mapper 改成 `$EQUIP_CODE$` 字面替换后，**单选调用方若仍传裸值**，拼出 `t1.EQUIP_ID 'EQ01'` 直接 SQL 语法错误。单选侧要同步包一层：

```csharp
{ "EQUIP_CODE", Adjust_Equip.SelectedItems.Count==0 ? "" : " in ('"+Adjust_Equip.Value.ToString()+"') "},
```

**操作规程**：改 Mapper 参数语义前，先全解决方案搜语句名，列出所有调用方逐一核对：

```bash
powershell -NoProfile -Command "Get-ChildItem '<项目路径>\P.Semi' -Recurse -Include '*.cs','*.aspx' | Select-String -Pattern 'SelectExecutePlan'"
```

## 六、参考实现位置与关联文档

| 场景 | 页面 |
|------|------|
| 机台多选（报表，Store.ReadData） | `Plugins/Semi/Report/ReturnProductOutput.aspx` |
| 机台多选（DirectMethod 查询 + 联动细类） | `Plugins/Semi/ProductPlan/SemiPlanExecute.aspx` |

关联文档：
- `semi-equip-combobox-filter-pitfalls.md` —— 机台下拉框（单选）加载/绑定/显示的三重陷阱
- `extnet-combobox-properties.md` —— ComboBox 属性速查
- `extnet-query-control-upgrade.md` —— 查询条件控件升级模式（TextField → 下拉框/搜索弹窗）
