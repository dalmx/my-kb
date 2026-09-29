---
category: 技术-.NET
factory: 通用
module: Ext.NET
status: active
tags:
- Ext.NET
- DataView
- CSS Grid
- 卡片布局
- 12列网格
- 滚动
- DENSE_RANK
- TRY_CAST
- CROSS APPLY
- 避坑
- 可视化
- 周期号
title: Ext.NET DataView 卡片网格可视化页面开发（含 CSS Grid 多列布局 + 滚动避坑）
updated: '2026-09-19'
---

# Ext.NET DataView 卡片网格可视化页面开发（含 CSS Grid 多列布局 + 滚动避坑）

> 以「机台周期号可视化」页面（EquipDotNoVisual）为案例，沉淀：Ext.NET `DataView` + CSS Grid 多列卡片布局 + iBATIS 分组排序 SQL 的完整开发模式，以及布局/滚动/CSS 优先级等高频踩坑。
> 案例位置：`P.Mould/Wongoing.Mould.WebSite/Plugins/Mould/Equip/MouldChangeManager/`

## 一、页面定位与最终效果

- **用途**：展示硫化机（`MAJOR_TYPE_ID='06'`）当前左右模具周期号，与本周/上周标准周期号比对，不一致标红报警；双击卡片查看更换记录。
- **布局**：顶部固定栏（上周/本周标准周期号 + 刷新/排序按钮）+ 下方 12 列网格卡片区域。
- **卡片规则**：相同 `EQUIP_UUID` 的机台落到同一列、向下堆叠；按 UUID 数值升序决定列号，同列内机台号降序排列。
- **交互**：每分钟自动刷新；双击左/右模查看更换记录 Top10；报警优先排序切换。

## 二、整体架构（四文件分层）

```text
EquipDotNoVisual.aspx          ← 页面骨架：Viewport(BorderLayout) + DataView + 弹窗
EquipDotNoVisual.aspx.cs       ← 后端：DirectMethod 加载数据 / 弹窗查日志
equipdotnopanel.css            ← 卡片/网格/报警样式
SbeEquipState.xml(BusinessMapper)  ← 取数 SQL：GetDotNoCompare@SbeEquipState
```

### 2.1 页面骨架（aspx）

```text
Viewport (BorderLayout)
├─ pnlUnitTitle [Region=North]         ← 顶部工具栏：刷新 / 报警优先排序
└─ MainPanel [Region=Center, VBoxLayout]
   ├─ HeaderInfo [Height=80]           ← 上周/本周标准周期号（固定，z-index 浮起）
   └─ DataViewMachines [Flex=1, AutoScroll]  ← 12 列网格卡片（CSS Grid）
└─ winDotLog [Window, Modal]           ← 周期号更换记录弹窗（GridPanel）
```

要点：
- **DataView 的 `Cls` 是关键**：自定义类（如 `dataview-center`）会加在 DataView **根元素**上。CSS Grid 要作用在这一层。
- **`ItemSelector="div.machine-card"`**：告诉 ExtJS「一条记录 = 哪个 DOM 节点」，悬停/选中状态依赖它。
- **`Tpl` 里用 XTemplate 语法**：`{字段名}` 取值、`{values.X===1 ? 'alarm':''}` 做条件 class。

### 2.2 后端（aspx.cs）

- 用 `XXXManager.GetDataTableByStatement("SQL语句ID", 参数字典)` 调用 iBATIS。
- `LoadData()` 把 DataTable 绑到 `MachineStore`；首行取标准周期号，用 `X.AddScript` 注入到页面 `<span>`。
- `RefreshData` / `ShowDotLog` 标 `[DirectMethod]` 供前端 `App.direct.XXX()` 调用。
- 自动刷新靠前端 `setInterval(function(){ App.direct.RefreshData(); }, 60000)`。

## 三、SQL 设计要点（iBATIS BusinessMapper）

`GetDotNoCompare@SbeEquipState` 的核心：**取数 + 比对报警 + 分组列号**，三件事一条 SQL 搞定。

```sql
SELECT
    i.EQUIP_CODE,
    e.DOT_NO_LEFT, e.DOT_NO_RIGHT,
    r_curr.SERIAL_CODE  AS STANDARD_DOT_NO,
    r_prev.SERIAL_CODE  AS PREV_STANDARD_DOT_NO,
    -- 为空时不报警（IS NOT NULL 判断，避免 NULL<>X 的歧义）
    CASE WHEN e.DOT_NO_LEFT  IS NOT NULL AND e.DOT_NO_LEFT  <> r_curr.SERIAL_CODE THEN 1 ELSE 0 END AS LEFT_ALARM,
    CASE WHEN e.DOT_NO_RIGHT IS NOT NULL AND e.DOT_NO_RIGHT <> r_curr.SERIAL_CODE THEN 1 ELSE 0 END AS RIGHT_ALARM,
    i.EQUIP_UUID,
    c.UUID_RANK,
    ((c.UUID_RANK - 1) % 12 + 1) AS UUID_COL        -- 落到第几列（1~12）
FROM SBE_EQUIP i
    LEFT JOIN SBE_EQUIP_STATE e ON e.EQUIP_CODE = i.EQUIP_CODE
    LEFT JOIN (
        SELECT EQUIP_UUID,
               DENSE_RANK() OVER (ORDER BY TRY_CAST(EQUIP_UUID AS BIGINT)) AS UUID_RANK
        FROM (SELECT DISTINCT EQUIP_UUID FROM SBE_EQUIP WHERE MAJOR_TYPE_ID='06') u
    ) c ON c.EQUIP_UUID = i.EQUIP_UUID
    CROSS APPLY (  -- 本周标准周期号
        SELECT TOP 1 SERIAL_CODE FROM tb_EQ_SET_DOT_RULES
        WHERE CAST(GETDATE() AS DATE) BETWEEN CAST(STR_DATE AS DATE) AND CAST(END_DATE AS DATE)
        ORDER BY STR_DATE, SERIAL_CODE
    ) r_curr
    CROSS APPLY (  -- 上周标准周期号
        SELECT TOP 1 SERIAL_CODE FROM tb_EQ_SET_DOT_RULES
        WHERE DATEADD(WEEK,-1,CAST(GETDATE() AS DATE)) BETWEEN CAST(STR_DATE AS DATE) AND CAST(END_DATE AS DATE)
        ORDER BY STR_DATE, SERIAL_CODE
    ) r_prev
WHERE i.MAJOR_TYPE_ID = '06'
ORDER BY TRY_CAST(i.EQUIP_UUID AS BIGINT), i.EQUIP_CODE DESC;   -- 列升序、同列机台降序
```

### 3.1 关键技术点

| 需求 | 手法 | 说明 |
|---|---|---|
| 主表切换、空机台也显示 | `FROM SBE_EQUIP LEFT JOIN SBE_EQUIP_STATE` | 主表选机台主数据，状态表 LEFT JOIN，未维护状态的机台也会出现 |
| 取「当前生效」的标准号 | `CROSS APPLY + TOP 1 + 日期 BETWEEN` | 按区间取当前生效规则，符合"周维度有效期"语义 |
| 取「上周」标准号 | `DATEADD(WEEK,-1,GETDATE()) BETWEEN ...` | 复用同一张规则表，靠日期区间匹配上周段 |
| 同 UUID 落同一列 | `DENSE_RANK() % 12` 算列号 | 去重 UUID 排序编号，取模映射到 1~12 列 |
| UUID 是数字串按数值排 | `TRY_CAST(EQUIP_UUID AS BIGINT)` | 字符串排序会 `1234<234`，转数值才正确；`TRY_CAST` 防脏数据报错 |
| 为空不报警 | `CASE WHEN ... IS NOT NULL AND ...<>...` | 显式判空，比依赖 `NULL<>X` 走 ELSE 更清晰 |
| 同列内机台从大到小 | `ORDER BY ... EQUIP_CODE DESC` | 列间顺序由第一个排序键控制，列内顺序由第二个 |

### 3.2 前端配套：Tpl 用 inline grid-column 指定落列

```html
<tpl for=".">
  <div class="machine-card {[values.LEFT_ALARM===1||values.RIGHT_ALARM===1?'alarm':'']}"
       style="grid-column: {UUID_COL};">
    ...卡片内容...
  </div>
</tpl>
```
- Store Model 必须声明 `UUID_COL`（`Type="Int"`），Tpl 才能取到。
- `grid-column` 用 inline style，值直接来自 SQL 的 `UUID_COL`，避免在 CSS 里硬编码列号。

## 四、CSS Grid 多列布局（最易踩坑部分）

### 4.1 核心 CSS

```css
.dataview-center {
    display: grid !important;
    grid-template-columns: repeat(12, minmax(130px, 1fr)) !important;
    grid-auto-flow: row dense !important;   /* 同列卡片自动向下堆叠 */
    align-items: start !important;
    gap: 4px !important;
    box-sizing: border-box !important;
    padding: 4px !important;
    overflow: auto !important;              /* 滚动容器就是 DataView 根元素本身 */
}
.dataview-center .machine-card {
    float: none !important;                 /* 抵消 ExtJS 默认给 dataview 子项加的 float */
    display: block !important;
    width: auto !important;
}
```

### 4.2 ⚠️ 最大坑：CSS 选择器命不中（症状：改了 CSS 完全没效果）

**现象**：`.dataview-center .x-dataview-component { display:grid }` 写了，页面"跟之前一样"。

**根因**：ExtJS classic 的 `Ext.view.View`（即 Ext.NET `<ext:DataView>`）**把 tpl 内容直接作为根元素的子节点渲染**，没有 `.x-dataview-component` 这层内层 div。

**判断方法**：F12 看 DOM，卡片 div 上若带 `role="option"` + `data-boundview="DataViewMachines"`，说明它是 DataView 根元素的直接子节点，没有中间层。

**解法**：grid 直接作用在 DataView 根元素（即 `Cls` 指定的那个类）本身，**不要写成 `.cls .子类`**。

> 经验：不要假设 ExtJS 的 DOM 层次。先用 F12 确认 tpl 卡片的父元素到底挂了哪个 class/id，再写选择器。

### 4.3 ⚠️ 第二大坑：滚动失效（症状：上下左右都拖不动）

**错误写法**（自己挖坑）：
```css
#DataViewMachines { overflow: visible !important; }   /* ❌ 覆盖了 overflow:auto */
```
**根因**：`.dataview-center`（类选择器）和 `#DataViewMachines`（ID 选择器）指向**同一个根元素**，而 **ID 优先级 > 类**，于是 `overflow:visible` 把 `overflow:auto` 顶掉，ExtJS 的 `AutoScroll` 也被覆盖 → 全方向滚不动。

**解法**：滚动统一由 DataView 根元素的 `overflow:auto` 承担，**不要给同元素再加 `overflow:visible` 覆盖**。如确需放行外层布局，只改外层（如 `.x-box-inner`），不要碰 DataView 自己。

### 4.4 ⚠️ 第三坑：滚动内容遮挡上方固定栏

**症状**：DataView 上下滚动时，卡片/滚动条蹭到顶部"标准周期号"栏。

**根因**：HeaderInfo 没有不透明背景 + 没有层级，下方滚动内容透上来。

**解法**：
```css
.header-info-fixed {
    position: relative !important;    /* z-index 生效前提 */
    z-index: 10 !important;           /* 层级浮到最上 */
    background: #E8F4FD !important;   /* 不透明背景挡住透上来的内容 */
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);   /* 视觉分隔 */
}
```
aspx 里 HeaderInfo 加 `Cls="header-info-fixed"` + 适当 `Height` + `margin-bottom` 拉开间距。

### 4.5 CSS 缓存坑

静态 CSS 改了不生效，多半是浏览器/IIS 强缓存。**链接加版本号破缓存**：
```html
<link href="equipdotnopanel.css?v=20260723a" rel="stylesheet" />
```
每次改 CSS 递增版本号字母（a→b→c…）。也可在 `<head>` 内再写一段 `<style>` 兜底，确保即使外部 CSS 没更新，inline 也能生效。

## 五、踩坑记录总表

| # | 问题 | 根因 | 解法 |
|---|---|---|---|
| 1 | SQL 改 LEFT JOIN 后卡片变多，下方看不到 | DataView 默认不滚动，溢出被父容器 `overflow:hidden` 裁掉 | DataView 加 `AutoScroll="true"` |
| 2 | CSS Grid 写了完全没效果（"跟之前一样"） | 选择器 `.cls .x-dataview-component` 命不中，Ext.view.View 无内层 div | grid 直接作用于 DataView 根元素（`Cls` 类）本身 |
| 3 | 上下左右都滚不动 | 给同根元素加 `#id { overflow:visible }` 覆盖了 `overflow:auto`（ID 优先级更高） | 滚动统一由根元素 `overflow:auto` 承担，不加 visible 覆盖 |
| 4 | 滚动时卡片遮挡上方固定栏 | 固定栏无背景/无层级，内容透上来 | 固定栏 `position:relative + z-index:10 + 不透明背景` |
| 5 | CSS 改了不生效 | 浏览器/IIS 强缓存 | 链接加 `?v=版本号`；head 内 inline style 兜底 |
| 6 | UUID 是数字串，列顺序错乱 | 字符串排序 `1234<234` | `DENSE_RANK() OVER (ORDER BY TRY_CAST(EQUIP_UUID AS BIGINT))` |
| 7 | 改 SQL 后脏数据可能让 CAST 报错 | 空/非数字值 CAST 失败中断查询 | 用 `TRY_CAST`（失败返回 NULL 不报错） |
| 8 | 报警优先排序后机台号变成升序 | 前端 `store.sort` 的 `EQUIP_CODE` 方向是 ASC，与 SQL DESC 不一致 | 若需一致，把 aspx 里排序按钮 JS 的 `EQUIP_CODE` 也改 `DESC` |

## 六、可复用模式

### 6.1「固定表头 + 可滚动内容区」布局
```text
Panel(VBoxLayout Align=Stretch)
  ├─ Header [固定高度 + position:relative + z-index + 不透明背景]
  └─ DataView/GridPanel [Flex=1 + overflow:auto]
```
适用：看板、监控大屏、可视化看板。

### 6.2「分组落列」SQL 模式
```sql
-- 1) 去重分组键 + 排名
DENSE_RANK() OVER (ORDER BY 分组键) AS RANK
-- 2) 取模映射到 N 列
((RANK - 1) % N + 1) AS COL_NO
-- 3) 结果集按 分组键, 项 排序（保证同组项相邻、grid-auto-flow:dense 才能堆成一列）
ORDER BY 分组键, 项
-- 4) Tpl 用 style="grid-column:{COL_NO}" 指定落列
```
适用：任何「按某字段分组、每组占一列、N 列网格」的可视化需求。

### 6.3「周期/有效期」取数模式
```sql
CROSS APPLY (
    SELECT TOP 1 规则字段 FROM 规则表
    WHERE CAST(GETDATE() AS DATE) BETWEEN CAST(STR_DATE AS DATE) AND CAST(END_DATE AS DATE)
    ORDER BY STR_DATE, 规则字段
) r_curr
```
适用：按时间区间生效的配置/规则/标准值查询（标准周期号、有效期参数、阶段性配置等）。

## 七、调试排查清单（不生效时按序自查）

1. **SQL 是否返回新字段**：后端断点 / SQL 直接跑，确认 `UUID_COL`、`EQUIP_UUID` 有值。
2. **Store Model 是否声明字段**：未声明的字段 Tpl 取不到。
3. **Tpl 是否输出 inline style**：F12 看卡片 div 上有没有 `style="grid-column: N"`。有 → SQL/Tpl OK；没有 → 检查字段名。
4. **CSS 选择器是否命中**：F12 看 tpl 卡片的**直接父元素** class 是什么，grid 要作用在那一层。
5. **overflow 是否被覆盖**：F12 Computed 看 `overflow` 是否为 `auto`；若有更高优先级规则覆盖成 `visible/hidden`，调整选择器或加 `!important`。
6. **CSS 是否缓存**：链接加版本号或强刷（Ctrl+F5）。
7. **固定栏是否被遮挡**：看固定栏 Computed 是否 `z-index>0` 且有不透明背景。

## 八、关联

- 页面骨架与布局容器（Viewport/Panel/Layout）：`extnet-page-skeleton.md`
- DirectMethod 与前端数据交互：`extnet-directmethod-and-data.md`
- 事件机制（Listeners/DirectMethod）：`extnet-event-mechanisms.md`
- 定时刷新（setInterval / TaskManager）：`js-setinterval-settimeout.md`
- iBATIS 语句命名与 `GetPageDataByReader` 陷阱：`ibatis-statement-naming-and-getpagedatabyreader-pitfall.md`
- CROSS APPLY / OUTER APPLY 用法：`sql-outer-apply-cross-apply.md`
- DENSE_RANK / 分组取模落列（本页所用）：本文第六章 6.2
- 看板类 TableLayout 实现（另一种卡片布局思路）：`extnet-desktop-framework-guide.md`

## 九、分侧三态着色 + 当班硫化计划置灰（2026-09-10 演进，取代 §3.2 旧 Tpl）

### 卡片新结构（结构性放大）
```html
<tpl for=".">
  <div class="machine-card" style="grid-column: {UUID_COL};">
    <div class="card-half card-side-click {[三态class]}" data-equip="{EQUIP_CODE}L">左模<br/>{DOT_NO_LEFT}</div>
    <div class="card-half card-side-click {[三态class]}" data-equip="{EQUIP_CODE}R">右模<br/>{DOT_NO_RIGHT}</div>
    <div class="card-title">{EQUIP_CODE}</div>   <!-- position:absolute 半透明白条压顶 -->
  </div>
</tpl>
```
- 三态优先级：**当班无计划灰 #D9D9D9 > 周期号错红 #FFB3B3(+alarm-text) > 正确绿 #D6F5D6**；无周期号数据不着色（透卡片底色）。整卡 normal 绿已废弃。
- Tpl 条件写法：`{[values.LEFT_HAS_PLAN===0 ? 'no-plan' : (values.LEFT_ALARM===1 ? 'alarm-text side-alarm' : (values.LEFT_ALARM===0 && values.DOT_NO_LEFT ? 'side-ok' : ''))]}`。
- **布局坑**：`.dataview-center div.machine-card` 的 `display:block !important`（aspx 内联 style 与 css 文件两处都有）会压掉卡片 flex，做左右半侧布局时必须两处同步改 `display:flex !important`，否则色块上下堆叠。

### 当班硫化计划判定（GetDotNoCompare 增强）
- SQL 新增 `LEFT_HAS_PLAN/RIGHT_HAS_PLAN`：`EXISTS(CPP_CURING_PLAN p JOIN CPP_CURING_PLAN_DETAIL d ON p.PLAN_ID=d.PLAN_ID WHERE p.PLAN_DATE=#PLAN_DATE# AND p.SHIFT_CODE=#SHIFT_CODE# AND p.EQUIP_CODE=i.EQUIP_CODE AND d.EQUIP_POSITION='L'/'R')`。
- **别照抄 Curing 大屏的 `d.PLAN_AMOUNT > 0`**：本库计划明细该列不满足，加上即全灰；口径=用户样例 SQL（PLAN_DATE+SHIFT_CODE+EQUIP_CODE+明细按侧）。
- `CPP_CURING_PLAN` 在 Mould 库**裸表名直查**（同库，非跨库）；`PLAN_DATE` 是 varchar(10) 存 yyyy-MM-dd（纯字符串比较）；`EQUIP_POSITION` 实证存 'L'/'R'。
- 当班班次：后台按 `SSB_SHIFT` 时间窗判定（DetectCurrentShift/ApplyShiftDate 两方法照搬 Curing `CuringEquipStateVisual.aspx.cs`：昨/今两日期 × 各班次 [begin,end) 窗口，DayFlag=1 跨天结束+1天，凌晨自动归昨晚夜班；未匹配到班次则空班次码=全灰兜底），把 PLAN_DATE(yyyy-MM-dd)/SHIFT_CODE 传给 SQL。
- **改 Mapper XML 后必须重建 Wongoing.Mould.Mapper.dll 并同步 WebSite\bin**（XML 是嵌入资源，详见 mould-mapper-convention.md 第九章）；bin 变更会掉登录态。

## 十二、JS 显隐卡片的三条铁律（2026-09-19 CuringEquipStateVisual 图例筛选实证）

场景：DataView 卡片墙上按汇总档筛选机台（点击图例只显示该档卡）。三条都是实测踩出来的，违反任何一条筛选都会"看似工作实际失效"或机台跳位：

1. **author `!important` 压制 JS 内联样式**——卡片墙防御规则 `.dataview-state-grid .state-card { display: block !important; }`（本文 §一 的 grid 布局防御）会压过 `element.style.display = 'none'`（CSS 层叠：author !important > 内联普通声明）。**显隐必须走 class**：JS 切 `.filtered-out` 类，css 写更高 specificity 的 `.dataview-state-grid .state-card.filtered-out { display: none !important; }`（同为 !important 比 specificity，0,3,0 > 0,2,0 稳赢），不要动防御规则本身。
2. **断言显隐必须 `getComputedStyle(el).display`**——读 `el.style.display` 只反映"JS 写了什么"不反映"视觉是什么"，被 !important 压制时内联值照读 'none' 但卡片仍显示（假阳性；截图粗看也漏，靠代码级审查才发现）。className 方案下同理：断言 computed display，别断言 className 已切换就收工。
3. **`grid-auto-flow` 用 `row` 不用 `row dense`**——dense 的定义行为就是回填空洞：一旦有卡片 display:none，同列后继卡上移顶进空格，"机台位置稳定"（车间按固定位置找机台）即被破坏。本文 §一 原写法 `row dense` 在无筛选时代价不可见，加显隐筛选后才暴露；改 `row` 后筛选态 12 卡位置零移动（getBoundingClientRect 前后对照实证）。

配套经验：筛选别动 ExtJS Store（filter 后 `store.getRange()` 返回过滤子集，同页其他汇总计数会被污染——汇总口径必须全量）；DOM 匹配键从卡片节点自带文本（如 `.card-code`）取；Ext 渲染晚于页尾 script 的交互元素用 `jQuery(document).on('click', 选择器, ...)` 委托绑定。完整页面实证见 [[curing-equipstate-visual]] §五。

---

## 十三、显式 grid 定位与断言坐标系补充（2026-09-19 第二轮实证，接第十二节）

第十二节坑 3 的修正与深化——**只删 dense 改 row 是错解**：

1. **`grid-auto-flow: row`（sparse）下"只显式列不显式行"会阶梯化**——sparse 自动放置光标单调前进：第 1 列 N 张卡占满后光标停在 (N,2)，第 2 列的卡从第 N 行起放，第 3 列从第 2N 行起……252 卡 12 列排成"一行一卡"的斜梯（各列首卡 offsetTop 相差一整列高度，实测列 1@76、列 2@4681）。dense 时代靠回填掩盖了这一点，删 dense 即暴露。**终态：SQL 出行号（ROW_NUMBER() OVER (PARTITION BY 分组键 ORDER BY 组内排序)），tpl `style="grid-column:{列}; grid-row:{行}"` 双显式定位**——auto-placement 完全不参与，dense/sparse 无副作用，显隐筛选后沟位纹丝不动。教训：CSS Grid 多列卡片墙凡是要"分组落列 + 位置稳定"的，**行列都要显式**，别指望 auto-flow。

2. **位置对比断言用 offsetLeft/offsetTop，勿用 getBoundingClientRect**——rect 是视口相对坐标，可滚动容器（DataView AutoScroll 横向滚动）的 scrollLeft 一变，同一张卡的 rect.left 全变（实测把"位置零移动"误报成"8 卡移动"，真值 offsetLeft 全部未变）。凡断言"位置不变"，一律 offset 坐标系。