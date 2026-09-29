---
title: 成型生胎重量分析页开发实录（BPM_PRODUCTION 聚合 PPK + 指标转置动态列双表）
category: 业务-通用
module: 通用
tags: [生胎重量, 成型, Molding, PPK, Pp, STDEV, 整体标准差, 过程能力, 等级, 转置表, 动态列, Ext.NET, END_TIME, 8点跨天, ColumnAlign, 报表]
status: active
updated: 2026-09-02
---

# 成型生胎重量分析页开发实录（BPM_PRODUCTION 聚合 PPK + 指标转置动态列双表）

> 2026-09-02 在 Molding 新增 `Plugins/Molding/Report/GreenTyreWeightAnalysis.aspx(.cs)` 的完整实录：按轮胎规格汇总生胎重量能力指标，SQL 端聚合 + STDEV 等价实现 PPK 整体标准差法，指标为行/规格为动态列，规格列对半分成上下两表（行内容相同）。同类型"按规格做能力分析"页面可直接复刻。

## 一、需求与数据口径

输入起始/截止日期，按规格（`BPM_PRODUCTION.TYRE_MATERIAL_NAME`，值形如 S3394）输出指标表。**每个胎重即一个数据点**（不抽样、不算 CPK），PPK 用整体标准差法（与成型接头 CPK 页同方法，见 `cpk-spc-calculation-formulas.md`）。

数据源 `BPM_PRODUCTION`（每胎一条）关键字段与口径：

| 字段 | 用途 | 口径 |
|------|------|------|
| REAL_WEIGHT | 实际重量（手持称重回写） | 过滤非空且 >0（未称重胎不进统计） |
| STD_WEIGHT / STD_WEIGHT_MAX / STD_WEIGHT_MIN | 标准重量/规格上下限（每条快照） | 同规格取 MAX 作代表值 |
| TYRE_MATERIAL_NAME | 规格代码 | GROUP BY 维度、动态列列头 |
| END_TIME (DateTime) | 生产结束时间 | 时间过滤字段（见第三节） |
| DELETE_FLAG | 删除标记 | 仅 =0（报废不排除） |

产量=区间内已称重胎数。

## 二、SQL 聚合与 PPK 等价性

statement `SelectGreenTyreWeightStat@BpmProduction`（BusinessMapper/BpmProduction.xml）：

```xml
<select id="SelectGreenTyreWeightStat@BpmProduction" parameterClass="map" resultClass="row">
  <![CDATA[
  select p.TYRE_MATERIAL_NAME as SPEC,
         count(1) as CNT,
         avg(p.REAL_WEIGHT) as AVG_W,
         stdev(p.REAL_WEIGHT) as STD_W,
         max(p.STD_WEIGHT) as STD_W_STD,
         max(p.STD_WEIGHT_MAX) as USL,
         max(p.STD_WEIGHT_MIN) as LSL
  from BPM_PRODUCTION p with (nolock)
  where p.DELETE_FLAG = 0
    and p.REAL_WEIGHT is not null and p.REAL_WEIGHT > 0
    and p.END_TIME >= #BEGIN_TIME#
    and p.END_TIME < #END_TIME#
  group by p.TYRE_MATERIAL_NAME
  order by p.TYRE_MATERIAL_NAME
  ]]>
</select>
```

**为什么不在 C# 端调 SixSigmaHelper**：单规格可达数万条/月，拉原始数组到 Web 端不划算；SQL Server `STDEV()` 与 `SixSigmaHelper.GetTotalStdDev` 同为 n-1 样本标准差，数学等价。C# 端按同式计算（公式实读 `App_Code/SPC/SixSigmaHelper.cs` 核对过）：

```text
Pp  = (USL - LSL) / (6σ)
Ppk = min(USL - μ, μ - LSL) / (3σ)
公差% = (USL - 标准重量) / 标准重量 × 100（1 位小数 + %）
均值-标准 = μ - 标准重量
```

**等级按 Ppk 显示值（保留 2 位后）判定**：≥1.67→A+、≥1.33→A、≥1.00→B、≥0.67→C、否则 D（与 BeltDrumSpliceCpk 页 JS getCpkEvaluation 同阈值）。小数位：均值-标准/标准/均值=3 位、上下规格限=2 位、Pp/Ppk=2 位、产量=整数。

**防御**：DBNull 聚合值显示"-"；σ 为 NULL/0 或 CNT<2（STDEV 单条返回 NULL）时 Pp/Ppk/等级显示"-"。

## 三、时间口径：END_TIME 一天 = 08:00 ~ 次日 08:00

初版按 `PLAN_DATE`（varchar yyyy-MM-dd）闭区间过滤，用户次日改为 **END_TIME + 8 点跨天**（工厂班次口径，同 `shift-to-time-range.md` / `pb-daily-job-architecture.md` 的 `DATEADD(HOUR,8,…)` 模式）。C# 端拼时间传参，SQL 字段裸用走索引、半开区间：

```csharp
// 一天 = 当日 08:00 ~ 次日 08:00（END_TIME=生产结束时间，夜班跨天产出归次日）
DateTime beginDay;
DateTime endDay;
if (!DateTime.TryParse(txtBeginDate.RawText, out beginDay)) { beginDay = DateTime.Now.Date; }
if (!DateTime.TryParse(txtEndDate.RawText, out endDay)) { endDay = DateTime.Now.Date; }
dic.Add("BEGIN_TIME", beginDay.AddHours(8).ToString("yyyy-MM-dd HH:mm:ss"));
dic.Add("END_TIME", endDay.AddDays(1).AddHours(8).ToString("yyyy-MM-dd HH:mm:ss"));
```

选起始 09-01、截止 09-02 → 实际查 `09-01 08:00 ≤ END_TIME < 09-03 08:00`。⚠️ 口径从 PLAN_DATE 切到 END_TIME 后夜班跨天产出的归属日会变（预期行为非 bug），边界恰好 08:00:00 整的记录算前一天。

## 四、指标转置动态列 + 规格分上下双表布局（三轮迭代定稿）

**第一版**：单表 11 行（含"规格"行）× 全部规格动态列。用户两条反馈：①首行"规格"与列名重复（列头已是规格代码，该行冗余）；②页面下半部空洞，要求"分上下两部分"。

**第二版（返工教训）**：按**指标行**拆成"重量数据统计 / 过程能力分析"两张表——用户纠正：**要拆的是规格（列维度），不是指标（行维度）**。教训：用户说"分上下两部分"时先确认拆的是行还是列，别猜。

**定稿（第三版）**：
- 去掉"规格"行，首列列头"项目"放指标名；
- **规格列对半分**：上表放前 (n+1)/2 个规格、下表放其余，**两表指标行完全相同**（均值-标准/产量/标准/公差/上规格限/下规格限/均值/Pp/Ppk/等级，顺序照用户示例）；
- 仅 1 个规格时下表与分隔条隐藏、上表独占；
- 表标题动态生成：「生胎重量分析（S3393 ~ S3395）」= 该表所含规格范围（SQL 已按规格排序）；
- **整个结构（外层 pnlStat）默认 Hidden=true**：初始未查询时不露空表格骨架（动态列表格在首次绑列前是空壳，静态标题+空白表体很难看），查询有数据才 `pnlStat.Hidden = false` 显示，查无数据保持隐藏只弹提示（用户点名"整个结构隐藏"）。

布局照 `extnet-page-skeleton.md` 组合模式②（Center 区上下双面板）：

```xml
<ext:Panel ID="pnlStat" runat="server" Header="false" Border="false" Layout="VBoxLayout" Hidden="true">
    <!-- 外层容器不挂标题（页签名已是"生胎重量分析"）；默认 Hidden，查询有数据才显示（初始空骨架不露） -->
    <LayoutConfig>
        <ext:VBoxLayoutConfig Align="Stretch" />
    </LayoutConfig>
    <Items>
        <ext:GridPanel ID="gridData" runat="server" Title="生胎重量分析" ColumnLines="true" RowLines="true" Flex="1">
            <!-- Store 的 Model/Columns 留空，code-behind ChangeModels 动态生成 -->
        </ext:GridPanel>
        <ext:BoxSplitter ID="splitStat" runat="server" Cls="border-bgcolor" Height="4" />
        <ext:GridPanel ID="gridCpk" runat="server" Title="生胎重量分析" ColumnLines="true" RowLines="true" Flex="1">
            <!-- 同上；单规格查询时代码端 Hidden -->
        </ext:GridPanel>
    </Items>
</ext:Panel>
```

code-behind 结构（C# 5）：`ComputeSpecMetrics(DataRow)` 返回 `Dictionary<string,string>`（键=指标名）→ `specCodes/specMetrics` 各 `GetRange(0, half)` / `GetRange(half, n-half)` 对半 → `BuildMetricTable(子集规格, 子集指标, MetricRows)` 转置建表 → `ChangeModels(store, grid, dt)` 参数化后两表各调一次（清空重建无残留列）；导出=全部规格一张表存 Session（不重复查库）。页面骨架/权限/导出/样式套路同 `molding-plan-trace-report.md` 与 create-report 技能，交付前过 `extnet-new-page-style-checklist.md`。

## 五、踩坑清单

1. **`Column.Align` 属性类型是 `Ext.Net.ColumnAlign` 不是 `Ext.Net.Alignment`（CS0266）**：code-behind 动态建列 `new Column { Align = ColumnAlign.Left }` 才对；aspx 标记里写字符串 `Align="Center"` 无此问题。审查时对 bin/Ext.Net.xml 文档只验证"类型存在"不够，必须核对属性签名的类型一致（实施与审查双漏，用户编译才暴露）。
2. **SPEC 为 NULL 的组**：SQL 未过滤 `TYRE_MATERIAL_NAME IS NULL` 时，NULL 组列名为空串、列头降级成自动列名（不崩溃）；要防加 `and p.TYRE_MATERIAL_NAME is not null` 即可。
3. **转置表的重复行问题本质**：动态列的列头已经承担了"规格"信息，就不该再输出一行规格值——交叉转置表设计时先看列头与首行是否语义重复。
4. **"分上下两部分"需求歧义**：单表拥挤/空洞要拆上下时，先问清拆**行**还是拆**列**——本例正解是列维度（规格对半分、两表行内容相同），按行拆（指标分组）被用户打回返工一轮。
5. **报表 SQL 表引用一律 WITH(NOLOCK)**（用户点名要求）。

## 六、部署与复用要点

- Mapper XML 是 EmbeddedResource：加语句须重编 Mapper 工程换 Bin；aspx/aspx.cs 是 CodeFile 免编译，保存即生效。
- 菜单：SSP_PAGE_MENU 经 SetPageMenu.aspx 配置；权限 2 个 Action（查询 btnSearch / 导出 btnExport）。
- 复刻同类"按规格/物料做 Pp/Ppk 能力分析"页面时：换表名+字段名+时间口径即可，计算与展示层可直接搬。
