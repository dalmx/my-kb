---
category: 技术-.NET
factory: 通用
module: Ext.NET
status: active
tags:
- Ext.NET
- Excel导出
- Session缓存
- DataTable.Copy
- 二次导出
- 踩坑
- 65536行上限
- 分Sheet导出
- HSSF
- DLL版本漂移
title: Ext.NET Excel 导出/上传 + 资源文件 i18n + 错误处理统一模式
updated: '2026-09-17'
---

# Ext.NET Excel 导出/上传 + 资源文件 i18n + 错误处理统一模式

> 本文覆盖 Semi 项目的三大横切关注点：Excel 导出（含列重命名/合计行/模板下载）、Excel 上传、资源文件中英双语用法、错误处理与提示的统一模式。这些都是每个页面都要做的事。

## 一、Excel 导出（DataTable → ExcelDownload）

### 1.1 核心调用

统一用 `Wongoing.Utility.Excel.ExcelDownload` 工具类：

```csharp
new Wongoing.Utility.Excel.ExcelDownload().ExcelFileDown(dataTable, "导出文件名");
```

### 1.2 列重命名 —— 方式 A：按 GridModel 映射（最通用）

遍历 DataTable 的列，到 GridPanel 的 ColumnModel 里找对应列，把列名改成列头的 `Text`，未在 GridPanel 中显示的列直接删除。

```csharp
protected void btnExportSubmit_Click(object sender, EventArgs e)
{
    var selPara = (Dictionary<string, object>)Session["inspara"];
    var data = hppSemisProductionManager.GetDataTableByStatement("MyQuery@HppSemisProduction", selPara);

    // 按前台 GridPanel 的列重命名/删除
    for (int i = 0; i < data.Columns.Count; i++)
    {
        bool isshow = false;
        DataColumn dc = data.Columns[i];
        foreach (ColumnBase cb in this.pnlBill.ColumnModel.Columns)
        {
            if (cb.DataIndex != null && cb.DataIndex.ToUpper() == dc.ColumnName.ToUpper())
            {
                dc.ColumnName = cb.Text;   // 列头 Text 作为导出列名
                isshow = true;
                break;
            }
        }
        if (!isshow)
        {
            data.Columns.Remove(dc.ColumnName);
            i--;   // ⚠️ 删除后索引回退
        }
    }

    new Wongoing.Utility.Excel.ExcelDownload().ExcelFileDown(data, "半成品产出统计");
}
```

> 优点：前台改列顺序/列头后，导出自动同步，不用改后台。`pnlBill` 是 GridPanel 的 ID。

### 1.3 列重命名 —— 方式 B：直接改列名（资源化）

```csharp
planData.Columns["PLAN_DATE"].ColumnName     = GetGlobalResourceObject("Semi","业务日期").ToString();
planData.Columns["MATERIAL_CODE"].ColumnName  = GetGlobalResourceObject("Semi","物料编码").ToString();
planData.Columns["TOTAL_WEIGHT"].ColumnName   = GetGlobalResourceObject("Semi","重量").ToString();

new Wongoing.Utility.Excel.ExcelDownload().ExcelFileDown(
    planData,
    GetGlobalResourceObject("Semi","半制品产量统计").ToString()
);
```

> 适用场景：列固定不变、需要资源化列头。混合使用两种方式也可以（部分列用 GridModel 映射，部分列直接改）。

### 1.4 合计行（DataTable.Compute + NewRow）

```csharp
// 求和（在改列名之前用原列名，或改后用新列名）
object totalQty = data.Compute("sum([数量])", "");
object totalWt  = data.Compute("sum([重量])", "");

DataRow dr = data.NewRow();
dr[0] = "合计";
dr["数量"] = totalQty;
dr["重量"] = totalWt;
data.Rows.Add(dr);

new Wongoing.Utility.Excel.ExcelDownload().ExcelFileDown(data, "统计报表");
```

> `DataTable.Compute("sum([列名])", "")` 第二参数是过滤条件，空串表示不过滤（全部行求和）。

### 1.5 多 DataTable 合并导出

汇总和明细是分别查询的，需要合并到一个 DataTable 导出：

```csharp
var summaryData = (DataTable)Session["summaryData"];
var detailData  = (DataTable)Session["detailData"];

// 方式：把明细列拼到汇总后面，或用 ImportRow 追加
// 详见各报表页的具体实现
```

### 1.6 模板下载

```csharp
protected void btnDownload_ClickEvent(object sender, DirectEventArgs e)
{
    Response.ContentType = "application/vnd.ms-excel";
    Response.AddHeader("Content-Disposition", "attachment;filename=Template.xls");
    Response.WriteFile(Server.MapPath("~/Templates/UploadTemplate.xlsx"));
    Response.End();
}
```

## 二、Excel 上传

### 2.1 上传按钮

```aspx
<ext:Button ID="btnImport" runat="server" Text="批量导入" Hidden="true">
    <DirectEvents>
        <Click OnEvent="UploadClick">
            <ExtraParams>
                <ext:Parameter Name="filePath" Value="#{FileUploadField1}.getValue()" Mode="Raw" />
            </ExtraParams>
        </Click>
    </DirectEvents>
</ext:Button>
```

### 2.2 上传处理（DataToFile.FromExcel + 列校验）

```csharp
protected void UploadClick(object sender, DirectEventArgs e)
{
    // 1. 取上传文件
    string filePath = e.ExtraParams["filePath"];
    // （实际路径由 FileUploadField 的 PostedFile 决定）

    // 2. 读 Excel 为 DataTable
    DataTable dt = DataToFile.FromExcel(filePath);

    // 3. 列校验（必须有这些列）
    string[] requiredCols = { "物料编码", "数量", "日期" };
    foreach (string col in requiredCols)
    {
        if (!dt.Columns.Contains(col))
        {
            X.Msg.Alert("提示", "缺少必要列：" + col).Show();
            return;
        }
    }

    // 4. 逐行处理
    foreach (DataRow row in dt.Rows)
    {
        var param = new Dictionary<string, object> {
            {"MATERIAL_CODE", row["物料编码"].ToString()},
            {"QTY", row["数量"].ToString()},
            {"PLAN_DATE", row["日期"].ToString()}
        };
        // 插入数据库...
    }

    X.Msg.Alert("提示", "导入成功").Show();
}
```

> `DataToFile.FromExcel` 是框架封装的 Excel 读取工具。列校验放在数据处理之前，避免脏数据。

## 三、资源文件 i18n 双端用法

资源文件位于 `App_GlobalResources/Semi.resx`（全局资源，类名 `Semi`）。键多为中文短语（`查询`、`物料编码`、`半制品产量统计`）。

### 3.1 前台用法（`<%$Resources:Semi,键 %>`）

```aspx
<!-- 控件属性绑定 -->
<ext:Button runat="server" Text="<%$Resources:Semi,查询 %>" ID="btnSearch">
<ext:DateField runat="server" FieldLabel="<%$Resources:Semi,开始日期 %>" ID="txt_Start_day" />
<ext:Column DataIndex="MATERIAL_CODE" Text="<%$Resources:Semi,物料编码 %>" Width="120" />

<!-- JS 文案用 Literal 包裹 -->
<script type="text/javascript">
    Ext.Msg.alert('<asp:Literal runat="server" Text="<%$Resources:Semi,错误 %>" />', errorMsg);
</script>
```

### 3.2 后台用法（`GetGlobalResourceObject`）

```csharp
// 弹窗标题/内容
X.Msg.Show(new MessageBoxConfig {
    Title   = GetGlobalResourceObject("Semi","错误").ToString(),
    Message = ex.Message,
    Icon = MessageBox.Icon.ERROR,
    Buttons = MessageBox.Button.OK
});

// 导出列名
planData.Columns["PLAN_DATE"].ColumnName = GetGlobalResourceObject("Semi","业务日期").ToString();

// 导出文件名
new Wongoing.Utility.Excel.ExcelDownload().ExcelFileDown(
    planData,
    GetGlobalResourceObject("Semi","半制品产量统计").ToString()
);
```

### 3.3 添加资源键

编辑 `App_GlobalResources/Semi.resx`（XML 格式），加 `<data>` 节点：
```xml
<data name="回收胶消耗" xml:space="preserve">
  <value>回收胶消耗</value>
</data>
```
> 新增页面时，把所有中文文案都加成资源键，避免硬编码。

## 四、错误处理与提示统一模式

### 4.1 服务端提示（X.Msg）

**轻提示（Alert）**：
```csharp
X.Msg.Alert("提示", "请选择开始日期").Show();   // ⚠️ 别忘了 .Show()
```

**规范提示（MessageBoxConfig + 图标）**：
```csharp
// 错误
X.Msg.Show(new MessageBoxConfig {
    Title = GetGlobalResourceObject("Semi","错误").ToString(),
    Message = ex.Message,
    Icon = MessageBox.Icon.ERROR,
    Buttons = MessageBox.Button.OK
});

// 成功
X.Msg.Show(new MessageBoxConfig {
    Title = GetGlobalResourceObject("Semi","提示").ToString(),
    Message = GetGlobalResourceObject("Semi","统计成功请查询信息").ToString(),
    Icon = MessageBox.Icon.INFO,
    Buttons = MessageBox.Button.OK
});

// 警告
X.Msg.Show(new MessageBoxConfig {
    Title = "提示",
    Message = "该记录已开单，不可删除",
    Icon = MessageBox.Icon.WARNING,
    Buttons = MessageBox.Button.OK
});
```

> ⚠️ 常见遗漏：`X.Msg.Alert(...)` 必须链式调 `.Show()` 才会显示。`X.Msg.Show(new MessageBoxConfig{...})` 则不需要 `.Show()`（因为 `Show` 方法本身就触发显示）。

### 4.2 前端提示（Ext.Msg）

```js
Ext.Msg.alert('操作', result);                    // 普通提示
Ext.Msg.confirm('确认', '确定删除吗？', function(btn) {
    if (btn == 'yes') { /* 执行 */ }
});                                              // 二次确认
```

### 4.3 DirectMethod 内 try-catch 标准结构

每个 DirectMethod 内必套 try-catch，catch 中弹错并 return：

```csharp
[DirectMethod]
public void GetStatisticsData()
{
    try
    {
        // 业务逻辑...
    }
    catch (Exception ex)
    {
        X.Msg.Show(new MessageBoxConfig {
            Title = GetGlobalResourceObject("Semi","错误").ToString(),
            Message = ex.Message,
            Icon = MessageBox.Icon.ERROR,
            Buttons = MessageBox.Button.OK
        });
        return;
    }
}
```

> 另一种风格：catch 中 `return ex.Message;`（返回 string 的 DirectMethod），由前端 failure 回调弹错。

## 五、输入校验模式

```csharp
[DirectMethod]
public void SearchData()
{
    // 必填校验
    if (string.IsNullOrWhiteSpace(this.txt_Start_day.RawText.ToString()))
    {
        X.Msg.Alert("提示", "请选择开始日期").Show();
        return;
    }
    if (string.IsNullOrWhiteSpace(this.txt_End_day.RawText.ToString()))
    {
        X.Msg.Alert("提示", "请选择结束日期").Show();
        return;
    }

    // 日期范围校验
    DateTime begin = DateTime.Parse(txt_Start_day.RawText);
    DateTime end   = DateTime.Parse(txt_End_day.RawText);
    if (begin > end)
    {
        X.Msg.Alert("提示", "开始日期不能晚于结束日期").Show();
        return;
    }

    // 查询...
}
```

## 六、参考页面索引

| 页面（相对 WebSite 根） | 涉及要点 |
|------------------------|---------|
| `Plugins/Semi/Report/SemisProductionClass.aspx.cs` | GridModel 列重命名 + 合计行 + 资源化标题 |
| `Plugins/Semi/Produce/SemiProduceAnalyse.aspx.cs` | 资源化列名 + Excel 上传 + 模板下载 |
| `Plugins/Semi/Produce/SemiProduceMaterial.aspx.cs` | MessageBoxConfig 错误提示 + 资源化 |
| `Plugins/Semi/Report/PlanCpkAnalysisDetail.aspx.cs` | Alert 提示 + ExtraParams 传值 |

## 七、关联文档

| 文档 | 关系 |
|------|------|
| `extnet-directmethod-and-data.md` | Session 缓存 + 导出回读参数的模式 |
| `extnet-page-skeleton.md` | 导出按钮在工具栏的位置 |
| `extnet-grid-complete-guide.md` | GridModel.Columns 用于导出列映射 |
| `button-permission.md` | 导出按钮的权限控制 |
| `semi-project-conventions.md` | 资源化是项目强制约定 |

---

## 八、框架坑：导出的 xlsx 文件无法用 FromExcel 导回（NPOI 强转崩溃）

**现象**：`ExcelDownload().ExcelFileDown()` 导出的文件是 **.xlsx**（`ExcelDownload.cs` 第 70 行 `filename + ".xlsx"`），但把该文件拿去 `DataToFile.FromExcel(stream, tableName)` 导入时报：
```text
Unable to cast object of type 'NPOI.XSSF.UserModel.XSSFRow' to type 'NPOI.HSSF.UserModel.HSSFRow'
```
**根因**：`Wongoing.Utility/Excel/DataToExcel.cs` 的 `ReadColumn`/`ReadRow` 里 `(HSSFRow)rows.Current` 硬编码强转 .xls 的行类型——2013 年老代码只支持 HSSF，不兼容 xlsx（XSSFRow）。

**修复选择**（2026-08-26 Molding SpliceParamLimit 采用页面级）：
- ✅ **页面级绕过（推荐，不动共享框架）**：自己写 `ReadExcel(Stream)`——`NPOI.SS.UserModel.WorkbookFactory.Create(stream)` + 全程用 **IRow/ICell 接口**（XSSF/HSSF 通用），逻辑对齐框架（首行作列头、Formula 单元格转 String、空列名补 `EmptyCell_n`）。前提：网站 Bin 里有 NPOI.dll（Utility 的依赖，通常已存在）。Molding 参考实现：`Plugins/Molding/Technology/SpliceParamLimit.aspx.cs` 的 `ReadExcel`。
- ⚙️ 框架级根治：把 DataToExcel.cs 两处 `(HSSFRow)` 改 `(IRow)`（语义等价放宽）——但 Wongoing.Utility 是 `@packages/Frame/Wongoing.Utility.dll` 编译包分发，改源码要重编框架并替换所有项目包+服务器 bin，影响全局，需用户拍板。

**判别口诀**：导出→修改→导入闭环报 XSSFRow/HSSFRow 强转错 = 撞上此坑，换 IRow 接口读取即可。

---

## 九、导入文件功能完整要求清单（2026-08-26 定稿，SpliceParamLimit 为参考实现）

> 一句话：**导出即模板、导出文件改完直接导回、报错定位到行、导完自动刷新**。参考实现：Molding `Plugins/Molding/Technology/SpliceParamLimit.aspx.cs`（UploadParamClick / UploadMaterialClick）。

### 9.1 交互要求

| 要求 | 实现 |
|------|------|
| 不选文件无法点确定 | FileUploadField `AllowBlank="false"` + 确定按钮 `Disabled="true"` + FormPanel `ValidityChange` 联动解禁 |
| 导入中防重复提交 | `<EventMask ShowMask="true" Msg="正在导入..." />` + `Timeout="180000"` |
| 导入成功自动刷新 | Click 的 `Success="关窗; 重置表单; 刷新函数();"`——**别在后续改动中弄丢 Success 属性** |
| 文件格式 | 必须兼容导出文件（.xlsx）——框架 `DataToFile.FromExcel` 有 XSSFRow 强转 bug，用自写 `ReadExcel`（IRow 接口，见第八节） |

### 9.2 数据处理要求

1. **导出列头 = 导入模板列**：导出时列名就用导入要认的中文列头（必填列带 `*` 号），闭环不需要单独模板文件。
2. **列校验（整单拒绝）**：必填列缺失（如"机台编码*"、"规格上限*"）→ 提示"导入文件缺少必填列：xxx"，整单返回。
3. **逐行校验（跳过错行）**：必填空/数值非法/大小关系（USL>LSL）→ `errors.Add("第" + (i + 2) + "行：原因")`（**i+2 含表头**），错行跳过、正常行照常入库，结果里列出前 10 条错误。
4. **文件内重复**：预加载字典判重（`Dictionary` + OrdinalIgnoreCase + Trim），同文件重复键跳过并计数（"文件内重复跳过 N 条"）。
5. **更新语义（upsert）**：预加载全表判重 → 已存在键收集旧 ObjId 批量 DELETE（iterate IN，每批 ≤500 防单语句 2100 参数上限）→ 全部行统一 `BatchInsert`（框架单事务，见 [[wongoing-batch-write-pattern]]）。先删后插天然支持可选字段清空。
6. **写入失败定位行号**：BatchInsert 整批回滚后**逐行重试 Insert**——合法行照常入库，失败行按 Excel 行号报"第N行：写入失败（字段超长或数据冲突）"（行号与数据用并行 List 同步记录）。
7. **结果提示**：`导入完成：新增 X 条，更新 Y 条（，文件内重复跳过 N 条）（；失败 Z 条：<br/>行号明细前10条）`，用 `X.Msg.Alert("导入结果", msg).Show()`。

---


## 十、导出前必须 Copy 副本，否则二次导出是空文件（2026-09-09 Mould SelectChangeAll 实证）

**坑**：项目惯例是 `Select()` 里 `Session["key"] = dataTable`，`btnExport_Click` 里把 **Session 里那个 DataTable 实例**直接改列名（英文列名 → 中文列头）再 `ExcelFileDown`。改列名是就地修改——第一次导出后 Session 里的列已全部变成中文，第二次点导出（未重新查询）时 GridModel 映射 `DataIndex.ToUpper() == ColumnName.ToUpper()` 全部匹配不上 → 所有列被剔除 → **导出一个 0 列空文件**。现有兄弟页（Mould/Select/SelectEquipRepairLog、IceCleanEarlyWarning 等）均存在此隐患。

**修复**：导出 handler 开头一行 `dataTable = dataTable.Copy();` 再做列名映射——副本被改不影响 Session 缓存，重复导出稳定，也不影响后续导出/其它读该 Session 的逻辑。参考实现：Mould `Plugins/Mould/Select/SelectChangeAll.aspx.cs` 的 `btnExport_Click`。

**写新导出页 checklist 增补**：`Session → Copy() → GridModel 列映射 → ExcelFileDown`，四步顺序不要省 Copy。

---


## 十一、动态构建列的页面导出读 ColumnModel 是空集合（2026-09-10 Mould SelectChangeAll 实证）

**现象**：导出文件能正常下载，但里面 0 列 0 内容（空 sheet）。同一写法在静态声明列的页面（SelectEquipRepairLog 等）一直正常。

**根因**：页面的 GridPanel 列是在 `Page_Load` 的 `!X.IsAjaxRequest` 块里**代码动态构建**的（按表结构 extended_properties 生成）。而导出按钮的 `<Click IsUpload="true" OnEvent="btnExport_Click" />` 是 **AJAX 请求**——该请求里 Page_Load 初始化块被跳过，动态列从未加进控件树，`this.grid.ColumnModel.Columns` 是**空集合** → GridModel 列映射循环里所有 DataTable 列都匹配不上（isshow=false）→ 全列剔除 → `ExcelFileDown` 写出 0 列空文件。

**判别口诀**：导出空文件 + 页面列是 code-behind 动态 Add 的（非 aspx 静态声明）= 此坑。aspx 静态声明的列每个请求都会实例化，不受影响。

**修复**（Mould `Plugins/Mould/Select/SelectChangeAll.aspx.cs` 为参考实现）：
1. 首载（!IsAjaxRequest）动态列构建完成后，把 **DataIndex→列头 Text 映射**遍历 ColumnModel 存进 Session；
2. 导出 handler 改读该 Session 缓存做改名/剔除，不碰本请求的 ColumnModel；
3. Session 键**带上区分维度**（如 tableNamePage）：一个 aspx 被多个菜单页共用时，同会话多开标签页会互相覆盖导出数据；
4. 两个列头 Text 同名（如多列 extended property 都叫"时间"）时 `dc.ColumnName = text` 会抛 DuplicateNameException——改名前用 HashSet 判重，冲突时追加序号（"时间"、"时间2"）。

```csharp
//首载缓存（Page_Load !IsAjaxRequest 块末尾，动态列建好后）
var exportColMap = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
foreach (ColumnBase cb in grid.ColumnModel.Columns)
    if (!string.IsNullOrEmpty(cb.DataIndex) && !string.IsNullOrEmpty(cb.Text))
        exportColMap[cb.DataIndex] = cb.Text;
Session["页面名ExportCols_" + 区分键] = exportColMap;

//导出 handler：读缓存映射改名，HashSet 去重防同名列
var usedNames = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
for (int i = 0; i < dataTable.Columns.Count; i++)
{
    string text;
    if (colMap.TryGetValue(dataTable.Columns[i].ColumnName, out text))
    {
        string unique = text; int n = 2;
        while (usedNames.Contains(unique)) unique = text + n++;
        usedNames.Add(unique);
        dataTable.Columns[i].ColumnName = unique;
    }
    else { dataTable.Columns.Remove(dataTable.Columns[i].ColumnName); i--; }
}
```

**导出页 checklist 再增补**：判断该页列是静态声明还是动态构建——动态构建的页面，列头映射必须走 Session 缓存，禁止在导出 handler 里读 ColumnModel。

---


## 十二、分组列丢叶子列 + 真 SQL 分页页导出重跑全量 + 主从页双导出口径（2026-09-10 Mould 三页实证）

### 12.1 两层表头（分组列）页面：平铺遍历 ColumnModel 丢叶子列

**现象**：列声明含分组列（`<ext:Column Text="组名"><Columns><ext:Column DataIndex=.../>...</Columns></ext:Column>`），导出后**组内叶子列全部丢失**（被当"未显示列"剔除）。

**根因**：`foreach (ColumnBase cb in grid.ColumnModel.Columns)` 只遍历**顶层**；分组列的叶子列在组列自己的 `Columns` 集合里，平铺循环拿不到 → 叶子列的 DataIndex 永远匹配不上 → DataTable 对应列被剔除。组列本身无 DataIndex，不会误映射，所以不报错、只 silently 丢列。

**修复**：递归下钻收集（Mould `Select/SelectMaintainLog.aspx.cs` 的 `CollectColumnTexts` 为参考实现）：

```csharp
private static void CollectColumnTexts(System.Collections.IEnumerable columns, Dictionary<string, string> map)
{
    foreach (ColumnBase cb in columns)
    {
        Column col = cb as Column;
        if (col != null && col.Columns.Count > 0)   //分组列：下钻取叶子
        {
            CollectColumnTexts(col.Columns, map);
            continue;
        }
        if (!string.IsNullOrEmpty(cb.DataIndex) && !string.IsNullOrEmpty(cb.Text))
            map[cb.DataIndex] = cb.Text;            //叶子列（含 DateColumn 等）
    }
}
```

> `Column.Columns` 属性一定存在——aspx 里 `<Columns>` 内部标签能解析就证明它是公开持久化属性。叶子列是 DateColumn 等子类时 `as Column` 判空分支自动落到注册逻辑，两种继承结构都安全。导出的 Excel 是单行表头，组名丢失是预期（Excel 表达不了两层表头）。

### 12.2 真 SQL 分页页（PageProxy DirectFn + GetPageDataByReader）：Session 无全量，导出必须重跑

**与既有模式的区别**：[[extnet-pagination-guide]] 第二章是「查询时一次查全量存 Session，翻页内存切片」——导出直接用 Session。但**真 SQL 分页页**（`ext:PageProxy DirectFn="App.direct.GridPanelBindData"`，每页由框架 `GetPageDataByReader` 现查 SQL）Session 里**只有当前页 50 条**，照抄 Session 导出=只导一页。

**导出模式**（Mould `ChangeMouldIntegratedQuery.aspx.cs`、`MouldModifyBill.aspx.cs` 双实证）：
1. 把私有分页方法里的**查询条件字典抽取成共用方法**（如 `GetSelectParams()`），分页与导出共用一份，改条件自动同步；
2. 导出 handler 用 `GetDataTableByStatement(同一条 statement, new Dictionary<string, object> { { "where", GetSelectParams() } })` 重跑全量；
3. **手工包 `{ "where", param }` 的原因**：这类分页语句的条件一律带 `where.` 前缀（`#where.XXX#`），`GetPageDataByReader` 会在框架层把 `pageResult.ParameterObject` 自动包成 where；直查 `GetDataTableByStatement` 没有这层包装，必须手包（页面里既有 DirectMethod 传 `{ "where", new Dictionary{...} }` 的调用即样例）。

> GetPageDataByReader 的 StatementId 默认值等框架陷阱见 [[ibatis-statement-naming-and-getpagedatabyreader-pitfall]]。

### 12.3 主从页（单据+明细）双导出的口径要先问清

Mould 模具改造单三轮回改的教训：**主从页"导出明细"有两种口径，动手前先与用户确认**——
- **全部口径**：当前查询条件下所有主单的明细（需单号列表 IN 批量查，每批 ≤500 防参数上限；明细文件首列必须补"单号"列区分归属）；
- **当前单口径**（用户最终选择）：只导下方正在展示的那张主单（`hd_cur_billid` 取单号，未选中时弹提示），直接复用明细加载语句；文件名带单号（如 `明细_MM20260910xxx.xlsx`）避免逐单导出重名。

按钮位置也听用户口径：主表工具栏放「导出单据」，明细表工具栏（维护按钮旁）放「导出明细」。

### 12.4 导出页 checklist 终版（判型三问）

写导出前先答三问，按型选写法：
1. **列是静态声明还是动态构建？** 动态→列头映射走 Session 缓存（第十一节）；静态→直接读 ColumnModel。
2. **有无分组列（两层表头）？** 有→递归收集叶子列（12.1）。
3. **数据加载是一次性还是服务端分页？** 一次性→Session 存表 + Copy()（第十节）；真分页→按当前条件重跑全量 + 手工 where 包装（12.2）。

另：导出文件名按**用户菜单名**确认，页面 `<title>` 可能与菜单名不一致（SelectMaintainLog title=保养记录查询、菜单=机台点检记录）。

## 十三、导出超 65536 行报 Invalid row number（.xls 单 Sheet 上限 + Mesnac.Utility.dll 版本漂移）（2026-09-17 Batch BatchTracing 实证）

### 13.1 症状
导出数据量大时报 `Invalid row number (65536) outside allowable range (0..65535)`，导出中断。出处：Batch `Plugins/Batch/BatchTracing/BatchTracing.aspx.cs` 的 `btnExportSubmit_Click`（普通导出口）。

### 13.2 根因：HSSF 上限 × DLL 版本漂移
- 报错数字 `(0..65535)` 是 NPOI **HSSFWorkbook（.xls）单 Sheet 行硬上限**；XSSF(.xlsx) 上限是 1048576，报错数字不同——看数字即可判格式。
- `Mesnac.Utility.Excel.ExcelDownload.ExcelFileDown(DataTable, string)` → `DataToFile.ToExcel`：**新版按 60000 行自动分 Sheet**，老版不分（单 Sheet 写满即炸）。
- **版本漂移实证**（排查此类问题第一步，先比文件日期/大小）：
  | 位置 | 日期 | 大小 | 行为（本地 PowerShell 实测） |
  |---|---|---|---|
  | Batch 网站 Bin（本地开发） | 2024-11-18 | 26KB | HSSF(.xls) + 60000 行分 Sheet，7 万行可正常导出 2 Sheet |
  | Main/Frame 源码及编译产物 | 2025-06-10 | 43KB | XSSF(.xlsx) + 60000 行分 Sheet，但 `FileDown` 文件名仍拼 `.xls` 后缀 |
  | **生产部署** | 未知 | — | 报 65536 错 → 推断比 Bin 本地版更老、无分 Sheet 逻辑 |

### 13.3 解法：页面级分块（不依赖部署的 DLL 版本）
超 5 万行时把 DataTable 按 50000 行 `Clone()` 分块塞进 `DataSet`（每块 `TableName = "Sheet" + N`），改调 `ExcelFileDown(DataSet, string)` 重载：

```csharp
//.xls单Sheet上限65536行，数据量大时按5万行分块导出到多个Sheet，避免Invalid row number (65536)报错
const int sheetRows = 50000;
if (data.Rows.Count <= sheetRows)
{
    new Mesnac.Utility.Excel.ExcelDownload().ExcelFileDown(data, "批次信息");
}
else
{
    DataSet ds = new DataSet();
    for (int i = 0; i < data.Rows.Count; i += sheetRows)
    {
        DataTable dt = data.Clone();
        dt.TableName = "Sheet" + (ds.Tables.Count + 1);
        for (int j = i; j < i + sheetRows && j < data.Rows.Count; j++)
        {
            dt.Rows.Add(data.Rows[j].ItemArray);
        }
        ds.Tables.Add(dt);
    }
    new Mesnac.Utility.Excel.ExcelDownload().ExcelFileDown(ds, "批次信息");
}
```

依据（旧 DLL 本地实测）：`ToExcel(DataSet)` **每个 DataTable 一个 Sheet**（2×40000 行 → T0/T1 两个 Sheet）；`ExcelFileDown(DataSet, string)` 重载自 2013 年初版就存在，签名稳定。分块后单 Sheet 最大 50001 行（含表头）< 65536，任何 DLL 版本（HSSF 无分 Sheet / HSSF 分 Sheet / XSSF 分 Sheet）下都安全。
**模板导出不受此限**：`ExportByExcelTemplate` 是固定单元格填充（`Dictionary<int[], object>` 定位），行数有界。

### 13.4 验证方法（不碰数据库、不依赖 IIS）
PowerShell `LoadFrom` 直接加载网站 Bin 里的 `Mesnac.Utility.dll` + NPOI 四件套，构造大 DataTable 调 `DataToFile.ToExcel`（公共方法）落盘，再用 `WorkbookFactory.Create` 回读 Sheet 数/lastRow/表头：
- 70000 行 DataTable → 2 Sheet（60001+9999，证明本地 DLL 已分 Sheet）
- DataSet 2×40000 → 2 Sheet（证明 DataSet 重载每表一 Sheet）
- 130000 行按页面分块逻辑模拟 → 3 Sheet（50000/50000/30000 lastRow），中文表头完好
反射列方法确认重载存在：`GetMethod` 传 `@([DataSet],[string])` 会因 PS 类型转换报错出假阴性，应用 `GetMethods() | Where Name -like '*FileDown*'` 列举。