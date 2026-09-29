---
title: 硫化机状态可视化页面（CuringEquipStateVisual）
category: 业务-通用
module: Curing
status: active
tags: [Curing, 硫化机状态可视化, CuringEquipStateVisual, 停机原因汇总, 状态大屏, DataView, 图例统计, 左右侧别, LR标注, 悬浮提示, 胶囊布局, 卡片半区着色, 仕样加硫时间, CURE_TIME, BOM参数, 图例点击筛选, 徽标精确筛选, important级联, getComputedStyle断言, grid显式定位, sparse阶梯化, 紧凑重排, 侧标志01化]
updated: 2026-09-19
---

# 硫化机状态可视化页面（CuringEquipStateVisual）
> Curing 子系统硫化机状态大屏：单条聚合 SQL（GetEquipStateVisual@CppCuringPlan）+ Ext.NET DataView 卡片墙 + 前端 updateSummary 顶部图例。2026-09-15 完成侧别改造（五档全按 L/R 标注）；**2026-09-19 四轮演进定稿：卡片「加硫 N秒」行（仕样加硫时间，BOM 参数口径）+ 五档图例点击筛选 + 停机原因徽标精确筛选 + 卡片墙显式 grid 定位（筛选态紧凑重排）**。本文为收拢后的终态权威版，前端技术坑见 [[extnet-hover-tooltip-pitfalls]]。

## 一、页面架构与文件

| 文件 | 作用 |
|------|------|
| `P.Curing/Wongoing.Curing.WebSite/Plugins/Curing/Equip/CuringEquipStateVisual.aspx` | 页面骨架：North 工具栏(刷新按钮) + Center 图例条(5 档计数 + 停机原因徽标,五项带 data-key 可点击筛选;徽标可按原因精确筛选) + DataView 卡片墙(左右半区含「加硫 N秒」行,显式 grid-column/grid-row 定位)；含 updateSummary/applyFilter JS |
| `CuringEquipStateVisual.aspx.cs` | 班次窗口反查（DetectCurrentShift 检查昨天+今天各班次 [begin,end) 窗口）+ LoadData 调 SQL 绑定 Store；UTF-8 编码 |
| `curingequipstatevisual.css` | 卡片网格(12 列 grid，单列下限 180px，**卡片显式定位，auto-flow 不参与；筛选态 .filtered-mode 切自动流紧凑重排**) + 五色卡片/半区 + 图例条/悬浮提示/选中筛选态样式，aspx 带 `?v=日期字母` 版本号刷缓存（当前 v=20260921a） |
| `P.Curing/Wongoing.Curing.Mapper/BusinessMapper/CppCuringPlan.xml` | `GetEquipStateVisual@CppCuringPlan`（id 2312 行附近），单条 select 聚合，含侧别 0/1 标志输出 + 仕样加硫时间两列(秒) + UUID_COL/UUID_ROW |

- 刷新链路：Page_Load / 刷新按钮 DirectMethod / 60 秒 setInterval → LoadData → Store.DataBind → Store Load 事件触发 `updateSummary(store)` 更新图例计数、悬浮机台列表、停机原因徽标，末尾重放 `restoreFilterActive()+applyFilter()`（筛选态在自动刷新后保持，含高亮）。
- 时间窗口参数：`PLAN_DATE`(班次归属日期)、`SHIFT_CODE`、`BEGIN_TIME`/`END_TIME`（班次主数据 SsbShift 的 StartTime/StopTime + DayFlag 跨天拼接，参照 shift-date-to-timerange-impl）。

## 二、五档状态与侧别口径（终态，图例计数/悬浮/卡片/筛选四处同口径）

**整机优先级**（决定卡片外框/标题色与图例落档）：红(胶囊预警) > 黄(停机) > 橙(换模计划) > 绿(有计划) > 灰(无计划空闲)。一台机同时停机+预警时计"预警"档不计停机数；卡片状态行仍按各标志独立显示。**整机黄卡的未停侧半区可显示绿（该侧仍有计划）**——信息更细但不改图例计数（既定设计，用户知情）。

**侧别标注规则（全档统一）**：双侧/整机在档 → 纯机台号；单侧在档 → 机台号+L/R（J204L/J204R）。

**各档侧别语义**：
- 胶囊预警/停机/换模/计划：按各自侧级标志（见 §四 SQL）标注悬浮列表；计数=台。
- **空闲=计划的反侧**：红/黄/橙三档整机优先出档（其机台不入空闲）；进入绿档后——双侧有计划→仅计划档；**单侧有计划→计划档标计划侧 + 空闲档补记空闲侧**（如 J204 同时出现在计划档"J204R"与空闲档"J204L"）；双侧无计划→空闲档纯机台号。**五档计数不是互斥分区**（单侧计划机台跨两档），计数单位仍是台。
- 图例"有停机"旁停机原因徽标：对落"停机"档机台按 STOP_REASON 分组（空原因归"未注明"）降序渲染 `.stop-reason-chip`，各徽标台数之和恒等于"有停机"计数。

**点击筛选系统（2026-09-19，两级粒度互斥单选）**：
- **五档图例**：挂 `data-key` + `title="点击筛选/取消"`，点击筛选卡片墙只显示该档机台（与图例计数同口径——updateSummary 循环里同步登记 `buckets[档][纯机台号]`）。
- **停机原因徽标（精确到明细）**：挂 `data-reason`（encodeURIComponent），点击只筛选该原因的机台（`reasonSets[原因][纯机台号]`，与徽标计数同口径）；**不**触发"有停机"整档筛选（单一委托 + closest 深度匹配，徽标优先于图例项，见 §六坑 6/9）。
- 交互：再点一次取消恢复全部；两者互斥（选原因清图例高亮、选图例清徽标高亮）；选中态深蓝 #2d6ca2 底白字（图例 .legend-active / 徽标 .stop-reason-chip.active 同语言，图例项负 margin 补偿 padding 不跳动）；60 秒刷新后重放（含高亮重放）；筛选对象刷新后消失/变空自动回退全部。
- **筛选态紧凑重排**：筛选时可见卡从第一格重新排起（容器挂 .filtered-mode 压掉显式定位），取消恢复原沟位——实现见 §六坑 8。

## 三、侧别表事实（三处 schema 实证，写相关 SQL 前必读）

| 表 | 侧别来源 | 实证样例 |
|----|---------|---------|
| `SBE_EQUIP_STOP_RECORD` | `EQUIP_CODE` **混存两种形态**：纯机台号=整机停（计入两侧），带侧别=单侧停 | J204（整机）、**J204R/J119R**（不带空格） |
| `CPP_CURING_PLAN_DETAIL` | `EQUIP_POSITION` = 'L'/'R'，计划按侧下在明细行（PLAN_AMOUNT>0）；**BOM_ID varchar(36)** 直连 SBM_BOM_MASTER | 用户样例 SQL 实证 |
| `tb_EQ_ChangeMouldPlan` | `EquipID` = 机台号+' L'/' R'（**带空格**，同 tb_EQ_EquipMonitor 形态） | 'J101 L' |

⚠️ 停机表等值匹配纯机台号会**漏掉所有单侧停机**，须五值 `IN (code, code+'L', code+'R', code+' L', code+' R')` 超集匹配。

## 四、SQL 关联链速查（GetEquipStateVisual，终态）

```text
SBE_EQUIP(硫化机, MAJOR_TYPE_ID='06', DELETE_FLAG=0)
 ├─ SBE_EQUIP_STATE(状态快照) → 胶囊编号/物料/左右模在机信息
 ├─ CPP_CURING_SULF_CAPSULE_NO(台账) → CPP_CURING_SULF_CAPSULE(上限MAX_USE_NUM)
 │    ⇒ L_/R_CAPSULE_WARN、CAPSULE_WARN(任一侧,原侧级列)
 ├─ SBM_MATERIAL(物料名, MAJOR_TYPE_ID='03')
 ├─ tb_EQ_EquipMonitor(EquipID=code+' L'/' R') → SideBoard/MouldCover/PatternBlock
 ├─ outer apply pl(本班计划聚合+仕样加硫时间): CPP_CURING_PLAN×DETAIL
 │    + left join SBM_BOM_MASTER(bm.BOM_ID=d.BOM_ID)
 │    + left join SBM_BOM_PARAM(bm.BOM_CODE=bp.BOM_CODE AND bm.BOM_VERSION=bp.BOM_VERSION
 │        AND bm.TYRE_MATERIAL_CODE=bp.TYRE_MATERIAL_CODE
 │        AND bp.ParamCode='CURE_TIME' AND bp.DeleteFlag=0)
 │    ⇒ HAS_PLAN/L_/R_HAS_PLAN(max) +
 │      L_/R_CURE_TIME = max(case 侧匹配 then cast(round(try_cast(ParamValue as float)*60,0) as int) end)  -- 秒(外层再转 m:ss 字符串)
 ├─ outer apply sr(未恢复停机, top 1 最新 + 窗口聚合侧 0/1 标志): SBE_EQUIP_STOP_RECORD
 │    where RESTART_EQU_DATETIME is null and REPORT_DATETIME∈[BEGIN,END)
 │      and EQUIP_CODE in (五值超集)
 ├─ outer apply cp(本班未完成换模, top 1 最新 + 窗口聚合侧 0/1 标志): tb_EQ_ChangeMouldPlan
 └─ DENSE_RANK(EQUIP_UUID) 对 12 取模 ⇒ UUID_COL 列号(12 列沟位)
    + ROW_NUMBER() OVER (PARTITION BY e.EQUIP_UUID ORDER BY e.EQUIP_CODE DESC) ⇒ UUID_ROW 行号
    (列数不能改;行号供 tpl 显式 grid-row 定位)
```

要点：计划判定用 apply 聚合而非 left join（避免重复行）；换模 ChangePlanID 前 8 位 yyyyMMdd 用范围比较替代 left() 保索引；**侧别标志统一"窗口聚合 max(0/1) 挂 top-1 apply"模式（0/1 语义，勿用 sum 计数，见 §六坑 7）**；停机窗口只统计**本班 REPORT_DATETIME**——跨班未恢复停机不可见（遗留项，见 §九）。

## 五、仕样加硫时间口径（2026-09-19，单位秒·终态）

- **取值 = SBM_BOM_PARAM（ParamCode='CURE_TIME'）的 ParamValue，存储单位分钟；本页显示单位秒**（`cast(round(try_cast(ParamValue as float)*60,0) as int)`，用户 2026-09-19 拍板）；链路 `CPP_CURING_PLAN_DETAIL.BOM_ID → SBM_BOM_MASTER → SBM_BOM_PARAM`，**与日报样式-3（curing-daily3-report-implementation）同链**，勿走 CPP_SULF_SPEC_BOOK（规格书 SF_TIME_MIN 路线已被用户否定）。
- 按侧取（明细 EQUIP_POSITION='L'/'R' 各自 max），**多规格取总时长最长者**；无值输出空串（本班无计划或 BOM 未配置 CURE_TIME，行不渲染）。
- **显示「硫化总时间 10:53」分:秒格式**（用户 2026-09-21 定稿名与格式）：SQL 层格式化 `cast(秒/60 as varchar)+':'+right('0'+cast(秒%60 as varchar(2)),2)`，L/R_CURE_TIME 输出字符串、Model Type=String、tpl `<tpl if="L_CURE_TIME">` 非空判断；**半钢胎 ParamValue 实际 10~15 分钟档 → 10:24~15:12**，勿误判单位。
- **5 字标签+时间在 180px 卡半区（文本区约 71px）一行放不下**（10px 换行）——.cure-time 收紧为 9px+letter-spacing -0.3px+nowrap+overflow:hidden，标签与值用 `<span class="cure-val">`（margin-left:2px）隔开；实测 156 行 sw=cw=68 零溢出单行。

## 六、图例悬浮与点击筛选实现（终态，坑 1~9 密集区）

- 结构：5 个图例项各带 `<span class="legend-tip" id="tip-*">`（整机/单侧机台列表）+ 停机原因徽标内嵌同名 tip（分原因列表）；JS `codesHtml()` 生成 `<span class="tip-code">机台号</span>` 胶囊，`:empty` 计数为 0 自然隐藏。
- 样式基线：深蓝 #2d6ca2 白字 **14px 加粗**（12px 两轮被打回）、半透明白底胶囊、小三角指向（`::after`）、`cursor:pointer`、`width:max-content`（左锚 max-width 480px / 右锚 tip-right 600px 永不右溢）。
- 选择器纪律：hover 规则必须 `>` 直接子级（嵌套 tip 防全点亮）；悬浮徽标区用 `.stop-reasons:hover ~ .legend-tip{display:none!important}` 抑制父级整表框。
- **九条坑（按踩中顺序）**：
  1. **显隐必须用 class（`.filtered-out` + css `display:none !important` 且选择器 specificity 高于防御规则），不能用 JS 内联 `style.display='none'`**——卡片墙 css 里有 `.dataview-state-grid .state-card{display:block!important}` 防御规则，author `!important` 压制内联样式（designer 第一轮审查抓出的阻断级 bug）。
  2. **验证显隐必须断言 `getComputedStyle(el).display`**——读 `el.style.display` 只反映 JS 写入值，是假阳性根源。
  3. **卡片必须显式 grid 定位（grid-column + grid-row 双显式）**——只显式列不显式行时，`grid-auto-flow: row`（sparse）的自动放置光标单调前进，第 N 列的卡从第 (N-1)×每列行数 行开始放，**布局阶梯化成"一行一卡"斜排**（2026-09-19 用户报障：dense→row 修复筛选跳位时引入）。终态：SQL 出 `UUID_ROW`（ROW_NUMBER partition EQUIP_UUID order EQUIP_CODE DESC），tpl `style="grid-column:{UUID_COL}; grid-row:{UUID_ROW}"`，auto-placement 完全不参与，dense/sparse 均无副作用。
  4. **位置对比断言用 offsetLeft/offsetTop，勿用 getBoundingClientRect**——后者是视口相对坐标，DataView 横向滚动位置变化会污染对比基准（实测伪"移动 8 卡"，实际 offsetLeft 全部未变）。
  5. **筛选不动 Store**——ExtJS filter 后 `store.getRange()` 返回过滤子集，图例计数会跟着变（汇总口径必须全量）；机台号从卡片 `.card-code` DOM 文本匹配。
  6. **事件绑定单一委托**——图例/徽标由 Ext 渲染或 JS 动态重建（晚于页尾 script），须 `jQuery(document).on('click', '.legend-item[data-key], .stop-reason-chip', ...)`；徽标嵌在图例项内，两个委托分别注册时点击徽标会先触发图例档筛选再触发原因筛选（**同节点多个 handler 不受 stopPropagation 阻止**）；单一委托里 `closest('.stop-reason-chip')` 深度匹配让徽标优先。
  7. **侧标志字段必须是 0/1 语义，窗口聚合用 max 不用 sum**——侧停机/侧换模标志最初写 `sum(case 侧匹配 then 1 else 0 end) over ()`（计数），某机台同侧有 2 条未恢复停机记录时值=2，前端 tpl/JS 的 `===1` 判断失效 → 停机侧漏黄落到下一档（用户报障"整机黄框左右明细绿"，J101/J316 实证）。修法：SQL 侧 `max(case … then 1 else 0 end) over ()` 0/1 化，前端判断零改动；**通用规则：给前端的标志字段一律 0/1 语义**。
  8. **筛选态紧凑重排（用户要求）**——筛选时给卡片墙容器挂 `.filtered-mode`，css 用 `grid-column/grid-row: auto !important` **压掉 tpl 内联的显式定位**（坑 1 的镜像用法：这次故意 author !important 压内联），可见卡恢复自动流排从第一格紧凑排起；取消筛选移除类回原沟位（车间位置地图）。sparse 自动流在"全部可见+无显式定位"下就是顺序填充，不会阶梯化（阶梯化只发生在"显式列+组间 DOM 连续"场景，见坑 3）。
  9. **图例项点击域注意**——"有停机"图例项内嵌停机原因徽标群，其几何中心可能落在徽标上：自动化测试点图例项中心会误触原因筛选（实测点到"模具换洗"只剩 1 台，一度误判筛选坏）；真实用户无碍但测试须点色块/文字部分。语义分界=点色块/文字→档筛选，点徽标→原因精确筛选。
- designer（CC 旗舰只读）两轮审查：第一轮抓出坑 1/坑 3 前身（!important 压制、dense 跳位）两阻断，均已修复复验；第二轮复审**通过**，唯一建议（徽标选中环与图例统一 2px 描边）已采纳（v=e）。

## 七、卡片半区着色与卡片墙

- 卡片结构：`.state-card`（整机色边框+标题+状态行）内 `.card-sides` 左右两半 `.card-side`，各按本侧**五档同序**着色（tpl 嵌套三元，L_/R_CAPSULE_WARN/STOPPED/CHANGE_PLAN/HAS_PLAN 逐级判断，侧标志均为 0/1）。
- 卡片信息行序（每侧）：规格名（11px 加粗）→ **硫化总时间 m:ss（蓝加粗 9px 单行）** → 胶囊/次数/模套/侧板/活络模/生产次数（10px 素色）——"规格→加硫→元数据"三级层次。
- 卡片墙：12 列沟位 grid `repeat(12, minmax(180px, 1fr))`，**卡片显式 grid-column/grid-row 定位**（见 §六坑 3；筛选态紧凑重排见坑 8），小屏横向滚动（DataView AutoScroll 原生支持）。
- ⚠️ tpl 三元嵌套改层后**先数括号**（多一个 `)` → Unexpected token、整面 DataView 空白）。

## 八、部署、惯例与验证纪律

- **部署清单（服务器上线三件套）**：`Wongoing.Curing.Mapper.dll`（重建手拷 Bin）+ `CuringEquipStateVisual.aspx` + `curingequipstatevisual.css?v=20260921a`。
- **Mapper XML 改动部署链**：MSBuild `//t:Rebuild` Wongoing.Curing.Mapper.csproj → 手拷 Debug dll 到 WebSite\Bin（备份 `.bak-日期`）→ `grep -ac 新列名` 验证（L_CURE_TIME/R_CURE_TIME/UUID_ROW）。**Bin 变更掉登录态属预期**。
- 纯前端惯例：Store 已有字段能支撑的汇总/展示改 aspx JS + css 即可；改 css 必须同步升版本号 query string。
- 本地开发目录已无 PrecompiledWeb 副本（2026-09-19 实证，跳过同步）。
- **验证纪律（防假阳性）**：渲染数断言 `querySelectorAll('.state-card').length === store.getCount()`；**显隐断言必须 getComputedStyle**（坑 2）；**位置断言必须 offsetLeft/offsetTop（勿用 rect，滚动污染，坑 4）**；口径类用 Store 正推基准 vs 可见卡片集合零差（实证：徽标筛选正推 8=可见 8、图例 idle 正推 179=可见 179，mismatch/missing 双空）；布局顶对齐断言各列首卡 offsetTop 相同。

## 九、遗留项

1. 自绘深蓝 tip 与刷新按钮 Ext 原生浅色 ToolTip 并存（designer 意见保留深蓝），要统一再改。
2. 卡片"停机：原因（时长）"行双侧原因不同时只显最新一条，要分侧展示再迭代。
3. 停机窗口只统计本班 REPORT_DATETIME——跨班未恢复停机不可见，要不要算待用户拍板。
4. 服务器部署三件套待上线（2026-09-19 终版：dll+aspx+css?v=20260921a）。

## 十、演进史（2026-09-15 一日十轮 css a→j；2026-09-19 五版 css a→f）

①悬浮机台号提示(v=a) → ②停机分侧 SQL(v=b) → ③停机原因徽标分原因悬浮 → ④hover 直接子级修复(v=e) → ⑤胶囊化排版 → ⑥计划分侧 SQL → ⑦卡片半区四色(v=h) → ⑧空闲=计划反侧 → ⑨换模分侧 SQL → ⑩半区加橙五色同序(v=j)。当日卡片墙加宽 150→180px(v=i)。
⑪(2026-09-19)卡片加硫时间行+图例点击筛选——初版误做"时间分档汇总条+点击筛选"被用户纠偏（"汇总"指既有五档图例，新维度勿自造汇总条）；designer 抓 !important/dense 两阻断修复（css v=a→c）。
⑫(2026-09-19)用户三连反馈定稿：**单位改秒**（×60）+ **dense→row 后 sparse 阶梯化"一行一卡"**（改显式 grid-row=UUID_ROW 定位修复，布局恢复 12 列顶对齐）+ **徽标精确筛选**（停机汇总中的明细，与图例档筛选互斥单选）（css v=d）。
⑬(2026-09-19)用户报"停机机台外黄内绿"——根因侧停机标志 sum 计数遇多条未恢复记录=2，前端 ===1 失效漏黄；SQL 四处 sum→max 0/1 化修复（J101/J316 两侧恢复 side-yellow，纯 SQL 改动无 css 版本）。
⑭(2026-09-19)designer 二轮复审通过，采纳徽标 outline 同粗细建议（css v=e）。
⑮(2026-09-19)用户要求筛选后卡片从头紧凑重排——容器 .filtered-mode + css auto!important 压内联定位；取消恢复原沟位（css v=f）。
⑯(2026-09-21)「加硫 N秒」改名「硫化总时间」+格式改 m:ss（10:53）；5 字标签超半区行宽——9px+收字距+nowrap 单行（css v=20260921a）。相关 [[extnet-dataview-card-grid]]。
