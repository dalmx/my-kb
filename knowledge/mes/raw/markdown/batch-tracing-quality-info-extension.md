---
category: 业务-通用
module: Batch
status: active
tags:
- 批次追溯
- BatchTracing
- tf_R_ScanTime
- 有值才显示
- SetHidden
- UseTime
- 胶料
- 显隐
title: BatchTracing 批次追溯页成品胎质量信息扩展
updated: '2026-09-09'
---

# BatchTracing 批次追溯页成品胎质量信息扩展

> 在成品胎信息区增加一检/二检不良名称、修理结果与修理OK时间、UF/DB 测定次数与不合格信息。数据全部走存储过程 PROC_BAT_GET_BATCHCURINGMSG 扩展列，页面零新增查询。

## 一、页面与数据链路（实证）

- 页面：`P.Batch\Wongoing.Batch.WebSite\Plugins\Batch\BatchTracing\BatchTracing.aspx(.cs)`，成品胎信息在 PanelCuring 的 5 个 FieldSet（硫化/外观/修理记录/UFDB/二次外观）。
- 数据链路：`getCuringMsg` → `GetCuringBatchMsg@CppCuringProduction`（Mapper 仅是 procedure 壳）→ **存储过程 `PROC_BAT_GET_BATCHCURINGMSG`**。过程定义不在项目里，由用户从 SSMS 导出放 `Batch\sql\PROC_BAT_GET_BATCHCURINGMSG.sql`；**改查询=改过程**，改完用户连库执行。
- 过程风格：OUTER APPLY TOP 1 ORDER BY OBJID DESC 取最新、WITH(NOLOCK)、不加 DELETE_FLAG——新增块必须照此风格（页面同区块口径才一致）。

## 二、新增 8 列口径（2026-09 定版）

| 列 | 来源 | 口径 |
|---|---|---|
| FCHECK_DEFECT_NAMES | FQF_FCHECK_INFO + FQD_DEFECT_INFO('4') | **只取最新一次检查**（RECORD_TIME=该胎 max）的病疵，同次多条"、"拼接去重（用户明确要求只取最新，不取全部历史）；DEFECT_CODE 非空；不加 DELETE_FLAG |
| SCHECK_DEFECT_NAMES | FQF_FCHECK_INFO_TWO + FQD_DEFECT_INFO('5') | 同上，二检表 |
| REPAIR_RESULT | FQR_REPAIR_RECORDS | 最新一条 REPAIR_RESULT_ID：'1'合格 '2'不合格；无 DELETE_FLAG 过滤（与已有修理人员/修理时间口径一致） |
| REPAIR_OK_TIME | FQR_REPAIR_RECORDS | REPAIR_RESULT_ID='1' 的最新一条 RECORD_TIME，CONVERT 120 |
| UF_CHECK_COUNT / UF_NG_INFO | FQB_UFCHECK_INFO | Barcode=胎号全部记录；行级NG=UF_Mark NOT IN(1,2)；NG分项=60 个 Class 列值>2（清单照抄 Proc_FinishDailyReport UNPIVOT）；NG_INFO='共测定N次：第X次NG[分项](时间)；…'，**全部合格则为空** |
| DB_CHECK_COUNT / DB_NG_INFO | FQB_BALANCE_INFO | 同构；DB_Mark NOT IN(1,2)；分项 SB/DBUpper/DBLower/DBUpper_Lower 四个 Class 列 |

- 长文本聚合用 STRING_AGG（库已确认 SQL2017+）；NG 行分项用 `OUTER APPLY (SELECT STRING_AGG(item,',') FROM (VALUES (c.XxxClass,'Xxx'),…) v(val,item) WHERE v.val>2)`——VALUES 相关子查询必须在 APPLY 内。
- FQB 系表字段 PascalCase（Barcode/RecordTime/UF_Mark/Objid）；FQF/FQR 表 UPPER_SNAKE。

## 三、页面绑定

```csharp
// getCuringMsg 内：有行时 8 个 SetValue；else 分支清空（原代码无 else，切换树节点会残留旧值——新字段已修，老字段行为不动）
txt_fcheck_defect.SetValue(formData.Rows[0]["FCHECK_DEFECT_NAMES"] == DBNull.Value ? "" : formData.Rows[0]["FCHECK_DEFECT_NAMES"].ToString());
```

整行宽字段（不良名称/不合格信息）用 `ColumnWidth="1"` 容器 + TextField LabelWidth="90"；窄字段填 FieldSet 原有空列位（.25）。

## 四、部署清单

1. 用户连库执行 `Batch\sql\PROC_BAT_GET_BATCHCURINGMSG.sql`（ALTER 形式可重复执行）。
2. 拷贝 aspx/aspx.cs 到网站（Website 动态编译自动生效）。
3. 不改 Mapper XML、不动 bin，**无需回收应用池**。

---



## 五、SQL 优化对照结论（对照 sql-server-performance-troubleshooting.md 语句优化原则）

| 原则 | 结论 |
|---|---|
| 1. 缩小范围 | ✅ 全部子查询先按 @BatchCode（胎号强约束字段）收窄到单胎几行，无全表扫描 |
| 2. 字段禁函数（SARGable） | ✅ WHERE 字段侧均裸用；`isnull(DEFECT_CODE,'')<>''` 套函数但作用于已收窄的单胎行数（与手持端既有写法一致），可接受；CONVERT 只在 SELECT 列表 |
| 3. 控制 JOIN | ✅ 仅一检/二检 APPLY 各挂 1 张 FQD_DEFECT_INFO 字典表，UF/DB 零 JOIN |
| 4. 禁 SELECT * | ✅（初稿曾在派生表用 `t.*` 拉全 90+ 列，已改明确列清单：UF_Mark/RecordTime+60 Class 列；DB_Mark/RecordTime+4 Class 列） |
| 5. 隐式类型转换 | ✅ '4'/'5'/'1' 对 varchar 列（WORK_PROCESS_ID/REPAIR_RESULT_ID，台账核对），1,2/>2 对 int 列（UF_Mark/DB_Mark/Class），@BatchCode varchar(50) 对 varchar |
| 7/9. 参数嗅探 | ✅ 第一个 SELECT 末尾 `option(recompile)`（12 个 APPLY 分支联接策略随首参变化的潜在嗅探，单胎点查重编译开销可忽略，跟随 Proc_FinishDailyReport/一检日报先例） |
| STRING_AGG 内存授予 | ✅ 不物化临时表——手册"大表 STRING_AGG 必须物化"针对全表/大范围聚合；此处均在单胎几行的 APPLY 内聚合，无内存授予压力 |
| NOLOCK | ✅ 全部 WITH(NOLOCK)（与原过程一致） |

> 经验：**单胎点查（胎号强约束）场景，"先收窄"就是最强的优化**；派生表即使行数少也别顺手写 `t.*`——90+ 列的波形明细列会被整行拉进内存，列清单才是合规写法。max(RECORD_TIME) 子查询在 OUTER APPLY 内对主行只执行一次，非逐行相关子查询，无需提变量。

---



## 六、修订记录（v2，2026-09-05 用户口径修正，覆盖上文对应条目）

| 修订 | 内容 |
|---|---|
| 取消修理OK时间列 | 用户新口径：**只保留统一修理时间（原有 repair_time）**，不再单独输出 REPAIR_OK_TIME；新列由 8 减为 7 |
| FQR 只查一遍 | 原 rp/rpok 两个 APPLY 与过程原有 repair 同为 TOP 1 最新逻辑，属重复查询（用户指出）；修理结果（REPAIR_RESULT）直接并入原 repair apply 输出——合格显示合格、不合格显示不合格，O(1) 次表访问 |
| FQR DELETE_FLAG=0 | 用户明确：`FQR_REPAIR_RECORDS delete_flag = 0 是有效数据`，repair apply 加 `t.DELETE_FLAG = 0`（tinyint，数值比较） |
| 一检/二检同样加 DELETE_FLAG=0 | 用户明确"一检 二检一样的要求"：f1d/f2d 均加 `fd.DELETE_FLAG = 0`（int），**覆盖一检日报"FQF_FCHECK_INFO 不加 DELETE_FLAG"的旧口径**（该旧口径适用于报表统计场景，追溯页单胎明细按用户口径取有效数据） |
| 一检/二换单遍读取 | max(RECORD_TIME) 子查询+外层过滤的两遍读改为 `select top 1 with ties ... order by RECORD_TIME desc` 一遍取出最新一次检查的全部行，再筛病疵去重聚合；语义等价（最新一次检查无病疵→空） |

> 教训：**给已有查询加字段前先看原查询怎么访问这些表**——同表同过滤同排序的 TOP 1 逻辑应直接在原 APPLY 上扩列，不要并排新开 APPLY（三遍读一遍搞定）。TOP 1 WITH TIES 是"取最新一组记录（同时间戳多行）"的单遍读法。

---



## 七、修订记录（v3 终版口径，2026-09-05）

| 项 | 终版口径 |
|---|---|
| 一检/二检表有效数据 | 用户明确：**每胎 DELETE_FLAG=0 的记录只有一条**——f1/f2 回归原 TOP 1 结构，检员/时间锚点恢复 OBJID DESC（与原过程一致），病疵名直取该条记录（`case when DEFECT_CODE<>'' then isnull(字典名,表内名) else '' end`），**无需"最新一组+聚合去重"**（WITH TIES/STRING_AGG 方案废弃） |
| 单遍读取 | 与修理同法：检员/时间/病疵合并进**原有 f1/f2 apply**，FQF_FCHECK_INFO、FQF_FCHECK_INFO_TWO、FQR_REPAIR_RECORDS 各只读一次 |
| UF/DB | 用户明确"跟UF/DB没关系"：**不加 DeleteFlag 过滤**，全部测定记录计入测定次数与 NG 判定（与 Proc_FinishDailyReport 口径一致） |
| 修理OK时间 | 已取消（v2），只保留统一修理时间 repair_time；修理结果=最新有效记录 REPAIR_RESULT_ID |

> 合并相关查询的语法坑：**SELECT 列表子查询里的派生表不能相关引用外层别名**（SQL Server 派生表禁止外部引用，只有 APPLY 可以）——`select max(..), (select string_agg(..) from (select .. from y ..) x) from (..) y` 这种写法编译报错；聚合类合并要在一层 SELECT 里直接写聚合（max + string_agg 并列），或依赖"有效记录唯一"退化成 TOP 1 直取。

---



## 八、修订记录（v4：UF/DB 也合并单遍，2026-09-05）

- 用户要求 UF/DB 同样只查一次：原 `uf`/`db`（TOP 1 取检员/机台/时间）并入 `ufq`/`dbq`（全量统计），改名统一为 `uf`/`db`，APPLY 总数 12→6，**FQF/FQF_TWO/FQR/FQB_UF/FQB_DB 五张表各恰好一次访问**。
- 检员/机台/时间的取法：聚合层 `max(case when c.rn = c.cnt then c.UserCode/EquipCode/RecordTime end)`——即按 (RecordTime,Objid) 排序的**最后一次测定**那条，与 NG 编号口径自洽（原 TOP 1 OBJID DESC 通常等价）。
- 合并时保持输出列名不变（uf: RECORD_USER_ID/EQUIP_ID/RECORD_TIME；db: UserCode/EquipCode/RecordTime），主 SELECT 的 UF_OPER/UF_DATETIME/DB_OPER/DB_DATETIME 引用零改动。
- 聚合型 OUTER APPLY 天然单行返回（无数据也返回一行全 NULL），替代原 TOP 1 标量子查询安全。

---



## 九、修订记录（v5：UF/DB 不合格信息悬浮框，2026-09-05）

- 问题：NG 信息文本较长（多次 NG 各带分项与时间），TextField 单行显示不全。
- 方案：字段内挂 `<ToolTips><ext:ToolTip>`（与本页 btnExport/ToolTip3 同款自动定向宿主控件的写法），`BeforeShow` 监听器实时取 `App.xxx.getValue()` setHtml——**内容随 DirectMethod 绑定自动同步，cs 零改动**；值为空时 return false 不弹出；`MaxWidth=600` 自动换行、`DismissDelay=0` 悬停期间不自动消失。
- 依据官方示例 ToolTips/Overview（ext:ToolTip Target/Html/DismissDelay/Listeners 用法）+ 本页既有 ToolTips 集合惯例。

---



## 十、修订记录（v6：批次信息/原料批次 Grid 风格对齐，2026-09-05）

- 用户要求"批次信息 Grid 风格与系统一致"。对照 Batch 项目三个新近交付日报页（部材/一检/仕上）提炼的系统标准：GridPanel 四件套 `ColumnLines="true" RowLines="true" EnableColumnHide="false" SortableColumns="false"` + 序号列 `Width="50" Align="Center" Text="序号"` + GridView 三件套 `EnableTextSelection/TrackOver/StripeRows`。
- 本页 pnlBatchs（批次信息）原四件套全缺、序号列为裸标签——已补齐；pnlMixBatchs（原料批次）补四件套并新增 GridView 三件套（原来无 View）。
- pnlBatchs 原有 GetRowClass 选中行高亮保留（功能性，非风格项）；winDetail 操作明细窗格属弹窗场景未动。

---



## 十一、修订记录（v7：页签条颜色不一致根因，2026-09-05）

- 现象（用户截图实证）：底部"批次信息/原料批次"页签条为 Ext 默认亮蓝，与上方深藏蓝面板标题栏（批次列表/批次信息）不一致。
- 根因：本页 `batchinfo` TabPanel 未挂系统页签标准类 **`Cls="ui-tab-bar"`**——extExtra.css 定义 `.ui-tab-bar .x-tab-bar { background:#2d6ca2 !important; }` 把页签条刷成系统深蓝，TyreRealTimeStockQuery / LabStockQuery / Main/MainFrame 等系统页均在用。
- 修复：`<ext:TabPanel ... ID="batchinfo" Cls="ui-tab-bar" Border="false">`。
- **通则：MES 项目族内任何 TabPanel（含页面主页签与局部页签）都要挂 ui-tab-bar，否则就是截图里那种亮蓝色默认样式。**

---



## 十二、修订记录（v8：FieldSet 整行字段右侧大片空白——ColumnLayout 换行坑，2026-09-05 实证）

- **现象（用户截图）**：外观/UFDB/二次外观 FieldSet 中新加的整行字段（不良名称/不合格信息）没有独占一行，被压成窄列，行尾右侧留大片空白。
- **根因**：Ext **ColumnLayout 子项不自动换行**——官方示例（Layout/ColumnLayout/Basic）证明子项按 columnWidth 比例排在同一水平带内；本页 FieldSet 原有 4×.25 恰好占满一行，我自创的 `ColumnWidth="1"` 容器（官方示例库中零用例）挤不进新行，比例被整体压缩变形。
- **正解（嵌套容器）**：
```aspx
<ext:FieldSet runat="server" Title="xxx">            <!-- 不设 Layout -->
    <Items>
        <ext:Container Layout="ColumnLayout">          <!-- 第一段：N 列字段 -->
            <Items> …ColumnWidth=".25" ×4… </Items>
        </ext:Container>
        <ext:Container Layout="FormLayout">            <!-- 第二段：整行字段，锚定100%撑满 -->
            <Items> …TextField… </Items>
        </ext:Container>
    </Items>
</ext:FieldSet>
```
FieldSet 默认布局垂直堆叠两段；FormLayout 字段默认 anchor 100%（先例：Main/SysUser/MyUser.aspx）。
- **通则**：ColumnLayout 内**每行 columnWidth 总和必须恰为 1**，多行内容靠嵌套 Container 分段，绝不靠"加一个 ColumnWidth=1 想换行"。

---



## 十三、修订记录（v9 终版布局：长字段并入同行，2026-09-05）

- v8 的"嵌套容器+整行字段"方案渲染后整行字段输入框塌缩到 ~200px（FieldSet 默认 auto 布局下无宽度约束的 FormLayout 容器宽度塌缩），右侧仍大片空白。
- 用户定版："页面宽度够的时候不用换行"——长字段（不良名称/不合格信息）**并入同一行**，不再独占整行。
- 终版（单层 ColumnLayout，列宽总和恒为 1）：
  - 外观信息：品级 .2｜检员 .2｜时间 .2｜一检不良名称 .4
  - UFDB信息：品级 .15｜检员 .15｜时间 .15｜测定次数 .15｜UF/DB不合格信息 .4（NG 两字段堆叠在 .4 列，悬浮框保留兜底看全文）
  - 二次外观信息：品级 .2｜检员 .2｜时间 .2｜二检不良名称 .4
  - 空占位列（container17/25/33）删除。
- **经验链总结**：ColumnLayout 里 ColumnWidth 总和必须恰为 1（>1 会被压缩变形、整行字段不会换行）；auto 布局下的 FormLayout 容器会宽度塌缩不可用作整行容器；长文本字段并入列（配 ToolTip 看全文）是追溯页最稳的布局。

---



## 十四、部材明细增加返回品使用信息（2026-09-05）

- 需求：部材节点明细增加"返回品使用信息"。口径：部材产出行（HPP_SEMIS_PRODUCTION）自带的 `RETURN_SPLICING_CARD`（拼接使用的返回品条码=返回品记录的 CARD_NO）+ `RETURN_SPLICING_NUM`（数量），见 [[semi-return-product-output-report]]。
- 改动三件套（沿用本页惯例）：
  1. `Batch\sql\PROC_BAT_GET_BATCHSEMIMSG.sql`（用户从 SSMS 导出后我改）：部材分支第一个 SELECT 末尾追加 `t1.RETURN_SPLICING_CARD RETURN_CARD, t1.RETURN_SPLICING_NUM RETURN_NUM`，胶料分支不动；用户连库执行 ALTER。
  2. aspx：PanelMold 的 container1（生产机台/物料单位/库位信息列）追加 `txt_return_card`（返回品条码）、`txt_return_num`（返回品数量），默认 Hidden=true；注意 **container1 是每字段一个 `<Items>` 块的特殊写法**。
  3. cs：GetBatchMsg 四分支显隐（仅部材分支 dataType==3 非8位 Hidden=false，成型/胶料×2 隐藏）；getSemiMsg 绑定用 `Columns.Contains("RETURN_CARD")` 防护（**过程未升级前页面可先部署，字段空且不报错**）+ else 清空。
- 本页三个明细存储过程模式统一：成品胎=PROC_BAT_GET_BATCHCURINGMSG、部材=PROC_BAT_GET_BATCHSEMIMSG、胶料=PROC_BAT_GET_BATCHRUBBERMSG，均"Mapper 仅 procedure 壳、改查询=改过程"。

---



## 十五、终版部署清单与自检（2026-09-05 全需求收口）

本页两项需求（成品胎质量信息 + 部材返回品使用信息）最终交付物与部署顺序：

1. **连库执行两个存储过程**（均为 ALTER 形式可重复执行，务必用当前文件）：
   - `Batch\sql\PROC_BAT_GET_BATCHCURINGMSG.sql`（成品胎：7 质量列，6 APPLY 单遍结构）
   - `Batch\sql\PROC_BAT_GET_BATCHSEMIMSG.sql`（部材：RETURN_CARD/RETURN_NUM 两列）
2. **拷贝页面两个文件**：`BatchTracing.aspx` + `BatchTracing.aspx.cs`（Website 动态编译自动生效）。
3. 不改 Mapper XML、不动 bin，**无需回收应用池**。页面绑定带 Columns.Contains 防护，过程未升级前字段空白不报错（可先部署页面）。

### 交叉自检结论（脚本化核对通过）
- 硫化过程 7 新列名与 cs 绑定逐一对应；部材过程 2 列与 cs Contains/绑定对应
- aspx 9 个新控件（7 质量 + 2 返回品）ID 唯一且均有 cs 引用（ToolTip 控件纯前端无 cs 引用属正常）
- 5 个 FieldSet columnWidth 总和全部恰为 1.0；两过程括号平衡；cs 大括号平衡；无 REPAIR_OK_TIME/"共测定"/废弃别名残留

### 验收要点
- 成品胎：一检/二检不良名称（单条有效记录直取）、修理结果、UF/DB 测定次数与不合格信息（悬浮框分号分行）；无 NG 胎信息为空；切换树节点无残留（含批次 Grid 清空）
- 部材：返回品条码/数量（仅部材节点显示）；成型/胶料节点不显示
- Grid 四件套风格、页签条深蓝（ui-tab-bar）、长字段并入行内（.4 列）

---

## 十五、dataType=5 胶料分支"扫描投料时间"不显示的坑（2026-09-09）

- 现象：dataType=5 分支写 `txt_scan_time.Hidden = false` 页面不展示。
- 根因：**Ext.NET 隐藏沿容器树继承，子控件 Hidden=false 无法覆盖祖先 Panel 的隐藏**。`txt_scan_time` 位于 PanelMold（container4→FormMoldPanel→PanelMold），而 dataType=5 分支 `PanelMold.Hidden = true`、显示的是 PanelRubber——整棵 PanelMold 子树不渲染，字段自身 Hidden 设什么都看不到（值其实已 SetValue 进去，只是不可见）。
- 修复（三件套）：
  1. aspx：FormPanelRubber 的 container13 末尾（每字段一个 Items 块惯例写法）新增 `tf_R_ScanTime`（FieldLabel=扫描投料时间）；
  2. cs `getRubberMsg`：清空与 UseTime 赋值两处从 `txt_scan_time` 改绑 `tf_R_ScanTime`；
  3. cs `GetBatchMsg` dataType=5 分支：`txt_scan_time.Hidden` 改回 true（与胶料 8 位分支完全一致）。
- 通用结论：**要让某字段在某个 Panel 分支显示，字段必须物理位于该 Panel 内**；跨 Panel 设 Hidden 无效。判断"设了 Hidden=false 为何不显示"时先查它的祖先链有无 Hidden=true。另：`ClearCuringPanelFields` 递归清空会自动覆盖新增的 tf_R_ScanTime，无需额外处理。

---

## 十六、tf_R_ScanTime 改为"有值才显示"（2026-09-09）

- 十五节新增的 tf_R_ScanTime 按用户要求改为值驱动显隐：aspx 初始 `Hidden="true"`；`getRubberMsg` 清空段 `SetValue("")` 后紧跟 `SetHidden(true)` 兜底，取数段仅当 `UseTime != DBNull` 时 SetValue+`SetHidden(false)`。空值/无值时字段不占位，胶料两个分支（dataType=3 八位、dataType=5）统一生效；写法沿用本方法内 tf_R_PlanID 的 SetHidden 既有惯例。