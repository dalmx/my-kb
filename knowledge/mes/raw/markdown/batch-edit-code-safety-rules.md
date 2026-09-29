---
category: 技术-.NET
module: 通用
status: active
tags: [批量编辑, 脚本, XML破坏, iBATIS, Mapper, 嵌入资源, isNotNull, JS语法错误, 标签配平, 良构校验, 大小写, 事故复盘, node脚本]
title: 脚本批量编辑代码文件铁律（XML/JS 结构破坏两次事故复盘）
updated: 2026-08-29
---

# 脚本批量编辑代码文件铁律（XML/JS 结构破坏两次事故复盘）

> 2026-08-26 Molding 接头参数限值功能开发中，用 node 脚本批量删改代码文件连续造成两次结构破坏事故，均由用户运行时报错发现。本文复盘根因并给出铁律。

## 一、两次事故

### 事故1：Mapper XML 按关键词删行 → XML 结构破坏

**操作**：实体删掉 Usl/Lsl 属性后，用「逐行过滤含 `/Usl|LSL|USL/` 的行」清理 `BasicMapper/BpmSpliceMaterialLimit.xml`。
**现象**：运行时报 `XML文件错误 [assembly://Wongoing.Molding.Mapper/...BpmSpliceMaterialLimit.xml]`——iBATIS 加载嵌入资源时解析失败。
**根因**（三个盲区叠加）：
1. **闭合标签 `</isNotNull>` 不含关键词** → 被删块的闭合残留成孤立标签
2. **大小写敏感匹配**：属性名 `Lsl`（小写l）不匹配 `LSL`/`Usl` → `<parameter property="Lsl">`、`<isNotNull property="where.Lsl">` 空壳残留（开标签残留+SQL行被删+闭合也残留）
3. 最终 `isNotNull` 45开/47闭，XML 良构性破坏
**修复**：正则宽松匹配（`\s*` 容差 + `\r?\n`）整块删除「孤立闭合+空壳」；单行自包含的 insert 值 `<isNotNull property="Lsl">#Lsl#</isNotNull>` 单独删。

### 事故2：JS 函数切片替换 → 整个 script 失效

**操作**：用 `indexOf('var getLimitForm')` 到 `indexOf('};')` 切片替换 JS 函数。
**现象**：`Uncaught ReferenceError: MinorTypeChangeQ is not defined`。
**根因**：函数内部嵌套的辅助函数 `var g = function(){...};` 的 `};` 先于外层函数出现，切片只覆盖前半段，**旧函数尾巴残留形成顶层 return 语法错误 → 整个 script 块解析失败 → 所有函数未定义**（报错指向第一个被引用的函数，误导排查方向）。

## 二、铁律

1. **删标签块必须整块删除（开标签到闭合同删），绝不按关键词逐行过滤**——闭合标签和大小写变体总会逃过匹配。
2. **JS 函数替换的边界锚必须唯一且属于该函数自身**（如函数完整体文本），或用「整文件重写」。
3. **每次批量编辑后立即验证**（成本秒级，比运行时报错便宜百倍）：
   - XML：标签栈良构校验（正则遍历 push/pop），不是只数开闭数量
   - JS：`new Function(code)` 真实语法解析，不是只配平花括号
   - 关键词复查用**大小写不敏感**（`/lsl|usl/i`）确认零残留
4. **改 Mapper XML 后必须重编 Mapper 工程**（EmbeddedResource 嵌入 dll，知识库已有铁律）——报 `assembly://...xml` 错误时先怀疑 XML 损坏，其次才是没重编。

---

## 三、补充实证：node -e 内联多行替换必然翻车（2026-08-26 再证）

用 `node -e "..."` 在 shell 里写**多行字符串替换**第三次翻车（bash 双引号转义吃掉引号 → SyntaxError: Invalid或Unexpected token，且报错行指向模板串开头）。本铁律升级为硬规则：

- **凡 node 脚本含多行字符串（替换模板）→ 一律 Write 临时 `.js` 文件执行再删除**，禁止 `node -e` 内联
- 临时脚本放项目目录下（如 `<项目>/tmp_xxx.js`），执行完即删，符合文件存放规则

另：知识库图谱体检结论（2026-08-26）——新建文档要主动织入链（挂进枢纽文档的关联区，如 extnet-page-skeleton 入度 21），否则成孤岛；改完 `check_broken_links` + 重建索引收尾。