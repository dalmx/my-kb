---
title: Ext.Net GridPanel 行底色条件高亮实现方案（过期预警 / 条码匹配）
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, GridPanel, 行底色, 过期预警, 条码高亮, GetRowClass, 条件高亮, 外部查询值高亮]
status: active
updated: 2026-08-29
---
# Ext.Net GridPanel 行底色条件高亮实现方案（过期预警 / 条码匹配）

> 本文汇总 Ext.Net GridPanel 行级背景色高亮的两种典型模式：**模式A 基于行内字段值**（过期预警）和**模式B 基于外部查询值**（条码反查匹配），含 CSS 编写、GetRowClass 函数模板、hover/selected 状态覆盖、颜色冲突排查等通用要点。

## 一、核心机制

行高亮使用 Ext.Net GridView 的 **`<GetRowClass>`** 配置，指向一个 JS 函数，函数返回 CSS 类名字符串，Ext 自动应用到该行：

```xml
<View>
    <ext:GridView ID="gvDetail" runat="server" EnableTextSelection="true">
        <GetRowClass Fn="setRowClass" />
    </ext:GridView>
</View>
```

```javascript
// 函数签名固定：返回 CSS 类名（字符串），空字符串 = 不高亮
var setRowClass = function (record, rowIndex, rowParams, store) {
    // record.data.xxx 读取行数据
    return 'some-css-class';  // 或 return '';
}
```

> **函数声明位置**：必须放在 `.aspx` 内联 `<script>` 块，不能放外部 `.js`。Ext.Net 在 ResourceManager 构建阶段按函数名查找，外部 JS 的 `var` 赋值此时可能尚未对其解析器可见（会报 `setRowClass is not defined`）。

---

## 二、模式A：基于行内字段值（过期预警）

### 适用场景

明细表按某日期字段（有效期/生产日期）判断，对行整条底色标色：已过期→红、临近→黄、正常→默认。

### CSS（复用 extExtra.css 已有类）

```css
.bgcolor-warning { background-color: #f4c414; }   /* 黄 */
.bgcolor-danger  { background-color: #d9534f; }   /* 红 */
```

> 不要重复定义；也不要用 `.x-grid-row.xxx` 前缀，直接返回类名即可被 Ext 应用到行。

### setRowClass 函数

**写法A：按有效期判断（"已过期/临近 N 天"）**

```javascript
var setRowClass = function (record, rowIndex, rowParams, store) {
    var value = record.data['有效期'];   // 字段名要和 ModelField/SQL 别名一致
    if (value != '' && value != null && value != undefined) {
        var valueDate = new Date(value);
        var now = new Date();
        var nowTs = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
        var windowTs = nowTs + 20 * 24 * 60 * 60 * 1000;   // 阈值窗口 = 20 天
        if (valueDate.getTime() <= nowTs) {
            return 'bgcolor-danger';        // 已过期 - 红
        } else if (valueDate.getTime() <= windowTs) {
            return 'bgcolor-warning';       // 临近过期 - 黄
        }
    }
    return "";
}
```

**写法B：按生产日期算存放时长（"超 N 天"）**

```javascript
var setRowClass = function (record, rowIndex, rowParams, store) {
    var value = record.data['生产日期'];
    if (value != '' && value != null && value != undefined) {
        var prodDate = new Date(value);
        var now = new Date();
        var nowTs = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
        var ageDays = (nowTs - prodDate.getTime()) / (1 * 24 * 60 * 60 * 1000);
        if (ageDays > 30) {
            return 'bgcolor-danger';        // 超生产时间30天 - 红
        } else if (ageDays > 20) {
            return 'bgcolor-warning';       // 超生产时间20天 - 黄
        }
    }
    return "";
}
```

### 配套 SQL — `是否超期` CASE 列（阈值与 JS 保持一致）

```sql
-- 按有效期（值 ≤ 今天 红色；未来窗口内 黄色）
CASE
    WHEN T1.Valid_Date <= CONVERT(VARCHAR(19), GETDATE(), 120)
        THEN '是'
    WHEN T1.Valid_Date <= CONVERT(VARCHAR(19), DATEADD(DAY, 20, GETDATE()), 120)
        THEN '即将超期'
    ELSE '否'
END [是否超期]
```

> UNION ALL 查询：CASE 必须加到**每个分支**，否则列数不匹配报错。

### 模式A 参考实现

| 页面 | 阈值规则 |
|---|---|
| `Plugins/Mix/RawMaterial/StockInfo/DynamicStock.aspx` | 有效期 1 个月 |
| `Plugins/Mix/RawMaterial/Report/MixRealTimeStock.aspx` | 生产日期 30/20 天 |
| `Plugins/Mix/ReturnRubber/ReturnRubberDynamicStock.aspx` | 有效期 20 天 |
| `Plugins/Semi/Report/MaterialRealTimeStock.aspx` | 页面级 CSS（`.x-grid-row-overdue`/`.x-grid-row-near-expire`）+ `setDetailRowClass` |
| `Plugins/Semi/Report/SemiReturnRubberRealTimeStock.aspx` | `makeRowClass` 工厂函数生成两个 GetRowClass |

---

## 三、模式B：基于外部查询值高亮（条码反查匹配）⭐

### 适用场景

用户在查询框输入一个值（如条码号），需在 Grid 中高亮**与该值匹配的行**。高亮依据不是行内某个固定字段的阈值，而是与一个**外部变量**（当前查询值）做比对。

典型案例：`SemiRubberConsumption.aspx`（回收胶出库）— 输入条码号反查，汇总表+两个明细表同时高亮匹配行。

### 与模式A 的关键区别

| 维度 | 模式A（过期预警） | 模式B（条码匹配） |
|------|-------------------|-------------------|
| 判断依据 | 行内字段值 vs 固定阈值 | 行内字段值 vs **外部变量**（当前查询值） |
| 触发时机 | 数据绑定时自动判断 | 查询时需**主动赋值**外部变量 |
| CSS 来源 | 复用 `extExtra.css` 全局类 | 通常需**页面级自定义 CSS** |
| 颜色冲突 | 一般无（红/黄醒目） | 需注意与**选中行颜色**区分 |

### 实现步骤

#### 1. 定义全局变量保存查询值 + 查询时赋值

```javascript
// 当前查询的条码号（GetRowClass 读取此变量）
var highlightBarcode = '';

var pnlListFresh = function () {
    highlightBarcode = App.txtBarcode.getValue();   // 查询前赋值
    App.direct.GetSummaryData(highlightBarcode, {   // 传给 DirectMethod
        success: function () { },
        eventMask: { showMask: true, target: 'customtarget', customTarget: 'pnlSummary' }
    });
}
```

> DirectMethod 重绑 Store 后，GetRowClass 会自动重新求值。

#### 2. setRowClass 函数 — 读取全局变量比对

**汇总表（条码列表字段，逗号分隔字符串 contains 判断）**：

```javascript
// 汇总行：Mixlot_Barcodes 或 Outlot_Barcodes（逗号分隔）包含查询条码 → 高亮
var setSummaryRowClass = function (record, rowIndex, rowParams, store) {
    if (highlightBarcode == null || highlightBarcode == '') return '';
    var mixCodes = record.get('Mixlot_Barcodes') || '';
    var outCodes = record.get('Outlot_Barcodes') || '';
    // 精确匹配（避免 R1 匹配到 R10）：两端补逗号后 indexOf
    if ((',' + mixCodes + ',').indexOf(',' + highlightBarcode + ',') >= 0
        || (',' + outCodes + ',').indexOf(',' + highlightBarcode + ',') >= 0) {
        return 'x-grid-row-highlight';
    }
    return '';
}
```

> **注意**：逗号分隔列表做 contains 判断时，必须在两端补逗号 `(',' + str + ',')` 再 indexOf，否则 `'R1,R10'` 会误匹配 `'R1'`。

**明细表（单值字段精确匹配）**：

```javascript
// 明细行：BARCODE 等于查询条码 → 高亮
var setDetailRowClass = function (record, rowIndex, rowParams, store) {
    if (highlightBarcode == null || highlightBarcode == '') return '';
    if (record.get('BARCODE') == highlightBarcode) return 'x-grid-row-highlight';
    return '';
}
```

#### 3. 页面级 CSS — 必须 cover hover/selected 状态 ⚠️

模式B 通常不能复用全局 CSS 类（颜色需自定义），且**必须覆盖 hover 和 selected 状态**，否则鼠标悬停/选中行时高亮背景会被默认样式冲掉：

```css
/* 基础高亮 */
.x-grid-row-highlight .x-grid-cell,
.x-grid-row-highlight .x-grid-cell-inner {
    background-color: #d4edda !important;       /* 浅绿 */
    background-image: none !important;
}
/* hover + selected 状态保持（不可省略！） */
.x-grid-row-over.x-grid-row-highlight .x-grid-cell,
.x-grid-row-selected.x-grid-row-highlight .x-grid-cell,
.x-grid-row-over.x-grid-row-highlight .x-grid-cell-inner,
.x-grid-row-selected.x-grid-row-highlight .x-grid-cell-inner {
    background-color: #d4edda !important;
    background-image: none !important;
}
```

> **模式A 为何不需要这层覆盖**：模式A 复用的 `bgcolor-danger`/`bgcolor-warning` 颜色饱和度高（红/黄），与选中行色差大；且部分场景不需要兼顾选中态。模式B 用浅色高亮，若不覆盖 selected 状态，点选高亮行后背景色会变回选中色，高亮"消失"。

### 踩坑：高亮色与选中行颜色撞色

**现象**：高亮色用浅黄 `#fff2cc`，选中行（`extExtra.css` 中 `.x-grid-item-selected`）也是浅黄 `#ffefbb`，两者几乎无法区分。

**排查**：先查选中行颜色：
```css
/* extExtra.css 第133行 */
.x-grid-item-selected { background-color: #ffefbb; }
```

**解决**：高亮色避开选中行色系。选中行是黄色系 → 高亮改用绿色系 `#d4edda`（浅绿），或蓝色系 `#cce5ff`（浅蓝）。

### 多表联动高亮

当汇总+多个明细表需同时高亮时，每个 GridPanel 各配一个 GetRowClass 函数（可共用全局变量）：

```xml
<!-- 汇总表 -->
<ext:GridView><GetRowClass Fn="setSummaryRowClass" /></ext:GridView>
<!-- 明细表1 -->
<ext:GridView><GetRowClass Fn="setMixDetailRowClass" /></ext:GridView>
<!-- 明细表2 -->
<ext:GridView><GetRowClass Fn="setOutDetailRowClass" /></ext:GridView>
```

明细数据通过 DirectMethod 异步加载，绑定后各表 GetRowClass 独立求值，无需额外协调。

### 模式B 参考实现

| 页面 | 高亮场景 |
|---|---|
| `Plugins/Semi/Report/SemiRubberConsumption.aspx` | 条码反查：汇总表（条码列表 contains）+ 两个明细表（精确匹配），浅绿 `#d4edda` |

---

## 四、通用踩坑记录

### 坑1：`setRowClass is not defined` — 函数位置错误

**现象**：把 `setRowClass` 放在外部 `*.js` 文件、用 `var fn = function(){}` 声明，页面加载报 `setRowClass is not defined`。

**原因**：Ext.Net 在 `ResourceManager` 构建阶段按**函数名查找**解析 `Fn="setRowClass"`，此时外部 JS 的全局 `var` 赋值可能尚未对其解析器可见。

**解决**：把 `setRowClass` 放在 `.aspx` 的内联 `<script>` 块（与 `pnlListFresh` 同位置）。

### 坑2：`Invalid component "id"` — 中文控件 ID

**现象**：新增控件用 `ID="CBB_过期"`，页面报 `Invalid component id`。

**原因**：Ext.Net 组件 `ID` 会生成客户端 JS 标识符 `App.CBB_过期`，而**中文字符不能作为合法 JS 标识符**。

**解决**：控件 ID 用 ASCII（如 `CBB_Expire`），显示文案走资源键。`FieldLabel`（显示）可中文，`ID`/`Name`（编程标识）必须 ASCII。

### 坑3：阈值/比对逻辑必须多处一致

模式A：`是否超期` 列（SQL CASE）、超期筛选框（SQL dynamic）、`setRowClass`（JS）三处阈值必须对齐。

模式B：查询框值（赋给全局变量）、DirectMethod 参数（传后端）、`setRowClass`（读全局变量比对）三处必须是同一个值。

### 坑4：SQL 别名跨页面不一致

`setRowClass` 里 `record.data['字段名']`、ModelField `Name`、Column `DataIndex` **三者必须与 SQL 别名完全一致**。列标题显示文案可用资源键（与别名无关）。

### 坑5：高亮色与选中行撞色

高亮色选择前先查 `extExtra.css` 中 `.x-grid-item-selected` 的颜色（`#ffefbb` 浅黄），避开同色系。详见模式B踩坑章节。

### 坑6：浅色高亮不覆盖 selected 状态 → 点选后高亮消失

模式B 用浅色高亮时，若只定义基础类不覆盖 `.x-grid-row-selected.xxx`，用户点选高亮行后背景会被选中色覆盖，高亮"消失"。必须写全 hover/selected 状态覆盖（见模式B第3步）。

---

## 五、改动 Checklist（复用模板）

### 模式A（过期预警）
- [ ] SQL Mapper：加/改 `是否超期` CASE（注意 UNION 各分支）
- [ ] .aspx Model：确认日期字段 ModelField 存在
- [ ] .aspx ColumnModel：确认日期列 DataIndex 与 SQL 别名一致
- [ ] .aspx GridPanel：加 `<View>` + `GetRowClass Fn="setRowClass"`
- [ ] .aspx 内联 `<script>`：定义 `setRowClass`（阈值与 SQL 一致）
- [ ] 控件 ID 用 ASCII
- [ ] （可选）TabChange 联动显示筛选框 + 自动刷新

### 模式B（条码匹配/外部查询值高亮）
- [ ] .aspx 查询区：加查询输入框（TextField + ENTER 监听）
- [ ] .aspx 内联 `<script>`：定义全局变量 `highlightValue` + 查询函数中赋值
- [ ] .aspx 内联 `<script>`：定义 `setRowClass`（读全局变量比对，逗号列表注意补逗号）
- [ ] .aspx GridPanel：加 `<View>` + `GetRowClass Fn="..."`
- [ ] .aspx `<style>`：定义高亮 CSS（**含 hover/selected 覆盖**）
- [ ] .aspx.cs DirectMethod：接收查询值参数传后端
- [ ] 颜色排查：确认高亮色与 `.x-grid-item-selected` 不撞色

## 六、关联文档

| 文档 | 内容 |
|------|------|
| `extnet-grid-complete-guide.md` | GridPanel 完整使用指南 |
| `semi-rubber-consumption-report.md` | 回收胶出库报表（模式B 完整案例） |
| `extExtra.css` | 全局 CSS（`bgcolor-warning`/`bgcolor-danger`/`.x-grid-item-selected`） |

---

## 七、模式C：基于行内数值越界高亮（标准值±公差）⭐

### 适用场景

检测/测量类报表：每行同时有 **标准值 + 公差 + 实际测量值**（常成组出现：重量/直径/周长等），实际值超出 `标准 ± 公差` 范围时整行标红预警。

典型案例：`Plugins/Semi/Report/BicMeasuredRecord.aspx`（BIC 检测记录，数据表 `Tb_BIC_MeasuredRecord`）。

### 与模式A/B 的区别

| 维度 | 模式A（过期预警） | 模式B（条码匹配） | 模式C（数值越界） |
|------|-------------------|-------------------|-------------------|
| 判断依据 | 日期字段 vs 阈值 | 行内值 vs 外部变量 | **多字段运算**：标准±公差 vs 实际值 |
| 字段数 | 1 个（日期） | 1 个（条码） | **3 个一组**（标准/公差/实际），可多组 |
| 关键陷阱 | 阈值多处对齐 | 逗号列表补逗号 | **必须 parseFloat + isNaN 容错** |

### 实现步骤

#### 1. 判定函数（parseFloat + isNaN 容错）

测量数据字段是字符串，直接比大小会变字符串比较出错；且常有空值/缺测，不判 isNaN 会误标红：

```javascript
// 实际值超出 标准 ± 公差 → true
var isOutOfRange = function (record, stand, tol, real) {
    var s = parseFloat(record.get(stand));
    var t = parseFloat(record.get(tol));
    var r = parseFloat(record.get(real));
    if (isNaN(s) || isNaN(t) || isNaN(r)) return false;   // 空值/非数字不标
    return (r < s - t) || (r > s + t);                     // 公差语义 = ± tolerance
}
```

#### 2. setRowClass — 多组任一越界即标红

```javascript
var setRowClass = function (record, rowIndex, rowParams, store) {
    try {
        if (isOutOfRange(record, "WeightStand", "WeightTolerance", "WeightReal")) return "x-grid-row-out-of-range";
        if (isOutOfRange(record, "DIAStand", "DIATolerance", "DIAReal")) return "x-grid-row-out-of-range";
        if (isOutOfRange(record, "BICStand", "BICTolerance", "BICReal")) return "x-grid-row-out-of-range";
    } catch (e) { }
    return "";
}
```

#### 3. 页面级 CSS（自定义类名 + hover/selected 覆盖）

```css
.x-grid-row-out-of-range .x-grid-cell,
.x-grid-row-out-of-range .x-grid-cell-inner {
    background-color: #ffcccc !important; background-image: none !important;
}
.x-grid-row-over.x-grid-row-out-of-range .x-grid-cell,
.x-grid-row-selected.x-grid-row-out-of-range .x-grid-cell,
.x-grid-row-over.x-grid-row-out-of-range .x-grid-cell-inner,
.x-grid-row-selected.x-grid-row-out-of-range .x-grid-cell-inner {
    background-color: #ffcccc !important; background-image: none !important;
}
```

> 用自定义类名（不复用 `extExtra.css` 的 `bgcolor-danger`，后者不覆盖 hover/selected）。

### 关键澄清：本场景是纯客户端，无 DirectMethod

本项目族（Semi/Quality/Curing）所有行高亮都是**纯客户端** `<GetRowClass Fn>` JS 函数读 Store 字段完成判定，**没有** `[DirectMethod] GetRowClass` 这种写法。

### 为什么不在 SQL 算越界标记

也可在 SQL 加派生列 `CASE WHEN ... THEN 'Y' END AS IS_OUT_OF_RANGE`，前端只读标记。但本场景选纯客户端，是为了**对用户提供的 SQL 做最小改动**（只参数化 WHERE，不加派生列）。两种方式取舍：

| 维度 | 纯客户端 JS（本模式） | SQL 派生列 |
|------|----------------------|-----------|
| 改 SQL | 不改 | 要加 CASE 列（需与用户确认） |
| 公差规则调整 | 改 JS 即时 | 改 SQL 需重编译 Mapper |

### 公差语义

本模式假设公差为 **±tolerance**（范围 = 标准 ± 公差）。若实际是上下限两列/比例/单边，改 `isOutOfRange` 比较式即可。

### 模式C 参考实现

| 页面 | 越界规则 |
|---|---|
| `Plugins/Semi/Report/BicMeasuredRecord.aspx` | 直径/周长 两组 各自 标准±公差，任一越界标红（重量不参与判定） |