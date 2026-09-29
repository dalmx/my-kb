---
title: Ext.NET 祖先容器隐藏导致子控件 Hidden=false 无效（踩坑）
category: 技术-.NET
module: Ext.NET
tags: [Ext.NET, Hidden, 显隐, 父容器隐藏, 子控件不显示, 容器树继承, Panel, SetHidden, 值驱动显隐, 踩坑, 面板切换]
updated: 2026-09-09
status: active
---

# Ext.NET 祖先容器隐藏导致子控件 Hidden=false 无效（踩坑）

> 子控件设了 Hidden=false 页面却不显示、值也"绑不上"（其实绑上了只是看不见）——先查祖先链：Ext.NET 隐藏沿容器树继承，父 Panel Hidden=true 时整棵子树不渲染，子控件自身 Hidden 设什么都无效。字段要显示，必须物理放进当前分支可见的面板。

## 一、现象与根因

- 现象：分支代码里写了 `某字段.Hidden = false;`，页面不显示；同页其他分支同样的写法却正常。
- 根因：Ext.NET 的隐藏**沿容器树继承**。父容器（Panel/FormPanel/Container）`Hidden=true` 时，其下整棵子树不渲染；子控件 `Hidden=false` 只是去掉自己的隐藏标记，无法"穿透"祖先的隐藏。
- 隐蔽点：`SetValue` 照常执行、不报错——值已设进控件，只是控件不可见。排查时容易误判成"数据没绑上"，实际是显隐问题。

## 二、排查步骤

1. 在 aspx 里定位该控件的完整祖先链（外层 Panel → FormPanel → Container → 字段），逐层查有无 `Hidden="true"`。
2. 在 cs 里查控制该祖先面板显隐的分支逻辑：本分支是否把该面板 `Hidden = true` 了。
3. 对比"能正常显示的分支"：通常那个分支把祖先面板设为可见（`Hidden = false`），所以同样的子控件 Hidden=false 才生效。

## 三、修复模式

- **正解：字段物理迁移**——想让某字段在某分支显示，字段必须位于该分支显示的 Panel 内；跨 Panel 设 Hidden 无效。
- **值驱动显隐模式**（字段只在有值时显示，避免空占位）：

```xml
<!-- 1. aspx：初始隐藏 -->
<ext:TextField ID="tf_X" runat="server" FieldLabel="某字段" Editable="false" LabelAlign="Right" Hidden="true" />
```

```csharp
// 2. cs 取数方法清空段：每次查询先兜底隐藏，防上次显隐残留
tf_X.SetValue("");
tf_X.SetHidden(true);

// 3. cs 取数段：有值才放出（SetHidden 是 Ext.NET 既有扩展方法）
if (formData.Rows[0]["X"] != DBNull.Value)
{
    tf_X.SetValue(Convert.ToDateTime(formData.Rows[0]["X"]).ToString("yyyy-MM-dd HH:mm:ss"));
    tf_X.SetHidden(false);
}
```

- 注意：递归清空方法（如本模式所在页的 ClearCuringPanelFields 递归 SetValue("")）会自动覆盖新增字段，无需额外处理。

## 四、实证案例：BatchTracing dataType=5 扫描投料时间（2026-09-09）

- `txt_scan_time` 位于 `container4 → FormMoldPanel → PanelMold`；dataType=5（胶料）分支 `PanelMold.Hidden = true` + `PanelRubber.Hidden = false`，此时 `txt_scan_time.Hidden = false` 无效，`getRubberMsg` 把 UseTime 绑了也看不见。
- 对照：dataType=3 部材分支 `PanelMold.Hidden = false`，同一行 `txt_scan_time.Hidden = false` 正常生效。
- 修复：PanelRubber 的 container13 新增 `tf_R_ScanTime`，getRubberMsg 绑定改到新字段，dataType=5 分支显隐与胶料 8 位分支对齐；再按"有值才显示"套第三节模式。
- 同族问题：Window 隐藏时内部控件可能未渲染（客户端引用需 show 回调），见 [[extnet-window-guide]]；页面级详情见 [[batch-tracing-quality-info-extension]]。
