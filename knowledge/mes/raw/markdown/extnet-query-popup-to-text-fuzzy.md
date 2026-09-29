---
status: active
updated: 2026-09-15
title: 查询条件由选择弹窗改文本模糊输入改造模式（精确编码 → 名称 LIKE）
category: 技术-.NET
module: Ext.NET
tags: [Ext.NET, TextField, 模糊查询, LIKE, 查询条件, 文本输入, 制造编号, MATERIAL_NAME, RawText, Name重名, 逗号拼接, iBATIS, 存储过程, 踩坑, 改造模式]
---

# 查询条件由选择弹窗改文本模糊输入改造模式（精确编码 → 名称 LIKE）

> 查询条件原来是"不可编辑 TextField + 选择弹窗回填编码 + SQL 精确 in('=')"，改为"可直接输入的文本框 + MATERIAL_NAME LIKE '%…%' 模糊查询"的完整改造模式。2026-09-15 Curing 项目 9 页批量实证，含 Name 重名拼逗号致恒空的排障实录。

## 一、适用场景与改动总览

用户要"少一步选择、打字直接模糊搜"时，把选择类控件降级为纯文本输入。改造涉及三件套，一处不改就出"页面空/报参数错"：

| 层 | 改什么 | 不改会怎样 |
|----|--------|-----------|
| aspx | TextField 去 `Editable="false"` 与 Search 触发器、**去 `Name` 属性**、删隐藏域与弹窗 JS | 仍弹窗/取不到值/拼逗号坑（见第五章） |
| aspx.cs | 取值改 `txtXxx.Text.Trim()` 传名称参数 | RawText 可能读到拼接串 |
| mapper xml / proc | 条件改 `MATERIAL_NAME like '%'+参数+'%'` | 仍按编码精确查=查不到 |

统一模板（9 页通用）：

```aspx
<ext:TextField runat="server" ID="txtMatreial" FieldLabel="制造编号" LabelAlign="Right">
    <Triggers>
        <ext:FieldTrigger Icon="Clear" />
    </Triggers>
    <Listeners>
        <TriggerClick Handler="if (index == 0) this.setValue(null);" />
    </Listeners>
</ext:TextField>
```

要点：不写 `Name` 属性；不留 Search 触发器；清空按钮用内联 Handler，不引公共函数。

## 二、aspx 侧要删干净的三件套（弹窗时代遗留）

1. **隐藏域**：`<ext:Hidden ID="hd_MaterialCode" runat="server" />`（或 ui_s_MATERIAL_ID 等）——查询不再依赖编码回填，删。
2. **JS 三段**：`SelectMaterial` 触发函数、`Ext.create` 建窗（iframe 指向 /MCUI/SearchBox/SearchBoxCppSbmMaterial.aspx）、`McUI_SearchBox_..._Request` 回填回调。先 grep 确认没有页内其它字段（新增/修改弹窗）共用再删；共用则只删查询字段的分支（参考 CuringPlanForZaoYe：弹窗留给对话框，只删"两个弹窗都隐藏时回填查询框"的分支）。
3. **死函数**：ComboBox 时代遗留如 `txtMajorTypeChange`（调 `txtMatreial.getStore()`，TextField 无 store，一触发就报错）——本次动的文件里发现可顺手删。

删完用 grep 复核零残留：`hd_MaterialCode|SelectMaterial|SearchBoxCppSbmMaterial`。

**改 markup 的结构陷阱**（CuringPlanExecute 实测三次失配）：TextField 后面常跟着**大段注释掉的旧 ComboBox**（`<%--<ext:ComboBox ID="txtMatreial"…--%>`），`</Items>` 在注释块之后——精确替换时 old_string 别带 `</Items>`；块内还可能有空行。反复失配时先 `sed -n '起始,结束p' 文件 | cat -A` 看原始空白字符（空格/制表符/空行）再构造 old_string。

## 三、code-behind 取值：一律 .Text.Trim()

```csharp
pageParams.Add("MATERIAL_NAME", string.IsNullOrWhiteSpace(txtMatreial.Text) ? "" : txtMatreial.Text.Trim());
```

- **用 `.Text`，不要 `RawText`**：`.Text` 是控件自身值；`.RawText` 读提交原文，查询 TextField 带 `Name` 且与页内其它字段重名时会读到逗号拼接串（第五章）。DateField 的 RawText 不受影响（无重名）。
- 参数名跟随各语句既有风格（MATERIAL_NAME / MaterialName / matername），空值传 `""` 不传 null——iBATIS dynamic `isNotEmpty` 对空串自动跳过条件。
- **旧参数删干净，不留空传兼容**：C# 取参、mapper 条件、存储过程参数三处同步删；动手前 grep 语句 id 确认调用方数量（多调用方时要么全改，要么像 SulfProduceAnalyse 钻取那样统一改传名称——语义上全名 LIKE 足够精确）。

## 四、SQL 改造四种形态

**形态 A：dynamic isNotEmpty（最常见）**，产出现成 JOIN 到物料表时直接用别名：

```xml
<isNotEmpty property="MATERIAL_NAME" prepend="AND">
    t2.MATERIAL_NAME like '%'+#MATERIAL_NAME#+'%'
</isNotEmpty>
```

**形态 B：产出表只有物料编码**（如 CPP_CURING_PRODUCTION.MATERIAL_ID），转子查询按名称反查：

```xml
<isNotEmpty property="MATERIAL_NAME" prepend="AND">
    B.TYRE_MATERIALID in (select MATERIAL_CODE from SBM_MATERIAL where MATERIAL_NAME like '%'+#MaterialName#+'%')
</isNotEmpty>
```

**形态 C：多语句共用 `<include>` 片段**——改一处全覆盖。7 条视图语句共用 `IncludeSelectPlanAnalyseReportWhere`（ProduceAnalyseReport），只在片段里改一次。先 `grep "include refid="` 摸清引用面。

**形态 D：存储过程动态 SQL 拼接**——参数类型对齐列 DDL（`nvarchar(300)` 对 SBM_MATERIAL.MATERIAL_NAME），拼接必须转义单引号防拼坏：

```sql
@MATERIAL_NAME nvarchar(300),   -- 对齐列类型
...
if isnull(@MATERIAL_NAME,'')!=''
    set @sqlselect = @sqlselect + 'and t4.MATERIAL_NAME LIKE ''%'+replace(@MATERIAL_NAME,'''','''''')+'%'''
```

静态参数化 proc（非动态拼接）不需要 replace：`(D.MATERIAL_NAME LIKE '%' + @MATERIAL_NAME + '%' or @MATERIAL_NAME = '')`。

## 五、踩坑实录：TextField 带 Name 且与弹窗字段重名 → RawText 恒带逗号 → LIKE 恒空

**现象**（CuringPlanForZaoYe 2026-09-15）：改造后页面查询恒空，SSMS 同参数有数据，请求全 200 无报错。抓实际 RPC 参数发现 `@MATERIAL_NAME=,`——用户**没输入**。

**根因**：查询 TextField 挂 `Name="MATERIAL_NAME"`，与页面上生胎物料/左模/右模等**弹窗字段同名**。Ext.NET 提交时同名值用逗号拼接（空+空=","），`RawText` 读到的是拼接串 ","，SQL 拼出 `LIKE '%,%'` 无任何制造编号含逗号 → 0 行。该页旧查询走 hd_MaterialCode 隐藏域从不读文本，坑一直潜伏。

**为什么 200 不可信**：Wongoing.DbAccess 是外部 dll，疑似吞 SQL 异常返回空表——参数不匹配、SQL 报错都可能表现为"200 + 空表格"而非报错弹窗。

**预防**：查询条件 TextField **一律不写 Name 属性**（Ext.NET 按 ClientID 同步控件状态，DateField 无 Name 的 RawText 正常即证）；取值用 `.Text`。

## 六、空结果排障清单（按序执行）

1. 抓页面**实际传参**（SQL Profiler RPC:Starting / VS 断点），别跟"右键执行存储过程"比——那是全 NULL 无过滤，没有可比性；要比就用页面等价参数 EXEC。
2. 检查参数值有没有**莫名逗号**（第五章重名坑）。
3. 核实部署链：aspx/aspx.cs 是网站模型动态编译（刷新即生效）；**mapper xml 是 EmbeddedResource 编进 Wongoing.Curing.Mapper.dll，必须 VS 生成解决方案刷 Bin**，用 `grep -a "新语句文本" Bin/Wongoing.Curing.Mapper.dll` 实证。
4. 确认 proc ALTER 执行在**应用连接的那个库**：导出件头部的 `USE [库名]` 只代表导出时 SSMS 开着的库，与应用真实连接（web.config 的 strDbCon）未必相同——执行前先 `SELECT DB_NAME()` 对一遍，别默认导出库就是应用库。
5. Edit 工具编 UTF-16 的 aspx.cs 会写回无 BOM UTF-8，必须 powershell 转回并 `file` 验证。

## 七、部署顺序（proc 页专属）

参数改名后新旧不兼容：**先库内执行 ALTER，再 VS 生成部署新 DLL**，两步同一窗口完成；中间态页面查询报参数错误属预期。sql/ 目录里"原样导出件"本身就是旧定义的 ALTER，跑错文件会把旧 proc 刷回去——改造脚本要用单独命名的副本（如 `PROC_XXX_模糊查询改造.sql`）。

## 八、参考实现位置（2026-09-15 九页实证）

| 页面 | 语句/proc | 形态 |
|------|----------|------|
| Plugins/Curing/ProductPlan/CuringPlanForZaoYe | PROC_CPP_SELECT_DAY_PLAN | D 动态拼接+replace |
| Plugins/Curing/ProductPlan/CuringPlanExecute | SelectExecutePlan@CppCuringPlan | A（一个语句两个调用方同改） |
| Plugins/Curing/ProductPlan/CuringProduceMonitor | PROC_CPP_MONITOR_PLANMONITOR | D 静态参数化 |
| Plugins/Curing/ProductPlan/CuringMonthPlan | SelectMonthPlan@CppCuringPlan | A+declare 变量改名，产线子查询用 B |
| Plugins/Curing/Produce/PersonalProduceAnalyse | SelectWorkerProduction@CppCuringProduction | B |
| Plugins/Curing/Produce/CuringProductionQuery | SelectProductionQuery/Page@CppCuringProduction | A（where. 前缀版+平铺版各一条，性能优化 SQL 只动条件不动结构） |
| Plugins/Curing/Produce/SulfProductionAnalyse | SulfProduceAnalyse@CppCuringProduction | B（明细钻取改传行 MATERIAL_NAME） |
| Plugins/Curing/Produce/ProduceAnalyseReport | SelectPlanAnalyseReport1~7@CppCuringPlan | C 共享 include |
| Plugins/Curing/Technology/CuringTechnalogyReport | SelectPlanStatistics@CppCuringPlan | A（参数名 matername） |

## 九、关联文档

- `extnet-query-control-upgrade.md` —— 反方向：TextField → 弹窗/下拉的升级模式（本篇是其逆操作）
- `extnet-combobox-fuzzy-search.md` —— 下拉框内模糊搜索（仍需可选时的替代方案）
- 项目记忆：制造编号模糊查询9页任务（curing-material-name-fuzzy-task）、Ext.NET查询TextField重名逗号坑（extnet-query-textfield-name-comma）
