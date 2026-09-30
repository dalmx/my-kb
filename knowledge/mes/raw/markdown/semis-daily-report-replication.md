---
category: 业务-通用
factory: 通用
module: Batch
status: active
tags:
- 索引落地回执
- SHIFT_DATE date型
- 优化确认
- EXTRA无主键
title: 部材作业日报（SemisDailyReport）Web 复刻实现方案
updated: '2026-09-04'
---

# 部材作业日报（SemisDailyReport）Web 复刻实现方案

> 项目：Batch（Web MES）｜复刻源：Semi 上位机 WinForms 作业日报（DayReportAction 按 EquipCode 前缀路由 11 窗体）
> 页面：`Plugins/Batch/Report/SemisDailyReport.aspx(.cs)`｜只读查询 + Excel 导出，无编辑
> 适用：上位机本地表数据要搬 Web 展示、多机台版式单页切换（动态多级表头）、跨表追踪反查拼装的场景。

## 一、数据链路双等价（业务确认，本方案基石）

| 上位机本地表（每台上位机自己的 [Semis] 库） | Server 等价表（MES 库） |
|---|---|
| `tb_PP_Output`（主数据+全部机台质检实测列 TM_/TC_/NY_/JH_/LY_/XC_/ZC_/ET_/GC_/JL_ 前缀、*_Set 仕样值、JLNums、LOCATION_NAME、PRODUCE_WIDTH 等） | **`HPP_SEMIS_PRODUCTION`** |
| `tb_QU_ProductTrace`（物料追踪：MainBarcode/SubBarcode/SubMaterName） | **`HPP_SEMI_LOT_DETAIL`**（推断列名 MAIN_BARCODE/SUB_BARCODE/SUB_MATER_NAME/SCAN_TIME，待列验证） |

Batch 网站连的正是 MES 库（SqlMapBatch.config）→ 同库直查；钢丝批号走 `MENS.dbo.Pmm_ReceiveCtrl/Pmm_StockBarCode` 三段名跨库（上位机 Server DB 同款）。基础字段映射：Barcode→CARD_NO、ProduceAmt→QTY、GroupId→CLASS_ID、MachineID→EQUIP_ID、ShiftDate(varchar yyyy-MM-dd)→SHIFT_DATE；追番拼接 `CLASS_NAME + RIGHT(EQUIP_ID,2) + '-' + BATCH_LOT`（上位机/GetBarcodeTracingInfo 双向一致）。

## 二、11 机台版式（单页 cmbEquipType 切换）

| value | 名称 | 票据号 | 专有列前缀 | JLNums 过滤 |
|---|---|---|---|---|
| TM | 胎面押出 | SQ-PD01 样式5 | TM_ | — |
| TC | 胎侧押出 | SQ-PD02 样式5 | TC_ | — |
| NY | 内衬层压延 | SQ-PD01 样式6 | NY_ | — |
| JH | 胎圈 | SQ-PG02 样式4 | JH_ | — |
| LY | 帘布压延 | SQ-PC01 样式1 | LY_ | — |
| XC | 钢丝帘布裁切 | SQ-PE01 样式4 | XC_ | — |
| ZC | 帘布裁断 | SQ-PE02 样式4 | ZC_ | — |
| ET | ET胶条分割 | SQ-PE04 样式4 | ET_ | **'1/16'** |
| GC | 钢丝圈 | SQ-PD01 样式6 | GC_ | — |
| JL1 | 冠带层一段 | SQ-PE03 样式3 | JL_ | **'1/6'** |
| JL2 | 冠带层二段分割 | SQ-PE03 样式4 | JL_ | **'1/24'** |

JLNums 过滤不带的版式会互相串数据（ET/JL 同机台前缀 JL），必须带。列头文案与多级分组照上位机 `Report_XX.Designer.cs` 的 label Text 还原；GC 六卷钢丝矩阵、JL2 24 段分割为宽表（横向滚动，与上位机一致）。

## 三、分层查询架构（对应上位机 BatchLoad* 逻辑）

一班几百卷内，.cs 端分层查询+内存拼装（贴近源逻辑，避免一条巨型 SQL）：

1. **主查询** `SelectSemisDailyList@HppSemisProduction`：HPP_SEMIS_PRODUCTION + SSB_CLASS，WHERE SHIFT_DATE/SHIFT_ID(isNotEmpty)/EQUIP_ID LIKE 前缀/QUALITY_SITUATION<>'错打'/JLNums(isNotEmpty)；机台专有列用 `$SelectFields$` 文本替换（.cs 白名单生成「,a.列 AS 列」，防注入）
2. **追踪** `SelectTraceByMainBarcodes@HppSemiLotDetail`：主结果 CARD_NO IN 批量取 SubBarcode
3. **BOM 工位**（4 分支 statement）：LY=非 COMP 首行、ET/JL2=BOM 首行、JL1=PLAN 物料、其余=按 STATION_NAME
4. **反查**（按版式启用）：半制品 HPP_SEMIS_PRODUCTION 自关联（JH/XC/ZC/JL2）、胶料时间 HPP_RUBBER_PRODUCTION（LY/GC/JL1）、钢丝 MENS 跨库（GC/JL1）
5. **拼装**（FillRow 按版式分支）：胶料条码位理解码照搬上位机（SubBarcode 不含"B"：yy=Substring(2,2)、dd=(4,2)、班=(8,1) 1白/3夜、start=(12,3)、lots=(15,3)）；工位映射 TM:CAP×2/UT/WT/ERTH、TC:BS/RC、NY:BTL/TAI/CHF、JH:FM(半制品)/BFL、LY:COMP×2+非COMP首行、XC:SCAL/ET、ZC:TCAL、ET:COMP、GC:COMP/WIRE×6、JL2:前8条；TG- 前缀去除、"(" 截断、2B 无 ET 显"/" 等口径全保留

抬头班别/作业员：HPP_SHIFT_MASTER（CLASS_NAME）+ HPP_SHIFT_DETAIL（作业员、顿号连接）。

## 四、文件清单（5 个，零新增实体/Data/Business）

| 文件 | 说明 |
|---|---|
| `Plugins/Batch/Report/SemisDailyReport.aspx(.cs)` | 页面 + code-behind（11 套列配置 Layouts 字典/分层查询拼装/动态列/导出/权限块） |
| `BusinessMapper/HppSemisProduction.xml` | +11 条 statement（主查询/半制品/钢丝/班次人员/BOM×4/字典/机台） |
| `BusinessMapper/HppSemiLotDetail.xml` | +1 追踪查询 |
| `BusinessMapper/HppRubberProduction.xml` | +1 胶料时间 |
| `resources/xls/Verify_SemisDailyReport.sql` | 列存在性验证 SQL（sys.columns 对照 + 一键 SELECT） |

SQL 全部 resultClass="Row" 走 DataTable，不依赖实体字段映射（HppSemisProduction 实体未映射质检列无妨）。权限：查询(btnSearch,1)+导出(btnExport,2)，只读无 EditActionId；菜单 SSP_PAGE_MENU 经 SetPageMenu.aspx 配置 `/Plugins/Batch/Report/SemisDailyReport.aspx`。

## 五、部署步骤

1. 重编译 `Wongoing.Batch.Mapper`（XML 是 EmbeddedResource）→ 替换网站 Bin 下 `Wongoing.Batch.Mapper.dll` → **回收 IIS 应用池**；
2. 页面 .aspx/.aspx.cs 为 CodeFile 动态编译，覆盖后首访即生效；
3. 用户连库跑 `Verify_SemisDailyReport.sql` 确认 11 版式依赖列在 HPP_SEMIS_PRODUCTION/HPP_SEMI_LOT_DETAIL 的实际列名（等价是推断，列名大小写无所谓但拼写/存在性要验证；不存在的列从 .cs Layouts 配置剔除即可，无需改结构）；
4. 系统内配菜单 + ACTION_ID。

## 六、开发过程踩坑（2026-09-04，已沉淀/修复）

1. **code-behind 引用 colModel/modelMain 报 CS0103**：`<ext:ColumnModel>/<ext:Model>` 是属性级元素，Website 模式无字段——须经 `gridMain.ColumnModel`/`storeMain.Model` 访问（详见 [[dynamic-column-grid]] 注意事项 6-8）
2. **Ext.NET 4.7.1 无 Ext.Net.ColumnModel 公开类型（CS0246）**：`var cm = gridMain.ColumnModel;`
3. **Column.Align 是 ColumnAlign 不是 Alignment（CS0266）**
4. **无 MSBuild 时的编译验证**：`aspnet_compiler.exe -v / -p <网站根> -u -f <临时目录>` 全站预编译（顺带验证 C#5 合规，v4 csc 即 C#5）
5. **designer 审查抓出 3 个阻断**：抬头缺 cdr-logo（系列 5 页都有）、cdr-c 底色应为 #f4f6f7（不是 #eaf2f8）、intRender 渲染函数 .cs 引用了但 aspx 没定义（XC 版式该列显示失败）——均已修复；另补 ToolbarSeparator、备注列 Flex=1 撑满
6. **ART_CODE 口径待验证**：主查询从 HPP_SEMIS_PRODUCTION 取 a.ART_CODE（上位机原口径来自 tb_PP_PlanDetail），若验证发现该列不在产出表，改为 join HPP_PLAN_DETAIL

## 七、关联文档

- [[dynamic-column-grid]] —— 动态列权威写法 + 本次 3 个编译坑
- [[curing-daily-report-implementation]] —— Batch 日报系列（表单式）
- [[semi-data-model]] —— HPP_SEMIS_PRODUCTION 字段详解、Server 端表清单
- 上位机源码（只读参考）：项目仓库 Semi 子系统"上位机页面/Report"目录

---

---

## 八、r2 修订：机台分类改三级联动（2026-09-04 业务新口径）

查询区从「机台类型（11 项硬编码）+ 机台号（前缀过滤）」改为**大类→小类→机台三级联动**（5 字段两行：日期/班次/大类/小类 + 机台）：

1. **三条联动 statement**（照业务给定 SQL 参数化，挂 HppSemisProduction.xml）：
   - 大类 `SelectMajorTypes@`：`SBE_EQUIP_MAJOR_TYPE WHERE EQUIP_DEPT_ID='04'`（部门 04=部材车间写死，页面加载查一次）
   - 小类 `SelectMinorTypes@`：`SBE_EQUIP_MINOR_TYPE WHERE MAJOR_TYPE_ID=#MajorTypeCode#`
   - 机台 `SelectEquipListByMinor@`：`SBE_EQUIP WHERE MINOR_TYPE_CODE=#MinorTypeCode#`（可空=该小类全部）
2. **版式推导** `DeriveEquipType(code)`（替代机台类型下拉）：取所选机台（未选取小类机台列表第一条）编码，**前 3 位优先**（JL1/JL2，覆盖 JL101→一段、JL201→二段）→ **前 2 位兜底**（TM/TC/NY/JH/LY/XC/ZC/ET/GC）→ 默认 TM。11 套 Layouts 配置不动
3. **主查询机台过滤** `LIKE #EquipPrefix#+'%'` → `IN ($EquipList$)`：选机台=单值；只到小类=该小类全部 EQUIP_CODE（值来自机台表查询非用户输入）；空列表拦截提示「该小类下没有机台」防 `IN ()` 语法错
4. **联动 DirectMethod**：`MajorChanged`（重绑小类默认第一项→链调）→ `MinorChanged`（重绑机台清空→QueryCore）→ `EquipChanged`（QueryCore）；前端联动前先 `clear()` 下级
5. ⚠️ **坑（r2 实证）**：Ext.NET ComboBox **没有 `SelectedIndex` 属性**（CS1061）——服务端设默认选中只能 `cmb.Value = code`（值在 Store 里有对应项即显示选中）；项目内也无 SelectedIndex 先例
6. 安全降级：若一段/二段（JL）机台同小类，选小类时 IN 列表含两类机台但 JLNums 按第一条推导——二段数据被过滤不显示（不串数据），需选到具体机台

---

---

## 九、r3 修订：按实库表结构定型（2026-09-04，用户跑列验证后给出三表结构）

**等价关系的实际形态**：`tb_PP_Output ≡ HPP_SEMIS_PRODUCTION（主表）+ HPP_SEMIS_PRODUCTION_EXTRA（扩展表，1:1 by CARD_NO）`——**全部机台质检实测列（TM_/TC_/NY_/JH_/LY_/XC_/ZC_/ET_/GC_/JL_ 前缀）+ IntervalTime/ScrewCleanTime/ProArtUse 都在 EXTRA 表**，主查询必须 `LEFT JOIN HPP_SEMIS_PRODUCTION_EXTRA e ON a.CARD_NO=e.CARD_NO`，`$SelectFields$` 生成 `e.列 AS 列`。

**列名映射表（上位机 → Server 实库）**：
| 上位机 tb_PP_Output | Server 实库 | 说明 |
|---|---|---|
| 质检/工艺专有列 | `e.HPP_SEMIS_PRODUCTION_EXTRA.原名` | EXTRA 表保留上位机 PascalCase 原名（varchar(10) 居多） |
| ProduceWidth | 主表 `Width`（numeric） | XC/ZC 宽幅实际值 |
| SplicingBarcode / SplicingAmt | 主表 `RETURN_SPLICING_CARD` / `RETURN_SPLICING_NUM` | 返回品条码/数量 |
| LOCATION_NAME | 主表 `LOCATION_CODE`（存 1B/2B/1P/2P） | 值即工位名 |
| INTERVAL_TIME/SCREW_CLEAN_TIME/PRO_ART_USE | EXTRA 表 `IntervalTime/ScrewCleanTime/ProArtUse`（原名） | |
| ART_CODE | `HPP_PLAN_DETAIL.ART_CODE`（join 计划明细取） | 不在产出两表 |
| Remark | 主表 `REMARK` | EXTRA 表另有一个 Remark 不用 |
| ShiftDate | 主表 `SHIFT_DATE`（**date 型**，非 varchar） | .cs 传 yyyy-MM-dd 字符串比较，隐式转换可接受 |

**追踪表 HPP_SEMI_LOT_DETAIL 真实列名（业务口径：LOT=子/SUB，MAIN=父/PARENT）**：
- MainBarcode → `PARENT_LOT_KEY`（父=产出条码，WHERE/分组键）
- SubBarcode → `LOT_KEY`（子=物料条码）
- SubMaterName → `LOT_MATERIAL_CODE`（**物料编码**，非名称）
- ScanTime → `SCAN_TIME` ✓

**匹配口径变更**：上位机"追踪行 SubMaterName = BOM 工位 MATERIAL_NAME"（名称对名称）→ Web 版统一为**编码对编码**：`TraceSubBarcode` 用 `LOT_MATERIAL_CODE` 匹配 BOM 的 `MATERIAL_CODE`（BOM statement 两列都返回，取 CODE 列）；页面"胶料号码"列显示编码。

**本次改动落点**：主查询 JOIN 两表（EXTRA+HPP_PLAN_DETAIL）+ 基础列映射别名（别名保持上位机原名 → DataIndex/列配置/导出零改动）；追踪 statement 列名改写；.cs 的 BuildSelectFields 前缀 a.→e.、LoadTrace/三个反查收集列名、TraceSubBarcode/BomName/FillRubberPair/LY 分支匹配口径。编译（aspnet_compiler）与 XML 良构复验通过。

---

---

## 十、r4 微修：SBE_EQUIP 关联小类的列名（2026-09-04 联调实测）

三级联动第 3 级（机台列表）`SelectEquipListByMinor@` 的 WHERE 列修正：`SBE_EQUIP` 表关联小类用的是 **`MINOR_TYPE_ID`**（列名叫 ID，存的却是小类编码值，如 '0101'），不是 MINOR_TYPE_CODE：

```sql
SELECT EQUIP_CODE, EQUIP_NAME FROM [dbo].[SBE_EQUIP] WITH(NOLOCK)
WHERE MINOR_TYPE_ID = #MinorTypeCode#   -- 传值=所选小类的 MINOR_TYPE_CODE
ORDER BY EQUIP_CODE
```

⚠️ 设备三表关联列名不对称（易踩）：`SBE_EQUIP_MAJOR_TYPE.EQUIP_DEPT_ID='04'`（大类按部门）、`SBE_EQUIP_MINOR_TYPE.MAJOR_TYPE_ID = 大类的 MAJOR_TYPE_CODE`、`SBE_EQUIP.MINOR_TYPE_ID = 小类的 MINOR_TYPE_CODE`——后两级都是"ID 列存对方 CODE 值"的口径。

---

---

## 十一、r4 微修补充：SSB_SHIFT 班次字典过滤（2026-09-04 联调实测）

班次下拉字典 `SelectShiftDict@` 补删除标志过滤（否则已停用班次会出现在下拉里）：

```sql
SELECT SHIFT_CODE, SHIFT_NAME FROM SSB_SHIFT WITH(NOLOCK)
WHERE DELETE_FLAG = 0
ORDER BY SHIFT_CODE
```

⚠️ 通用提醒：SSB_ 系字典表（SSB_SHIFT/SSB_CLASS/SSB_USER 等）都有 DELETE_FLAG，做下拉数据源时应带 `DELETE_FLAG = 0`；本页 SSB_CLASS 关联（追番拼接/抬头班别）为历史口径未加，若发现停用班组出现在追番里，同法补过滤。

---

---

## 九、r5 口径：排序与部材编号显示（2026-09-04 联调定版）

主查询 `SelectSemisDailyList@` 两处定版（业务确认）：

1. **排序按追番**：`ORDER BY c.CLASS_NAME + RIGHT(a.EQUIP_ID, 2) + '-' + a.BATCH_LOT`（原 BEGIN_TIME 排序废弃；BATCH_LOT 为 varchar，字典序排序）；
2. **「部材编号」列显示物料名称**：`LEFT JOIN SBM_MATERIAL m ON a.MATERIAL_ID = m.MATERIAL_CODE`，`m.MATERIAL_NAME AS MaterCode`（别名不变→页面/导出零改动；与上位机原口径 `c.MATERIAL_NAME MaterCode` 一致，TM/TC 的口型板仕样值取同值逻辑不受影响）。

---

---

## 十二、r6 口径：交互行为定版（2026-09-04 联调确认）

1. **切换大类/小类/机台只联动重绑下拉，不触发查询**——查询仅由「查询」按钮触发（前端 Search() 调 Query()；后端 MinorChanged 只 BindEquipList，EquipChanged DirectMethod 已删除；首屏 Page_Load 也不自动查询，待用户选机台后手动点查询）。
2. **机台必选**——不选机台不能查询：前端 Search() 校验 + 后端 QueryCore 兜底提示「请选择机台」；主查询机台 IN 列表恒为所选机台单值（不再有小类全部机台分支），版式直接按所选机台编码推导。
3. 无自动刷新（与上位机一致，业务确认不加）。

---

---

## 十三、r7 补充：大类/小类可清空与级联清空（2026-09-04 联调确认）

大类、小类下拉加清空触发器（FieldTrigger Icon="Clear"，纯前端操作不触发查询/重绑）：

- **清空大类** → 小类、机台一并清空（`App.cmbMajor.clear(); App.cmbMinor.clear(); App.cmbEquip.clear();`）
- **清空小类** → 机台清空
- 清空后再重选：Select 联动（onMajorChange/onMinorChange）会清下级并调 DirectMethod 重绑恢复默认项，行为自洽
- 机台下拉的清空触发器为纯 clear（不触发查询）；查询按钮对日期/大类/小类/机台全必填校验兜底

---

---

## 十四、r8 补充：追番排序 `-` 后段转数值（2026-09-04 联调）

r9 节的追番排序进一步定版：`BATCH_LOT` 是 varchar，字典序会把 '12' 排在 '2' 前面——排序键改为前缀（班名+机台号）字符串序 + 后段 `CAST(a.BATCH_LOT AS int)` 数值序：

```sql
ORDER BY c.CLASS_NAME + RIGHT(a.EQUIP_ID, 2) + '-', CAST(a.BATCH_LOT AS int)
```

注意：**显示**仍拼 varchar（`+ '-' + a.BATCH_LOT`），仅排序键转换；`CAST AS int` 要求 BATCH_LOT 全为数字（上位机批次号口径即纯数字，若日后出现非数字批次此排序会报转换错误）。

---

---

## 十五、r9 口径：编号/名称显示与匹配分离（2026-09-04 联调定版）

业务确认：**页面所有"编号/号码/品名"类列显示物料名称（SBM_MATERIAL.MATERIAL_NAME），追踪匹配保持编码对编码**（LOT_MATERIAL_CODE ↔ BOM MATERIAL_CODE，名称会因物料改名失配）。

实现模式（.cs）：
- `BomName(bomRows, station)` 返回**编码**——只用于 `TraceSubBarcode` 匹配与子条码收集；
- 新增 `BomMaterName(bomRows, station)` 返回**名称**（MATERIAL_NAME，空则退编码）——用于全部显示位；
- `FillRubberPair` 重载出 `(…, materCode, displayName, seq)` 双参版本：显示名与匹配码分离，TM(CAP1/CAP2/UT/WT/ERTH)/TC(SIDE/RC)/NY(BTL/TAI/GFS)/JH(BFL)/LY(COMP×2)/ET/GC 全部改走双参；LY 帘布 CAL_Name、XC(SCAL)/ZC(TCAL) 大卷钢帘布编号列、JL1/JL2 胶帘布品名同步改名称显示；
- JL2 顺带修复一个 r3 遗留失配：其追踪匹配原来传名称，现改传 MATERIAL_CODE。

主查询「部材编号」列（r5）同口径：`SBM_MATERIAL.MATERIAL_NAME AS MaterCode`。口型板仕样值（ProArtSet=部材编号同值/TG- 前缀处理）沿用 MaterCode（即物料名称）——如需编码再单独调。

---

---

## 十六、r10 口径：XC/ZC「部材名」列取 STORE_ID（2026-09-04 联调确认）

钢丝帘布裁切（XC）/ 帘布裁断（ZC，斜裁）版式明细第三列「部材名」的取值定版：**主表 `STORE_ID`**（工序），不再取 LOCATION_CODE——SQL 仍别名 `Location_Name`（页面列配置零改动）：

```sql
a.STORE_ID AS Location_Name
```

列宽 90→120（工序名长于 1B/2B 位号）。⚠️ XC 分支"2B 无 ET 站显示 /"的判断仍比对 '2B' 值——若 STORE_ID 实际值域不是 1B/2B 位号，该判断以现场实际值修正。

---

---

## 十七、r10：查询性能专家审查与优化（2026-09-04）

查询慢的优化遵循 [[sql-server-performance-troubleshooting]] 手册（连库禁令下：诊断脚本交用户跑，索引 DDL 带触发条件注释在脚本里）。

**逐语句体检结论**（9 类语句）：
- 主查询：SHIFT_DATE 实际类型存疑（半制品反查对它做 LEFT() 字符串截取且口径正确，暗示可能 varchar）——varchar 列 × 程序 nvarchar 参数 = 列侧隐转非 SARGable（手册原则 5），修法预案 `CONVERT(varchar(10), #ReportDate#, 23)`；`EQUIP_ID IN ($字面量$)` 反而 SARGable；无冗余 join/列
- 头号嫌疑：EXTRA 表 CARD_NO 无索引 → 百万级宽表全表扫；嫌疑 #2：追踪表 PARENT_LOT_KEY 无索引；嫌疑 #3：HPP_RUBBER_PRODUCTION.BARCODE
- ET/JL2 BOM 分支的 SBM_BOM.MATERIAL_PARENT_CODE 中嫌疑；抬头两条/字典类无嫌疑；反查三条已是版式互斥削减后形态

**已落地（.cs）**：反查 IN 列表统一 500 值分批（`QueryInBatches(values, runner)`，ImportRow 合并；分批按键划分不破坏组内顺序口径）；XML 零改动（体检确认语句层无可精简）。

**索引预案 DDL**（`Diagnose_SemisDailyReport.sql` 文末注释，诊断确认后启用）：
1. 主表 `(SHIFT_DATE, EQUIP_ID) INCLUDE (CARD_NO, PLAN_DETAIL_ID)`——前导 SHIFT_DATE Scan 时
2. EXTRA `UNIQUE(CARD_NO)`——无前导 CARD_NO 索引时（大概率主键已带）
3. 追踪表 `(PARENT_LOT_KEY) INCLUDE (LOT_MATERIAL_CODE, LOT_KEY, SCAN_TIME)`——覆盖 4 输出列消 Lookup
4. 胶料表 `(BARCODE) INCLUDE (PRODUCE_TIME)`——BARCODE 无索引时

**架构评估**：两段式窄查+宽查（Projection 下推收益有限）、服务端真分页（跨行拼装复杂度高）均不推荐；反查并行（Parallel.Invoke）列为索引落地后仍慢时的可选项。优先级：索引 >> IN 分批 > 并行。

**诊断路径**（用户执行）：`Diagnose_SemisDailyReport.sql` 5 段——行数基线 → 索引清单 → 列类型核对（SHIFT_DATE 隐转 A/B 对照：nvarchar 参数 vs varchar(10) 参数，Scan→Seek 即坐实）→ 执行计划取证（Ctrl+M，看主表 Seek/Scan、CONVERT_IMPLICIT、EXTRA join 算子、Key Lookup 占比）→ 结果回传模板。

---

---

## 十八、r11：优化落地（2026-09-04，不等诊断直接着手）

1. **SHIFT_DATE 参数侧显式转换已落地**（`SelectSemisDailyList` + `SelectShiftMasterInfo` 两处）：`SHIFT_DATE = CONVERT(varchar(10), #ReportDate#, 23)`——列是 date 时转换在参数侧仍 SARGable；列是 varchar 时消除列侧隐转。**两种类型场景通吃**，无需等类型诊断（诊断脚本第 3 段仍可跑留档）。
2. **幂等索引脚本** `Optimize_SemisDailyReport.sql`（用户整篇执行）：4 条预案 DDL 全带存在性守卫（按"索引名不存在 + 无同前导列索引"双查，已存在自动跳过打印提示），重复执行安全——把"先诊断再建"合并为"直接跑、守卫自判"。EXTRA 表 CARD_NO 用非唯一索引保证脏数据下也能建成（唯一性建议人工核对）。FILLFACTOR 90（有更新）/100（纯追加）；ONLINE=ON 仅企业版，默认不带。

---

---

## 十九、r12：优化结果确认（2026-09-04，用户连库执行回执）

**四条索引全部建成**（守卫脚本各条均打印 [完成]，说明四表此前确实都没有可用索引——EXTRA 的 CARD_NO 也不是主键，主查询 JOIN 此前是百万级宽表全扫，坐实头号根因）。

**SHIFT_DATE 类型定论：date 型**（EXEC 脚本收尾核对输出：SHIFT_DATE date / CARD_NO varchar(30) / EQUIP_ID varchar(20)）——此前"可能 varchar"的存疑排除（半制品反查 `LEFT(SHIFT_DATE,7)` 显示正确是 date 隐转字符串后截取，恰好可用）。r11 的 `CONVERT(varchar(10), #ReportDate#, 23)` 参数侧修法**保留**：date 列场景下转换在参数侧、SARGable 不受影响，且显式 ISO 格式对两类列都稳。

**数据字典同步勘误**：`semi-tables-data-dictionary.md` 2.3 节 SHIFT_DATE 的 date 型记载与实库一致（本次二次确认）。