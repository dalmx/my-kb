---
status: active
updated: 2026-09-17
title: 基础查询报表模板（单表查询+导出+UI基线）
category: 技术-.NET
module: Ext.NET
tags: [Ext.NET, 报表模板, 基础查询报表, 简单报表, 查询导出, FilterHeader, 表头过滤, 列居中, 分钟粒度, 时间精确到分钟, DATEADD, 客户端分页, doRefresh, loadPage, 每页条数, 刷新按钮, DELETE_FLAG, 轻量报表, 不建实体, 复用statement, 免重编dll]
---

# 基础查询报表模板（单表查询+导出+UI基线）

> 单表/简单多条件、固定列、查询+导出的**轻量报表**完整样式基线：查询区固定宽布局、分钟粒度时间条件全链路、CuringProductionQuery 级 UI 丰富度（FilterHeader/列居中/序号列）、客户端分页 doRefresh 禁忌。差异式模板，骨架以 [standard-report-template.md](standard-report-template.md) 为基座。实证页：Curing `Plugins/Curing/ReportCenter/AbnormalTireScanRecord.aspx`（2026-09-11 交付，全流程一次通过）、Molding `Plugins/Molding/Report/ArtTrolleyBindLog.aspx`（2026-09-17 交付，statement 复用变体，见 [molding-art-trolley-bind-log.md](molding-art-trolley-bind-log.md)）。

## 一、适用场景与选型

单张业务表（或简单 JOIN）、查询条件 ≤5 个（时间范围+若干输入/下拉）、固定列、客户端分页、导出 Excel。不需要汇总明细（→汇总+明细模板）、动态列（→动态列模板）、图表（→图表+表格模板）时的默认选择。

轻量报表**不新建实体**：复用同域现有 Manager（如 `CppCuringProductionManager`）+ `GetDataTableByStatement("SelectXxx@Entity", param)`，statement 按文件已有风格命名（Curing 的 CppCuringProduction.xml 用 `动作@Entity` 风格）。

**复用既有 statement 优先于新写（2026-09-17 实证）**：动手写新语句前，先 grep 同表/同域既有 statement 的 `<dynamic>` 条件清单——若已覆盖新报表需求（含**口径区分参数**，如固定传 `LogSys='PC'`/`DeleteFlag='0'` 做同表口径变体页），新页面直接传参复用，**零 Mapper 改动、免重编 dll**，部署只剩拷页面文件。实证：Molding 生胎台车绑定记录整页克隆同表「生胎出入库记录」页，仅换固定参数与列头。

## 二、UI 样式基线（"太简单"的答案，参考 CuringProductionQuery）

用户对纯复刻 RetainedTireRecord 的极简版反馈"UI 太简单，参考 CURINGPRODUCTIONQUERY"。基础报表 UI 丰富度基线 = standard 骨架 + 以下增强：

1. **TopBar**：查询 | 导出查询结果 | `ToolbarFill`（把"隐藏查询"推到最右）——不堆业务按钮。
2. **查询区**：`ext:Container Layout="FormLayout" Width="320"` 固定宽竖排列（不用 ColumnWidth=".25" 等分），列间用 `<%-- 列N --%>` ASP.NET 注释分节（服务端注释在 Items 内安全，HTML 注释不行）。
3. **时间组合框**：FieldContainer + `HBoxLayoutConfig Align="Stretch" Pack="Start"`，DateField `Width="110"` + TimeField `Width="110" MarginSpec="0 0 0 5"`，Format 用 `H:i`（Ext PHP 格式符，≡HH:mm）。
4. **GridPanel**：`Cls="border-top"`、`<Plugins><ext:FilterHeader CaseSensitive="false" /></Plugins>`（表头过滤，客户端分页下对全量数据生效）、RowNumbererColumn 带 `Text="序号" Width="50" Align="Center"`、**所有列 `Align="Center"`**、日期 ModelField 加 `Type="Date"`、GridView 三件套（EnableTextSelection/TrackOver/StripeRows）。
5. **选择模型**：无行操作就 `RowSelectionModel Mode="Single"`——CheckboxSelectionModel Multi 是为批量业务功能准备的，用户明确"不需要复选框"。
6. **分页条**：档位 20/30/50/100 + `<SelectedItems><ext:ListItem Index="3" /></SelectedItems>`（默认 100）+ ProgressBarPager 插件。

## 三、时间条件精确到分钟的完整链路

页面 TimeField `Format="H:i" Increment="1"`（分钟粒度）起，三层配合：

1. **默认值**（C# Page_Load + JS viewportAfterRender 双层兜底）：日期=今天，时间 `00:00`/`23:59`。
2. **C# 拼接**（.aspx.cs，RawText 取值，空兜底）：
```csharp
string beginTime = txt_BeginDate.RawText + " " + (string.IsNullOrEmpty(txt_BeginTime.RawText) ? "00:00" : txt_BeginTime.RawText);
string endTime = txt_EndDate.RawText + " " + (string.IsNullOrEmpty(txt_EndTime.RawText) ? "23:59" : txt_EndTime.RawText);
```
3. **SQL 边界（关键语义）**：分钟粒度下结束侧必须 `DATEADD(minute, 1, #END_TIME#)` 开区间——传 `23:59` 被 SQL Server 解析为 23:59:00.000，`<=` 会漏掉 23:59:01~59 的记录；`< DATEADD(minute,1,...)` = < 次日 00:00 才含所选分钟整段。偏移只放 SQL 一侧，页面传原始分钟值。开始侧 `>=` 天然含整分钟无需处理。天粒度（HH:mm:ss + 默认 23:59:59）用 `<=` 即可（RetainedTireRecord 模式）——两种口径别混。

## 四、客户端分页禁忌（改条数变空的根因）

无 Proxy 的客户端分页 Store，`doRefresh()` = `store.load()` 空加载会**清空已查数据**。改每页条数必须用内存切片，刷新按钮 ↻ 同根因须一并接管（详细原理见 [extnet-pagination-guide.md](extnet-pagination-guide.md)）：
```javascript
var applyPageSize = function (combo) {
    var size = parseInt(combo.getValue(), 10);
    if (isNaN(size) || size < 1) return;
    App.Store1.pageSize = size;
    App.Store1.loadPage(1);   // 内存切片回首页，禁 doRefresh
}
var bindRefresh = function (toolbar) {
    var btn = toolbar.child('#refresh');
    if (btn) { btn.setHandler(function () { pnlListFresh(); }); }  // 刷新=重查
}
```
ComboBox 挂 `<Change Fn="applyPageSize" />`；PagingToolbar 挂 `<AfterRender Handler="bindRefresh(this);" />`。禁忌：不要用 Store `BeforeLoad` 全局拦截实现刷新（破坏 DataBind）。本项目旧页 RetainedTireRecord 的 Change 里就是 `doRefresh()`——复刻时必改。

## 五、Mapper 与 SQL 要点

```xml
<select id="SelectXxxRecord@CppCuringProduction" parameterClass="map" resultClass="row">
    <![CDATA[
        SELECT t1.OBJID, t1.BARCODE, t1.RECORD_TIME, t1.RECORD_USER_ID, t1.REMARK
        FROM CPP_XXX t1 WITH(nolock)
        WHERE t1.DELETE_FLAG = '0'
    ]]>
    <dynamic>
        <isNotEmpty property="BEGIN_TIME" prepend="AND"><![CDATA[t1.RECORD_TIME >= #BEGIN_TIME#]]></isNotEmpty>
        <isNotEmpty property="END_TIME" prepend="AND"><![CDATA[t1.RECORD_TIME < DATEADD(minute, 1, #END_TIME#)]]></isNotEmpty>
        <isNotEmpty property="BARCODE" prepend="AND"><![CDATA[t1.BARCODE LIKE '%' + #BARCODE# + '%']]></isNotEmpty>
    </dynamic>
    <![CDATA[ORDER BY t1.RECORD_TIME DESC]]>
</select>
```

- **DELETE_FLAG 是 varchar 列时用 `= '0'`**（字符串比较，与列类型一致）：`= 0` 整数比较会把列侧隐式转 int，列中存非数字字符即报转换错误。项目旧代码 43 处不带引号是历史主流（多表实际存数字未炸），**新写 SQL 按列类型严格匹配**——2026-09-11 用户实证纠正。
- **人员字段转真实姓名**：`*_USER_ID` 存工号条码，`LEFT JOIN SSB_USER t2 WITH(NOLOCK) ON t2.WORK_BARCODE = t1.RECORD_USER_ID`，取 `ISNULL(t2.REAL_NAME, t1.RECORD_USER_ID) AS RECORD_USER_NAME`——ISNULL 兜底让 JOIN 不上的行退回显示工号（信息不丢、不空白）；Model/DataIndex/导出列名映射同步用 RECORD_USER_NAME 别名。详细规则（关联键是 WORK_BARCODE 非 OBJID、Mould 存量双模式警告）见 [mes-dic-user-join-pattern.md](mes-dic-user-join-pattern.md)。
- 固定条件写 SQL 本体、动态条件 `<dynamic>` 首子元素 `prepend="AND"`（CDATA 内不写 AND）；全表 WITH(NOLOCK)；导出列名改中文、剔除 OBJID 内部字段；权限 PageAction 只声明 btnSearch/btnExport 两个功能按钮。
- **导出剔列靠 ColumnModel**：导出按 `ColumnModel.Columns` 的 DataIndex 匹配重命名——**Hidden=true 的列也会被匹配保留**。不想导出的列干脆别放进 ColumnModel（2026-09-17 实证：ArtTrolleyBindLog 只放可见列，SQL 多返回的 OBJID/工号等自动剔除）。

## 六、参考落地页

- `Curing/ReportCenter/AbnormalTireScanRecord.aspx(.cs)`：本模板全量实证（CPP_ABNORMAL_TIRE_INVENTORY 异常胎扫描记录，2026-09-11）。
- `Molding/Report/ArtTrolleyBindLog.aspx(.cs)`：**statement 复用变体**实证（2026-09-17，克隆同表 Storage/ArtStoreLocationLog 整页 + 固定传 LogSys/DeleteFlag + 三个 LIKE 模糊条件，零 Mapper 改动免重编 dll；详见 [molding-art-trolley-bind-log.md](molding-art-trolley-bind-log.md)）。
- `Curing/Produce/CuringProductionQuery.aspx`：UI 基线来源（业务功能勿抄——追溯/年周号修改/Excel 导入是重型业务，双模式时间切换依赖其表字段）。
- `Curing/ReportCenter/RetainedTireRecord.aspx`：分钟粒度时间条件的另一形态（HH:mm:ss + `<=` 口径），但其分页 Change 是带病的 doRefresh 写法，勿照抄。
