---
status: active
updated: 2026-09-03
title: Ext.NET 自绘表格钉顶表头与合并格联动交互指南
category: 技术-.NET
module: Ext.NET
tags: [Ext.NET, sticky表头, 钉顶, border-collapse, 透字, 层间缝隙, 整数递推, background简写优先级, 十字定位, rowspan联动, data-pg组键, 悬停动画, 事件委托, 自绘表格, 还原xlsx, Chrome无头截图, 踩坑]
---

# Ext.NET 自绘表格钉顶表头与合并格联动交互指南

> 自绘 HTML 表格（还原 xlsx 原表版式）实现四层表头钉顶、行悬停动画、点击十字定位与 rowspan 合并格联动的完整套路；含三个渲染级深坑（sticky+collapse 不绘制、层间透字、background 简写优先级）的根因与修复。实证页：Molding/Report/MoldSchedulePlan.aspx（2026-09-03 交付，群模式三审+用户多轮实测）。

## 一、适用场景与总体架构

适用：Ext.NET GridPanel 做不了的版式——多层表头（rowspan/colspan）、机台块合并单元格、产品成对两行、横向 30+ 日列的自绘表格（还原 Excel 原表）。项目先例：点检纸表单还原页 + 本页（成型机生产日程计划）。

```text
Ext Panel(AutoScroll) > div.sched-box(overflow:auto + max-height) > table.sheet
层1 日期数字 th rowspan=4 左6列头 | 层2 星期 | 层3/4 操业时间
数据区：机台格 rowspan=产品数×2 + 属性格 rowspan=2 + 成对两行(模具面数/计划本数)
```

钉顶前提：**滚动容器必须是 .sched-box 自己**（不是 Ext Panel body）——中间隔了 overflow:auto 的元素会让 sticky 相对错误容器失效。给 .sched-box 设 `overflow:auto; max-height: calc(100vh - 170px)`。

## 二、钉顶坑一：border-collapse:collapse 下 sticky 单元格背景/边框不绘制

- 症状：钉住的表头**透出下方数据文字**（背景没画出来）。
- 根因：Chromium 对 collapsed 表格的 sticky 单元格背景/边框绘制有兼容缺陷（表头钉顶时背景丢失）。
- 修复：`border-collapse: separate; border-spacing: 0`，边框归单元格自绘（`border: 0 solid X; border-right-width:1px; border-bottom-width:1px`），表格补 `border-top/border-left` 外框。sticky 背景与边框即正常随钉。

```css
.sched-box table.sheet { border-collapse: separate; border-spacing: 0; border-top: 1px solid #b8b8b8; border-left: 1px solid #b8b8b8; }
.sched-box .sheet td, .sched-box .sheet th { border: 0 solid #b8b8b8; border-right-width: 1px; border-bottom-width: 1px; }
.sched-box .sheet th.schd, .sched-box .sheet td.schd { position: sticky; z-index: 2; }
```

注意 separate 模式下机台块 2px 分隔线：用单元格 `border-top/bottom: 2px solid` 自绘，相邻块交界处 1px+2px 叠出 3px 属可接受误差。

## 三、钉顶坑二：多行表头层间 0.4px 透明缝（小数行高透字）

- 症状：collapse 修复后，层与层之间（如星期行↔操业时间行）仍隐约透字。
- 根因：行实际高 20.6px（小数），sticky 偏移按取整的 offsetHeight 累加 → 层间留 0.4px 透明缝（实测 L2 底 41.6 / L3 顶 42.0）。
- 修复：**整数 top 递推**——`top[i+1] = Math.floor(top[i] + 行高小数)`，下一层顶必然 ≤ 本层底（每层向上叠压 0.6px，只叠不留缝）。勿用"累计行高各自取整"（floor(cum) 与前层底仍可能留缝）。

```js
var applyStickyHeader = function (box) {
    var rows = box.querySelector('table.sheet').rows;
    var top = 0;
    for (var r = 2; r <= 5 && r < rows.length; r++) {   // 行0=meta 行1=title 不钉
        var cells = rows[r].cells;
        for (var i = 0; i < cells.length; i++) {        // th 和 td 都要（操业时间空白格是 td！）
            cells[i].className += ' schd';
            cells[i].style.top = top + 'px';
        }
        top = Math.floor(top + rows[r].getBoundingClientRect().height);
    }
};
// 字体加载后行高会变：document.fonts.ready.then 重算（className 加类前先 indexOf 判重，幂等）
```

另两个细节：rowspan 跨层的左列头随首层 top:0 钉住天然盖住下方层；操业时间行的空白日格是 `td` 不是 `th`，遍历时别按 tagName 过滤（漏掉会整行散架）。

## 四、十字定位 + rowspan 合并格联动（组键方案）

构建期打组键：成对两行 `data-pg="机台#产品序"`、机台格 `data-mg="机台码"`、合计标签格 `class="sumlab"`。事件委托挂在容器 div 的 onclick/onmouseover/onmouseout。

**点击分流矩阵**（用户逐轮定稿的语义）：

| 点击对象 | 高亮范围 |
|---|---|
| 机台格（rowspan=块高） | 整个机台块全部行 `tr[data-pg^="机台#"]` + 机台格 |
| 属性格/合计标签（rowspan=2） | 成对两行 `tr[data-pg=组]`，**不带机台格**（机台格物理上属于首产品行的 cells，组标记须显式跳过 mach） |
| 日格/行标签（未合并） | 仅本行自有格，**跳过一切跨行合并格**（attr/mach/sumlab） |
| 合计行日格 | 仅本行，不带合计标签 |

**悬停联动**：划过任何数据行 → 成对两行 + 跨越的属性格 + 机台格一起亮（.hov 类 + box-shadow 半透明叠层 + .18s transition）。纯 CSS `tr:hover` 够不到别的行，必须 JS 组标记；跨两个表格容器时 hover 清理要清**全部容器**并给标记 key 带容器 id，防残留。

## 五、坑三：background 简写优先级抹掉叠层高亮（最隐蔽）

- 症状：十字高亮"只有日列格亮、中间 rowspan 合并格不亮"；实测合并格 **class 在、计算样式 background-image 却是 none**。
- 根因：`.attr/.mach/.rowlab/.sumrow` 等规则用 `background` 简写（隐含 `background-image:none`），specificity (0,3,1) 恰好高于叠层规则 `.x-cross-row` 的 (0,3,0)；日格基础底色规则只有 (0,2,1) 压不过，所以日格能亮。
- 修复：**叠层高亮规则加 `!important`**（页面内自闭 CSS 无外部冲突，可接受）：

```css
.sched-box .sheet .x-cross-row, .sched-box .sheet .x-cross-col
  { background-image: linear-gradient(rgba(244,196,20,.27), rgba(244,196,20,.27)) !important; }
.sched-box .sheet .x-cross-cell
  { background-image: linear-gradient(rgba(244,196,20,.45), rgba(244,196,20,.45)) !important; }
```

配色体系（ui-ux-pro-max 评审通过）：冷主题（青绿 #017F7E）+ 暖选择高亮（琥珀）是数据面板推荐组合；悬停用主题色 10% box-shadow（落在十字格上降到 6% 防发浊）；十字行/列 27%/单格 45% 两级明度差；正文 #222 全组合 WCAG AAA。

**双通道渲染原则**：十字用 background-image 叠层（保留任意底色、不与悬停 box-shadow 冲突），悬停用 box-shadow——两种效果同格叠加互不覆盖。

## 六、迭代期调试套路（版本对不上/缓存排查）

- 页面迭代期间给 `<title>` 加版本号 + 工具栏右端加 build 灰字标签，用户一眼对版本；交付前再删。
- Page_Load 加 `Response.Cache.SetCacheability(NoCache)+SetNoStore()+SetExpires(MinValue)` 禁缓存。
- 用户"效果没变"三步排查：强刷 Ctrl+F5 → 核对页内版本标记 → 核对地址栏是否目标站点（服务器旧部署没有新文件）。给用户带 `?v=N` 参数的链接强制绕缓存。
- **开着的旧页签永远跑旧 JS**（inline script 是加载那一刻的快照），多页签排查先关多余页签。
- 定位"类在但样式不对"用 `getComputedStyle` 直接量计算样式（比截图更硬）；DOM 标记数 + 计算样式 + 截图三重验证。
- 内置浏览器截图偶发超时/卡死（reload 后尤其），本地核验用 Chrome 无头更稳：`chrome --headless=new --screenshot=out.png --window-size=1900,900 --virtual-time-budget=6000 --user-data-dir=<项目内临时目录> URL`（Edge 无头在本机被企业策略拦截不可用）。
