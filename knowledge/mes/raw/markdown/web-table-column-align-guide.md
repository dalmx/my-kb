---
status: active
title: 自绘 HTML 表格跨表列对齐指南（auto 布局三坑与实测排障）
category: 技术-.NET
module: 通用
tags: [自绘表格, 列对齐, min-width, colspan分摊, width被压, box-sizing, offsetWidth, getBoundingClientRect, 表格收缩, CSS特异性, 边框隐藏, 占位格, 跨表, Chrome无头, 调试套路, 对齐]
updated: 2026-09-07
---

# 自绘 HTML 表格跨表列对齐指南（auto 布局三坑与实测排障）

> 同一容器里两张独立 `<table>` 要日列上下对齐（如主表 + 尾部小结块分成两张表、留间隔显示）时的完整套路。三坑全部来自 MoldSchedulePlan 模套块实机三轮闭环（2026-09-07），实测终版 diff=0。适用一切 `table-layout:auto + border-collapse:separate` 的自绘表格场景（Ext.NET 页面自绘表、纸表单还原表同理）。

## 一、结论速查

- 两表列对齐**唯一可靠做法**：B 表每行的每个格子逐格 `style.min-width = A 表对应列 getBoundingClientRect().width`（含小数），不能只对齐左区、不能信 `.day{width:34px}` 这类列宽下限在两表相等。
- 占位格要隐藏时**保留 DOM 只做视觉隐去**（transparent + 去边框），删格子=丢对齐。
- 验证只认数值（getBoundingClientRect 三点差值），视觉模型/肉眼截图判对齐不可靠。

## 二、三坑机理（auto 表格布局）

1. **`style.width` 只是提示值**：table-layout:auto 下表格会"收缩到容器宽"，指定的 cell width 会被压缩（实测设 534px 渲染成 54px）。**必须用 `min-width`（硬下限）**——主表既有列宽稳住正是因为其 CSS 用的是 `min-width`。
2. **colspan 大格的宽度被分摊**：跨列格上的 width/min-width 会被浏览器**分摊到所跨的虚拟列**（534px 摊到 6 列每列 ~89px 再被压掉），锁不住整块总宽。**左区必须拆成与主表列数相同的独立格子逐格对齐**。
3. **日列自身宽度两表不同 + offsetWidth 取整**：主表日列可能被宽内容撑大（如四位数值 1440 把 34px 下限撑到 ~38.4px），而 B 表内容窄、停在 34px——只对齐左区会右侧累计偏移（实测 30 列偏 ~40px）；且 `offsetWidth` 只返回整数，38.39px 取整成 38 每列丢 ~0.39px、30 列再累计 ~12px。**日列也逐列同步，且必须用 `getBoundingClientRect().width`（含小数）**。

## 三、终版实现要点

```text
结构：B 表每行 = [N 个占位格(与主表左列一一对应)] + [数据格] + [日格×n] + [尾注格]
CSS ：占位/数据格 box-sizing:border-box；min-width 由 JS 写入（.day 格不必 border-box，实测表格算法近似按列宽生效）
JS  ：alignTables()——找 A 表表头行（cells.length > 左列数 的首行），逐列取
      rect.width.toFixed(3)+'px' 写入 B 表各行同序格的 style.minWidth；
      innerHTML 后立即跑一次 + document.fonts.ready 后重跑一次（幂等）
交互：整列高亮等按列遍历的逻辑要改成遍历容器内全部 table（querySelectorAll），B 表同序日格一并标记
```

## 四、占位格隐去与表框自绘

- 用户不想要左侧空格子时：占位格 `background:transparent + border-right/bottom-width:0`，**保留 min-width 占位**；B 表去掉表级 `border-left/border-top`（否则空白区挂悬空线）；可见部分自绘边框——首行可见格补 `border-top`，首个可见格补 `border-left`，从该格起完整成框。
- **特异性坑**：行底色规则若写 `.a .sheet tr.covrow td`（3类2元素 (0,3,2)），普通 `.a .sheet td.covpad`（(0,3,1)）盖不住——隐藏规则必须带 `tr.covrow` 前缀升到 (0,4,2)；"写在后面就赢"只对同特异性成立。
- 导出 Excel 侧不用逐格：HTML 导入按列位置共享工作表列，B 表首部用 colspan=（左列数-1）+1 格即可与主表列位天然对齐。

## 五、数值排障套路（比截图可靠）

1. **Chrome 离线 mock**：从真实 aspx 抽取 `<style>`/`<script>` 块 + 模拟数据拼静态页，`chrome --headless --screenshot` 渲染；页内加 `#dbg` 调试条（position:fixed 红字）输出关键数值，OCR 读数定位。
2. **实机三点测量**：内置浏览器开受控页签 → 触发查询 → `getBoundingClientRect().left` 量两表同序日格差值，测**首/中/尾三点**（只测首列会漏"右侧累计漂移"——首列 0.39px 对齐、尾列偏 11.6px 的案例）。
3. **视觉模型复核仅作参考**：实测两轮误判——14px 间隔判成"无间隔"、末日无计划的留空数据格判成"缺列"。布局问题以 DOM 数值为准，视觉判断只用来发现"有没有明显异常"。
4. 主表/B 表宽度差（offsetWidth）是快速信号：两表同宽不代表对齐（尾注格会加宽），但差值大必有问题。

## 六、先例与关联

- 实证页：[molding-schedule-plan-report](molding-schedule-plan-report.md)（MoldSchedulePlan 模套块，2026-09-07，diff 首/中/尾全 0）。
- 同族自绘表格渲染坑（sticky 钉顶三坑/成对行联动）：[extnet-sticky-header-merged-table-guide](extnet-sticky-header-merged-table-guide.md)。
