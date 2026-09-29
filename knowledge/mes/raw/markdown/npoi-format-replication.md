---
category: 技术-.NET
module: C#
status: active
tags: [NPOI, Excel导出, xlsx格式复刻, 格式对齐, 边框体系, 虚线边框, DisplayGridlines, 合并单元格, 冻结窗格, 数字格式, 动态列, 版本列, 参数求值顺序, CloneStyleFrom, openpyxl验证, 文件锁, ThreadingHTTPServer, 样式污染, 八区块, 逐格探针, CreateRow重建清空, GetRow守卫, NPOI行语义]
title: NPOI 2.1 原表格式复刻技法（边框体系/合并布局/按版本动态列/验证闭环）
updated: '2026-09-28'
---

# NPOI 2.1 原表格式复刻技法（边框体系/合并布局/按版本动态列/验证闭环）

> 把导出 xlsx 做成"和客户原表逐格一样"的通用技法，2026-09-23 在 Curing 月生产计划导出（MonthlyProductionPlan，八区块）上全流程实证。与 [[npoi-2-1-excel-compat-pitfalls]]（styles.xml 兼容性）互补：那篇管"Excel 能不能开"，这篇管"开出来像不像"。适用于任何"按客户 xlsx 复刻导出格式"的任务。

## 一、分区对齐工作法（先建底图再动手）

1. **把导出页划成独立区块**（如月生产计划八区块：主表/统计区×2/操业日数/规格块/出口/对比块/签名），每块和原件对应区域逐格 probe（值/四边框/填充/字体/对齐/number_format/行高/合并区），列差异清单再动手。
2. **用户按块迭代**：一次只改一块，改完重导出验证，避免多块混杂回归。
3. openpyxl 逐格探针（bd 四边首字符/fgColor[-6:]/font/alignment.horizontal/number_format）是对齐和验证的唯一手段，肉眼截图不可靠。

## 二、API 要点（NPOI 2.1 实证）

- **隐藏整表网格线**：`((XSSFSheet)sh).DisplayGridlines = false;`（2.1 属性名是 DisplayGridlines，dll 元数据 grep 可确认；设了它，"没有边框的格子"才是真空白）
- **样式批量构建**：写一个 `ZStyle(wb, font, halign, l, r, t, b, numFmt)` 私有静态帮助函数，四边框+对齐+数字格式一行一个样式；**禁用 CloneStyleFrom**（会污染源样式边框，2026-09-22 与 09-23 两次实证），全部显式构建
- **数字格式**：`#,##0`（整数不留小数）与 `#,##0.##`（可有可无小数）两个 DataFormat 够用；改样式上的 DataFormat 即改显示（存储值不变）
- **列隐藏**：`sh.SetColumnHidden(i, true)` 存在，但"关网格线+无边框"场景通常要的是去边框而非隐藏列——先和用户确认语义（本例用户要的是去边框，隐藏列被撤回）
- **冻结**：`sh.CreateFreezePane(colCount, rowCount)`；合并格跨冻结线可渲染（文字在冻结侧始终可见），滚动观感需用户实测

## 三、边框体系（语义化四档）

| 档 | BorderStyle | 用途 |
|---|---|---|
| Medium | 中粗 | 区块外框/表格左右边缘/英寸計行大框/签名格/TOTAL 行/表头顶边 |
| Thin | 细实线 | 表头/列边界/底行收口（"最外圈实线"即 Thin/Medium，绝不用 hair） |
| Hair | 发丝线 | 统计区网格内部线（原件同款） |
| Dashed | 虚线 | 明细行单元格分隔（用户口径：明细虚线、大框中粗） |

- **"某行/某块没有边框线"类投诉的排查路径**：先确认是没写边框、边框被更重级的相邻边盖过、还是样式分发落错——三种都遇到过
- 合并格：只有左上格样式管内容/填充，边缘看各边缘格（右边缘=最右格.right）；内部边不渲染

## 四、填充色语义（本族报表惯例，跨页复用）

| 色 | 用途 |
|---|---|
| #FAC090 | 主表表头 / 出口格 |
| #66CCFF | TOTAL 行 / 订单预算标签 / 强调值 |
| #CCFFFF | 加硫量值行（无数据源空格占位） |
| #FDEADA | 库入值行整行 |
| #FFFF00 | 出口订单值 / 差异表头（黄底=待填数标记） |
| #E6B9B8 | 纯OE/纯REP 节标签 |
| 无填充 | 统计区网格、明细行（去底色=明确要求时） |

## 五、布局模式

- **标签+值双栏**：F:G 合并放标签/量值，H 放日均标签/日均 值（用户口径"内容右移一列"）
- **版本列向右延顺**：表头 `foreach v Put(H起, "R"+v)`，值行同列位——版本涨到 R2/R3 自动多列；表头用无边框 sph，值格 #,##0
- **统计区骑产品行**：区块锚定 sheet 行号（`ZONE1_RIX`、`ZONE1_RIX+count+间隔`），格写在产品行右侧列上；块间距用 `rix += 2` 空行
- **合并区写入**：F:G 合并 = F、G 各 Put 同一 style + `AddMergedRegion(row,row,5,6)`；纵向合并跨行同理（签名 2×2 格 = 上格角色/下格签名位）

## 六、三个高危坑（全部踩过）

1. **C# 参数求值顺序**：`Put(rr, cx++, cx == last ? "a" : "b", "")` —— 三元里读到的 cx 是**自增后**的值，末列样式错位到倒数第二列。正解：先 `bool isLast = cx == last;` 再 `Put(rr, cx++, isLast ? ... , "");`
2. **kind 分发漏项**：Put 是 if-chain 分发，新增 kind 忘加分发行、或 FillZone 后缀（首列加 L/末列加 R）白名单漏了它 → 落到默认分支变 TOTAL 蓝底中粗样式。症状："个别格子莫名蓝底+四边中粗"。修法：白名单只收网格类 kind，标签/空格/无边框列显式排除
3. **样式污染**：CloneStyleFrom 禁用（见上）；改共享样式前先查它还被谁用（StLab 曾被统计区标签和出口行共用，改一处动两块）

## 七、验证闭环（工具链）

1. **导出落盘**：页面查询出数后，页内 `fetch(POST form + btnExportSubmit)` 拿二进制 → POST 到本地 python 接收器落盘。接收器必须 `ThreadingHTTPServer`（单线程版一遇异常整个死掉）+ 输出路径走 `sys.argv`（用户开着 Excel 时原文件被锁，PermissionError → 换 vN 新文件名写入）
2. **登录过期症状**：导出 POST 返回 267 字节跳转 HTML（而非 xlsx）→ 重登录；**导出前必须先查询**（数据在 Session）
3. **openpyxl 逐格探针**：值/四边框/填充/字体/对齐/number_format/merged 全断言；改一处验一处+回归抽查（冻结/网格线/既无边框）
4. **FileLayout**：aspx.cs 改完只需浏览器重载页面（CodeFile 动态编译），无需部署 dll
5. 相关：兼容性/文件损坏类问题见 [[npoi-2-1-excel-compat-pitfalls]]；编译验证见 curing-msbuild-verify 记忆

---



## 九、高危坑增补：CreateRow 重建清空（2026-09-28 Molding 日程计划导出实证）

- **XSSFSheet.CreateRow(ri) 对已存在行是"丢弃重建"语义**——返回全新空行，原行所有格子（值+样式+行高）全部清空，无任何警告。循环里每轮对**同一行** CreateRow，最后只剩最后一轮写的内容（症状：签名区 4 格只剩最后 1 格有值，前 3 格连边框样式都没了——不是合并区清值，是行被重建）。
- **正解**：建行一律 `IRow row = sh.GetRow(ri); if (row == null) { row = sh.CreateRow(ri); }` 后再写格；需要预设行高的行在循环外建一次。辅助写入函数（Put 类）内部应自带此守卫，切勿在调用方随手 CreateRow。
- 判别口诀：**"循环写同一行，只留最后一轮"** = 撞上重建清空；与 AddMergedRegion 清值（POI 不清、openpyxl 只报左上）区分。
- **增补（同日第二坑）：XSSF AddMergedRegion 会把合并区非首行格子的上下边框清掉**（症状：合并区中/尾行边框变 m..m/..mm）——merge 之后须对区域全部格子统一重设 CellStyle 补边；合并区中间行的内部竖线值不影响渲染（Excel 只画边缘），与用户原样逐格比对即可。