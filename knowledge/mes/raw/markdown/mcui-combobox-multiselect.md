---
title: McUI 下拉框多选改造模式（MANY_TYRE_NO_INFOR 约定 + JS 重建多选）
category: 技术-.NET
module: McUI
tags: [McUI, 下拉框, 多选, ComboBox, MANY_TYRE_NO_INFOR, 多选下拉框, 机台多选, ReportPPTPlanAnalyse, 计划执行分析, multiSelect, pickerSelectionModel, _state隐藏域, IN查询, iBATIS字面替换, Report模板, 踩坑]
updated: 2026-09-02
status: active
---
# McUI 下拉框多选改造模式（MANY_TYRE_NO_INFOR 约定 + JS 重建多选）

> McUI 配置化页面的查询下拉框原生只支持单选。要做成多选：**字段改名挂 `MANY_TYRE_NO_INFOR` 前缀**（触发 Report/Crud 模板的服务端多值拆分）**+ JS 用 initialConfig 克隆重建 ComboBox 为多选 + 提交前把 `_state` 多值合并成单条目**，Mapper 条件改 `in ($..$)` 字面替换。2026-09-02 在 Mix `ReportPPTPlanAnalyse`（计划执行分析，机台多选）首例落地并浏览器实测通过（双机选择 G1+G2 查询两机数据同时返回、抓包确认提交值正确）。

## 一、原理：框架现成的多值拆分通道 + 两个拦路虎

`McUI_Report.GetPageResultData`（源码 `Main\P.Main\Wongoing.Main.WebSite\McUI\Report.aspx.cs`，编译进 `Wongoing.Main.Website.dll`，各子系统共用）在收集查询参数后有一段硬编码约定：

```csharp
string tyreInforKey = "MANY_TYRE_NO_INFOR";
foreach(var key in keys)   // 键名不区分大小写以前缀匹配
    if (key.ToLower().StartsWith(tyreInforKey.ToLower()))
        formParam[key] = getListValue(formParam[key].ToString());
```

`getListValue` 把值按 `, ， * # +` 分割，每段 `Trim().ToUpper()` 后包单引号拼成 `'A','B','C'`。**查询（GridPanelBindData）和导出（btnExportSubmit_Click）共用这条链路**，SqlPage 分页模式同样带这段。

但直接用会撞上两个拦路虎（Ext.NET 4.7.1 实测）：

1. **构造后设 `combo.multiSelect = true` 无效**——下拉列表（BoundList）的 SelectionModel 仍是 `SINGLE`，选第二个会把第一个顶掉。multiSelect 必须进控件的**初始配置**。
2. **多选值提交走 `_<字段>_state` 隐藏域 JSON**（形如 `[{"value":"G1","text":"G1 320母炼机","index":0},{...}]`），而框架 `PageData.getJsonParamFieldValue` 解析时**只取第一个条目就 break**（`PageData.cs:39-43`）——多条目会被截断成第一个值。

对应解法：① 用 `initialConfig` 克隆重建控件；② 包一层 `Ext.net.DirectEvent.request`，提交前把多值合并成单条目（value 用逗号拼接），服务端拆分正好接上。**全程不用改任何 DLL，纯配置三件套。**

## 二、改造清单（3 个文件，不动 DLL 不编译）

| # | 文件 | 改动 | 要点 |
|---|------|------|------|
| 1 | `<页面>.xml` | ParamField 的 FieldName 改为 `MANY_TYRE_NO_INFOR_<业务名>`；Captions 同步新增该字段名的标签（**原字段名的 Caption 若被表格列头引用必须保留**） | 下拉数据语句 id 随字段名变化 |
| 2 | `<页面>.Mapper.xml` | `GetComboBoxData@Select@<页面>@<新字段名>` 语句 id 改名；查询条件 `= #where.X#` 改 `in ($where.新字段名$)` | `$..$` 在 CDATA 内同样生效（同语句 `$OrderString$` 可证） |
| 3 | `<页面>.js`（新建） | `viewportAfterRender` 里：重建下拉为多选 + 挂提交前合并钩子 | 本页 JS 排在借用的共享 JS 之后加载以覆盖其 `viewportAfterRender` |

### 2.1 xml 写法（ReportPPTPlanAnalyse 实例）

```xml
<Captions>
  <!-- 原字段名 Caption 保留：表格列头 Equip_Code 还在用它 -->
  <Caption Name="Equip_Code" Value="机台" ResourceKey="Mix.机台"></Caption>
  <Caption Name="MANY_TYRE_NO_INFOR_EQUIP" Value="机台" ResourceKey="Mix.机台"></Caption>
</Captions>
<WebPage Title="计划执行分析">
  <JavaScripts>
    <JavaScript FileUrl="../Plugins/Mix/McUI/@McUI/ReportPmmPoOrder.js" />
    <!-- 排后面：覆盖借用 JS 的 viewportAfterRender（其引用的列在本页不存在会静默报错） -->
    <JavaScript FileUrl="../Plugins/Mix/McUI/@McUI/ReportPPTPlanAnalyse.js" />
  </JavaScripts>
</WebPage>
<Select>
  <ParamFields>
    <ParamField FieldName="MANY_TYRE_NO_INFOR_EQUIP" Type="ComboBox" Nullable="true"></ParamField>
  </ParamFields>
</Select>
```

### 2.2 Mapper 写法

```xml
<select id="GetComboBoxData@Select@ReportPPTPlanAnalyse@MANY_TYRE_NO_INFOR_EQUIP" parameterClass="int" resultClass="row">
  <![CDATA[select equip_code AS ssKey,Equip_name AS ssValue from Pmt_Equip where Equip_class<='02']]>
</select>
<!-- 主查询条件 -->
<isNotNull property="where.MANY_TYRE_NO_INFOR_EQUIP" prepend="AND">
  <![CDATA[Equip_code in ($where.MANY_TYRE_NO_INFOR_EQUIP$)]]>
</isNotNull>
```

### 2.3 JS 写法（实测可用版，直接抄）

```javascript
// 机台下拉重建为多选：multiSelect 必须进初始配置，构造后设置无效
var ui_s_MANY_TYRE_NO_INFOR_EQUIP_multiFix = function () {
    var old = App.ui_s_MANY_TYRE_NO_INFOR_EQUIP;
    if (!old || old.__multiRebuilt) return;
    var cont = old.ownerCt;
    if (!cont) return;
    var cfg = Ext.apply({}, old.initialConfig);
    cfg.multiSelect = true;
    var idx = cont.items.indexOf(old);
    cont.remove(old, true);
    var neu = cont.insert(idx, cfg);
    neu.__multiRebuilt = true;
}

// 提交前把 _state 多条目合并为单条目（框架 getJsonParamFieldValue 只取第一条）
var ui_s_MANY_TYRE_NO_INFOR_EQUIP_sync = function () {
    try {
        var cbb = App.ui_s_MANY_TYRE_NO_INFOR_EQUIP;
        if (!cbb) return;
        var stateEl = document.querySelector('input[name="_ui_s_MANY_TYRE_NO_INFOR_EQUIP_state"]');
        if (!stateEl) return;
        var vals = cbb.getValue();
        if (vals && !Ext.isArray(vals)) vals = [vals];
        if (vals && vals.length > 0) {
            stateEl.value = Ext.encode([{ value: vals.join(','), text: cbb.getRawValue(), index: 0 }]);
        } else {
            stateEl.value = '';
        }
    } catch (e) { }
}

var viewportAfterRender = function () {
    // 沿用借用 ReportPmmPoOrder.js 的既有行为：一次拉全量数据、去掉分页工具栏
    App.gridPanelMainStore.proxy.limitParam = '-1';
    App.gridPanelMainPageToolbar.removeAll();

    // 机台下拉重建为多选
    ui_s_MANY_TYRE_NO_INFOR_EQUIP_multiFix();

    // 所有 Ext.NET DirectEvent/DirectMethod 请求（查询/导出）提交前合并多选 _state
    if (Ext.net && Ext.net.DirectEvent && Ext.net.DirectEvent.request && !Ext.net.DirectEvent.request.__msPatched) {
        var orig = Ext.net.DirectEvent.request;
        Ext.net.DirectEvent.request = function () {
            ui_s_MANY_TYRE_NO_INFOR_EQUIP_sync();
            return orig.apply(this, arguments);
        };
        Ext.net.DirectEvent.request.__msPatched = true;
    }
}
```

**换字段时全局替换 `MANY_TYRE_NO_INFOR_EQUIP` 三处**（multiFix 的控件 id、sync 的 hidden 选择器、两个函数名可不动）。

## 三、实测验证过的关键机制

- **重建后 picker 选择模型为 SIMPLE**（点击即多选，无需按 Ctrl）；`getValue()` 返回值数组；显示文本逗号拼接（如"G1 320母炼机, G2 320母炼机"）。
- **抓包确认提交**：`_<字段>_state=[{"value":"G1,G2","text":"...","index":0}]`——合并后单条目，服务端 `getListValue` 拆成 `'G1','G2'` 进 `in (...)`；不选时 `_state` 置空串，服务端 `isNotNull/isNotEmpty` 跳过条件。
- **查询和导出共用链路**：DirectMethod（查询）和 DirectEvent（导出）都走 `Ext.net.DirectEvent.request`，包一层全覆盖。
- 框架生成的 ComboBox：`Nullable=true` 自带 Clear 触发器（`this.clearValue()`，多选模式正确清空）；查询/导出按钮点击无需额外处理。

## 四、死路备忘（试过不行，别再踩）

| 尝试 | 结果 |
|------|------|
| 构造后 `cbb.multiSelect = true`（含销毁重建 picker） | picker SelectionModel 仍 SINGLE，多选值被顶掉 |
| `cbb.picker.getSelectionModel().setMode('SIMPLE')` | 该版本 Ext.selection.Model 无 setMode 方法 |
| `cbb.listConfig = { multiSelect: true }` 后重建 picker | BoundList 构造期 applySelectionModel 报 null 崩溃 |
| `cbb.pickerSelectionModel = { type:..., mode:'SIMPLE' }`（配置对象） | combo.setValue 调 `pickerSelectionModel.deselectAll()` 直接崩——必须是实例；换新实例又在 bindStore 崩 |
| **initialConfig 克隆重建（本文方案）** | ✅ 全通过 |

## 五、坑与边界

1. **`getListValue` 会 `ToUpper()`**：数据库排序规则需大小写不敏感（中文库默认 `Chinese_PRC_CI_AS` 满足）。
2. **分隔符是 `, ， * # +` 五种**：候选值含这些字符会被错误拆分（机台/班组码不会）。
3. **配置缓存**：改 xml/js/Mapper 后须清 `UiHelper` 进程缓存（重启站点或 SysConfig.aspx 清缓存）。
4. **原字段名 Caption 别删**：表格列头仍按原列名查 Caption。
5. **URL 带参调用方失效**：字段改名后原来 URL 传 `<原字段名>=值` 的入口静默失效，改造前全解决方案搜页面名排查。
6. **Mix 的 McUI 框架 DLL 比 Main 当前源码旧**：`editable=false`（Main 新源码是 `Editable=true`）、无 ForceSelection——initialConfig 里看到什么就以什么为准，克隆时不要自己加戏。
7. **多值显示文本较长**会截断省略号（Ext 默认），查询区列宽按需调。
8. **验证日期范围**：默认 BeginTime=-1/EndTime=0 只查昨天~今天，没排产的机台查不出来是数据问题不是功能问题（验证时放宽日期或全选确认哪些机台有量）。

## 六、参考实现位置

| 文件 | 位置 |
|------|------|
| 页面配置 | `Mix\P.Mix\Wongoing.Mix.WebSite\Plugins\Mix\McUI\@McUI\ReportPPTPlanAnalyse.xml` |
| Mapper | 同目录 `ReportPPTPlanAnalyse.Mapper.xml` |
| 页面 JS | 同目录 `ReportPPTPlanAnalyse.js`（新建） |
| 框架拆分源码 | `Main\P.Main\Wongoing.Main.WebSite\McUI\Report.aspx.cs`（GetPageResultData / getListValue） |
| 框架取值截断 | `Main\Frame\Wongoing.McUI\ExtNet\PageData.cs`（getJsonParamFieldValue 只取第一条） |

## 七、关联文档

- [[extnet-combobox-multiselect]] —— 手写 aspx 页面的 ComboBox 多选改造（4 处联动），与本文档互为补充：**McUI 页走本文档，手写页走该文档**
- [[main-mcui-config-framework]] —— McUI 框架全景（控件类型、取值链路、限制）
- [[mcui-crud-page-extension-guide]] —— McUI 页面 JS 扩展通用指南（viewportAfterRender 等钩子）
