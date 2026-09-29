---
status: active
title: Ext.NET ColumnModel 前缀陷阱：ext:ColumnModel 致列静默丢失
category: 技术-.NET
module: Ext.NET
tags: [Ext.NET, 踩坑, ColumnModel, 列丢失, ext前缀, columns空, 表头不渲染, grid空白, 分页条有数据, InnerProperty, BillSourceTrace, 浏览器控制台排障, 排障方法论]
updated: 2026-09-16
---

# Ext.NET ColumnModel 前缀陷阱：ext:ColumnModel 致列静默丢失

> GridPanel 列定义写在 `<ext:ColumnModel>`（带 ext: 前缀）里时，Batch 站点（Ext.Net 4.7.1）服务端序列化产出 `columns:{}`——**列集合静默丢失**：查询正常、store 有数据、分页条显示"共 N 条"，但表头+表体整片空白且无任何报错。修复 = 改无前缀 `<ColumnModel>`。实证：Batch `Plugins/Batch/Report/BillSourceTrace.aspx` 2026-09-16。

## 一、症状（与相近坑的分辨）

| 观察 | 本坑（列定义丢失） | 列名大小写坑（extnet-grid-columname-case.md） |
|---|---|---|
| 表头 | **完全没有**（连列名都不渲染） | 有，正常 |
| 数据行 | **完全没有**（空白一片） | 行在、值空白 |
| 分页条 | 显示"共 N 条"（store 有数据） | 同样有 N 条 |
| 后端 | 正常返回 DataTable（行数、列名都对） | 正常返回，但列名与 DataIndex 大小写不匹配 |

**快速分辨口诀**：表头都没有 = 列定义丢失；表头在但整列空白 = 值匹配问题。

## 二、根因

- web.config 注册：`<add assembly="Ext.Net" namespace="Ext.Net" tagPrefix="ext" />`（命名空间通配）。
- `<ext:ColumnModel runat="server">` 解析为独立的 `Ext.Net.ColumnModel` 控件实例，其 `<Columns>` 内的列**没有转发进 GridPanel 的列集合** → 初始配置序列化为 `columns:{}`（空对象、无 items）。
- 无前缀 `<ColumnModel>` 走 GridPanel 的 **InnerProperty 直通道**，列正常收集 → `columns:[...]`。
- **全站实证分布**：Batch Plugins 下所有正常页（LabStockQuery/SemisDailyReport/BatchTracing 等）全部用无前缀 `<ColumnModel>`；唯一用 `ext:` 前缀的就是出问题的 BillSourceTrace（2026-09-16 全目录扫描确认）。
- Curing 站点的 CuringCheckRecord.aspx 用 `<ext:ColumnModel>` 写法，但该站点本机未运行未实测；两站 Ext.Net.dll 版本相同（4.7.1.0）。**作用域按 Batch 站点实证表述**，新页统一无前缀写法即可规避。

## 三、排障路径（可复用方法论）

1. **后端/前端分流**：DirectMethod 里临时 `X.Msg.Notify` 弹参数值+行数+列名（CodeFile 运行时编译，保存即生效）——本例证实后端 27 行、五列名全对 → 锁定前端/序列化层。
2. **控制台查列**：`App.gridX.columns.length` → 0 即列丢失；`App.gridX.store.getCount()` 有值证明 store 通道正常。
3. **抓初始配置串**：`document.querySelectorAll("script")` 文本里搜组件 id，看 `columns:` 形态——`{}`=列没序列化，`[{...}]`=正常。
4. **竞速轮询**（reload 后每 150ms 采样 columns/rows）可分辨"初始就没有"vs"DataBind 后被清空"——本例从 0ms 起就 cols=0，证明是初始配置丢失，与 Store.DataBind() 无关。

## 四、修复（一行）

```xml
<!-- 坏：列静默丢失 -->
<ext:ColumnModel ID="colModel" runat="server">
    <Columns>...</Columns>
</ext:ColumnModel>

<!-- 对：与全站既有页一致 -->
<ColumnModel ID="colModel" runat="server">
    <Columns>...</Columns>
</ColumnModel>
```

开闭标签同步改，`<Columns>` 内的列定义不动。

## 五、验证方法

- 控制台：`columns.length`=预期列数、`store.getCount()`=行数、`store.getAt(0).data` 首行字段完整。
- 截图目视：表头列名+数据行+分页条；确认无诊断残留、无乱码。
- 移除临时诊断代码后 reload 复测一遍（防止"改 A 验 B"假阳性）。

## 六、遗留项

- Curing 站点（端口 12908）未运行，`<ext:ColumnModel>` 在该站点的实际表现未实测；如后续 Curing 新页遇同样症状，优先对照本坑。
- 根因只定位到"前缀写法→序列化丢列"的实证层，Ext.NET 内部转发逻辑未深挖（无源码级定源，不影响规避）。
