---
title: PageResult.ParameterObject 双包 where 坑（查询条件全部失效）——排查全过程与正解
category: 技术-.NET
module: 通用
factory: 通用
tags: [iBATIS, ParameterObject, PageResult, GetPageDataByReader, where, 查询条件失效, 筛选不生效, 分页, DirectMethod, OnReadData, Hidden中转, 踩坑, 耗时教训]
updated: 2026-08-29
status: active
---
# PageResult.ParameterObject 双包 where 坑（查询条件全部失效）——排查全过程与正解

> 症状：分页查询数据正常但筛选条件全部失效。根因（框架源码铁证）：GetPageDataByReader 内部已自动把 pageResult.ParameterObject 包进 "where" 键，C# 侧再手动包一层就变成 {where:{where:{...}}}，mapper 的 where.XXX 取到字典对象而非字符串值。正解：ParameterObject 直接传字典；附 Hidden 中转 + OnReadData 的生产级可靠组合与四轮无效排查的教训。

## 一、现象

GridPanel 分页查询页（PageProxy + DirectFn DirectMethod / OnReadData）：表格数据正常显示，但**查询条件全部失效**——SQL 日志里 WHERE 只有固定条件、动态条件一个没拼上、参数为空。输入筛选值点查询，结果集不变。

## 二、根因（框架源码铁证）

`BaseService.GetPageDataByReader` / `GetSqlPageData` 内部**自动**把 `pageResult.ParameterObject` 包进 `"where"` 键：

```csharp
// Main/Frame/Wongoing.DbAccess/BaseService.cs 第1097/1184行
param["where"] = pageResult.ParameterObject;
param["OrderString"] = pageResult.OrderString;
...
```

mapper 里动态条件写的是 `property="where.XXX"`。如果 C# 侧**手动**又包一层 where：

```csharp
// ❌ 错误：双包 where
pageResult.ParameterObject = new Dictionary<string, object> { { "where", where } };
```

实际传给 iBATIS 的结构变成 `{ where: { where: { UserName: "xxx" } } }`，mapper 的 `where.UserName` 取到的是**内层字典对象而非字符串值** → 动态条件失效、参数为空。

```csharp
// ✅ 正确：直接传字典，框架自动包 where 层
pageResult.ParameterObject = where;
```

## 三、验证依据

参考生产页 `BusSpecialEquipmentOperators.aspx.cs` 的 SelectDetil（GetFile 语句 mapper 用 `where.TABLEID`）：
```csharp
var pageParams = new Dictionary<string, object>();
busManager.InitDic(pageParams, "TABLEID", id);
pageResult.ParameterObject = pageParams;   // 直接传，没有手动包 where
```

## 四、排查教训（避免重复走弯路）

本坑的迷惑性：症状是"筛选值没传到后台"，极易引导你去排查**前端传参通道**。实际踩坑轨迹（浪费四轮）：

| 轮次 | 尝试 | 结果 |
|---|---|---|
| 1 | ComboBox `.Value` 改 `.Text` | 无效（真凶不在取值） |
| 2 | DirectMethod 不回传控件 → BeforeLoad 注入 proxy.extraParams | 无效（getText 报错修掉后仍无效） |
| 3 | Store `<ext:StoreParameter>` 声明式传参（注意：集合元素必须是 StoreParameter 不是 Parameter） | 无效 |
| 4 | 换 OnReadData 服务端事件 + Hidden 中转 | 仍无效（通道其实已通） |
| 5 | **用户发现 `ParameterObject` 手动包了 where，去掉后立即生效** | ✅ |

**教训：查询条件失效时，先用 SQL 日志确认"参数是否真的没到服务端"。如果连服务端已知的固定条件正常、只有动态条件失效，优先检查 ParameterObject 是否双包 where，再排查前端通道。**

## 五、最终可靠组合（生产验证）

**前端**：查询按钮先把筛选值写入 `<ext:Hidden>`，再刷新 store（Hidden 值随每个 Ext.NET 请求回传，通道最可靠）：
```javascript
var gridPanelMainFresh = function () {
    App.hidden_q_username.setValue(App.selectUserName.getValue() || '');
    App.hidden_q_workbarcode.setValue(App.selectWorkBarcode.getValue() || '');
    App.gridPanelMainStore.currentPage = 1;
    App.gridPanelMainPageToolbar.doRefresh();
    return false;
}
```

**Store**（OnReadData 服务端事件模式，见 `extnet-store-databinding-guide.md` 4.2）：
```xml
<ext:Store ID="gridPanelMainStore" runat="server" PageSize="50" OnReadData="Store_ReadData">
    <Proxy><ext:PageProxy /></Proxy>
    <Model>...</Model>
</ext:Store>
```

**后台**：
```csharp
protected void Store_ReadData(object sender, StoreReadDataEventArgs e)
{
    int pageSize = e.Limit > 0 ? e.Limit : 50;
    int pageIndex = e.Start > 0 ? e.Start / pageSize : 0;
    var pageResult = new PageResult { PageIndex = pageIndex, PageSize = pageSize };

    var where = new Dictionary<string, object>();
    if (!string.IsNullOrEmpty(hidden_q_username.Text))
        where.Add("UserName", hidden_q_username.Text.Trim());

    pageResult.ParameterObject = where;   // ⚠️ 直接传！框架自动包 where
    pageResult.StatementId = "GetMeasureUserPage";
    pageResult.OrderString = "T1.OBJID ASC";

    manager.GetPageDataByReader(pageResult);
    var data = pageResult.ResultDataSet.Tables[0];
    // ...日期格式化等处理...
    store.DataSource = data;
    store.DataBind();
    (store.Proxy[0] as PageProxy).Total = pageResult.RecordCount;
}
```

## 六、附带小坑（同一页踩过的）

1. **ComboBox 客户端取值**：ExtJS 5 没有 `getText()` 方法（报 `getText is not a function` 且中断 store 加载），用 `getValue()`。
2. **Store `<Parameters>` 集合元素**：必须是 `<ext:StoreParameter>`，写 `<ext:Parameter>` 报"必须具有类型为 Ext.Net.StoreParameter 的项"。
3. **清空触发器**：`TriggerClick` 里不要用 `this.triggerWrap.blur()`（triggerWrap 在 ExtJS 5 不存在），只用 `this.clearValue()`。

## 七、参考页面

- `Plugins/EquipManage/Measure/BusMeasurePersonnelQualification.aspx(.cs)` — 计量人员资质（最终正确版）
- `Plugins/EquipManage/Measure/BusCheckDeptManage.aspx(.cs)` — 检定机构管理（同模式）
- `Plugins/EquipManage/Measure/BusSpecialEquipmentOperators.aspx.cs` — SelectDetil 直传 ParameterObject 的生产范例

## 八、关联文档

- `extnet-pagination-guide.md` — 分页完整方案（GetPageDataByReader 用法）
- `extnet-store-databinding-guide.md` — OnReadData 模式
- `extnet-event-mechanisms.md` — DirectMethod/DirectEvents 传值差异
