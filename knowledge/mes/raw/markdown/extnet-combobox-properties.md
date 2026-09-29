---
title: Ext.NET ComboBox 属性速查与客户端方法
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, ComboBox, 属性速查, 本地化, 必填校验, 模糊匹配, 客户端API]
status: active
updated: 2026-08-29
---
# Ext.NET ComboBox 属性速查与客户端方法

> ComboBox 属性分主题速查：本地化 FieldLabel（<%$Resources:Semi,机台 %>）、必填三件套（IndicatorText/IndicatorCls 只管星号显示，校验靠 AllowBlank="false"）、可编辑+模糊匹配组合语义（Editable/ForceSelection/AnyMatch/QueryMode）、静态下拉用 Items 内联 ListItem；客户端两种"清空"语义：clearValue() 只清选中值，getStore().removeAll() 清选项数据。

## 一、基础属性

| # | 属性 | 作用 |
|---|------|------|
| 1 | `ID="add_com_Equip"` | 控件唯一标识符，用于后端 C# 代码引用 |
| 2 | `runat="server"` | 声明为服务器端控件，可在 C# 代码中访问 |
| 3 | `FieldLabel="<%$Resources:Semi,机台 %>"` | 标签文本，从资源文件 `Semi.resx` 取"机台"的本地化值 |
| 4 | `LabelAlign="Right"` | 标签文本右对齐 |
| 5 | `MultiSelect="false"` | 禁用多选（单选模式） |

> 资源文件语法 `<%$Resources:ClassName,Key%>`：运行时从 `App_GlobalResources/ClassName.resx` 取 Key 对应的值，支持多语言切换。

## 二、必填校验

| # | 属性 | 作用 |
|---|------|------|
| 6 | `IndicatorText="*"` | 必填字段标识符（显示红色星号 `*`） |
| 7 | `IndicatorCls="red-text"` | 必填标识符的 CSS 样式类（控制星号颜色等） |
| 8 | `AllowBlank="false"` | 禁止空值，强制用户必须选择，否则校验不通过 |

> `IndicatorText` + `IndicatorCls` 只控制**星号的显示样式**；真正的**校验逻辑**由 `AllowBlank="false"` 控制。三者通常配套使用。

## 三、可编辑与模糊匹配

| # | 属性 | 作用 |
|---|------|------|
| 9 | `Editable="true"` | 允许用户输入文本（配合 `ForceSelection` 实现自动补全） |
| 10 | `ForceSelection="true"` | 强制选择下拉列表中的有效项；输入值必须匹配某个选项，否则无效 |
| 11 | `AnyMatch="true"` | 匹配任意位置的字符（如输入 "ab" 可匹配 "xab"、"abc"） |
| 12 | `ValueField="EquipCode"` | 选项值字段，提交到后端的实际值 |
| 13 | `DisplayField="EquipName"` | 选项显示字段，用户看到的文本 |
| 14 | `QueryMode="Local"` | 使用本地数据过滤（非远程 API 查询） |
| 15 | `MatchFieldWidth="false"` | 下拉框宽度不自动匹配输入框宽度（可更宽以展示长文本） |

> 组合语义：
> - `Editable="true"` + `ForceSelection="true"` = 可输入但必须选有效项（自动补全模式）
> - `Editable="true"` + `ForceSelection="false"` = 可输入任意值（自由文本 + 联想）
> - `Editable="false"` = 只能从下拉选，不可输入

## 四、完整示例：数据绑定型 ComboBox

```xml
<ext:ComboBox ID="add_com_Equip" runat="server"
    FieldLabel="<%$Resources:Semi,机台 %>"
    LabelAlign="Right"
    MultiSelect="false"
    IndicatorText="*"
    IndicatorCls="red-text"
    AllowBlank="false"
    Editable="true"
    ForceSelection="true"
    AnyMatch="true"
    ValueField="EquipCode"
    DisplayField="EquipName"
    QueryMode="Local"
    MatchFieldWidth="false">
    <Store>
        <ext:Store runat="server">
            <Model>
                <ext:Model runat="server">
                    <Fields>
                        <ext:ModelField Name="EquipCode" />
                        <ext:ModelField Name="EquipName" />
                    </Fields>
                </ext:Model>
            </Model>
        </ext:Store>
    </Store>
</ext:ComboBox>
```

## 五、静态下拉框（固定选项）

固定枚举值不绑 Store，直接用 `<Items>` 内联 `ListItem`：

```xml
<ext:ComboBox ID="IsSummary" runat="server"
    FieldLabel="<%$Resources:Part,汇总状态%>"
    LabelAlign="Right">
    <Items>
        <ext:ListItem Value="0" Text="未汇总" />
        <ext:ListItem Value="1" Text="已汇总" />
    </Items>
</ext:ComboBox>
```

## 六、下拉框可拉伸

`Resizable`（或 `Resizable="true"`）使下拉列表窗口可拉伸，方便查看长文本列内容。放在 ComboBox 标签属性上。

## 七、客户端方法：清空

两种"清空"语义不同，注意区分：

| 方法 | 作用 | 适用场景 |
|------|------|----------|
| `App.txt_Freeze.clearValue()` | 清空**选中值**（Store 数据保留，只是把当前选中项置空） | 重置查询条件 |
| `App.txt_Freeze.getStore().removeAll()` | 清空**下拉选项数据**（Store 清空，下拉没东西可选） | 重新加载前先清空、或级联清空下级选项 |

```javascript
// 场景 A：重置查询条件 —— 值清空，选项还在，可重新选
App.txt_Freeze.clearValue();

// 场景 B：级联联动 —— 上级变了，下级选项整体清掉再重载
App.txt_Freeze.getStore().removeAll();
App.txt_Freeze.getStore().loadData(newData);
```

## 八、关联

- 查询条件 ComboBox 升级（TypeAhead / AnyMatch / 远程查询）：见 `extnet-query-control-upgrade.md`
- 模糊搜索踩坑：见 `extnet-combobox-fuzzy-search.md`
- 标准/汇总明细报表模板中的 ComboBox 用法：见 `standard-report-template.md`、`summary-detail-report-template.md`
- NumberField 属性速查（数值控件）：见 `extnet-numberfield-properties.md`
- DateField 属性速查（日期控件）：见 `extnet-datefield-range-and-month.md`


## 九、补充关联（反向链接）

| 文档 | 说明 |
|------|------|
| `extnet-resourcemanager-locale.md` | ResourceManager Locale 中文化 |
| `extnet-query-form-compound-control-layout.md` | 查询表单复合控件布局 |
