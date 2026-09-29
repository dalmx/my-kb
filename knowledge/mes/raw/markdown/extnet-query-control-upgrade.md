---
category: 技术-.NET
factory: 通用
module: Ext.NET
status: active
tags:
- Ext.NET
- 查询条件
- DateField
- 日期范围
- daterange
- 开始结束日期
- 存储过程
- procedure
- Mapper多调用方兼容
- 部署顺序
- proc转写diff铁律
- expert-sql审查
title: 查询条件控件升级模式（TextField → 搜索弹窗 / TextField → 下拉框）
updated: '2026-09-15'
---

# 查询条件控件升级模式（TextField → 搜索弹窗 / TextField → 下拉框）

> 报表/查询页的查询条件区，常把"自由输入的 TextField"升级为更友好的控件：
> - **物料/机台等主数据** → **搜索弹窗控件**（点放大镜弹窗选择，避免手工输错）
> - **枚举/有限集合（细类、班组等）** → **下拉框 ComboBox**（可选可搜）
>
> 本篇给出两类升级的标准写法、落地 Checklist，以及 MaterialRealTimeStock（部材实时库存）的真实改造案例。

---

## 一、TextField → 搜索弹窗控件（点放大镜弹窗选择）

### 适用场景
物料、机台、客户等**主数据**字段，数据量大、需带条件检索，输入易错。全站统一复用 **McUI SearchBox** 通用弹窗。

### 命名约定（全站统一，务必遵守）
- 弹窗 Window id：`McUI_SearchBox_<SearchBox名>_Window`
- 回填回调函数：`McUI_SearchBox_<SearchBox名>_Request(record)`（弹窗 iframe 内 `parent.McUI_SearchBox_..._Request(record)` 调用）
- iframe URL：`/McUI/SearchBox/<SearchBox名>.aspx?<参数>`（物理上由通用 `McUI/SearchBox.aspx` 处理，按 URL 末段加载 `Plugins/<插件>/McUI/@McUI/<SearchBox名>.xml + .Mapper.xml + .js`）

### 1. aspx — 触发字段（双 Trigger：Clear + Search）
```aspx
<ext:TextField ID="txt_material_name" runat="server" FieldLabel="物料名称" LabelAlign="Right" Editable="false">
    <Triggers>
        <ext:FieldTrigger Icon="Clear" />      <!-- index 0：清除 -->
        <ext:FieldTrigger Icon="Search" />     <!-- index 1：弹窗 -->
    </Triggers>
    <Listeners>
        <TriggerClick Handler="if (index == 0) { this.setValue(''); } else if (index == 1) { SelectMaterial(); }" />
    </Listeners>
</ext:TextField>
```
- `Editable="false"`：只允许弹窗选，不允许手输（视需求，查询条件可放开为 true）
- 若同时需要携带物料**编码**（code）和显示**名称**（name），配一个 `<ext:Hidden>` 存 code，本案例查询只用到 name 故省略

### 2. aspx — JS（建窗 + 弹出 + 回填）
```javascript
var SelectMaterial = function () {
    App.McUI_SearchBox_SearchBoxSemiSbmMaterial_Window.show();
}

// 复用全站统一 McUI_SearchBox_SearchBoxSemiSbmMaterial
Ext.create("Ext.window.Window", {
    id: "McUI_SearchBox_SearchBoxSemiSbmMaterial_Window",
    height: 460, hidden: true, width: 600,
    html: "<iframe src='/McUI/SearchBox/SearchBoxSemiSbmMaterial.aspx?closable=1' width=100% style='height:100%' scrolling=no frameborder=0></iframe>",
    bodyStyle: "background-color: #fff;",
    closable: true, title: "请选择物料", modal: true
})

// 弹窗选中行 → 回填到查询字段
var McUI_SearchBox_SearchBoxSemiSbmMaterial_Request = function (record) {
    App.txt_material_name.setValue(record.data.MATERIAL_NAME);
    App.McUI_SearchBox_SearchBoxSemiSbmMaterial_Window.close();
}
```
- 常用 SearchBox 名：`SearchBoxSemiSbmMaterial`（半制品物料，源表 SBM_MATERIAL）、`SearchBoxSbeEquip`（机台）、`SearchBoxBasPackingInfo`（ERP 包装/编号）
- 可选 URL 参数：`majorlst=01`（按大类过滤）、`minorlst=<code>`（按细类过滤）、`equipcode=<code>`（按机台过滤）、`closable=1`（选中后自动关窗）
- 带参数动态切 iframe 用 `App.<winId>.setHtml("<iframe ...>")`（参考 SemiPlan.aspx）

### 3. cs — 无需改动（回填的是 TextField.Text）
SQL 参数仍取 `this.txt_material_name.Text`，`where.MaterialName LIKE '%' + #值# + '%'` 兼容。

---

## 二、TextField → 下拉框 ComboBox（模糊搜索可选）

### 适用场景
枚举或有限集合：物料细类、班组、锁定标志等。参考 `extnet-combobox-fuzzy-search.md`  的模糊搜索写法。

### aspx — 本地模糊搜索下拉
```aspx
<ext:ComboBox ID="cbb_minor_type" runat="server" FieldLabel="物料细类" LabelAlign="Right"
    Editable="true" TypeAhead="true" AnyMatch="true" MinChars="1" ForceSelection="false"
    DisplayField="MINOR_TYPE_NAME" ValueField="MINOR_TYPE_NAME" EmptyText="请选择">
    <Store>
        <ext:Store ID="storeMinorType" runat="server" AutoLoad="false">
            <Model>
                <ext:Model ID="modelMinorType" runat="server">
                    <Fields><ext:ModelField Name="MINOR_TYPE_NAME" /></Fields>
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
- 关键属性：`TypeAhead`（输入联想）、`AnyMatch`（任意位置匹配）、`ForceSelection="false"`（允许不选 = 全部）、`MinChars`（输入几个字才触发）
- `DisplayField/ValueField` 都用**名称**还是**编码**，取决于后端 SQL 的参数语义：
  - 若 SQL 是 `LIKE '%名称%'`（对中文类别名）→ ValueField 用名称
  - 若 SQL 是 `= #编码#`（精确匹配编码）→ ValueField 用编码，DisplayField 用名称

### cs — 服务端绑定 Store（首次加载）
```csharp
protected void Page_Load(object sender, EventArgs e)
{
    if (IsPostBack || X.IsAjaxRequest) return;
    BindMinorType();
}

private void BindMinorType()
{
    try
    {
        var param = new Dictionary<string, object>();
        var data = manager.GetDataTableByStatement("GetMaterialRealTimeStockMinorType", param);
        this.storeMinorType.DataSource = data;
        this.storeMinorType.DataBind();
    }
    catch { /* 忽略，下拉为空即可 */ }
}
```
- 下拉数据**服务端绑定**（非 DirectFn），放 `!IsAjaxRequest` 首次加载即可，无需每次回发

### cs — 取值改为 `.Value`
原 `this.txt_minor_type.Text` → `this.cbb_minor_type.Value == null ? "" : this.cbb_minor_type.Value.ToString()`
> ⚠️ **踩坑**：ComboBox 空选时 `.Value` 可能为 null，务必判空；**导出 / 汇总 / 明细三处查询入口都要同步改**，否则导出时报空引用或漏带条件。

---

## 三、改造 Checklist（通用）

- [ ] aspx：TextField → 触发字段 / ComboBox，确认 ID、LabelAlign、列宽（ColumnWidth）不变
- [ ] aspx：搜索弹窗加建窗 + `SelectXxx()` + `McUI_SearchBox_..._Request(record)` 三段 JS
- [ ] aspx：下拉加 Store + Model + Clear Trigger
- [ ] cs：Page_Load 首次加载绑定下拉 Store（`!IsAjaxRequest`）
- [ ] cs：**导出 / 汇总 / 明细** 三处（或更多）查询参数全部改控件引用，Value 判空
- [ ] SQL：确认参数名（`where.Xxx`）与 dynamic `<isNotEmpty>` 不变；下拉数据源新增独立 mapper 语句
- [ ] 回归验证：弹窗能选/回填/查询；下拉有数据/模糊/清除；导出条件生效

---

## 四、落地案例：MaterialRealTimeStock（部材实时库存）

**页面**：`Plugins/Semi/Report/MaterialRealTimeStock.aspx(+.cs)`
**数据源**：`Wongoing.Semi.Mapper/BusinessMapper/HppSemisProduction.xml`

### 改动对照
| 字段 | 改造前 | 改造后 |
|------|--------|--------|
| 物料名称 | TextField `txt_material_name` | 搜索弹窗（McUI_SearchBox_SearchBoxSemiSbmMaterial），回填 MATERIAL_NAME |
| 物料细类 | TextField `txt_minor_type` | ComboBox `cbb_minor_type`，绑定在库涉及的 distinct 细类 |

### 新增 mapper 语句 `GetMaterialRealTimeStockMinorType`
取**当前在库物料涉及的 distinct 细类**，库型覆盖与主报表一致（HPP_STORAGE 的 C%/X% 部材 + HPP_RUBBER_STORAGE 的 FN%/X%/Z% 胶料骨架），过滤阈值（LEFT_QTY > 5、QUALITY_SITUATION <> '错打' 等）与 `GetMaterialRealTimeStockSum/Detail` 完全对齐，保证下拉只显示有库存的细类。
```sql
SELECT DISTINCT smm.MINOR_TYPE_NAME
FROM (
    -- HPP_STORAGE + HPP_SEMIS_PRODUCTION：C%（产出库）/ X%（线边）
    SELECT sm.MINOR_TYPE_ID FROM HPP_STORAGE T ... WHERE T2.AREA_CODE LIKE 'C%' AND sp.LEFT_QTY > 5 AND sp.QUALITY_SITUATION <> '错打'
    UNION ALL ... LIKE 'X-%' ...
    -- HPP_RUBBER_STORAGE + HPP_RUBBER_PRODUCTION：FN% / X% / Z%
    UNION ALL SELECT sm.MINOR_TYPE_ID FROM HPP_RUBBER_STORAGE T ... WHERE T.StockID LIKE 'FN%' AND TRY_CAST(sp.LEFT_QTY...) > 5
    UNION ALL ... LIKE 'X-%' ...  UNION ALL ... LIKE 'Z-%' AND LEN(T.Barcode)=8 ...
) t
LEFT JOIN SBM_MATERIAL_MINOR_TYPE smm WITH(NOLOCK) ON smm.MINOR_TYPE_CODE = t.MINOR_TYPE_ID
WHERE smm.MINOR_TYPE_NAME IS NOT NULL
ORDER BY smm.MINOR_TYPE_NAME
```

### 关键决策点
- 物料弹窗**不按大类过滤**（本报表涵盖部材+胶料+骨架多类，与单一 majorlst=01 的页面不同）。如需限定范围，iframe URL 加 `?majorlst=xx`。
- 细类下拉 `ValueField=DisplayField=MINOR_TYPE_NAME`，因主 SQL 用 `where.MinorTypeName` 对 `[物料类别]`（中文细类名）做 LIKE，保持兼容。
- **未改动** `GetMaterialRealTimeStockSum/Detail` 及其参数名，不影响汇总/明细/导出现有逻辑。

---

## 五、参考实现位置
| 模式 | 参考页面 |
|------|---------|
| 物料搜索弹窗（最干净范例） | `Plugins/Semi/Material/MoldingAlternativeMaterial.aspx` |
| 物料搜索弹窗（报表查询条件） | `Plugins/Semi/Produce/SemiProduceAnalyse.aspx` |
| 物料弹窗 + 动态字段回填 | `Plugins/Semi/BasicInfo/CurdMaterial.aspx`（SelectERPCode） |
| 动态切 iframe 参数 | `Plugins/Semi/ProductPlan/SemiPlan.aspx` |
| 细类下拉（库存涉及的细类） | `Plugins/Semi/Material/SemisRawMaterial.aspx`（GetSemisRawMaterialMinorType@HPP_RUBBER_STORAGE） |
| 细类下拉（按大类/实体管理器） | `Plugins/Semi/Material/CutFitPosition.aspx`（SbmMaterialMinorTypeManager.GetEntityList） |

## 六、相关条目
- `extnet-combobox-fuzzy-search.md` （下拉模糊搜索基础）
- `semi-material-storage-flow.md`（部材库存业务流程）
- `semi-data-model.md`（库存查询相关 statement id 索引）
- `extnet-event-mechanisms.md`（Listeners / DirectMethod / TriggerClick 机制）

---

## 七、单日期 DateField → 开始/结束日期范围（四件套改造）

> 查询条件从"单日期"升级为"日期范围"的标准套路，共动 **aspx 控件 / aspx JS / cs 参数 / Mapper 条件** 四处。
> 落地案例：`Plugins/Semi/ProductPlan/SemiPlanExecute.aspx`（计划日期 → 开始/结束日期，2026-09）。

### 7.1 aspx 控件——两个 DateField + daterange 联动

```aspx
<ext:DateField ID="txt_begin_date" runat="server" FieldLabel="<%$Resources:Semi,开始日期 %>" AllowBlank="false" LabelAlign="Right" Type="Date" Format="yyyy-MM-dd" Vtype="daterange">
    <CustomConfig>
        <ext:ConfigItem Name="endDateField" Value="txt_end_date" Mode="Value" />
    </CustomConfig>
</ext:DateField>
<ext:DateField ID="txt_end_date" runat="server" FieldLabel="<%$Resources:Semi,结束日期 %>" AllowBlank="false" LabelAlign="Right" Type="Date" Format="yyyy-MM-dd" Vtype="daterange">
    <CustomConfig>
        <ext:ConfigItem Name="startDateField" Value="txt_begin_date" Mode="Value" />
    </CustomConfig>
</ext:DateField>
```

- `Vtype="daterange"` + CustomConfig 互指对方 ID（`Mode="Value"` 表示值是字面量 ID 串），实现开始 ≤ 结束的 minValue/maxValue 联动（详见 `extnet-datefield-range-and-month.md`）
- 标签资源 `Semi,开始日期` / `Semi,结束日期` 在 Semi.resx 已存在，直接用
- **布局手法**：两个字段上下摞进原字段所在的 Container（列数列宽都不动，行数不变）；若该 Container 因此多出一行，把原有别的字段（如班次）挪去"只有一项的短列"补空位——不要新增列，避免分辨率下挤压重叠

### 7.2 aspx JS——默认值补齐

页面加载初始化函数（如 `viewportAfterRender`）里给**两个**日期框都设当天；老代码常有注释掉的 `txt_end_date` 行，说明字段当初就预留过，放开即可。

```javascript
var viewportAfterRender = function () {
    var curDate = new Date();
    App.txt_begin_date.setValue(new Date(curDate.setDate(curDate.getDate())));
    App.txt_end_date.setValue(new Date(curDate.setDate(curDate.getDate())));
}
```

### 7.3 cs——参数名换成 BEGIN/END 两个

```csharp
var param = new Dictionary<string, object> {
    { "PLAN_DATE_BEGIN", txt_begin_date.RawText},
    { "PLAN_DATE_END",   txt_end_date.RawText},
};
```

取值用 `RawText`（得到 yyyy-MM-dd 字符串），与原单日期写法一致。

### 7.4 Mapper——isNotEmpty + CDATA 范围条件，**保留原等值条件**

```xml
<isNotEmpty prepend="and" property="PLAN_DATE">
    t1.PLAN_DATE = #PLAN_DATE#
</isNotEmpty>
<isNotEmpty prepend="and" property="PLAN_DATE_BEGIN"><![CDATA[ t1.PLAN_DATE >= #PLAN_DATE_BEGIN# ]]></isNotEmpty>
<isNotEmpty prepend="and" property="PLAN_DATE_END"><![CDATA[ t1.PLAN_DATE <= #PLAN_DATE_END# ]]></isNotEmpty>
```

- `>=` / `<=` 用 CDATA 包裹（项目惯例，同 HppSemisProduction.xml 的 BEGIN_DATE/END_DATE 写法）
- **多调用方兼容**：改 Mapper 前先搜该 statement 全部调用方（同 ComboBox 多选改造教训）。本例 `SelectExecutePlan@HppPlan` 还被产出调整弹窗 `GetTargetPlan` 以单日期 `PLAN_DATE` 调用——原等值条件保留给它，新条件用 `isNotEmpty`，调用方不传 key 时安全跳过（⚠️ `isEqual` 缺 key 会崩，别用）
- 结束边界 `<=` 按整天匹配：前提是日期列存零点值（现有单日期等值查询按 yyyy-MM-dd 匹配正常即证明），否则需 `< dateadd(day,1,#END#)`

### 7.5 顺手项——固定排序

范围查询结果集变大后建议给 statement 加固定排序，主字段 + 次级字段保证行序稳定：

```sql
ORDER BY t1.PLAN_DATE, t1.EQUIP_ID, t2.SEQ_INDEX
```

### 7.6 参考实现位置

| 内容 | 位置 |
|------|------|
| 本次案例页面 | `Plugins/Semi/ProductPlan/SemiPlanExecute.aspx(+.cs)` |
| 范围条件 Mapper | `Wongoing.Semi.Mapper/BusinessMapper/HppPlan.xml` → `SelectExecutePlan@HppPlan` |
| 双 Container 并排摆法（另一种布局） | `Plugins/Semi/Produce/SemiShiftStatics.aspx`（注意其结束日期标签误写为开始日期，抄时修正） |

---


## 八、Curing 落地案例：CuringPlanExecute（2026-09-03）

> 第七章模式在 Curing 子项目的复刻：`Plugins/Curing/ProductPlan/CuringPlanExecute.aspx(+.cs)` 计划日期 → 开始/结束日期，四件套与 Semi 案例完全同构，另有三处 Curing 特有细节。

### 8.1 改动对照

| 改动点 | 位置 | 内容 |
|--------|------|------|
| aspx 控件 | `container3`（ColumnWidth .25） | 单日期 → 两个 DateField 上下摞（开始日期/结束日期，daterange 互指），列数列宽不动 |
| aspx JS | `viewportAfterRender` | 原文件本就有一行注释掉的 `App.txt_end_date.setValue(...)`（字段当初预留），放开即可 |
| cs 参数 | `GetStatisticsData` | `PLAN_DATE` → `PLAN_DATE_BEGIN` / `PLAN_DATE_END`（均 `RawText`） |
| Mapper | `SelectExecutePlan@CppCuringPlan`（Wongoing.Curing.Mapper/BusinessMapper/CppCuringPlan.xml） | 保留原 `PLAN_DATE` 等值条件，新增两条 isNotEmpty + CDATA 范围条件；排序 `ORDER BY EQUIP_CODE,EQUIP_POSITION` → `ORDER BY PLAN_DATE,EQUIP_CODE,EQUIP_POSITION` |

### 8.2 Curing 特有细节（与 Semi 案例的差异点）

- **标签用明文中文**：该页面查询区 FieldLabel 全是明文（`FieldLabel="开始日期"`），不走 `<%$Resources%>` 资源表达式。
- **日期条件包在 `<isEmpty property="TYRE_CODE">` 分支内**：按二维码搜索时日期/班次/机台条件整体跳过（既有语义）。BEGIN/END 两条范围条件必须加在同一个 isEmpty 分支内、紧跟原等值条件之后，不要提到 dynamic 顶层，否则破坏"二维码直达"语义。
- **多调用方**：`SelectExecutePlan@CppCuringPlan` 被 `GetStatisticsData`（主查询，改范围）和 `GetTargetPlan`（产出调整弹窗，仍传单日期 `PLAN_DATE` 走原等值条件）共用；弹窗内 `target_plan_date` 保持单日期不动（调整按天操作）。
- 该 statement 的 SQL 主体是 `##curingplanexe` 全局临时表两段式，范围条件加在 CTE 的 WHERE dynamic 段；`<=` 结束边界按整天匹配成立（PLAN_DATE 为零点值，既有单日期等值查询可证）。

---

---

## 八、四件套的存储过程变体（MoldingPlanExecute，2026-09-03）

> 第七章的落地页 statement 是 `<select>` 动态条件；当查询走 **`<procedure>` 存储过程**（动态拼 SQL 在 proc 里）时，第四件"Mapper 条件"变成"改存储过程"，前三件套路完全不变。落地案例：`Plugins/Molding/ProductPlan/MoldingPlanExecute.aspx`（计划日期 → 开始/结束日期）。

### 8.1 与第七章的差异对照

| 件 | 第七章（select 语句） | 本章（存储过程） |
|----|----------------------|------------------|
| aspx 控件 / JS | 相同 | 相同（daterange 联动 + 双默认值） |
| cs 参数 | PLAN_DATE_BEGIN/END 两个 key | 同左；**PLAN_DATE 仍传开始日期**（过渡兼容，见 8.3） |
| Mapper | 加 isNotEmpty + CDATA 范围条件 | `<procedure>` 里加两行 `@{PLAN_DATE_BEGIN,column=PLAN_DATE_BEGIN}` |
| 数据过滤 | xml dynamic 条件 | **ALTER PROCEDURE 增量 SQL 交付用户执行**（数据库禁连，改不了库端） |

### 8.2 Mapper procedure 写法

```xml
<procedure id="SelectExecutePlan@BpmMoldingPlan" parameterClass="map" resultClass="row">
  PROC_BPM_SELECT_EXECUTE_PLAN
  @{PLAN_DATE,column=PLAN_DATE},
  @{PLAN_DATE_BEGIN,column=PLAN_DATE_BEGIN},
  @{PLAN_DATE_END,column=PLAN_DATE_END},
  @{SHIFT_CODE,column=SHIFT_CODE}
</procedure>
```

- 该项目 iBATIS 的 `<procedure>` 对**调用方字典缺 key 宽容**（先例：`GetRdmBomRDM@RdmBomProduction` 被两处传完全不同的 key 集合调用均正常）；保险起见仍让所有调用方把新增 key 补齐传空串
- ⚠️ **BasicMapper 与 BusinessMapper 目录下同名 xml 内容不同、各嵌一份**，改前先 `grep -l "语句id"` 确认改哪份（本例 SelectExecutePlan 只在 BusinessMapper 份里）

### 8.3 存储过程改造三要点（PROC_BPM_SELECT_EXECUTE_PLAN 实录）

proc 原日期过滤是动态拼接 `if isnull(@PLAN_DATE,'')!='' → 'and t1.PLAN_DATE = xxx'`，改造：

```sql
@DEPT_TYPE VARCHAR(30),--车间
@PLAN_DATE_BEGIN varchar(30)='',--开始日期(范围查询,新增)
@PLAN_DATE_END varchar(30)=''--结束日期(范围查询,新增)
```

```sql
--① 新参数追加在参数表【末尾】且带 '' 默认值：位置传参的老调用方(如上位机)不受影响
--② 范围条件优先：等值条件加"未传范围"守卫，单日期调用方(GetTargetPlan调整弹窗)行为不变
if isnull(@PLAN_DATE,'')!='' and isnull(@PLAN_DATE_BEGIN,'')='' and isnull(@PLAN_DATE_END,'')=''
    set @sqlselect = @sqlselect + 'and t1.PLAN_DATE = '''+@PLAN_DATE+''''
if isnull(@PLAN_DATE_BEGIN,'')!=''
    set @sqlselect = @sqlselect + 'and t1.PLAN_DATE >= '''+@PLAN_DATE_BEGIN+''''
if isnull(@PLAN_DATE_END,'')!=''
    set @sqlselect = @sqlselect + 'and t1.PLAN_DATE <= '''+@PLAN_DATE_END+''''
--③ 最终结果集加固定排序 order by PLAN_DATE,EQUIP_CODE,SEQ_INDEX,SEQ_NO
```

- **过渡兼容技巧**：cs 的 GetStatisticsData 里 PLAN_DATE 仍传 `txt_begin_date.RawText`（不传空串）→ 新页面代码 + 老 Mapper dll 共存期间，过滤退化为"按开始日期等值"= 原行为，**不会出现无日期条件的全量重查询**；proc 改造后范围条件优先，PLAN_DATE 自动失效，无双重过滤
- proc 定义不在仓库时，让**用户从 SSMS 导出一份**（右键存储过程 → 编写脚本）再改，勿凭猜测重写过程体

### 8.4 部署顺序（procedure 变体专属坑）

**必须先跑 UPGRADE SQL、后拷新 Mapper dll**——顺序反了，新 dll 给老 proc 传 `@PLAN_DATE_BEGIN` 会报"为过程或函数指定了过多的参数"，在用页面查询立即报错。顺序对了则全程无破坏窗口：

1. WebSite 页面/cs 改完即生效（动态编译），老 dll 期间 = 原单日等值行为
2. 用户执行 `SQL/UPGRADE_20260903_EXECUTE_PLAN_DATE_RANGE.sql`（proc 加默认参数，向后兼容）
3. 拷 `Wongoing.Molding.Mapper/bin/Release/Wongoing.Molding.Mapper.dll` → WebSite `Bin`（先备份旧 dll 到 tmp/）

### 8.5 参考实现位置

| 内容 | 位置 |
|------|------|
| 本次案例页面 | `Plugins/Molding/ProductPlan/MoldingPlanExecute.aspx(+.cs)` |
| procedure 型 Mapper | `Wongoing.Molding.Mapper/BusinessMapper/BpmMoldingPlan.xml` → `SelectExecutePlan@BpmMoldingPlan` |
| 存储过程增量脚本 | `SQL/UPGRADE_20260903_EXECUTE_PLAN_DATE_RANGE.sql`（含完整 ALTER，可直接执行） |
| proc 原始导出件 | `SQL/PROC_BPM_SELECT_EXECUTE_PLAN.sql`（改造前快照） |

---


## 九、勘误与通用规则：xml 里的 ## 是 iBATIS 字面量转义符（2026-09-03）

> ⚠️ 本节勘误第八章的一处错误论断，并沉淀一条 iBATIS 通用规则。

### 9.1 规则：mapper xml 中要输出字面量 `#` 必须写 `##`

iBATIS 语句体里 `#` 是内联参数定界符（`#参数名#`）。SQL 里需要字面量 `#` 字符时必须写 `##`（转义），iBATIS 渲染后发给数据库的是**单个 `#`**。

- 项目里所有 `tempdb..##xxx` / `into ##xxx` 写法，**数据库端实际都是本地临时表 `#xxx`**（会话隔离），不是 SQL Server 语法的全局临时表 `##xxx`。
- 直接在 xml 里写单个 `#`（如 `into #equiplist`）→ 解析器把它当参数定界符吞掉后续文本直到下一个 `#` → 启动/执行时报 `can't recognize parameter mapping field: '...'`，且报错里显示的"字段名"是一大段无关 SQL。

### 9.2 勘误

第八章 8.2 曾写"`##curingplanexe` 全局临时表两段式"并暗示多用户并发竞态风险——**错误**：经上述转义规则，DB 端一直是本地临时表，无跨会话共享，原语句本就没有并发竞态问题。当日优化中 `##→#` 的"修正"正是踩了这个坑（报错后已回退为 `##`）。

### 9.3 当日 SQL 优化的最终形态（2026-09-03）

- `##curingplanexe` 中转表已删除：原"CTE → into 临时表 → 再 select"合并为对 CTE 单次 SELECT 直出（`row_number()` 移到输出列第二位计算，列名列序不变）——该改动不含 `#`，不受转义规则影响。
- `##equiplist` 保留原样（`##` 转义 = DB 端本地临时表，正确写法）。
- 改动任何含 `#`/`##`/`$` 的 mapper 语句后，除 XML 良构校验外，还需在测试环境触发一次该语句执行验证 iBATIS 解析通过（良构 ≠ 解析通过）。

---


## 十、日期范围改造的第五件套：结果表放开日期列（2026-09-03 Curing 补充）

> 单日查询时代，结果表格的日期列常被 `Hidden="true"`（当天查询里日期冗余）。改日期范围后跨天结果必须能分辨行属哪天——把该列放开并配日期-only 渲染，否则用户看到多天数据却无从分辨。落地：CuringPlanExecute 主表 pnlCuring 的 PLAN_DATE 列。

```aspx
<ext:Column runat="server" DataIndex="PLAN_DATE" Text="计划日期" Width="90">
    <Renderer Fn="changeDateOnly" />
</ext:Column>
```

```javascript
var changeDateOnly = function (value) {
    if (value == null || value == "") { return ""; }
    var date = new Date(value);
    function padZero(num) { return num < 10 ? '0' + num : num; }
    return date.getFullYear() + '-' + padZero(date.getMonth() + 1) + '-' + padZero(date.getDate());
}
```

- 不加渲染会显示 ISO 原串（`2026-09-03T00:00:00`）且被列宽截断；渲染函数复用页面既有 changePlanDate 的写法，只留年月日
- 配合 statement 的 `ORDER BY PLAN_DATE, ...`（7.5 顺手项），跨天行按日期自然分组
- 弹窗类单日场景（如调整弹窗/源计划弹窗）的日期列不必动——单日信息冗余，维持原状

---

---

## 九、proc 转写铁律：改造后必须与导出件逐行 diff（2026-09-03 expert-sql 抓出 P0 实录）

> 第八章落地当天，expert-sql 审查抓出交付脚本里一个**转写引号错误**——手打复写 proc 体的误差靠肉眼复查不出来，必须机械 diff。

### 9.1 案例

改造 `PROC_BPM_SELECT_EXECUTE_PLAN` 时，EQUIP_CODE 拼接行原版行尾 `+''`（空串）被误打成 `+'''`：

```sql
-- 原版（对）：...+@EQUIP_CODE+''
-- 误打（错）：...+@EQUIP_CODE+'''   ← T-SQL 字面量错位，吞行到下个引号才闭合
```

- 后果：T-SQL 字符串可含换行，多余引号让字面量错位吞行 → **ALTER 批次整体编译失败**，proc 部署不上去；同时新 Mapper 已按 8 参数传参，打到旧 6 参数 proc 连锁报 8144"参数过多"——双重阻断
- 转写还会顺手改掉行内空白（如 `case when` 行缩进），串内空白无害但说明"复写不可信"

### 9.2 铁律（改存储过程的收尾动作）

1. **改完 proc 必须与原始导出件逐行 diff**（python difflib：以 `ALTER PROCEDURE` 行对齐起点，unified_diff 输出全部偏差行），每条偏差必须能对应到"有意改动清单"，出现清单外的偏差行=转写错误，逐条修掉
2. **引号奇偶目检**：动态 SQL 拼接行的 `'` 总数与原版同模式行一致（`'...'''+@X+''''` 是项目标准引号模式，照抄别自创）
3. SQL 重交付（含 proc 改造）默认走 expert-sql 审——本次 byte 级核验正是审查员抓出主线程漏掉的错误；报告归档项目 `SQL_Review_<日期>/`

### 9.3 相关

- 部署顺序与 8144 连锁：见本文 8.4
- 审查报告实例：`Molding/SQL_Review_20260903/PROC_BPM_SELECT_EXECUTE_PLAN_优化角度清单.md`（P0 修复 + P1/P2 优化角度分级清单 + 索引 DDL + sys.columns 核查 SQL 模板）

---

## 十一、反向改造：选择弹窗/下拉 → 纯文本模糊输入（2026-09-15）

> 与本篇方向相反的改造：用户不要"弹窗选一个"，要"打字直接模糊搜"。

适用：选择成本高、值域过大、用户明确要模糊匹配名称（如 Curing 九页"制造编号改 MATERIAL_NAME LIKE"批量改造）。完整模式见 `extnet-query-popup-to-text-fuzzy.md`，三句话版：

- aspx：TextField 去掉 Editable/Search 接线与 `Name` 属性，只留 Clear；删隐藏域与弹窗 JS 三件套
- cs：`txtXxx.Text.Trim()` 传名称参数（不要 RawText——Name 与弹窗字段重名时会读到逗号拼接串）
- SQL：`like '%'+参数+'%'`；多语句共用 `<include>` 时改一处全覆盖；proc 动态拼接需 replace 转义单引号