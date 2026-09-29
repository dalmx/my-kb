---
category: 技术-.NET
factory: 通用
module: C#
status: active
tags: [权限控制, PageAction, 按钮权限, 命名规范]
title: 按钮权限控制（PageAction）
updated: 2026-08-29
---

# 按钮权限控制（PageAction）

> Quality 项目按钮权限控制模式：后台定义继承 Wongoing.Web.UI 基类的权限类（中文属性名=按钮 Text、ActionName=按钮 ID/CommandName），框架自动控制工具栏/操作列按钮显隐。含核心命名规范（权限名必须与按钮 Text 完全一致）、PrepareCommand 动态控制、renderer 生成控件的三层闸权限方案（Permit 探针 + Ajax 缓存坑）。

## 一、概述

Quality项目使用权限控制系统来管理页面按钮和操作列按钮的显示与隐藏。权限通过后台定义权限类，框架自动根据用户权限控制按钮可见性。

## 二、权限定义结构

### 后台代码定义

在页面后台代码（.aspx.cs）中定义权限类：

```csharp
#region 权限定义
protected __ _ = new __();
public class __ : Wongoing.Web.UI.___  // 必须继承___
{
    public __()
    {
        查询 = new PageAction() { ActionId = 1, ActionName = "btnSearch" };
        编辑 = new PageAction() { ActionId = 2, ActionName = "Edit" };
        删除 = new PageAction() { ActionId = 3, ActionName = "Invalid" };
        上传附件 = new PageAction() { ActionId = 4, ActionName = "UploadFile" };
        查看附件 = new PageAction() { ActionId = 5, ActionName = "See" };
    }

    public PageAction 查询 { get; private set; }     // 必须为 public
    public PageAction 编辑 { get; private set; }
    public PageAction 删除 { get; private set; }
    public PageAction 上传附件 { get; private set; }
    public PageAction 查看附件 { get; private set; }
}
#endregion
```

### 权限属性说明

| 属性 | 说明 |
|-----|------|
| ActionId | 权限ID，同一页面内唯一 |
| ActionName | 权限名称，对应前端按钮ID或CommandName |
| 权限名称属性 | 用于在系统中显示权限名称，如"查询"、"编辑"等 |

## 三、前端按钮权限控制

### 工具栏按钮（Toolbar Button）

工具栏按钮通过设置ID与ActionName对应，框架自动控制显示：

```aspx
<ext:Button runat="server" Text="查询" ID="btnSearch">
    <Listeners>
        <Click Fn="pnlListFresh" />
    </Listeners>
</ext:Button>
```

后台定义：`查询 = new PageAction() { ActionId = 1, ActionName = "btnSearch" }`

### 操作列按钮（ImageCommandColumn）

操作列按钮通过CommandName与ActionName对应：

```aspx
<ext:ImageCommandColumn runat="server" Width="280" Text="操作" Align="Center">
    <Commands>
        <ext:ImageCommand IconCls="fa fa-pencil color-info" CommandName="Edit" Text="编辑">
            <ToolTip Text="修改单据信息" />
        </ext:ImageCommand>

        <ext:ImageCommand IconCls="fa fa-upload color-info" CommandName="UploadFile" Text="上传附件">
            <ToolTip Text="上传附件" />
        </ext:ImageCommand>

        <ext:ImageCommand IconCls="fa fa-eye color-primary" CommandName="See" Text="查看">
            <ToolTip Text="查看附件" />
        </ext:ImageCommand>
    </Commands>
    <PrepareCommand Fn="prepareCommand" />
    <Listeners>
        <Command Handler="return commandcolumn_click(command, record);" />
    </Listeners>
</ext:ImageCommandColumn>
```

后台定义：
- `编辑 = new PageAction() { ActionId = 2, ActionName = "Edit" }`
- `上传附件 = new PageAction() { ActionId = 4, ActionName = "UploadFile" }`
- `查看附件 = new PageAction() { ActionId = 5, ActionName = "See" }`

## 四、动态权限控制（PrepareCommand）

通过JavaScript函数动态控制按钮显示，适用于需要根据数据状态控制按钮的场景：

```javascript
var prepareCommand = function (grid, command, record, row) {
    // 根据删除标志控制按钮
    if (record.get("DELETE_FLAG") == 0 && command.command == 'Recover') {
        command.hidden = true;
        command.hideMode = 'display';
    }
    if (record.get("DELETE_FLAG") == 1 && command.command != 'Recover') {
        command.hidden = true;
        command.hideMode = 'display';
    }

    // 根据状态控制编辑按钮
    if (record.get("BILL_FLAG") > 2 && command.command == 'Edit') {
        command.hidden = true;
        command.hideMode = 'display';
    }
}
```

## 五、完整示例

### 后台代码 (TyreCheckQueryNew.aspx.cs)

```csharp
public partial class Plugins_Quality_FakeReport_TyreCheckQueryNew : Wongoing.Web.UI.Page
{
    #region 权限定义
    protected __ _ = new __();
    public class __ : Wongoing.Web.UI.___
    {
        public __()
        {
            查询 = new PageAction() { ActionId = 1, ActionName = "btnSearch" };
            起草 = new PageAction() { ActionId = 2, ActionName = "btnConfirm" };
            编辑 = new PageAction() { ActionId = 3, ActionName = "Edit" };
            预览 = new PageAction() { ActionId = 4, ActionName = "PreView" };
            删除 = new PageAction() { ActionId = 5, ActionName = "Invalid" };
            审核 = new PageAction() { ActionId = 6, ActionName = "Button2" };
            批准 = new PageAction() { ActionId = 7, ActionName = "Button3" };
            上传附件 = new PageAction() { ActionId = 11, ActionName = "UploadFile" };
            查看附件 = new PageAction() { ActionId = 12, ActionName = "See" };
        }

        public PageAction 查询 { get; private set; }
        public PageAction 起草 { get; private set; }
        public PageAction 编辑 { get; private set; }
        public PageAction 预览 { get; private set; }
        public PageAction 删除 { get; private set; }
        public PageAction 审核 { get; private set; }
        public PageAction 批准 { get; private set; }
        public PageAction 上传附件 { get; private set; }
        public PageAction 查看附件 { get; private set; }
    }
    #endregion

    // 其他代码...
}
```

### 前端代码 (TyreCheckQueryNew.aspx)

```aspx
<%-- 工具栏按钮 --%>
<ext:Button runat="server" Text="查询" ID="btnSearch">
    <Listeners><Click Fn="pnlListFresh" /></Listeners>
</ext:Button>
<ext:Button runat="server" Text="起草" ID="btnConfirm">
    <Listeners><Click Handler="pnlListConfirm(0)" /></Listeners>
</ext:Button>

<%-- 操作列按钮 --%>
<ext:ImageCommandColumn runat="server" Width="280" Text="操作">
    <Commands>
        <ext:ImageCommand CommandName="Edit" Text="编辑" />
        <ext:ImageCommand CommandName="PreView" Text="预览" />
        <ext:ImageCommand CommandName="Invalid" Text="删除" />
        <ext:ImageCommand CommandName="UploadFile" Text="上传附件" />
        <ext:ImageCommand CommandName="See" Text="查看" />
    </Commands>
    <PrepareCommand Fn="prepareCommand" />
    <Listeners>
        <Command Handler="return commandcolumn_click(command, record);" />
    </Listeners>
</ext:ImageCommandColumn>
```

## 六、权限配置流程

1. **后台定义权限**：在页面后台代码中定义 `__` 权限类
2. **前端设置按钮ID/CommandName**：确保与ActionName对应
3. **系统配置权限**：在系统权限管理页面为角色分配操作权限
4. **框架自动控制**：框架根据用户权限自动显示/隐藏按钮

## 七、注意事项

1. ActionId 在同一页面内必须唯一
2. ActionName 必须与前端按钮ID或CommandName完全匹配（区分大小写）
3. 权限属性必须声明为 `public`
4. 权限类必须继承 `Wongoing.Web.UI.___`
5. 如果需要动态控制（如根据数据状态），使用 `PrepareCommand` 函数

---

## 八、权限名必须与按钮 Text 完全对应（核心命名规范）

> **本节是实战踩坑后补充的关键规则**，原章节只说"权限名称属性用于在系统中显示权限名称"，没强调必须和按钮 Text 一致——这会导致权限管理界面里看到的权限名和用户在页面上看到的按钮文字对不上，运维和业务方无法准确分配权限。

### 规则

权限类的**中文属性名**（如 `查询`、`删除登记`、`模板下载`）必须与 aspx 里对应按钮的 **`Text` 属性完全一致**，包括字数和用词。

### 为什么必须一致

权限管理页面（`SysMenu/SetPageMenu.aspx` 之类）展示给运维/业务方的权限清单，用的就是权限类里的**中文属性名**。如果属性名和按钮 Text 不一致：
- 运维看到权限列表里写"删除"，但页面上按钮叫"删除登记"——不知道这俩是不是一回事
- 业务方申请权限时说"我要删除登记权限"，运维在权限表里找不到，得翻代码确认
- 多人协作时极易漏配/错配权限

### 正确对应表（举例）

| aspx 按钮 `Text` | 权限类属性名 | ActionName | 按钮 ID |
|---|---|---|---|
| `查询` | `查询` | `btnSearch` | `btnSearch` |
| `导入` | `导入` | `btnImport` | `btnImport` |
| `删除登记` | `删除登记`（**不是"删除"**） | `btnDelete` | `btnDelete` |
| `模板下载` | `模板下载` | `btnDownload` | `btnDownload` |
| `批量导入` | `批量导入`（**不是"导入"**） | `btnAddBatch` | `btnAddBatch` |

### 反例（踩过的坑）

```csharp
// ❌ 错：属性名"删除"与按钮 Text "删除登记" 不一致
删除 = new PageAction() { ActionId = 4, ActionName = "btnDelete" };
// aspx: <ext:Button Text="删除登记" ID="btnDelete" />

// ✅ 对：属性名改成"删除登记"，与 Text 完全一致
删除登记 = new PageAction() { ActionId = 4, ActionName = "btnDelete" };
```

### 检查清单（每次新增/修改按钮时过一遍）

- [ ] 权限类里每个 `public PageAction XxxYyy` 的 `XxxYyy` 是否与 aspx 对应按钮的 `Text` 完全相同
- [ ] ActionName 是否与按钮 `ID`（工具栏按钮）或 `CommandName`（操作列按钮）完全相同（区分大小写）
- [ ] ActionId 在同一页面内是否唯一
- [ ] 新增权限点后，是否提醒用户去权限管理页面为角色重新分配（新增 ActionId 不会自动继承旧权限）

### 不纳入权限的按钮（项目惯例）

以下按钮**不需要**在权限类里声明，参考 Semi `CurdMaterial` / Quality `ReportFqScrapInfo` 等样本：

| 按钮类型 | 例子 | 原因 |
|---|---|---|
| UI 折叠/展开按钮 | `btnPnlQuery`（隐藏查询▲） | 纯界面操作，不涉及业务 |
| 弹窗内按钮 | `btnUploadSave`（导入窗"确定"）、`btnUploadClose`（关闭） | 跟随父按钮权限（如"导入"）统一控制 |
| 分页工具栏按钮 | PagingToolbar 的翻页/每页条数 | 框架自带，所有用户可用 |

> 但如果业务要求弹窗内按钮（如"提交审核"）单独控制权限，仍需为其声明权限点，权限名同样要与按钮 Text 一致。

---

## 九、renderer 生成控件/表格行内交互的权限控制（Permit 探针 + Ajax 缓存，2026-08-28 实战）

框架的自动禁用只认**服务端控件 ID**（`setPageControls` 用 ID 匹配 ActionName），`renderer` 生成的 `<select>`/`<a>`、TableLayout 里的 `ext:ComboBox` 这类**没有服务端控件 ID 的交互**管不到。成型每日/每班点检页（MoldInspection/MoldShiftInspection）落地的三层闸模式：

1. **权限点声明**：`__` 类加一个 PageAction（如 `判定 = new PageAction() { ActionId = 2, ActionName = "btnJudge" }`）。无对应实体按钮时 ActionName 随意但保持唯一；首次访问自动注册进 SSP_PAGE_ACTION，**管理员需手动给角色授权（新增 ActionId 不自动继承）**。
2. **Ajax 缓存（关键坑）**：框架权限绑定（UserBindAction→Permit）只在**非 Ajax** 的 OnInit 跑——DirectMethod 里直接读 `Permit` 恒为默认值 0，会把所有人拒掉。正解=首渲染 Page_Load 里缓存：
   ```csharp
   bool canJudge = (_.判定.Permit == 1);            // Permit 是 Int32（反射 Wongoing.Web.UI.dll 证实）
   Session["<页面>_CanJudge"] = canJudge;           // 给 Ajax DirectMethod 用
   Page.ClientScript.RegisterClientScriptBlock(GetType(), "canJudge",
       "window._canJudge = " + (canJudge ? "true" : "false") + ";", true);  // 给前端渲染用
   ```
   DirectMethod 里 `if (!HasJudgePerm()) return "{\"ok\":false,\"msg\":\"无判定权限\"}";`——**服务端闸是硬闸**（文档明示 Ajax 不重跑权限渲染，前端拦截只是体验层）。
3. **前端只读化**（体验层，`window._canJudge !== true` 走只读分支，undefined 视为无权=失败安全）：
   - renderer 下拉：无权返回当前判定文本（`√ 正常` 等）而非 `<select>`
   - ext:ComboBox（TableLayout 内）：`cbx.setReadOnly(true)`（渲染前设置也生效）
   - 行内操作链接（确认按钮）：直接不渲染

**Permit 类型坑**：反射确认 `PageAction.Permit` 是 `Int32` 不是 bool，判 `== 1`。PowerShell 反射脚本必须存成 **UTF-8 带 BOM**（无 BOM 时 PowerShell 按 ANSI 读，中文路径全乱码）。