---
title: Quality 报表开发指南（新增报表速查）
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET,报表,开发规范,踩坑,Quality]
status: active
updated: 2026-09-16
---
# Quality 报表开发指南（新增报表速查）

> 基于「轮胎领用记录」报表开发过程沉淀，后续新增报表直接照此模板。2026-09-16 并入「成品胎仕上流转记录」交付期四条新坑（第六节标注），完整实录见 [[tire-flow-record-implementation]]。

## 一、什么时候用动态列 vs 固定列

| 场景 | 方式 | 示例 |
|------|------|------|
| 列名固定、数量不变 | **ASPX 直接声明** Model + Columns | 轮胎领用记录（6 列） |
| 交叉统计/行列动态生成 | CS 动态 BuildGrid | 质检数量统计（按视图切换列） |
| 列数不固定（如 UF/DB 检测项） | CS 动态 BuildGrid | 轮胎移动台账 |

**原则**：能固定就固定，不要为了"灵活"把简单报表复杂化。

## 二、ASPX 骨架（固定列）

```aspx
<%@ Page Language="C#" AutoEventWireup="true" CodeFile="ReportName.aspx.cs"
    Inherits="Plugins_Quality_ReportAnalyse_ReportName" %>

<ext:GridPanel ID="pnlMain" runat="server" Region="Center">
    <Store>
        <ext:Store ID="storeMain" runat="server" AutoLoad="false" PageSize="100">
            <Model>
                <ext:Model ID="model" runat="server">
                    <Fields>
                        <ext:ModelField Name="COL1" />
                        <ext:ModelField Name="COL2" />
                    </Fields>
                </ext:Model>
            </Model>
        </ext:Store>
    </Store>
    <ColumnModel>
        <Columns>
            <ext:RowNumbererColumn Width="40" Align="Center" />
            <ext:Column Text="列1" DataIndex="COL1" Width="150" Align="Center" />
            <ext:DateColumn Text="时间列" DataIndex="COL2" Width="150" Align="Center" Format="yyyy-MM-dd HH:mm:ss" />
        </Columns>
    </ColumnModel>
    <View>
        <ext:GridView runat="server" StripeRows="true" TrackOver="true" EnableTextSelection="true" />
    </View>
    <BottomBar>
        <ext:PagingToolbar runat="server" DisplayInfo="true">
            <Items>
                <ext:Label runat="server" Text="每页显示:" />
                <ext:ComboBox runat="server" Width="60" Editable="true" ForceSelection="false">
                    <Items>
                        <ext:ListItem Text="100" Value="100" />
                        <ext:ListItem Text="200" Value="200" />
                        <ext:ListItem Text="500" Value="500" />
                    </Items>
                    <SelectedItems>
                        <ext:ListItem Value="100" />
                    </SelectedItems>
                    <Listeners>
                        <Select Handler="#{storeMain}.pageSize = parseInt(this.getValue()); #{storeMain}.loadPage(1);" />
                    </Listeners>
                </ext:ComboBox>
            </Items>
        </ext:PagingToolbar>
    </BottomBar>
</ext:GridPanel>
```

## 三、分页规范

### 纯客户端分页（UNION ALL / 固定列报表推荐）
- Store 设 `PageSize="100"`，**不加 `RemotePaging`，不加 `<PageProxy>`**
- 翻页不发请求，前端自动切片
- 每页条数 ComboBox：**必须 `Editable="true" ForceSelection="false"`**，否则手输数字会被清空
- 改条数后调 `loadPage(1)` 回到首页，不用 `reload()`

### 服务端分页（大表 + 单表查询推荐）
- Store 加 `RemotePaging="true"` + `<PageProxy DirectFn="App.direct.GridPanelBindData">`
- 后端用 `GetPageDataByReader` 配合 `PageResult`
- UNION ALL 不适合此模式（需要 includeSelect/includeWhere 结构）

## 四、Code-Behind 最小模板（固定列）

```csharp
public partial class Plugins_Quality_ReportAnalyse_ReportName : Wongoing.Web.UI.Page
{
    private IFqbBalanceInfoManager balanceManager = new FqbBalanceInfoManager();

    // 权限定义（固定模板）
    protected __ _ = new __();
    public class __ : Wongoing.Web.UI.___
    {
        public __()
        {
            查询 = new PageAction() { ActionId = 1, ActionName = "btnSearch" };
            导出 = new PageAction() { ActionId = 2, ActionName = "btnExport" };
        }
        public PageAction 查询 { get; private set; }
        public PageAction 导出 { get; private set; }
    }

    protected void Page_Load(object sender, EventArgs e)
    {
        if (!X.IsAjaxRequest)
        {
            txt_Start_day.SelectedDate = DateTime.Now;
            txt_End_day.SelectedDate = DateTime.Now;
            // 初始化下拉框...
        }
    }

    [DirectMethod(Timeout = 3000000)]
    public string storeMain_ReadData()
    {
        try { BindData(); return ""; }
        catch (Exception ex) { return ex.Message; }
    }

    private void BindData()
    {
        var param = new Dictionary<string, object>() {
            {"Start_date", txt_Start_day.RawText},
            {"End_date", txt_End_day.RawText},
        };
        DataSet ds = balanceManager.GetDataSetByStatement("SelectXxx", param);
        DataTable dt = (ds != null && ds.Tables.Count > 0) ? ds.Tables[0] : new DataTable();

        Session["ReportData"] = dt;       // 缓存给导出用
        storeMain.DataSource = dt;
        storeMain.DataBind();             // 就这两行，不用 ClearGrid/BuildGrid
    }

    // 导出：从 Session 读全量，生成 HTML 表格输出 .xls
    protected void btnExportSubmit_Click(object sender, EventArgs e)
    {
        DataTable dt = Session["ReportData"] as DataTable;
        if (dt == null || dt.Rows.Count == 0) return;
        // ... GenerateHtmlTable + Response.Write ...
    }
}
```

## 五、SQL 编写要点

### 派生表 vs 条件下推
- ❌ 不要 `SELECT * FROM (UNION ALL) T WHERE ...` → 外层过滤可能导致全表扫描
- ✅ 把条件分别推入每个 UNION 分支的 WHERE 中，让各自基表索引生效

### 参数化（iBATIS）
```xml
<select id="SelectXxx" parameterClass="map" resultClass="row">
    <![CDATA[SELECT ... WHERE DELETE_FLAG = 0]]>
    <dynamic prepend="AND">
        <isNotNull property="Start_date" prepend="AND">
            <![CDATA[CONVERT(VARCHAR, t1.RECORD_TIME, 23) >= #Start_date#]]>
        </isNotNull>
    </dynamic>
</select>
```
- `dynamic prepend` 的值会**替换第一个子元素的 prepend**，不会出现 `AND AND` 双写
- 参数传 null 时对应 `<isNotNull>` 跳过，避免生成多余的筛选条件
- **追溯/履历类报表例外**：用户口径"记录全量显示"，DELETE_FLAG 过滤整个去掉（见 [[tire-flow-record-implementation]]，勿照抄本节示例的 DELETE_FLAG=0）

### 时间列
- DateField 的 `RawText` 取到 `yyyy-MM-dd` 格式字符串
- SQL 中用 `CONVERT(VARCHAR, RECORD_TIME, 23)` 转同格式比较
- 前端用 `<ext:DateColumn Format="yyyy-MM-dd HH:mm:ss" />` 显示

## 六、Grid 细节

| 项目 | 设置 |
|------|------|
| **内容可复制** | `<ext:GridView EnableTextSelection="true" />` |
| 隔行变色 | `StripeRows="true"` |
| 鼠标悬停高亮 | `TrackOver="true"` |
| 单元格边距 | CSS `.x-grid-cell-inner { padding: 3px 4px !important; }` |
| 时间列 | `<ext:DateColumn Format="yyyy-MM-dd HH:mm:ss" />` |
| 行号 | `<ext:RowNumbererColumn Width="40" Align="Center" />` |
| **页面内筛选** | GridPanel 挂 `<Plugins><ext:FilterHeader runat="server" CaseSensitive="false" /></Plugins>`（纯前端），要"直接输入即模糊"再配 matchAnywhere JS——写法与生产同款页面清单见 [[extnet-grid-advanced-features]] |

## 七、导出规范

- 导出按钮用 `<asp:Button display:none>` + JS `$('#btnExportSubmit').click()` 触发 postback
- 数据从 `Session["ReportData"]` 取，**不要重新查库**
- HTML 表格导出 .xls：UTF-8 BOM + Content-Type `application/ms-excel`
- **扫枪输入页必防**：隐藏的 `btnExportSubmit` 是 WebForms 表单默认提交钮（DOM 第一个 submit），输入框按回车会误触导出下载旧数据——查询输入框加 `<Listeners><SpecialKey Handler="if (e.getKey() === e.ENTER) { e.preventDefault(); 查询函数(); }" /></Listeners>`

## 八、常见坑速查（建报表高频）

| 坑 | 正解 |
|----|------|
| iBATIS XML 里 `<` `>` `&` 报错 | XML 特殊字符，含它们的 SQL 必须包 `<![CDATA[ ]]>`。开区间时间比较 `record_time < DATEADD(...)` 尤其易漏 |
| Grid 列显示空白 | ModelField `Name`/Column `DataIndex` 大小写敏感，必须和 SQL 返回列名一致。`HPP_SEMIS_*`/`SBM_*` 全大写，`Ppt_*` PascalCase。详见 `extnet-grid-columname-case.md` |
| `isNotNull` 空串仍触发过滤 | 可选过滤场景用 `isNotEmpty`（null 和空串都跳过）；`isNotNull` 只跳过 null。详见 `consumption-output-report.md` 第五节 |
| `<Renderer Format="0.000" />` 报错 | `Format` 是 `RendererFormat` 枚举，不能填任意字符串。用合法枚举值或去掉 Renderer，数值格式化改用其他方式 |
| `<isEqual>` 对 Dictionary 参数抛空引用 | iBATIS 兼容 bug。用 `<isNotNull>`/`<isNotEmpty>` 替代。详见 `mcui-to-handwritten-aspx-full-pattern.md` |
| UNION 报表里的标记列（`1 AS SCRAP_TYPE`）当物理列用 → "列名无效" | 标记列是语句拼的字面量不是表列；先读原语句分支注释与 SELECT 列表实证（案例：FQS_SCRAP_INFO 无 SCRAP_TYPE，整表即 YRC 报废） |
| 字典表名列臆写 ITEM_NAME → "列名无效" | `SSB_DIC_ITEM` 名列是 **ITEM_DESC**；JOIN：`DIC_CODE='字典码' AND 业务码列=ITEM_CODE` |
| 扫枪回车误触隐藏导出钮 | 见第七节导出规范末条：SpecialKey ENTER 拦截后调查询函数 |
| `CASE 列 WHEN '1' THEN '文本' ELSE 列 END` 报转换失败 | 整型列+字符串分支混用，返回类型按优先级取 int；ELSE 侧补 `CONVERT(VARCHAR(10), 列)` |

## 九、技术约束（C# 5，防编译失败）

- ❌ 禁用：字符串插值 `$""`、null 条件 `?.`、null 合并 `??`、表达式体 `=>`、`nameof`
- ✅ 用 `string.Format()`、显式 null 检查、传统属性

## 十、关联文档

| 文档 | 内容 |
|------|------|
| `sql-server-performance-troubleshooting.md` | **SQL 语句优化原则 6 条（本文第五节来源）** |
| `extnet-grid-columname-case.md` | Grid 列名大小写坑（第八节） |
| `consumption-output-report.md` | isNotNull/isNotEmpty 区别、改 SQL 踩坑、Renderer 枚举坑 |
| `mcui-to-handwritten-aspx-full-pattern.md` | iBATIS `<isEqual>` 对 Dictionary 的 bug |
| `semi-report-styles.md` | 10 种报表布局样式选型 |
| `standard-report-template.md` | 标准报表完整 ASPX + CS 骨架 |
| `summary-detail-report-template.md` | 汇总+明细报表模板 |
| `dynamic-column-grid.md` | 动态列 GridPanel |
| `data-dictionary.md`（quality 库） | 字段释义，B 路径查表用 |
| [[tire-flow-record-implementation]] | 成品胎仕上流转记录页：12 表多源 UNION 追溯报表完整实录（2026-09-16 新坑 4 条的出处） |
| [[extnet-grid-advanced-features]] | FilterHeader 表头筛选与 matchAnywhere 模糊写法 |

## 十一、部署 Checklist

- [ ] BusinessMapper XML → **重新编译 Mapper 工程**
- [ ] .aspx / .aspx.cs → 直接部署到 WebSite（新建 aspx 记得带 UTF-8 BOM）
- [ ] `SSP_PAGE_MENU` 表新增菜单入口
- [ ] 测试查询 + 分页 + 导出
- [ ] 确认 GridView `EnableTextSelection="true"` 已加
