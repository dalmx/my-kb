---
category: 技术-.NET
factory: 通用
module: Ext.NET
status: active
tags:
- Ext.NET
- 状态看板
- 机台布局
- 原生table
- rowspan
- 非对称rowspan
- 后端注入JS
- DOM刷色
- setProperty
- EXISTS
- ROW_NUMBER去重
- 原生悬浮框
- 智能定位
- 班次
- 当班口径
- 60秒刷新
- Molding
- 踩坑
- 复刻手册
title: Ext.NET 机台状态监控看板开发模式（原生 table 布局 + 后端注入 JS + 前端 DOM 刷色 + EXISTS 状态 SQL）
updated: '2026-09-18'
---

# Ext.NET 机台状态监控看板开发模式（原生 table 布局 + 后端注入 JS + 前端 DOM 刷色 + EXISTS 状态 SQL）

> 以「成型车间机台状态看板」（`MoldingMaterialStateBoard`）为案例，沉淀一种**与现有 KB 不同的看板变体**：只读状态监控看板（要料标黄/断档标红/无色），区别于 `extnet-tablelayout-cell-edit-pitfalls.md` 的「可编辑看板」和 `extnet-dataview-card-grid.md` 的「DataView+CSS Grid 看板」。
>
> 案例位置：`P.Molding/Wongoing.Molding.WebSite/Plugins/Molding/Report/MoldingMaterialStateBoard.aspx(.cs/.css)`
> 数据来源：`Wongoing.Molding.Mapper/BusinessMapper/SbeEquipState.xml`

## 一、什么时候用这个模式

- **只读**展示一批固定对象（机台/工位/库位）的实时状态，按状态染色（绿/黄/红/无色）
- 对象布局是**固定网格**（行列数已知，不随数据动态增减）
- 需要**定时刷新**（车间看板大屏、监控墙）
- 状态卡片可悬浮查看明细（物料/告警详情）
- **不需要**编辑单元格（区别于可编辑看板）

满足以上 → 用本模式。若对象数量/位置动态变化 → 用 DataView+CSS Grid 模式（`extnet-dataview-card-grid.md`）。若需要双击编辑单元格存库 → 用可编辑看板模式（`extnet-tablelayout-cell-edit-pitfalls.md`）。

## 二、核心架构（四文件分层）

```text
XxxStateBoard.aspx          ← Ext.NET Viewport(BorderLayout) + 原生 <table> 网格 + JS 刷色/悬浮/定时刷新
XxxStateBoard.aspx.cs       ← 后端：查状态/明细 → X.AddScript 注入 JS 变量 → 调前端刷色
XxxStateBoard.css           ← 卡片/网格/状态色/原生悬浮框样式
SbeEquipState.xml(Mapper)   ← EXISTS 状态判定 SQL + 明细查询 SQL
```

**数据流**（关键：后端不碰 DOM，只产数据；前端只拿数据刷 DOM）：

```text
后端 LoadAndApplyState()
  ├─ 查状态 SQL（每台机一行：EQUIP_CODE + WANT_FLAG + STOP_FLAG）
  ├─ 查明细 SQL（每笔明细一行）
  ├─ X.AddScript("_equipState = {机台:{stop,want}, ...};")      ← 注入状态
  ├─ X.AddScript("_materialDetail = {机台:[明细], ...};")        ← 注入明细
  └─ X.AddScript("setTimeout(applyBoardState, 100);")           ← 调前端刷色

前端 applyBoardState()  ← 每次 RefreshData 后调用
  ├─ 遍历 td[data-equip]
  ├─ 按 _equipState[code] 设背景色（setProperty('important')）
  ├─ 按 _materialDetail[code] 有无，绑/解绑悬浮框
  └─ 定时 setInterval(60s) → App.direct.RefreshData()
```

## 三、🔴 最大坑：Ext.NET TableLayout 处理非对称 rowspan 会错位

### 现象
布局是「**左列单行格 + 中间列跨多行格**」的非对称结构（如左列每段 2 台小机台 + 中间 7 列各 rowspan=3 的大机台）。用 `ext:TableLayout Columns="8"` + `RowSpan="3"`，页面渲染后**左列机台错位、整体不工整**——左列的 C6xx 被塞进中间 rowspan 跨越的行里。

### 根因
Ext.NET TableLayout 采用**流式填充算法**：按 `<Items>` 顺序逐个扫描，遇到 rowspan 占用的格子跳过。但**非对称 rowspan**（有的格 rowspan=1、有的 rowspan=3，且不在同一行起止）时，流式扫描的"跳过"逻辑算不准，导致后续单元格落位错乱。

### 解法：放弃 Ext.NET TableLayout，改用原生 HTML `<table>` 放进 `<Content>`
Ext.NET Panel 的 `<Content>` 会原样输出 HTML。原生 `<table>` 的 rowspan 由浏览器精确渲染（HTML 标准绝对可靠），非对称结构也能完美对齐。

```aspx
<ext:Panel ID="pnlCenter" runat="server" Region="Center" AutoScroll="true">
    <Content>
        <table class="msb-board">
            <%-- 每段3行：[左C6偶][中间7台各rowspan=3] / [左分隔空行] / [左C6奇] --%>
            <tr>
                <td class="equip-card equip-side" data-equip="C610">...C610...</td>
                <td class="equip-card" rowspan="3" data-equip="C507">...C507...</td>
                <td class="equip-card" rowspan="3" data-equip="C506">...C506...</td>
                ... 其他5台 rowspan=3 ...
            </tr>
            <tr><td class="equip-divider-inner"></td></tr>   <%-- 左列分隔空行，中间被rowspan占满 --%>
            <tr>
                <td class="equip-card equip-side" data-equip="C609">...C609...</td>
            </tr>
        </table>
    </Content>
</ext:Panel>
```

**为什么左列3行能精确等高于中间 rowspan=3？** 因为 `<tr><td></td></tr>`（分隔行）只有左列1个 td，中间7列的位置已被上一行 rowspan=3 占据，浏览器自动让左列3个 td 的高度之和 = rowspan 格的高度。这是 HTML 表格标准行为。

### 关键 CSS（让左列3行紧凑、与 rowspan 格协调）
```css
.msb-board {
    border-collapse: separate;     /* separate 才能让 td 圆角 + 间距生效 */
    border-spacing: 4px;
    table-layout: fixed;
}
.msb-board td.equip-card.equip-side {   /* 左列单行格：固定小高度 */
    height: 6.5vh; min-height: 46px;
}
.msb-board td.equip-card[rowspan="3"] { /* 中间大格：不设高度，由 rowspan 撑开 */
    height: auto;
}
.msb-board td.equip-divider-inner {     /* 分隔空行：极矮 */
    height: 4px;
}
```

### 对比：三种看板布局方案选型

| 方案 | 适用 | 坑 | 参考 KB |
|------|------|----|---------|
| **原生 `<table>` rowspan** | 固定网格 + 非对称 rowspan（本模式） | 无（浏览器标准渲染） | 本文 |
| Ext.NET `TableLayout` | 对称网格 / 单层行列合并 | **非对称 rowspan 错位** | `extnet-tablelayout-cell-edit-pitfalls.md` |
| DataView + CSS Grid | 对象数量/位置动态变化 | 选择器命不中、滚动失效、CSS缓存 | `extnet-dataview-card-grid.md` |

> 决策树：固定网格 → 原生 table（本模式）；动态对象 → DataView；可编辑 → TableLayout（但避开非对称 rowspan）。

## 四、状态染色：后端注入 JS 变量 + 前端 DOM 刷色

### 为什么不后端直接改 CellCls？
KB `extnet-tablelayout-cell-edit-pitfalls.md` 坑4/5 已证：后端运行时改 `CellCls` 属性，在 **DirectMethod Ajax 回发**（定时刷新场景）时**不可靠**——属性改了但 DOM 不更新。本模式用原生 table 没有 Ext.NET 控件树，更没有 CellCls 可言。

### 正解：后端只产数据，前端遍历 DOM 刷色
```javascript
function applyBoardState() {
    var YELLOW = '#FFE082', RED = '#F5B7B1', NORMAL = '#ffffff';
    var cards = document.querySelectorAll('.msb-board td.equip-card[data-equip]');
    for (var i = 0; i < cards.length; i++) {
        var td = cards[i];
        var code = td.getAttribute('data-equip');
        var st = _equipState[code];
        var color = NORMAL, stateCls = '';
        if (st) {
            if (st.stop === 1) { color = RED; stateCls = 'material-stop'; }      // 断档优先
            else if (st.want === 1) { color = YELLOW; stateCls = 'want-material'; }
        }
        // 关键：用 setProperty('important')，否则被 CSS !important 覆盖
        td.style.setProperty('background-color', color, 'important');
        td.classList.remove('want-material', 'material-stop');
        if (stateCls) { td.classList.add(stateCls); }
        // ... 悬浮绑定见第五节
    }
}
```

**两个必须点**：
1. **`setProperty('background-color', color, 'important')`**——CSS 优先级链里 `CSS !important > JS 普通 inline`，必须 JS 也带 `!important` 才能覆盖 CSS 兜底色（KB `extnet-tablelayout-cell-edit-pitfalls.md` 坑4）。
2. **状态 class（want-material/material-stop）加在 td 上**——文字色、角标、动效靠 CSS 选择器 `td.equip-card.want-material` 命中，背景色交给 JS 设。

### 后端注入 JS 变量（C# 5，无 `$""`）
```csharp
// 序列化 DataTable → JS 对象字面量
string jsState = BuildEquipStateJs(dtState);     // { 'C507':{stop:1,want:0}, ... }
X.AddScript("_equipState = " + jsState + ";");
X.AddScript("_materialDetail = " + jsDetail + ";");
// 调前端刷色（setTimeout 等 Ext.NET 容器布局完成）
X.AddScript("setTimeout(function(){ applyBoardState(); }, 100);");
```

> 注意：qty 数值用裸数字（`qty:50` 不加引号），name/time 用字符串。转义 `\` `'` `"`。

## 五、原生悬浮框（明细展示）

### 不用 Ext.ToolTip（KB `extnet-tablelayout-cell-edit-pitfalls.md` 坑24 已证不可靠）
Ext.ToolTip 在动态多行内容场景有 `white-space:nowrap` 截断、`maxWidth` 不生效的坑。复杂悬浮框用原生 DOM。

### 悬浮框实现要点
1. **300ms 延时关闭 + mouseenter 取消**——防鼠标稍移就触发 mouseout 瞬间消失（KB 坑24）
2. **`pointer-events:auto`**——悬浮框挂 `document.body`（顶层，不被看板容器 overflow 裁切）
3. **智能定位（关键，防底部裁切）**：先 `visibility:hidden` 测尺寸，再判断上下空间翻转、左右收边

```javascript
function _showTip(equipCode) {
    var detail = _materialDetail[equipCode];
    if (!detail || detail.length === 0) { return; }
    var box = _ensureTipBox();
    box.innerHTML = '...明细表格...';
    var node = document.querySelector("td.equip-card[data-equip='" + equipCode + "']");
    var rect = node.getBoundingClientRect();
    // 临时隐藏测尺寸
    box.style.visibility = 'hidden'; box.style.top = '0px'; box.style.left = '0px';
    box.classList.add('show');
    var bw = box.offsetWidth, bh = box.offsetHeight;
    // 上下翻转：下方空间不够则翻上方
    var spaceBelow = vh - rect.bottom;
    var top = (spaceBelow >= bh + 6 || spaceBelow >= rect.top)
              ? rect.bottom + 6            // 放下方
              : rect.top - bh - 6;         // 翻上方
    if (top + bh > vh - 4) top = vh - bh - 4;   // 兜底贴边
    if (top < 0) top = 4;
    // 左右收边
    var left = rect.left;
    if (left + bw > vw - 4) left = vw - bw - 4;
    if (left < 4) left = 4;
    box.style.top = (top + sy) + 'px'; box.style.left = (left + sx) + 'px';
    box.style.visibility = '';
}
```

### 内容限高滚动（明细条目多时）
```css
.mater-tooltip { max-height: 60vh; overflow-y: auto; }
```

### 绑定条件：有明细就绑（不限状态）
断档机台同时有要料明细时也要能悬浮。判定依据是「`_materialDetail[code]` 有数据」，不是「状态是 want-material」：
```javascript
var hasDetail = _materialDetail[code] && _materialDetail[code].length > 0;
if (hasDetail) { /* 绑 mouseenter/mouseleave */ }
```

## 六、状态判定 SQL（EXISTS 半连接 + ROW_NUMBER 去重）

**要料取值口径（2026-09-09 起）**：`BPM_STORAGE_OUT_LIST` 中 `DEST_STORAGE=机台号`、`STATUS=3`（手持端字典：3=未出库、4=在途）、`RECORD_TIME ∈ [当前班次开始, 现在)` 的记录；同机台同物料编码取最新一条（ROW_NUMBER rn=1）。

### 状态 SQL：每台机一行，用 EXISTS 判定（避免 JOIN 产生重复行）
```sql
SELECT
    e.EQUIP_CODE,
    CASE WHEN EXISTS(
        SELECT 1 FROM BPM_STORAGE_OUT_LIST s WITH(NOLOCK)
        WHERE s.DEST_STORAGE = e.EQUIP_CODE
          AND s.STATUS = 3              -- int 类型，字面量不加引号（防隐式转换）；3=未出库
          AND s.RECORD_TIME >= #MATERIAL_BEGIN#   -- 当前班次开始（.cs 算好传入）
          AND s.RECORD_TIME < #NOW#     -- 时间字段裸用（SARGable），开区间
    ) THEN 1 ELSE 0 END AS WANT_MATERIAL,
    CASE WHEN EXISTS(
        SELECT 1 FROM SBE_EQUIP_STOP_RECORD r WITH(NOLOCK)
        WHERE r.EQUIP_CODE = e.EQUIP_CODE
          AND r.STOP_REASON_ID = 'ESCX08'   -- varchar，加引号
          AND r.RESTART_PRO_DATETIME IS NULL
          AND r.REPORT_DATETIME >= #STOP_BEGIN#   -- 当前班次开始
          AND r.REPORT_DATETIME < #NOW#
    ) THEN 1 ELSE 0 END AS MATERIAL_STOP
FROM SBE_EQUIP e WITH(NOLOCK)
WHERE e.MAJOR_TYPE_ID = '04' AND e.DELETE_FLAG = 0
```

**要点**：
- 用 `EXISTS`（半连接，找到即停）而非 JOIN——避免一台机多条记录导致状态行重复
- 主表 `SBE_EQUIP` 按 `MAJOR_TYPE_ID`+`DELETE_FLAG` 收窄到目标机台
- 时间参数由 .cs 算好传入（不在 SQL 里套 `GETDATE()`，便于扩展班次表）
- `WITH(NOLOCK)` 降锁（看板可接受脏读）

### 明细 SQL：相同物料取最新一条（ROW_NUMBER 去重）
```sql
SELECT t.EQUIP_CODE, t.MATER_NAME, t.MATER_CODE, t.QTY, t.RECORD_TIME
FROM (
    SELECT s.DEST_STORAGE AS EQUIP_CODE, s.MATER_NAME, s.MATER_CODE, s.QTY, s.RECORD_TIME,
        ROW_NUMBER() OVER(
            PARTITION BY s.DEST_STORAGE, s.MATER_CODE   -- 按机台+物料编码分组
            ORDER BY s.RECORD_TIME DESC                 -- 组内时间倒序
        ) AS rn
    FROM BPM_STORAGE_OUT_LIST s WITH(NOLOCK)
    WHERE s.STATUS = 3 AND s.RECORD_TIME >= #MATERIAL_BEGIN# AND s.RECORD_TIME < #NOW#
) t
WHERE t.rn = 1
ORDER BY t.EQUIP_CODE, t.RECORD_TIME DESC
```

> 注意：去重按 `MATER_CODE`（物料编码）而非 `MATER_NAME`（物料名），避免"同名异物"误合并。

### iBATIS 注意
- WHERE 条件全固定（班次时间始终传值）→ **不用 `<dynamic>`**，无 `AND AND`/缺 AND 风险
- 含 `<` 的 SQL（开区间上界 `RECORD_TIME < #NOW#`）必须包 `<![CDATA[ ]]>`

## 七、班次时间计算（C# 端）

白班 8:00-20:00 / 夜班 20:00-次日8:00。**2026-09-09 口径变更：要料窗口由「上个班次开始→现在」收紧为「当前班次开始→现在」**（用户要求只查当班），状态与明细两条 SQL 的 `MATERIAL_BEGIN` 都传当前班次开始，`GetLastShiftStart` 已从页面删除。班次切换瞬间（8:00/20:00 整点）跨班旧要料自动清空，属预期行为。
```csharp
private static DateTime GetCurrentShiftStart(DateTime now) {
    DateTime today8 = new DateTime(now.Year, now.Month, now.Day, 8, 0, 0);
    DateTime today20 = new DateTime(now.Year, now.Month, now.Day, 20, 0, 0);
    if (now >= today8 && now < today20) return today8;        // 白班
    else if (now >= today20) return today20;                   // 夜班（今天20点）
    else return today20.AddDays(-1);                           // 凌晨<8点，昨晚夜班
}
// 若业务再需要"上个班次"口径：GetCurrentShiftStart(now).AddHours(-12)
```
> 若班次规则复杂（多段/跨天），改查班次表，不在 C# 硬编码。

## 八、定时刷新（60秒）

前端 `Ext.onReady` 里 `setInterval`，调 `[DirectMethod] RefreshData`：
```javascript
Ext.onReady(function () {
    setTimeout(function(){ applyBoardState(); }, 300);   // 首次刷色（延迟等渲染）
    setInterval(function () {
        try { App.direct.RefreshData({ success: function () {} }); } catch (e) {}
    }, 60000);                                            // 60秒自动刷新
});
```
后端 `RefreshData` 重跑 `LoadAndApplyState()`（查数据 + 注入 JS + 调 applyBoardState）。

## 九、角标用 Font Awesome（不用 Unicode 符号）

CSS `::after` 用 Unicode 符号（`\2139` ⓘ / `\26A0` ⚠）在不同字体下可能渲染成方框/模糊。项目已引 Font Awesome（FA4，`fa fa-xxx` 语法），用 FA 的 unicode + `font-family: FontAwesome` 矢量清晰：
```css
.msb-board td.equip-card.want-material .card-equip::after {
    content: '\f05a';              /* FA4 info-circle */
    font-family: FontAwesome;
    font-size: 15px;
    color: #f39c12;                /* 饱和色，与浅底强对比 */
    opacity: 1;                    /* 不透明 */
}
.msb-board td.equip-card.material-stop .card-equip::after {
    content: '\f071';              /* FA4 exclamation-triangle */
    font-family: FontAwesome;
    color: #c0392b;
}
```
> FA4 常用 unicode：info-circle `\f05a`、exclamation-triangle `\f071`、check `\f00c`、times `\f00d`、arrow-down `\f063`、ban `\f05e`。

## 十、完整踩坑速查（本模式新增）

| # | 现象 | 根因 | 解法 |
|---|------|------|------|
| 1 | TableLayout 非对称 rowspan 错位、不工整 | Ext.NET 流式填充算法算不准非对称 rowspan 的跳过 | 改原生 HTML `<table>` 放进 `<Content>` |
| 2 | DirectMethod 改 CellCls DOM 不更新 | Ajax 回发时控件属性不重渲染（KB 坑4/5） | 后端只注入 JS 变量，前端 `setProperty('important')` 刷色 |
| 3 | JS 设背景色没效果 | CSS `!important` 覆盖 JS 普通 inline | JS 用 `setProperty('bg', color, 'important')` |
| 4 | 底部卡片悬浮框被裁切 | 固定放下方，超视口底 | 智能定位：测尺寸 + 上下翻转 + 左右收边 + 贴边兜底 |
| 5 | 明细条目多悬浮框超高 | 无高度限制 | `max-height:60vh; overflow-y:auto` |
| 6 | 同一机台同一物料明细重复 | 多次要料都查出 | `ROW_NUMBER() PARTITION BY 机台,物料编码 ORDER BY 时间 DESC` 取 rn=1 |
| 7 | 角标 ⓘ/⚠ 不清楚 | Unicode 符号字体回退 + opacity 淡 + 字号小 | 改 Font Awesome unicode + `font-family:FontAwesome` + 饱和色 + opacity:1 |
| 8 | 卡片一页装不下 | 每格固定大高度 × 行数超 100vh | 左列单行格用 `vh` 小高度，rowspan 格 `height:auto` 由 rowspan 撑开 |
| 9 | STATUS 字段过滤失效/慢 | 字面量引号与列类型不符（隐式转换） | 先 grep 实体确认列类型，int 不加引号、varchar 加引号 |
| 10 | 断档机台看不到要料明细 | 悬浮只绑 want-material 状态 | 改「有 `_materialDetail[code]` 数据就绑」，不限状态 |

## 十一、关键边界与决策

| 决策点 | 本模式选择 | 原因 |
|--------|-----------|------|
| 布局容器 | 原生 `<table>` 放 `<Content>` | 非对称 rowspan 必须浏览器渲染 |
| 机台号 | 硬编码到 aspx（ID=card_Cxxx, data-equip=Cxxx） | 固定网格，性能最好，运行时只染色 |
| 染色主体 | 前端 JS | 后端 CellCls 在 Ajax 回发不可靠 |
| 明细去重 | SQL 层 ROW_NUMBER | 比后端/前端去重更早、更干净 |
| 要料时间窗口 | 当前班次开始→现在（2026-09-09 起） | 只看当班；旧口径为上个班次开始→现在 |
| 班次计算 | C# 端 | 便于未来扩展班次表，SQL 保持纯查询 |
| 悬浮框 | 原生 DOM（非 Ext.ToolTip） | KB 坑24 验证 Ext.ToolTip 不可靠 |
| 断档 vs 要料都命中 | 显示红色（断档优先） | 断档更严重；但若有要料明细仍可悬浮查看 |

## 十二、关联

- 可编辑看板（TableLayout + DirectMethod 存库）：`extnet-tablelayout-cell-edit-pitfalls.md`（坑4/5/7/24 本文复用）
- DataView + CSS Grid 看板（动态对象）：`extnet-dataview-card-grid.md`
- DirectMethod 数据访问：`extnet-directmethod-and-data.md`
- 班次/班组在 MES 库（Mix 项目）：`mix-project-dev-conventions.md`
- SQL 优化原则：`sql-server-performance-troubleshooting.md`
- iBATIS dynamic prepend 规则：`ibatis-dynamic-prepend-rules.md`
- iBATIS `#` vs `$`、命名空间冲突：`report-common-pitfalls.md`

## 十三、2026-09-17 增补：明细行"停机已结束"不再标红

> 需求：悬浮框要料明细中，关联停机已恢复（`RESTART_PRO_DATETIME` 有值）的行不再整行标红。本节口径与第六节明细 SQL 增量冲突时**以本节为准**。

### 改动点（三处，前端 JS 零改动）
1. **SQL**（`GetMoldingWantMaterialDetail@SbeEquipState`）外层 SELECT 增加一列：
```sql
-- 停机是否已结束：1=已恢复（RESTART_PRO_DATETIME 有值），前端据此不再标红
CASE WHEN esr.RESTART_PRO_DATETIME IS NULL THEN 0 ELSE 1 END AS STOP_ENDED
```
2. **.cs**（`BuildMaterialDetailJs`）`isKey` 判定改为：`EQUIP_STOP_RECORD_ID` 有值 **且** `STOP_ENDED=0` 才 `key:1`；停机已结束 → `key=0`，前端渲染为普通行（不标红、也不显示停机详情块）。
3. **.aspx** 仅注释同步，`_showTip` 的 `it.key === 1` 逻辑不动。

### 口径对齐
- 状态 SQL（`GetMoldingEquipState`）断档标红本就要求 `RESTART_PRO_DATETIME IS NULL`（停机中）；本次让**明细行标红与卡片标红同口径**——红色只表示"停机进行中"。
- 边界：`EQUIP_STOP_RECORD_ID` 有值但对应 `SBE_EQUIP_STOP_RECORD` 行被物理删除（LEFT JOIN 不中）时 `STOP_ENDED` 为 NULL → 按 0（未结束）处理，保持标红，宁可多警不漏警。
- `STOP_DURATION_MIN` 对已结束停机返回最终时长（`DATEDIFF(REPORT_DATETIME, RESTART_PRO_DATETIME)`），但该行已不再显示详情块，此列仅作数据保留。

### 部署
- xml 是 EmbeddedResource → **须重编 Mapper dll**（Release）拷 WebSite Bin，ASP.NET 检测 Bin 变更自动回收；`.aspx`/`.aspx.cs` 同步拷服务器（动态编译免重编）。
- 三件（dll + aspx + aspx.cs）须一起上：只上新 aspx.cs 不上 dll → `row["STOP_ENDED"]` 列不存在，页面抛"列不属于表"异常。无 DB 变更、无 UPGRADE SQL。

## 十四、2026-09-18 增补：要料明细缺料检查（产出库/线边库均无 → 整行红色闪烁）

> 需求：检查要料单的料在部材产出库和线边库有没有，没有的明细行红色闪烁。库存口径参考页 `Plugins/Molding/Produce/MoldExistSemiRealTimeStock.aspx`（成型机台半制品即时存量）。

### 库存口径实证（两处项目既有定义拼合）
1. **参考页 proc**（`SQL/PROC_GetMoldSemiRealTimeInventory.sql`，即 `GetMoldSemiRealTimeInventory@BpmMoldingRawStock` 调的）：线边库/机台即时存量 = `BPM_MOLDING_RAW_STOCK` + `HPP_SEMIS_PRODUCTION`(CARD_NO=Barcode) + `BPM_STORE_LOCATION/AREA`，条件 `HOUSE_CODE='3'`、`LEFT_QTY>5`（proc 写 `TRY_CAST(...AS DECIMAL(18,2))>5`，台账 LEFT_QTY=numeric(10,3) 本可直接比）、`STATE_FLAG IN (0,2,4)`。
2. **`GetMoldingStockWarning@BpmMoldingRawStock`（成型预警库存）的 t2"现有库存"** = `HPP_STORAGE`（StockPlaceID→`HPP_SM_LOCATION`→`HPP_SM_AREA`）在 `C%`(部材产出库) 或 `X-%`(线边库) 库区，`LEFT_QTY>5`、`QUALITY_SITUATION<>'错打'` ∪ 上述 raw stock 池。

### 实现（GetMoldingWantMaterialDetail 增列 STOCK_OK）
```sql
CASE WHEN EXISTS(  -- 产出库 C% + 线边库 X-%（HPP_STORAGE 链）
    SELECT 1 FROM HPP_STORAGE hs ... INNER JOIN HPP_SEMIS_PRODUCTION sp ON sp.CARD_NO = hs.Barcode
    WHERE sp.MATERIAL_ID = t.MATER_CODE AND (AREA_CODE LIKE 'C%' OR LIKE 'X-%')
      AND sp.LEFT_QTY > 5 AND sp.QUALITY_SITUATION <> '错打'
) OR EXISTS(       -- 成型机台即时存量（BPM_MOLDING_RAW_STOCK 链，参考页口径）
    SELECT 1 FROM BPM_MOLDING_RAW_STOCK rs ... WHERE rs.MaterialCode = t.MATER_CODE
      AND ba.HOUSE_CODE = '3' AND sp2.LEFT_QTY > 5 AND rs.STATE_FLAG IN (0,2,4)
) THEN 1 ELSE 0 END AS STOCK_OK
```
- `.cs`：`BuildMaterialDetailJs` 序列化 `stock:0/1`；`stock=0` = 各库均无有效库存。
- 前端：`it.stock === 0` → 行加 `mater-lack` 类 + "缺料"红底白字徽标；CSS `@keyframes msb-row-blink 1s step-end infinite` 红白硬闪（版本号 l→m 破缓存）。
- **与 mater-key 的冲突规则**：行同时停机中(mater-key) 且缺料(mater-lack) 时，mater-key 的 `!important` 静态红底**优先于 animation**（CSS 级联：animation origin 低于 author !important）→ 不闪但红底，缺料徽标仍显示。若要求"缺料闪烁压过停机红"，需去掉 mater-key td 背景的 !important 或给 blink 关键帧也上 important 场景（未做，待用户反馈）。
- 关联键域：`HPP_SEMIS_PRODUCTION.MATERIAL_ID`(varchar20) ≡ `BPM_STORAGE_OUT_LIST.MATER_CODE` ≡ `BPM_MOLDING_RAW_STOCK.MaterialCode`(varchar50)，与 GetMoldingStockWarning 的 `t2.MATERIAL_ID = t1.MATERIAL_CODE` 同域，无隐式转换。

### 部署
重编 Mapper dll（Release→Bin）+ `MoldingMaterialStateBoard.aspx/.aspx.cs/.css` 四件一起上服务器；无 DB 变更。EXISTS 关联子查询仅对当班 rn=1 明细行（几十行）执行，负载与 GetMoldingStockWarning 同量级。

## 十五、2026-09-18 增补 v3：安全库存验证三态化（STOCK_LEVEL）+ 安全库存维护页

> 需求：新建安全库存维护页面（可导出导入）+ 看板安全库存验证——低于安全库存黄色闪烁。本节与第十四节增量冲突时以本节为准（STOCK_OK 列已删除，改为 STOCK_LEVEL）。

### 口径终态（三态）
`GetMoldingWantMaterialDetail` 外层 LEFT JOIN 两张：
1. **stk**（三池有效库存合计子查询，同十四节的池定义：产出库 C%∪线边库 X-% 走 HPP_STORAGE 链 + 成型机台即时存量走 BPM_MOLDING_RAW_STOCK/HOUSE_CODE='3' 链；LEFT_QTY>5、非错打、STATE_FLAG IN(0,2,4)）
2. **ss** = `BPM_MOLDING_SAFE_STOCK`（物料级安全库存维护表，`DELETE_FLAG=0`）

```sql
ISNULL(stk.STOCK_QTY, 0) AS STOCK_QTY, ss.SAFE_QTY AS SAFE_QTY,
CASE WHEN ISNULL(stk.STOCK_QTY, 0) <= 0 THEN 0                       -- 无库存→红闪
     WHEN ss.SAFE_QTY IS NOT NULL AND ISNULL(stk.STOCK_QTY,0) < ss.SAFE_QTY THEN 1  -- 低于安全→黄闪
     ELSE 2 END AS STOCK_LEVEL                                        -- 正常/未维护→不闪
```
- `.cs` 序列化 `level/stockQty/safeQty`（替代 stock）；前端 level=0→`mater-lack` 红闪+"缺料"徽标，level=1→`mater-low` 黄闪+琥珀徽标带"低于安全库存(现X/安Y)"，level=2 不闪。CSS 版本 m→n。
- 维护页 Grid 的状态列同 SQL 同口径（Select@BpmMoldingSafeStock 复用同一 stk 子查询），一处定义两处消费。

### 新表 BPM_MOLDING_SAFE_STOCK（DDL：SQL/TABLE_BPM_MOLDING_SAFE_STOCK.sql，用户执行）
OBJID identity PK / MATERIAL_CODE varchar(50) / SAFE_QTY decimal(18,3) / REMARK nvarchar(200) / RECORD_USER_ID varchar(50) / RECORD_TIME / DELETE_FLAG int 0,1 / FACTORY_ID / ROW_VERSION；过滤唯一索引 UX_..._MATERIAL_CODE WHERE DELETE_FLAG=0。**维度=物料级一条**，比较对象=三池合计。

### 维护页（SpliceParamLimit 第三次克隆：Semi CPK→Mix SPC→本次）
`Plugins/Molding/Storage/MoldSafeStock.aspx(.cs)`，PageAction 查询1/新增2/编辑3(Edit)/删除4(Delete)/导出5/导入6。全链新文件：Entity/BasicMapper/BusinessMapper/Data/Business 各一对（csproj 已注册，Manager/Service 零业务方法走 BaseManager）。BusinessMapper 两条：`Select@BpmMoldingSafeStock`（join 物料名/细类/记录人+stk 子查询+STOCK_LEVEL；条件=细类精确+物料编码/名称模糊）、`DeleteBpmMoldingSafeStockByObjIds`（iterate 批删）。
- 编辑窗：物料编码（编辑只读，后端校验存在于 SBM_MATERIAL+唯一性预检）+ 安全库存 NumberField>0 + 备注；保存先删后插。
- 导入：模板列 `物料编码*/安全库存*`（+物料名称/细类/备注/当前有效库存/状态 显示列，导入忽略）；按物料编码 upsert（先删后插批500+BatchInsert 失败逐行重试）；行级校验=编码不在 SBM_MATERIAL 报行号错。
- 导出：隐藏 asp:Button 完整回发，Session["MoldSafeStockQuery"] 复用最近查询条件，ExcelDownload。
- 细类下拉=SbmMaterialMinorTypeManager(MajorTypeId='01')，与参考页 MoldExistSemiRealTimeStock 同源（Main.Business 引用）。

### 部署（比十四节多的部分）
四层 dll（Entity/Data/Business/Mapper 重编）+ MoldSafeStock.aspx/.cs + 看板三件 + **先执行建表 SQL**（无表时页面查询/看板明细 SQL 直接报错——LEFT JOIN 的表不存在）。

## 十六、2026-09-18 性能收窄：三池库存聚合加 IN 半连接（两条语句）

> 用户要求"优化查询语句"。对照 sql-server-performance-troubleshooting.md 原则①缩小范围：原实现的三池库存聚合对**全量物料**做 SUM 再 LEFT JOIN 到小驱动表，改为先按驱动域收窄。

- `GetMoldingWantMaterialDetail@SbeEquipState`（看板明细，60s 刷新）：两个池各加 `AND MATERIAL IN (SELECT MATER_CODE FROM BPM_STORAGE_OUT_LIST WHERE STATUS=3 AND RECORD_TIME ∈ 当班窗口)` —— 与内层明细子查询 t 完全同谓词，结果集不变，聚合范围从全量物料降到当班要料物料（通常几十个）。
- `Select@BpmMoldingSafeStock`（维护页列表）：两个池各加 `AND MATERIAL IN (SELECT MATERIAL_CODE FROM BPM_MOLDING_SAFE_STOCK WHERE DELETE_FLAG=0)` —— 驱动表本身就这么大，聚合范围随之收窄。
- 语义不变性：LEFT JOIN 语义下，stk 只可能被驱动表的物料引用；IN 集合 ⊇ 驱动表物料集合（同谓词/超集），故每行 join 结果与收窄前完全一致；无库存物料仍走 ISNULL(stk.STOCK_QTY,0)=0 分支。
- 其余原则复核：两语句列清单明确无 `SELECT *`；时间字段裸用 SARGable；库区 `LIKE 'C%' OR LIKE 'X-%'` 同列前缀 OR 可走索引;全链 varchar=varchar 无隐式转换（台账核对）；NOLOCK 与既有口径一致。未加 OPTION(RECOMPILE)（参数为简单区间，嗅探风险低，无证据不加）。
- 部署：仅 Mapper dll 变更（Release 已重编拷 WebSite Bin，grep 验证四处收窄注释已嵌入）。