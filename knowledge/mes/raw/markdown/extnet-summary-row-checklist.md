---
title: Ext.NET GridPanel 合计行实施清单
category: 技术-.NET
module: Ext.NET
tags: [Ext.NET, Summary, 合计行, 汇总行, SummaryType, SummaryRenderer, Dock, FilterHeader, 多语言合计标签, 分页合计口径, 导出不含合计, 前端求和, 停机持续时间]
updated: 2026-09-04
status: active
---

# Ext.NET GridPanel 合计行实施清单

> 给现有查询页补"合计行"的落地清单：四步标记写法 + 三大口径陷阱（分页页只合计当页、导出 Excel 不含合计、FilterHeader 过滤联动重算）+ 多语言合计标签的 asp:Literal 嵌法。基础写法见 `extnet-grid-complete-guide.md` 四章，浮点尾差专题见 `extnet-summary-row-decimal-precision.md`，本文不重复。

## 一、动手前先确认两件事

1. **列的数据类型必须是数值**：Summary 是前端把 store 里的值逐行相加，字符串列（如"1小时20分"）不能 Sum——先改 SQL 出数值列。实证：Equip 停机记录页 STOP_TIME 来自存储过程 `DATEDIFF(MINUTE, REPORT_DATETIME, COALESCE(RESTART_PRO_DATETIME, RESTART_EQU_DATETIME, GETDATE()))`，整数分钟，可直接 Sum。
2. **页面是否分页，决定合计口径**（见二章陷阱 1）。

## 二、三大口径陷阱（交付前必须向用户说明或规避）

1. **分页页面只合计当前页**：Summary 求和的是 store 当前数据。无分页全量加载页（DirectMethod 里 `Store.DataBind()` 一次性灌全部结果）→ 合计=整个查询结果 ✅；带 PagingToolbar 远程分页页（如 Equip 的 EquipEfficiencyAnalyse.aspx）→ 合计只覆盖当前页，需要全量合计时必须服务端算好回传，不能靠 Summary。
2. **导出 Excel 不含合计行**：项目导出惯例是从 Session 里的 DataTable 直接生成 Excel，与前端 Summary 无关。用户要"导出也带合计"时需另在导出 DataTable 末尾追加一行合计。
3. **FilterHeader 过滤联动重算**：列头过滤后 summary 随过滤后的可见数据重算（合理行为，但口径变了，交付时说明一句）。

## 三、标准四步写法（Equip Record/StopRecord.aspx 实证，2026-09）

### 第 1 步：GridPanel 挂 Summary Feature（Dock="Top" 顶部合计行）

```aspx
</ColumnModel>
<Features>
    <ext:Summary ID="Summary1" runat="server" Dock="Top" />
</Features>
<Plugins>
    <ext:FilterHeader runat="server" />
</Plugins>
```

### 第 2 步：数值列加 SummaryType="Sum" + 归整渲染

```aspx
<ext:Column runat="server" DataIndex="STOP_TIME" Text="<%$Resources:Equip,停机持续时间 %>" Width="100" SummaryType="Sum">
    <SummaryRenderer Fn="STOP_TIME_SummaryRenderer" />
</ext:Column>
```

```js
var STOP_TIME_SummaryRenderer = function (value) {
    //整数分钟场景 Math.round 归整；小数场景用 toFixed(2)，见 extnet-summary-row-decimal-precision.md
    if (value == null || value === '' || isNaN(value)) {
        return '';
    }
    return Math.round(value);
}
```

### 第 3 步：首列显示"合计"标签（无 SummaryType 的列返回常量即可）

```aspx
<ext:Column runat="server" DataIndex="EQUIP_CODE" Text="<%$Resources:Equip,机台编号 %>" Width="80">
    <SummaryRenderer Fn="summaryLabelRenderer" />
</ext:Column>
```

### 第 4 步：多语言合计标签——JS 里嵌 asp:Literal 取资源键

资源键"合计"在中越双语资源文件里都已存在（Equip.resx=合计 / Equip.vi.resx=Tổng hợp），不要硬编码中文：

```js
var summaryLabelRenderer = function () {
    return '<asp:Literal runat="server" Text="<%$Resources:Equip,合计 %>"/>';
}
```

该嵌法与页面既有 `var alt = '<asp:Literal .../>'` 同款，JS 全局函数放页面 script 块即可。

## 四、合计行样式

多数页面 head 里已内置官方示例模板的 summary CSS（加粗 15px、浅灰底、顶部停靠 2px 边框），挂上 Feature 即自动生效；页面没有时补这段：

```css
.x-grid-row-summary .x-grid-cell-inner {
    font-weight: bold;
    font-size: 15px;
    background-color: #f1f2f4;
}
.x-docked-summary.x-docked-summary-top {
    border-top-width: 2px !important;
}
```

## 五、代表页面

| 页面 | 特点 |
|------|------|
| `Equip/Record/StopRecord.aspx` | 无分页全量口径 + 多语言标签 + FilterHeader 共存（2026-09 新增实证） |
| `Semi/Material/SemisRawMaterial.aspx` | 指南基础示例页 |
| `Equip/Analyse/EquipEfficiencyAnalyse.aspx` | SummaryRenderer 首列硬编码'合计:'先例；CustomSummaryType 自定义加权合计（合格率/OEE 这类不能直接 Sum 的比率列）；注意带 PagingToolbar，受二章陷阱 1 约束 |
