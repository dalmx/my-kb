---
title: Ext.NET GridPanel 汇总行(Summary)小数精度问题
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, Summary, SummaryType, SummaryRenderer, 浮点精度, 汇总行, toFixed, 前端累加]
status: active
updated: 2026-08-29
---
# Ext.NET GridPanel 汇总行(Summary)小数精度问题

> SummaryType="Sum" 后汇总行出现一长串小数（如 123.55000000000001）是前端 ExtJS 按 IEEE 754 逐行累加的浮点误差，不是 SQL SUM 或数据脏的问题——别去改存储过程。解法：给列加 <SummaryRenderer> 对合计值 toFixed(2)（只作用于汇总行，与明细行 Renderer 互不影响）；判定表区分前端误差（仅汇总行超长）与 SQL 层问题（明细也超长用 ROUND）。

## 一、问题现象

GridPanel 列设置 `SummaryType="Sum"` 后,页面底部汇总行出现一长串小数,例如：

```text
总量: 123.55000000000001
```

而明细行每条数据本身是正常的（如 `12.3`、`0.1`）。

## 二、根因（关键认知）

**这是前端浮点累加问题,不是 SQL / 数据库问题。**

Ext.NET 的 Summary feature 工作机制：**在浏览器端用 JavaScript 把当前页每行的数值逐个相加**,计算合计。JavaScript 浮点数遵循 IEEE 754,十进制小数无法精确表示,累加时误差逐步放大：

```js
0.1 + 0.2        // 0.30000000000000004
12.3 + 0.1 + ...  // 多次累加后位数更长
```

所以：
- ❌ 不要去改 SQL 的 `SUM()` 或存储过程——服务端 `SUM` 通常正常（数值类型精度足够）。
- ❌ 不要怀疑数据脏——明细行数据是对的。
- ✅ 汇总行是前端 Ext.NET/ExtJS 单独算的,精度误差出在这里。

## 三、修复方案：SummaryRenderer + toFixed

给需要格式化的列加 `<SummaryRenderer>`,对合计值做 `toFixed(n)`：

```aspx
<ext:Column ID="Column2" runat="server" Text="部材存量" DataIndex="SEMI_WEIGHT"
            Width="120" Align="Right" SummaryType="Sum">
    <SummaryRenderer Handler="return value.toFixed(2);"></SummaryRenderer>
</ext:Column>
```

- `SummaryType="Sum"` 触发前端求和。
- `<SummaryRenderer>` 只作用于**汇总行单元格的渲染**,不影响明细行。
- `value.toFixed(2)` 四舍五入到 2 位小数（重量常用 2 位,工时/工资可用 3 位）。

三个重量列都加上即可。

## 四、要素速查

| 元素 | 作用 | 说明 |
|------|------|------|
| `<ext:Summary>` Feature | 在 GridPanel 启用汇总行 | 放在 `<Features>` 内,`Dock="Top"` 可置顶 |
| 列的 `SummaryType` | 汇总计算类型 | `Sum`/`Count`/`Average`/`Max`/`Min` |
| 列的 `<SummaryRenderer>` | 格式化汇总单元格 | 只影响汇总行,`Handler="return value.toFixed(2);"` |
| 列的 `<Renderer>` | 格式化明细单元格 | 两者互不影响,不要混淆 |

完整结构示例：

```aspx
<ext:GridPanel ID="pnlListSum" runat="server" Region="Center">
    <Store>...</Store>
    <ColumnModel>
        <Columns>
            <ext:Column DataIndex="MATERIAL_NAME" Text="物料名称" />
            <ext:Column DataIndex="SEMI_WEIGHT" Text="部材存量" SummaryType="Sum">
                <SummaryRenderer Handler="return value.toFixed(2);"></SummaryRenderer>
            </ext:Column>
        </Columns>
    </ColumnModel>
    <Features>
        <ext:Summary ID="Summary1" runat="server" Dock="Top" />
    </Features>
</ext:GridPanel>
```

## 五、判定要点

| 现象 | 判断 |
|------|------|
| 汇总行小数超长,明细行正常 | 前端 Summary 累加误差 → 加 `SummaryRenderer` |
| 汇总行 + 明细行都有超长小数 | 数据本身浮点,SQL `SUM` 也有误差 → SQL 层 `ROUND(..., 2)` |
| 想让明细行也统一精度 | 用列的 `<Renderer>` + `Ext.util.Format.numberRenderer('0.00')` |

## 六、项目内参考

- **本知识点出处**：`Plugins/Semi/Report/SemiReturnRubberRealTimeStock.aspx`（部材回收胶实时库存,数据汇总 Tab 三个重量列）。
- **同类已验证用法**：`Plugins/Semi/Report/PersonalProduceHourQuery.aspx` 工时/工资列用 `toFixed(3)`。
- 关联文档：`extnet-grid-complete-guide.md`（GridPanel 总览）、`extnet-numberfield-properties.md`（NumberField 精度,属输入控件）。
