---
title: Ext.NET Calendar 日历 / ColorPicker 颜色选择 / Keys 键盘映射完整指南
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Calendar, 日历, CalendarPanel, EventStore, ColorPicker, 颜色选择, KeyMap, KeyNav, 键盘映射, 快捷键]
status: active
updated: 2026-08-29
---
# Ext.NET Calendar 日历 / ColorPicker 颜色选择 / Keys 键盘映射完整指南

> 本文档从 Ext.NET 4.7.1 官方示例库 `Examples/Calendar/`、`ColorPicker/`、`Keys/` 提炼。目标是让 AI/开发者读完即可复现日历事件管理、颜色选择、键盘快捷键。
>
> 适用：Ext.NET 4.x + Triton 主题。

---

## 一、Calendar 日历

## 二、CalendarPanel 核心结构

`<ext:CalendarPanel>` 是核心容器，内含两个 Store 和若干视图：

```aspx
<ext:CalendarPanel ID="CalendarPanel1" runat="server" Region="Center" ActiveIndex="2">
    <%-- 日历分类存储（不同颜色/分组） --%>
    <CalendarStore ID="CalendarStore1" runat="server">
        <Calendars>
            <ext:CalendarModel CalendarId="1" Title="工作" />
            <ext:CalendarModel CalendarId="2" Title="个人" />
        </Calendars>
    </CalendarStore>

    <%-- 视图（不写用默认；写了可定制） --%>
    <MonthView runat="server" ShowHeader="true" ShowWeekLinks="true" />
    <WeekView runat="server" />
    <DayView runat="server" />

    <Listeners>
        <EventClick Fn="onEventClick" />
        <DayClick Fn="onDayClick" />
        <EventMove Fn="onEventMove" />
        <EventResize Fn="onEventResize" />
    </Listeners>
</ext:CalendarPanel>
```

| 属性/子元素 | 作用 |
|------------|------|
| `ActiveIndex` | 默认视图：0=日/1=周/2=月 |
| `CalendarStore` | 日历分类（颜色/分组），每项是 `CalendarModel` |
| `MonthView`/`WeekView`/`DayView` | 视图配置 |
| `EventStore` | 事件数据存储 |

## 三、事件数据模型 EventModel 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `EventId` | int | 事件唯一 ID |
| `CalendarId` | int | 关联 CalendarModel（决定颜色/分组） |
| `Title` | string | 标题 |
| `StartDate` | DateTime | 开始时间 |
| `EndDate` | DateTime | 结束时间 |
| `IsAllDay` | bool | 是否全天 |
| `Location` | string | 地点（可选） |
| `Notes` | string | 备注（可选） |
| `Reminder` | string | 提醒（分钟数："15"/"60"） |

## 四、绑定事件数据

### 方式 A：后台直接 Add（最简）

```csharp
protected void Page_Load(object sender, EventArgs e)
{
    if (!X.IsAjaxRequest)
    {
        this.CalendarPanel1.EventStore.Events.AddRange(new EventModelCollection {
            new EventModel {
                EventId = 1001, CalendarId = 1,
                Title = "会议",
                StartDate = DateTime.Now.AddHours(10),
                EndDate = DateTime.Now.AddHours(12),
                IsAllDay = false
            }
        });
    }
}
```

### 方式 B：远程 AjaxProxy 加载

```aspx
<EventStore ID="EventStore1" runat="server" NoMappings="true">
    <Proxy>
        <ext:AjaxProxy Url="CalendarService.asmx/GetEvents" Json="true">
            <ActionMethods Read="POST" />
            <Reader>
                <ext:JsonReader RootProperty="d" />
            </Reader>
        </ext:AjaxProxy>
    </Proxy>
</EventStore>
```

```csharp
[ScriptService]
public class CalendarService : WebService
{
    [WebMethod]
    public EventModelCollection GetEvents(DateTime? start, DateTime? end)
    {
        return GetEventsFromDb(start, end);
    }
}
```

> asmx 返回 JSON 数据包在 `.d` 字段，故 `JsonReader RootProperty="d"`。

## 五、EventWindow 编辑窗

```aspx
<ext:EventWindow ID="EventWindow1" runat="server" Hidden="true"
    CalendarStoreID="CalendarStore1">
    <Listeners>
        <EventAdd Fn="onAdd" />
        <EventUpdate Fn="onUpdate" />
        <EventDelete Fn="onDelete" />
    </Listeners>
</ext:EventWindow>
```

```javascript
var onDayClick = function (cal, dt, allDay, el) {
    App.EventWindow1.show({ StartDate: dt, IsAllDay: allDay }, el);  // 新增
};

var onEventClick = function (cal, rec, el) {
    App.EventWindow1.show(rec, el);  // 编辑
};

var onUpdate = function (win, rec) {
    win.hide();
    rec.commit();
    App.EventStore1.sync();
};
```

## 六、八个核心事件

| 事件 | 触发时机 |
|------|---------|
| `EventClick` | 点击事件 |
| `DayClick` | 点击空白处（新增） |
| `RangeSelect` | 框选时间范围 |
| `EventMove` | 拖动事件 |
| `EventResize` | 拉伸事件时长 |
| `EventAdd` / `EventUpdate` / `EventDelete` | 增删改 |

---

## 七、ColorPicker 颜色选择

## 八、基础 ColorPicker

`Value` 是 6 位十六进制颜色字符串（**不带 #**，如 `"FF7F00"`）。

### 三种触发模式

```aspx
<!-- 1. Listener 模式（纯前端，最快） -->
<ext:ColorPicker ID="cp1" runat="server">
    <Listeners>
        <Select Fn="function(picker, color){ /* color 如 'FF7F00' */ }" />
    </Listeners>
</ext:ColorPicker>

<!-- 2. DirectEvent 模式（AJAX 回发） -->
<ext:ColorPicker ID="cp2" runat="server">
    <DirectEvents>
        <Select OnEvent="ColorChanged">
            <EventMask ShowMask="true" />
        </Select>
    </DirectEvents>
</ext:ColorPicker>

<!-- 3. PostBack 模式 -->
<ext:ColorPicker ID="cp3" runat="server" AutoPostBack="true" OnColorChanged="ColorChanged" />
```

```csharp
protected void ColorChanged(object sender, EventArgs e)
{
    string color = this.cp2.Value;   // 如 "FF7F00"
}
```

### 自定义颜色集

```csharp
this.cp1.Colors = new string[] { "FF0000", "00FF00", "0000FF", "FFFF00" };
```

## 九、高级组件

| 控件 | 作用 |
|------|------|
| `ext:ColorButton` | 标题栏小色块按钮，`Change` 事件 |
| `ext:ColorField` | 表单字段，`Change` 事件，可提交 |
| `ext:ColorSelector` | 完整选择器（含 OK/Cancel，支持 alpha） |

**ColorField 在表单中**：

```aspx
<ext:ColorField ID="cf1" runat="server" FieldLabel="颜色">
    <DirectEvents>
        <Change OnEvent="OnColorChange">
            <ExtraParams>
                <ext:Parameter Name="color" Value="newValue" Mode="Raw" />
            </ExtraParams>
        </Change>
    </DirectEvents>
</ext:ColorField>
```

> 高级组件的颜色值含 `#`（如 `#0f0f0fff` 含 alpha），与基础 ColorPicker（无 `#`）不同。

---

## 十、Keys 键盘映射

## 十一、组件内嵌 KeyMap（推荐，最简）

直接挂在 Viewport/Window/Panel 上：

```aspx
<ext:Window ID="Win1" runat="server" Title="ESC 关窗" Width="400" Height="300">
    <Listeners>
        <AfterRender Handler="this.focus();" />   <!-- 需聚焦才能接收按键 -->
    </Listeners>
    <KeyMap>
        <ext:KeyBindItem Key="esc" Handler="#{Win1}.close();" />
        <ext:KeyBindItem Key="ctrl+s" Handler="save();" />
    </KeyMap>
</ext:Window>
```

`Key` 字符串语法：`esc` / `enter` / `delete` / `ctrl+s` / `shift+e` / `alt+x`（修饰符与键名用 `+` 或 `-` 连接）。

## 十二、独立 KeyMap（全局）

```aspx
<ext:KeyMap runat="server" Target="={Ext.getBody()}">
    <Binding>
        <ext:KeyBinding Handler="#{Panel1}.toggleCollapse();">
            <Keys><ext:Key Code="P" /></Keys>
        </ext:KeyBinding>
    </Binding>
</ext:KeyMap>
```

| 元素 | 作用 |
|------|------|
| `Target="={JS表达式}"` | 目标元素（`={Ext.getBody()}` 或 `={Ext.getDoc()}`） |
| `<ext:KeyBinding Handler="JS">` | 按键处理 |
| `<ext:Key Code="N" />` | 键码（字符或常量名） |

`Code` 可用：字符（`N`/`A`）、键名常量（`DELETE`/`RIGHT`/`UP`/`ENTER`/`ESC`/`HOME`）。

## 十三、KeyNav（导航式）

用语义化方向名：

```aspx
<ext:KeyNav runat="server" Target="={document.body}">
    <Left  Handler="move('left');" />
    <Right Handler="move('right');" />
    <Up    Handler="move('up');" />
    <Down  Handler="move('down');" />
    <Home  Handler="move('home');" />
</ext:KeyNav>
```

每个标签名就是一个方向事件。

## 十四、修饰键属性（Window 内嵌）

```aspx
<ext:Window ID="Win1" runat="server">
    <KeyMap>
        <Binding>
            <ext:KeyBinding Ctrl="true" DefaultEventAction="PreventDefault"
                Handler="#{Win1}.setWidth(#{Win1}.getSize().width+10);">
                <Keys><ext:Key Code="RIGHT" /></Keys>
            </ext:KeyBinding>
        </Binding>
    </KeyMap>
</ext:Window>
```

- `Ctrl="true"` / `Alt="true"` / `Shift="true"`：修饰键
- `DefaultEventAction="PreventDefault"`：阻止浏览器默认行为

## 十五、Grid 行级键盘（DELETE 删除）

```aspx
<ext:GridPanel runat="server">
    <View>
        <ext:GridView runat="server">
            <Listeners>
                <ItemKeyDown Handler="if (e.getKeyName()=='DELETE') deleteRow(item, record);" />
            </Listeners>
        </ext:GridView>
    </View>
</ext:GridPanel>
```

```javascript
var deleteRow = function (view, record) {
    Ext.Msg.confirm('确认', '删除选中行？', function (btn) {
        if (btn == 'yes') view.getStore().remove(record);
    });
};
```

`e.getKeyName()` 返回 `'DELETE'`/`'ENTER'` 等键名。

---

## 十六、踩坑要点

### 坑1：Calendar 的 CalendarStore 是"分类"，EventStore 是"事件"

不要混淆。CalendarStore 装日历分类（颜色分组），EventStore 装具体事件，事件通过 `CalendarId` 关联分类。

### 坑2：基础 ColorPicker 的 Value 不带 #

```javascript
// ✅ 正确
Ext.get(el).setStyle('background-color', '#' + color);

// ❌ color 已含 # 会变 ##
```

高级组件（ColorButton/ColorField）的值含 `#`，两者不同。

### 坑3：Window 接收键盘需先聚焦

```aspx
<Listeners>
    <AfterRender Handler="this.focus();" />   <!-- 必须 -->
</Listeners>
```

不聚焦，按 ESC 无反应。

### 坑4：KeyBindItem 的 Key 字符串用小写

```aspx
<ext:KeyBindItem Key="esc" />      <!-- ✅ 小写 -->
<ext:KeyBindItem Key="ESC" />      <!-- ❌ 可能不匹配 -->
```

### 坑5：独立 KeyMap 的 Target 要用 ={} 包裹

```aspx
<ext:KeyMap Target="={Ext.getBody()}">    <!-- ✅ -->
<ext:KeyMap Target="Ext.getBody()">        <!-- ❌ 当字符串 -->
```

---

## 十七、关联文档

| 文档 | 关系 |
|------|------|
| `extnet-window-guide.md` | Window（ESC 关窗、键盘操作） |
| `extnet-store-databinding-guide.md` | Store（日历事件数据源） |
| `extnet-grid-complete-guide.md` | GridPanel（行级键盘删除） |

## 十八、参考来源

- `Examples/Calendar/Overview/`（Basic / Remote_Data）
- `Examples/ColorPicker/`（Basic / Advanced）
- `Examples/Keys/`（KeyMap / KeyNav / Panel_Keys）
