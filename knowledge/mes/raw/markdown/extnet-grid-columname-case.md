---
title: Ext.NET GridPanel 列名大小写不匹配导致显示空
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, 踩坑, Store, DataIndex, 列名, 大小写, resultClass, SELECT, HPP_SEMIS]
status: active
updated: 2026-08-29
---
# Ext.NET GridPanel 列名大小写不匹配导致显示空

> resultClass="Row" + SELECT t1.* 返回 DB 原始列名（HPP_SEMIS_*/SBM_* 建表全大写），而 ModelField Name 与 DataIndex 大小写敏感——按惯例写 PascalCase 就匹配不到、列显示空。修复 = ModelField/DataIndex/record.get 一致化改大写，别名列（如 LEFT JOIN ssb_user 的 real_name）保持小写；Ppt_*（Mix）建表即 PascalCase 故不受影响。

## 一、背景

在 Semi 项目中新建页面时，用 `BusinessMapper` 的 `resultClass="Row"` + `SELECT t1.* FROM HPP_SEMIS_xxx` 返回 DataTable 并绑到 Ext.NET Store。

前端的 Store ModelField Name 和 Column DataIndex 按惯例写了 **PascalCase**（`PlanDate`、`MaterName`…），但实际数据列名来自建表语句，`HPP_SEMIS_*` 表的列名全部是 **UPPERCASE**（`PLAN_DATE`、`MATER_NAME`…）。

大小写对不上 → Ext.NET 匹配不到数据 → 列显示为空。

## 二、根因

| 查询方式 | 返回列名来源 | 示例列名 |
|---------|------------|---------|
| `resultClass="Row"` + `SELECT t1.*` | DB 原始列名 | `PLAN_DATE`（全大写） |
| `resultClass="Row"` + `SELECT t1.PLAN_DATE AS PlanDate` | SQL 别名 | `PlanDate`（按别名） |
| `resultMap="R_XXX"` + entity 映射 | resultMap `column` 属性 | 取决于 mapper 定义 |

而 Ext.NET Store 的 ModelField Name 和 Column DataIndex 是**大小写敏感**的，必须与返回的列名严格一致。

## 三、为什么 Mix 的 RubOutPlan 能用 PascalCase？

Mix 表 `Ppt_RubOutPlan` 建表时列名就是 PascalCase（`PlanId`、`PlanDate`、`RubName`…），所以 `SELECT *` 直接返回 PascalCase，ModelField 也用 PascalCase，恰好匹配。

但 Semi 的 `HPP_SEMIS_RUBOUTPLAN` 建表列名是 `PLAN_ID`、`PLAN_DATE`、`MATER_NAME`…（全大写）。

## 四、排查方法

已知 ModelField → 查对应列是否为空 → 核对原始 SQL 返回列名。

```bash
# Semi 同类型页面（用 SELECT t1.* 的）全用大写，验证约定
grep -n "ModelField Name" Plugins/Semi/Storage/SMLocation.aspx | head
grep -n "ModelField Name" Plugins/Semi/Produce/SemiReturnRubber.aspx | head
```

## 五、修复

**一致化**：Store ModelField/DataIndex 全部改为与 `SELECT t1.*` 一致的大写列名。

```text
# 改动前
<ext:ModelField Name="PlanDate" />         ← 不匹配
DataIndex="PlanDate"                         ← 不匹配

# 改动后
<ext:ModelField Name="PLAN_DATE" />          ← 匹配
DataIndex="PLAN_DATE"                        ← 匹配
```

JS 中 `record.get(...)` 同步改为大写：
```javascript
// 改动前
record.get("PlanId")
record.get("Outnum")
record.get("ActOutnum")

// 改动后
record.get("PLAN_ID")
record.get("OUTNUM")
record.get("ACT_OUTNUM")
```

`real_name`（来自 `LEFT JOIN ssb_user`）保持小写，因为是别名列。

## 六、相关文件模式

| 表前缀 | 列名风格 | 页面 ModelField 风格 |
|-------|---------|-------------------|
| `HPP_SEMIS_*` | 全大写 | 全大写匹配 |
| `SBM_*` | 全大写 | 全大写匹配 |
| `Ppt_*` (Mix) | PascalCase | PascalCase 匹配 |
