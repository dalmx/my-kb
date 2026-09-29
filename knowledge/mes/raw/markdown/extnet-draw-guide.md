---
title: Ext.NET Draw 自由绘图完整指南
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Draw, DrawContainer, Sprite, PathSprite, RectSprite, CircleSprite, TextSprite, 矢量绘图, 渐变, 动画]
status: active
updated: 2026-08-29
---
# Ext.NET Draw 自由绘图完整指南

> 本文档从 Ext.NET 4.7.1 官方示例库 `Examples/Draw/`（12 示例）提炼，覆盖 DrawContainer 容器与各类 Sprite（绘图元素）。目标是让 AI/开发者读完即可在任意 Ext.NET WebForms 项目复现矢量绘图。
>
> 适用：Ext.NET 4.x + Triton 主题。底层是 ExtJS 的 `Ext.draw` 包。

---

## 一、DrawContainer 容器

`<ext:DrawContainer>` 是绘图画布，内部放 Sprite（图形元素）。

### 核心属性

| 属性 | 作用 |
|------|------|
| `Width` / `Height` | 画布像素尺寸 |
| `Border` | 边框 |
| `Region` | 用于 BorderLayout（`Center` 等） |

### 子节点集合

| 集合 | 作用 |
|------|------|
| `<Items>` | 放置 Sprite（图形元素） |
| `<Gradients>` | 渐变定义（供 Sprite `FillStyle="url(#id)"` 引用） |
| `<Plugins>` | 放 `ext:SpriteEvents` 启用 Sprite 鼠标事件 |
| `<Listeners>` | 容器级事件 |

### 最小声明式示例

```aspx
<ext:DrawContainer runat="server" Width="320" Height="240">
    <Items>
        <ext:RectSprite X="10" Y="10" Width="300" Height="200"
            FillStyle="#4CAF50" Radius="10" />
        <ext:TextSprite Text="Hello Draw" X="100" Y="120"
            FontSize="20px" FillStyle="#fff" />
    </Items>
</ext:DrawContainer>
```

---

## 二、Sprite（绘图元素）

所有 Sprite 共有属性：`SpriteID`（唯一标识）、`TranslationX/Y`（平移）、`Scaling`/`ScalingX/Y`（缩放）、`RotationDegrees`（旋转）、`Hidden`、`Opacity`/`GlobalAlpha`（透明度）、`Duration`/`Easing`（动画）。

### 2.1 RectSprite（矩形）

```aspx
<ext:RectSprite X="0" Y="0" Width="640" Height="480"
    FillStyle="#CECECE" Radius="10" />
```

| 属性 | 作用 |
|------|------|
| `X`/`Y`/`Width`/`Height` | 位置与尺寸 |
| `Radius` | **圆角半径**（注意：不是圆半径） |
| `FillStyle`/`StrokeStyle`/`LineWidth` | 填充/描边/线宽 |

### 2.2 CircleSprite（圆）

```aspx
<ext:CircleSprite CX="160" CY="120" Radius="60" FillStyle="#000" />
```

| 属性 | 作用 |
|------|------|
| `CX`/`CY` | 圆心坐标 |
| `Radius` | 半径 |

### 2.3 PathSprite（路径——最通用）

画任意形状/折线/直线/弧，用 SVG path 字符串：

```aspx
<!-- 三角形 -->
<ext:PathSprite Path="M100 50 L150 150 L50 150 z"
    FillStyle="#f00" StrokeStyle="#000" LineWidth="2" />

<!-- 直线（M 起点 L 终点） -->
<ext:PathSprite Path="M10 10 L 290 190" StrokeStyle="blue" LineWidth="3" />

<!-- 扇形/弧（A 弧命令） -->
<ext:PathSprite Path="M250 250 L x1 y1 A r r 0 0 0 x2 y2 z" FillStyle="url(#g1)" />
```

**关键命令**：`M`(移动) / `L`(直线) / `C`(三次贝塞尔) / `A`(弧) / `z`(闭合)。

> 注意：**没有独立 LineSprite**，画直线用 PathSprite 的 `"M x1 y1 L x2 y2"`。

### 2.4 TextSprite（文本）

```aspx
<ext:TextSprite SpriteID="t1" Text="标签"
    X="100" Y="50" FillStyle="#000"
    FontSize="16px" FontFamily="Arial" />
```

| 属性 | 作用 |
|------|------|
| `Text` | 文本内容 |
| `X`/`Y` | 基线起点 |
| `FontSize`/`FontFamily` | 字号/字体 |
| `TextAlign` | 对齐 |

### 2.5 ImageSprite（图片）

```aspx
<ext:ImageSprite Src="logo.png" X="10" Y="10" Width="200" Height="100" />
```

**镜像倒影**：`ScalingY="-0.7"` + `Opacity="0.5"` 实现垂直翻转半透明。

### 2.6 CompositeSprite（组合，统一动画）

```aspx
<ext:CompositeSprite SpriteID="group1" Duration="1000">
    <Items>
        <ext:CircleSprite CX="10" CY="10" Radius="10" FillStyle="#f00" />
        <ext:CircleSprite CX="50" CY="50" Radius="10" FillStyle="#0f0" />
    </Items>
</ext:CompositeSprite>
```

打包后整体平移/缩放/旋转。

---

## 三、渐变 Gradients

```aspx
<ext:DrawContainer runat="server">
    <Gradients>
        <ext:LinearGradient GradientID="g1" Degrees="90">
            <Stops>
                <ext:GradientStop Offset="0" Color="rgb(156,178,248)" />
                <ext:GradientStop Offset="1" Color="rgb(33,33,33)" />
            </Stops>
        </ext:LinearGradient>
    </Gradients>
    <Items>
        <ext:PathSprite Path="..." FillStyle="url(#g1)" />
    </Items>
</ext:DrawContainer>
```

Sprite 用 `FillStyle="url(#GradientID)"` 引用渐变。

---

## 四、变换与动画

变换属性叠加于坐标之上，都支持动画（`Duration`/`Easing`）：

| 属性 | 作用 |
|------|------|
| `TranslationX` / `TranslationY` | 平移（不改 X/Y 本身） |
| `Scaling` / `ScalingX` / `ScalingY` | 缩放（负值翻转） |
| `RotationDegrees` | 旋转（度） |

**客户端动态变换**（属性名 camelCase）：

```javascript
// 取 Sprite
var sprite = App.Draw1.getSurface().get('SpriteID');

// 变换
sprite.setAttributes({ translationX: 150 });
sprite.setAttributes({ rotationRads: deg * Math.PI / 180 });
sprite.setAttributes({ scalingX: 1.1, scalingY: 1.1 });

// 必须手动重绘
App.Draw1.getSurface().renderFrame();
```

> **关键**：改 `setAttributes` 不会自动刷新，**必须调用 `renderFrame()`**。

---

## 五、事件与交互

### 方式 1：SpriteEvents 插件 + 容器级 Listener（推荐）

```aspx
<ext:DrawContainer runat="server" ID="dc1" Width="640" Height="480">
    <Items>
        <ext:CircleSprite SpriteID="btn1" CX="50" CY="50" Radius="30" FillStyle="#ccc" />
    </Items>
    <Plugins>
        <ext:SpriteEvents runat="server" />   <!-- 关键：启用 Sprite 事件 -->
    </Plugins>
    <Listeners>
        <SpriteClick Fn="onClick" />
        <SpriteMouseOver Fn="onMouseOver" />
        <SpriteMouseOut Fn="onMouseOut" />
    </Listeners>
</ext:DrawContainer>
```

回调签名：`function(me, event, eventOpts)`，`me.sprite` 是触发事件的 Sprite，`me.sprite.id` 是其 id。

### 交互后标准三步曲

```javascript
function onMouseOver(sprite, i) {
    sprite.fx.stop();                    // 1. 停掉旧动画
    sprite.setAttributes({               // 2. 改属性（含动画参数）
        scalingX: 1.1, scalingY: 1.1,
        duration: 500, easing: "backOut"
    });
    sprite.getSurface().renderFrame();   // 3. 重绘
}
```

---

## 六、服务端动态绘图

在 `Page_Load` 循环添加 Sprite：

```csharp
protected void Page_Load(object sender, EventArgs e)
{
    if (!X.IsAjaxRequest)
    {
        for (int i = 0; i < 10; i++)
        {
            this.Draw1.Items.Add(new CircleSprite
            {
                SpriteID = "dot_" + i,
                CX = i * 30,
                CY = 100,
                Radius = 10,
                FillStyle = "#333"
            });
        }
        this.Draw1.RenderFrame();
    }
}
```

**服务端 API**：
- `draw.Items.Add(sprite)`：添加 Sprite
- `draw.RenderFrame()`：触发重绘
- `draw.GetSprite("id")`：按 ID 取 Sprite

---

## 七、踩坑要点

### 坑1：没有独立 LineSprite

画直线用 `PathSprite` 的 `Path="M x1 y1 L x2 y2"`，没有 `<ext:LineSprite>`。

### 坑2：改 setAttributes 必须手动 renderFrame

```javascript
sprite.setAttributes({ translationX: 100 });
// ❌ 不刷新
sprite.setAttributes({ translationX: 100 });
App.Draw1.getSurface().renderFrame();   // ✅ 必须重绘
```

### 坑3：RectSprite 的 Radius 是圆角，CircleSprite 的 Radius 是半径

同名属性含义不同，注意区分。

### 坑4：拼 path 数字要用 JSON.Serialize

服务端拼 path 时用 `JSON.Serialize(num)` 而非 `ToString()`，确保小数点恒为 `.`（避免不同区域设置导致坐标错误）。

### 坑5：Sprite 坐标是像素坐标

画布左上角为原点，y 轴向下。坐标范围按 `Width`/`Height` 像素排布，无自动 ViewBox 缩放（需自己用 `Scaling`/`TranslationX/Y` 适配）。

---

## 八、关联文档

| 文档 | 关系 |
|------|------|
| `extnet-chart-guide.md` | Chart 图表（底层同用 draw 包，Sprite 概念相通） |
| `extnet-status-board-pattern.md` | 状态看板（Draw 绘制自定义图形） |

## 九、参考来源

- 官方示例库：`Examples/Draw/Basic/`（12 示例）
  - `Actions/`：服务端 Add/SetAttributes/RenderFrame
  - `Animation/`：CompositeSprite + 客户端 Surface API
  - `Rotate_Text/`：TextSprite + 滑块旋转（最简入门）
  - `Rotate_Image/`：ImageSprite + SpriteEvents 事件交互
  - `Reflection/`：ImageSprite 镜像 + 渐变遮罩
  - `Analytics/`：服务端动态折线图
  - `Pie_Chart/`：服务端动态饼图 + 渐变
  - `Tiger/`：大规模 Path 矢量插画
