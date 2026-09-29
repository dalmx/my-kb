---
title: Ext.NET 表单杂项控件完整指南
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [表单, Slider, 滑块, SpinnerField, 微调, TagField, 标签, Triggers, 触发器, DropDownField, FieldContainer, Indicator, Note]
status: active
updated: 2026-08-29
---
# Ext.NET 表单杂项控件完整指南

> 本文档从 Ext.NET 4.7.1 官方示例库 `Examples/Form/` 提炼 Slider/SpinnerField/Tag/Triggers/DropDownField/FieldContainer/字段指示器等杂项表单控件。补强已有表单文档。
>
> 适用：Ext.NET 4.x + Triton 主题。

---

## 一、Slider 滑块

`<ext:Slider>` 放进 FormPanel 并设 `FieldLabel` 即为 SliderField（参与表单提交）。

```aspx
<!-- 单滑块 -->
<ext:Slider runat="server" Single="true" FieldLabel="红色"
    MinValue="0" MaxValue="255" Number="128">
    <Listeners><Change Fn="updateColor" /></Listeners>
</ext:Slider>

<!-- 多滑块（区间） -->
<ext:Slider runat="server" FieldLabel="区间" MinValue="0" MaxValue="100">
    <Values>
        <ext:SliderValue Number="20" />
        <ext:SliderValue Number="80" />
    </Values>
</ext:Slider>
```

| 属性 | 作用 |
|------|------|
| `Single="true"` | 单滑块（false 为多滑块） |
| `Number` | 初始值（单滑块） |
| `MinValue`/`MaxValue`/`Increment` | 范围/步长 |
| `Vertical="true"` | 垂直方向 |

取值：JS `App.ID.getValue()`（单）/ `getValues()`（多）；服务端 `ID.Number`。

事件：`Change`（拖动中）、`ChangeComplete`（释放鼠标）。

---

## 二、SpinnerField 数字微调

带上下箭头逐步增减。

```aspx
<ext:SpinnerField runat="server" FieldLabel="数量"
    MinValue="0" MaxValue="100" Step="1" Number="10">
    <Listeners><Spin Handler="Ext.Msg.alert('值', this.getValue());" /></Listeners>
</ext:SpinnerField>
```

| 属性 | 作用 |
|------|------|
| `MinValue`/`MaxValue`/`Step` | 范围/步长 |
| `DecimalPrecision` | 小数位数 |

事件：`Spin(spinner, direction)`，`direction` 为 `"up"`/`"down"`。

---

## 三、Tag 标签

### TagField（输入型多选）

```aspx
<ext:TagField runat="server" FieldLabel="标签" TypeAhead="true" EmptyText="输入标签">
    <Tags>
        <ext:Tag Value="1" />
    </Tags>
    <Items>
        <ext:Tag Value="1" Text="张三" Icon="User" />
        <ext:Tag Value="2" Text="李四" Icon="User" />
    </Items>
</ext:TagField>
```

| 属性 | 作用 |
|------|------|
| `ForceSelection="true"` | 强制只能从 Items 选 |
| `Editable="false"` | 禁止输入 |
| `HideSelected="true"` | 选中后从下拉隐藏 |

JS API：`addTag('1')` / `removeTag('1')` / `setValue(['1','2'])` / `getValue()`。

### TagLabel（只读展示型）

```aspx
<ext:TagLabel runat="server" DefaultClosable="true" SelectionMode="Single">
    <Tags>
        <ext:Tag Text="标签1" Icon="UserAdd" />
        <ext:Tag Text="标签2" Closable="false" />
    </Tags>
</ext:TagLabel>
```

| 属性 | 作用 |
|------|------|
| `DefaultClosable="true"` | 全部可关闭 |
| `SelectionMode` | `Single`/`Simple`/`Multi` |
| `<Menu>` | 右键菜单 |

---

## 四、Triggers 触发按钮（TextField 加按钮）

给字段右侧追加图标按钮。

```aspx
<ext:TextField runat="server" Width="200" EmptyText="点击右侧">
    <Triggers>
        <ext:FieldTrigger Icon="Clear" QTip="清空" Hidden="true" />
        <ext:FieldTrigger Icon="Ellipsis" QTip="选择" Tag="pick" />
    </Triggers>
    <Listeners>
        <TriggerClick Fn="triggerHandler" />
    </Listeners>
</ext:TextField>
```

```javascript
var triggerHandler = function (field, trigger, index, tag) {
    switch (tag) {   // 用 Tag 分支（比 index 清晰）
        case "pick":
            App.PickWindow.show();
            break;
    }
    // 或用 index：0=清空，1=选择
};
```

| 元素 | 作用 |
|------|------|
| `Icon` | 内置图标（`Clear`/`Ellipsis`/`Search`/`Combo` 等） |
| `IconCls` | 自定义图标 CSS 类 |
| `QTip` | 悬停提示 |
| `Tag="标识"` | 自定义标记（TriggerClick 第三参） |
| `Hidden="true"` | 初始隐藏，运行时 show |

动态控制：`field.getTrigger(0).hide()` / `.show()`。

---

## 五、DropDownField 自定义下拉面板

字段 + 触发按钮，**下拉内容是任意 Component**（Panel/Tree/Grid/Form）。

### 基础用法（下拉菜单）

```aspx
<ext:DropDownField runat="server" TriggerIcon="Search" Editable="false">
    <Component>
        <ext:Panel runat="server" Height="200">
            <Items>
                <ext:MenuPanel runat="server" Title="选择">
                    <Menu runat="server">
                        <Items>
                            <ext:MenuItem runat="server" Text="选项1" />
                        </Items>
                        <Listeners>
                            <Click Handler="#{DDF1}.setValue(menuItem.text);" />
                        </Listeners>
                    </Menu>
                </ext:MenuPanel>
            </Items>
        </ext:Panel>
    </Component>
</ext:DropDownField>
```

### ValueText 双值模式（Tree 多选）

```aspx
<ext:DropDownField runat="server"
    UnderlyingValue="1,2" Text="[张三,李四]"
    Editable="false" Mode="ValueText" TriggerIcon="SimpleArrowDown">
    <Component>
        <ext:TreePanel runat="server" Height="250" RootVisible="false">
            <Root>
                <ext:Node>
                    <Children>
                        <ext:Node NodeID="1" Text="张三" Leaf="true" Checked="False" />
                        <ext:Node NodeID="2" Text="李四" Leaf="true" Checked="False" />
                    </Children>
                </ext:Node>
            </Root>
            <Listeners>
                <CheckChange Handler="this.dropDownField.setValue(getValues(this), getText(this), false);" />
            </Listeners>
        </ext:TreePanel>
    </Component>
    <SyncValue Fn="syncValue" />
</ext:DropDownField>
```

| 属性 | 作用 |
|------|------|
| `<Component>` | 下拉面板（任意控件） |
| `Mode="ValueText"` | 双值模式（Value 提交值 + Text 显示） |
| `PickerAlign` | 对齐方式 |
| `MatchFieldWidth="false"` | 下拉宽度不跟随字段 |

取值：`getValue()`（Value）/ `getText()`（Text）；服务端 `SetValue(value, text)`。

> 下拉面板内控件用 `this.dropDownField` 引用宿主字段（自动注入）。

---

## 六、FieldContainer 字段容器（组合多字段）

把多个子字段打包成一个逻辑字段，统一 `FieldLabel`。

```aspx
<ext:FieldContainer runat="server" FieldLabel="日期范围"
    CombineErrors="true" MsgTarget="Side" Layout="HBoxLayout">
    <Defaults>
        <ext:Parameter Name="Flex" Value="1" Mode="Raw" />
        <ext:Parameter Name="HideLabel" Value="true" Mode="Raw" />
    </Defaults>
    <Items>
        <ext:DateField runat="server" Name="StartDate" AllowBlank="false" MarginSpec="0 5 0 0" />
        <ext:DateField runat="server" Name="EndDate" />
    </Items>
</ext:FieldContainer>
```

| 属性 | 作用 |
|------|------|
| `CombineErrors="true"` | 合并子字段校验错误 |
| `Layout="HBoxLayout"` | 横向排列（最常用） |
| `<Defaults>` | 子字段统一默认值 |

子字段用各自 `Name`，`getForm().getValues()` 自动收集。

---

## 七、字段指示器与备注（任意字段通用属性）

### Indicator（右侧状态图标）

```aspx
<ext:TextField runat="server" FieldLabel="名称" AllowBlank="false"
    IndicatorText="*" IndicatorCls="red-text" />

<ext:TextField runat="server" FieldLabel="提示"
    IndicatorIcon="Information" IndicatorTip="这是说明" />
```

| 属性 | 作用 |
|------|------|
| `IndicatorIcon` | 右侧图标 |
| `IndicatorText` | 右侧文字（如必填星号 `*`） |
| `IndicatorTip` | 图标 tooltip |
| `IndicatorCls` | 文字 CSS 类 |

### Note（下方说明）

```aspx
<ext:TextField runat="server" FieldLabel="邮箱" Note="请输入有效邮箱" />

<ext:ComboBox runat="server" Note="必选项" NoteAlign="Top" NoteCls="red-note" />
```

| 属性 | 作用 |
|------|------|
| `Note` | 备注内容（支持 HTML） |
| `NoteAlign="Top"` | 位置（默认下方） |
| `NoteCls` | CSS 类 |

---

## 八、控件速查（按场景）

| 需求 | 控件 | 关键点 |
|------|------|--------|
| 数值拖选 | `Slider` | `Single`/`MinValue`/`Number` |
| 数字加减 | `SpinnerField` | `Spin` 事件 + `direction` |
| 多选标签输入 | `TagField` | `addTag`/`setValue`/`ForceSelection` |
| 只读标签展示 | `TagLabel` | `DefaultClosable`/`SelectionMode` |
| 文本框加按钮 | `TextField`+`Triggers` | `FieldTrigger.Tag`+`TriggerClick` |
| 自定义下拉 | `DropDownField` | `<Component>`+`Mode="ValueText"` |
| 多字段合一 | `FieldContainer` | `Layout="HBoxLayout"`+`CombineErrors` |
| 字段右侧图标 | `Indicator*` 属性 | `IndicatorIcon`/`IndicatorText` |
| 字段下方说明 | `Note` 属性 | `Note`/`NoteAlign` |

---

## 九、踩坑要点

### 坑1：TagField 的 addTag 参数是 Value 不是 Text

```javascript
App.Tags1.addTag('1');          // ✅ 按 Value
App.Tags1.addTag('张三');        // ❌ Text 无效（除非自由输入模式）
```

### 坑2：DropDownField 双值模式 setValue 第三参

```javascript
field.setValue(value, text, false);   // 第三参 false = 不触发 change
```

### 坑3：FieldContainer 子字段要 HideLabel

子字段默认有自己的标签，组合时设 `HideLabel="true"`，标签由容器统一管。

### 坑4：Triggers 的 TriggerClick 参数因 Tag 而变

无 Tag 时：`(field, trigger, index)`；有 Tag 时第三参变成 Tag 字符串，注意签名变化。

### 坑5：Slider 多滑块用 Values 而非 Number

```aspx
<!-- 多滑块 -->
<Values><ext:SliderValue Number="20" /><ext:SliderValue Number="80" /></Values>
<!-- Number 只对单滑块生效 -->
```

### 坑6：IndicatorIcon 服务端改要 RegisterIcon

```csharp
Field1.IndicatorIcon = Icon.Accept;
ResourceManager1.RegisterIcon(Icon.Accept);   // 必须注册图标资源
```

---

## 十、关联文档

| 文档 | 关系 |
|------|------|
| `extnet-combobox-properties.md` | ComboBox（下拉基础） |
| `extnet-numberfield-properties.md` | NumberField（数字字段） |
| `extnet-datefield-range-and-month.md` | DateField（日期字段） |
| `extnet-form-validation-complete.md` | 表单校验 |
| `extnet-query-form-compound-control-layout.md` | 查询表单复合控件（FieldContainer 实战） |

## 十一、参考来源

- `Examples/Form/Slider/Overview/`
- `Examples/Form/SpinnerField/Custom/`
- `Examples/Form/Tag/TagField/`、`TagLabel/`
- `Examples/Form/Triggers/Overview/`、`Custom_Icon/`
- `Examples/Form/DropDownField/Overview/`、`ValueText_Mode/`
- `Examples/Form/FieldContainer/Overview/`
- `Examples/Form/Field_Indicator/Overview/`
- `Examples/Form/Field_Note/Overview/`
