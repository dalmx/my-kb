---
category: 技术-.NET
module: Ext.NET
status: active
tags:
- Ext.NET
- 页面样式
- extExtra.css
- ui-tab-bar
- fabtn
- 主题色
- 按钮图标
- fa图标
- Layout run failed
- VBoxLayout
- LayoutConfig
- 新增页面
- 样式对齐
- 页面骨架
- 踩坑
- 皮肤
- 清单
- 操作列权限
- 折叠
- FieldSet
- ShowHideQuery
- 限值设置
- 隐藏查询
- 弹窗
- BodyPadding
- BodyStyle
- 内边距
- 类型转换异常
- Panel
title: 新增 Ext.NET 页面样式对齐清单（踩坑实录）
updated: '2026-09-09'
---
# 新增 Ext.NET 页面样式对齐清单（踩坑实录）
> 2026-08-26 在 Molding 新增接头参数限值维护页（Technology/SpliceParamLimit.aspx）时连续踩中 6 个样式坑，用户三次反馈"风格对不上"。本文是逐一定位修复后的完整清单——**新增任何 Ext.NET 页面（报表/维护页/查询页）交付前必须逐条过一遍**。相关骨架见 [[extnet-page-skeleton]]。
>
> ⚠️ 范围说明：第一~四节是**所有页面通用标配**；第五节起标注"按需"的条目是**特定页面的特殊要求**，仅当用户明确提出对应需求时才做，不要机械套用。
## 一、交付前检查清单（按出现频率排序）
### 1. head 必须手动引用 extExtra.css（最高频坑！）
`resources/css/extExtra.css` **不是全局自动加载的**，每个页面自己在 head 里 `<link>` 引用。漏引则下述所有样式类（fabtn / color-xxx / border-xxx / ui-tab-bar）全部失效，页面灰扑扑毫无主题色。
```html
<!-- ✅ 正确：按页面目录深度写相对路径（Plugins/<X>/<子目录>/ 下三级回退） -->
<link href="../../../resources/css/extExtra.css" rel="stylesheet" />
<!-- ❌ 错误：纯 html 标签里 ~/ 不会被 ASP.NET 解析，浏览器请求 /~/resources/... → 404 -->
<link rel="Stylesheet" type="text/css" href="~/resources/css/extExtra.css" />
```
注意 `<~/resources/...>` 写法在部分存量页面存在（如 BeltDrumSpliceCpk.aspx），**那是失效的**，别照抄。参照有效写法：BarcodeTraceLock.aspx / MoldingStockWarning.aspx。
### 2. TabPanel 必须挂 `Cls="ui-tab-bar" Border="false"`
项目页签条的主题色（青绿色 `#017F7E`）定义在 extExtra.css 的 `.ui-tab-bar .x-tab-bar` 里，不挂类就是 Ext 默认灰白条，观感立刻对不上。
```html
<ext:TabPanel ID="tabXxx" runat="server" Region="Center" Cls="ui-tab-bar" Border="false">
```
参照：EquipAssistArt.aspx、MoldStockQueryForUnsulfided.aspx。
### 3. 按钮一律用 fa 图标类，不用 Ext 内置 Icon 枚举
统计全站 60+ 处得出的标准映射（IconCls 属性）：
| 功能 | 写法 |
|------|------|
| 查询 | `IconCls="fa fa-search fabtn color-info"` |
| 新增 | `IconCls="fa fa-plus fabtn color-primary"` |
| 修改 | `IconCls="fa fa-pencil color-info"` |
| 删除 | `IconCls="fa fa-remove fabtn"` |
| 导出 | `IconCls="fa fa-file-excel-o fabtn color-success"` |
| 导入/上传 | `IconCls="fa fa-upload fabtn color-primary"` |
| 弹窗确定/保存 | `IconCls="fa fa-check-circle fabtn"` |
| 弹窗取消/关闭 | `IconCls="fa fa-times-circle fabtn"` |
| 隐藏查询区箭头 | `IconCls="fa fa-angle-double-up fabtn color-inverse"` |
❌ 不要写 `Icon="Add"` / `Icon="Pencil"` / `Icon="Disk"` / `Icon="Cancel"` 等 Ext 枚举（存量老页有，新页不要用）。危险按钮可加 `UI="Danger"`（全站 66 处）。
### 4. VBoxLayout 布局配置必须用子元素写法（否则 Layout run failed）
```html
<!-- ✅ 正确 -->
<ext:Panel runat="server" Region="Center" Layout="VBoxLayout">
    <LayoutConfig>
        <ext:VBoxLayoutConfig Align="Stretch" />
    </LayoutConfig>
<!-- ❌ 错误：连字符属性写法在 Ext.NET 4 静默失效，VBoxLayout 无 Align=Stretch，
      子面板宽度塌缩 → 控制台报 [E] Layout run failed -->
<ext:Panel runat="server" Layout="VBoxLayout" LayoutConfig-Align="stretch">
```
HBoxLayout 同理（`<ext:HBoxLayoutConfig Align="Stretch" />`）。参照 [[extnet-page-skeleton]] 组合模式②③。
### 5. North 查询区标准骨架
```html
<ext:Panel ID="pnlNorth" runat="server" Region="North" Header="false" Cls="border-bottom">
    <TopBar>  <!-- 工具栏：按钮组 + ToolbarSeparator 分隔 + 尾部 ToolbarFill -->
        <ext:Toolbar runat="server">…按钮…<ext:ToolbarFill /></ext:Toolbar>
    </TopBar>
    <Items>
        <ext:FormPanel runat="server" Layout="ColumnLayout" Cls="border-top" Header="false">
            <!-- Container(FormLayout, ColumnWidth=".25") × 4，字段 LabelAlign="Right" -->
        </ext:FormPanel>
    </Items>
</ext:Panel>
```
要点：`Header="false"` + `Cls="border-bottom"`（North 外框线）、FormPanel `Cls="border-top"`（查询区上边线）、查询字段放 **FormPanel 不放工具栏**（放工具栏观感立刻出戏）。边框色 `#d0d0d0` 由这两个类提供。
### 6. 其它标配
- **GridPanel**：`ColumnLines="true" RowLines="true"`；`<ext:GridView EnableTextSelection="true">`
- **分页条**：BottomBar PagingToolbar + 每页条数下拉（`Editable="true" ForceSelection="false"`，50/100/200/500）+ `<ext:ProgressBarPager>`；客户端分页查询回调里 `loadData` 后要 `loadPage(1)`；刷新按钮接管 `AfterRender Handler="var r=this.child('#refresh'); if(r){r.setHandler(查询函数);}"`（见 [[extnet-pagination-guide]]）
- **ComboBox**：查询类下拉配 Clear 触发器（`<Triggers><ext:FieldTrigger Icon="Clear" /></Triggers>` + `TriggerClick` 清空），不放"全部"选项
- **Window**：没有 `DefaultButton` 属性（FormPanel 才有），别乱挂
- **JS 引用控件**：Ext.NET 4 里一律 `App.<ID>`（裸 ID 全局变量不可用）；Listener 的 Handler 里可用 `#{ID}` 简写
- **窗体图标**：编辑窗 `IconCls="fa fa-pencil"`、导入窗 `IconCls="fa fa-upload"`
## 二、方法论：为什么连续踩坑
1. **只对齐"功能"没对齐"骨架"**——第一轮只换了图标+加分页条，布局仍是自创的"上下两块各带工具栏"，用户看一眼就说对不上。正确做法：先确定目标骨架（North 查询区+Center 表格/页签），再往里填内容。
2. **样式类是全局 css 手动引用的**——项目没有母版页（无 .master），每页自带 head，css 引用、主题类全靠页面自己写全。新建页面最容易漏。
3. **对齐前先统计**——按钮图标映射是 grep 全站 IconCls 出现频次统计出来的（47 处 fa-search、22 处 fa-file-excel-o…），比看单个页面可靠。
4. **用户说"参考某页"时先问清参考的是哪种控件**——CPK 限值区折叠连改三次（Panel 标题头→工具栏按钮→FieldSet），用户贴图后才发现参照物是批次追溯页的**可折叠 FieldSet 分组框**，第一次就该贴图/指着具体控件问。
## 三、关联
- 页面骨架与布局组合模式：[[extnet-page-skeleton]]
- 查询表单复合控件布局：[[extnet-query-form-compound-control-layout]]
- 维护页面 CRUD 分层套路：[[mes-crud-maintain-page-guide]]
- 客户端分页：[[extnet-pagination-guide]]（mes-common）
- 按钮与操作列权限：[[button-permission]]
- 本次踩坑页面：Molding `Plugins/Molding/Technology/SpliceParamLimit.aspx`（North+TabPanel 双页签+四弹窗，可作参考实现）
## 四、补充：head 引用资源全清单（2026-08-26 第二次踩坑后补）
页面 head 的资源引用是逐页手动的，**漏一项就运行时报错**。新建页面按需自查：
| 引用 | 作用 | 漏了的现象 |
|------|------|-----------|
| `<link href="<相对路径>/resources/css/extExtra.css" rel="stylesheet" />` | 主题样式（fabtn/color-xxx/border/ui-tab-bar） | 全页无主题色 |
| `<script src="<相对路径>/resources/js/jquery-1.7.1.js"></script>` | jQuery 1.7.1（导出触发 `$('#btnXxxSubmit').click()` 等用） | 导出报 `$ is not defined` |
> jQuery 只在页面 JS 用到 `$` 时才需要（CPK 页导出用它触发隐藏 asp:Button）；不用 jQuery 的触发可改 `Ext.getDom('btnXxxSubmit').click()`（Ext 内置、零依赖）。相对路径按页面在 `Plugins/<X>/<子目录>/` 下三级回退 `../../../`。
## 五、按需功能：操作列与导入窗（仅用户明确要求时做，非通用标配）
> 本节条目来自 Molding SpliceParamLimit 的**特定需求**，新建页面默认不做，用户提出下列需求时按此实现。
### 5.1 Grid 行操作列（ImageCommandColumn）——用户要求行内修改/删除时
项目操作列统一用 fa 图标 + 文字命令 + ToolTip（参照 EquipAssistArt / EquipAssistArtByMater）：
```xml
<ext:ImageCommandColumn runat="server" Text="操作" Align="Center" Width="160">
    <Commands>
        <ext:ImageCommand IconCls="fa fa-pencil color-info" CommandName="Edit" Text="编辑">
            <ToolTip Text="修改本条数据" />
        </ext:ImageCommand>
        <ext:ImageCommand IconCls="fa fa-trash color-danger" CommandName="Delete" Text="删除">
            <ToolTip Text="删除本条数据" />
        </ext:ImageCommand>
    </Commands>
    <Listeners>
        <Command Handler="onXxxRowCmd(command, record);" />
    </Listeners>
</ext:ImageCommandColumn>
```
- ❌ 不用 Ext 内置 `Icon="Pencil"`/`Icon="Delete"` 枚举
- 两个命令（图标+文字）并排需 **Width≈160**，110 会换行
- ✅ **操作列命令同样做权限控制**（见 [[button-permission]]）：权限类加 `编辑 = new PageAction() { ActionName = "Edit" }`、`删除 = new PageAction() { ActionName = "Delete" }`——**ActionName 对应命令的 CommandName**（不是按钮 ID）；权限属性名与命令 `Text` 完全一致（编辑/删除）。框架按权限自动隐藏命令，前端无需 JS 校验。多个 Grid 的同名命令（如两个页签都有 Edit）共用同一个权限点。
- 若以行操作列+双击为修改入口，工具栏可不放"修改/删除"按钮（保留多选批量删除时才留删除按钮）
- 按数据状态动态隐藏命令用 `PrepareCommand`（button-permission 有完整示例）
### 5.2 导入窗（FileUploadField）——用户要求 Excel 导入时
1. **文件必选才能点确定**：`<ext:FileUploadField AllowBlank="false" />` + 确定按钮 `Disabled="true"` + FormPanel `<Listeners><ValidityChange Handler="#{btnXxxSave}.setDisabled(!valid);" /></Listeners>`（与编辑窗保存按钮同款联动，见 [[extnet-form-validation-complete]]）
2. **导入成功后 Success 脚本三件套**：`Success="App.winXxx.hide(); App.fpXxx.getForm().reset(); 刷新函数();"` —— 关窗 + 重置文件框 + 刷新 Grid。**DirectEvents 的 Click 节点改动时注意别把 Success 属性弄丢**（丢失后导入完无任何反馈）
3. 导入中 mask：`<EventMask ShowMask="true" Msg="正在导入..." />`，Click 加 `Timeout="180000"`
4. 报错带 Excel 行号：`errors.Add("第" + (i + 2) + "行：原因")`（DataTable 索引+2，第1行是表头），一次列出前 10 条
5. 弹窗内不放说明文字 Container——`<Items>` 集合里的孤立文字会报"ItemsCollection 内不允许包含文字内容"
### 5.3 下拉联动顺序约束（先细类后机台）——用户明确要求填写顺序时（特殊要求）
这是 SpliceParamLimit 页面的特定需求，**不是通用标配**；默认下拉全部可选，不做顺序限制。要求按序填写时：下游下拉初始 `Disabled="true"`，上游 Select 后 `App.xxx.setDisabled(false)` 解禁（服务端控件禁用不要用 `SetDisabled(bool)`——protected 不可访问，改前端 JS）。参照 GetEquipByMinorType DirectMethod + 双击回填回调里启用/设值的时序处理。
---
## 六、按需功能：多页签页面的查询区联动（用户要求"不同页签不同查询条件"时）
Molding SpliceParamLimit 双页签（机台参数 / 生胎重量）实证，2026-08-26。
### 6.1 结构与联动
```text
North 查询区放两组条件 Container（同层级并列）：
  grpParamQ（细类/参数/机台三字段，默认显示）
  grpMaterialQ（制造编码一字段，Hidden="true"）
TabPanel 加 <Listeners><TabChange Fn="onTabChange" /></Listeners>：
  onTabChange = 按 activeDomain() 切换两组 setVisible
查询按钮只刷当前页签：btnQueryFn = activeDomain()==='P' ? 查P : 查M
（不要一次刷两个页签——条件混排+双刷会让用户觉得"条件不生效"）
```
外层容器用 `ext:Container`（AutoLayout）装两个 ColumnLayout 子组，`Cls="border-top"` 挂外层保持查询区上边线。
### 6.2 高频疏漏：联动下拉 ≠ 参与查询（实证坑）
细类下拉做了"联动参数列表+过滤机台列表"，但**查询参数没带它**——用户选了细类查询结果不变，报"查询不生效"。**联动只改了候选列表，过滤必须把值传进 SQL where**。改一处查询条件要同步**三处**：
1. 前端查询函数传参（`App.direct.QueryXxx(…, minorType, …)`）
2. 后台 where 字典 + **Session 缓存的查询条件**（导出复用，漏了导出就不过滤）
3. BusinessMapper 的 `<isNotNull>` 条件（无对应列时走 join 表字段过滤，如细类经 `SBE_EQUIP.MINOR_TYPE_ID`）
### 6.3 表里没有的维度字段怎么办
限值表无细类列 → 利用列表查询里**已有的 join**（SBE_EQUIP）过滤 `T3.MINOR_TYPE_ID`，不必加列不必改表。
---
## 七、按需功能：输入区折叠（用户要求"可折叠"时）——FieldSet 定稿
> CPK 页限值输入区折叠**三次修正后的最终模式**：① Panel Collapsible（灰标题头）被批"太丑"；② 工具栏按钮（右上角撞主框架保留位→挪按钮组）被批"不是我要的形式，要加在输入框的边框上"；③ **可折叠 FieldSet（批次追溯页"硫化信息"分组框同款）→ 用户贴图认可**。教训：用户说"参考某页"时，先确认参照的具体控件再动手。
### 7.1 ❌ 不要用 Panel Collapsible 折叠输入区
`<ext:Panel Collapsible="true" Collapsed="true" Title="xxx">` 渲染的是一条**灰色标题栏**（重、丑，收起后标题栏仍占一行）。Panel 的折叠适合 BorderLayout 的 West/East 大区域（如"检验数据"侧栏），不适合表单输入区。
### 7.2 ✅ 最终模式：可折叠 FieldSet（仿批次追溯信息分组框）
参照 `Batch/P.Batch/.../Plugins/Batch/BatchTracing/BatchTracing.aspx` 的"硫化信息/外观信息/修理记录/UFDB信息"FieldSet——细边框分组框、**标题骑在边框线上**（legend）、左侧折叠箭头：
```xml
<ext:FieldSet runat="server" ID="fsLimit" Title="限值设置（选参数/输编码后自动带出，可手改）"
    Collapsible="true" Collapsed="true" Layout="ColumnLayout" MarginSpec="5 5 5 5">
    <Listeners>
        <Collapse Fn="onWestToggle" />
        <Expand Fn="onWestToggle" />
    </Listeners>
    <Items>
        <!-- Container(FormLayout, ColumnWidth=".25") × N：4 个一行，第 5 个自动换行 -->
        <ext:Container runat="server" Layout="FormLayout" ColumnWidth=".25">
            <Items>
                <ext:NumberField ID="txtUSL" runat="server" FieldLabel="规格上限" LabelAlign="Right" LabelWidth="55" />
            </Items>
        </ext:Container>
        …
    </Items>
</ext:FieldSet>
```
要点：
1. **默认收起** `Collapsed="true"`，收起后只剩一条带箭头的 legend 线（约 25px），比隐藏方案多一行但功能自解释。
2. 放在 North 的 Items 里（查询行 FormPanel 之后）；**North 不写死 Height**、查询 FormPanel 加 `AutoHeight="true"`，展开/收起北区高度自适应、Center 随之伸缩。
3. `MarginSpec="5 5 5 5"` 让分组框与查询行留白。
4. 折叠/展开有 echarts 图表的页面挂 `<Collapse>/<Expand>` → `Ext.defer(resizeAllCharts, 100)` 重绘（等布局完成）。
5. 字段直接用 Container×N 排布（4+1 自动换行），**不要再套 FormPanel 行**。
6. 无需任何自定义 JS/CSS——Ext.NET 原生组件，Triton 主题渲染，与参照页完全同款。
### 7.3 ⚠️ 被否掉的两条路（不要再走）
- **工具栏按钮切换 setVisible**：无论放右上角还是按钮组内，用户都不认——折叠开关要贴着输入区本身（"加在输入框的边框上"），不是工具栏里的一个按钮。
- **自定义 HTML 骑线小钮**（绝对定位 div 骑在查询区下边框上）：方向对了但多余——FieldSet 原生就是这个形态，且自定义定位在 Ext 布局里排查成本高（实测出现过 pointer probe 无点击点问题）。
- 附带位置常识：**工具栏最右侧（ToolbarFill 后）是保留位**——主框架"隐藏工具栏"按钮在页面右上，且全站十几页的右上角都是 ShowHideQuery"隐藏查询区"按钮（折叠查询区本身时才用这个位，见 default.js）。
### 7.4 有图表的页面联动重绘
折叠/展开改变 Center 尺寸，echarts 需要 `Ext.defer(resizeAllCharts, 100)` 后重绘（等 BorderLayout 完成布局）；与 West 面板折叠的 onWestToggle 处理一致，可复用同一函数（FieldSet 的 Collapse/Expand 与 West 面板共用同一 Fn）。
参照实现：Molding `Plugins/Molding/Report/BeltDrumSpliceCpk.aspx`（限值设置 FieldSet，默认收起）；`Batch/.../BatchTracing.aspx`（信息分组 FieldSet 鼻祖）。
---
## 八、弹窗标题栏颜色必须与项目主题色一致（2026-08 Mould 三轮误判后补）
新建 `ext:Window` 的标题栏默认是 Ext **蓝色**，与页面 Panel/Grid 标题栏的项目主题色（`extExtra.css` 全局 `.x-panel-header { background-color:#017F7E; }`）不一致——`.x-window-header-default` 的主题色规则在皮肤里被注释，仅 `SearchBox` 系弹窗吃到专项规则。
**交付前检查**：打开新建弹窗，标题栏颜色是否与同页 Panel 标题栏同色（青绿 #017F7E）。不一致时在页面 head 加同构规则：
```css
#<窗口ID>_header { border-color:#017F7E; background-color:#017F7E; }
#<窗口ID>_header .x-window-header-title-text,
#<窗口ID>_header .x-window-header-title-text-default { color:#ffffff; }
```
完整排障过程与"纯 HTML 注入替代动态用户控件"等关联坑见 `extnet-dynamic-panel-and-popup-pitfalls.md`。
---
> **⚠️ 2026-08-28 重要更正**：本节原结论（"弹窗标题栏应刷 #017F7E"）已被实践推翻——**Mould 服务器上项目弹窗就是 Ext 默认蓝色**，本地源码 extExtra.css 的 #017F7E 规则与服务器部署版本不同步（本地疑为未发布改版皮肤）。**弹窗颜色对齐以部署服务器的实际观感为准：服务器存量弹窗是默认蓝时，新弹窗不设 UI、不加颜色 CSS 保持默认蓝即为正确对齐。** 先在服务器打开参照页面确认观感再动手，不要按本地皮肤文件推断。完整误判实录见 `extnet-dynamic-panel-and-popup-pitfalls.md` 第三节。
---
## 九、视觉观感两坑（2026-09-07 CurdCottonColor 实测，代码级审查发现不了）
### 9.1 列少的 Grid 别给短数据列 Flex=1
数据值短的列（如物料名称全是 GX110 类 5 字符短码）给 `Flex="1"` 会吞掉**全部**剩余宽度，该列占半屏、大片留白。列少的表格用**固定 Width**（对齐同类参考页取值，如 CurdMaterial 物料名称 Width="240"），列总宽小于表格宽时右侧自然留白是项目常态，比强行拉某列美观。`Flex + MinWidth` 组合对短数据列无效（Flex 依然吞满剩余）。
### 9.2 弹窗表单必须 BodyPadding≥10 + anchor 95%
`BodyPadding="5"` 且字段默认 anchor=100% 时，输入框顶到弹窗边缘，用户观感"内容紧贴边框没有边距"。标准写法（参考 CurdMaterial winAdd / SemiEquipByMaterParam WinBindEquip）：
```xml
<ext:FormPanel ID="pnlEdit" runat="server" BodyPadding="10">
    <Defaults>
        <ext:Parameter Name="anchor" Value="95%" Mode="Value" />
        <ext:Parameter Name="msgTarget" Value="side" Mode="Value" />
    </Defaults>
```
### 9.3 元教训：代码级审查的盲区
列宽观感、表单间距这类**纯视觉比例**问题，静态代码审查（无站点无截图）发现不了——交付新页面后应尽快拿真实截图复核一轮（用户截图或浏览器走查），尤其列少的表格和含表单的弹窗。
---
## 十、实证：`~/` 形式 css 引用导致整页裸主题色（2026-09-08 Curing）
Curing TemperPressureTrend 页加弹窗后用户反馈"弹窗颜色与系统不一致"，两轮排查后根因不在弹窗属性，而是页面 head：
```html
<link rel="Stylesheet" type="text/css" href="~/resources/css/extExtra.css" />
```
**`~/` 只有在 runat="server" 控件里才被 ASP.NET 解析**——纯 html `<link>` 标签原样发给浏览器，按相对路径请求 `.../ReportCenter/~/resources/css/extExtra.css` → 404 → **extExtra.css 从未加载**。症状隐蔽性：页面主体（图表/表格）看不出异常（ECharts 不吃该 css、Grid 差异细微），**新增弹窗后原生主题色暴露**才被发现——该页 css 已 404 存活多日。修复：改 `../../../resources/css/extExtra.css` 相对路径（与全项目一致）。
**排查方法论**：控件样式"不对"先查 css 是否加载（浏览器 F12 Network 看 404），再对齐控件属性——顺序反了会像我一样先白改一轮 Window 属性。同页顺带清了另两处旧账：导出按钮 `Icon="PageWhiteExcel"` → `IconCls="fa fa-file-excel-o fabtn color-success"`（项目 16 处主流）、pnlNorth 补 `Cls="border-bottom"`。
---
## 十一、BodyPadding 是整数类型，CSS 四值内边距必须走 BodyStyle（2026-09-09 MoldProductionTrace 实测）
**现象**：给 `ext:Panel` 写 `BodyPadding="10 0 0 10"`（想要上左不对称内边距），页面直接抛异常：
> 无法从其"BodyPadding"属性的字符串表示形式"10 0 0 10"创建 System.Nullable<int>（即 int?）类型的对象。
**根因**：Ext.NET 的 `Panel.BodyPadding` 是 `int?`，只接受**单个像素整数**（如 `BodyPadding="10"`，四边同值），不是 CSS padding 简写字符串。
**解法**：不对称/带单位的内边距用 `BodyStyle`（项目成熟用法，DeptInfo/MainFrame/SetPageMenu 等大量在用）：
```xml
<ext:Panel runat="server" Height="38" Border="false" Cls="border-top" BodyStyle="padding:10px 0 0 10px">
```
四边同值才用 `BodyPadding="10"`（弹窗表单标准 ≥10，见 9.2 节）。
