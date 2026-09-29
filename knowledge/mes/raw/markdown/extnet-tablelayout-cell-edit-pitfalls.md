---
category: 技术-.NET
factory: 通用
module: Ext.NET
status: active
tags: [Ext.NET, TableLayout, 看板, 目标实绩标红, 查询格DOM定位, 双周轮询格, checkWasteOverrun, 踩坑]
title: Ext.NET TableLayout 看板单元格可编辑 + DirectMethod 存库 + 底色动态刷（实战踩坑全记录）
updated: 2026-08-29
---

# Ext.NET TableLayout 看板单元格可编辑 + DirectMethod 存库 + 底色动态刷（实战踩坑全记录）

> 在 Ext.NET TableLayout 看板（31×31 网格，446+ 单元格）上实现：双击单元格弹窗编辑 → DirectMethod 存库 → 刷新回填 → 按数据来源动态刷底色。
>
> 记录全过程的踩坑和解法，每个坑都花过大量时间排查。

## 一、踩坑速查表

| 坑 | 现象 | 根因 | 解法 |
|---|---|---|---|
| 1 | Label 的 Html 显示字面文本 | Label 编码 HTML | 改用 Component |
| 2 | Component 的 `&lt;div&gt;` 不渲染 | aspx 实体编码当字面 | Html 里直接用 `<` `>` |
| 3 | getAttribute is not a function | Ext 的 t 是包装对象 | 用 `e.getTarget()` |
| 4 | 双击 td 找不到 data-key | div 在 td 内部，向上找不到 | 双向查找（向上+向下） |
| 5 | 匿名类型转换失败 | WebSite 动态编译跨 DLL | 用 Hashtable 传参 |
| 6 | SelectedDate.HasValue 报错 | 是 DateTime 非 DateTime? | 用 `!= DateTime.MinValue` |
| 7 | X.JsCall 不存在 | 方法名不对 | 用 `X.AddScript` |
| 8 | JS 设了 backgroundColor 没效果 | CSS !important 覆盖 inline | 用 `setProperty('important')` |
| 9 | CellCls 运行时没渲染到 DOM | Label CellCls 不可靠 | 前端模拟网格算坐标 |
| 10 | Component 白底盖住 td 底色 | 内部 div 默认白底 | CSS 设 `> div { transparent }` |
| 11 | Ext.getCmp(key) 找不到控件 | 嵌套控件 ID 带前缀 | 前端遍历 DOM 算坐标 |
| 18 | 改了 CSS 没变化 | td 被运行时追加多类，`!important` 同特异性按书写顺序裁决 | 用双类选择器 `.prod-split.ds-import` 提高特异性 |
| 19 | 只读格被刷成导入色 | MarkDataSources 网格算法坐标错位 | CSS 高特异性覆盖 + JS key 白名单 skip |
| 20 | 查询格改导入格后双击无反应 | initQuerySpans 误删 div[data-key] | 清空前检查 td.querySelector('div[data-key]') |
| 21 | 查询格表有数据页面不显示 | 存储 ROT_DATE 但前端按 DATA_DATE 查 | 普通查询格用 DATA_DATE=@Today 存储 |
| 22 | 新导入格不继承前一天 | 没加入 @ImportKeys | 存储过程 @ImportKeys VALUES 加 key |
| 23 | ECharts y 轴多位小数 | maxVal*1.15 后自动均分 | axisLabel.formatter Math.round |
| 24 | 明细格内容撑大单元格 | 多行 HTML 直接填入 | 单元格显示汇总+原生悬浮框多列展示 |
| 25 | 特例页需要控制编辑权限 | 继承 System.Web.UI.Page 不走权限基类 | 声明权限类+手动查V_SSP_USER_ALL_ACTION+前端_canEdit拦截 |
| 26 | 聚合排除报废胎号怎么写都错 | SUM不能嵌NOT EXISTS+LEFT JOIN膨胀+DISTINCT全表 | CTE分步收窄+EXISTS精确匹配 |
| 27 | 悬浮框超出视口底部 | 只做右溢出没做下溢出 | 四方向边界检测 |

## 二、坑20：查询格从 Label 改 Component 后双击不响应 — initQuerySpans 误删 div[data-key]

### 现象
把看板某行原本是 `<ext:Label>` 的查询格改成 `<ext:Component Html="<div data-key='r9c6'>...">`（导入格），编译部署后双击完全无反应，控制台无输出。相邻的 r9c4 写法一模一样却正常。

### 根因
前端 `initQuerySpans` 遍历所有 td，用渲染坐标生成 key，查 `_cellTypes[key]`。如果命中"查询"，就执行 `while (td.firstChild) { td.removeChild(td.firstChild); }` 清空 td 内容再注入 query-val span。这会把 Component 的 `div[data-key]` 清掉，双击处理找不到 `div[data-key]` → 无反应。

### 解法
`initQuerySpans` 清空前加保护：td 里已有 `div[data-key]`（导入格 Component）则跳过：
```js
if (src === '查询' && !td.querySelector('.query-val') && !td.querySelector('div[data-key]')) {
```

## 三、坑21：查询格存储用 ROT_DATE 还是 DATA_DATE — 不匹配导致前端查不到值

### 要点
| 格子类型 | 存储字段 | 前端查询方式 |
|---------|---------|------------|
| 普通查询格/导入格 | `DATA_DATE=@Today` | 按看板日期查 |
| 双周轮询格（行≤23 列17-31） | `ROT_DATE=实际日期` | 按两周范围查 |
| 单周轮询格（行14-17 列3-9） | `ROT_DATE=@Today` | 按完整key+ROT_DATE查 |
| 月度格（行25-31） | `ROT_DATE=当月1号` | 按当年各月1号查 |

## 四、坑22：新增导入格忘记加入 @ImportKeys — 不继承前一天数据

新增导入格时必须同步更新三处：①aspx 改 Component 带 data-key；②xlsx 改数据来源为"导入"；③存储过程 @ImportKeys 加 key。

## 五、坑23：ECharts y 轴出现多位小数

手动设 max 后 ECharts 的自动分割不会保证整数刻度。y 轴 axisLabel 加 `formatter: function(v) { return Math.round(v); }`。

## 六、坑24：明细格内容过多撑大单元格 — 原生 DOM 悬浮框 + 多列 + 动画

Ext.ToolTip 在 TableLayout 看板里不可靠（maxWidth/width 不生效、内容被截断），改用原生 DOM div 悬浮框。多列排列：把 `<br/>` 分隔的内容转成 `display:inline-block` 的 span。延时关闭 + CSS 动画（opacity + transform:scale）。

## 七、坑25：特例页（继承 System.Web.UI.Page）如何做编辑权限控制

三层方案：
1. 声明权限类 `__ : Wongoing.Web.UI.___`（需要 `using Wongoing.Web.UI.Entity`）
2. 后端手动查权限 `GetIntByStatement` + `V_SSP_USER_ALL_ACTION` 视图（用 ACTION_ID 直接查）
3. 前端双击拦截 `_canEdit` 标志

## 八、坑26：SUM(CASE WHEN ... NOT EXISTS) 报错 + LEFT JOIN 行数膨胀 + DISTINCT 全表扫描

### 三种坑
1. 聚合嵌 NOT EXISTS → 报错：SQL Server 不允许
2. LEFT JOIN 一对多膨胀：报废表一个胎号多条记录 → 行翻倍
3. DISTINCT 全表扫描：没时间范围，扫全表

### 解法：CTE 分步收窄 + EXISTS 精确匹配
```sql
;WITH FcheckMonth AS (
    SELECT TYRE_NO, GRADE, RECORD_TIME
    FROM FQF_FCHECK_INFO WITH(NOLOCK)
    WHERE RECORD_TIME >= @MonthStart AND RECORD_TIME < @DayEnd AND DELETE_FLAG = 0
),
ScrapTyres AS (
    SELECT DISTINCT TYRE_NO
    FROM FQS_SCRAP_INFO WITH(NOLOCK)
    WHERE EXISTS (SELECT 1 FROM FcheckMonth WHERE FcheckMonth.TYRE_NO = FQS_SCRAP_INFO.TYRE_NO)
)
SELECT
    ISNULL(SUM(CASE WHEN fc.RECORD_TIME >= @DayStart AND fc.RECORD_TIME < @DayEnd THEN 1 ELSE 0 END), 0),
    ISNULL(SUM(CASE WHEN fc.RECORD_TIME >= @DayStart AND fc.RECORD_TIME < @DayEnd AND fc.GRADE <> '1' AND sc.TYRE_NO IS NULL THEN 1 ELSE 0 END), 0)
FROM FcheckMonth fc
LEFT JOIN ScrapTyres sc ON sc.TYRE_NO = fc.TYRE_NO;
```

### 教训
- 聚合函数里不能嵌 NOT EXISTS，改 LEFT JOIN + IS NULL。
- LEFT JOIN 一对多表必须先 DISTINCT。
- EXISTS 匹配收窄后的主表比加时间范围更准确。

## 九、坑27：原生 DOM 悬浮框定位超出视口底部

### 解法：四方向智能边界检测
```js
var boxW = 620, boxH = 420, gap = 14;
var vw = window.innerWidth, vh = window.innerHeight;
var x = mouse.x + gap;
if (x + boxW > vw) { x = Math.max(0, mouse.x - gap - boxW); }
var y = mouse.y + gap;
if (y + boxH > vh + window.scrollY) { y = Math.max(0, mouse.y - gap - boxH); }
```

---

## 十、坑28：目标 vs 实绩标红——查询格 DOM 定位 + 双周轮询格逐天对比

### 现象
看板需要目标 vs 实绩对比，不达标时实绩格文字标红。涉及三种格子类型：
1. 普通导入格（Component 带 data-key）——目标手填
2. 普通查询格（Label，前端 initQuerySpans 注入 .query-val span）——作业自动算
3. 双周轮询格（行号 key，c17-c31 对应14天）——按天对比

### 三个坑

**坑1：查询格找不到 DOM**
标红代码用 `document.querySelector('div[data-key="r4c6"] .cell-val')` 找实绩格——但查询格是 `.query-val` span，不是 `div[data-key] .cell-val`。
```js
// ❌ 只找导入格
var actualSpan = document.querySelector('div[data-key="' + actualKey + '"] .cell-val');
// ✅ 导入格和查询格都找
var actualSpan = document.querySelector('div[data-key="' + actualKey + '"] .cell-val');
if (!actualSpan) { actualSpan = document.querySelector('.query-val[data-key="' + actualKey + '"]'); }
```

**坑2：标红时机在查询格填值前**
`fillCellValues` 先填导入格再填查询格。如果标红检查放在导入格填值后，查询格的 DOM 还没填值，`_cellValues[key]` 有值但 DOM 还没更新。
**解法**：标红检查放在**查询格填值循环之后**，确保所有格子都填完。

**坑3：双周轮询格逐天对比**
双周轮询格用行号 key（如 r2/r5），c17-c31 对应14天。目标和实绩是不同行号，需要遍历14天逐列对比：
```js
for (var col = 17; col <= 31; col++) {
    if (col === 24) { continue; }  // c24 无格子
    var tKey = tRow + 'c' + col;   // 如 r2c17
    var aKey = aRow + 'c' + col;   // 如 r5c17
    // 从 _cellValues 取值对比，找 DOM 标红
}
```

### 完整配置

```js
// 普通对比对（单值格/查询格）
var _comparePairs = [
    ['r2c3','r2c4','>'],    // 废品类：实绩>目标标红
    ['r2c6','r4c6','>'],
    ['r6c4','r6c6','>'],
    ['r11c4','r11c6','>'],
    ['r6c8','r6c9','<'],    // 产量类：实绩<目标标红
    ['r6c12','r6c13','<'],
    ['r26c18','r27c18','<'],
    ['r26c21','r27c21','<'],
    ['r29c18','r30c18','<'],
    ['r29c21','r30c21','<']
];
// 双周轮询对（行号key，遍历14天逐列对比）
var _rotaryPairs = [
    ['r2','r5','<'], ['r3','r6','<'], ['r4','r7','<'],
    ['r16','r17','<'], ['r16','r18','<'],
    ['r19','r20','<'], ['r21','r22','<']
];
```

### 三个触发时机
| 时机 | 调用方式 | 说明 |
|------|---------|------|
| 页面加载/切换日期 | `fillCellValues` 末尾 `checkWasteOverrun()` | 全量检查所有对 |
| 保存编辑 | `saveCellEdit` 末尾 `checkWasteOverrun(key)` | 只检查被编辑的那一对 |

### 教训
- **查询格 DOM 用 `.query-val[data-key="..."]` 找**，不是 `div[data-key] .cell-val`。两种都要兼容。
- **标红检查必须在所有格子填值后执行**，不能在导入格填完、查询格还没填时就检查。
- **双周轮询格用行号 key，需遍历 c17-c31 逐列对比**，不能用单个 key 直接对比。

---

## 十一、速度查（新增）

| 坑 | 现象 | 根因 | 解法 |
|----|------|------|------|
| 28 | 标红不生效/不全 | 查询格DOM定位错+时机错+轮询格需逐天 | query-val选择器+填值后检查+遍历14天 |

---

## 十二、坑29：纸质表单类 TableLayout 的跨行跨列/定宽/只读值格（成型作业检查实战）

在 MoldShiftInspection 作业检查页签用 TableLayout 复刻纸质点检表（一次法 27 行结构/二次法 30 行，7 列），全部验证可用的做法：

1. **跨行跨列**：Item 上直接 `RowSpan="3"` / `ColSpan="2"`（官方 Simple_in_Markup 写法）。跨行格只声明一次，后续行不再放占位格。
2. **列宽不能 td:nth-child**：大量跨行跨列后各行 td 序号与逻辑列错位，nth-child 定宽会张冠李戴。正解=JS 向 Ext 渲染出的 `<table>` 注入 `<colgroup>`+CSS `table-layout:fixed`：`tbl.getEl().down('table.x-table-layout')` 拿 DOM，无 colgroup 则建（7 个 `<col>` 插到 firstChild 前），逐个设 `style.width='15%'`。渲染后幂等执行（renderJob 时调）。
3. **静态文本格用 ext:Component**（Html 里直接写 `<div class="job-cell">`，配合坑2/坑10 的白底/实体转义教训）；**只读值格用 ext:DisplayField**：`Cls` 给底色（`.job-z .x-form-display-field{background:#FFFFE1;text-align:center}`），标红用 `addCls/removeCls('job-z-over')`（Component 通用 API，配 `!important`），`setValue()` 填值。
4. **值绑定复刻 Android 映射**：JS 数组 {item, part, df/cbx} 按 `ItemName+'|'+EquipPartName` 索引数据行填值，与 Android `_paramMapping` 同构——固定模板结构+运行时填值，模板未覆盖的数据行计数提示不静默丢弃。
5. **行内 ComboBox 改即存防回灌**：`<Listeners><Change Fn="onJobJudgeChange" /></Listeners>`（Fn 签名 `(combo, newValue, oldValue)`）；`_jobSaving[id]` 标志：初始 `setValue` 前置 true 后置 false，失败回滚 `setValue(oldValue)` 也要在标志未释放时执行——否则回灌的 change 再触发保存形成死循环。
6. **双模板切换**：两张表都声明、默认 Hidden，查询后按数据行字段（本例 ItemCode）`setVisible` 互斥切换，比动态改 TableLayout 结构便宜得多。

---

## 十三、坑30：页面 <style> 会被 Ext 后注入的样式按加载顺序盖掉——字段级覆盖必须 !important 且打到内部元素

**现象**（成型作业检查纸质表单页实测）：TableLayout 单元格里 `ext:DisplayField` 的 `text-align:center` 写在页面 `<style>` 里不生效（数值仍偏左）、`ext:ComboBox` 只给根 Cls 设 `width:100%` 下拉仍是内容宽不撑满格子。

**根因**：ResourceManager 把 Ext 的 css 注入在页面 `<style>` **之后**，同特异性按书写顺序裁决 → Ext 自己的字段样式（text-align、宽度收缩）赢了页面规则。

**解法**（全部 `!important` + 覆盖内部层级，不只是组件根）：

```css
/* 只读值格(DisplayField)：黄底铺在 td 上，值文字强制撑满居中 */
.job-z .x-form-display-field { width:100% !important; text-align:center !important; background:transparent !important; }
/* 下拉(ComboBox)撑满：根/item-body/trigger-wrap 表/input 四层全打 */
.job-cbx { width:100% !important; }
.job-cbx .x-form-item-body { width:100% !important; }
.job-cbx table.x-form-trigger-wrap { width:100% !important; }
.job-cbx input.x-form-field { width:100% !important; box-sizing:border-box; }
```

配套：整格底色加在父 td 上（`df.getEl().up('td').addCls(...)`），别加在组件上——Ext 组件只盖内容区，盖不满格子。

**纸质表单层级三档模板**（标题/分节/表头别共用一条规则，否则"主次不清"）：

```css
.job-title   { font-size:16px; font-weight:bold; color:#fff;    background:#157fcc; letter-spacing:4px; padding:7px 0; }
.job-section { font-size:13px; font-weight:bold; color:#1f3864; background:#d9e1f2; letter-spacing:2px; }
.job-head    { font-size:12.5px; font-weight:bold; color:#333;  background:#f2f5fa; }
```

---

## 十四、坑31（勘误并取代坑30 的字段部分）：TableLayout 单元格里放表单字段是方向性弯路——只读值用 Component，可编辑下拉用绝对定位铺满

坑30 给的"DisplayField 加 !important 链 + td 标底色类"方案在成型作业检查页实测被推翻，最终版（已验证）：

1. **只读值格不要用任何表单字段（DisplayField/TextField 只读）**——Ext 会包出 label/body/display-field 三层 DOM、根 display:table 随内容收缩、百分比高对 auto 父级失效，CSS 打补丁打不完。用 `ext:Component`（纯 div）：`setHtml(转义后的值)` 填值、`addCls/removeCls` 标红。td 的 `text-align:center` + `vertical-align:middle` 直接接管居中——但组件根必须 `display:inline-block` 参与 td 行盒（块级子元素 vertical-align 不生效）：
   ```css
   .job-tbl table.x-table-layout td > div.x-component { display:inline-block; width:100%; vertical-align:middle; }
   ```
2. **可编辑下拉铺满 td 用绝对定位，别用百分比高度链**：行高由同行文本格贡献（判定行都有文字格兄弟），td 加 `position:relative`，字段根 `position:absolute; top:2px; bottom:2px; left:2px; right:2px`——inset 给出确定高度，内部 `item-body/trigger-wrap/input` 的 `width/height:100%!important` 链才生效。百分比高度对 auto 高父级恒失效，!important 救不了。
3. **不要给 td 打标记类**（此前的 job-z-td/job-cbx-td + render 事件补标全删）：Hidden 容器里组件 rendered=false、show() 渲染异步，任何"渲染后补标"都有时机坑；CSS 选择器直接定位（`td > div.x-field` / `td > div.x-component`）零时机依赖。
4. 值填充用 `setHtml` 时必须转义（&<>），值文本是匿名 inline 内容，随 td text-align 居中。