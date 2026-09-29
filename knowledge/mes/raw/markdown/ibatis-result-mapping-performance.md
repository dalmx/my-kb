---
title: iBATIS Result Mapping 性能优化（ADO.NET 直连 + 序列化）
category: 技术-.NET
module: iBATIS
factory: 通用
tags: [iBATIS, 性能优化, ADO.NET, 结果映射, 报表慢, 13秒, 序列化, ResultMapping]
updated: 2026-08-29
status: active
---
# iBATIS Result Mapping 性能优化（ADO.NET 直连 + 序列化）

> 报表 8812 行×102 列耗时 13.49s（SSMS 仅 0.5-2s）的定位与修复全过程：分层实测（前端 Rendering 0.9% / Newtonsoft 序列化 2% / SQL 93% → 逐 JOIN 累加仅 392ms）确诊瓶颈在 iBatis `resultClass="row"` 逐行反射映射（程序比 SQL 本体慢 38 倍）；解法三件套 = ADO.NET DataReader+DataTable.Load 直连（连接串取自 SessionFactory 复用解密逻辑）+ Newtonsoft 序列化替代 Ext.NET DataBind（~5000ms→~280ms）+ Web.config 显式压缩 application/json；附四步诊断方法论、反直觉教训表与"列≥30+行≥5000 才考虑直连"的适用判据，最终 13.49s→4.08s。

## 一、问题现象
- 报表页查询大数据量（8812 行 × 102 列）耗时 **13.49s**
- SQL Server Management Studio (SSMS) 里手动执行同一存储过程只要 **0.5-2s**
- 性能差异巨大，但表面看 SQL "没问题"
---

## 二、诊断过程（层层剥洋葱）

### 第 1 层：前端 vs 后端

F12 Performance 面板：Idle（等待）占 90%，Rendering 仅 0.9%。
→ **瓶颈在后端，不是前端渲染**（推翻了"102列渲染慢"的猜测）。

### 第 2 层：传输 vs 序列化

加 Web.config Gzip 压缩后，响应从 5MB → 875KB，但总耗时仅小幅下降。
→ **传输不是主要瓶颈**，压缩省的是网络时间，序列化发生在压缩之前。

### 第 3 层：序列化 vs SQL（关键转折）

后端 `Stopwatch` 分阶段计时（通过返回的 JSON `_timing` 字段暴露）：

| 阶段 | 耗时 | 占比 |
|---|---|---|
| SQL（QueryData） | 12908 ms | 93% |
| Copy + 改名 | 150 ms | 1% |
| Newtonsoft 序列化 | 279 ms | 2% |

→ **序列化只占 2%（已用 Newtonsoft 优化）！真正瓶颈是 SQL 调用（iBatis）。**

### 第 4 层：SQL 本身 vs iBatis 调用（真相）

**逐个 JOIN 累加计时**（`DiagnoseJoinCost.sql`，每个 JOIN 测一次）：

```text
【0】主表 FQB_UFCHECK_INFO: 16 ms, 行数=8812
【1-7】所有 LEFT JOIN 累加: 399 ms
【8-9】两个 outer apply: 392 ms
```

**全部 9 个 JOIN + outer apply 加起来才 392ms！**

但程序里同一段查询要 15081ms。**差 38 倍。**

→ **瓶颈 100% 在 iBatis 数据访问层**，最可能是 `resultClass="row"` 的逐行结果映射。

### 第 5 层：ADO.NET 验证

绕过 iBatis，用 `SqlCommand + DataReader + DataTable.Load` 直连存储过程：

| 调用方式 | 耗时 |
|---|---|
| iBatis `GetDataSetByStatement` | 15081 ms |
| ADO.NET 直连 | 3615 ms |

→ **确诊：iBatis 结果映射是瓶颈，ADO.NET 直连快 4 倍。**

---

## 三、最终优化方案

### 方案 1：ADO.NET 直连（绕过 iBatis 结果映射）

```csharp
private DataTable QueryDataByAdoNet()
{
    // 从 iBatis SessionFactory 获取已解密连接串，避免硬编码密码
    string connStr = new SsbDicItemManager().DbHelper.SessionFactory.DataSource.ConnectionString;
    string procName = "ProcReportTyreUniformityCommonUF";

    using (SqlConnection conn = new SqlConnection(connStr))
    using (SqlCommand cmd = new SqlCommand(procName, conn))
    {
        cmd.CommandType = CommandType.StoredProcedure;
        cmd.CommandTimeout = 60;

        cmd.Parameters.AddWithValue("@START_DAY", txt_Start_day.RawText ?? "");
        // ... 其余参数

        // DataReader + Load 比 SqlDataAdapter.Fill 更轻量
        DataTable dt = new DataTable();
        conn.Open();
        using (SqlDataReader reader = cmd.ExecuteReader())
        {
            dt.Load(reader);
        }
        return dt.Rows.Count > 0 ? dt : null;
    }
}
```

**关键点**：
- **连接串**：从 iBatis 已初始化的 `SessionFactory` 获取，复用框架的解密逻辑，无明文密码
- **`DataReader + Load`** 优于 `SqlDataAdapter.Fill`（Fill 内部多一层封装）
- **`CommandType.StoredProcedure`**：直接调存储过程，不走 iBatis 的 `exec proc #p1#, ...` 拼接
- **只对大数据量查询改用 ADO.NET**；下拉框等小数据查询仍走 iBatis（无性能差异）

### 方案 2：Newtonsoft 序列化替代 Ext.NET DataBind

```csharp
[DirectMethod]
public string SearchData()
{
    DataTable dt = QueryDataByAdoNet();
    Session["..."] = dt;

    // loadData 路径下 ServerMapping 不生效，副本上改名 ID→CheckID
    DataTable forJson = dt.Copy();
    if (forJson.Columns.Contains("ID") && !forJson.Columns.Contains("CheckID"))
        forJson.Columns["ID"].ColumnName = "CheckID";

    string json = JsonConvert.SerializeObject(forJson, Formatting.None);
    return "{\"data\":" + json + ",\"total\":" + dt.Rows.Count + "}";
}
```

前端用 `store.loadData(obj.data)` 装载。

**对比**：
| 方式 | 1万行×102列序列化 |
|---|---|
| Ext.NET `DataBind`（JavaScriptSerializer） | ~5000 ms |
| Newtonsoft `JsonConvert` | ~280 ms |

### 方案 3：Gzip 压缩（Web.config）

```xml
<urlCompression doDynamicCompression="true" doStaticCompression="true"/>
<httpCompression>
  <dynamicTypes>
    <add mimeType="application/json" enabled="true"/>
    <add mimeType="application/json; charset=utf-8" enabled="true"/>
    <!-- 其它文本类型 -->
  </dynamicTypes>
</httpCompression>
```

- IIS / IIS Express **默认不压缩 `application/json`**，必须显式声明
- 只压缩文本类，不压缩图片/PDF（避免白耗 CPU）
- **IIS 服务器需开启 Windows 功能**："动态内容压缩"

---

## 四、优化效果对比

| 阶段 | 8812行耗时 |
|---|---|
| 初始（Ext.NET DataBind + 无 Gzip + iBatis） | 13.49 s |
| + Gzip 压缩 | ~11 s |
| + Newtonsoft 序列化 | 2.65 s（小数据量） |
| + ADO.NET 直连（大数据量） | **4.08 s** |

剩余 ~3.6s 是 8812行×102列跨网络传输（远程数据库），受带宽限制，代码层面无法再降。

---

## 五、诊断方法论（最重要的部分）

### 方法 1：后端 Stopwatch 分阶段计时

通过返回 JSON 的 `_timing` 字段暴露后端各阶段耗时，前端弹窗显示：
```csharp
var sw = Stopwatch.StartNew();
DataTable dt = QueryData();
long t1 = sw.ElapsedMilliseconds;   // SQL
// ... 序列化 ...
return "{...\"_timing\":{\"sql\":" + t1 + ",\"serialize\":...}}";
```
> 临时加，测完删。比前端 Performance 面板精确。

### 方法 2：逐个 JOIN 累加计时（定位关联瓶颈）

把存储过程的每个 JOIN 拆成独立查询，逐步累加测耗时，看哪步暴涨：
```sql
-- 0: 只查主表
-- 1: +JOIN表A
-- 2: +JOIN表B
-- ...
```
本次用这招证明**所有 JOIN 加起来才 392ms**，排除"SQL 关联慢"的假设。

### 方法 3：SSMS vs 程序对比

同一段 SQL、相同参数，分别在 SSMS 和程序里跑：
- **SSMS 快、程序慢** → 数据访问层（iBatis/ORM）开销
- **SSMS 也慢** → SQL 本身问题
- ⚠️ 必须用**相同数据量**对比（不同日期数据量不同会误判）

### 方法 4：ADO.NET 直连对比

同样的存储过程，iBatis 调用 vs ADO.NET 调用，对比耗时。差值就是 ORM 开销。

---

## 六、反直觉教训

本次优化中，**对瓶颈的判断几乎每一次都是错的**，全靠实测数据纠正：

| 直觉判断 | 实测真相 |
|---|---|
| 102列渲染慢 | Rendering 仅 0.9%，不是瓶颈 |
| 传输慢（30MB JSON） | 实际 5MB，Gzip 后 875KB |
| 序列化是大头 | Newtonsoft 序列化仅 280ms（2%） |
| outer apply 逐行慢，CTE 能优化 | CTE 改完反而更慢（15081ms），outer apply 不是瓶颈 |
| 缺索引导致扫描计数高 | 索引都有，扫描次数高是 iBatis 多次调用，非缺索引 |
| parameter sniffing | 加 RECOMPILE 无改善，不是执行计划问题 |
| **SQL 是瓶颈** | **SQL 本体 392ms，iBatis 结果映射才是真瓶颈** |

**一句话：性能优化的直觉几乎总是错的。每一步都必须用 Stopwatch / STATISTICS IO / 逐 JOIN 计时等手段实测，不要凭经验猜。**

---

## 七、iBatis/MyBatis 结果映射慢的根因

iBatis 的 `resultClass="row"`（或对象映射）对每行结果做反射/字典映射：
- **102 列 × 8812 行 = 89万次列映射**
- 每次映射涉及类型判断、DBNull 处理、属性设置
- 宽表（列数多）场景下，映射开销随列数线性放大

ADO.NET 的 `DataTable.Load` 用 SQL Server 原生的 TDS 反序列化，跳过逐列反射，快数倍。

**适用判断**：列数 ≥ 30 + 行数 ≥ 5000 的查询，建议考虑 ADO.NET 直连。

---

## 八、部署清单

1. **数据库**：生产库执行存储过程（本例加了 `OPTION(RECOMPILE)`）
2. **Windows 功能**：IIS 开启"动态内容压缩"
3. **Web.config**：手动加 Gzip 配置段（勿直接覆盖生产 Web.config）
4. **代码**：重新编译，部署 DLL + aspx
5. **验证**：连接串确认指向**生产库**（`SessionFactory.DataSource`）

---

## 九、关联文档

| 文档 | 关系 |
|------|------|
| `extnet-pagination-guide.md` | 前端 loadData 与服务端分页方案：本文的 ADO.NET 优化建立在其上；当"不能分页"时，用本文的直连+序列化优化 |


---

## 十、一句话总结

宽表大数据量报表慢，**先测 SQL 本体（SSMS/逐JOIN），再测 ORM 调用**——差值往往就是 ORM 结果映射。
解法：**ADO.NET 直连（绕过 ORM 映射）+ Newtonsoft 序列化（替代 Ext.NET DataBind）+ Gzip（省传输）**。
但每一步前必须实测，因为瓶颈判断几乎总是错的。
