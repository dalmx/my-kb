---
title: Ext.NET 查询表单复合控件布局（防重叠正解）
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, 查询表单, 复合控件, ColumnLayout, HBoxLayout, FieldContainer, DateField, TimeField, 布局, 踩坑]
status: active
updated: 2026-08-29
---
# Ext.NET 查询表单复合控件布局（防重叠正解）

> 查询表单里"日期+时间"复合控件（一个 FieldContainer 内横向排 DateField + TimeField）在不同分辨率下挤压、与相邻控件重叠的问题。记录正确写法和踩过的坑。
>
> 场景：Curing 子系统 `CuringProductionQuery.aspx`，查询表单含 `ui_s_BEGIN_TIME`/`ui_s_END_TIME` 两个复合控件（DateField+TimeField），低分辨率下重叠。

## 一、正确写法（验证通过）

### 核心要点

```text
FormPanel Layout="ColumnLayout"  ← 不用 AutoLayout
 └─ Container Layout="FormLayout" Width="320"  ← 固定像素宽度，不用 ColumnWidth 百分比，不用 inline-block
     └─ FieldContainer Layout="HBoxLayout" FieldLabel="开始时间" LabelAlign="Right"
         └─ LayoutConfig: HBoxLayoutConfig Align="Stretch" Pack="Start"
             ├─ DateField Width="110"   ← 子控件用固定 Width，不用 Flex，不靠自然宽度
             └─ TimeField Width="110" MarginSpec="0 0 0 5"
```

### 完整示例

```aspx
<ext:FormPanel ID="container_top" runat="server" Layout="ColumnLayout" AutoHeight="true"
    Collapsible="false" Cls="border-top">
    <Items>
        <%-- 列：固定像素宽度，每列可纵向堆叠多个字段 --%>
        <ext:Container runat="server" Layout="FormLayout" Width="320">
            <Items>
                <%-- 普通字段 --%>
                <ext:ComboBox ID="ui_s_SearchType" runat="server" FieldLabel="查询类型" LabelAlign="Right" ... />

                <%-- 复合控件：DateField + TimeField 横向排列 --%>
                <ext:FieldContainer ID="ui_s_BEGIN_TIME" runat="server" FieldLabel="开始时间"
                    LabelAlign="Right" Layout="HBoxLayout" Hidden="true">
                    <LayoutConfig>
                        <ext:HBoxLayoutConfig Align="Stretch" Pack="Start" />
                    </LayoutConfig>
                    <Items>
                        <ext:DateField ID="ui_s_BEGIN_TIME_Date" Width="110" runat="server"
                            AllowBlank="true" Format="yyyy-MM-dd" />
                        <ext:TimeField ID="ui_s_BEGIN_TIME_Time" Width="110" runat="server"
                            AllowBlank="true" Format="H:i" Increment="30" MarginSpec="0 0 0 5" />
                    </Items>
                </ext:FieldContainer>
            </Items>
        </ext:Container>
    </Items>
</ext:FormPanel>
```

### 三条铁律

| # | 规则 | 说明 |
|---|---|---|
| 1 | **外层用 `ColumnLayout` + `Width="320"` 固定像素** | 不用 `ColumnWidth=".25"` 百分比（低分辨率下百分比列太窄导致子控件挤压）；不用 `AutoLayout`+`inline-block`（画蛇添足） |
| 2 | **复合控件子字段用 `Width="110"` 固定像素** | 不用 `Flex="1"`（Flex 在窄列下比例计算会挤压）；不靠自然宽度（不同浏览器/分辨率下自然宽度不稳定）。110+110+5间距=225px，在 320px 列内从容不挤压 |
| 3 | **`HBoxLayoutConfig Align="Stretch" Pack="Start"`** | 让两个子控件高度对齐 |

## 二、踩过的坑（全部验证过，别再踩）

### 坑1：ColumnWidth 百分比 + Flex=1 → 低分辨率重叠 ❌

```aspx
<!-- 错误写法 -->
<ext:Container Layout="FormLayout" ColumnWidth=".25">          <!-- 25% 太窄 -->
    <ext:FieldContainer Layout="HBoxLayout">
        <ext:DateField Flex="1" />                               <!-- Flex 在窄列下挤压 -->
        <ext:TimeField Flex="1" MarginSpec="0 0 0 5" />
    </ext:FieldContainer>
</ext:Container>
```

问题：`.25`（25%）列宽在低分辨率下太窄，内部两个 `Flex="1"` 子控件被比例强行拉伸/挤压，触发图标和输入框重叠。改成 `.3` 只是缓解不是根治。

### 坑2：盲目照搬 SemiCurveReport 的 inline-block → 过度复杂 ❌

SemiCurveReport 用 `AutoLayout` + `Width="280"` + `display: inline-block; vertical-align: top; margin-right: 130px` + 子控件无 Width（自然宽度）。直接照搬的问题：

- `inline-block` + `margin-right` 是 SemiCurveReport 为对齐"时间/-"短标签的手工微调，不是通用最佳实践
- 子控件不设 Width 靠自然宽度，在不同浏览器/分辨率下不稳定
- `AutoLayout` + `inline-block` 比 `ColumnLayout` + `Width` 复杂，没有额外收益

**结论**：SemiCurveReport 的复合控件防重叠核心技巧只有 `HBoxLayoutConfig Align="Stretch"` 这一点值得借鉴，外层布局用 `ColumnLayout` + `Width` 固定像素更简单可靠。

### 坑3：互斥控件不放同一列同位 → 切换查询类型错位 ❌

`ui_s_BEGIN_DATE`/`ui_s_END_DATE`（日期模式）与 `ui_s_BEGIN_TIME`/`ui_s_END_TIME`（时间模式）通过 JS `show()/hide()` 互斥。如果它们不在**同一列同一位置**，隐藏后该位置塌陷，下方字段上移 → 切换时错位。

**正确**：日期和时间放在同一列同一位置（日期在上、时间在下，时间 `Hidden="true"`），JS 控制各字段本身 show/hide：

```js
var set_ui_s_SearchType = function (item, newValue, oldValue) {
    if (newValue == "1") {
        // 接班日期模式
        App.ui_s_BEGIN_DATE.show();
        App.ui_s_END_DATE.show();
        App.ui_s_BEGIN_TIME.hide();
        App.ui_s_END_TIME.hide();
    } else {
        // 生产时间模式
        App.ui_s_BEGIN_DATE.hide();
        App.ui_s_END_DATE.hide();
        App.ui_s_BEGIN_TIME.show();
        App.ui_s_END_TIME.show();
    }
}
```

### 坑4：嵌套多层 FieldContainer → 结构臃肿 ❌

曾尝试用 `ui_s_TIME_RANGE`(HBox) > `ui_s_BEGIN_TIME`(HBox) > DateField+TimeField 三层嵌套来让开始/结束时间左右并排，结构臃肿且 JS 控制复杂。**不要嵌套超过一层 FieldContainer**。

## 三、字段分组堆叠

查询字段多时（如 12 个），不必每个字段独占一列。用 `ColumnLayout` + `Width="320"` 分 4-5 列，每列纵向堆叠 2-3 个字段（FormLayout 天然纵向排列），更紧凑：

```text
列1(320px)    列2(320px)    列3(320px)    列4(320px)    列5(320px)
查询类型       结束日期       机台          接班班次       二维码
制造编号       结束时间(Hidden) 制造编号      操作工
开始日期       开始时间(Hidden) 轮胎状态
(Hidden)
```

- 互斥的日期/时间字段放在同一列同一位置（如列2 放结束日期+结束时间）
- `ColumnLayout` 会按 `Width` 自动排列，一行放不下自动换行

## 四、关联

- 标准报表页面骨架与 FormPanel 结构：见 `standard-report-template.md`、`extnet-page-skeleton.md`
- DateField 日期范围联动与年月选择器：见 `extnet-datefield-range-and-month.md`
- 查询条件控件升级（TextField→ComboBox/搜索弹窗）：见 `extnet-query-control-upgrade.md`
- ColumnLayout + FormLayout 的 AllowBlank 坑：见 `extnet-columnlayout-form-allowblank-pitfall.md`
- SemiCurveReport 原始页面（参考来源）：`Semi\P.Semi\Wongoing.Semi.WebSite\Plugins\Semi\Technology\SemiCurveReport.aspx`
- 本条目来源页面：`Curing\P.Curing\Wongoing.Curing.WebSite\Plugins\Curing\Produce\CuringProductionQuery.aspx`
