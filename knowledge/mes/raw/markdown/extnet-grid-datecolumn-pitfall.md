---
title: Ext.NET Grid 时间列（DateColumn）显示空白踩坑
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, DateColumn, ModelField, 时间列, 解析失败, 显示空白, 服务端分页, CONVERT, 踩坑, Grid]
updated: 2026-08-21
status: active
---
# Ext.NET Grid 时间列（DateColumn）显示空白踩坑

> 沉淀场景：Grid 里加一列显示数据库 datetime 字段（带时分秒），用 `DateColumn` + `Format`，结果列整列空白。原因是 Store ModelField 上多声明了 `Type="Date"` + `DateFormat`，把原始值按固定格式解析失败。

## 一、现象

把某列从普通 `Column`（只显示日期）改成 `DateColumn`（要显示时分秒），数据明明查出来了，但前端整列空白。

## 二、错误写法（会空白）

```aspx
<ext:Store ID="gridStore" runat="server">
    <Model>
        <ext:Model ID="model1" runat="server">
            <Fields>
                <!-- ❌ 在 ModelField 上声明 Type=Date + DateFormat -->
                <ext:ModelField Name="SHIFT_DATE" Type="Date" DateFormat="yyyy-MM-dd HH:mm:ss" />
            </Fields>
        </ext:Model>
    </Model>
</ext:Store>
...
<ext:DateColumn runat="server" Text="生产时间" DataIndex="SHIFT_DATE" Format="yyyy-MM-dd HH:mm:ss" />
```

## 三、正确写法（不空白）

```aspx
<ext:Store ID="gridStore" runat="server">
    <Model>
        <ext:Model ID="model1" runat="server">
            <Fields>
                <!-- ✅ ModelField 不声明类型，原始值透传 -->
                <ext:ModelField Name="SHIFT_DATE" />
            </Fields>
        </ext:Model>
    </Model>
</ext:Store>
...
<!-- DateColumn 负责渲染格式即可 -->
<ext:DateColumn runat="server" Text="生产时间" DataIndex="SHIFT_DATE" Format="yyyy-MM-dd HH:mm:ss" Width="150" Align="Center" />
```

## 四、原理

Ext.NET 的 `ModelField` 有两个作用层次，容易混淆：

| 层次 | 位置 | 作用 |
|------|------|------|
| **读取/解析层** | `ModelField` 的 `Type` + `DateFormat` | 把后端返回的原始值（字符串）**解析**成 JS Date 对象 |
| **显示/渲染层** | `DateColumn` 的 `Format` | 把 Date 对象**格式化**成显示字符串 |

- 后端 datetime（SQL Server）经 iBATIS → DataTable → JSON 回到前端时，字符串格式**不固定**：可能是 `2026-07-14T08:30:00`、`7/14/2026 8:30:00 AM`、`2026-07-14 08:30:00` 等，取决于序列化路径。
- 在 `ModelField` 上写死 `DateFormat="yyyy-MM-dd HH:mm:ss"`，等于要求原始字符串**严格**是这个格式。一旦实际格式带 `T` 或带 `AM/PM` 或用 `/` 分隔，`Date.parse` 失败 → 返回 `null`/`Invalid Date` → 列显示空白。
- `DateColumn.Format` 只作用于**渲染**，它对输入值是 `null` 没有救援能力——值在解析阶段已经丢了。

**结论**：`ModelField` 不要轻易声明 `Type="Date"`，除非你能保证后端返回的原始字符串格式与 `DateFormat` 完全一致。否则保持默认（auto）让值原样透传成字符串/Date，由 `DateColumn.Format` 负责显示格式即可。

## 五、第三方案：服务端分页场景直接 SQL 输出字符串 + 普通 Column（2026-08 补充，Mould 项目验证）

**服务端分页**（`PageProxy DirectFn` + `GetPageDataByReader` 返回 `new { data, total }`）的场景下，datetime 走 DirectMethod JSON 序列化，格式不确定性最大（不同 Ext.NET 版本行为不同，且项目内可能没有可抄的先例）。此时最稳的做法是**彻底绕开解析层**：

```xml
<!-- BusinessMapper 的 GetPageData：SQL 输出侧转成固定格式字符串 -->
<select id="GetPageData" parameterClass="map" resultClass="Row">
  <![CDATA[SELECT
  OBJID,
  ...,
  CONVERT(VARCHAR(19), RecordTime, 120) AS RecordTime
  FROM tb_XXX]]>
  ...
</select>
```

```aspx
<!-- ModelField 普通声明 + 普通Column 直接显示字符串，所见即所得 -->
<ext:ModelField Name="RecordTime" />
...
<ext:Column runat="server" Text="录入时间" DataIndex="RecordTime" Width="150" Align="Center" />
```

要点：
- `CONVERT(..., 120)` 是 `yyyy-mm-dd hh:mi:ss` 标准格式，显示即所需，无解析环节，**不可能空白**。
- 只在 **SELECT 输出侧**做 CONVERT，不违反"WHERE 字段侧禁函数"的性能原则（不涉及过滤与索引）。
- 代价：该列在前端不可再当 Date 参与排序/筛选（字典维护类小表无此需求；报表大表需要时间排序时仍用方案三的 ModelField 透传 + DateColumn）。

**选型**：客户端绑定（DataSource/DataBind）→ 第三节写法即可；服务端分页 DirectFn → 优先第五节方案。

## 六、判断方法

时间列空白时，先排查这两步：

1. **F12 看接口返回 JSON** 里该字段的实际字符串长什么样（确认数据有、确认格式）。
2. 对照 `ModelField` 的 `DateFormat` 是否与该字符串匹配。
   - 不匹配 → 去掉 `ModelField` 的 `Type`/`DateFormat`，只留 `DateColumn.Format`。
   - 字段根本没返回 → 查 SQL 是否 select 了该列。

## 七、关联

- DateColumn 的正确正面示例（ModelField 无类型声明）：见 `quality-report-dev-guide.md`、`standard-report-template.md`
- DateField（查询条件日期框）的 Format 与 daterange 联动：见 `extnet-datefield-range-and-month.md`
- 班次（SHIFT_NAME）取值来源与 SSB_SHIFT 字典：见 `shift-value-source.md`
- 本坑的实际出处：`Plugins/Batch/BatchTracing/BatchComponentTracing.aspx`（部材批量追溯页"生产时间"+"班次"列）
- 第五节方案出处：`Plugins/Mould/Equip/MouldModifyType.aspx(.cs)`（模具改造类型维护页）；维护页整体套路见 `mes-crud-maintain-page-guide.md`
