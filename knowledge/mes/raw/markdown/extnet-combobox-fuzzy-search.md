---
title: Ext.NET ComboBox 本地模糊搜索与远程数据加载
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, ComboBox, 模糊搜索, 下拉框, 下拉框过滤, 输入过滤, 边输入边过滤, 自动补全, 联想输入, TypeAhead, AnyMatch]
updated: 2026-08-29
status: active
---
# Ext.NET ComboBox 本地模糊搜索与远程数据加载

> Ext.NET ComboBox 两种数据过滤模式：本地模糊搜索（数据预加载 + TypeAhead 联想过滤）与远程数据加载的选型与实现。

## 一、本地模糊搜索（数据预加载到本地）

适用于数据量不大、不频繁变动的下拉框。

### aspx

```aspx
<ext:ComboBox ID="cboRubName" runat="server" FieldLabel="胶料名称" 
    Editable="true" TypeAhead="true" AnyMatch="true"
    EmptyText="输入名称搜索...">
    <Triggers>
        <ext:FieldTrigger Icon="Clear" Hidden="true" />
    </Triggers>
    <Listeners>
        <Select Handler="this.getTrigger(0).show();" />
        <BeforeQuery Handler="this.getTrigger(0)[this.getRawValue().toString().length == 0 ? 'hide' : 'show']();" />
        <TriggerClick Handler="if (index == 0) { this.clearValue(); this.getTrigger(0).hide(); }" />
    </Listeners>
</ext:ComboBox>
```

### 后端 Page_Load 加载数据

```csharp
protected void Page_Load(object sender, EventArgs e)
{
    if (IsPostBack || X.IsAjaxRequest) return;
    InitRubName();
}

private void InitRubName()
{
    DataTable dt = manager.GetDataTableByStatement("GetRubNameList", null);
    if (dt != null && dt.Rows.Count > 0)
    {
        foreach (DataRow row in dt.Rows)
        {
            string name = row["RubName"].ToString();
            if (!string.IsNullOrEmpty(name))
            {
                cboRubName.Items.Add(new Ext.Net.ListItem(name, name));
            }
        }
    }
}
```

### Mapper 语句

```xml
<select id="GetRubNameList" parameterClass="map" resultClass="row">
  <![CDATA[SELECT DISTINCT LEFT(Mater_name, 6) AS RubName 
  FROM Pmt_material WHERE Mkind_code IN ('3','4','5','6') ORDER BY RubName]]>
</select>
```

### 关键属性

| 属性 | 说明 |
|------|------|
| `Editable="true"` | 允许用户输入 |
| `TypeAhead="true"` | 自动补全 |
| `AnyMatch="true"` | **任意位置**子串匹配（否则只从开头匹配） |
| `FieldTrigger Icon="Clear"` | 清除按钮，选值后显示 |
| `Hidden="true"` | 触发器初始隐藏（非 `HideTrigger`） |

## 二、远程搜索（通过 Store + DirectFn）

适用于数据量大、需要服务端分页的场景。

### aspx

```aspx
<ext:ComboBox ID="cboRubName" runat="server"
    DisplayField="RubName" ValueField="RubName"
    Editable="true" TypeAhead="true" MinChars="1"
    QueryMode="Remote" PageSize="20">
    <Store>
        <ext:Store ID="storeRubName" runat="server" AutoLoad="false">
            <Proxy>
                <ext:PageProxy DirectFn="App.direct.GetRubNameList" />
            </Proxy>
            <Model>
                <ext:Model runat="server">
                    <Fields>
                        <ext:ModelField Name="RubName" />
                    </Fields>
                </ext:Model>
            </Model>
        </ext:Store>
    </Store>
</ext:ComboBox>
```

## 三、常见错误

- `HideTrigger="true"` → 应改为 `Hidden="true"`
- `resultClass="Row"`（大写R）→ 应改为 `resultClass="row"`（小写，与 GetEquipGroup 一致）
- `QueryMode="Remote"` 时 Mapper 参数需用平级 `#RubName#` 而非嵌套 `#where.RubName#`

## 四、常见问法

- **"下拉框想边输入边过滤选项" / "下拉框输入时自动筛选" / "输入关键字带出选项"** → 场景一：`Editable="true" + TypeAhead="true" + AnyMatch="true"` 三属性组合（数据预加载到本地时）。
- **"下拉框支持搜索吗？" / "选项太多翻不过来想输入过滤"** → 数据量小、不常变动用场景一（本地模糊搜索）；数据量大、需服务端分页用场景二（Store + DirectFn 远程搜索）。
- **"输入过滤只能从头匹配"** → 加 `AnyMatch="true"`（默认只从开头匹配，任意位置子串匹配需显式开启）。
