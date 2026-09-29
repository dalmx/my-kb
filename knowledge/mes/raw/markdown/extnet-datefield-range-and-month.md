---
title: Ext.NET DateField — 日期范围联动与年月选择器
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, DateField, daterange, 日期范围, 年月选择, 客户端API, 属性速查]
status: active
updated: 2026-08-29
---
# Ext.NET DateField — 日期范围联动与年月选择器

> 两个技巧：①两个 DateField 设 Vtype="daterange" 并用 CustomConfig 互指对方 ID（endDateField/startDateField），实现开始 ≤ 结束的 minValue/maxValue 联动；②客户端把 dateField.type 设为 'month'、format 设为 'Y-m'，将 DateField 变成只选年月的选择器并设当前年月初始值。附 Format 两种写法（Y-MM-dd 与 yyyy-MM-dd）的差异提醒。

## 一、日期范围控制（开始 ≤ 结束）

### 1.1 原理

ExtJS 的 `daterange` Vtype 用于约束两个 DateField 的大小关系：
- 开始日期 ≤ 结束日期
- 在其中一个日期改变时，自动更新另一个日期的可选范围（minValue / maxValue）

关键是通过 `CustomConfig` 互相指定对方的 ID，让 Vtype 知道"参照谁"。

### 1.2 用法

两个 DateField 都设 `Vtype="daterange"`，再用 `CustomConfig` 互指：

```xml
<!-- 开始日期：告知结束日期是谁 -->
<ext:DateField ID="DateStart" runat="server" Vtype="daterange"
    FieldLabel="制定开始日期" Format="Y-MM-dd">
    <CustomConfig>
        <ext:ConfigItem Name="endDateField" Value="DateEnd" Mode="Value" />
    </CustomConfig>
</ext:DateField>

<!-- 结束日期：告知开始日期是谁 -->
<ext:DateField ID="DateEnd" runat="server" Vtype="daterange"
    FieldLabel="制定截止日期" Format="Y-MM-dd">
    <CustomConfig>
        <ext:ConfigItem Name="startDateField" Value="DateStart" Mode="Value" />
    </CustomConfig>
</ext:DateField>
```

### 1.3 配对规则

| 字段 | 所在控件 | 指向 |
|------|----------|------|
| `endDateField` | 开始日期 DateField | 结束日期的 **ID**（字符串） |
| `startDateField` | 结束日期 DateField | 开始日期的 **ID**（字符串） |

- 开始日期改了 → 结束日期的 minValue 自动更新（不能早于开始）
- 结束日期改了 → 开始日期的 maxValue 自动更新（不能晚于结束）
- `Mode="Value"` 表示 `Value` 是字面量字符串值（即 ID 名），非表达式

### 1.4 关于最大值/最小值

- `daterange` 联动本身就是通过动态设置 minValue / maxValue 实现的。
- 若只需固定上下限（不联动），可直接用 `MinValue="2026-01-01"` / `MaxValue="2026-12-31"` 属性，不必用 Vtype。

## 二、年月选择器（只选年-月，不选日）——两种方法

### 2.1 原理

Ext.NET DateField 没有独立的"年月控件"，靠 `type='month'` 配置把弹层切换为年月选择（官方示例 `form/DateField/Overview`）。Ext.Net.dll 内嵌源码实证：`createPicker()` 在**首次展开弹层时**才读取 `this.type == "month"` 决定建哪种选择器（惰性求值）——因此该配置既可在创建期由服务端属性下发（**方法一**），也可在组件创建后、首次展开前由 JS 赋值（**方法二**），两条路都通。

### 2.2 方法一（首选）：服务端 `Type="Month"` 属性

```xml
<ext:DateField ID="dtMonth" runat="server" FieldLabel="月份" AllowBlank="false" Type="Month"
    LabelAlign="Right" Editable="false" Format="yyyy-MM" />
```

- 官方示例 `form/DateField/Overview`（Ext.NET 4.7）实证写法；
- 创建期配置、**零时序依赖**，最稳；
- `Format="yyyy-MM"` 显示 2026-09，后端 RawText/TryParseExact 零改动；初始值服务端 `SelectedDate=Now` 即可。

### 2.3 方法二：客户端 JS 赋值（备选，注意时序坑）

```javascript
// 脚本必须放在组件树之后（body 末尾）或 afterrender 时机执行——组件已建、用户尚未首次点开
var df = App.ui_s_YueFen;
df.type = 'month';
df.format = 'Y-m';
df.setValue(Ext.Date.format(new Date(), 'Y-m'));
```

- ⚠️ **时序坑（2026-09-18 MoldSchedulePlan 实测踩坑）**：写在 `<head>` 脚本块里的 `Ext.onReady` 回调**早于 ResourceManager 初始化组件树**执行，此时 `App.<id>` 尚未创建——配 `if (df)` 保护会静默跳过，表面症状"没生效"，根因是时机不是写法；
- 须满足：组件创建之后 + 用户首次展开之前；
- 适用场景：服务端控件改不了（公共模板/封装死的控件），只能客户端补配置。

### 2.4 两法对比与格式要点

| 项 | 方法一（服务端） | 方法二（客户端） |
|----|------------------|------------------|
| 写法 | `Type="Month"` | `df.type='month'` + format + setValue |
| 时序 | 无依赖 | 须组件创建后、首次展开前 |
| 定位 | ✅ 首选 | 备选 |

格式串：`Y`=四位年（2026）、`m`=两位月（01-12）、`d`=两位日；`Y-m` → 2026-07。服务端 `Format="yyyy-MM"` 与之等效（.NET 风格被 Ext.NET 兼容映射），同一页面保持一种写法。

> 误判记录：2026-09-18 曾因 head 脚本时序问题误判"渲染后赋值无效"并错将本节标作废，同日经 dll 反编译（createPicker 惰性读 type）纠正——勿再重蹈，排障先查执行时机。

### 2.5 取值（提交到后端）

```javascript
var yueFen = Ext.getCmp('ui_s_YueFen').getValue(); // 形如 "2026-07"
```

后端拿到的是字符串，按需解析为 `DateTime` 或直接拼 SQL。

## 三、Format 写法差异提醒

项目中存在两种日期格式写法，均可工作，但建议统一：

| 写法 | 出现场景 | 示例 |
|------|----------|------|
| `Format="Y-MM-dd"` | 日期范围示例、部分老页面 | `2026-07-09` |
| `Format="yyyy-MM-dd"` | 报表模板、多数页面 | `2026-07-09` |

- ExtJS 原生格式串用 `Y/m/d`（如 `Y-m-d`）。
- `yyyy-MM-dd` 是 .NET 风格，Ext.NET 做了兼容映射。
- **同一页面内保持一致**即可，避免混用。

## 四、关联

- 报表模板中的 DateField 基础用法：见 `standard-report-template.md`、`chart-table-report-template.md`、`dynamic-column-popup-report-template.md`
- 表单校验模式（AllowBlank 等）：见 `extnet-form-validation-complete.md`
