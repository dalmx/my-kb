---
title: McUI 报表 DetailGrid 行展开明细（UNION ALL 多源明细 + WHERE EXISTS 控制分隔行）
category: 技术-.NET
module: McUI
factory: 通用
tags: [McUI, DetailGrid, 行展开明细, UNION ALL, WHERE EXISTS, iBATIS, 报表模板, Quality, 配置化]
updated: 2026-08-23
status: active
related: [main-mcui-config-framework.md]
---
# McUI 报表 DetailGrid 行展开明细（UNION ALL 多源明细 + WHERE EXISTS 控制分隔行）

> McUI 配置式报表（`McUI/Report.aspx` 模板）的主表每行展开一个**明细弹窗**，展示该行的子记录（如某胎号的一检/修理明细）。全部靠两个 XML 节点驱动，不写 aspx/js。
>
> 本文记 `ReportFqFacecheckInfoTwo`（外观检测信息 Two）加明细的实际案例与踩坑点。

## 一、核心机制：两套"明细"，别混

McUI 报表有**两个**名字相近、用途不同的东西，极易混淆：

| 后缀 | UI 节点 | 触发方式 | 数据来源 select id | 用途 |
|------|---------|----------|---------------------|------|
| `@MainDetail` | **无**（框架自带的 East 侧栏 `panelMainDetail`） | `ShowFieldsInfo` 命令 | `Select@<Name>@MainDetail` | 主表行字段太多，点"信息"图标在**右侧折叠面板**展开字段清单 |
| `@DetailGrid` | `<DetailGrid><GridColumns>` | `ShowDetail` 命令 | `Select@<Name>@DetailGrid` | **本篇主角**：弹出 `winDetail` 窗口，展示一个**子表 Grid** |

**踩坑**：`ReportFqFacecheckInfoTwo.Mapper.xml` 初始自带了一个占位的 `Select@...@MainDetail`（SELECT `FQX_XCHECK_INFO`），但它**没有任何 UI 节点驱动、全项目无引用**，是模板复制时残留的死代码，加明细时一并删掉，避免误导。

## 二、所需改动（仅 2 个 XML 节点）

### 2.1 UI 配置 `<Name>.xml`：加 `<DetailGrid>` 节点

在 `<Select>` 下、`</MainGrid>` 之后加：

```xml
<Select>
  <MainGrid OrderString="T1.RECORD_TIME">
    <GridColumns>...主表列...</GridColumns>
  </MainGrid>

  <!-- 新增：明细弹窗的列定义 -->
  <DetailGrid Width="700">
    <GridColumns>
      <GridColumn ColumnName="TYRE_NO"      Width="150"></GridColumn>
      <GridColumn ColumnName="RECORD_TIME"  Width="150"></GridColumn>
      <GridColumn ColumnName="DEFECT_NAME"  Width="120"></GridColumn>
      <GridColumn ColumnName="USER_NAME" Width="100" Caption="操作人员"></GridColumn>
    </GridColumns>
  </DetailGrid>
</Select>
```

框架据此自动在主表每行生成"明细"命令按钮，点击弹 `winDetail` 窗口渲染该子 Grid。列标题取 `<Captions>` 里同名字段，**无需新建 Captions**。

### 2.2 SQL 配置 `<Name>.Mapper.xml`：加 `@DetailGrid` select

```xml
<select id="Select@<Name>@DetailGrid" parameterClass="map" resultClass="row">
  <!-- 明细 SQL，主表当前行所有字段以 where.字段名 注入 -->
</select>
```

**关键**：框架把主表当前行整条 record 注入为 `where.<列名>`。用 `where.TYRE_NO`（本表主键）过滤，**不要**把样例里的硬编码胎号 `'S339360VPXG00000'` 留下。

## 三、UNION ALL 多源明细的写法

业务要在一个明细窗里把"一检记录 + 修补记录 + 修理记录"按时间混排。用 `UNION ALL`，每段独立加动态过滤：

```xml
<select id="Select@ReportFqFacecheckInfoTwo@DetailGrid" parameterClass="map" resultClass="row">
  <![CDATA[
  SELECT T1.TYRE_NO, T1.RECORD_TIME, T16.DEFECT_NAME, T8.real_name AS USER_NAME
  FROM FQF_FCHECK_INFO T1
  LEFT JOIN SSB_USER T8 with(nolock) ON T1.RECORD_USER_ID = T8.work_barcode
  LEFT JOIN FQD_DEFECT_INFO T16 with(nolock) ON T1.DEFECT_CODE = T16.DEFECT_CODE AND T16.WORK_PROCESS_ID = '4'
  WHERE T1.DELETE_FLAG = 0
  ]]>
  <dynamic prepend="AND">
    <isNotNull property="where.TYRE_NO">
      <isNotEmpty property="where.TYRE_NO">
        <![CDATA[T1.TYRE_NO = #where.TYRE_NO#]]>
      </isNotEmpty>
    </isNotNull>
  </dynamic>

  <!-- 修补记录分隔行：仅当存在修理记录时才输出（见第四节） -->
  <![CDATA[
  UNION ALL
  SELECT '修补记录', NULL, NULL, NULL
  WHERE EXISTS (
      SELECT 1 FROM FQR_REPAIR_RECORDS T9 WHERE T9.DELETE_FLAG = 0
  ]]>
  <dynamic prepend="AND">
    <isNotNull property="where.TYRE_NO">
      <isNotEmpty property="where.TYRE_NO">
        <![CDATA[T9.TYRE_NO = #where.TYRE_NO#]]>
      </isNotEmpty>
    </isNotNull>
  </dynamic>
  <![CDATA[
  )
  ]]>

  <![CDATA[
  UNION ALL
  SELECT T0.TYRE_NO, T0.RECORD_TIME, '', T3.real_name
  FROM FQR_REPAIR_RECORDS T0
  LEFT JOIN SSB_USER T3 ON T0.RECORD_USER_ID = T3.work_barcode
  WHERE T0.DELETE_FLAG = 0
  ]]>
  <dynamic prepend="AND">
    <isNotNull property="where.TYRE_NO">
      <isNotEmpty property="where.TYRE_NO">
        <![CDATA[T0.TYRE_NO = #where.TYRE_NO#]]>
      </isNotEmpty>
    </isNotNull>
  </dynamic>
</select>
```

要点：
- **UNION ALL 各段列数/类型必须一致**，分隔行用 `NULL` 占位空列。
- 第一段"一检"用真实 `TYRE_NO`，分隔行用字面量 `'修补记录'`，第三段修理用真实 `TYRE_NO` —— 同一列语义混用，是业务要求的展示效果（用户明确选择"忠实原 SQL"）。
- `with(nolock)` 保留，与生产环境一致。

## 四、WHERE EXISTS：让固定分隔行"有值才显示"

问题：`UNION ALL SELECT '修补记录', NULL...` 是写死的，**无论该胎有没有修理记录都会冒一行**，误导用户。

解决：给分隔行套 `WHERE EXISTS`，判定条件跟修理记录段**完全一致**：

```sql
UNION ALL
SELECT '修补记录', NULL, NULL, NULL
WHERE EXISTS (
    SELECT 1 FROM FQR_REPAIR_RECORDS T9
    WHERE T9.DELETE_FLAG = 0 AND T9.TYRE_NO = #where.TYRE_NO#
)
```

→ 有修理记录：分隔行 + 修理明细行都出；没有：都不出。EXISTS 内别名换 `T9` 避免与外层 `T0` 冲突。

**iBATIS 动态拼接**：`WHERE EXISTS (...)` 里的 `#where.TYRE_NO#` 要走 `<dynamic prepend="AND">` 块（跟主段同结构），不能直接写死在 CDATA 里，否则主表当前行 TYRE_NO 传不进来。

## 五、列标题：用列级 Caption 覆盖，不动全局 Captions

明细的 `USER_NAME` 列想叫"操作人员"，但主表的 `USER_NAME` 列叫"检验人员"。

**错误做法**：改 `<Captions>` 里的 `USER_NAME` —— 会把主表列标题也改了。

**正确做法**：`GridColumn` 支持 `Caption` 属性（见 `ReportSpecQualityAnalyse.xml` 用法），在明细列上单独覆盖：

```xml
<GridColumn ColumnName="USER_NAME" Width="100" Caption="操作人员"></GridColumn>
```

主表同名列不受影响。`ReportSpecQualityAnalyse.xml` 大量使用 `Caption="..."` 已验证框架支持。

## 六、范例参考与关联文档

- **同框架范例**（DetailGrid + @DetailGrid 双节点齐全）：`Plugins/Quality/McUI/@McUI/ReportFqkKtCheckInfo.xml(.Mapper.xml)`（扩胎产出信息，主从 FQK_KTCHECK_INFO → FQK_KTCHECK_DETAIL，用 `where.OBJID` 过滤 `MASTER_ID`）。
- **McUI 框架全貌**：`main-mcui-config-framework.md`（9.4 节讲了 `@MainDetail` 侧栏机制，本篇是 `@DetailGrid` 弹窗机制的补充）。
- **iBATIS 动态 SQL 语法**：`<dynamic prepend>` / `<isNotNull>` / `<isNotEmpty>` / `#参数#` vs `$参数$`。

## 七、检查清单（加 DetailGrid 时的自检）

1. [ ] `<Name>.xml` 有 `<DetailGrid><GridColumns>` 节点（否则不弹窗）
2. [ ] `<Name>.Mapper.xml` 有 id 精确为 `Select@<Name>@DetailGrid` 的 select（命名约定，差一个字符都不工作）
3. [ ] 明细 SQL 用 `where.<主表列名>` 过滤，没有残留硬编码主键值
4. [ ] UNION ALL 各段列数/类型对齐
5. [ ] 固定分隔行用 `WHERE EXISTS` 控制是否输出
6. [ ] 列标题如需与主表不同，用列级 `Caption=` 覆盖，不动 `<Captions>`
7. [ ] 删掉无用的 `Select@<Name>@MainDetail` 残留（全项目 grep 确认无引用）
8. [ ] 改完清 UI 缓存（`UiHelper.ClearCache()` 或重启）再验证
