---
status: active
updated: 2026-09-18
title: Ext.NET DataView StoreID 前向引用导致整页不渲染
category: 技术-.NET
module: Ext.NET
tags: [Ext.NET, DataView, Store, StoreID, 前向引用, 整页白, 初始化顺序, onReady, 排查]
---
# Ext.NET DataView StoreID 前向引用导致整页不渲染
> Ext.NET 页面把独立 `<ext:Store>` 定义在 `<ext:Viewport>` **之后**时，生成的初始化脚本顺序=先 Ext.create(Viewport) 后 create(Store)；Viewport 里 DataView 以 `StoreID="xxx"` 字符串引用 store，构建时 StoreManager 查不到即抛错，**整段 Ext.onReady 中断**——页面 200、无服务端异常、body 近乎空（仅 quicktips 殂留），极易误判为服务端没渲染。2026-09-18 CuringJiaDongRate 实证。

## 一、症状特征
- 页面返回 200，`document.title` 正常，但 `document.querySelector('.x-viewport')`/组件 DOM 全无，body innerHTML 仅 2KB 左右（表单隐藏域+quicktips tip）
- 服务端日志无任何异常；Page_Load 正常执行（可查到 SQL 日志）
- 初始化脚本（`<script>` 内联 Ext.onReady）**语法完整**（eval 不报错），但组件不挂载
- 浏览器 console 有 JS 异常（服务端看不到）

## 二、根因与判定
- Ext.NET 按控件树顺序生成初始化 JS；Viewport 先 create，其 items 里 DataView 的 `store:"storeOverview"` 在组件构造时经 StoreManager.lookup 解析，store 尚未 create → 构造异常 → onReady 整段中断
- 判定方法：取页面最后一个内联 script，确认 `Ext.create("Ext.net.Viewport",...{store:"storeXxx"}...)` 出现在 `window.App.storeXxx=Ext.create("Ext.data.Store",...)` **之前**

## 三、解法（按优先级）
1. **独立 Store 块物理前移到 Viewport 之前**（form 内顺序即生成顺序）——多 DataView 共享一 Store 时唯一可行
2. 单 DataView 用的 Store 直接**嵌进控件**：`<Store><ext:Store …/></Store>`（CuringEquipStateVisual 模式），嵌套 store 随宿主组件生成
3. 检查手段：改完 reload 后 `document.querySelector('.x-viewport')` 应为真、面板标题 `.x-panel-header-title` 齐全

## 四、关联
- 项目实证页：[[curing-jiadongrate-page]]（块1/块2 两个 DataView 共享 storeOverview + 两个停机栏各一 store，全部前移修复）
- 同族坑：Ext.NET `<Items>` 内放 HTML 注释报错、LayoutConfig 连字符静默失效（见 extnet-new-page-style-checklist）
