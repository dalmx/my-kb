---
title: Ext.NET Miscellaneous 杂项控件完整指南
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Miscellaneous, 杂项, Icon, Image, ProgressBar, Factory, SparkLine, Gauge, ToolTip, Resizable, Spotlight, XTemplate]
status: active
updated: 2026-08-29
---
# Ext.NET Miscellaneous 杂项控件完整指南

> 本文档从 Ext.NET 4.7.1 官方示例库 `Examples/Miscellaneous/` 提炼 Icon/Image/ProgressBar/Factory/SparkLine/Gauge/ToolTip/Resizable/MouseDistanceSensor/Spotlight/XTemplate 等。补强已有杂项文档。
>
> 适用：Ext.NET 4.x + Triton 主题。

---

## 一、Icon 内置图标

`Icon` 枚举有数百个值（FamFamFam Silk/Flag 图标集），任意支持 `Icon` 属性的控件可用。

```aspx
<ext:Button runat="server" Text="保存" Icon="Disk" />
<ext:Window runat="server" Icon="Application" />
```

服务端枚举所有图标：`Enum.GetNames(typeof(Icon))`；取 URL：`ResourceManager.GetIconUrl(icon)`。

---

## 二、Image 图片控件

支持平移（Pan）、可缩放（Resizable）。

```aspx
<ext:Image ID="img1" runat="server" ImageUrl="map.jpg" AllowPan="true">
    <Listeners>
        <Complete Handler="App.Label1.setText('加载完成');" />
        <Pan Handler="App.StatusBar1.setStatus({text:'X:'+x+' Y:'+y});" Buffer="100" />
    </Listeners>
</ext:Image>
```

| 属性/方法 | 作用 |
|-----------|------|
| `AllowPan="true"` | 开启拖拽平移 |
| `ImageUrl` | 图片地址 |
| `scrollTo(x,y)` | 滚动到坐标 |
| `getOriginalSize()` | 原始尺寸 `{width,height}` |

等比缩放：

```aspx
<ext:Image runat="server" ImageUrl="photo.jpg">
    <ResizableConfig runat="server" PreserveRatio="true" HandlesSummary="s e se" />
</ext:Image>
```

---

## 三、ProgressBar 进度条

```aspx
<ext:ProgressBar ID="pb1" runat="server" Width="300" Text="准备中..." />
```

**客户端方法**：

```javascript
App.pb1.updateProgress(0.5, '加载中 50%...');   // value 0~1
App.pb1.updateText('请稍候');
App.pb1.wait({ interval:200, duration:5000, increment:15 });  // 不定式等待
App.pb1.reset(true);   // 重置并隐藏
```

**服务端**：`pb1.UpdateProgress(floatValue, "步骤...")`。

**配合 TaskManager 轮询长任务**：

```csharp
protected void StartLongAction(object sender, DirectEventArgs e)
{
    Session["Progress"] = 0;
    ThreadPool.QueueUserWorkItem(LongTask);
    ResourceManager1.AddScript("{0}.startTask('poll');", tm1.ClientID);
}

protected void RefreshProgress(object sender, DirectEventArgs e)
{
    object p = Session["Progress"];
    if (p != null)
        pb1.UpdateProgress(((int)p) / 10f, "步骤 " + p + "/10");
    else
    {
        ResourceManager1.AddScript("{0}.stopTask('poll');", tm1.ClientID);
        pb1.UpdateProgress(1, "完成！");
    }
}
```

> `wait()` 是不定式滚动，`updateProgress(v,t)` 是定值，不可混用。

---

## 四、Factory 控件工厂（动态克隆）

注册一段控件树为全局工厂，之后用 `FactoryAlias` 克隆。

**注册（Global.asax，仅一次）**：

```csharp
// 委托方式
Ext.Net.ResourceManager.AddFactory(delegate {
    return new Ext.Net.Button {
        Text = "工厂按钮",
        Handler = "Ext.Msg.alert('提示','点击');"
    };
}, "mybutton", "My.Button");

// .ascx 方式
Ext.Net.ResourceManager.AddFactory("~/Controls/MyWindow.ascx", "mywindow", "My.Window");
```

**消费**：

```aspx
<ext:Button runat="server" Text="工厂按钮" FactoryAlias="mybutton" />
```

> Factory 内**不能用 `<Content>`**，只能用 `<Items>`（Content 无法克隆）。

---

## 五、SparkLine 迷你趋势图

无坐标轴的微型图表，6 种类型：`LineSparkLine`/`BoxSparkLine`/`BulletSparkLine`/`DiscreteSparkLine`/`PieSparkLine`/`TriStateSparkLine`。

```aspx
<ext:LineSparkLine runat="server" Width="100" Height="25" Values="6,10,4,-3,7,2" />
```

`Values` 是 double 数组或逗号字符串。适合表格单元格/卡片里的微型趋势条。

---

## 六、Gauge SVG 仪表盘（非 Chart 系）

独立 SVG 组件，配合 ViewModel 双向绑定。

```aspx
<ext:Panel ID="p1" runat="server" Title="仪表盘">
    <TopBar>
        <ext:Toolbar runat="server"><Items>
            <ext:Slider runat="server" BindString="{value}" FieldLabel="值" />
        </Items></ext:Toolbar>
    </TopBar>
    <Items>
        <ext:Gauge runat="server" BindString="{value}" Flex="1" />
        <ext:Gauge runat="server" TrackStart="180" TrackLength="360"
            UIName="green" BindString="{value}" Flex="1" />
    </Items>
</ext:Panel>
```

```csharp
p1.ViewModel = new { data = new { value = 30 } };  // 0~100
```

| 属性 | 作用 |
|------|------|
| `TrackStart`/`TrackLength` | 弧线起始角度/跨度（度），`180/360` 整圆 |
| `UIName="green"` | UI 主题 |
| `Needle` | 指针：`Arrow`/`Wedge`/`Spike` |
| `<TextTpl>` | 中心文字模板 |

> Gauge 必须配合 `ViewModel` + `BindString="{value}"` 驱动。

---

## 七、ToolTip 工具提示

```aspx
<!-- 基础 -->
<div id="tip1">悬停看提示</div>
<ext:ToolTip runat="server" Target="tip1" Html="简单提示" />

<!-- 可关闭可拖动 -->
<ext:ToolTip runat="server" Target="tip2" Title="提示" Html="点 X 关闭"
    AutoHide="false" Closable="true" Draggable="true" />

<!-- 跟随鼠标 -->
<ext:ToolTip runat="server" Target="tip3" Html="跟随" TrackMouse="true" />

<!-- 原生 HTML（QuickTip） -->
<div data-qtip="QuickTip 提示">悬停</div>
```

| 属性 | 作用 |
|------|------|
| `Target` | 目标元素 id 或 `={表达式}` |
| `TrackMouse="true"` | 跟随鼠标 |
| `AutoHide="false"` | 不自动隐藏 |
| `Anchor="top"` | 气泡箭头方向 |
| `Delegate=".x-grid-cell"` | 仅在匹配子元素触发 |
| `DismissDelay` | 自动隐藏延时（ms） |

**Grid 单元格 Tooltip**：

```aspx
<ext:ToolTip runat="server"
    Target="={#{Grid1}.getView().el}"
    Delegate=".x-grid-cell"
    TrackMouse="true">
    <Listeners><Show Fn="onShow" /></Listeners>
</ext:ToolTip>
```

```javascript
var onShow = function (tip) {
    var view = App.Grid1.getView();
    var record = view.getRecord(view.findItemByChild(tip.triggerElement));
    var column = view.getHeaderByCell(tip.triggerElement);
    tip.update(record.get(column.dataIndex));
};
```

---

## 八、Resizable 可缩放

```aspx
<!-- 独立 Resizer 绑到 DOM -->
<div id="box" style="width:200px;height:100px;">拖我缩放</div>
<ext:Resizer runat="server" Target="box" MinWidth="100" MinHeight="50"
    Pinned="true" Dynamic="true" />
```

| 属性 | 作用 |
|------|------|
| `Pinned="true"` | 句柄常驻可见 |
| `Dynamic="true"` | 拖动时实时改尺寸（默认代理框） |
| `PreserveRatio="true"` | 等比缩放（图片常用） |
| `Handles="All"` | 句柄方向（`N/S/E/W/NE/NW/SE/SW`） |

也可作为容器子配置：`<ResizableConfig runat="server" .../>`。

---

## 九、MouseDistanceSensor 鼠标距离感应

```aspx
<ext:Window runat="server" Title="靠近显示" Hidden="false">
    <Plugins>
        <ext:MouseDistanceSensor runat="server" MinOpacity="0.3" />
    </Plugins>
</ext:Window>
```

| 属性/事件 | 作用 |
|-----------|------|
| `MinOpacity` | 最小透明度（鼠标越远越透明） |
| `Threshold="25"` | 触发 Near 的距离阈值 |
| `Near`/`Far` 事件 | 进入/离开阈值 |

---

## 十、Spotlight 聚光灯（引导聚焦）

```aspx
<ext:Spotlight ID="spot" runat="server" Easing="EaseOut" Duration="300" />
<ext:Button runat="server" Text="开始引导">
    <Listeners><Click Handler="App.spot.show(App.Panel1);" /></Listeners>
</ext:Button>
<ext:Button runat="server" Text="下一步">
    <Listeners><Click Handler="App.spot.show(App.Panel2);" /></Listeners>
</ext:Button>
```

服务端：`spot.Show(panel)` / `spot.Hide()`。适合新手引导/强制聚焦。

---

## 十一、XTemplate 模板系统

### 语法

| 语法 | 作用 |
|------|------|
| `{FieldName}` | 字段插值 |
| `<tpl for=".">` | 遍历当前数组 |
| `<tpl for="Children">` | 切到子数组作用域 |
| `<tpl if="Age &gt; 0">` | 条件（`>` 必须写 `&gt;`） |
| `{parent.Name}` | 子作用域访问父 |
| `{#}` | 循环序号（1 起） |
| `{[ JS代码 ]}` | 执行任意 JS（`values`/`parent`/`xindex`） |

### 用法

```aspx
<ext:XTemplate ID="tpl1" runat="server">
    <Html>
        <tpl for=".">
            <div class="{[xindex % 2 === 0 ? 'even' : 'odd']}">
                <p>{Name}</p>
                <tpl for="Children">
                    <tpl if="Age &gt; 0">{Name} </tpl>
                </tpl>
            </div>
        </tpl>
    </Html>
</ext:XTemplate>

<ext:Panel runat="server">
    <Listeners>
        <AfterRender Handler="#{tpl1}.overwrite(this.body, data);" />
    </Listeners>
</ext:Panel>
```

服务端：`tpl.Overwrite(panel, data)` + `tpl.Render()` + `panel.UpdateLayout()`。

### TemplateWidget（可克隆模板控件）

```aspx
<ext:Window runat="server" IDMode="Ignore" Title="窗口"
    TemplateWidget="true" TemplateWidgetFnName="getWin">
    <Items>...</Items>
</ext:Window>

<ext:Button runat="server" Text="多开" Handler="App.getWin().show();" />
```

`TemplateWidgetFnName` 生成 `App.getWin(config, cached)` 工厂函数，第二参 `true` 用缓存实例。`IDMode="Ignore"` 让模板内控件 id 不全局注册（多实例必需）。

---

## 十二、踩坑要点

### 坑1：XTemplate 的 > 必须写 &gt;

```aspx
<tpl if="Age &gt; 0">   <!-- ✅ -->
<tpl if="Age > 0">      <!-- ❌ XML 解析失败 -->
```

### 坑2：Factory/TemplateWidget 不能用 Content

工厂/模板控件内**只能用 `<Items>`**，`<Content>` 无法克隆。

### 坑3：ProgressBar wait vs updateProgress

`wait()` 是不定式滚动条（无具体进度），`updateProgress(v,t)` 是定值。两者不可混用。

### 坑4：Grid Tooltip 的 Target 要用表达式

```aspx
Target="={#{Grid1}.getView().el}"   <!-- ✅ 视图已渲染元素 -->
Target="Grid1"                       <!-- ❌ 控件 ID 无效 -->
```

### 坑5：Resizable 默认代理框

不设 `Dynamic="true"`，拖动时只显示虚线框，松开才改尺寸。要实时改必须 `Dynamic="true"`。

### 坑6：Gauge 必须配 ViewModel

```csharp
p1.ViewModel = new { data = new { value = 30 } };   // 必须有
```
Gauge 的 `BindString="{value}"` 依赖 ViewModel 驱动。

---

## 十三、关联文档

| 文档 | 关系 |
|------|------|
| `extnet-chart-guide.md` | Chart 图表（Gauge/SparkLine 的对比） |
| `extnet-draw-guide.md` | Draw 绘图（XTemplate/Sprite 渲染） |
| `extnet-desktop-framework-guide.md` | Desktop（Factory 控件工厂应用） |
| `extnet-grid-tooltip-delegate.md` | Grid Tooltip（已有实战文档） |

## 十四、参考来源

- `Examples/Miscellaneous/Icon/`
- `Examples/Miscellaneous/Image/`（Pan / Resizable）
- `Examples/Miscellaneous/ProgressBar/`（Client_Side / Server_Side）
- `Examples/Miscellaneous/Factory/Basic/`
- `Examples/Miscellaneous/SparkLine/Basic/`
- `Examples/Miscellaneous/Gauge/`（Basic / Custom / Needles）
- `Examples/Miscellaneous/ToolTips/`（Overview / GridPanel_Cell / GridPanel_Row）
- `Examples/Miscellaneous/Resizable/Basic/`
- `Examples/Miscellaneous/Mouse_Distance_Sensor/`
- `Examples/Miscellaneous/Spotlight/`
- `Examples/Miscellaneous/XTemplate/`、`Render_Template/`、`Template_Widget/`
