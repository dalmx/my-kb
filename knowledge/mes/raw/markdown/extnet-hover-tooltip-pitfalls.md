---
title: Ext.NET 悬浮提示与 XTemplate 踩坑实录
updated: 2026-09-15
category: 技术-.NET
module: Ext.NET
status: active
tags: [Ext.NET, 悬浮提示, tooltip, hover作用域, 嵌套tip, XTemplate, tpl括号, DataView渲染空白, 绝对定位烟囱, width max-content, nowrap继承, 胶囊布局, 渲染数断言, 踩坑]
---

# Ext.NET 悬浮提示与 XTemplate 踩坑实录
> 在 Ext.NET DataView 卡片墙上做"悬浮提示 + 内嵌 tip"时五个高频坑的完整实录：嵌套 hover 作用域、窄容器绝对定位烟囱、nowrap 继承、双框叠加、XTemplate 括号失衡致整面空白——全部 2026-09-15 在 Curing CuringEquipStateVisual 页实站踩中并修复，附验证纪律与排版基线，任何 Ext.NET 页面做悬浮提示前先过一遍。

## 一、实证来源与适用场景

- 实证页：Curing `Plugins/Curing/Equip/CuringEquipStateVisual.aspx`（DataView 卡片墙 + 图例条 + 停机原因徽标），完整演进见 [[curing-equipstate-visual]]（业务口径）与本文（纯技术坑，跨页复用）。
- 场景特征：图例/徽标等**嵌套组件共用同一个 tip class**、tip 绝对定位挂在**窄 inline-block** 里、tip 内容由 JS 动态填充、XTemplate tpl 里写嵌套三元算 class。

## 二、坑1：嵌套组件共用 tip class，hover 规则必须 `>` 直接子级

后代选择器会跨层误伤：`.legend-item:hover .legend-tip` 把**所有**内嵌 tip（含徽标里的）一起点亮——症状是"悬浮无切换、移开不隐藏"。

```css
/* ❌ 后代选择器:嵌套 tip 全部点亮 */
.legend-item:hover .legend-tip { display: block; }
/* ✅ 直接子级:父级只管自己的 tip,嵌套 tip 归各自宿主 */
.legend-item:hover > .legend-tip { display: block; }
.stop-reason-chip:hover > .legend-tip { display: block; }
```

## 三、坑2：窄 inline-block 内的绝对定位 tip 会变"烟囱"

tip 挂在 `position:relative` 的窄容器（如 65px 宽的图例项）里时，`width:auto` 的 shrink-to-fit 可用宽度=**包含块宽度**而非视口——长列表被压成 100px 宽、1200px 高的烟囱。

```css
.legend-tip {
    position: absolute; top: 100%; left: 0;
    width: max-content;      /* 关键:破除收缩,由内容定宽 */
    max-width: 480px;        /* 再压上限触发换行 */
}
.legend-tip.tip-right { left: auto; right: 0; max-width: 600px; }  /* 右锚定永不右溢,可放宽 */
```

## 四、坑3：父容器的 white-space:nowrap 会继承进内嵌 tip

徽标 `white-space:nowrap`（防文案折行）被内嵌 tip 继承后，长机台列表溢出框外不换行。tip 必须显式 `white-space: normal` 覆盖。

## 五、坑4：嵌套 tip 与父级整表框双框叠加

悬浮徽标时父级"整表提示"同时出现（宿主在父级 hover 范围内）。用**兄弟选择器抑制**——前提是父级 tip 在 DOM 里排在徽标容器**之后**：

```css
.stop-reasons:hover ~ .legend-tip { display: none !important; }
```

## 六、坑5：XTemplate 三元嵌套括号失衡 → DataView 整面空白

tpl `{[...]}` 里三元加一层嵌套后多打一个 `)` → 前端报 `Unexpected token`，**DataView 整面渲染为空**（store 有数据、0 张卡，页面其他部分正常）。改 tpl 表达式后**先数括号**再刷新；排障时先看渲染数而不是只看数据。

```xml
<!-- ✅ 三层嵌套=三个右括号,末尾 )) ) 别多别少 -->
<div class="card-side {[values.L_CAPSULE_WARN===1 ? 'side-red' :
    (values.L_STOPPED===1 ? 'side-yellow' :
    (values.L_CHANGE_PLAN===1 ? 'side-orange' :
    (values.L_HAS_PLAN===1 ? 'side-green' : 'side-gray')))]}">
```

## 七、验证纪律：渲染数断言防"零错配"假阳性

tpl 编译挂掉后 `querySelectorAll('.state-card')` 空集合，任何"遍历比对"都返回零错配——看起来全绿实为没跑。**凡校验类映射/样式，先断言渲染数**：

```js
var cards = document.querySelectorAll('.state-card');
if (cards.length !== App.MachineStore.getCount()) throw new Error('DataView 未渲染全');
// ...再逐卡比对 class 与 Store 正推期望
```

配套验证法：无活数据的分支用**桩数据**喂前端函数（`{getRange:()=>[{get:f=>map[f]}]}`）验完用真实 Store 恢复；hover 交互用 cua.move 后读 computedStyle.display 断言（比截图硬）。

## 八、悬浮提示排版基线（用户两轮反馈定稿）

- **胶囊逐台**：每个机台号一个 `<span class="tip-code">`（半透明白底 `rgba(255,255,255,0.18)`、圆角 3px），比空格串易扫读；容器 flex（`flex-wrap:wrap; gap:4px`，toggle 规则用 `display:flex` 不是 block）。
- **字号 ≥14px 加粗**（12px 被用户两轮打回"不易阅读/太小"）；大屏场景宁大勿小。
- 深色底（如项目 Primary 深蓝 #2d6ca2）白字对比度达标；`::after` 小三角指向触发项（左右锚定各自偏移 12px）。
- 计数为 0 的档用 `.legend-tip:empty { display:none !important }` 自然消失，不必 JS 判空。
