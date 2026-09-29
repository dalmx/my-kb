---
title: McUI 翻译手写 aspx 完全指南（配置页完整模式 + 报表踩坑全集）
category: 技术-.NET
module: McUI
factory: 通用
tags: [McUI翻译, 手写aspx, 主从表, SSB_USER, 实时关联, 附件上传, 权限审计, PageAction, 报表翻译, isEqual, isNotNull, GetDataTableByStatement, 踩坑]
updated: 2026-08-29
status: active
---

# McUI 翻译手写 aspx 完全指南（配置页完整模式 + 报表踩坑全集）

> 2026-08-23 合并：原《McUI配置页翻译成手写aspx完整模式》+《McUI 报表翻译成独立 aspx 页面的踩坑全集》两篇合一。
> 第一部分=配置页（Crud 配置翻译为主从表/附件/权限审计复杂页）的完整实现模式；第二部分=报表翻译的 9 个踩坑与推荐做法。

## 一、配置页翻译完整模式（主从表 + SSB_USER 实时关联 + 附件 + 权限审计）

### 适用场景

EquipManage 项目 Measure 模块需要超越 McUI 配置能力的复杂页面（附件上传、行标色、主从表联动等）时，把现有 McUI 配置页**翻译成手写 aspx**。

典型案例：
- **计量人员资质** `BusMeasurePersonnelQualification.aspx`：主表=SSB_USER 计量系人员（实时关联），附件为人员资质 PDF
- **检定机构管理** `BusCheckDeptManage.aspx`：原 McUI 配置页 CrudBusCheckDept 翻译为手写 aspx，加附件+有效期预警标色

### 一、SSB_USER 实时关联主表（按部门查人员）

#### 场景
主表显示某部门人员，需实时显示用户名/工号/部门/岗位（人员调岗后信息自动更新）。

#### SQL（BusinessMapper 新增语句）
```xml
<select id="GetMeasureUserPage" parameterClass="map" resultClass="Row">
  <![CDATA[SELECT T1.OBJID, T1.USER_NAME, T1.REAL_NAME, T1.WORK_BARCODE,
           T3.DEPT_NAME AS DEPT_ID, T4.WORK_NAME AS WORK_ID
    FROM SSB_USER T1 with(nolock)
    LEFT JOIN SSB_DEPT T3 with(nolock) ON T1.DEPT_ID = T3.DEPT_CODE
    LEFT JOIN SSB_WORK T4 with(nolock) ON T1.WORK_ID  = T4.WORK_CODE
    WHERE T1.DEPT_ID = '090303' AND T1.DELETE_FLAG = '0']]>
  <dynamic prepend="AND">
    <isNotNull property="where.UserName" prepend="AND"><![CDATA[(T1.USER_NAME LIKE '%' + #where.UserName# + '%' OR T1.REAL_NAME LIKE '%' + #where.UserName# + '%')]]></isNotNull>
    <isNotNull property="where.WorkBarcode" prepend="AND"><![CDATA[T1.WORK_BARCODE LIKE '%' + #where.WorkBarcode# + '%']]></isNotNull>
  </dynamic>
  <isNotNull property="OrderString" prepend=" ">ORDER BY $OrderString$</isNotNull>
</select>
```

**要点**：
- `SSB_USER.DEPT_ID` 关联 `SSB_DEPT.DEPT_CODE`（不是 OBJID）
- `SSB_USER.WORK_ID` 关联 `SSB_WORK.WORK_CODE`
- 部门编码硬编码（计量系=090303），也可改参数化
- 用户名查询同时匹配 USER_NAME（登录名）和 REAL_NAME（真实姓名）

#### 后台 GridPanelBindData（PageProxy 分页）
```csharp
[DirectMethod]
public object GridPanelBindData(string action, Dictionary<string, object> extraParams)
{
    StoreRequestParameters prms = new StoreRequestParameters(extraParams);
    var pageResult = new PageResult { PageIndex = prms.Page, PageSize = prms.Limit };
    var where = new Dictionary<string, object>();
    if (!string.IsNullOrEmpty(selectUserName.Text)) where.Add("UserName", selectUserName.Text.Trim());
    if (!string.IsNullOrEmpty(selectWorkBarcode.Text)) where.Add("WorkBarcode", selectWorkBarcode.Text.Trim());
    pageResult.ParameterObject = new Dictionary<string, object> { { "where", where } };
    pageResult.StatementId = "GetMeasureUserPage";
    pageResult.OrderString = "T1.OBJID ASC";
    userManger.GetPageDataByReader(pageResult);
    var data = pageResult.ResultDataSet.Tables[0];
    var total = pageResult.RecordCount;
    return new { data, total };
}
```

### 二、主从表联动（行点击加载附件）

#### 前端
```xml
<ext:GridPanel ID="gridPanelMain" ...>
    <Listeners>
        <RowClick Fn="selectDetil" />
    </Listeners>
</ext:GridPanel>
<ext:GridPanel runat="server" ID="gridPanelDetil" Region="South" Height="220" Title="资质附件" Split="true" Collapsible="true">
    ...
</ext:GridPanel>
```
```javascript
var selectDetil = function (item, record) {
    App.hidden_sel_user.setValue(record.data.OBJID);
    App.direct.SelectDetil(record.data.OBJID, { eventMask: { showMask: true } });
}
```

#### 后台 SelectDetil（附件明细：解析上传人姓名+格式化时间）
```csharp
[DirectMethod]
public void SelectDetil(object id)
{
    var pageResult = new PageResult();
    pageResult.ParameterObject = new Dictionary<string, object> { { "TABLEID", id }, { "TABLENAME", tableName } };
    pageResult.StatementId = "GetFile";
    pageResult.OrderString = "RECORD_TIME desc";
    operManager.GetPageDataByReader(pageResult);

    var Datatable = pageResult.ResultDataSet.Tables[0];
    string rootPath = ConfigurationManager.AppSettings["ftpview"];

    //批量解析上传人姓名（避免逐行查询）
    var userIds = new HashSet<string>();
    foreach (DataRow row in Datatable.Rows)
        if (row["RECORD_USER_ID"] != null && row["RECORD_USER_ID"] != DBNull.Value)
            userIds.Add(row["RECORD_USER_ID"].ToString());

    var userNameMap = new Dictionary<string, string>();
    foreach (var uid in userIds)
    {
        int oid;
        if (int.TryParse(uid, out oid))
        {
            var u = userManger.GetByObjId(oid);
            if (u != null) userNameMap[uid] = string.IsNullOrEmpty(u.RealName) ? u.UserName : u.RealName;
        }
    }

    //FILEPATH 拼下载根路径；UPLOAD_USER 取用户名；RECORD_TIME 格式化字符串
    Datatable.Columns.Add("UPLOAD_USER", typeof(string));
    Datatable.Columns.Add("RECORD_TIME_STR", typeof(string));
    foreach (DataRow row in Datatable.Rows)
    {
        if (row["FILEPATH"] != null && !string.IsNullOrEmpty(row["FILEPATH"].ToString()))
            row["FILEPATH"] = rootPath + row["FILEPATH"].ToString();
        string uid = row["RECORD_USER_ID"] == null || row["RECORD_USER_ID"] == DBNull.Value ? "" : row["RECORD_USER_ID"].ToString();
        row["UPLOAD_USER"] = userNameMap.ContainsKey(uid) ? userNameMap[uid] : "";
        if (row["RECORD_TIME"] != null && row["RECORD_TIME"] != DBNull.Value)
        {
            DateTime dt; row["RECORD_TIME_STR"] = DateTime.TryParse(row["RECORD_TIME"].ToString(), out dt) ? dt.ToString("yyyy-MM-dd HH:mm:ss") : row["RECORD_TIME"].ToString();
        }
        else row["RECORD_TIME_STR"] = "";
    }
    Datatable.Columns.Remove("RECORD_TIME");
    Datatable.Columns["RECORD_TIME_STR"].ColumnName = "RECORD_TIME";

    storeGridPanelDetil.Data = Datatable;
    storeGridPanelDetil.DataBind();
}
```

> **时间列必须后端格式化字符串 + 前端普通 Column**，不能用 DateColumn（详见 `extnet-grid-datecolumn-pitfall.md`）。

### 三、上传附件时更新机构日期（填了更新，没填保留原值）

```csharp
//上传成功后，如果填了日期则更新该机构的有效期/预警日期
DateTime? validDate = string.IsNullOrEmpty(dfUploadValid.Text) ? (DateTime?)null : (DateTime?)dfUploadValid.Value;
DateTime? alarmDate = string.IsNullOrEmpty(dfUploadAlarm.Text) ? (DateTime?)null : (DateTime?)dfUploadAlarm.Value;
if (validDate.HasValue || alarmDate.HasValue)
{
    var updateEntity = new BusCheckDept();
    if (validDate.HasValue) updateEntity.ValidDate = validDate;
    if (alarmDate.HasValue) updateEntity.AlarmDate = alarmDate;
    deptManager.Update(updateEntity, new BusCheckDept { ObjId = oid });
}
```

> `deptManager.Update(update, where)` 只更新 updateEntity 里非 null 的字段（BasicMapper includeUpdate 用 isNotNull 动态拼接 SET）。

### 四、权限审计清单（发布前必查）

每次新增/修改页面后，按此清单逐项核对：

#### 权限类 `__` 必须覆盖所有业务按钮

| 按钮类型 | 声明权限 | 对应方式 |
|---|---|---|
| 工具栏按钮 | ✅ 声明 | ActionName = 按钮 ID |
| 操作列按钮（ImageCommandColumn） | ✅ 声明 | ActionName = CommandName |
| 弹窗内确定/取消 | ❌ 不声明 | 跟随父按钮权限 |
| 分页工具栏 | ❌ 不声明 | 框架自带 |
| UI 折叠按钮（btnPnlQuery） | ❌ 不声明 | 纯界面操作 |

#### 权限名必须与按钮 Text 完全一致
```csharp
//✅ 权限名"添加检定机构"与 aspx 按钮 Text="添加检定机构" 一致
添加检定机构 = new PageAction() { ActionId = 2, ActionName = "btnAdd" };

//❌ 权限名"添加"与按钮 Text="添加检定机构" 不一致
添加 = new PageAction() { ActionId = 2, ActionName = "btnAdd" };
```

#### 审计步骤
1. grep aspx 里所有 `ext:Button runat` 的 `Text` 和 `ID` → 核对权限类是否有对应权限点
2. grep aspx 里所有 `CommandName=` → 核对权限类是否有对应权限点
3. 核对每个权限点的**权限名==按钮 Text**、**ActionName==按钮ID/CommandName**
4. 核对 ActionId 同页唯一
5. **提醒用户**：新增权限点后去权限管理页给角色分配（不会自动继承）

#### 检定机构管理页面权限完整清单（参考）
| 权限名 | ActionId | ActionName | 位置 |
|---|---|---|---|
| 查询 | 1 | btnSearch | 工具栏 |
| 添加检定机构 | 2 | btnAdd | 工具栏 |
| 上传附件 | 3 | UploadFile | 主表操作列 |
| 编辑 | 4 | Edit | 主表操作列 |
| 删除 | 5 | Delete | 主表操作列 |
| 预览 | 6 | Preview | 附件明细操作列 |

### 五、给已有表加字段（DDL + Entity + BasicMapper 同步改）

以 BUS_CHECK_DEPT 加 VALID_DATE/ALARM_DATE 为例：

1. **DDL**（交用户执行）：`ALTER TABLE BUS_CHECK_DEPT ADD VALID_DATE datetime NULL, ALARM_DATE datetime NULL`
2. **Entity**（BusCheckDept.cs）：加 `ValidDate`/`AlarmDate` 属性
3. **BasicMapper**（BusCheckDept.xml）：5 处同步改
   - `resultMap`：加 result 行
   - `parameterMap`：加 parameter 行
   - `includeWhere`：加 isNotNull 条件
   - `includeInsert`：加列名 + 值
   - `includeUpdate`：加 SET 子句
4. **BusinessMapper**（如需自定义查询）：新增带 JOIN 的查询语句

### 参考页面

- `Plugins/EquipManage/Measure/BusMeasurePersonnelQualification.aspx(.cs)` — 计量人员资质（SSB_USER 实时关联）
- `Plugins/EquipManage/Measure/BusCheckDeptManage.aspx(.cs)` — 检定机构管理（McUI 翻译+附件+标色）
- `Plugins/EquipManage/Measure/BusSpecialEquipmentOperators.aspx(.cs)` — 特种设备作业人员证书（主从表+FTP 附件参考）

### 关联文档

- `measure-attachment-full-solution.md` — FTP 附件上传/预览/删除完整方案
- `extnet-row-color-by-date.md` — 行底色标黄标红 + 日期格式化
- `ibatis-null-directmethod-null-window-layout-pitfalls.md` — parameterMap null / DirectMethod null / 弹窗布局坑
- `button-permission.md` — 按钮权限控制
- `main-mcui-config-framework.md` — McUI 配置化框架（理解原 McUI 页）

---

### ⚠️ 重要勘误：本文 GridPanelBindData 示例中 ParameterObject 的错误写法

本文「二、主从表联动」等节示例中出现的：

```csharp
pageResult.ParameterObject = new Dictionary<string, object> { { "where", where } };  // ❌ 错误！
```

是**错误写法**（双包 where，导致 mapper 的 `where.XXX` 全部取不到值、查询条件失效）。正确写法：

```csharp
pageResult.ParameterObject = where;  // ✅ 直接传字典，框架自动包 where 层
```

框架 `BaseService.GetPageDataByReader` 内部会执行 `param["where"] = pageResult.ParameterObject;`（BaseService.cs 第1097/1184行），手动再包一层 where 会让动态条件全部失效。

完整排查过程、框架源码证据、前端传参通道的可靠组合（OnReadData + Hidden 中转），详见 [[pageresult-parameterobject-double-where-pitfall]]。

---

### 五点五、行点击去重：同一行不重复查询附件明细（性能细节）

主从表联动（RowClick → 加载附件明细）默认每次点击都发 DirectMethod 请求。用户经常反复点击同一行查看，造成无意义的重复查询。

**优化写法**：用已有的 `hidden_sel_*`（记录当前选中行 OBJID）做比较，点击前行 ID 相同则直接返回：

```javascript
//行点击：加载该人员的资质附件明细（与上次点击同一行时不重复查询）
var selectDetil = function (item, record) {
    var newId = record.data.OBJID;
    if (App.hidden_sel_user.getValue() == newId) {
        return false;   //同一行不重复查询
    }
    App.hidden_sel_user.setValue(newId);
    App.direct.SelectDetil(newId, {
        eventMask: { showMask: true }
    });
}
```

**行为**：
- 首次点击正常查询；反复点同一行只查一次
- 切换到别的行再点回来会重新查（选中值已变化）
- 上传/删除附件后后台主动调 `SelectDetil(id)` 刷新数据，不受此逻辑影响（hidden 值未变，下次点同一行仍跳过，但数据已是最新）

**适用**：所有「主表 RowClick → 明细 DirectMethod 查询」的主从表页面。参考 `BusMeasurePersonnelQualification.aspx` / `BusCheckDeptManage.aspx` 的 selectDetil 函数。

## 二、报表翻译踩坑全集（9 坑 + 推荐做法）

### 坑 1：iBatis `<isEqual>` 对 `Dictionary` 参数抛 NullReferenceException（最致命）
#### 现象
`GetDataTableByStatement("stmtId", dic)`（dic 是 `Dictionary<string,string>`）调用时抛：
```text
NullReferenceException: Object reference not set to an instance of an object.
  at System.Object.GetType()
  at MyBatis.DataMapper.Model.Sql.Dynamic.Handlers.ConditionalTagHandler.Compare(...)
  at ...IsEqualTagHandler.IsCondition(...)
```
#### 根因
Mapper 里用了 `<isEqual property="TYPE" compareValue="1">`。`IsEqualTagHandler` 在对 **Dictionary 参数对象**做属性比较时，内部 `Compare` 调 `parameterObject.GetType()` 取属性拿到 null → 空引用。`<isEqual>` 对 Dictionary 参数有兼容 bug。
#### 实证
`RepairRecords` 的 `GetRepairInfo`（FqrRepairRecords.xml）**全程只用 `<isNotNull>`，从不用 `<isEqual>`** —— 这就是它能跑通的原因。
#### 修复
把 `<isEqual>` 换成 `<isNotNull>` + SQL 直接比较：
```diff
- <isEqual property="TYPE" compareValue="1"> where t.SCRAP_TYPE = 1 </isEqual>
- <isEqual property="TYPE" compareValue="2"> where t.SCRAP_TYPE = 2 </isEqual>
- <isEqual property="TYPE" compareValue="3"> where t.SCRAP_TYPE = 3 </isEqual>
+ <isNotNull property="TYPE" prepend="where"> t.SCRAP_TYPE = #TYPE# </isNotNull>
- 不传 TYPE → 不加 where，返回全部 ✓
- 传 "1"/"2"/"3" → `where t.SCRAP_TYPE = #TYPE#`，SQL Server 字符串与 int 隐式比较 ✓
```
#### 规则
**用 `GetDataTableByStatement` + `Dictionary` 参数时，Mapper 动态标签一律用 `<isNotNull>`，禁用 `<isEqual>`。** 空值在 .cs 端不加入 Dictionary（触发 isNotNull 跳过）。
---

### 坑 2：`GetPageDataByReader` 参数自动包 `where`

框架内部已自动 `param["where"] = pageResult.ParameterObject`——`.cs` 端 `GetParameterObject()` 必须返回**扁平字典**，手动再包一层会变成 `where.where.xxx` 导致条件全部失效。

完整根因分析（框架源码铁证）与修复对照见 [pageresult-parameterobject-double-where-pitfall.md](pageresult-parameterobject-double-where-pitfall.md)。


### 坑 3：`GetPageDataByReader` 的 `PageSize=0` 取不到全量

#### 现象
`PageSize=0, PageIndex=0` 想取全量，结果返回**空 DataTable**（不是全量）。

#### 根因
`getPageDataByReader` 逻辑：`begin = PageSize*(PageIndex-1)+1`，然后循环读 PageSize 条。`PageSize=0` → 读 0 条。

#### 修复
取全量用 `PageIndex=1, PageSize=1000000`（给大值即等同全量）。

#### 更优方案
**改用 `GetDataTableByStatement`**（直接返回 DataTable，不经过分页框架，彻底避开）。`RepairRecords` 即用此法。

---

### 坑 4：Ext.NET 控件集合内禁止注释

`<Items>/<Columns>/<TopBar>` 等 `ItemsCollection<T>` 集合标签内**不放任何 HTML 注释/文字**（解析器报错"不允许包含文字内容"）；说明用控件 `Title` 属性或把注释放集合外。

完整现象/根因/正解见 [report-common-pitfalls.md](report-common-pitfalls.md) 坑 4。


### 坑 5：控件 ID 重复（Edit 重写残留）

#### 现象
```text
ID "tbReport" 已被其他控件使用
```

#### 根因
用 Edit 重写某段（如 TopBar）时，若 old_string 未覆盖整段，原内容残留 + 新内容并存 → 同 ID 出现两次。

#### 修复
重写控件块时，确保 old_string 包含完整结构（含闭合标签），或用 Write 整体重写文件。

#### 规则
重写后用 `grep -oE 'ID="[^"]+"' | sort | uniq -c | awk '$1>1'` 扫描重复 ID。

---

### 坑 6：`PageResult` / `PageAction` 的命名空间

#### 现象
```text
CS0246: 未能找到类型或命名空间"PageResult"
CS0246: 未能找到类型或命名空间"PageAction"
```

#### 根因
精简 using 时误删命名空间。

#### 命名空间归属（实证）
| 类 | 命名空间 | 文件 |
|---|---|---|
| `PageResult` | `Wongoing.DbAccess` | `Frame/Wongoing.DbAccess/DbHelper/PageResult.cs` |
| `PageAction` | `Wongoing.Web.UI.Entity` | — |
| `___`（权限基类） | `Wongoing.Web.UI` | — |
| `Page`（页面基类） | `Wongoing.Web.UI` | — |

#### 规则
aspx.cs 的 using 至少含：
```csharp
using Wongoing.DbAccess;        // PageResult（用 GetPageDataByReader 时）
using Wongoing.Web.UI;          // Page, ___
using Wongoing.Web.UI.Entity;   // PageAction
```
用 `GetDataTableByStatement`（不依赖 PageResult）时 `Wongoing.DbAccess` 可省。

---

### 坑 7：接口变量调 BaseManager 方法

#### 现象
通过 `ISppTyreStateManager`（接口）调 `GetDataTableByStatement`（BaseManager 方法）行为可疑。

#### 修复
字段类型用**具体类**而非接口（和 RepairRecords 用 `FqrRepairRecordsManager` 一致）：
```csharp
private SppTyreStateManager tyreStateManager = new SppTyreStateManager();
```

---

### 坑 8：文件位置与 Inherits/类名

#### 现象
独立 aspx 放在 `Plugins/Quality/` 顶层，应归类到子目录。

#### 修复
移到 `Plugins/Quality/ReportAnalyse/`，同步改：
- `Inherits="Plugins_Quality_ReportAnalyse_ReportFqScrapInfo"`（目录路径对应下划线）
- `partial class Plugins_Quality_ReportAnalyse_ReportFqScrapInfo`
- 相对资源路径 `../../../resources/...`（从 WebSite 根算 3 层，与同目录其它报表一致）

#### 规则
`Inherits` 和类名必须与目录路径对应（`Plugins_<模块>_<子目录>_<页名>`）。

---

### 坑 9：McUI 报表的 `Cls="msg"` 限制宽度

#### 现象
汇总/明细 Grid 标题栏被压成 250px 宽，视觉崩坏。

#### 根因
`<style>.msg { width: 250px; }</style>` + `Cls="msg"` 加在 GridPanel 父 Panel 上。DailyReport 列少（4~5 列）勉强能显示，列多（14 列）直接崩。

#### 修复
去掉 `.msg` 的 `width: 250px`，让 GridPanel 自适应满宽。

---

### 总结：McUI 报表翻译 aspx 的推荐做法

1. **数据获取**：用 `GetDataTableByStatement` + 扁平 `Dictionary<string,string>`（参照 RepairRecords），不用 `GetPageDataByReader` 的分页框架。
2. **Mapper 动态标签**：一律 `<isNotNull>`，禁用 `<isEqual>`；参数用扁平 `#xxx#`。
3. **页面结构**：汇总/明细用 TabPanel 标签页切换（参照 RepairRecords），汇总不分页（DataSource 直接绑定）+ 占比%列，明细内存分页（RemotePaging + Session 缓存切片）。
4. **汇总口径**：C# 端 LINQ 对明细 Session 分组（与明细口径一致，只查一次库），不在 SQL 端 group by。
5. **导出**：汇总+明细双 Sheet（DataSet + ExcelDownload）。
6. **aspx 注释**：控件集合内禁放注释。
7. **Manager 字段**：用具体类类型。

