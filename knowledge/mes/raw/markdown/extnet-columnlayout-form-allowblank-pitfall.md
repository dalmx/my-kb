---
title: "ColumnLayout 弹窗表单\"一列一行\"+ Defaults 覆盖 allowBlank 踩坑"
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, ColumnLayout, FormPanel, Defaults, allowBlank, anchor, 弹窗, 踩坑, 布局]
status: active
updated: 2026-08-29
---
# ColumnLayout 弹窗表单"一列一行"+ Defaults 覆盖 allowBlank 踩坑

> 两个坑：①anchor 是 AnchorLayout 参数，ColumnLayout 下无效且打架，Defaults 里应换 ColumnWidth="1" 实现一列一行；②Defaults 注入优先级高于子控件自身属性——allowBlank 放 Defaults 会把选填 TextArea 覆盖成必填，必填/选填应各控件单独声明。

## 一、场景

弹窗 Window（`Layout="FitLayout"`）里放一个 `FormPanel`（`Layout="ColumnLayout"`），原本有两个必填下拉框（并排），需求要**追加一个选填的多行备注 TextArea**，且希望三个字段"一列一行"（每个独占一整行）。

典型页：`TyreLockAndUnLock.aspx` 的"冻结原因"弹窗 `winFreeze`，给"行为锁定""冻结原因"两个 ComboBox 之后加"冻结备注" TextArea。

---

## 二、坑 1：anchor 与 ColumnLayout 冲突 → 字段位置错乱

### 现象
加了 TextArea 后，三个控件宽度/位置错乱、挤在一行或串行。

### 根因
FormPanel 用的是 `Layout="ColumnLayout"`，但 `Defaults` 里继承了 `anchor="95%"`：
```aspx
<ext:FormPanel ID="FormPanel1" runat="server" Layout="ColumnLayout" BodyPadding="5">
    <Defaults>
        <ext:Parameter Name="anchor" Value="95%" Mode="Value" />   <%-- ⚠️ AnchorLayout 的参数，在 ColumnLayout 下无效且打架 --%>
        <ext:Parameter Name="allowBlank" Value="false" Mode="Raw" />
        <ext:Parameter Name="msgTarget" Value="side" Mode="Value" />
    </Defaults>
```
`anchor` 是 **AnchorLayout** 的参数，ColumnLayout 不识别它；ColumnLayout 靠 `ColumnWidth`（相对值，同行各项相加=1）或 `Width`（像素）控制宽度。两者混用导致宽度计算异常。

### 解法
`Defaults` 里把 `anchor` 换成 `ColumnWidth`：
```aspx
<Defaults>
    <ext:Parameter Name="ColumnWidth" Value="1" Mode="Raw" />   <%-- 每个子项默认占满一整行 → 一列一行 --%>
    <ext:Parameter Name="msgTarget" Value="side" Mode="Value" />
</Defaults>
```
`ColumnWidth="1"` = 100% 宽度，每个字段自动换行独占一行。无需在每个控件上重复写。

> **布局参数对应关系**（别混用）：
> - `Layout="AnchorLayout"` → 子项用 `anchor`（如 `"100% 50%"`）
> - `Layout="ColumnLayout"` → 子项用 `ColumnWidth`（相对值）或 `Width`（像素）
> - `Layout="FormLayout"` → 子项用 `anchor`

---

## 三、坑 2：Defaults 的 allowBlank 覆盖子控件的 AllowBlank → 选填失效

### 现象
TextArea 明明写了 `AllowBlank="true"`，运行时却变成**必填**（空值时冻结按钮不启用 / 校验报红）。

### 根因
Ext.NET 的 `Defaults` 在容器初始化时把参数**注入到每个子控件，且优先级高于子控件自己声明的同名属性**。所以 `Defaults` 里 `allowBlank="false"` 把 TextArea 自己写的 `AllowBlank="true"` 覆盖了。

### 解法
**从 `Defaults` 移除 `allowBlank`**，改成在**必填**的控件上各自显式声明 `AllowBlank="false"`，选填的控件声明 `AllowBlank="true"`：
```aspx
<Defaults>
    <ext:Parameter Name="ColumnWidth" Value="1" Mode="Raw" />
    <ext:Parameter Name="msgTarget" Value="side" Mode="Value" />
    <%-- allowBlank 不放这里，由各控件自己控制 --%>
</Defaults>
<Items>
    <ext:ComboBox ID="lockTypeComboBox" ... AllowBlank="false" .../>   <%-- 必填，参与 ValidityChange --%>
    <ext:ComboBox ID="txt_Freeze" ... AllowBlank="false" .../>         <%-- 必填 --%>
    <ext:TextArea ID="txt_FreezeRemark" ... AllowBlank="true" MaxLength="500" .../>  <%-- 选填 --%>
</Items>
```

> **规律**：`Defaults` 适合放"所有子项都一样"的参数。一旦有子项需要**不同的值**（如部分必填、部分选填），就别放 Defaults，改成各控件单独声明，否则 Defaults 会覆盖子项设置。

---

## 四、完整正确写法（弹窗 FormPanel 一列一行 + 部分选填）

```aspx
<ext:Window ID="winFreeze" runat="server" Title="冻结原因"
    Width="400" Height="240" Hidden="true" Modal="true" Layout="FitLayout">
    <Items>
        <ext:Container runat="server">
            <Items>
                <ext:FormPanel ID="FormPanel1" runat="server" Layout="ColumnLayout" BodyPadding="5">
                    <Defaults>
                        <ext:Parameter Name="ColumnWidth" Value="1" Mode="Raw" />
                        <ext:Parameter Name="msgTarget" Value="side" Mode="Value" />
                    </Defaults>
                    <Items>
                        <ext:ComboBox ID="lockTypeComboBox" runat="server" FieldLabel="行为锁定"
                            LabelAlign="Right" AllowBlank="false" ColumnWidth="1" Editable="false">
                            ...
                        </ext:ComboBox>
                        <ext:ComboBox ID="txt_Freeze" runat="server" FieldLabel="冻结原因"
                            LabelAlign="Right" AllowBlank="false" ColumnWidth="1" ...>
                            ...
                        </ext:ComboBox>
                        <ext:TextArea ID="txt_FreezeRemark" runat="server" FieldLabel="冻结备注"
                            LabelAlign="Right" AllowBlank="true" MaxLength="500" ColumnWidth="1" />
                    </Items>
                    <Listeners>
                        <%-- ValidityChange 仍生效：必填项空时禁用提交按钮，选填项不影响 --%>
                        <ValidityChange Handler="#{Button3}.setDisabled(!valid);" />
                    </Listeners>
                </ext:FormPanel>
            </Items>
        </ext:Container>
    </Items>
    <Buttons>
        <ext:Button runat="server" Text="冻结" ID="Button3" Disabled="true" .../>
    </Buttons>
</ext:Window>
```

效果：
```text
┌────────────────────────────┐
│  行为锁定  (必填)           │  ← ColumnWidth=1
├────────────────────────────┤
│  冻结原因  (必填)           │  ← ColumnWidth=1
├────────────────────────────┤
│  冻结备注  (选填，多行)      │  ← ColumnWidth=1 + AllowBlank=true
└────────────────────────────┘
```

---

## 五、要点速查

| 坑 | 现象 | 根因 | 解法 |
|----|------|------|------|
| anchor/ColumnLayout 混用 | 字段位置/宽度错乱 | anchor 是 AnchorLayout 参数，ColumnLayout 不识别 | Defaults 用 `ColumnWidth="1"` |
| Defaults 覆盖 allowBlank | 选填项变必填 | Defaults 注入优先级高于子控件自身属性 | Defaults 不放 allowBlank，必填/选填各控件单独声明 |
| 一列一行 | 想每个字段独占一行 | ColumnLayout 默认横排 | 每个字段 `ColumnWidth="1"`（或 Defaults 统一设） |

> **追加字段窗口加高**：加了 TextArea 后窗口高度不够会撑出滚动条，记得把 Window 的 `Height` 调大（如 170→240）。

---

## 六、关联

- 查询区 ColumnLayout 列错位（多列横排场景）：见 `extnet-columnlayout-query-field-pitfall.md`
- 各布局容器适用场景与参数：见 `extnet-page-skeleton.md` 第二节
- 弹窗 Window 标准结构：见 `extnet-page-skeleton.md` 第四节
- 隐藏弹窗内 Grid 加悬浮：见 `extnet-tooltip-in-hidden-window.md`
