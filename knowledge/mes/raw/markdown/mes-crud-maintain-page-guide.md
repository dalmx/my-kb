---
title: MES 基础数据维护页面（字典 CRUD）通用开发指南
category: 技术-.NET
module: 通用
factory: 通用
tags: [维护页面, 字典表, CRUD, 增删改查, BasicMapper, BusinessMapper, GetPageDataByReader, 软删除, 分层模板, csproj注册, 记录人, UserBarcode, 通用]
updated: 2026-08-29
status: active
---
# MES 基础数据维护页面（字典 CRUD）通用开发指南

> 全 MES 项目族（Quality / Semi / Batch / Main / Curing / Mix / Molding / Mould / Equip / EquipManage / Storage / TechRecipe）通用的"基础数据/字典维护页面"开发套路：一张字典表 + 查询/添加/修改/删除。与报表页（查询+导出，见 create-report 技能）相对，维护页核心是**增删改 + 弹窗编辑**。2026-08 在 Mould 项目"模具改造类型"页面上完整验证。

## 一、整体套路与开发顺序

```text
建表 SQL（sql/ 目录，幂等脚本）
  → 实体 BasicEntity/<Entity>.cs
  → Data 层 Service + Interface
  → Business 层 Manager + Interface
  → Mapper：BasicMapper/<Entity>.xml（标准 CRUD）+ BusinessMapper/<Entity>.xml（分页/扩展）
  → 页面 Plugins/<X>/<子目录>/<Page>.aspx + .aspx.cs
  → 编译（Entity → Mapper → Data → Business）+ 菜单/权限配置
```

动手前**先找一个同类维护页照抄**（每个项目都有：如 Mould 的 `frmTbEqBladderSpec`、EquipManage 的 `BusCheckDeptManage`），比凭空写可靠。

## 二、分层文件与 csproj 注册清单

| 层 | 新建文件 | csproj 注册 |
|----|---------|------------|
| 实体 | `BasicEntity/<Entity>.cs` | `<Compile Include="BasicEntity\<Entity>.cs" />` |
| 数据层 | `Data/Implements/<Entity>Service.cs` + `Data/Interface/I<Entity>Service.cs` | 各一条 `<Compile Include=...>` |
| 业务层 | `Business/Implements/<Entity>Manager.cs` + `Business/Interface/I<Entity>Manager.cs` | 各一条 `<Compile Include=...>` |
| Mapper | `BasicMapper/<Entity>.xml` + `BusinessMapper/<Entity>.xml` | 各一条 `<EmbeddedResource Include=...>` |
| 页面 | `Plugins/<X>/<子目录>/<Page>.aspx(+.cs)` | 无需注册（WebSite 是 CodeFile 动态编译） |

**四层 csproj 都要手工编辑**（旧式 csproj 不会自动包含新文件），按字母序插到相邻实体旁。Mapper XML 是 EmbeddedResource，**改了必须重编 Mapper 工程**才生效。

### 命名转换规则

| 项 | 规则 | 示例 |
|----|------|------|
| 表名 | `tb_XX_XXX` 模块前缀 | `tb_EQ_MouldModifyType` |
| 实体类 | 去 `tb_`、驼峰拼接 | `TbEqMouldmodifytype` |
| 实体属性 | 列名首字母小写驼峰（ObjId 除外） | `ModifyTypeCode → Modifytypecode`、`ObjId(long?)` |
| Service/Manager | `<Entity>Service` / `<Entity>Manager` + 同名 Interface | `TbEqMouldmodifytypeManager` |
| 页面类 | `Plugins_<X>_<子目录>_<Page>`（新页面用完整路径，老页面有不带 `<X>` 的历史遗留别学） | `Plugins_Mould_Equip_MouldModifyType` |

## 三、BasicMapper 与 BusinessMapper 分工

- **BasicMapper/<Entity>.xml**：生成器风格的标准 CRUD——`resultMap`/`parameterMap`/`includeSelect`/`includeWhere`/`includeInsert`/`includeUpdate` + `GetByObjId`/`GetEntityList`/`GetRowCount`/`Insert`/`UpdateByObjId`/`Update`/`Delete`/`DeleteByObjId`。页面经 `BaseManager<T>` 直接调用，**不用改它**。要点：
  - `parameterMap` **不含自增主键 OBJID**（IDENTITY 自增）。
  - `includeWhere` 是**等值**条件（`where.XXX = #where.XXX#`），配合 `GetEntityList(new E{...})` 做精确查询/查重。
  - `UpdateByObjId(new E{只赋要改的字段}, objid)` 动态 SET 只更新非 null 字段——软删除就靠它。
- **BusinessMapper/<Entity>.xml**：放页面真正用的扩展语句：
  - `GetPageData`（`parameterClass="map"` + `resultClass="Row"`）：`GetPageDataByReader` 的数据源，条件用 `where.XXX`（`isNotEmpty` 模糊 / `isNotNull` 等值，每个子元素带 `prepend="AND"`，CDATA 内不写 AND）。
  - `updateData`：编辑保存的**全列更新**（BasicMapper 动态 SET 对"清空字段"无效——null 不更新）。

## 四、页面标准骨架（照抄参考页）

- **North**：Toolbar（查询 `btn_search` / 添加 `btn_add` / 隐藏查询 `btnPnlQuery`）+ FormPanel 查询条件（ColumnLayout .25，下拉带 Clear 触发器，不放"全部"项）。
- **Center**：GridPanel + 服务端分页（`<ext:PageProxy DirectFn="App.direct.GridPanelBindData" />`，`PageSize="50"`，PagingToolbar + 每页条数 ComboBox `Editable="true"`）。操作列 `ImageCommandColumn`（Edit/Delete Command）+ JS `Ext.Msg.confirm` 二次确认。
- **弹窗**：新增/编辑共用一个 `Window` + `Hidden` 存主键区分模式；`ValidityChange` 控制确定按钮 Disabled。弹窗高度要给足（字段 3~4 个时 Height ≥ 300，TextArea 显式 `Height="90"`，`Resizable="true"` 兜底），否则备注等控件被挤压展示不全。
- **code-behind 命名**：查询条件控件 `tf_xxx_select`；弹窗字段 `addOrEdit_Xxx`；Grid `GridPanelPlanControl`/`store`/`pageToolBar`（与各项目参考页一致，方便互相抄）。

### 分页代码模式（私有重载 + DirectMethod）

```csharp
private PageResult GridPanelBindData(PageResult pageResult)
{
    var pageParams = new Dictionary<string, string>();
    //...收集查询条件，非空才 Add...
    pageResult.ParameterObject = pageParams;
    pageResult.StatementId = "GetPageData";   //BusinessMapper 里的 id
    return xxxManager.GetPageDataByReader(pageResult);
}
[DirectMethod]
public object GridPanelBindData(string action, Dictionary<string, object> extraParams)
{
    StoreRequestParameters prms = new StoreRequestParameters(extraParams);
    var pageResult = new PageResult { PageIndex = prms.Page, PageSize = prms.Limit };
    pageResult = GridPanelBindData(pageResult);
    var data = pageResult.ResultDataSet.Tables[0];
    var total = pageResult.RecordCount;
    return new { data, total };
}
```

查询按钮 JS：`App.store.currentPage = 1; App.pageToolBar.doRefresh();`（翻页/刷新统一走 PageProxy）。

## 五、删除策略与查重

- **软删除**（字典将来会被业务单据引用时用，推荐默认）：表带 `DeleteFlag INT DEFAULT 0`；页面删除 = `manager.UpdateByObjId(new E{Deleteflag = 1}, objid)`；查询默认 `DeleteFlag='0'`，查询条件给"删除标志"下拉（否/是，清空触发器=查全部）。
- **物理删除**（纯配置、无引用时可用）：`manager.Delete(new E{...})`。
- **代码查重**：插入/编辑前 `GetEntityList(new E{Code = x, Deleteflag = 0})`，编辑时排除自身（比对 ObjId）。
- **不加 UNIQUE 数据库约束**：软删除的行会占用代码导致同代码无法重新新增，唯一性交给应用层校验。

## 六、记录人/记录时间字段规范（2026-08 补充，Mould 验证）

- **保存值**：`.cs` 端存 `this.Data.User.UserBarcode.ToString()`（工号条码）——**不是** `UserId`（那是 SSB_USER.OBJID，Mould 存量大量误用，新代码统一 UserBarcode，详见 `mes-dic-user-join-pattern.md` 人员关联节的存量警告）。
- **列表显示**：GetPageData 里 `LEFT JOIN SSB_USER T2 ON T1.RecordUser = T2.WORK_BARCODE`，输出 `T2.REAL_NAME AS RecordUserName`；ModelField/DataIndex 用别名 `RecordUserName`。LEFT JOIN 保证人员缺失/占位值（'system'）不丢行、只显示空白。
- **添加与修改都刷新**：Insert 实体带 `Recorduser/Recordtime`；`updateData` 全列更新语句同时 SET `RecordUser = #RecordUser#`、`RecordTime = #RecordTime#`，修改分支传当前用户 + `DateTime.Now`——"记录人/记录时间"语义为最后操作人/最后操作时间。
- **时间输出**：`CONVERT(VARCHAR(19), T1.RecordTime, 120) AS RecordTime`（服务端分页场景，见 `extnet-grid-datecolumn-pitfall.md`）。

## 七、三个必守的坑（详见对应文档）

1. **BasicMapper Insert 的 parameterMap null 坑**：可空 string 字段在 .cs 端兜底空串（null 会空引用或参数错位落错列）；`DateTime?`/`int?` 可空字段改走 `InsertByStatement` + BusinessMapper 动态 SQL。→ 详见 `ibatis-null-directmethod-null-window-layout-pitfalls.md`
2. **时间列显示**：服务端分页场景 SQL 输出侧 `CONVERT(VARCHAR(19), col, 120)` + 普通 Column 最稳（绕开解析层）；客户端绑定场景 ModelField 不声明 Type + DateColumn.Format。→ 详见 `extnet-grid-datecolumn-pitfall.md`
3. **DirectMethod/控件取值 null 防护**：`x.Value == null ? "" : x.ToString()` 先兜底再用。→ 详见 `ibatis-null-directmethod-null-window-layout-pitfalls.md` 第二节

## 八、权限定义与部署 checklist

### PageAction（每个功能按钮一个，ActionName 与按钮 ID/CommandName 完全一致）

权限类完整结构（`__`/`___` 基类、PageAction 定义、ActionId 分配惯例）见 [button-permission.md](button-permission.md)；CRUD 四动作惯例：查询 btn_search=1、添加 btn_add=2、修改 Edit=3（操作列 CommandName）、删除 Delete=4。

### 部署 checklist

- [ ] 建表 SQL 已执行（脚本放项目 `sql/` 目录，幂等可重复执行）
- [ ] 四个工程按依赖序重编：Entity → Mapper → Data → Business
- [ ] 页面 .aspx/.aspx.cs 拷到目标站点（CodeFile 动态编译，改了 cs 一般还需重启应用池）
- [ ] `SysMenu/SetPageMenu.aspx`（SSP_PAGE_MENU 表）配菜单入口
- [ ] 角色管理里给相应角色勾选查询/添加/修改/删除权限
- [ ] C# 5 语法自查：无 `$""`、`?.`、`??`、表达式体成员

## 九、参考页面

- `P.Mould/Wongoing.Mould.WebSite/Plugins/Mould/Equip/MouldModifyType.aspx(.cs)` — 模具改造类型维护（2026-08，本指南的完整落地样例：软删除+查重+服务端分页+时间列 CONVERT+记录人 UserBarcode/REAL_NAME 关联）
- `P.Mould/.../Equip/StandardPartsManagement/frmTbEqBladderSpec.aspx(.cs)` — 胶囊规格维护（更简版，物理删除）
- `P.Mould/.../TechnicalManagement/TechnicalParameter.aspx(.cs)` — 技术参数维护（大表单多弹窗版）

## 十、关联文档

- `ibatis-null-directmethod-null-window-layout-pitfalls.md` — parameterMap/DirectMethod null 坑详解
- `extnet-grid-datecolumn-pitfall.md` — 时间列空白坑与三方案
- `mes-dic-user-join-pattern.md` — 字典/人员关联通用规则（含 Mould 存量 OBJID 模式警告）
- `button-permission.md` — 权限系统详解
- `sql-server-table-design-principles.md` — 建表 DDL 规范（字典表主键/DeleteFlag/注释模板）
