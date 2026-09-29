---
title: 机台下拉框三重陷阱 + UNION ALL 多分支报表加筛选列（MATERIALREALTIMESTOCK 实战）
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, ComboBox, 机台下拉框, SelectSbeEquip, iBATIS, WORK_SHOP, QueryMode, 踩坑, Semi]
updated: 2026-08-29
status: active
---
# 机台下拉框三重陷阱 + UNION ALL 多分支报表加筛选列（MATERIALREALTIMESTOCK 实战）

> 场景：在 Semi 项目「部材实时库存」(MATERIALREALTIMESTOCK) 报表页新增「机台」筛选框，按 `HPP_SEMIS_PRODUCTION.EQUIP_ID` 过滤。
> 踩了一连串坑，每个坑症状都是「下拉框没值/显示不对」。本文记录**按日志定位**的完整排障过程与结论。

---

## 一、机台下拉框的「三重陷阱」

机台下拉框加载半制品车间机台，参考 `SelectSbeEquip@SbeEquip`（`SbeEquip.xml`）。三个坑缺一不可，任何一个错了都表现为「下拉框没值」或「只显示 code」。

### 陷阱 1：传参 key 大小写 → 走不同的 SQL 分支（字符串拼接 vs 参数化）

`SelectSbeEquip@SbeEquip` 对 `WORK_SHOP` 有**两个分支**，靠传参 key 的大小写区分：

```xml
<!-- 大写 WORK_SHOP → 参数化 #...#（自动加引号，能匹配字符串列） -->
<isNotNull property="where.WORK_SHOP" prepend="AND">
    <![CDATA[T1.WORK_SHOP in (#where.WORK_SHOP#)]]>
</isNotNull>
...
<!-- 小写 workshop → 字符串拼接 $...$（不加引号！） -->
<isNotNull property="where.workshop" prepend="AND">
    <![CDATA[T1.WORK_SHOP in ($where.workshop$)]]>
</isNotNull>
```

传 `"02"` 时两种 key 生成的实际 SQL（看日志实锤）：

| 传参 key | 生成的 SQL | SQL Server 行为 | 结果 |
|---|---|---|---|
| `WORK_SHOP`（大写） | `WORK_SHOP in (@param0)`，`@param0='02'` | 字符串匹配 | ✅ 查到 |
| `workshop`（小写） | `WORK_SHOP in (02)` | `02` 无引号当数字 `2`，不匹配 `'02'` | ❌ 空 |

**结论**：传 `WORK_SHOP`（大写），走参数化分支。**用日志验证，不要靠「抄 PlanCpkAnalysis」**——PlanCpkAnalysis 用的是小写 `workshop`，恰好是坏的那条。

> ✅ 正确写法：`{ "WORK_SHOP", "02" }`

### 陷阱 2：`QueryMode="Local"` 与 Page_Load 服务端绑定冲突

`cbb_minor_type`（同页能正常工作的物料细类下拉）**没有** `QueryMode` 属性（默认 Remote）。而抄 SemiPlan 的机台下拉带了 `QueryMode="Local"`。

- `QueryMode="Local"`：要求数据已在客户端内存。SemiPlan 用 DirectMethod `GetEquipByMajorType` 动态绑定，配合 Local 正常。
- 本页用 **Page_Load 服务端绑定**（`DataSource + DataBind()`），Local 模式下数据不会随首次渲染下发，下拉框为空。

**结论**：服务端绑定的 ComboBox **不要设 `QueryMode="Local"`**，用默认（Remote）。

### 陷阱 3：`DisplayField` 决定显示 code 还是 name

用户要求「只显示 code（机台号），不显示 name」。

| 配置 | 下拉框显示文本 | 选中值(ValueField) |
|---|---|---|
| `DisplayField="EquipName"` | 机台名称 | EquipCode |
| `DisplayField="EquipCode"` | 机台号(code) | EquipCode |

- 想只显示 code：`DisplayField="EquipCode"`（与 ValueField 相同）。
- 想显示名称：`DisplayField="EquipName"`，且 `SelectSbeEquip@SbeEquip` 的 SQL 已 `EQUIP_NAME as EquipName` 别名对齐。

**教训**：用户说「只显示 id 不显示 name」是**需求描述**，不是 bug 报告。先确认意图，别急着当问题修。

### 绑定代码（Page_Load 服务端绑定，最终可用版）

```csharp
private void BindEquip()
{
    Wongoing.Semi.Business.Interface.ISbeEquipManager equipManager = new SbeEquipManager();
    var sbeEquipList = equipManager.GetDataTableByStatement("SelectSbeEquip@SbeEquip", new Hashtable{
        { "where", new Dictionary<string, string>
            {
                { "WORK_SHOP", "02" }   //大写 key → 参数化 #where.WORK_SHOP#
            }
        } });
    this.storeEquip.DataSource = sbeEquipList;   //直接引用 Store 控件，同 cbb_minor_type
    this.storeEquip.DataBind();
}
```

### ComboBox 标记（只显示 code 版）

```aspx
<ext:ComboBox ID="cbb_equip" runat="server" FieldLabel="机台" LabelAlign="Right"
    Editable="true" TypeAhead="true" AnyMatch="true" MinChars="1" ForceSelection="false"
    DisplayField="EquipCode" ValueField="EquipCode" EmptyText="请选择">
    <Store>
        <ext:Store ID="storeEquip" runat="server">   <!-- 不要 AutoLoad="false"，不要 QueryMode="Local" -->
            <Model>
                <ext:Model ID="modelEquip" runat="server">
                    <Fields>
                        <ext:ModelField Name="EquipCode" />
                        <ext:ModelField Name="EquipName" />
                    </Fields>
                </ext:Model>
            </Model>
        </ext:Store>
    </Store>
    <Triggers><ext:FieldTrigger Icon="Clear" /></Triggers>
    <Listeners>
        <TriggerClick Handler="if (index == 0) this.clearValue();" />
    </Listeners>
</ext:ComboBox>
```

---

## 二、排查方法论：用日志定位，别靠猜

「下拉框没值」这种问题，**不要反复试错**，直接看运行时日志：

```text
P.Semi/Wongoing.Semi.WebSite/log/YYYYMM/YYYYMMDD.txt
```

grep 语句 id，看生成的**实际 SQL + 参数**，一步到位判断是 SQL 层还是前端层问题：

- 日志里 SQL 没出现 → 后端根本没调（绑定没触发 / catch 吞了异常）。
- SQL 出现了但参数/语法不对 → iBATIS 层问题（如上面的 `in (02)`）。
- SQL 正确且参数对 → 数据库层（确认有数据）或**前端绑定层**（QueryMode/DisplayField）。

> ⚠️ **不要用空 `catch{}` 吞异常**——会让「SQL 报错」伪装成「下拉框没值」，无从排查。

---

## 三、UNION ALL 多分支报表新增「筛选列」的模式

`GetMaterialRealTimeStockSum` / `GetMaterialRealTimeStockDetail` 是 **6 个分支 UNION ALL** 的大查询，各分支 join 不同的生产表（`HPP_SEMIS_PRODUCTION` / `HPP_RUBBER_PRODUCTION`）。要新增「按 EQUIP_ID 筛选」时，难点是：动态标签只能写在外层 `<dynamic>` 里，但各分支的表别名/列不同。

### 模式：给每个分支补 SELECT 列 + 外层 WHERE 过滤

**步骤 1**：给 UNION 的**每个分支** SELECT 末尾补上 `EQUIP_ID` 列，保证 UNION 列数对齐：

| 分支类型 | 加的列 |
|---|---|
| 部材产出库(C%) / 线边部材(X%)（join `HPP_SEMIS_PRODUCTION sp`） | `sp.EQUIP_ID` |
| 胶料/骨架/FN（join `HPP_RUBBER_PRODUCTION`，无 EQUIP_ID） | `null as EQUIP_ID` |

```sql
-- 部材分支
sp.PLAN_DETAIL_ID, ..., sp.EQUIP_ID as EQUIP_ID
-- 胶料/骨架分支
null as PLAN_DETAIL_ID, ..., null as EQUIP_ID
```

**步骤 2**：外层 `<dynamic>` 加 `isNotEmpty` 守卫（`pageParams` 是 `Dictionary<string,string>`，空值是 `""` 不是 `null`，必须用 `isNotEmpty` 不是 `isNotNull`）：

```xml
<dynamic prepend="WHERE">
    ...既有条件...
    <isNotEmpty property="where.EquipId" prepend="AND">
        <![CDATA[t1.EQUIP_ID = #where.EquipId#]]>
    </isNotEmpty>
</dynamic>
```

**效果**：选中机台时，只有 `sp.EQUIP_ID = 选中值` 的部材行匹配；胶料/骨架分支 `EQUIP_ID` 为 NULL，`= 'xxx'` 不成立被自动排除——天然实现「按机台只看该机台部材库存」。

### 汇总表加展示列：同时改 SELECT + GROUP BY

汇总表按物料 GROUP BY 聚合。要显示机台号列，必须**同时**在 SELECT 输出列和 GROUP BY 里加 `t1.EQUIP_ID`，否则 SQL 报错：

```sql
-- SELECT 加输出列
select ..., t3.TYRE_MATERIAL_CODE [制造编码], t1.EQUIP_ID [机台号], ...
-- GROUP BY 加分组键
GROUP BY [物料类别],[物料名称],t3.TYRE_MATERIAL_CODE, t1.EQUIP_ID, ...
```

> 加了 GROUP BY 的 EQUIP_ID 后，同一物料在不同机台会分成多行——这是预期行为（按机台看库存）。

### iBATIS 动态守卫选型备忘

| 守卫 | 触发条件 | 适用 |
|---|---|---|
| `<isNotEmpty>` | 值非 null **且非空串** | `Dictionary<string,string>` 参数（空值是 `""`）✅ |
| `<isNotNull>` | 值非 null（空串也算） | 参数可能是真正 null 时 |

本页 pageParams 是 `Dictionary<string,string>`，未选时传 `""`，故一律用 `isNotEmpty`。

---

## 四、相关文件

- 页面：`P.Semi/Wongoing.Semi.WebSite/Plugins/Semi/Report/MaterialRealTimeStock.aspx(.cs)`
- SQL：`P.Semi/Wongoing.Semi.Mapper/BusinessMapper/HppSemisProduction.xml`（`GetMaterialRealTimeStockSum/Detail`）
- 机台下拉数据源：`SbeEquip.xml` 的 `SelectSbeEquip@SbeEquip`
- 参考页：`Plugins/Semi/ProductPlan/SemiPlan.aspx`（机台只显示 code 的范例）
- 运行时日志：`P.Semi/Wongoing.Semi.WebSite/log/YYYYMM/YYYYMMDD.txt`

## 五、关联

- ComboBox 属性速查：`extnet-combobox-properties.md`
- 查询条件控件升级（TextField→下拉框）：`extnet-query-control-upgrade.md`
- iBATIS 语句命名与 GetPageDataByReader 踩坑：`ibatis-statement-naming-and-getpagedatabyreader-pitfall.md`
- E-SafeNet 加密（.aspx.cs 不可直接读）：`mes-website-esafenet-encryption.md`
- ComboBox 多选改造（MultiSelect + in 片段 + $..$）：`extnet-combobox-multiselect.md`
