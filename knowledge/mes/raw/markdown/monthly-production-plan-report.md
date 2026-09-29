---
title: 月生产计划报表页面（Curing·MonthlyProductionPlan，APS 跨库动态版本列）
category: 业务-通用
module: Curing
tags: [月生产计划, MonthlyProductionPlan, Curing, ReportCenter, APS跨库, 动态版本列, xlsx格式复刻, NPOI导出, 八区块, 虚线边框, 差异列, 版本可增长, 规格数按版本, 操业日数, 四工序交集, tra_order_monthly_version, 版本号0基, DisplayGridlines, 模具在库, 模套, DateField月份模式, NOLOCK, 按代码为准]
updated: '2026-09-23'
status: active
---
# 月生产计划报表页面（Curing·MonthlyProductionPlan，APS 跨库动态版本列）

> Curing 子系统「月生产计划」报表页：月份查询 + 主表（区分→英寸→ArtNo 排序，英寸计标签行 + 类型 TOTAL 小计行 + 按当月实际版本号动态生成的 R0..Rn 订单/計劃列对）+ 南区三块（英寸统计 13"~19"、类型统计 OE/REP、汇总指标）+ NPOI xlsx 导出（八区块，2026-09-23 定稿）。数据全部查 APS 库（同实例 `APS.dbo.` 跨库），口径对齐 CHQY-APS-Backend `MonthlyProductionPlanReportHandler`（2026-09-19 用户裁定「按代码为准」，xlsx 手工版差异一律反转）。2026-09-19 交付实测出数；2026-09-23 导出格式八区块逐块对齐原件定稿（v27），并实证版本增长（R1 进库后页面/导出自动长出 R1 列）。

## 一、页面概览与交付状态

- 页面：`P.Curing/Wongoing.Curing.WebSite/Plugins/Curing/ReportCenter/MonthlyProductionPlan.aspx(.cs)`；Inherits=`Plugins_Curing_ReportCenter_MonthlyProductionPlan`
- Mapper：`CppCuringProduction.xml` 追加 4 语句（`SelectMonthlyPlanMainData/MoldCount/MouldCover/Calendar@CppCuringProduction`），复用 `CppCuringProductionManager` 不建实体
- 用户验证 SQL：`Curing/sql/20260919_MonthlyProductionPlan_selects.sql`（六条：主数据/模具在库/模套/日历/操业日数链 + 部分五规格数按版本两式）
- 结构：North 查询区（计划月份 DateField 月份模式 + 查询/导出按钮）→ Center 主表（客户端分页 100、FilterHeader、GetRowClass 两档行底色：英寸计 #FFF3E0 / TOTAL #D6EAF8）→ South 300px 三块（英寸统计 Grid + 类型统计 Grid + 汇总 DisplayField×7）
- 权限：btnSearch / btnExport 两个 PageAction（ActionName=按钮 ID）
- 导出：NPOI 2.1 真 xlsx（`btnExportSubmit` 回发 → `Response.BinaryWrite`），八区块格式 2026-09-23 定稿（见第五节）

## 二、取值口径（按代码为准，2026-09-19 裁定；规格数口径 2026-09-23 更新）

| 区域 | 口径 |
|---|---|
| 主表产品行 | SQL 按 产品×版本×订单类型 聚合，C# 按 type\|product 归并成一行、版本转字典；**非版本字段（英寸/ArtNo/Size/Pattern/前月在库）取该产品最大版本行值**；月末在库预定 = 在库 + 末版計劃 − 末版订单 |
| 排序分组 | 类型序 REP→OE→其他；英寸数值升序（空/非数值=未知排尾）；组前插「N英寸计」标签行，类型尾插 TOTAL 行（纯 SUM） |
| 版本列 | 按**当月实际出现的版本号集合**动态生成 ORDER_Vn/PLAN_Vn 列对，表头「Rn版订单/Rn版生产計劃」；产品无该版本留空。**版本可增长（2026-09-23 实证：R1 后进库，重查即自动长出 R1 列与 R1 独有产品行），勿写死版本数** |
| 英寸统计 | 13"~19" 固定七行（0 值行保留）+ 合计 = 纯 SUM；比率 = 行計劃/合计計劃 |
| 类型统计 | 仅 OE/REP 两行；订单预算 = 0（硬编码）；订单实绩 = **全局最大版本**订单量聚合 |
| 汇总区 | 操业日数 = 四工序停机交集（见下）；总/REP生产计划 = 全局最大版本計劃聚合；**月当规格数 = 按版本区分的产品编码去重（2026-09-23 用户口径更新：只数规格块表头所示版本，页面显示最大版本口径；勿跨版本去重）**；plan98 = ⌈总計劃×0.98⌉；日当规格数 = 月当规格数（公式引用）；英寸段替 = 0 |
| 操业日数 | 当月总分钟 − 全厂停机分钟；全厂停机 = S/GREEN/PART/MIX 四工序停机区间**交集**（先裁剪到当月、工序内合并重叠/相接；任一工序无记录则无全厂停机），四舍五入 1 位 |

**已按裁定反转的 xlsx 手工版差异**：TOTAL 的 −396(Q)/−413(R) 人工扣减 → 纯 SUM；类型表 EXP-OE/EXP-REP 行、手填预算 → 删；英寸 13~20 八行 → 13~19 七行；英寸合计 SUM−413 → 纯 SUM。取值链路详见记忆 monthly-plan-report-data-sources。

## 三、SQL 四条（APS 跨库，优化原则落实）

- 主数据：`tra_order_monthly_version mv` INNER JOIN `tra_sales_order`/`tra_sales_order_item_middle`（试作/量试、手动添加、order_state=5 三过滤）LEFT JOIN `bas_resource`（产品主数据）/`bas_product_inventory_month`（前月在库，month=varchar 与 #PREV_MONTH# 同型）；`WHERE mv.order_month = #MONTH_FIRST#`（date 列，C# 传 DateTime）；GROUP BY 产品+版本+类型。**不过滤 mv.delete_flag 是 Java 原口径**（勿"顺手修正"）
- 模具在库：`bas_process_resource_mapping`（resource_category='PRI'）× `bas_resource`，COUNT(DISTINCT resource_code)，产品 LIKE '03%'
- 模套：MOULD-02 机型 MIN(mould_cover)，IN 列表由 C# 拼码经 `$PRODUCT_CODES$` 文本替换（编码来自库内非用户输入）
- 工厂日历：四工序区间开区间裸列比较，交集在 C# 算
- 全表 `WITH(NOLOCK)`；字段侧无函数；验证 SQL 全集在 `sql/20260919_MonthlyProductionPlan_selects.sql`

## 四、表事实（APS 库实证）

- `tra_order_monthly_version.version` **0 基且可增长**（0/1/2… 对应展示 R0/R1/R2…；2026-09-23 实证 R1 后进库：R0=56 规格/R1=68 规格，R1 独有产品 S45xx 系列同步进主表）
- `tra_order_monthly_version.order_month`：date 型；`bas_product_inventory_month.month`：varchar 'yyyy-MM'（参数须同型）
- 英寸 = `bas_resource.size_id` 首个 'R' 之后的部分
- `bas_process_resource_mapping`：PRI=主资源(模具)、MOULD-02=模套机型；`mould_cover` LM/RV 与 G/E 两套命名并存（映射惯例见 [[molding-schedule-plan-report]]）

## 五、导出（NPOI xlsx 八区块，2026-09-23 定稿）

导出八区块划分（逐块对齐 CHQY 原表，全部落 `btnExport_Click`）：

| # | 区块 | 位置/结构 | 关键格式 |
|---|---|---|---|
| 一 | 主表 | R1 标题/R2 表头/产品行/英寸計行/TOTAL 行，F..S(+版本列浮动) | 表头 #FAC090+WrapText；英寸計行整条 F..末列中粗框不拆格；产品明细行**虚线格**（F 左/末列右中粗接边）；TOTAL 行 #66CCFF 四格含 F/G/H/I；纯REP/OE 与右两格合并 C:E；A-E 列无边框（A/B 微软雅黑9、C/D/E Arial9） |
| 二 | 订单预算/实绩 | 统计区（骑产品行右侧，锚定 sheet 行号 ZONE1_RIX=6） | 标签行 #CCFFFF 蓝底无边框 Arial10B；表头/数据发丝网格+边界细线，Arial10，标签居中数值左对齐；合计行整行下边框实线 |
| 三 | 当月英寸别 | 统计区第二块，与部分二**间隔两行** | Arial9 左对齐系；比率列整列无边框；外圈实线（顶/左/右/底行收口） |
| 四 | 操业日数块 | F:H（与主表间隔两行），**F:G 合并=标签/量值，H=日均标签/日均值** | 加硫值行整行 CCFFFF 且 F 格带左边框；库入值行整行 FDEADA；OE/REP 值行无底色；数字 #,##0 不留小数 |
| 五 | 规格块 | F:G 合并标签，**版本列自 H 起向右延顺（R0/R1/R2…每版本一列，可能多个）** | 值 = 各版本规格数；英寸段替恒 0；数字 #,##0 |
| 六 | 出口块 | 两行，F:H **纵向合并** | 出口格底色=主表表头 FAC090；订单/生产相邻（I/J），订单值黄底 FFFF00、生产值粗体；保管期限3年 Y 列粗体；全块无边框 |
| 七 | 对比块 | 操业日数行右侧 O 起：9月/R0..Rn/差异 | 微软雅黑10 粗体居中；左/顶边、末版本列右边、末行下边中粗，内部细线；**黄底差异表头 R{末}-R{前}差异，差异值=末版本−前一版本，仅到库入日均（OE/REP 行不算）**；数字 #,##0 |
| 八 | 签名区 | S..Z 四个 2×2 格 | 上格角色（批准/审核/审核/作成）微软雅黑11 粗居中，下格空白签名位；四边中粗框；行高 17.25/15 交替 |

整表 `DisplayGridlines=false`（只显单元格边框）；冻结 H3（A..G 七列 + 标题/表头两行）；数字格式 #,##0 不留小数（四/五/七）。技法与坑详见 [[npoi-format-replication]]。

## 六、踩坑与根因

1. **APS 版本 0 基坑**：归并逻辑「v > LocalMaxVersion(初值0)」+ 版本列 1 起循环 → version=0 永不触发。正解：初值 **-1**，版本列按实际版本集合生成
2. **动态列四步缺一即「Store 有数视图空白」**：必须 `store.Reader.Clear()` + `Columns.RemoveRange` + 整体替换 Model + `grid.Render()`，见 [[dynamic-column-grid]] 第 10 条
3. **GetRowClass 是 GridView 直接子元素**；**DateField 不支持声明式 ToolTip**（月份模式 RawText=yyyy-MM）
4. **规格数跨版本去重坑（2026-09-23）**：`COUNT(DISTINCT product_code)` 不带版本条件会把 R0/R1 的规格混在一起数；正解按版本过滤（规格块表头所示版本），SQL 见 sql/20260919 部分五①②
5. **NPOI 导出三坑**：① `Put(rr, cx++, 三元读cx)` 参数求值顺序——条件读到的是自增后的值，末列样式错位（先取值再自增）；② 新增 Put kind 忘加分发/后缀白名单漏项 → 落默认分支变 TOTAL 蓝底样式（"某格莫名变蓝底中粗框"即此症）；③ `CloneStyleFrom` 污染源样式，样式一律显式构建（ZStyle 模式）。详见 [[npoi-format-replication]]
6. csc 单文件自检 CS0103 族属预期（控件字段运行时生成）；`this.Store1` 归入 CS1061 同族

## 七、验证方法（防假阳性纪律）

- csc 单文件 C#5 自检 → Mapper Rebuild + grep 产物 → 手拷 Bin → 浏览器实测
- **导出验证闭环**：页面查询出数 → 页内 fetch 导出 POST → 本地 python 接收器（ThreadingHTTPServer，输出文件名走 argv 可换 vN 避 Excel 文件锁）落盘 → openpyxl 逐格探针（四边框字符/fill/font/align/number_format/merged）
- 登录过期症状：导出 POST 返回 **267 字节跳转 HTML**（content-type text/html）→ 重登录；**导出前必须先查询**（数据在 Session，未查询时按钮返回普通页面 HTML）
- DOM 取证优先于视觉模型；三处咬合断言（TOTAL↔英寸表↔汇总区）继续有效
- 数据锚点：2026-09-23（R1 进库后）：R0=56/R1=68 规格、总庫入 R0=413,382/R1=430,850、操业日数 30.0 天

## 八、部署清单与遗留项

**部署**：Mapper Rebuild → 产物 dll 手拷 WebSite/Bin（或 VS 生成解决方案统一拷）→ IIS 应用池重启 → `SSP_PAGE_MENU` 挂菜单 → 授权 btnSearch/btnExport。
**遗留**：① 4+2 条 SQL 待用户在库上全量验证（sql/20260919）；② 出口订单/生产值无数据源（黄底空格占位，原件 I277=SUM 出口订单），待业务给口径；③ 加硫量值行同无数据源（CCFFFF 空格占位）；④ 部分五规格块 F:G 合并跨冻结线（G|H），滚动观感待用户实测；⑤ RowNumberer 对英寸计/TOTAL 行也编号。