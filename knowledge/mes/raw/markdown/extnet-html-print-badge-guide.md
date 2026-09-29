---
title: Ext.NET 纯HTML浏览器打印工牌技术指南
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, 打印, 工牌, 二维码, qrcode.js, window.print, CheckboxSelectionModel, A4排版, 纯HTML打印, 浏览器打印]
status: active
updated: 2026-08-29
---
# Ext.NET 纯HTML浏览器打印工牌技术指南

> Main MES 用户信息页(UserInfo)实现"多选员工 → 批量打印工牌(姓名+工号二维码+结束二维码)"。区别于项目既有的 FastReport(.frx) 打印方案，本方案采用**纯 HTML + 浏览器 window.print() + qrcode.js**，无需报表设计器，适合卡片/标签类批量打印。

## 一、适用场景判断

| 需求 | 推荐方案 | 参考 |
|------|---------|------|
| 需要精确套打、复杂表格、条码铭牌、有现成 .frx 模板 | **FastReport** | `semi-fastreport-print-guide.md` |
| 卡片/标签批量排版（工牌、吊牌、贴纸）、内容简单、要二维码 | **纯 HTML 打印（本方案）** | 本文档 |
| 仅导出数据到 Excel | ExcelDownload | `Wongoing.Utility.Excel.ExcelDownload` |

选纯 HTML 方案的前提：内容能用 div+CSS 排版，不需要票据/套打精度。

## 二、整体架构（数据流）

```text
[业务页 UserInfo.aspx]
   ① GridPanel 多选行 (CheckboxSelectionModel)
   ② 按钮 DirectEvent 提交 getRowsValues({selectedOnly:true}) 的 JSON
   ▼
[业务页后端 UserInfo.aspx.cs]
   ③ JSON.Deserialize 反序列化 → 取所需字段 → 存 Session["PrintBadgeData"]
   ④ X.AddScript("window.open('打印页.aspx')") 触发新窗口
   ▼
[独立打印页 XxxPrint.aspx + .cs]
   ⑤ Page_Load 读 Session → Repeater 渲染卡片 HTML
   ⑥ 前端 qrcode.js 渲染二维码 → 自动 window.print()
   ▼
[浏览器打印对话框] (用户关闭页眉页脚后输出)
```

## 三、关键技术点（含踩坑）

### 1. 多选：GridPanel 必须显式配置 SelectionModel

**坑**：GridPanel 不写 `<SelectionModel>` 时默认单选，导致 `getRowsValues({selectedOnly:true})` 永远只取到一行甚至取不到，后端拿到空数据，打印页显示占位符/空白（典型现象："打印内容是测试信息"）。

**正解**：在 `</ColumnModel>` 后、`<View>` 前，加项目标准写法（参考 `SetUserAction.aspx` / `SetUserOneRole.aspx`）：

```xml
<SelectionModel>
    <ext:CheckboxSelectionModel ID="checkModel" runat="server" Mode="Multi" />
</SelectionModel>
```

- `Mode="Multi"`：配合复选框列，可勾选任意多行（项目既有例子统一用 Multi，非 SIMPLE/MULTI）
- 加上后，页面已有的 `getRowsValues({selectedOnly:true})` 调用（预警/导出/打印等按钮）**无需改 JS**，自动取到全部勾选行
- 表格最左自动出现复选框列，与既有 `RowNumbererColumn`（行号列）共存无冲突

### 2. 取选中行数据：getRowsValues 字段名规则

- `#{pnlList}.getRowsValues({selectedOnly:true})` 返回 JSON 数组，**字段名 = Store Model 里 `<ext:ModelField Name="XXX">` 的大写原名**（如 `REAL_NAME`、`WORK_BARCODE`）
- 后端反序列化：`JSON.Deserialize<Dictionary<string,string>[]>`，按大写原名取值 `row["WORK_BARCODE"]`
- **防御**：某字段可能为 null 导致 JSON 里缺该 key，后端用 `row.ContainsKey("XXX") ? (row["XXX"] ?? "") : ""` 兜底
- 验证字段名正确性的快捷法：看同页已有的、能正常工作的批量按钮（如"设置预警"）怎么取值

### 3. 批量数据传递：用 Session，不要用 URL 参数

**坑**：项目用 jquery-1.7.1（IE 兼容环境），IE 的 URL 长度上限 2083 字符，多选大量人员时 JSON 拼到 URL 会超长截断。

**正解**：DirectEvent 提交 → 后端存 `Session["PrintBadgeData"]` → 打印页读 Session。与"设置预警"等批量操作模式一致。

### 4. 后端触发前端打开新窗口的 API

Ext.NET 4.7 中**注入前端脚本**的方法是 `X.AddScript(...)`：

```csharp
X.AddScript("window.open('UserBadgePrint.aspx', '_blank');");
```

**坑**：旧资料里的 `X.Js.AddBuildScriptCall(...)` 在 Ext.NET 4.7 **不存在**（反射 DLL 确认无此方法）。验证某 API 是否存在：`grep -ao "方法名" Bin/Ext.Net.dll`。

### 5. 二维码生成：qrcode.js（前端纯 JS）

- 库：davidshimjs/qrcodejs（MIT，~20KB，纯 JS 无依赖），API `new QRCode(element, {text,width,height,colorDark,colorLight,correctLevel})`
- 项目 `resources/js/` 原本**没有**二维码库，需自行下载引入（放 `resources/js/qrcode.js`）
- 引用写法沿用项目规范：`<script src="<%= Page.ResolveUrl("~/") %>resources/js/qrcode.js"></script>`
- 渲染时机：`window.onload` 后遍历所有二维码容器 `new QRCode(...)`，**图片是异步生成**，调 `window.print()` 前需 `setTimeout` 延迟（约 500ms）等 `<img>`/`<canvas>` 就绪
- 扫码内容：`text` 的值就是扫出来的内容，支持字母+数字+连字符（如工号 `GP-08629` 原样编码，用 UTF-8 字节模式）

### 6. A4 打印排版 CSS 要点

```css
/* A4 = 210mm × 297mm */
.page { width:210mm; min-height:297mm; }
@media print {
    @page { size:A4; margin:0; }       /* margin:0 是隐藏浏览器页眉页脚的关键技巧之一 */
    html,body { margin:0 !important; padding:0 !important; }
    .badge.page-break { page-break-before:always; }   /* 每 N 张分页 */
    .no-print { display:none !important; }             /* 工具栏等预览元素打印时隐藏 */
}
```

- 每页固定张数（如 3列×4行=12张）：卡片高度算准，`page-break-inside:avoid` 防止单卡被截断
- 卡片间留空隙：用 `display:flex; gap:4mm;`，卡片宽度用 `calc((100% - 8mm)/3)` 配合减去间距防溢出
- 预览/打印双态：屏幕用 `.page{margin:10mm auto;box-shadow}` 居中白纸效果，`@media print` 里清零这些

### 7. 浏览器页眉页脚无法用代码强制关闭（重要限制）

**坑**：打印预览上下出现网址/日期/页码 = 浏览器自带的页眉页脚。Chrome/Edge 较新版本即使 `@page margin:0` 仍会显示。

**事实**：这是浏览器隐私设计，**CSS 无标准属性可控制**，代码只能做到 `@page margin:0` 降低出现概率，不能保证。

**解决**：必须由用户在打印对话框手动关闭——Chrome/Edge：`更多设置 → 取消勾选"页眉和页脚"`，边距设为"无"。浏览器通常记住该域名上次设置。

## 四、权限定义

新增按钮需在页面 `__ : ___` 权限类里注册权限点（框架反射自动扫描 `PageAction` 属性，靠 `ActionId` 去重）：

```csharp
打印工牌 = new PageAction() { ActionId = 11, ActionName = "btnPrintBadge" };  // ActionId 接现有最大值+1
...
public PageAction 打印工牌 { get; private set; }   // 必须 public，属性名=权限中文名
```

## 五、相关文件清单

| 文件路径 | 说明 |
|---------|------|
| `P.Main/Wongoing.Main.WebSite/Plugins/Main/SysUser/UserInfo.aspx` | 业务页（加按钮+多选） |
| `P.Main/Wongoing.Main.WebSite/Plugins/Main/SysUser/UserInfo.aspx.cs` | 后端（存Session+开窗口） |
| `P.Main/Wongoing.Main.WebSite/Plugins/Main/SysUser/UserBadgePrint.aspx` | 打印页（A4排版+二维码容器） |
| `P.Main/Wongoing.Main.WebSite/Plugins/Main/SysUser/UserBadgePrint.aspx.cs` | 打印页后端（读Session渲染卡片） |
| `P.Main/Wongoing.Main.WebSite/resources/js/qrcode.js` | 二维码库（新增引入） |
| `P.Main/Wongoing.Main.WebSite/Plugins/Main/SysUser/SetUserAction.aspx` | CheckboxSelectionModel 参考范例 |
| `Frame/Wongoing.Web.UI/Entity/PageAction.cs` | 权限点实体类 |
| `Frame/Wongoing.Web.UI/Page/IPageAction.cs` | 权限反射基类(___ ) |

## 六、复用清单（再给别的页面加"打印XX"功能时）

1. 业务页 GridPanel 加 `<ext:CheckboxSelectionModel Mode="Multi">`（如已有多选则跳过）
2. 工具栏加按钮，`DirectEvent` + `ExtraParams` 传 `getRowsValues({selectedOnly:true})`
3. 后端方法：反序列化 → 取字段存 Session → `X.AddScript("window.open('打印页')")`
4. 新建打印页 `.aspx`：`@media print` + A4 尺寸 + Repeater 渲染卡片 + `window.onload` 调 `window.print()`
5. 需要二维码就引 `resources/js/qrcode.js`，需要条码就走 FastReport
6. 权限类加 `PageAction`，`ActionId` 取现有最大值+1
7. 提醒用户：打印时在对话框关掉"页眉和页脚"
