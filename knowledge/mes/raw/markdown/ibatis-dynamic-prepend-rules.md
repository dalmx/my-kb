---
category: 技术-.NET
factory: 通用
module: iBATIS
status: active
tags: [iBATIS, MyBatis, dynamic, prepend, isNotNull, isNotEmpty, AND, 连接词, 踩坑, 复刻手册]
title: iBATIS dynamic 标签 prepend 连接词规则（AND AND / 缺 AND 踩坑）
updated: 2026-09-02
---

# iBATIS dynamic 标签 prepend 连接词规则（AND AND / 缺 AND 踩坑）

> iBATIS.NET（MyBatis.DataMapper）的 `<dynamic>` + `<isNotNull>`/`<isNotEmpty>` 动态 SQL 拼接，连接词 `AND` 怎么加、加在哪，是高频踩坑点。本文给出**唯一正确的标准写法**，源自实战（同一处过滤条件连续改了三版才对）。

## 一、三种错误写法（都踩过）

假设要拼 `WHERE a='1' [AND b>=#x#] [AND c<=#y#]`（方括号为可选条件）。

### ❌ 错误 1：CDATA 里写 AND + 子元素无 prepend → `AND AND`

```xml
<dynamic prepend="AND">
    <isNotNull property="BeginTime">
        <![CDATA[AND t.Used_time >= #BeginTime#]]>   <!-- CDATA 里多了 AND -->
    </isNotNull>
</dynamic>
```
**结果**：`WHERE a='1' AND AND t.Used_time >= ...`（两个 AND 重复）
**原因**：`<dynamic prepend="AND">` 已在块前注入一个 AND，CDATA 里再写一个就重复。

### ❌ 错误 2：首个子元素不写 prepend → 条件间缺 AND

```xml
<dynamic prepend="AND">
    <isNotNull property="BeginTime">                 <!-- 首个不写 prepend -->
        <![CDATA[t.Used_time >= #BeginTime#]]>
    </isNotNull>
    <isNotNull property="EndTime" prepend="AND">     <!-- 只有第二个写 -->
        <![CDATA[t.Used_time <= #EndTime#]]>
    </isNotNull>
</dynamic>
```
**结果**：`WHERE a='1' AND t.Used_time >= @p0  t.Used_time <= @p1`（两条件间缺 AND）
**原因**：`<dynamic>` 的 prepend 只作用于**整个块前**（块与前面 SQL 的连接），**不会传递给块内子元素之间**。首个子元素不写 prepend，它和后续子元素之间就没有连接词。

### ❌ 错误 3：误以为 dynamic 会自动给首个子元素加 prepend

这是对 iBATIS 机制的常见误解。`<dynamic>` 的 prepend **只在块前出现一次**（连接前面的 SQL），块内子元素之间的连接**完全靠子元素各自的 prepend**。

## 二、✅ 唯一正确写法（现网标准）

**每个动态子元素都带 `prepend="AND"`，包括第一个；CDATA 内绝不写 AND。**

```xml
WHERE a = '1'                              <!-- 固定条件，写死 -->
<dynamic prepend="AND">                    <!-- 块前 AND：连接前面的 WHERE -->
    <isNotNull property="BeginTime" prepend="AND">     <!-- 每个都带 prepend="AND" -->
        <![CDATA[t.Used_time >= #BeginTime#]]>         <!-- CDATA 内无 AND -->
    </isNotNull>
    <isNotNull property="EndTime" prepend="AND">
        <![CDATA[t.Used_time <= #EndTime#]]>
    </isNotNull>
    <isNotEmpty property="Barcode" prepend="AND">
        <![CDATA[t.S_barcode LIKE '%' + #Barcode# + '%']]>
    </isNotEmpty>
</dynamic>
```

**为什么首个子元素也带 prepend 不重复？** iBATIS 的机制：`<dynamic>` 会把**首个有效子元素的 prepend 抑制**（用 dynamic 自己的 prepend 代替），后续子元素的 prepend 正常生效。所以全带 `prepend="AND"` 是安全的——无论哪些条件有效，连接词既不缺失也不重复。

### 现网范例

`P.Mix/.../PptLot.xml`、`P.Mix/.../PpmReturnrubber.xml` 等所有多条件 dynamic 都是这种写法：
```xml
<dynamic prepend="WHERE">
    <isNotNull property="where.ObjId" prepend="AND">   <!-- 全带 prepend="AND" -->
        <![CDATA[ObjID = #where.ObjId#]]>
    </isNotNull>
    <isNotNull property="where.Barcode" prepend="AND">
        <![CDATA[Barcode = #where.Barcode#]]>
    </isNotNull>
    ...
</dynamic>
```

## 三、prepend 机制速查

| 标签 | prepend 作用时机 | 注入位置 |
|---|---|---|
| `<dynamic prepend="X">` | 块内有任意有效子元素时 | **整个块前**注入一个 X（连接前面的 SQL） |
| 子元素（isNotNull 等）`prepend="X"` | 该子元素有效时 | **该子元素前**注入 X |
| 首个有效子元素的 prepend | 被 dynamic 的 prepend 抑制 | 不重复注入 |
| 后续有效子元素的 prepend | 正常生效 | 各自前注入 |

## 四、dynamic prepend="WHERE" vs "AND" 的选择

| 场景 | 写法 |
|---|---|
| 前面**没有** WHERE（dynamic 是唯一条件来源） | `<dynamic prepend="WHERE">` |
| 前面**已有** WHERE（有固定条件 + 动态条件） | `<dynamic prepend="AND">` |

```xml
<!-- 情况1：纯动态条件 -->
<select id="...">
    SELECT ... FROM T
    <dynamic prepend="WHERE">           <!-- 无固定 WHERE，dynamic 提供 WHERE -->
        <isNotNull property="X" prepend="AND">...</isNotNull>
    </dynamic>
</select>

<!-- 情况2：固定条件 + 动态条件（本文主场景） -->
<select id="...">
    SELECT ... FROM T WHERE a='1'       <!-- 已有 WHERE + 固定条件 -->
    <dynamic prepend="AND">             <!-- dynamic 提供 AND 连接 -->
        <isNotNull property="X" prepend="AND">...</isNotNull>
    </dynamic>
</select>
```

## 五、与 `<isEqual>` 的兼容性坑

用 `GetDataTableByStatement` + Dictionary 参数时，**禁用 `<isEqual>`**（对 Dictionary 参数有 NullReferenceException bug），改用 `<isNotNull>` + SQL 直接比较。详见 `mcui-to-handwritten-aspx-full-pattern.md` 坑1。

## 六、调试技巧：看实际生成的 SQL

iBATIS 动态拼接出错时，报错信息（如 `关键字 'AND' 附近有语法错误`）会带**实际生成的 SQL**。据此反推是「多 AND」还是「缺 AND」：

- `AND AND` → CDATA 里写了 AND，删掉
- `条件1  条件2`（中间空格无 AND）→ 子元素漏写 `prepend="AND"`
- 单独一个条件正常，多条件出错 → prepend 机制没理解对，回到第二节标准写法

## 七、关联文档

- `mix-project-dev-conventions.md` —— Mix 项目开发约定（本文规则的落地场景）
- `mcui-to-handwritten-aspx-full-pattern.md`—— `<isEqual>` 对 Dictionary 的 bug
- `extnet-GetDataTableByStatement-ImageCommand.md`—— GetDataTableByStatement 参数平级引用规则
- `ibatis-statement-naming-and-getpagedatabyreader-pitfall.md` —— Statement 命名 + GetPageDataByReader 陷阱

## 八、补充变体坑：裸 CDATA 文本放 dynamic 内当前置条件 → 首个标签条件缺 AND（2026-08-26 实证）

**错误写法**（把固定条件作为裸文本放 `<dynamic prepend="WHERE">` 内第一个元素）：

```xml
<!-- ❌ 生成 WHERE T1.DELETE_FLAG = 0  T1.PARAM_FIELD = @p（缺 AND，SQL 语法错） -->
<dynamic prepend="WHERE">
    <![CDATA[T1.DELETE_FLAG = 0]]>
    <isNotNull property="where.PARAM_FIELD" prepend="AND">
        <![CDATA[T1.PARAM_FIELD = #where.PARAM_FIELD#]]>
    </isNotNull>
</dynamic>
```

**根因**：dynamic 的"首个有效子元素 prepend 抑制"机制把**第一个标签**（isNotNull）的 `AND` 剥掉（dynamic 的 prepend="WHERE" 已被用于 WHERE 本身，无处补偿）——裸文本不是标签、没被算作首元素，真正的首标签反而中招。

**判别信号**：调试日志里 WHERE 后两个条件之间**空两格没有 AND**（`0  T1.XXX`）＝ 撞此变体；只传一个可选条件时报 `"xx"附近有语法错误`（xx=第一个可选条件涉及的表别名，如 `DATEADD(...) t2.TYRE_MATERIAL_NAME LIKE` 报 `"t2"附近有语法错误`）也查这里。

**正解一（2026-08-26 实证：Molding BpmSpliceParamLimit/BpmSpliceMaterialLimit）**——固定条件写死在 SQL 本体，dynamic 只管动态条件：

```xml
<!-- ✅ 固定条件写死在 SQL 本体，dynamic 带 prepend="AND" 连接 -->
WHERE T1.DELETE_FLAG = 0
<dynamic prepend="AND">
    <isNotNull property="where.PARAM_FIELD" prepend="AND">...</isNotNull>
</dynamic>
```

**正解二（2026-09-02 实证：Molding MoldMaterialScanQuery）**——固定条件搭"页面常传参数"的便车，合并进**第一个条件子元素**的 CDATA：

```xml
<!-- ✅ 固定条件随 BeginDate（页面必填常传）一并输出；后续条件各带 AND -->
<dynamic prepend="WHERE">
    <isNotNull property="BeginDate" prepend="AND">
        <![CDATA[T1.LOG_TYPE = '0008' AND T1.LOG_RESULT = '成功' AND T1.RECORD_TIME >= #BeginDate#]]>
    </isNotNull>
    <isNotNull property="EndDate" prepend="AND">
        <![CDATA[T1.RECORD_TIME < DATEADD(DAY, 1, #EndDate#)]]>
    </isNotNull>
    <isNotEmpty property="CardNo" prepend="AND">
        <![CDATA[T1.CARD_NO = #CardNo#]]>
    </isNotEmpty>
</dynamic>
```

前提：所搭车的 property（如时间范围 BeginDate）由页面**始终传值**（BuildParam 无条件加入字典），否则固定条件会随参数缺失而丢失——须在 XML 注释里注明此依赖。两版正解都现网验证通过；同一 mapper 的报表语句与基础 CRUD 的 includeSelect/includeWhere 重名时，新增语句用独立 fragment id（如 includeWhereMaterialScan）并选正解一/二皆可。

**元教训（2026-09-02）**：写含固定条件的 dynamic 前先通读本文——第八节 2026-08-26 已记录此坑，MoldMaterialScanQuery 首写仍重踩（技能避坑速查引用了本文却只看速查行没读全文）。凡速查表里标注"详见 KB xxx"的坑，动手前把目标文档读完。
