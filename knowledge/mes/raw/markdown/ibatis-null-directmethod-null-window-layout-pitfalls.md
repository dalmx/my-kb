---
title: iBATIS parameterMap null 坑 + DirectMethod null 防护 + 弹窗日期控件布局坑
category: 技术-.NET
module: iBATIS
factory: 通用
tags: [iBATIS, parameterMap, InsertByStatement, null, 错位, 空串兜底, DirectMethod, 空引用, Ext.NET, Window, Container, ColumnLayout, DateField, 布局坑, 踩坑]
updated: 2026-08-29
status: active
---
# iBATIS parameterMap null 坑 + DirectMethod null 防护 + 弹窗日期控件布局坑

> EquipManage Measure 模块四类高频坑：①BasicMapper Insert 走 parameterMap 位置绑定，可空字段为 null 时空引用、string 字段还会整体错位（正解 = InsertByStatement + parameterClass="map" 动态 SQL；仅一两个 string 可空字段可兜底空串）；②DirectMethod object 参数必须先 null 防护（Ext.NET 把空串序列化成 null，前端用 '0' 占位）；③弹窗 Layout="Form" 内不要嵌 Container+ColumnLayout 放 DateField；④DateField 不支持 ToolTip 子元素，提示文案用 EmptyText。

## 一、iBATIS BasicMapper parameterMap 对 null 字段处理坑

### 现象
`deptManager.Insert(entity)` 新增检定机构时报 `Object reference not set to an instance of an object`（空引用），当实体的可空日期字段（ValidDate/AlarmDate）为 null 时。

### 根因
BasicMapper 的 `Insert` 语句声明了 `parameterMap="P_BusCheckDept"`（位置参数映射），同时 `includeInsert` 用动态 `<isNotNull>`：
```xml
<statement id="Insert" parameterMap="P_BusCheckDept" resultClass="int">
  <include refid="includeInsert"/>   <!--动态 isNotNull-->
</statement>
```
`parameterMap` 要求参数按固定顺序传入，当可空字段为 null 时，parameterMap 机制仍尝试按位置取值 → 空引用。

### 解决：用 InsertByStatement + 自定义动态 SQL 绕开

在 **BusinessMapper** 新增一个 `parameterClass="map"` 的插入语句（动态字段，null 自动跳过）：
```xml
<!--BusinessMapper\BusCheckDept.xml-->
<statement id="InsertCheckDept" parameterClass="map" resultClass="int">
  <![CDATA[INSERT INTO BUS_CHECK_DEPT]]>
  <dynamic prepend="(">
    <isNotNull property="CheckDeptCode" prepend=",">CHECK_DEPT_CODE</isNotNull>
    <isNotNull property="CheckDeptName" prepend=",">CHECK_DEPT_NAME</isNotNull>
    <isNotNull property="RecordUserId" prepend=",">RECORD_USER_ID</isNotNull>
    <isNotNull property="RecordTime" prepend=",">RECORD_TIME</isNotNull>
    <isNotNull property="DeleteFlag" prepend=",">DELETE_FLAG</isNotNull>
    <isNotNull property="ValidDate" prepend=",">VALID_DATE</isNotNull>
    <isNotNull property="AlarmDate" prepend=",">ALARM_DATE</isNotNull>
  </dynamic>
  <dynamic prepend=") VALUES (">
    <isNotNull property="CheckDeptCode" prepend=",">#CheckDeptCode#</isNotNull>
    ...同上对应...
  </dynamic>
  <![CDATA[)]]>
</statement>
```

后台调用：
```csharp
var param = new Dictionary<string, object>();
param.Add("CheckDeptCode", code);
param.Add("CheckDeptName", name);
param.Add("RecordUserId", userId);
param.Add("RecordTime", DateTime.Now);
param.Add("DeleteFlag", 0);
if (validDate.HasValue) param.Add("ValidDate", validDate);   //null 不加入字典
if (alarmDate.HasValue) param.Add("AlarmDate", alarmDate);
deptManager.InsertByStatement("InsertCheckDept", param);
```

> `InsertByStatement(string stmtId, object param)` 确认在 `BaseManager<T>` 第 207 行。

### 规律总结
**BasicMapper 的 Insert（parameterMap 机制）适合字段全非空的实体**。一旦给实体加了可空字段且新增时可能为 null，就应该改用 `InsertByStatement` + BusinessMapper 自定义动态 SQL。

## 二、补充：null 的第二症状——参数错位，与轻量兜底方案（2026-08，Mould 项目验证）

null 字段除空引用外还有**第二种症状**：若 null 字段是 string 类型且位置靠前，动态 `<isNotNull>` 会少生成一列，而 parameterMap 仍按**原顺序**绑定 SQL 里的 `?` 占位符 → **后续所有字段整体左移一位，数据落到错误的列里**（不报错，更隐蔽）。

### 轻量兜底（可空字段只有一两个 string 时）
不想新写 BusinessMapper 插入语句，可在 .cs 端把可空 string 字段兜底成空串再走 BasicMapper Insert（全字段非 null → 动态列数与 parameterMap 参数数一致，不会错位）：
```csharp
//Remark 兜底空串：Insert 走 parameterMap 位置绑定，null 会导致动态列与参数错位
string remark = addOrEdit_Remark.Text == null ? "" : addOrEdit_Remark.Text;
```
注意：**只对 string 型可空字段有效**（空串对 NVARCHAR 列合法）；`DateTime?`/`int?` 型可空字段无法兜底（没有合法的"空值"），仍必须走 InsertByStatement 方案。另外自增主键 OBJID 不进 parameterMap（生成器模板本来就不含它），无此问题。

## 三、DirectMethod 参数为 null 的防护

### 现象
`public void SaveDept(object objid)` 报 `Object reference not set to an instance of an object`，因为 `objid` 是 null。

### 根因
前端新增时 `hidden_edit_objid.setValue('')`（空字符串），Ext.NET DirectMethod 把空字符串序列化成 `null` 传给后台，`objid.ToString()` 空引用。

### 解决

**前端**：新增时用 `'0'` 占位，不用空字符串：
```javascript
var btnAddClick = function () {
    App.hidden_edit_objid.setValue('0');   //不用 ''
    ...
};
```

**后台**：先做 null 防护，再用字符串判断：
```csharp
[DirectMethod]
public void SaveDept(object objid)
{
    string objidStr = (objid == null) ? "0" : objid.ToString();  //null 防护
    ...
    if (objidStr == "0") { /*新增*/ } else { /*编辑，Convert.ToInt32(objidStr)*/ }
}
```

### 规律总结
所有接收前端传值的 DirectMethod 参数（尤其是 object/string 类型），**必须先做 null 防护**再使用。Ext.NET 对空字符串/空值的序列化行为不可靠。服务端控件取值同理：`field.Value == null ? "" : field.Value.ToString()`。

## 四、Ext.NET 弹窗内 Container+ColumnLayout 嵌套导致日期控件框显示异常

### 现象
添加/编辑弹窗里的 DateField 控件框显示异常（高度塌陷/无边框/错位）。

### 根因
把两个 DateField 包在 `<ext:Container Layout="ColumnLayout">` 里各占 `.5` 宽度：
```xml
<!--❌ 错误写法-->
<ext:Container runat="server" Layout="ColumnLayout">
    <Items>
        <ext:DateField ID="dfValidDate" ColumnWidth=".5" .../>
        <ext:DateField ID="dfAlarmDate" ColumnWidth=".5" .../>
    </Items>
</ext:Container>
```
ColumnLayout 容器不会自动给子表单控件设置正确高度和字段间距。

### 解决：去掉 Container，DateField 各自独立成行
弹窗是 `Layout="Form"`，Form 布局会自动垂直堆叠并正确渲染每个字段：
```xml
<!--✅ 正确写法-->
<ext:Window ... Layout="Form">
    <Items>
        <ext:TextField ID="txtCode" .../>
        <ext:TextField ID="txtName" .../>
        <ext:DateField ID="dfValidDate" FieldLabel="有效期" LabelAlign="Right" Format="yyyy-MM-dd" />
        <ext:DateField ID="dfAlarmDate" FieldLabel="预警日期" LabelAlign="Right" Format="yyyy-MM-dd" />
    </Items>
</ext:Window>
```

### 规律总结
**Ext.NET 弹窗（Layout="Form"）内的表单控件不要嵌套 Container+ColumnLayout**，直接平铺让 Form 布局垂直排列。需要横排两个字段时，要么增大弹窗宽度改竖排，要么用 HBoxLayout（需正确配置子项高度）。

## 五、DateField 不支持 ToolTip 子元素

### 现象
报错 `Ext.Net.DateField 的 ToolTip 属性不能声明为内部属性，必须将它声明为特性`。

### 根因
`<ext:DateField>` 不支持 `<ToolTip>` 子元素（只有 Button、ImageCommand 等控件支持）。

### 解决
把提示文案挪到 `EmptyText` 属性（输入框空时显示灰色提示）：
```xml
<ext:DateField ID="dfUploadValid" ... EmptyText="不填保留原值" />
```

## 六、参考页面

- `Plugins/EquipManage/Measure/BusCheckDeptManage.aspx(.cs)` — 检定机构管理（以上三个坑都在此页遇到）
- `Plugins/Mould/Equip/MouldModifyType.aspx(.cs)` — 模具改造类型维护（第五节错位兜底在此页验证）

## 七、关联文档

- `button-permission.md` — 权限定义（权限名与按钮 Text 一致）
- `mes-crud-maintain-page-guide.md` — 维护页面通用开发指南（Insert 兜底属于其中一环）
- `extnet-grid-datecolumn-pitfall.md` — Grid 时间列空白坑（同为"取值/解析不可靠"主题）
