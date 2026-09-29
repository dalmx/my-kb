---
title: Semi 平台 Ext.NET 弹窗（Window）风格对齐规范
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [弹窗, Window, 风格对齐, 平台标准, Ext.NET, 弹窗风格, 弹窗样式, 对齐平台, 选择弹窗, 确定关闭按钮, fa-paper-plane, fa-file-text, CheckboxSelectionModel, 项目差异, 明细弹窗]
status: active
updated: '2026-09-18'
---
# Semi 平台 Ext.NET 弹窗（Window）风格对齐规范

> 做新弹窗（Window）前必读。基于 Semi 项目全量 **98 个 `<ext:Window>` + 74 个确定按钮** 的统计结论，纠正"凭印象写弹窗"的常见错误：业务弹窗不设 UI、IconCls 用 `fa-paper-plane`、Layout 用 FitLayout、确定按钮不设 UI、文案用"确定/关闭"。附标准样本路径和对齐检查清单。基础 Window 用法见 [[extnet-window-guide]]，页面骨架见 [[extnet-page-skeleton]]，按钮权限见 [[button-permission]]。

## 一、适用边界：本规范是 Semi 平台统计，目标项目内同类弹窗惯例优先（2026-09-18 Molding 实证）

同族项目（Molding/Mould/EquipManage…）共用 Ext.NET 体系但**弹窗惯例有差异**。给目标项目做弹窗的正确顺序：

1. **先 grep 目标项目的 `ext:Window` 统计同类弹窗惯例**（按场景找同类：明细查看类对明细查看类、表单类对表单类）；
2. 项目内同类惯例与本规范冲突时，**以项目内为准**（同页/同项目观感一致才是用户眼中的"对齐"）；
3. 本规范兜底项目内无先例的场景（结构骨架：FitLayout/Hidden/Closable/按钮文案"确定/关闭"等跨项目稳定的部分）。

**实证（2026-09-18 成型作业日报 winForward）**：明细查看类弹窗按本规范第四节配成 `fa-paper-plane + Modal=true + 不设 UI`（动作类风格），被用户指出"弹窗风格不一致"——Molding 明细窗（winDetail 族）实际惯例是 `fa fa-file-text + Modal=false + UI="Default" + 1500×500`（MoldCheckStockQuery/MoldExistSemiRealTimeStock 两个明细窗完全一致）。按项目惯例改回后通过。**颜色（标题栏色）两类规范都不管——统一由皮肤 extExtra.css 驱动、页面零颜色代码，见 [[extnet-dynamic-panel-and-popup-pitfalls]] 第三节。**

## 二、核心结论：两类弹窗千万别混用

项目里弹窗分两类，风格**完全不同**，混用就是"没对齐"的根源：

| 维度 | McUI Crud 框架弹窗（winAdd/winUpdate） | 业务弹窗（绝大多数，98个里占86个） |
|---|---|---|
| Window 是否设 `UI` | **设**（winAdd=Info, winUpdate=Primary） | **不设**（仅 12/98 设 UI，且基本都是框架弹窗） |
| 按钮文案 | "确定 / **取消**" | "确定 / **关闭**" |
| 确定按钮是否设 `UI` | 设（Info/Primary） | **不设**（74个确定按钮里只有14个设UI，全是框架的） |
| `Closable` | `false`（框架弹窗不让关） | `true` |
| 典型场景 | McUI Crud 页的新增/修改表单 | 选择行、查询、动作确认、明细查看等 |

> **判断依据**：弹窗是写在 `McUI\Crud.aspx` 框架模板里 → 走框架风格；写在业务 `.aspx` 里 → 走业务弹窗风格。新做业务功能弹窗一律按"业务弹窗"风格。
> ⚠️ 个别项目（如 Molding 明细窗）业务弹窗也有 `UI="Default"` 惯例——Default 即无观感变化，同页/同项目照抄即可，别当成冲突。

## 三、Window 标配属性（98 个样本统计）

| 属性 | 出现率 | 说明 |
|---|---|---|
| `Hidden="true"` | 100% | 必设，弹窗默认隐藏 |
| `Modal="true"` | 98% | 必设，模态遮罩（**Semi 统计**；Molding 明细窗族反例 Modal=false，见一节） |
| `IconCls="fa fa-..."` | 89% | 用 FontAwesome 图标，**不用 `Icon` 枚举** |
| `Resizable="true"` | 81% | 惯例设 true |
| `Closable="true"` | 76% | 业务弹窗用 true（框架弹窗才用 false） |
| `Layout="FitLayout"` | 71% | 绝大多数弹窗 |
| `Layout="BorderLayout"` | 14% | 内部要 North查询区+Center表格 时用 |
| `Title="<%$Resources:Semi,xxx %>"` | 几乎全部 | 走资源键；个别老页面硬编码中文（同页一致即可） |
| `Width` / `Height` | 业务弹窗必设 | McUI 框架级 winDetail 例外不设（运行时定） |

业务弹窗 Window 头标准写法（7件套）：

```aspx
<ext:Window ID="winXxx" runat="server" IconCls="fa fa-paper-plane" Closable="true" Title="<%$Resources:Semi,标题 %>"
    Width="860" Height="560" Resizable="true" Hidden="true" Modal="true" Layout="FitLayout">
```

> **不要在业务弹窗的 Window 上设 `UI` 属性**——设了会让标题栏变色，和平台其他业务弹窗不一致。（Molding 明细窗 `UI="Default"` 不在此列，见一节备注。）
> **不要给弹窗标题图标加 `fabtn`**——那是工具栏按钮的样式类，弹窗标题图标裸 `fa fa-xxx`。

## 四、IconCls 图标惯例（按业务语义选）

| 图标 | 用途 | 出现次数 |
|---|---|---|
| `fa fa-paper-plane` | **选择 / 查询 / 动作类弹窗**（最通用，做新弹窗默认选它） | 43 |
| `fa fa-upload` | Excel 导入弹窗 | 13 |
| `fa fa-lock` | 锁定/解锁弹窗 | 10 |
| `fa fa-pencil-square` | 修改表单（McUI 风格） | 6 |
| `fa fa-plus-square` | 新增表单（McUI 风格） | 4 |
| `fa fa-file-text` | **明细查看类弹窗**（Molding winDetail 族惯例，Semi 统计外补录） | — |

> 记忆口诀：**"选择/动作类弹窗 = fa-paper-plane；明细查看 = fa-file-text"**。锁定类才用 fa-lock。

## 五、按钮标准写法

### 确定按钮（业务弹窗不设 UI）

```aspx
<ext:Button ID="btnXxxOK" runat="server" Text="<%$Resources:Semi,确定 %>" IconCls="fa fa-check-circle fabtn">
    <Listeners><Click Fn="xxxClick" /></Listeners>
</ext:Button>
```

- `IconCls="fa fa-check-circle fabtn"` 是 **100% 标配**
- **不设 `UI`**（业务页惯例；只有 McUI Crud 框架才设 Info/Primary）
- 依赖表单校验时加 `Disabled="true"`，配合 FormPanel 的 `<ValidityChange Handler="#{btnXxxOK}.setDisabled(!valid);" />` 联动解禁

### 关闭按钮（唯一稳定设 UI=Danger 的地方）

```aspx
<ext:Button ID="btnXxxClose" runat="server" Text="<%$Resources:Semi,关闭 %>" IconCls="fa fa-times-circle fabtn" UI="Danger">
    <Listeners><Click Handler="#{winXxx}.close();" /></Listeners>
</ext:Button>
```

- 文案用 **"关闭"**（业务页惯例）；**"取消"只用在 McUI Crud 框架弹窗**
- 有表单时 Handler 先 reset 再 close：`#{formPanel}.getForm().reset();#{winXxx}.close();`

## 六、GridPanel 弹窗标准结构（选择行 + 确定/关闭）

这是业务里最高频的弹窗形态。标准结构 = `FitLayout Window` → `Container(BorderLayout)` → `North(可选信息/查询区) + Center(GridPanel)`：

```aspx
<ext:Window ID="winXxx" runat="server" IconCls="fa fa-paper-plane" Closable="true" Title="<%$Resources:Semi,标题 %>"
    Width="860" Height="560" Resizable="true" Hidden="true" Modal="true" Layout="FitLayout">
    <Items>
        <ext:Container runat="server" Layout="BorderLayout">
            <Items>
                <!-- 可选：North 信息/查询区 -->
                <ext:Panel ID="pnlHeader" runat="server" Region="North" Header="false" Layout="HBoxLayout" Marginspec="5 5 5 5" Height="32">
                    <Items>
                        <ext:TextField ID="txtInfo" runat="server" FieldLabel="信息" ReadOnly="true" LabelAlign="Right" />
                    </Items>
                </ext:Panel>
                <!-- Center 表格 -->
                <ext:GridPanel ID="gpXxx" runat="server" Region="Center" StoreID="storeXxx" Cls="border-top" Scrollable="Both">
                    <ColumnModel>
                        <Columns>
                            <ext:RowNumbererColumn runat="server" Width="50" />
                            <ext:Column runat="server" Text="列名" DataIndex="FIELD" Flex="1" />
                        </Columns>
                    </ColumnModel>
                    <View>
                        <ext:GridView runat="server" EnableTextSelection="true" />
                    </View>
                    <SelectionModel>
                        <ext:CheckboxSelectionModel Mode="Multi" AllowDeselect="true" />
                    </SelectionModel>
                </ext:GridPanel>
            </Items>
        </ext:Container>
    </Items>
    <Buttons>
        <ext:Button ID="btnXxxOK" runat="server" Text="确定" IconCls="fa fa-check-circle fabtn">
            <Listeners><Click Fn="xxxSaveClick" /></Listeners>
        </ext:Button>
        <ext:Button ID="btnXxxClose" runat="server" Text="关闭" IconCls="fa fa-times-circle fabtn" UI="Danger">
            <Listeners><Click Handler="App.winXxx.close();" /></Listeners>
        </ext:Button>
    </Buttons>
</ext:Window>
```

GridPanel 标配子元素：
- 列首 `<ext:RowNumbererColumn>`（行号列）
- `<View><ext:GridView EnableTextSelection="true" /></View>`（支持选中复制单元格）
- 多选行用 `<ext:CheckboxSelectionModel Mode="Multi">`（列头自带全选/反选）
- 数据量大时加 `<BottomBar><ext:PagingToolbar>`（复杂版内嵌"每页条数 ComboBox + ProgressBarPager 插件"）
- 行内操作用 `<ext:ImageCommandColumn>` + `<ext:ImageCommand IconCls="fa fa-check-circle color-primary" CommandName="Select">`（行内"确认"按钮，替代底部确定）

## 七、做新弹窗的对齐检查清单

每次新增/修改弹窗，过一遍这个清单（踩过坑的项）：

- [ ] **有没有先统计目标项目的同类弹窗？**（一节：项目内同类惯例 > 本规范）
- [ ] Window 上是否**误设了** `UI`？（业务弹窗应去掉，只有 McUI Crud 框架弹窗才设；项目内有 `UI="Default"` 惯例的照抄）
- [ ] `IconCls` 是否按业务语义选对？（选择/动作类用 `fa-paper-plane`、明细查看用 `fa-file-text`，且不带 `fabtn`）
- [ ] `Modal` 是否与项目内同类窗一致？（Semi≈全 true；Molding 明细窗族=false）
- [ ] `Layout` 是否用了 `FitLayout`？（不要用 VBoxLayout/HBoxLayout 撑弹窗）
- [ ] 内部结构是否 `Container(BorderLayout) + North + Center(GridPanel)`？
- [ ] 确定按钮是否**误设了** `UI`？（业务弹窗应去掉，只有框架才设 Info/Primary）
- [ ] 按钮文案是否"**确定 / 关闭**"？（不要写"取消"，那是框架弹窗的词）
- [ ] 关闭按钮是否设了 `UI="Danger"`？
- [ ] GridPanel 是否有 `RowNumbererColumn` + `View(EnableTextSelection)` + `Cls="border-top"`？
- [ ] `Title` 是否走 `<%$Resources:Semi,xxx %>` 资源键？（同页老弹窗硬编码中文时，同页一致即可）
- [ ] 页面里是否写了任何颜色代码？（应为零——颜色统一交给皮肤 extExtra.css）

## 八、标准样本位置（抄就抄这些）

**McUI 框架标准（平台基线）**：
- `P.Semi\Wongoing.Semi.WebSite\McUI\Crud.aspx` — winAdd(行275, Info) / winUpdate(行316, Primary)
- `P.Semi\Wongoing.Semi.WebSite\McUI\Report.aspx` — winDetail(行248，GridPanel 明细弹窗基线)
- `P.Semi\Wongoing.Semi.WebSite\McUI\ReportBill.aspx` — winDetail(行126)

**业务弹窗样本（做新功能直接抄）**：
- `Plugins\Semi\ProductPlan\SemiPlan.aspx` — `WindowAddmaterial`(行1697，选择行+GridPanel+分页，最全)、`WinCheckDeleteMult`(行2131，CheckboxGroup+确定/关闭)
- `Plugins\Semi\Technology\SemiEquipByMaterParam.aspx` — `WinBindEquip`(行764，表单+确定/关闭按钮标准写法)、`WinBindMaterial`(行848)
- `Plugins\Semi\Technology\SemiCPKReport.aspx` — `WinSelect`(行1470)、`WinQueryPlan`(行1515)

**Molding 明细查看类弹窗样本（Molding 项目内对齐基准）**：
- `Plugins\Molding\Report\MoldCheckStockQuery.aspx` — `winDetail`（fa-file-text + Modal=false + UI=Default + 1500×500）
- `Plugins\Molding\Report\MoldExistSemiRealTimeStock.aspx` — `winDetail`（同款 1300×400）
- `Plugins\Molding\Report\MoldProductionTrace.aspx` — `winForward`（正向追溯明细窗，2026-09-18 误配返修后的对齐实证）

> 抄法：做"选择行+GridPanel+确定/关闭"弹窗 → 抄 `SemiPlan.aspx` 的 `WindowAddmaterial`（Window头+GridPanel）+ `SemiEquipByMaterParam.aspx` 的 `WinBindEquip`（Buttons）；做 Molding 明细查看弹窗 → 抄 `MoldCheckStockQuery.aspx` 的 `winDetail`。

## 九、关联文档

| 文档 | 关系 |
|------|------|
| [[extnet-window-guide]] | Window 基础用法（显示/隐藏/Modal/Loader/Toast），本文是其"项目风格约束"的补充 |
| [[extnet-dynamic-panel-and-popup-pitfalls]] | 弹窗颜色跟随皮肤正解 + "只改颜色不动格式"教训（本文一节/七节颜色条目的依据） |
| [[extnet-page-skeleton]] | 页面骨架，含简略的 Window 弹窗模式（注意其 UI=Primary 示例仅适用 McUI Crud 框架，业务弹窗不设 UI） |
| [[button-permission]] | 按钮权限（PageAction），弹窗内确定/关闭按钮不纳入权限，跟随父按钮 |
| [[molding-plan-trace-report]] | winForward 误配返修实证（一节案例出处） |
