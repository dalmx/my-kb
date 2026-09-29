---
title: "openpyxl 修改 xlsx 后 C# 无法读取的兼容性修复（inlineStr + 绝对路径）"
category: 技术-.NET
module: 通用
factory: 通用
tags: [openpyxl, xlsx, OOXML, inlineStr, sharedStrings, "C#", XlsxParser, 兼容性, 踩坑, ProductionBoard]
status: active
updated: 2026-08-29
---
# openpyxl 修改 xlsx 后 C# 无法读取的兼容性修复（inlineStr + 绝对路径）

> 场景：用 Python `openpyxl` 改了一份 `.xlsx`（比如把看板配置表 `ProductionBoard.cells.xlsx` 里某些单元格从"查询"改成"导入"），保存后 C# 后端的 XML 解析器（`XlsxParser`）就读不出数据了。
>
> 记录两个根因和修复，都是 openpyxl 改了 OOXML 内部结构导致的。

---

## 一、根因 1：openpyxl 把 sharedStrings 改成了 inlineStr

### 1.1 标准 xlsx 的字符串存储

Excel 正常保存的 xlsx：所有字符串集中在 `xl/sharedStrings.xml`，单元格里只存一个索引（`<c t="s"><v>5</v></c>` 指向第 5 个共享字符串）。

```xml
<!-- xl/worksheets/sheet1.xml -->
<c r="A1" t="s"><v>5</v></c>   <!-- t="s" = shared string，v=索引 -->
```

### 1.2 openpyxl 保存后的格式

openpyxl 保存时**不用共享字符串表**，改成**内联字符串**：每个单元格直接写文本，`xl/sharedStrings.xml` 文件干脆不生成。

```xml
<!-- openpyxl 输出 -->
<c r="A1" t="inlineStr"><is><t>查询</t></is></c>
```

### 1.3 C# 解析器（按老格式写的）会怎样

如果解析器只处理了 `t="s"` + `sharedStrings.xml` 索引方式，遇到 `t="inlineStr"` 会：
- 找不到 `sharedStrings.xml` → 报错或返回空
- 或者忽略 `inlineStr` 节点 → 所有字符串值丢失

### 1.4 修复：解析器要支持 inlineStr

```csharp
// 老代码：只在 sharedStrings 里查索引
var vNode = cellNode.Element(x + "v");
string value = sharedStrings[int.Parse(vNode.Value)];

// 新代码：判断 t 属性，inlineStr 直接取内联 <t>
var t = cellNode.Attribute("t")?.Value;
if (t == "inlineStr") {
    // ⚠️ 关键：用 .//s:t 后代搜索，不是 .Element("t")
    // 因为 <is> 下可能有 <r><t>（富文本）多层结构
    var tNode = cellNode.XPathSelectElement(".//s:t", nsResolver);
    value = tNode?.Value ?? "";
} else if (t == "s") {
    // 老的共享字符串方式
    var vNode = cellNode.Element(x + "v");
    value = sharedStrings[int.Parse(vNode.Value)];
} else {
    // 数字/日期等，直接取 <v>
    value = cellNode.Element(x + "v")?.Value;
}
```

> ⚠️ **关键坑**：`inlineStr` 的文本节点路径是 `<c><is><t>` 或 `<c><is><r><t>`（富文本），层级不固定。用 `.//s:t`（后代轴搜索）比 `.Element("is").Element("t")` 稳。`s:` 是 OOXML 主命名空间前缀，要在 `XmlNamespaceManager` 里声明。

---

## 二、根因 2：openpyxl 把相对路径改成了绝对路径

### 2.1 标准 xlsx 的关系文件路径

`xl/_rels/workbook.xml.rels` 里记录 sheet 文件的**相对路径**：

```xml
<!-- 标准（Excel 保存）-->
<Relationship Id="rId1" Type=".../worksheet" Target="worksheets/sheet1.xml"/>
```

### 2.2 openpyxl 保存后的格式

openpyxl 有时把 `Target` 写成**绝对路径**（带前导 `/`）：

```xml
<!-- openpyxl 输出 -->
<Relationship Id="rId1" Type=".../worksheet" Target="/xl/worksheets/sheet1.xml"/>
```

### 2.3 C# 解析器（按相对路径拼接的）会怎样

```csharp
// 老代码：base = "xl/"，Target = "worksheets/sheet1.xml" → 拼成 "xl/worksheets/sheet1.xml" ✅
string fullPath = Path.Combine(baseDir, target);
```

但 openpyxl 输出 `Target="/xl/worksheets/sheet1.xml"`，拼接结果可能变成：
- `Path.Combine("xl/", "/xl/worksheets/sheet1.xml")` → 在 Windows 上绝对路径会**覆盖 base**，变成 `/xl/worksheets/sheet1.xml`，而 zip 里实际路径是 `xl/worksheets/sheet1.xml`（无前导 `/`）→ 找不到文件

### 2.4 修复：处理路径前缀

```csharp
string target = rel.Attribute("Target").Value;
// 修复 openpyxl 的绝对路径问题
if (target.StartsWith("/")) target = target.TrimStart('/');
// base 已经是 "xl/"，Target 可能重复带 "xl/" 前缀
if (target.StartsWith("xl/")) {
    // base 不再加 "xl/"
    fullPath = target;
} else {
    fullPath = "xl/" + target;
}
// 最后统一正斜杠
fullPath = fullPath.Replace("\\", "/");
```

---

## 三、验证流程（改完 xlsx 一定要走一遍）

1. 用 openpyxl 改 xlsx 并保存
2. 用 C# 解析器读一遍，确认数据完整
3. 把 xlsx 发到服务器，跑页面，确认配置正确加载
4. 改完后端解析逻辑后，**回归测试老格式（Excel 保存的）xlsx**，别改坏了原本能读的

---

## 四、替代方案（如果不想改解析器）

- **用 Excel 手改**：保持原格式，但 Excel 占用文件时 C# 读会 `IOException`（见 `extnet-tablelayout-cell-edit-pitfalls.md` 的"xlsx 占用"坑）
- **用 NPOI 改**：C# 库，能保持 sharedStrings 格式，但 NPOI API 比 openpyxl 啰嗦
- **改完后用 Excel 另存一次**：Excel 会把 inlineStr 转回 sharedStrings，但路径问题不一定修

> 本次项目的选择：**保留 openpyxl（改 xlsx 方便），修复 C# 解析器兼容 inlineStr + 绝对路径**。

---

## 五、关联文档

- `extnet-tablelayout-cell-edit-pitfalls.md` — xlsx 被 Excel 占用导致 IOException 的踩坑（静默吞异常使配置丢失）
- `pb-daily-job-architecture.md` — 看板每日作业架构（xlsx 配置表是 SOURCE_TYPE 的来源）
