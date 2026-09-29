---
title: Ext.NET 表单验证全模式（本地必填 + 远程校验 + 按钮控制）
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, 表单验证, 必填, ValidityChange, RemoteValidation, allowBlank, IndicatorText, 按钮控制, 踩坑]
status: active
updated: 2026-08-29
---
# Ext.NET 表单验证全模式（本地必填 + 远程校验 + 按钮控制）

> 合并说明： 本文由本地必填（ValidityChange）与远程校验（RemoteValidation）两篇同题文档合并而成，涵盖两种验证机制及其与按钮控制的配合。

Ext.NET 表单验证分两种模式：
- **本地验证**：必填校验、格式校验，纯前端完成（ValidityChange + AllowBlank）。
- **远程验证**：需到后台查库判断（如编码是否重复），通过 RemoteValidation 异步回调。

---

## 一、本地必填验证（ValidityChange + Disabled 初始态）

## 二、核心模式

参考页面：`StoragePlaceBaseInfo.aspx`（库位设置）

### 前端 aspx 写法

```aspx
<ext:Window ID="winEdit" runat="server" Layout="FitLayout">
    <Items>
        <ext:FormPanel ID="frmEdit" runat="server" MonitorValid="true" Layout="FormLayout">
            <Items>
                <ext:TextField ID="editName" runat="server" FieldLabel="名称" 
                    AllowBlank="false" IndicatorText="*" IndicatorCls="red-text" />
                <ext:NumberField ID="editNum" runat="server" FieldLabel="数量" 
                    AllowBlank="false" IndicatorText="*" IndicatorCls="red-text" />
            </Items>
            <Listeners>
                <ValidityChange Handler="#{btnSave}.setDisabled(!valid);" />
            </Listeners>
        </ext:FormPanel>
    </Items>
    <Buttons>
        <ext:Button ID="btnSave" runat="server" Text="保存" Disabled="true">
            <DirectEvents>
                <Click OnEvent="BtnSave_Click">
                    <EventMask ShowMask="true" Msg="保存中..." MinDelay="50" />
                </Click>
            </DirectEvents>
        </ext:Button>
    </Buttons>
</ext:Window>
```

### 关键要点

| 要素 | 说明 |
|------|------|
| `MonitorValid="true"` | FormPanel 属性，启用客户端表单验证监控 |
| `AllowBlank="false"` | 字段级，标记为必填 |
| `IndicatorText="*"` + `IndicatorCls="red-text"` | 必填字段红色星号标记 |
| `ValidityChange` 监听器 | 表单有效性变化时触发，`valid` 参数为 `true/false` |
| `btnSave` 初始 `Disabled="true"` | 打开窗口时按钮禁用，填完后自动启用 |
| **不需要** `FormBind` | 此项目中 `FormBind` 不可靠，用 `ValidityChange` 替代 |
| **不需要** `Before` 拦截 | 按钮已通过 `Disabled` 控制，无需额外前端校验 |

### 错误示范（不生效的方式）

- `FormBind="true"` — 在此项目中不生效
- `<Before Handler="...">` — 不能作为 `<Click>` 的子元素，只能作为属性
- `Before` 属性中写 `return false` — 语法可行但不如 `ValidityChange` 彻底

### 编辑回填时的行为

当通过 `LoadEditForm`（DirectMethod）回填数据后，`ValidityChange` 会自动触发，表单有效时按钮自动启用。无需额外处理。

### 通用字段属性

```aspx
<FieldDefaults LabelWidth="100" LabelAlign="Right" />
```

统一设置 FormPanel 内所有字段的标签宽度和对齐方式。

---

## 三、远程验证（RemoteValidation + 控制确认按钮）

## 四、场景

输入框输入内容后，需到**后台查库验证**该值是否合法/重复，并根据验证结果控制前台「确认/保存」按钮的启用与禁用。

典型用途：
- 新增时校验编码/名称是否已存在（防重复）。
- 校验外键值是否在主数据中存在。
- 校验通过才允许点「确认」提交。

## 五、方案概览

```text
输入框输入 → Blur/RemoteValidation 触发
           → 后台 RemoteValidation 事件查库
           → 返回成功/失败
           → 前台根据结果 setDisabled(true/false) 确认按钮
```

核心三件套：
1. **aspx**：TextField 配 `RemoteValidation`，按钮设初始 `Disabled="true"`。
2. **C#**：`RemoteValidation` 事件处理方法，查库后设 `e.Success`。
3. **JS**：验证完成回调里控制按钮 `setDisabled`。

## 六、aspx 配置

```xml
<ext:TextField ID="txtCode" runat="server" FieldLabel="编码"
    AllowBlank="false" IndicatorText="*" IndicatorCls="red-text"
    Width="300" LabelAlign="Left">
    <RemoteValidation Url="页面名.aspx" Method="POST">
        <ExtraParams>
            <ext:Parameter Name="action" Value="checkCode" Mode="Value" />
        </ExtraParams>
    </RemoteValidation>
</ext:TextField>

<ext:TextField ID="txtName" runat="server" FieldLabel="名称"
    ReadOnly="true" Width="300" />

<ext:Button ID="btnConfirm" runat="server" Text="确认" Icon="Accept" Disabled="true">
    <DirectEvents>
        <Click OnEvent="btnConfirm_Click" />
    </DirectEvents>
</ext:Button>
```

## 七、C# 后台校验

```csharp
protected void CheckField(object sender, RemoteValidationEventArgs e)
{
    TextField field = sender as TextField;
    string inputCode = field.Text;

    if (string.IsNullOrWhiteSpace(inputCode))
    {
        e.Success = false;
        e.ErrorMessage = "请输入编码";
        return;
    }

    bool exists = CheckCodeExists(inputCode);

    if (exists)
    {
        e.Success = true;
        e.ErrorMessage = "";
        txtName.Text = GetCodeName(inputCode);
    }
    else
    {
        e.Success = true;
    }
}
```

- `e.Success = true` → 输入框标记为有效（绿勾）。
- `e.Success = false` + `e.ErrorMessage` → 标记无效并显示错误提示。

## 八、JS 控制按钮可用性

```javascript
// 方式 A：监听 validitychange
App.txtCode.on('validitychange', function (field, isValid) {
    App.btnConfirm.setDisabled(!isValid);
});

// 方式 B：RemoteValidation 客户端回调
var onCodeValidated = function (field, isValid) {
    App.btnConfirm.setDisabled(!isValid);
    if (!isValid) {
        App.txtName.setValue('');
    }
};
```

## 九、多字段联动

```javascript
var checkAllFields = function () {
    var allValid = App.txtCode.isValid() && App.txtName.isValid();
    App.btnConfirm.setDisabled(!allValid);
};

App.txtCode.on('validitychange', checkAllFields);
App.txtName.on('validitychange', checkAllFields);
```

## 十、两种验证模式对比

| 维度 | 本地验证（ValidityChange） | 远程验证（RemoteValidation） |
|------|---------------------------|------------------------------|
| 校验位置 | 纯前端 | 后台查库 |
| 触发时机 | 每次字段值变化 | blur（失焦）时 |
| 典型场景 | 必填、格式校验 | 防重复、外键存在性校验 |
| 按钮控制 | `ValidityChange` Handler 里 `setDisabled` | `validitychange` 事件或 RemoteValidation 回调 |
| 性能 | 无网络开销 | 每次 AJAX 回发 |

> 两者可共存：本地验证保证必填/格式，远程验证保证业务唯一性。

## 十一、注意

- `FormBind` 在此项目不可靠，统一用 `ValidityChange` + `Disabled` 控制按钮。
- RemoteValidation 默认 blur 触发；需即时校验可改用 `DirectMethod` + `Blur` 监听。
- 校验失败时按钮保持禁用，防止绕过校验直接提交。
- RemoteValidation 会发 AJAX 回服务端，高频输入注意节流。
- 编辑回填后 ValidityChange 自动触发，按钮自动启用，无需额外处理。

## 十二、关联

- DirectMethod 与数据交互：见 `extnet-directmethod-and-data.md`
- ComboBox 属性与本地校验（AllowBlank / ForceSelection）：见 `extnet-combobox-properties.md`
- DateField 范围校验（Vtype daterange）：见 `extnet-datefield-range-and-month.md`
- NumberField 范围校验（MinValue / MaxValue）：见 `extnet-numberfield-properties.md`
