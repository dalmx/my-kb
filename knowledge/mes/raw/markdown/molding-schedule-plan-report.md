---
category: 业务-通用
module: Molding
status: active
tags: [成型, 日程计划, 一次法, 二次法, MoldSchedulePlan, MoldSchedulePlanWeek, 周报表, PROC_TRA_MOLD_SCHEDULE_PLAN, PROC_TRA_MOLD_SCHEDULE_OP_TIME, PROC_TRA_MOLD_SCHEDULE_MOULD_COVER, PROC_TRA_MOLD_SCHEDULE_DOWN_TIME, 操业时间, 模套, mould_cover, bas_product_resource_mapping, v_MouldCoverCount, bas_factory_calendar, 工厂日历停机, 停机事件, 月份界限, 月桶分摊, "0401", "0402", 成型机小类, 钉顶表头, 十字定位, 导出xls, APS, 还原xlsx, 生产联络单, 繁转简, 列对齐, 占位格隐藏, CSS特异性, 自然周, 跨月周, 整表居中, 型号排序, 超库标红, 库入本数, OE库入量, REP库入量, CPP_TYRE_INBOUND_RECORD, 内联语句, 合计块, IISExpress, 大合计, GT合计, PLAN_TYPES, HAS_CLEANING, HAS_BREAK, 模具清洗, 模具段替, 试作量试标记, 导出标记色, FF92D050, FFCC99, FFFF00, indexed颜色, openpyxl读色, NPOI导出, xlsx格式复刻, 导出对齐手工表, DownMark, 双sheet, CHQY-R2版, 样式矩阵, decimal装箱, 合计块, 模具面数, NPOI, 导出xlsx, 列去重, DrawSumBlock, 反射测试, openpyxl断言, 排除未知, H列I列删除]
title: 成型机生产日程计划页面（一次法二次法 xlsx 原表还原，含周报表）
updated: '2026-09-29'
---

# 成型机生产日程计划页面（一次法二次法 xlsx 原表还原，含周报表）

> Molding/Report/MoldSchedulePlan.aspx（2026-09-03 群模式交付：CC 实现+reviewer/expert-sql/designer 三审+用户十轮实测迭代；2026-09-07 增量：补表头操业时间两行、二次法尾部模套块（独立表格）、全页繁转简、明细日格双 0 显示空；同日新增周报表 MoldSchedulePlanWeek；2026-09-10 周页整表居中、模套口径 v2；2026-09-18 型号显示序定稿 + 使用超在库标红；2026-09-28 增量：标题与日期之间加工厂日历停机行）。还原《CHQY-2026年N月生产计划》xlsx 的「一次法/二次法日程计划」sheet：四层表头 + 左6列主表 + 机台合并块 + 成对两行 + 合计块，数据链 = APS 库存储过程 → C# 0401/0402 分拣透视 → 前端自绘表格。

## 一、数据链路与页面结构（月报表）

```text
月份查询 → GetDataSetByStatement("SelectMoldSchedulePlan@BpmProduction")
  → APS.dbo.PROC_TRA_MOLD_SCHEDULE_PLAN @MONTH_FIRST（整月长表：日期×成型机×硫化产品）
  → C# 按 SbeEquip(MajorTypeId=04).MinorTypeId 分拣：0401=一次法页签 / 0402=二次法页签
  → 透视成 机台→产品 结构（成对两行 faces/qty 数组）手工 JSON
  → 前端 buildScheduleTable 自绘表格（两页签一次查询都填，Session 存透视对象供导出）

操业时间（表头第3/4层）→ GetDataSetByStatement("SelectMoldScheduleOpTime@BpmProduction")
  → APS.dbo.PROC_TRA_MOLD_SCHEDULE_OP_TIME @MONTH_FIRST（整月每天 × S/GREEN 两工序）
  → QuerySchedule 二查，填 string[] OpCure/OpMold（分钟/日，空串=无值留空）挂到 d1/d2

模套块（仅二次法尾部）→ GetDataSetByStatement("SelectMoldScheduleCoverUsage@BpmProduction")
  → APS.dbo.PROC_TRA_MOLD_SCHEDULE_MOULD_COVER @MONTH_FIRST（单结果集 UNION 两段：
     ROW_TYPE='D' 每日使用数（日期×型号×数量），'T' 在库总数（v_MouldCoverCount））
  → LoadCoverUsage 并集型号 → 按显示序排序 → d2.Covers（List<ScheduleCover>）
```

proc 输出 12 列英文别名：PROD_DATE/EQUIP_CODE/PRODUCT_NAME/SIZE_SPEC/ORDER_TYPES/PLAN_TYPES/QUANTITY/CURE_LIST/CURE_RATE/HAS_CLEANING/HAS_BREAK/MOLD_COUNT；页面消费 9 列（PLAN_TYPES/HAS_CLEANING/HAS_BREAK 留作后续格子标记扩展）。

## 二、版式要点（用户逐轮定稿，月/周报表共用）

- **月报查询控件（2026-09-18）**：dtMonth 日期选择器改月份模式——客户端 `Ext.onReady` 里 `App.dtMonth.type='month'; format='Y-m'; setValue(当前月)`（KB extnet-datefield-range-and-month 定式），弹出层只选年月不展开日历；显示值仍为 2026-09，后端 RawText/TryParseExact 零改动。周报保持日期(yyyy-MM-dd)选择器（取周需要天）。
- **四层表头**：日期数字（月报=1..N / 周报=周内实际几号）/ 星期 / 加硫操业时间 / 成型操业时间（操业时间两行 2026-09-07 起有数据：分钟/日）；制表日已删、右上角保留表单号 QY-WM-008 样式-2（导出仍留制表日）；周末列灰底已取消。
- **左侧 6 列主表**：成型机/加硫机/检测/Art.No./SIZE/加硫稼动率（xlsx 里的 INCH/Lay/BIC/模套/CB/各CT 仕样列按用户要求不还原）+ 行标签列（模具面数/计划本数）。
- **机台块**：成型机格 rowspan=产品数×2（2px 分隔线），每产品 5 属性格 rowspan=2 + 成对两行。
- **合计块**：标签一格 colspan=6 rowspan=2 + 成对两行按日汇总。
- **模套块（2026-09-07，仅二次法尾部）**：**独立一张 covertbl 表**（margin-top:14px 与主表间隔），每型号一行 = 5 个隐去占位格 + 在库 N（右对齐紧贴型号）+ 型号 + 逐日使用数 + 末列「MAX面数 N面」（比表头多一格，xlsx 原样）；**型号显示序 = S、G、E 固定在前，其余字母型号升序居中，'未知' 恒排末位**（2026-09-18 用户口径，LoadCoverUsage 的 CompareCoverType；在库有而无使用的型号也列出）；**使用数量 > 在库数量的日格标红**（红底 #e74c3c 白字加粗，class covex，2026-09-18 用户口径；在库空/非数字不比较，等于不标，仅"大于"标；页面+导出同步）；左区占位格隐去显示（transparent+去边框，保留 min-width 对齐作用），表级左/上边框去掉、可见部分自绘边框，模套块从「在库」起完整成框；行不挂 drow（无成对悬停），日格仍参与列十字高亮（跨两表标记）。详见 [web-table-column-align-guide](web-table-column-align-guide.md)。
- **列不锁定**，整表随 .sched-box 横向滚动；表头四层钉顶（sticky，详见 [extnet-sticky-header-merged-table-guide](extnet-sticky-header-merged-table-guide.md)）。
- 左6列+行标签 min-width：60/100/48/60/130/76/64px 防短数据压窄。
- **UI 精修（2026-09-18 用户"优化下表格UI"，纯 CSS 月/周两页同步）**：表头 hd=实底色 #e4ebf1+浅渐变叠加（**纯 background:linear-gradient 系 image 无 color 保底，浅值在 sticky 表头上观感"透明"被用户打回；表头必须 background-color 保底再叠渐变**）+ 操业时间行（四层末层）2px 收口线（钉顶时表头/数据区分更清晰）；单元格 padding 2px4px→3px5px、`font-variant-numeric:tabular-nums` 数字等宽；网格边框 #b8b8b8→#c9d2da 柔化；合计块底色 #eef7f7→#e7f2f2；模套行悬停浅反馈（covex 红格不参与，告警保持醒目）；.sched-box 细滚动条（thumb 圆角 #c3ccd4）。结构与交互零改动，还原报表骨架不动。第二轮追加：机台格左侧 3px 蓝色 accent 条+文字 #2c5f8a（宽表视觉锚点）；**产品成对行斑马**（奇数产品对 attr #f8fafc/日格 #fafcfd 淡底，machineBlock 给两行同挂 palt 类——第二行原本硬编码 drow 须一并带 cls）；块粗分隔线 #808080→#94a3b0 柔化（mach/blkstart/sumstart/sumend 四处）；covex 红格 2px 圆角；**MAX面数 定稿留在行末右侧列（2026-09-18 用户确认：试挪左侧后要求放回原位）——代价=模套表比主表宽约一列，窄视口下二次法页签会出表格滚动条，用户接受**；页级 `html,body{overflow-x:hidden}`（项目框窄视口下 Ext 布局会让浏览器页级多出一条横向滚动条，与表格自己的叠成两条——页级禁掉只留表格一条）。
- **繁体清零（2026-09-07）**：标题「日程計劃」→「日程计划」、表头「操业時間」→「操业时间」等全部改简体（真繁体字集程序扫描归零；导出 Excel 标题同步）。

## 三、透视与显示口径（自行决策项，用户认可）

- 加硫机列 = 当月各日 CURE_LIST 认领列表按序去重合并（空格分隔，如 "J105L J111"）；加硫稼动率 = 各日均值/100 保留两位（xlsx 口径 0.92）；检测 = 首个非空 ORDER_TYPES。
- faces 当日取大 / qty 当日累加（长表粒度理论上一天一行，防御性处理）；机台编码升序，产品按首现日期+制造编号。
- **明细日格双 0 显示空（2026-09-07 用户口径）**：模具面数/计划本数同日两值都为 0 时该日两格显示空（无计划的天不铺 0）；单边为 0 保留显示；合计行照常显示数值。页面 dayPairedCells(own, other, cls) 与导出 DetailCell(v, paired) 同口径成对判断。
- **操业时间口径**：S=加硫、GREEN=成型，每天基数 1440 分钟减当日停机分钟（停机区间按天裁剪并合并重叠/相接岛屿，跨天记录自动拆到两天，与月生产计划报表 calcWorkingDays 及 Java mergeIntervals 口径一致）；工厂级口径，一次法/二次法两页签共用同一组值；无值留空。验证：2026-09 停机 09-25 08:00~09-26 08:00 → 09-25=480、09-26=960、其余 1440。
- **模套口径（v2，2026-09-10 用户更新 SQL）**：当天硫化计划（tra_cur_production_assignment，delete_flag='0' 且 JOIN tra_manufacture_order_pro 隐含 mfg_order_pro_id 非空，NOT EXISTS 剔除试作 bom_type=2/process_code='S'）；**模套型号 = 按 a.product_code 经 bas_product_resource_mapping（enable=1，TOP 1）映射到 bas_resource.mould_cover，无映射记 '未知'（OUTER APPLY + ISNULL）**；**数量 = COUNT(\*) 行数（每条分派行代表一副模具）**，v1 的 COUNT(DISTINCT mold_code) 与 mold_code IS NOT NULL 过滤均已废弃（**mold_code 字段不准、有空值，勿再依赖**）；在库=dbo.v_MouldCoverCount 视图直取（项目内无定义、APS 库既有视图，InsightChart 同源；**两种命名并存（bas_resource.mould_cover 使用侧也有 LM/RV 值）——C# 读出 COVER_TYPE 后统一映射 LM→G、RV→E，使用/在库两侧同域合并（2026-09-18 用户口径；只映一侧会多出 LM/RV 孤行）**；查看定义 `EXEC sp_helptext 'dbo.v_MouldCoverCount'`；若口径不合需求应改 proc 内嵌计算而非动视图——动视图会影响 InsightChart）；型号集合取使用∪在库并集；**显示序 = S、G、E 固定在前（xlsx 原表序），其余字母型号升序居中，'未知' 恒末位（2026-09-18）**；**超库告警 = 日使用数 > 在库数时该日格红底白字（2026-09-18，仅"大于"，在库缺失不比较）**；MAX面数=周期内逐日峰值（月报=当月/周报=周内）；全厂口径不分方法，只显示在二次法页签；无计划日不补零留空。
- 导出：同结构 HTML 表 .xls（vnd.ms-excel + UrlEncode 文件名「一次法/二次法日程计划yyyy-MM」），按当前激活页签（SetTab DirectMethod + Session）；模套块仅二次法导出带（独立一张表，中间空一行；Excel HTML 导入按列位置共享工作表列，covstock colspan=6+型号 1 列=7 列与主表日列起点一致天然对齐；超库标红同步导出）。
- 操纵留白：计划类型/洗模/段替三列未展示、二次法页签无「(一次法+二次法)合计」、一次法页签无模套块。

## 四、部署链与文件清单

1. 2026-09-03：用户在 **APS 库**执行 `SQL\UPGRADE_20260903_MoldSchedulePlan.sql`（主表 proc）——已执行，真数据验证过（一次法 110 行/二次法 34 行）。
2. 2026-09-07：用户在 **APS 库**执行 `SQL\UPGRADE_20260907_MoldSchedulePlanOpTime.sql`（操业时间 proc）——已执行（实机页签已出 480/960 数据）。
3. 2026-09-07 v1 已执行；**2026-09-10 v2 口径更新：重跑 `SQL\UPGRADE_20260907_MoldSchedulePlanMouldCover.sql`**（DROP IF EXISTS 幂等重建；型号改 product 映射+未知桶、数量改 COUNT(*) 行数）；页面/Mapper/dll 零改动（输出列不变）。注意 dbo.v_MouldCoverCount 不带库前缀，若报「对象名无效」说明视图在 MES 库，改 MES.dbo. 前缀重建。
4. Mapper dll 已重编拷入 Bin 免重启（含三条语句，备份 tmp/mapper-backup-20260907/cover-prefix）。
5. 挂菜单：`~/Plugins/Molding/Report/MoldSchedulePlan.aspx` 与 `~/Plugins/Molding/Report/MoldSchedulePlanWeek.aspx` + 各自授权：查询(btnSearch,1)/导出(btnExport,2)。
6. 文件：月/周页面 aspx/aspx.cs 各一对（免注册）、BpmProduction.xml 三条语句（SelectMoldSchedulePlan / SelectMoldScheduleOpTime / SelectMoldScheduleCoverUsage）、Bin 的 Wongoing.Molding.Mapper.dll。
7. 交付全记录：`pi-handoff/report-20260903-1044-mold-schedule-plan.md`（二十一节，含三审结论与每轮返工）。
8. **2026-09-28 停机行增量**：用户在 **APS 库**执行 `SQL\UPGRADE_20260928_MoldSchedulePlanDownTime.sql`（停机事件 proc，幂等 DROP 重建）——待执行；Mapper 已加第四条语句 SelectMoldScheduleDownTime 并重编拷入 Bin（备份 tmp/mapper-dll-backup-20260928-downtime）；月/周 aspx 四文件更新（动态编译）；无菜单/授权变更。

## 五、跨表列对齐（模套块 vs 主表，2026-09-07 三轮实机闭环）

模套独立表格与主表**不共享网格**，日列必须逐列对齐，三层坑全踩过（通用套路沉淀为 [web-table-column-align-guide](web-table-column-align-guide.md)，此处记本页实测定稿）：

- **对齐机制**：模套行前 7 格（含隐去的占位格）+ 全部日格，逐格 `style.min-width = 主表行2 对应列 getBoundingClientRect().width`（border-box）；`document.fonts.ready` 后重跑一次（幂等）。
- **三层坑**：① `style.width` 在 auto 表格布局只是提示值，表格收缩到容器宽时被压掉（534px 压成 54px）→ 必须 `min-width`；② colspan 大格上的宽度会被浏览器**分摊到所跨虚拟列**锁不住总宽 → 左区拆 7 个独立格逐格对齐；③ 主表日列被操业时间「1440」撑到 ~38.4px 而模套表两位数值只到 34px 下限（日列不同步右侧累计偏 ~40px），且 `offsetWidth` 只回整数每列丢 ~0.39px/30 列累计 12px → **日列也要逐列同步 + 必须用 getBoundingClientRect().width 含小数**；④ **跨内核坑（2026-09-18）**：部分 Chromium 版本对表格格子 min-width 按 content-box 计（同步值再多出 padding+border 逐列漂移），IAB 内核按 border-box——**所有被同步格（含 td.day）必须显式 box-sizing:border-box**。
- **占位格隐去**（用户口径"在库左边的格子不要显示"）：占位格保留占位（min-width 对齐依赖）但 transparent+去边框；covertbl 去表级左/上边框防悬空线，首行可见格自补 border-top、covstock 补 border-left。**特异性坑**：`tr.covrow td` 底色规则 (0,3,2) 盖得过 `td.covpad` (0,3,1)，隐藏规则必须写 `tr.covrow td.covpad` (0,4,2)。
- **实测定稿**：diffDay 首/中/尾 = 0（占位格隐去后 -0.8px 均匀亚像素偏移，125% DPI 下 1 设备像素，不可见）；两表间隔 14px；30 日格宽度与主表逐列一致（38.4/38.4/37）。
- **排障实录**：内置浏览器受控页签 → 点查询 → `getBoundingClientRect().left` 量两表同序日格差（首/中/尾三点）。视觉模型两轮均误判（14px 间隔判成无间隔、末日无计划的留空数据格判成缺列）——**数值测量为准，视觉复核只作参考**。

## 六、周报表 MoldSchedulePlanWeek（2026-09-07 增量，同数据零 DB 改动）

- **定位**：同数据换查询粒度——自然周（周一~周日 7 天）视图，版式/口径与月报表完全同款；`Plugins/Molding/Report/MoldSchedulePlanWeek.aspx`(.cs)。
- **数据链零新增**：复用同三条语句/proc，不动数据库、不动 Mapper、不重编 dll；纯两页面文件，部署=拷文件。
- **周口径**：查询条件=日期（yyyy-MM-dd，默认今天，选周内任意一天）→ `WeekStart=((int)DayOfWeek+6)%7` 前移到周一；**跨月周自动并查**——取周起/周止所在月首日去重（1~2 条 MONTH_FIRST），逐月调 proc 后 DataTable.Copy+Merge 合并长表，C# 再按 weekStart~weekEnd 过滤、日索引=(日-weekStart).Days。
- **与月报表的差异面（全部且仅这些）**：层1 日期数字=后端 dates（周内实际几号，跨月周如 31,1,2..6 也能正确显示）；层2 星期=列位固定 一~日（第1列=周一）；标题/文件名带周区间与（周）后缀（如「2026-09-07 ~ 09-13 一次法成型机生产日程计划（周）」）；模套块 MAX面数=周内峰值、在库仍取月值现值；机台块只出现周内有计划的机台/产品。
- **整表居中（2026-09-10 用户口径）**：周表只有 7 天列填不满容器，报表整体水平居中——`innerHTML` 外包一层 `<div class="week-wrap">` 同时包住主表+模套表，`.sched-box .week-wrap { width: max-content; margin: 0 auto; }`。**不能两表各自 margin:0 auto**（模套表多 MAX 列更宽，各自居中会把左缘错开、日列对齐全毁）；容器宽=最宽子表，两表左缘关系不变、整组居中；表格超宽时 margin 塌 0 退化为滚动；sticky 表头不受包裹层影响。离线实测（1500px 容器/内容 ~1210px）：左右边距各 145.0 完美居中，diffDay1/diffDay7=0.0 对齐不破。月报表不居中（宽表贴左滚动，用户未要求）。
- **双胞胎页面维护提醒**：周报 aspx 的 CSS/JS 为月报全量拷贝+点改（CodeFile/标题/日期控件/Search入口/wk函数/日期表头/标题行/空数据文案/week-wrap 居中），**月报版式或交互再定稿改动须两页同步**（同 Semi/BeltTension 拷贝先例；模套排序 CompareCoverType、超库标红 covex、2026-09-28 工厂日历停机行两页已同步）；Session 键用 MoldSchedulePlanWeek_* 隔离。
- **验证状态**：静态全绿（C#5 csc EXIT 0、JS 括号配平、繁体扫零、与月报 diff 仅目标改动）；样式预览=tmp_preview/MoldSchedulePlanWeek_preview.html（Chrome 无头截图+视觉复核通过）。**运行时实测待用户环境**（本地 IIS Express 随 VS 起停，未登录无法代验；勿绕过认证）。
- 排障附记：本机 55721 站点由 VS 起的 IIS Express 托管（.vs/Wongoing.MESWeb.Molding.2013/config/applicationhost.config，site=Wongoing.Molding.WebSite）；项目未开时端口不在、页面空白属正常。ZCode 可用 `iisexpress /config:... /site:Wongoing.Molding.WebSite` 临时拉起验证，**用完必须停掉还端口**（否则 VS 再开项目会端口冲突）；新进程无登录会话，页面会跳登录，不要绕认证。

## 七、同款数据源的其他知识

- proc 口径注释头即文档：贪心认领与生产联络单 matchCurDevicesByFaces 一致、稼动率=滚动30天停机公式（车间04）、段替=寸别变化日（前推7天种子）、版本流/手工流两流取大等。
- xlsx 结构参照：两个 sheet 布局一致（机台 C101~C307=一次法 21 台 / C601~C608=二次法 8 台，与 0401/0402 小类对应）；横向 1..31 日列、盘点/TPM 标记行（未还原）；二次法 sheet 尾部有模套使用块（2026-09-07 已还原，型号 S/G/E 即 xlsx 原表三型号）。
- 复杂批处理/多结果集不能进 Mapper → 包装 proc 建 APS 库 + `<procedure>@{参数,column=列}` 跨库调用，多段结果用 ROW_TYPE 判别列 UNION 成单结果集（模套 proc 先例），详见 [ibatis-hash-temp-table-to-proc](ibatis-hash-temp-table-to-proc.md)。

## 八、合计块库入三行（2026-09-18 增量）

- 需求：一次法/二次法合计块增加三行——**库入本数（=OE+REP）、OE库入量、REP库入量**；合计块由成对两行变五行（标签格 rowspan=5，五行 data-pg=SUM 整组联动，REP 行收底边框）。
- **数据链（内联语句，无 proc）**：CPP_TYRE_INBOUND_RECORD×SPP_TYRE_GRADE×BPM_PRODUCTION×SBE_EQUIP 全是 MES 表、无 #临时表 → 直接进 Mapper `<select>`：`SelectMoldScheduleInbound@BpmProduction`（CDATA，参数 #BEGIN_TIME#/#END_TIME#，英文别名 IN_DATE/TYRE_CLASS/IN_COUNT/MINOR_TYPE_ID）；月报传月区间、**周报直接传周区间（无需双月并查）**。用户 SQL 唯一适配=补上界 `< #END_TIME#`（原 SQL 只有下界会查全历史）。
- **口径**：TYRE_CLASS_VALUE isnull 默认 'REP'；仅 OE/REP 两类计入（其他等级值忽略，库入本数严格=OE+REP，C# SumStringArrays 求和、双空=空）；MINOR_TYPE_ID 分 0401→一次法页签 / 0402→二次法页签（SBE_EQUIP 未匹配到设备的行 MINOR_TYPE_ID 为 NULL 自然落不进两页签）；当日无入库显示空（与操业时间/模套口径一致）。
- 部署：Mapper 重编拷 Bin（含该语句，备份 tmp/mapper-backup-20260918-inbound）；页面文件动态编译；无 DB 脚本。
- 实测（离线 mock）：sumlabRowspan=5、五行序正确、库入本数=OE+REP 逐日吻合、空日留空。

## 九、(一次法+二次法)合计块（2026-09-18 增量）

- 需求：二次法页签在「二次法合计」之后再增加「(一次法+二次法)合计」；位置=主表内、二次法合计块之后、模套表之前（列对齐/钉顶/悬停十字全继承，避免第三张表）。
- 结构：与合计块同款五行（模具面数/计划本数/库入本数/OE库入量/REP库入量），标签格 colspan=6 rowspan=5，data-pg=GT 独立整组联动（与 SUM 组分开），底边框由 GT 的 REP 行收口；两合计块间的 2px+2px 双线分隔与机台块间样式一致。
- 数值：d1+d2 逐日相加（GTFaces/GTQty=SumIntArrays；gtIn 三行=SumStringArrays 复用，双空=空）；仅 d2 填充（GTFaces null=不渲染），一次法页签无此块；导出同步（GTFaces 非空时输出同结构五行）。
- 纯页面改动（aspx/aspx.cs 月+周四文件），零 Mapper/dll/DB 变更；离线 mock 实测 rowspan=5、行序正确、数值相加吻合。

## 十、工厂日历停机行（2026-09-28 增量，月/周两页同步）

- 需求：标题与日期（四层表头第一层日数字行）之间增加「工厂日历停机」行——bas_factory_calendar 维护的工序停机事件按日展示（事件名+时长，如 中秋节24H）。
- **数据链（第四条 proc 语句）**：proc = `APS.dbo.PROC_TRA_MOLD_SCHEDULE_DOWN_TIME @MONTH_FIRST`，Mapper `<procedure id="SelectMoldScheduleDownTime@BpmProduction">`；**来源=用户 2026-09-22 在 APS/APS_BOX 实测通过的独立 SQL**（国庆 10-01 00:00 起停机 → 10-01 显示 32H），四处适配：入参化（删 DECLARE @month）、英文别名拆列（FACTORY_DATE/EVENT_NAME/DURATION/EVENT_TIME——页面用 name+duration 分两行显示，EVENT_TIME=原口径连写列）、bas_factory_calendar 补 NOLOCK、时长 CASE 抽 dur CTE；脚本=`SQL\UPGRADE_20260928_MoldSchedulePlanDownTime.sql`（USE APS + DROP IF EXISTS 幂等）。
- **口径（proc 注释头即文档）**：工厂日=当天 08:00~次日 08:00，**月份界限按每月 1 号 00:00 切开**——1号桶=[1号00:00,2号08:00) 32H、月末桶=[当天08:00,次月1号00:00) 16H、其余 24H，整月 N 桶无缝分完；同一事件四工序（S/GREEN/PART/MIX）各一条按 起止时间+事件名 去重，**同名事件重叠区间合并成一段（gaps-and-islands 并集，不重复计时）**；时长整小时 NH、不整 NHM（结束时间维护到秒）；工厂级口径两页签共用一组值；显示=事件名`<br>`时长两行、同日多事件 `<br>` 连接（proc 按 日期+事件名 升序拼接）、空日留空。
- **版式（dtrow）**：`<tr class="dtrow">` 插在 title 行与 headRows 之间=行索引2；左6列区 `<td class="dtpad" colspan="6">` 白底去边框占位（**白底非 transparent：钉顶时挡住滚过内容**）；行标签「工厂日历停机」（6字与加硫操业时间同宽不撑行标签列）；日格 td.day.dtcell **white-space:normal 防长事件名撑宽日列**——内容按 `<br>` 分行，最长段≈3汉字，实测日列仍 ~39.2px；参与钉顶与日列十字高亮（挂 td.day 类即自动纳入 toggleCross 列高亮）。
- **⚠️ 两个必须联动的既有机制**（月/周两页同改）：① `applyStickyHeader` 钉顶循环 2..5 → **2..6**（行2=停机行、行3..6=四层表头，偏移照旧整数 top 递推）；② `alignCoverTable` 选 mainRow 时**必须跳过 dtrow**——停机行左区是 colspan=6 占位格，格子数不与主表列一一对应，不跳过会被当成宽度源把模套表对齐全毁（`rows[r].className.indexOf('dtrow')>=0 continue`）。
- 周报同步：跨月周逐月调 proc（1~2 次）后 `FillDownTime` 按**实际日期**入周桶（日索引=(日-周一).Days），跨月的 1 号列用该月自己的月桶口径值，与月报显示一致；月报单次调用 `LoadDownTime` 按日-1 入桶。导出两页同步（DownCell：空日 `&nbsp;`，Xd 的 nowrap 不拦 `<br>` 换行）。
- **旧会话兼容**：Session 里旧透视对象无 Down 字段=null，页面 AppendStringArray(null)=空数组、导出 DownCell(null)=&nbsp;，不炸。
- 验证：C#5 csc 双页 EXIT 0（dtMonth/dtWeekDate 控件字段桩补）；JS 语法绿+六项存在性断言（dtrow/dayDown/sticky6/skipdt/css/label）；离线 mock（国庆32H/年度定期保全8H/中秋24H/双事件日）Chrome 无头数值断言全过——停机行在行2、30日格、钉顶5行、日列39.2px、模套 mainRow 正确选日数字行、多事件日 4 段 `<br>`；模套列差 ~1px 隔离实验（隐藏 dtrow 重对齐差值不变）证明为环境亚像素、与新增行无关；截图视觉复核（事件两行显示、无溢出错位）。**运行时实测待用户环境**（须先跑 UPGRADE proc）。

---



## 十一、导出计划本数行标记色（2026-09-28 增量，月/周两页同步，仿 xlsx R2 版图例）

- 需求：导出 Excel 仿《CHQY-2026年N月生产计划-R2版.xlsx》——机台块**计划本数行日格**按标记着色：PLAN_TYPES 后两个字符 / HAS_CLEANING 模具清洗 / HAS_BREAK 模具段替。仅导出（页面自绘表格未标色）；PLAN_TYPES/HAS_CLEANING/HAS_BREAK 三列 proc 早已输出（此前留作扩展，本次消费）。
- **xlsx 图例考证（openpyxl 逐格扫描）**：两 sheet 表尾图例（一次法 R582-585/二次法 R320-323）——「试作、量试」swatch=旧调色板 **indexed 13=FFFF00 黄**、「模具清洗」swatch=indexed 50=99CC00 但**数据区实际涂 FF92D050 亮绿（55 格，取实际色）**、「模具段替」swatch=indexed 47=**FFCC99 奶橙**（数据区为 theme accent6 F79646@tint0.4≈FAC090，视觉同橙系，取图例 FFCC99）；另「设备点检」=accent2 淡红（未实现）。标记全部落在**计划本数行**日格（xlsx 本数行另有整行浅绿底 CCFFCC，页面/导出均未还原，用户未要求）。索引色/主题色解析：openpyxl start_color.type=indexed/theme 时查 `COLOR_INDEX[i]` 或 theme1.xml（本簿=Office2007 默认主题）；「先行/收尾/正常」图例无色→不标。
- **数据链（零 DB/Mapper/dll 改动，纯 aspx.cs）**：PivotSchedule 透视时从长表行补三组逐日标记挂 ScheduleProduct：`PlanType[d]`=PLAN_TYPES.Trim() 取 **Substring(Length-2)**（最后一个类型词，proc 值域=正常/先行/试作/收尾/量试，'/' 连接）、`Cleaning[d]`=HAS_CLEANING 非 DBNull 且 ≠0（清洗计数）、`MoldBreak[d]`=HAS_BREAK ≠0（proc 已 ISNULL 0）；数组不入页面 JSON（导出专用，Session 随 ScheduleProduct 持久化）。
- **着色规则 MarkStyle(p,d)**（月/周同款静态方法）：优先级 **清洗绿 #92D050 > 段替橙 #FFCC99 > 试作/量试黄 #FFFF00**（同日多标记取高者——xlsx 手工表一格一色；优先级为自定，可调）；先行/收尾/正常/无标记=""；null 数组（旧会话 Session 对象）安全返回空。导出落点=计划本数行 `Xd(DetailCell(...), MarkStyle(p,d), 0, 0)`（原 style 空串处）；**表尾追加图例行 LegendHtml()**（三色块 span+文案，仅三项不含设备点检）。
- 验证：C#5 csc 双页 EXIT 0；**反射实测编译产物**（check dll 拷 WebSite Bin 旁加载依赖，PowerShell FieldInfo.SetValue 须显式 [string[]]/[bool[]] 转型）——8 用例全绿：叠加→绿、段替+试作→橙、试作/量试→黄、先行/正常/空串/null→空；LegendHtml 输出三色块正确。运行时导出实测待用户环境。

---



## 十二、页面标记色与图例（2026-09-28 二次增量，月/周两页同步；排障实录见本节尾）

- 需求演进：先只做导出标记色（第十一节），用户反问"为什么 web 展示没有标记"→ 页面同步同款标记色+图例。**页面与导出现同口径**：计划本数行日格，清洗绿 92D050 > 段替橙 FFCC99 > 试作/量试黄 FFFF00，面数行不标。
- **数据链**：BuildMarkChars(p, dayCount) 把透视对象三标记压成 `mk` 字符数组（'C'/'B'/'T'/''，与 MarkStyle 同优先级）→ BuildScheduleJson 产品对象追加 `"mk":[...]`（AppendStringArray，稀疏空串多数）；JS dayPairedCells 加第 4 参 mk，qty 行传 p.mk（faces 行不传），格子 class 拼 `mk'+m.toLowerCase()`；页面底部 legendBlock() 三色块图例（.sched-legend/.sw，周报在 week-wrap 外避免影响居中组宽度）。
- **本轮两个真坑（mock 断言抓出，均已修）**：
  1. **class 大小写坑**：后端标记字符大写 C/B/T，JS 直接拼 class 得 `mkC/mkB/mkT`，CSS 定义 `.mkc/.mkb/.mkt`——CSS 类选择器大小写敏感，标记全失效（getComputedStyle 全白底）。修=JS `m.toLowerCase()`。
  2. **斑马特异性坑（covex/covpad 同款再现）**：标记规则 `.sched-box .sheet td.day.mkc` (0,4,1) 被斑马 `.sched-box .sheet tr.palt td.day` (0,4,2) 盖过——**奇数产品对（palt 斑马行）的标记色变成斑马浅底**，只有偶数对显色。修=标记规则带 `tr.drow` 前缀升到 (0,5,2) 稳压。教训：给页面日格加底色类，必须先查同格位全部 background 规则的特异性（斑马/悬停/十字/covex 全在）。**同日全面排查（用户要求检查其他导出错误）**：①合计/GT 标签块 AddMergedRegion 清非首行上下边框（与签名区同坑，块底边中粗缺失）→merge 后重设 MS_LABBOX（四边中粗专用样式，勿用边缘矩阵样式——首行样式 bottom 是 Thin 不够）；②周报 HTML 导出在库 `Stock==""` 漏 null（未知行会显示裸'在库 '字样）→IsNullOrEmpty；③其余写入路径逐一核查无恙：DrawSumBlock 各 TryParse 均在 `xx!="" && TryParse` 三元条件内（写入受同条件保护，短路坑不成立）、操业/稼动率独立三元、双 0 判空、DownMarks/Daily/OpCure ?? 保护、decimal 已修、周报 HTML 模套写入用原字符串 v 非解析值（无短路坑）、页面 JS parseInt 独立。
- 排障附记（用户报"没有看到标色的单元格"三轮定位）：①端到端反射调 BuildExportHtml 证明导出链路无 bug（mock 试作→HTML background:#FFFF00 输出正确）；②用户贴 proc 输出 PLAN_TYPES 大量试作→数据素材充足；③根因=最初只做了导出（用户原话"导出样式"），页面未标——用户实际两者都要。另加**旧查询缓存防呆**：btnExportSubmit_Click 检查 `Machines[0].Products[0].PlanType==null`（部署前查询缓存的 Session 对象）→ 弹"请重新点击查询后再导出"（月/周同款）。
- 验证：csc 双页 EXIT 0；JS 语法绿；mock（T/C/B 各一日+斑马行 T+无标记日）Chrome 无头断言全绿——qty 行 class/计算色 rgb(255,255,0)/rgb(146,208,80)/rgb(255,204,153)、面数行无标记、斑马行标记格显黄、图例 3 色块在 box 内。运行时待用户环境。

---



## 十三、导出 xlsx 逐格复刻手工表（2026-09-28 三次增量，月报单页，NPOI 双 sheet）

- 需求："导出格式对齐手工表格"（用户指路 KB 已沉淀技法）——月报导出从 HTML .xls 整体切换为 **NPOI 真 xlsx**，按 [[npoi-format-replication]] 分区对齐工作法逐格复刻《CHQY-2026年N月生产计划-R2版.xlsx》。**一次导出双 sheet**（一次法日程计划+二次法日程计划，对齐手工表整本结构，不再按激活页签分次导）；文件名`成型机生产日程计划yyyy-MM.xlsx`。纯 aspx.cs 单文件改动（NPOI.dll 全家桶 Molding Bin 已有），零 DB/Mapper/dll。
- **手工表底图（openpyxl 逐格 probe 的版式规格，还原依据）**：列 0 空边距|1 成形機|2 加硫机|3 检测|4 Art.No.|5 SIZE|6 加硫稼动率|7 本数行=检测+Art(如 REPS3538)|8 本数行=产品号|9 行标签|10.. 日列|空1列|计划本数合计|库入本数(=合计×合格率0.98)。**初版曾复刻手工表 G-R 十二仕样列（INCH/Lay/BIC/模套/CB/开合模T/加硫T/模具在库/成型CT/材料交换CT/成型段替CT/成型稼动率），用户验收后要求删除（"G-R 列不需要"，2026-09-28 同日）——列整体收窄左移（cDay=10、冻结 K9、模套块 MAX/H 在库/I 型号/J、合计标签合并 B..I），ExtractInch 随删**。同日追加：**冻结改 A..E**（CreateFreezePane(5,8)，用户口径"锁定列到E"）；**比率格（加硫稼动率/合格率0.98）数字格式 0%**（存值不变 0.92/0.98，显示 92%/98%；页面仍显示 0.92 未同步）。同日再补：**合计/GT 块改 5 行制**（用户指出缺模具面数/库入本数——与页面合计块同序：模具面数/计划本数/库入本数/OE库入量/REP库入量，标签合并 B..I 跨 6 行，库入本数行取 InTotal；手工表 3 行制弃用）。同日列宽整体加宽（用户反馈"部分列列宽不够"）：SIZE 13→19、加硫稼动率 6→10.5（5 汉字表头原被截）、日列 6→7（五位数原会 ####）、行标签 12→13、检测+Art 9→10、产品号 6→7.5、成形機 6→7、检测 5→5.5、Art.No. 7→8、统计列 9→10.5（double[]+SetColumnWidth(int)(w*256) 支持半字符）。同日再修三处（用户验收）：①合计/GT 块不再写统计列（"合计不需要计算AP列"，产品行统计列保留）；②**签名区**（用户改样定稿，终版=以用户手改文件为准）：**日列右端末 8 列**（cSig=cDay+N-8）、角色格 2 行×2 列（批准/审核/审核/作成，微软雅黑11粗居中，行高 16.8/14.4）+ 下方**签名空位 4 行×2 列合并**，与左侧备注（挂角色第 2 行）/图例 4 行**并排**，保管期限收尾——初版 B..I 横排被用户打回；同日第四轮（用户验收四点）：①合计/GT 块改 **4 行制**（计划本数/库入本数/OE/REP，模具面数移出）；②**模具面数独立行**（仅二次法 sheet，标签@J+逐日值=GTFaces d1+d2，位置夹在二次法合计与 GT 块之间）；③模套块改版：表头仅 在库@H，每行=在库@H(浅绿)|空I|型号@J|日值|**BB 列(统计列位 cStat1)"MAX面数 N面"粉红底 FF9999 左中粗 Arial10B（样式位置照手工 R2 二次法 BB302:BB304 实探）**，MAX 数值列删除；④判定行移 **F 列**（SIZE 列下），OK 判定=每行 MaxUse<在库 全满足（有超即 NG）；**第五轮**：⑤判定**排除"未知"型号行**（无有效映射不参与 OK/NG）；⑥**删 H/I 两标识列**（检测+Art、产品号），布局再左移两列（cDay=8、行标签@H、合计标签合并 B..G、模套=在库@G/型号@H、BB=统计列位）——**期间源文件疑被 VS 旧版本保存覆盖回滚（v3 合计/面数改动丢失），合并补丁一次补齐重验全绿；教训=多轮补丁前确认编辑器没开着旧版文件****第六轮（终版口径）**：三个合计块（一次法/二次法/GT）**统一恢复 5 值行制**（模具面数=块内首个值行，紧跟标签行；**第七轮（真终版）**：用户三轮"合计第一行没有信息"的正解=**标签行右段即模具面数行**——合计块改 5 行：R0=标签(B..G 合并跨5行)+行标签"模具面数"+逐日面数值、R1..R4=计划本数/库入本数/OE/REP（此前"标签行独立空行"的 6 行结构废弃，手工表原版亦为空标签行但用户不要）；**第八轮（顺序按手工表定稿）**：二次法 sheet 尾部顺序=**二次法合计 → 模套块（模具数量）→ 使用判定 → (一次法+二次法)合计**（手工表同序，此前模套误排 GT 之后）；一次法 sheet 仍仅一次法合计；合计块 5 行结构（标签行右段=模具面数）不变。⚠️反射 mock 构造 Covers 不走 CompareCoverType 排序（真实数据在 LoadCoverUsage 排好），mock 须按显示序手动 Add。**同日排障：在库未知/数量不对**——C# LoadCoverUsage 两处加固：①视图 v_MouldCoverCount 桶名空(NULL)行原被 type==空 continue 直接丢弃（在库缺一块）→ 归'未知'**模套未知行 0 值 bug（终闭环）**：用户实机导出未知行在库=0、日格 1 变 0——**根因=C# && 短路链**：`bool exceed = hasStock && v!="" && int.TryParse(v,out use) && ...`——hasStock=false（未知 Stock=null）时整链短路，**TryParse 未执行、use 留初值 0**，而写入用的正是 use → 日值 1 写成 0；在库侧 `cv.Stock==""` 漏 null 判断 → 走 stockN=0 写 0（页面 JS parseInt 独立解析故显示正常）。修=TryParse 移出短路链独立执行 + 在库判空改 string.IsNullOrEmpty；mock（Stock=null、日值1）验证在库空/日格1。**教训：C# 导出写入变量勿复用 && 短路链内的 out 变量**。；②同型号两套命名并存映射后同键时原为覆盖→改累加。验证 SQL（用户连 APS 跑）：EXEC sp_helptext 'dbo.v_MouldCoverCount' 看桶值域 + SELECT * FROM v_MouldCoverCount 对各桶数量与页面在库逐一对账；各块用各自 SumFaces/GTFaces）——第四轮的"面数独立行夹中间"方案废弃（用户反馈：独立行悬在 GT 上方致"位置不对+下一行空白"、且各合计块缺面数信息）；块间保留 1 空行间距（手工表同款）；；**第五轮**：⑤判定**排除"未知"型号行**（无有效映射不参与 OK/NG）；⑥**删 H/I 两标识列**（检测+Art、产品号），布局再左移两列（cDay=8、行标签@H、合计标签合并 B..G、模套=在库@G/型号@H、BB=统计列位 40/41）——**期间发生源文件被 VS 旧版本保存覆盖回滚的事故（v3 合计/面数改动丢失、模套/签名幸存），用合并补丁 v5 一次补齐重验 14 项全绿；教训=补丁轮次多时先确认编辑器没开着旧版**；**踩两个坑**：CreateRow 重建清空（GetRow??CreateRow 移出循环）+ AddMergedRegion 清合并区非首行上下边框（merge 后统一重设 CellStyle 补边，详见 [[npoi-format-replication]] 九）；③模套块列位 MAX@G(6)/在库@H(7)/空@I(8)/型号@J(9) 连片浅绿（原挤在 H/I/J 少一空列）。行：R1 制表日+表单号|R2 标题(合并+CCFFCC浅绿底+Arial16B)|R3/R4 日历标记两行(淡蓝7992B1=停机/盘点/开机类、橙FAC090=TPM；同日第2事件上行)|R5 日数字|R6 星期+合格率(FFFF99黄底0.98)|R7 左区18列头(无边框)+加硫操業時間数值+**24H全天事件黄底标事件名(中秋/停产)**+统计表头|R8 成型操业时间|R9+ 数据对(**机台块间空1行**、面数/本数成对、属性格纵向合并、本数行整行 CCFFCC 浅绿+标记色、四边细边框)→合计块(**3行制**：计划本数/OE库入量/REP库入量青底00FFFF小数；标签 B..U 纵向合并中粗外框)→GT块(仅二次法,同构)→模套块(仅二次法：表头 MAX/在库 + 每行 MAX|在库|空2|型号|日值，标签区CCFF底中粗框)→模套使用判定OK→备注行→图例4项(含设备点检D99694粉)→保管期限3年。全程 DisplayGridlines=false。手工表冻结 F325 为浏览残留，导出取 W9（左区22列+表头8行）。
- **数据源映射**：proc 12 列覆盖 成形機/加硫机/检测/Art.No./SIZE/稼动率/面数/本数/标记；INCH=SIZE_SPEC 里 R 后数字+'"'（ExtractInch）；右侧统计列 Σqty 与 Σ×0.98（合格率 0.98 黄底占位常量，手工表=库入本数为折算值 646.8=660×0.98 实证）；日历标记行/节日黄底=DownTime proc 事件（新增 **DownMark 结构化清单**挂 ScheduleData.DownMarks，LoadDownTime 加 out 参同步填充；同日第2事件放上一行、TPM 橙色、24H→操业行黄底）。仕样列已整体删除（见上），不再有留空列。
- **实现结构**：InitMsStyles 显式构建样式（ZStyle 仿 Curing；**ICellStyle 接口无 SetFillForegroundColor(XSSFColor)——须 ((XSSFCellStyle)s) 强转**；3×3 边缘样式矩阵 MS_EDGE[rp][cp] 供合计/GT/模套块"外缘中粗内部细"）；Put(sh,r,c,object,style) 统一写入（string/double/int 三分支，空串只设样式）；BlankBox 铺边缘框；DrawSumBlock 复用于合计/GT；旧 HTML 导出族（BuildExportHtml/Xd/LegendHtml/MarkStyle/OpCell/DownCell/WeekLabel）整体删除。
- **本轮三个真 bug（断言抓出）**：① `Math.Round(sum*0.98m,2)` 返回 **decimal**，Put 类型分支不认→统计列空值（转 (double)）；② 操业时间 string '1440' 直接写为文本格（int.TryParse 转数值，手工表为数值）；③ 模套 Daily 数组元素为 null（LoadCoverUsage 初始化 new string[]）时 `v==""` 判断漏 null→写成 0（?? "" 兜底）。
- 验证：csc C#5 EXIT 0（加 NPOI 四 dll 引用）；**反射调 BuildScheduleXlsx 落盘 + openpyxl 36 项逐格断言全绿**（双sheet/关网格/冻结/标题底色/日历两行色与同日分行/节日黄底/18列头/INCH/统计列Σ×0.98/本数浅绿/三标记色/双0空/块间空行/合并区/合计3行制REP青底/GT/模套MAX在库/covex红/空日留空/判定行/图例4项/保管期限）；genoffice 渲染出图成功（文件结构完好）；肉眼复核缺位（media 工具未登录）——实机 Excel 打开观感待用户验收。
- 差异与遗留（对齐手工表时的口径决策，可调）：① 12 仕样列+段组已按用户要求删除（如日后要回，初版列位规格见本节底图段）；② 合计块 OE/REP 用 MES 实际入库（页面 0918 口径），手工表 REP=计划×0.98 折算——格式对齐、数值口径不同，如需折算改一行；③ 模套日值沿用页面"逐日使用数"口径，手工表疑似"逐日在库数"（起伏 84-88 无法确证）——待用户确认；④ **周报导出未动**（仍 HTML .xls；手工表无周表对照，如需同款 NPOI 再说）。

---

## 十四、合计块恢复模具面数 + 主表 I 列去重（2026-09-29 增量，月报导出单页）

- 需求（用户报）：一次法合计、二次法合计没有模具面数（09-28 第四轮曾改 4 行制把模具面数移出）；(一次法+二次法)合计中要有模具面数；导出主表 H、I 两列内容重复。
- 改动（纯 MoldSchedulePlan.aspx.cs 单文件，DrawSumBlock 及调用处）：①**DrawSumBlock 恢复 5 数据行制**（签名加 `int[] faces` 参数放 qty 前）：块高 5→6 行，数据行=模具面数/计划本数/库入本数/OE库入量/REP库入量（标签合并与 BlankBox 范围 r0+4→r0+5，return r0+6）；②合计调用传 `data.SumFaces`、GT 调用传 `data.GTFaces`——三个块（一次法合计/二次法合计/GT）全有模具面数；③**删 09-28 第四轮②的"模具面数独立行"**（GT 块自带后同值冗余）；④**删 I 列（列 8）写入**（原 `Put(sh, rq, 8, p.Art)` 与 H 列 Chk+Art 在检测为空时完全重复；保 H=Chk+Art 信息超集；heads 表头本就无 H/I 列、模套块 I 列设计为空列——零牵连）。
- 验证：csc EXIT 0（**tmp/csc-check-month.ps1 可复用：引用须补 Wongoing.DbAccess.dll + Wongoing.Molding.Data.dll，否则 CS0012 传递依赖缺失**）；反射 mock（tmp/reflect-test.ps1 落盘 check-export.xlsx）+ openpyxl 断言：一次法 L12 合计模具面数=SumFaces(1,2,3)、二次法 L12=(2,4,6) 与 L19 GT=(3,6,9)（数学关系 GT=d1+d2 吻合）、每模具面数行下一行=计划本数（行序）、独立行消失（二次法"模具面数"标签 3 处=明细1+合计1+GT1，若独立行在应为 4）、I 列全空、H 列本数行=Chk+Art。**断言坑：明细区每产品面数行标签也叫"模具面数"（L9），计数断言要区分明细/合计/GT 三场景**。反射坑：Machines/Products 是泛型 List 字段，PowerShell 填 ArrayList 报 ArgumentException，须 `[Activator]::CreateInstance([List``1].MakeGenericType($type))`。
- 部署：aspx.cs 动态编译拷文件即生效，零 Mapper/dll/DB 变更。周报不受影响（周导出仍 HTML .xls，且页面版合计块本就是 5 行制）。