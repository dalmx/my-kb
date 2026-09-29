---
title: Ext.NET NumberField — 数字框小数与范围控制
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, NumberField, DecimalPrecision, AllowDecimals, MinValue, MaxValue, TrimTrailedZeros, 属性速查]
status: active
updated: 2026-08-29
---
# Ext.NET NumberField — 数字框小数与范围控制

> NumberField 数值控制五属性：MinValue/MaxValue 范围校验（超范围红色提示边框）、AllowDecimals 是否允许小数、DecimalPrecision 小数位数（超位四舍五入，须配合 AllowDecimals）、TrimTrailedZeros 去末尾无意义零。注意 DecimalPrecision 只管前端显示，后端需自行 Math.Round；输入约束用属性、展示格式化用 Renderer+toFixed，两者独立分工。

## 一、属性速查

| 属性 | 作用 | 示例值 |
|------|------|--------|
| `MinValue="0"` | 允许输入的最小值 | `0` |
| `MaxValue="100"` | 允许输入的最大值 | `100` |
| `AllowDecimals="true"` | 允许输入小数 | `true` / `false` |
| `DecimalPrecision="1"` | 小数点后精度位数 | `1`、`2`、`3` |
| `TrimTrailedZeros` | 去除末尾不必要的零 | `true` / `false` |

## 二、属性详解

### MinValue / MaxValue — 范围限制

设定数字框可接受的最小/最大值，超出范围时触发校验失败（红色提示边框）。

```xml
<ext:NumberField ID="nfScore" runat="server"
    MinValue="0" MaxValue="100" />
```

- 输入 -5 → 校验失败（小于 MinValue）
- 输入 120 → 校验失败（大于 MaxValue）
- 仅限制**数值范围**，不限制输入位数；与 `AllowBlank` 配合可控制是否必填

### AllowDecimals — 是否允许小数

```xml
<ext:NumberField runat="server" AllowDecimals="true" />
```

- `true`：可输入小数点（如 `12.5`）
- `false`：只允许整数，输入小数点会被拦截/校验失败

> 整数场景（如数量、件数）设 `AllowDecimals="false"`；涉及测量值（如重量、尺寸、合格率）设 `true`。

### DecimalPrecision — 小数精度

控制小数点后保留几位，**超出部分自动截断/四舍五入**。

```xml
<ext:NumberField runat="server"
    AllowDecimals="true" DecimalPrecision="1" />
```

| DecimalPrecision | 输入 12.567 显示为 |
|------------------|-------------------|
| `1` | `12.6` |
| `2` | `12.57` |
| `3` | `12.567` |

- 必须配合 `AllowDecimals="true"` 才生效
- `DecimalPrecision="0"` 等同于不允许小数

### TrimTrailedZeros — 去除末尾零

去除数字表示中末尾不必要的零。

| 输入值 | TrimTrailedZeros | 显示 |
|--------|------------------|------|
| `12.50` | 未设/`false` | `12.50` |
| `12.50` | `true` | `12.5` |
| `12.00` | `true` | `12` |

> 当 `DecimalPrecision="2"` 但实际值是 `12.5` 时，默认会显示 `12.50`；设 `TrimTrailedZeros` 后显示 `12.5`，避免末尾无意义的零影响查看。

## 三、完整示例

```xml
<ext:NumberField ID="nfValue" runat="server"
    FieldLabel="数值"
    LabelAlign="Right"
    AllowBlank="false"
    IndicatorText="*"
    IndicatorCls="red-text"
    MinValue="0"
    MaxValue="100"
    AllowDecimals="true"
    DecimalPrecision="1"
    TrimTrailedZeros="true"
    Width="200" />
```

效果：
- 只能输入 0~100 之间的数
- 允许小数，精度 1 位
- 输入 `50.00` → 显示 `50`；输入 `50.50` → 显示 `50.5`

## 四、后端取值

```csharp
// NumberField 的值是 decimal 类型
decimal value = nfValue.Value;
// 或
double dValue = Convert.ToDouble(nfValue.Value);
```

> 注意 `DecimalPrecision` 只控制**前端显示精度**，后端拿到的仍是实际输入值。若需后端也按精度截断，需在 C# 里 `Math.Round(value, 1)`。

## 五、与前端 toFixed 格式化的区别

| 维度 | NumberField 属性 | JS toFixed |
|------|-----------------|------------|
| 作用对象 | 输入控件本身（输入时约束） | Grid/展示列渲染时格式化 |
| 控制阶段 | 输入阶段 | 显示阶段 |
| 典型属性/方法 | `DecimalPrecision`、`AllowDecimals` | `value.toFixed(2)` |

- NumberField 属性管**输入时**能输什么、显示几位
- `toFixed` 管**表格/展示时**显示几位
- 两者独立，输入控件用属性，展示列用 Renderer + toFixed

## 六、关联

- 前端 toFixed 格式化（Grid 展示列）：见 `dynamic-column-grid.md`
- 表单校验模式（AllowBlank 等）：见 `extnet-form-validation-complete.md`
- ComboBox 属性速查：见 `extnet-combobox-properties.md`
- DateField 属性速查：见 `extnet-datefield-range-and-month.md`
