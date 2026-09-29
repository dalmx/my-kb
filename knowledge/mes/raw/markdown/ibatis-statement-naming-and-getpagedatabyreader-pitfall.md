---
title: iBATIS Statement 命名约定与 GetPageDataByReader 框架专用陷阱
category: 技术-.NET
module: iBATIS
factory: 通用
tags: [分页, GetPageDataByReader, GetSqlPageData, RecordCount, PageResult, iBATIS, 踩坑, Mix]
status: active
updated: 2026-08-29
---
# iBATIS Statement 命名约定与 GetPageDataByReader 框架专用陷阱

> 沉淀自 Molding 项目「生胎出入库记录」报表开发过程中的踩坑发现。**适用于所有子系统**（Molding / Quality / Semi / Curing / Batch / Equip / Mix / Mould / Storage / TechRecipe / Main 等）。

## 一、核心规律（一句话）

**报表查询的 statement id 必须用 `XxxQuery@Entity` 或 `SelectXxxByYyy@Entity` 这种带 `@Mapper名` 后缀的自定义 id，不能直接用 `GetPageDataByReader`！** `GetPageDataByReader` 是框架专用 id，有特殊语义。

## 二、两类 statement id 的本质区别

### 2.1 框架专用 `GetPageDataByReader`（⚠️ 别误用）

**用途**：`BaseManager<T>` / `BaseService<T>` 基类提供的**单表 CRUD 分页查询**方法，走服务端 ROW_NUMBER 分页。

**XML 写法**（BasicMapper 标配，自动生成的）：
```xml
<select id="GetPageDataByReader" parameterClass="map" resultClass="Row">
  <include refid="includeSelect"/>   <!-- SELECT * FROM TABLE with(nolock) -->
  <include refid="includeWhere"/>     <!-- WHERE 字段名 = #where.字段# -->
  <include refid="includeOrderString"/>
</select>
```

**调用方式**：**只能**通过 `manager.GetPageDataByReader(pageResult)` 方法调用，**不能**用 `GetDataSetByStatement("GetPageDataByReader@XXX", ...)`！

```csharp
// ✅ 正确（框架分页查询）
PageResult pr = new PageResult();
pr.StatementId = "GetStoreTyreInfo@BpmProduction";  // 也可指定自定义 id
pr.ParameterObject = pageParams;
pr.OrderString = "MATERIAL_CODE ASC";
pr.PageIndex = prms.Page;
pr.PageSize = prms.Limit;
PageResult result = manager.GetPageDataByReader(pr);

// ❌ 错误（会报 The DataMapper does not contain a MappedStatement）
DataSet ds = manager.GetDataSetByStatement("GetPageDataByReader@BpmProduction", param);
```

**参数约定**：`<include refid="includeWhere"/>` 里的字段都是 `#where.字段#` 前缀（框架把 `ParameterObject` 包成 `where`）。

### 2.2 自定义查询 `XxxQuery@Entity`（✅ 报表常用）

**用途**：报表查询、多表 JOIN、聚合统计等所有非标准 CRUD 场景。

**XML 写法**（BusinessMapper，手写的）：
```xml
<select id="SelectArtStoreLocationLog@BpmMoldingArtAndStoreLocationLog"
        parameterClass="map" resultClass="Row">
  SELECT A.*, ISNULL(U.REAL_NAME, A.RECORD_USER_ID) AS RECORD_USER_NAME
  FROM BPM_XXX A WITH(NOLOCK)
  LEFT JOIN SSB_USER U WITH(NOLOCK) ON U.WORK_BARCODE = A.RECORD_USER_ID
  <dynamic prepend="WHERE">
    <isNotNull property="BeginDate" prepend="AND"><![CDATA[A.RECORD_TIME >= #BeginDate#]]></isNotNull>
    <isNotNull property="EndDate" prepend="AND"><![CDATA[A.RECORD_TIME < #EndDate#]]></isNotNull>
  </dynamic>
  ORDER BY A.RECORD_TIME DESC
</select>
```

**调用方式**：通过 `GetDataSetByStatement` / `GetDataTableByStatement`：

```csharp
var param = new Dictionary<string, object>()
{
    { "BeginDate", "2026-07-01 00:00:00" },
    { "EndDate",   "2026-07-21 00:00:00" }
};
DataSet ds = manager.GetDataSetByStatement(
    "SelectArtStoreLocationLog@BpmMoldingArtAndStoreLocationLog", param);
// 或
DataTable dt = manager.GetDataTableByStatement(
    "SelectArtStoreLocationLog@BpmMoldingArtAndStoreLocationLog", param);
```

**参数约定**：**直接用 `#字段#`，不带 `where.` 前缀**（因为没有框架的 `where` 包装）。

## 三、Statement id 命名规则（关键）

格式：**`<自定义名>@<Mapper文件名去掉.xml>`**

| Mapper 文件 | namespace | statement id 模板 |
|------|------|------|
| `BusinessMapper/BpmProduction.xml` | `Wongoing.Molding.Mapper.BusinessMapper.BpmProduction` | `SelectXxx@BpmProduction` |
| `BusinessMapper/BpmMoldingArtAndStoreLocationLog.xml` | `Wongoing.Molding.Mapper.BusinessMapper.BpmMoldingArtAndStoreLocationLog` | `SelectXxx@BpmMoldingArtAndStoreLocationLog` |
| `BusinessMapper/HppSemisProduction.xml` | `Wongoing.<X>.Mapper.BusinessMapper.HppSemisProduction` | `XxxQuery@HppSemisProduction` |

`@` 后面的就是 **namespace 末尾段**（即 Mapper 文件名不含扩展名）。`@` 前面的命名风格项目间略有差异：
- Molding / Main：`SelectXxx@Entity`、`GetXxx@Entity`（动词开头）
- Batch / Curing：`XxxQuery@Entity`（Query 结尾）
- **同文件内保持一致即可**，照抄同 Mapper 文件已有 statement 的风格。

## 四、两种调用方式 vs 两种 statement id 的对应矩阵

|  | `GetPageDataByReader` id | `Xxx@Entity` 自定义 id |
|---|---|---|
| **`manager.GetPageDataByReader(pr)`** | ✅ BasicMapper 单表 CRUD 分页 | ✅ 也可指定自定义 id（`pr.StatementId = "Xxx@Entity"`） |
| **`manager.GetDataSetByStatement("...", param)`** | ❌ **找不到 statement 报错** | ✅ 报表查询主力 |
| **`manager.GetDataTableByStatement("...", param)`** | ❌ 同上 | ✅ 同上 |

## 五、典型踩坑：误用 GetPageDataByReader 做 BI 报表

### 5.1 错误症状

```text
MyBatis.DataMapper.Exceptions.DataMapperException: The DataMapper does not contain
a MappedStatement named
Wongoing.Molding.Mapper.BusinessMapper.BpmMoldingArtAndStoreLocationLog.GetPageDataByReader@BpmMoldingArtAndStoreLocationLog
```

注意错误信息里的 statement 名是 `namespace + id`：
- namespace 是 BusinessMapper 的（说明查的是 BusinessMapper XML）
- id 是 `GetPageDataByReader@BpmMoldingArtAndStoreLocationLog`
- **但 iBATIS 的 statement 注册名就是 XML 里的 `<select id="...">` 原值**，不会自动加 `@Mapper名` 拼接

### 5.2 错误根因

开发者（看了 BasicMapper XML 里的 `<select id="GetPageDataByReader">`）在 BusinessMapper 里也定义了同名 id：

```xml
<!-- BusinessMapper/MyReport.xml（❌ 错误写法） -->
<select id="GetPageDataByReader" parameterClass="map" resultClass="Row">
  SELECT ... FROM ... WHERE ...
</select>
```

然后在 .aspx.cs 里调用：
```csharp
manager.GetDataSetByStatement("GetPageDataByReader@MyReport", param);
// ❌ 报错：找不到 statement
```

**为什么找不到**：iBATIS 按 `<select id="...">` 的原值注册 statement。如果 XML 里写 `id="GetPageDataByReader"`，那注册名就是 `GetPageDataByReader`（不带 `@Mapper名`）。`@Mapper名` 是**项目命名约定**，必须**在 XML 里就写完整**：

```xml
<!-- ✅ 正确写法：id 里就带 @Mapper名 -->
<select id="SelectMyReport@MyReport" parameterClass="map" resultClass="Row">
```

### 5.3 正确修法（三步）

1. **BusinessMapper XML**：把 `<select id="GetPageDataByReader">` 改成 `<select id="SelectXxx@MapperName">`
2. **`.aspx.cs` 查询**：调用 id 改成同样的 `SelectXxx@MapperName`
3. **重新编译 Mapper 工程**（XML 是 EmbeddedResource）+ 重启 IIS 应用池

## 六、参考报表与对应 statement id（Molding 项目）

| 报表 | Manager | Statement id |
|------|---------|-------------|
| `Storage/MoldStorageInfo.aspx` | `BpmProductionManager` | `GetStoreTyreInfo@BpmProduction`（PageResult 分页） |
| `Storage/MoldStorageBarcode.aspx` | `BpmProductionManager` | `SelectMoldStorageBarcode@BpmProduction`（DataTable） |
| `Report/MoldCheckStockQuery.aspx` | `BpmProductionManager` | `SelectCheckInfoMain@BpmProduction` + `SelectCheckInfoDetail@BpmProduction` |
| `Storage/MoldInventoryTrend.aspx` | `BpmProductionManager` | `SelectInventoryTrend@BpmProduction` |

**规律**：所有自定义报表查询都是 `Xxx@BpmProduction` 格式，**没有一个用 `GetPageDataByReader@XXX`**。

## 七、避坑速查

| 想做的事 | 正确做法 |
|------|------|
| 写一个报表查询（多表 JOIN、聚合） | BusinessMapper XML 里 `<select id="Xxx@Entity">` + `.cs` 里 `GetDataSetByStatement("Xxx@Entity", param)` |
| 单表 CRUD 分页（`PageResult`） | 用框架自带的 BasicMapper `<select id="GetPageDataByReader">` + `manager.GetPageDataByReader(pr)` |
| 想 override 框架分页的 SQL | 在 BusinessMapper 加 `<select id="Xxx@Entity">` + `pr.StatementId = "Xxx@Entity"`，仍用 `GetPageDataByReader(pr)` 调用 |
| XML 里 `where.字段#` 还是 `#字段#`？ | 走 `PageResult` 用 `#where.字段#`；走 `GetDataSetByStatement` 用 `#字段#` |

## 八、相关条目

- `consumption-output-report.md` —— Batch 项目 iBatis 命名约定（`XxxQuery@Entity`）
- `extnet-GetDataTableByStatement-ImageCommand.md`—— 明确「区别于 `GetPageDataByReader`」
- `extnet-directmethod-and-data.md` —— `GetDataTableByStatement` 用法
- `extnet-pagination-guide.md` —— `PageResult` / `GetPageDataByReader` 完整分页方案
- `extnet-pagination-guide.md` —— `getPageDataByReader` 框架源码（`stmtId = pageResult.StatementId ?? "GetPageDataByReader"`）

---

## 九、补充：GetSqlPageData vs GetPageDataByReader 的关键区别（RecordCount 列陷阱）

**踩坑场景**（2026-07 Mix 项目，技术处置操作日志报表 TechDealLogView）：
照搬 `RubberTechDeal.aspx.cs` 用 `GetSqlPageData(PageResult)` + 普通 `SELECT ... FROM ... LEFT JOIN ...` 的 statement，运行时报：

```text
System.ArgumentException: Column 'RecordCount' does not belong to table ...
   at Wongoing.DbAccess.BaseService`1.getSqlPageData(PageResult pageResult)
```

### 根因（BaseService.cs 第 1173-1202 行源码）

两种分页方法对 SQL 的要求**完全不同**：

| 方法 | 分页方式 | SQL 要求 | 适用场景 |
|------|---------|---------|---------|
| **`GetPageDataByReader`** | 内存分页（DataReader 读全量→C# 切片） | 普通 `SELECT` 即可，**无特殊字段要求** | **推荐默认**，与 PlanLogView 同模式 |
| **`GetSqlPageData`** | SQL 端分页 | **结果集第一行第一列必须含 `RecordCount` 字段**（特殊协议） | 性能敏感的大表，需手写 `ROW_NUMBER() OVER` + 子查询返回总数的复杂 SQL |

`GetSqlPageData` 源码关键行：
```csharp
DataSet result = this.GetDataSetByStatement(stmtId, param);
pageResult.RecordCount = result.Tables[0].Rows.Count > 0 
    ? Convert.ToInt32(result.Tables[0].Rows[0]["RecordCount"])  // ← 没有 RecordCount 列就崩
    : 0;
```

### 正确用法对比

**❌ 错误（普通 SELECT 配 GetSqlPageData → 崩）：**
```csharp
pageResult.StatementId = "GetXxxPageData";  // 普通 SELECT
pageResult = new XxxManager("MENS").GetSqlPageData(pageResult);  // 找 RecordCount 列报错
```

**✅ 正确 A：内存分页（推荐，SQL 不动）：**
```csharp
pageResult.StatementId = "GetXxxPageData";  // 普通 SELECT 即可
pageResult = new XxxManager("MENS").GetPageDataByReader(pageResult);
```

**✅ 正确 B：SQL 端分页（性能优化时用，需改 SQL）：**
SQL 必须返回两个结果集或带 `RecordCount` 字段，例如：
```sql
SELECT COUNT(1) AS RecordCount FROM ... WHERE ...
-- 然后用 ROW_NUMBER() OVER (ORDER BY ...) 做真分页
```

### 重要：StatementId 默认值陷阱

`GetPageDataByReader` 在 `pageResult.StatementId` 为空时**默认找名为 `GetPageDataByReader` 的 statement**（BaseService.cs line 1091-1095）：

```csharp
string stmtId = pageResult.StatementId;
if (string.IsNullOrWhiteSpace(stmtId))
    stmtId = "GetPageDataByReader";  // ← 默认值
```

→ **新增了自定义 statement（如 `GetTechDealLogPageData`）时，必须显式设置 `pageResult.StatementId`，否则会走表里原始的 `SELECT *` 版本**（绕过规范的 SQL、JOIN、过滤条件）。PlanLogView 没显式设 StatementId 是因为它的新 statement id 就叫 `GetPageDataByReader`（与默认值同名）；新建报表若 statement 名自定义则必须显式传。

### 性能权衡

- `GetPageDataByReader`（内存分页）：会按时间范围查出全部匹配行，再 C# 端切片。对**带时间范围收窄的日志/查询表**完全够用（PlanLogView 同模式）。
- `GetSqlPageData`（SQL 分页）：每次只查当前页，适合单表千万级数据。但 SQL 复杂度高、易踩坑，**非必要不用**。

### 参考实现

- 同库同模式范例：`Plugins/Mix/Plan/PlanLogView.aspx(.cs)` — 用 `GetPageDataByReader` + 自定义 statement + 时间范围收窄，标准日志查询报表
- 本次落地：`Plugins/Mix/Plan/TechDealLogView.aspx(.cs)` — 技术处置操作日志查询，先踩坑用 `GetSqlPageData` 报错，改回 `GetPageDataByReader` 修复