---
title: JavaScript 定时器 — setInterval / setTimeout 与清除
category: 技术-前端
module: 通用
factory: 通用
tags: [JavaScript, setInterval, setTimeout, clearTimeout, clearInterval, 定时器, 前端]
status: active
updated: 2026-08-29
---
# JavaScript 定时器 — setInterval / setTimeout 与清除

> JavaScript 定时器 setInterval（周期）/ setTimeout（单次延迟）的语义、清除对照（clearInterval / clearTimeout）与常见场景陷阱。

## 一、概述

| 方法 | 触发方式 | 返回值 | 典型用途 |
|------|----------|--------|----------|
| `setInterval(fn, ms)` | **周期**重复执行（每隔 ms 毫秒） | intervalId | 自动刷新、轮询、定时查询 |
| `setTimeout(fn, ms)` | **单次**延迟执行（ms 毫秒后） | timeoutId | 延迟初始化、防抖、等布局完成 |
| `clearInterval(id)` | 停止周期定时器 | — | 离开页面/切 Tab 时停止刷新 |
| `clearTimeout(id)` | 取消尚未触发的单次定时器 | — | 防抖、条件取消 |

> 两者返回的都是一个整数 ID（定时器句柄），传给对应的 clear 方法即可停止。

## 二、setInterval — 周期调用

每隔固定时间触发一次，常用于自动刷新页面数据。

```javascript
var timer = setInterval(() => {
    App.btnSubmit = document.getElementById('btnSearch');
    if (App.btnSubmit) {
        App.btnSubmit.click();   // 模拟点击查询按钮，触发刷新
    }
}, 60000);   // 每 60 秒一次
```

要点：
- 保存返回的 ID（`timer`），以便后续 `clearInterval(timer)` 停止。
- 回调里先判断目标元素是否存在，避免控件未渲染时报错。
- `App.xxx` 是 Ext.NET 暴露的客户端控件引用；`document.getElementById` 取原生 DOM。两者可混用，但 Ext.NET 控件优先用 `App.ID`。

### 停止周期定时器

```javascript
clearInterval(timer);
```

## 三、setTimeout — 单次延迟

延迟一段时间后执行一次。

```javascript
// 延迟 3 秒后执行（单次触发）
setTimeout(() => {
    console.log("3秒后触发");
}, 3000);
```

### 取消单次定时器

```javascript
const timeoutId = setTimeout(...);
clearTimeout(timeoutId);   // 若尚未触发，则不再执行
```

## 四、清除对照

```javascript
// 清除 setTimeout
const timeoutId = setTimeout(...);
clearTimeout(timeoutId);

// 清除 setInterval
const intervalId = setInterval(...);
clearInterval(intervalId);
```

> 注意：`clearTimeout` 与 `clearInterval` 在浏览器实现中其实可互换（都从同一队列移除），但**语义上应配对使用**，便于阅读和维护。

## 五、常见场景与陷阱

### 5.1 页面卸载时清理

周期定时器在页面卸载/跳转前应清除，避免内存泄漏或对已销毁控件操作报错：

```javascript
// 离开页面时停止刷新
window.onbeforeunload = function () {
    clearInterval(timer);
};
```

### 5.2 避免请求堆积

`setInterval` 不会等上一次回调完成就排下一次。若回调里有异步请求且较慢，会导致请求堆积。两种对策：
- 改用 Ext.NET `TaskManager` 的 `WaitPreviousRequest="true"`（见关联文档）。
- 或在回调内用 setTimeout 自递归，等请求完成再排下一次：

```javascript
function autoRefresh() {
    doRefresh(function () {
        timer = setTimeout(autoRefresh, 60000);  // 上次完成后才排下次
    });
}
timer = setTimeout(autoRefresh, 60000);
```

### 5.3 this 指向

箭头函数继承外层 `this`；普通 `function` 里 `this` 指向 `window`。Ext.NET 场景下回调里多用 `App.xxx` 或 `Ext.getCmp`，一般不依赖 `this`，故箭头函数更安全。

## 六、与 Ext.NET TaskManager 的对比

| 维度 | 原生 setInterval/setTimeout | Ext.NET TaskManager |
|------|---------------------------|---------------------|
| 触发目标 | 纯客户端 JS | 可触发服务端 DirectEvent |
| 防请求堆积 | 需手动处理 | `WaitPreviousRequest="true"` 内置 |
| 声明方式 | JS 代码 | aspx 标签声明 |
| 适用 | 纯前端轮询、模拟点击 | 需回服务端取数据刷新 |

若定时刷新需要走服务端，优先用 TaskManager；若只是前端模拟点击已有查询按钮，`setInterval` 更轻量。

## 七、关联

- Ext.NET TaskManager 服务端定时刷新：见 `extnet-desktop-framework-guide.md`（SystemStatus 实时图表）
- Tab 切换后延迟触发（defer + resize）：见 `extnet-tabpanel-echarts-not-display.md`
