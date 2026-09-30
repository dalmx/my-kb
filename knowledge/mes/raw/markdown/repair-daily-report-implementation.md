---
title: 修理作业日报（表单式手填日报）实现方案与踩坑
category: 业务-通用
module: Batch
factory: 通用
tags: [修理日报, RepairDailyReport, SQ-PR01, CPP_REPAIR_DAILY_DATA, 权限探针, 快照复用, 表单式填报, 手工录入, FIELD_KEY白名单, 是非点选即存, Batch, 日报, 修理, 点检, 踩坑]
status: active
updated: 2026-09-09
---
# 修理作业日报（表单式手填日报）实现方案与踩坑

> 项目：Batch ｜ 编号：SQ-PR01 样式-1
> 页面：`Plugins/Batch/Report/RepairDailyReport.aspx(.cs)`｜手输快照表：`CPP_REPAIR_DAILY_DATA`（长表，维度=日期×班别×FIELD_KEY）
> 同系列参考：[[curing-daily-report-implementation]]（SQ-PK01 硫化）、[[first-inspection-daily-report-implementation]]（SQ-PL01 一检）、[[finishing-daily-report-implementation]]（SQ-PP01 仕上）
> 本文三个新范式：**零存储过程复用兄弟日报快照**、**长表手输项白名单保存**、**权限探针整页只读化**（最后一个是硬编码 ACTION_ID 翻车后的定稿）。

## 一、与硫化日报（SQ-PK01）的关键差异

| 维度 | 硫化日报 | 修理日报（本文） |
|---|---|---|
| 班别 | 表内「早班/夜班/合计」列 | **班别是查询条件**（早D/夜N下拉，同仕上日报），页面单班显示；⚠️ 版式定版后勿再加早/夜列（曾加过被用户整体回退） |
| 自动项来源 | 自建存储过程 Proc_CuringDailyReport 写自己的快照 | **零存储过程**：直接读硫化快照 `CPP_DAILY_REPORT_DATA`（口径天然一致，跨日报复用） |
| 手输载体 | 同一张快照长表（FIELD_KEY 区分） | 独立长表 `CPP_REPAIR_DAILY_DATA`（+SHIFT_CODE 维度，VAL_TEXT 统一存文本） |
| 编辑权限 | BusinessMapper SQL 写死 ACTION_ID=49452 | **权限探针**（框架自动禁用，授权即生效）——勿再抄硬编码 |

## 二、页面结构（纸表 SQ-PR01 还原，12 轮微调定稿）

分区：抬头(Logo+标题+编号) → 日期+实际出勤 → 安全(G0003领用，半宽卡) → 品质(1平板加硫机点检/2原辅料点检/3胶料清空/4保留品/5废品) → 设备(工具清单8项+备注) → 产量(三项蓝字+外观不良前五项) → 其它 → 页脚(禁带清单外工具+保管年限20年)。

版式定版要点（用户偏好，同类页面沿用）：
- **忠实纸表**：去多余前缀/编号（如「1、G0003领用」→「G0003领用」）；标题用**表格外 div** 而非表内表头行（如「2、修理用原辅料点检」）；「规格番号」表头通栏合并（纸表预印式），是/否预印在数据行
- 点检两机并排、无机台标签行（左右栏自身区分）；每机表：时间12±1×6时点 + 温度130±5×时点1、4/2、5/3、6（占1/3/5行）+ 压力0.25±0.05（设定/实际/判定 rowspan=6 整列）
- 左右并排表**等高**：外层 `display:flex;flex-direction:column` + 表格 `flex:1`（行少的表自动拉伸）
- 是/否判定：纸表画圈 → 页面 `td.cdr-yn` 点选高亮（`toggleYn`），值存隐藏载体 `txt_clr_<规格番号>`
- cdr- 卡片族 CSS 骨架照硫化日报；黄底=手填、蓝字=自动取数

## 三、产量自动项：复用硫化快照（零存储过程）

`CppDailyReportDataManager.GetEntityList(ReportDate)` 一遍读出后按 FIELD_KEY 拆：

| 页面格 | FIELD_KEY | 取值 |
|---|---|---|
| 修理量 | `rep` | 早班 VAL_DAY / 夜班 VAL_NIGHT |
| 外观不良量 | `c1bad` | 同上 |
| 待修量 | `repwait_d` / `repwait_n` | 分班字段存 VAL_TOTAL |
| 外观不良前五项 | `scrap4_d` / `scrap4_n` | 解析 VAL_TEXT（见下） |

前五项解析（存储过程 STRING_AGG 时已按数量降序，直接取前 5 条）：

```csharp
// VAL_TEXT 条目格式："代码-缺陷名-数量"，<br/> 分隔（Regex 容错多种写法）
string[] items = System.Text.RegularExpressions.Regex.Split(
    row.ValText, "<br\\s*/?>", System.Text.RegularExpressions.RegexOptions.IgnoreCase);
for (int i = 0; i < items.Length && i < 5; i++)
{
    string s = items[i].Trim();
    int lastDash = s.LastIndexOf('-');          // 数量在最后一个'-'后，缺陷名含'-'也安全
    if (lastDash <= 0) continue;
    reportData["top" + (i + 1)] = s.Substring(0, lastDash);   // 项目=代码-缺陷名
    reportData["topn" + (i + 1)] = s.Substring(lastDash + 1); // 数量
}
```

无数据默认"0"；硫化快照查询异常 alert 提示（便于定位），修理表查询异常静默留空。

## 四、手输保存：CPP_REPAIR_DAILY_DATA 长表

建表 DDL：`WebSite/resources/xls/Proc_RepairDailyReport.sql`（表/列注释齐全）。要点：
- `UNIQUE (REPORT_DATE, SHIFT_CODE, FIELD_KEY)` 唯一约束（兼作查询索引）；`VAL_TEXT NVARCHAR(500)` 统一存文本（数值/日期串/是否），免去类型纠结
- **FIELD_KEY = 页面输入框 id 去 `txt_` 前缀**，与页面一一对应；**白名单校验**（全名 att/g0003/hold/scrap/equip_note/other + 前缀 m1_/m2_/mat1_/mat2_/mat3_/clr_/tool），防任意 key 写库
- 单字段 Upsert：`GetEntityList(日期+班别+key)` → 有则 `Update(setValues, where)` 无则 `Insert`（同硫化模式，走 BasicMapper 基础 CRUD，无需业务语句）
- 是/否点选**即存**：隐藏载体无聚焦交互，不走浮动保存按钮，`toggleYn` 点选后直调 `App.direct.SaveSingle`；回查 `applyRecordData` 回填 + `markYnFromHidden` 恢复高亮（按 td 的 onclick 属性含载体 id + 文字匹配）
- 四件套（Entity/Data/Business/Mapper）+ BasicMapper XML 照 `CppDailyReportData` 同构改名，4 个 csproj 注册（Mapper XML 用 EmbeddedResource）

## 五、编辑权限：权限探针（翻车后定稿，勿再走弯路）

**反面教材**（两次返工）：① 照硫化/仕上硬编码 `EditActionId`（未申请填 0）→ 用户在权限系统给权后仍不能编辑——硬编码值与角色实际授权的 `SSP_PAGE_ACTION.objid` 对不上；② 改成「页面URL+按钮名」动态 join SQL 能用但多余——框架本来就自带这套机制。

**正解**（出处 [[button-permission]] 第九章、[[curing-check-dev-notes]] 4.3）：放**隐藏探针 ext:Button**，ID 严格等于权限类对应 PageAction 的 ActionName，框架 `setPageControls` 按角色授权自动禁用无权限按钮：

```aspx
<ext:Button ID="btnSave" runat="server" Text="编辑" Hidden="true">
    <Listeners><AfterRender Handler="initPerm();" /></Listeners>
</ext:Button>
```

```javascript
// 权限探针：读隐藏按钮禁用状态（框架按角色授权自动置 disabled）
var initPerm = function () {
    _canEdit = !(App.btnSave && App.btnSave.disabled);
    if (!_canEdit) disableAllInputs();   // 黄底变灰/是-否失效/不弹保存按钮
};
```

效果：角色管理授本页「编辑」动作 → 刷新即生效，**权限变更零代码零重编译**。注意探针 Text 要与权限类中文属性名一致（「编辑」）。`_.X.Permit` 不可靠（恒 0，框架不回写），别走那条路。

## 六、文件清单（新建）

| 文件 | 说明 |
|---|---|
| `Entity/BasicEntity/CppRepairDailyData.cs` | 实体（ObjId/ReportDate/ShiftCode/FieldKey/ValText/RecordUserId/RecordTime） |
| Data `ICppRepairDailyDataService`+`CppRepairDailyDataService`；Business `ICppRepairDailyDataManager`+`CppRepairDailyDataManager` | 三件套样板（照 CppDailyReportData 同构） |
| `Mapper/BasicMapper/CppRepairDailyData.xml` | 基础 CRUD（includeSelect/Where/Insert/Update） |
| `Mapper/BusinessMapper/CppRepairDailyData.xml` | 业务语句预留位（权限走探针，无 SQL） |
| `WebSite/resources/xls/Proc_RepairDailyReport.sql` | 建表 DDL（无存储过程） |
| `Plugins/Batch/Report/RepairDailyReport.aspx(.cs)` | 页面 |

## 七、踩坑速查

| 坑 | 正解 |
|---|---|
| code-behind 用 PageAction 报 CS0246 | 必须 `using Wongoing.Web.UI.Entity;`（PageAction 在 Frame 层 DLL，不在解决方案源码里） |
| 给权限后不能编辑（硬编码 ACTION_ID） | 用权限探针（见五章）；`SSP_PAGE_ACTION.action_id` 列只是页内序号，**objid 才是权限视图的 ACTION_ID** |
| `_.编辑.Permit` 恒为 0 | 框架不回写 Permit；探针按钮 + JS 读 `App.<ID>.disabled` |
| 改了类库/Mapper XML 不生效 | 重新编译 + **回收 IIS 应用池**（运行中 w3wp 不换 dll） |
| 用户手工合并代码留重复注释 | 只做增量清理（类头一份 summary，删误放在方法前的重复块） |
| 左右并排表高度不齐 | 外层 flex-column + 表格 flex:1 自动拉伸 |
