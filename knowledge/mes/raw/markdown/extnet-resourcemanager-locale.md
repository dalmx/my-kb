---
title: ResourceManager.Locale — 控制控件界面语言（日期筛选框中文等）
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, ResourceManager, Locale, zh-CN, 本地化, 中文, 属性速查]
status: active
updated: 2026-08-29
---
# ResourceManager.Locale — 控制控件界面语言（日期筛选框中文等）

> ResourceManager 的 Locale 属性控制 Ext.NET/ExtJS 控件内置 UI 文本语言（DateField 日期选择器的月份/星期/Today 按钮、PagingToolbar 文案等，默认英文）。页面 body 第一个元素处设 Locale="zh-CN" 强制中文（"client" 则跟随浏览器语言）；与 FieldLabel 资源文件本地化（业务字段标签，<%$Resources:...%>）是两套独立机制，中文化页面通常两者都要做。

## 一、作用

`<ext:ResourceManager>` 的 `Locale` 属性控制 **Ext.NET / ExtJS 控件自带 UI 文本的语言**，最典型的是：

- **DateField 日期选择器弹窗**：月份名（January→一月）、星期名（Mon→周一）、"Today"按钮（→今天）、翻页提示等。
- PagingToolbar：上一页/下一页提示、页码显示文案。
- 其他内置按钮、校验提示等。

不设 Locale 时，这些文本默认为英文。

## 二、用法

在页面 `<body>` 第一个元素处配置 ResourceManager，指定 `Locale="zh-CN"`：

```xml
<ext:ResourceManager ID="rmUnit" runat="server" Locale="zh-CN" />
```

配置后，该页面所有 Ext.NET 控件的内置 UI 文本变为简体中文。

## 三、Locale 取值

| 值 | 含义 | 效果 |
|----|------|------|
| `"zh-CN"` | 简体中文 | 强制本页控件 UI 为中文（日期选择器、分页栏等） |
| `"en"` | 英文 | 显式英文（等同默认） |
| `"client"` | 跟随客户端浏览器语言 | 自动按浏览器 `navigator.language` 匹配 |
| 不设 | 默认 | 通常为英文 |

> `Locale="client"` 是让 ExtJS 按浏览器语言自动匹配；`Locale="zh-CN"` 是**强制**中文，不依赖浏览器设置。需要确保页面 UI 统一中文时用后者更稳。

## 四、与 FieldLabel 资源文件的区别

两种"中文"来源不同，不要混淆：

| 中文化对象 | 机制 | 示例 |
|-----------|------|------|
| **控件内置 UI**（日期弹窗月份/星期、分页按钮提示） | `ResourceManager Locale="zh-CN"` | "一月""周一""今天""下一页" |
| **业务字段标签**（FieldLabel="机台"） | `<%$Resources:Semi,机台%>` 资源文件 | 见 `extnet-combobox-properties.md` |

- `Locale` 管"控件自带的界面词"；
- `FieldLabel` + 资源文件管"你给字段起的业务名字"。
- 两者独立，通常都要做：Locale 保证日期选择器中文，资源文件保证业务标签多语言。

## 五、注意

- ResourceManager 是页面级，**一个 .aspx 放一个**，放在 body 第一个元素。
- `Locale` 影响的是 ExtJS 内置 locale 资源包；若项目未引入对应语言的 locale js，设了也可能不生效（Ext.NET 默认自带 zh-CN）。
- 本项目多数页面用最简形式 `<ext:ResourceManager runat="server" />`（无 Locale，控件内置文本为英文）；需要日期选择器中文的页面才加 `Locale="zh-CN"`。

## 六、关联

- ResourceManager 最简配置与页面骨架：见 `extnet-page-skeleton.md`
- DateField 日期选择器用法：见 `extnet-datefield-range-and-month.md`
- FieldLabel 资源文件本地化：见 `extnet-combobox-properties.md`
