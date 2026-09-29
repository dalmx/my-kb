---
title: Wongoing框架批量写库模式（BatchInsert与自定义批量UPDATE）
category: 技术-.NET
module: 通用
factory: 通用
tags: [BatchInsert, 批量更新, iBATIS, iterate, SQL Server, 参数上限, 2100参数, 文本替换, IN列表, 导入查询, Wongoing.DbAccess, 性能优化]
updated: 2026-09-23
status: active
---
# Wongoing框架批量写库模式（BatchInsert与自定义批量UPDATE）

> 框架层 BaseManager/BaseService 只提供 BatchInsert（单事务循环Insert一次提交），没有 BatchUpdate；批量更新需自定义「VALUES构造表+iterate」语句，且必须分批（SQL Server 单语句参数上限约2100）。

> 症状速查：报「传入的请求具有过多的参数。该服务器支持最多2100个参数」= 单语句 IN 列表 iterate 展开参数超限，解法见第五节。

## 一、框架已有的 BatchInsert

- 位置：`Main/Frame/Wongoing.DbAccess/BaseService.cs` 的 `public int BatchInsert(List<T> lst)`
- 实现：单 ISession 单 ITransaction 内 foreach 执行标准 Insert 语句，最后 `transaction.Complete()` 一次提交
- 特点：整批原子（任一行失败整批回滚）；列处理与单条 Insert 完全一致（动态非空列）；无需考虑参数上限、无需分块
- 用法：`Manager.BatchInsert(list);`
- 注意：框架**没有** BatchUpdate，不要照 BatchInsert 名去找

## 二、自定义批量UPDATE（VALUES构造表模式）

```xml
<update id="XxxBatchUpdate" parameterClass="map">
  UPDATE t SET t.A = s.A, t.B = s.B
  FROM XXX_TABLE t
  INNER JOIN (VALUES
    <iterate property="list" conjunction=",">
    (#list[].Objid#, #list[].A#, #list[].B#)
    </iterate>
  ) s (OBJID, A, B)
  ON t.OBJID = s.OBJID
</update>
```

调用方式：

```csharp
for (int i = 0; i < lst.Count; i += 50)
{
    Manager.UpdateByStatement("XxxBatchUpdate",
        new Dictionary<string, object> { { "list", lst.Skip(i).Take(50).ToList() } });
}
```

## 三、必须分批：每批最多50行

SQL Server 单语句参数上限约 2100；每行 27 个参数时 50 行/批 = 1350 参数，留足余量。逐批循环执行即可，不必单语句装下全部。

## 四、批量IN查询回查（可分批场景）

```xml
<select id="GetByCodes" parameterClass="map" resultClass="Row">
  SELECT OBJID, CODE FROM XXX_TABLE WHERE CODE IN
  <iterate property="list" open="(" close=")" conjunction=",">#list[]#</iterate>
</select>
```

IN 值数量大且**查询结果可在 C# 内存合并**时分批（如每批500个值）逐批查再合并（先例：Quality ReportTyreUniformityCommon 的 ApplyOere 每批1000）。

## 五、单语句分页场景：iterate 撞 2100 时改 $文本替换$（不分批）

**判定标准**：查询走 `GetPageDataByReader(pageResult)`（StatementId 单语句，count+分页均由框架从同一条语句派生）时，C# 分批会破坏分页语义（总数/页码对不上）——此时不能分批，把 IN 列表从「iterate 每元素一参数」改为「**C# 拼字面值串 + Mapper `$文本替换$`**」，参数数固定（仅剩其余 isNotEmpty 条件十来个），IN 三五千个值也不超限，SQL 文本几万字符远低于 batch 上限。

Mapper 写法（嵌套路径 `$where.X$` 先例：Molding `CbmSize.xml:72`、`Interface.xml:130`；顶层属性先例：Quality `FqbBalanceInfo.xml` 的 `$TyreNos$`）：

```xml
<isNotEmpty property="where.TYRE_NO_LIST" prepend="and">
    TT2.TYRE_NO in ($where.TYRE_NO_LIST$)
</isNotEmpty>
```

C# 侧（**必须**把 List 转成拼好转义的字符串——$替换$ 对 List 会 ToString 成类型名垃圾）：

```csharp
private static string ToSqlInList(IEnumerable<string> values)
{
    return string.Join(",", values.Distinct().Select(v => "'" + v.Replace("'", "''") + "'"));
}
// param.Add("TYRE_NO_LIST", ToSqlInList(importtyres));
```

- `Replace("'","''")` 防注入必做；`Distinct()` 去重缩短 SQL（IN 语义无差异）
- isNotNull 改 isNotEmpty（字符串空串时不拼条件）
- **同语句的全部传参点必须一起改**（同一参数既是 List 又是 string 会类型不一致）：如 TyreLockAndUnLock 的 `SelectTyreList@BpmProduction` 有 6 处传 TYRE_NO_LIST/GREEN_TYRE_NO_LIST（导入列表2处+单胎号起止4处），全部统一走 ToSqlInList
- 代价：IN 字面值不参数化，计划缓存碎片化；胎号精确匹配场景可接受
- 实证：Molding `TyreLockAndUnLock`（胎号锁定/解锁页）条码导入查询 2026-09-23 改造，导入 3000+ 条码不再报 2100 错。该页冻结/解冻操作语句（Freeze/Unfreeze 系）已有 300 条/批分批保护无需改
- 部署：Mapper xml 是嵌入资源须重编 Mapper dll 拷 Bin；WebSite 的 aspx.cs 拷过去 IIS 动态编译生效

## 六、关键注意

- **全字段覆盖**：批量 UPDATE 把 Excel 空单元格也写成 NULL/空串（清空库中字段），与动态 Update 的「只更新非空字段」语义不同，使用前确认业务是否接受；不接受则用 BatchInsert 类似思路在事务内循环 Update
- mapper XML 是**嵌入资源**，改/加语句必须重编对应子系统 Mapper.dll 再部署
- 编译环境：用 `D:\VSIDE\MSBuild\Current\Bin\MSBuild.exe` 且必须传 `//p:SolutionDir=...（以\\结尾）`，否则后置 XCOPY 报 MSB3073；`C:\Windows\Microsoft.NET\Framework\v4.0.30319\MSBuild.exe` 是 C#5 编译器，遇到 C#6 语法（自动属性初始化等）报 CS1519/CS1002
- iterate 语法项目内现成例子：`Mapper/BusinessMapper/PsbStorePlaceSpare.xml`
- 自定义语句用全局唯一 ID，短 ID 可跨 mapper 被 UpdateByStatement/GetDataTableByStatement 直接调用；BaseManager 的 CRUD（Insert/Update）走 BasicMapper 命名空间约定
- WebSite 改动验证：`aspnet_compiler.exe -v /<站点名> -p <WebSite目录> <输出目录>` 预编译 0 error 即编译无误（输出含中文须 `grep -a`）

相关：[[bus-measure-import-full-solution]] [[batch-edit-code-safety-rules]]（脚本批量编辑代码的铁律，两次事故复盘） [[sql-server-performance-troubleshooting]]
