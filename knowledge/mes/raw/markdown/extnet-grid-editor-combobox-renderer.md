---
title: GridPanel 编辑列 ComboBox 选中后显示 value 的坑与 Renderer 解决
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, GridPanel, Column, Editor, ComboBox, Renderer, ValueField, DisplayField, 踩坑]
status: active
updated: 2026-08-29
---
# GridPanel 编辑列 ComboBox 选中后显示 value 的坑与 Renderer 解决

> Editor 管编辑、Renderer 管显示：编辑列内嵌 ComboBox 选定后写回单元格的是 ValueField（编码），DisplayField 不会自动影响显示——必须给列加 Renderer，在 ComboBox 绑定的 Store 里按编码查名称（判空 + find 结果兜底）；数据量大时预构建 {编码:名称} 映射表做 O(1) 查找。此模式适用于一切"列存编码、显示名称"的字典列。

## 一、现象

在 GridPanel 列里放 `<Editor>` 内嵌 ComboBox 做行内编辑：
- 进入编辑态，ComboBox 下拉显示名称（DisplayField），一切正常。
- **选定后退出编辑态，单元格显示的是 ValueField（编码/ID），而不是名称**，影响查看。

```text
期望：设备类型列显示 "注塑机"
实际：设备类型列显示 "M001"（即 ValueField 值）
```

## 二、根因

Grid 单元格存的是 Store 的原始字段值（`DataIndex` 对应的 value）。ComboBox 作为 Editor 只负责**编辑时**的输入，编辑结束后把 ValueField 写回 record，单元格**显示**由 Column 的 Renderer 决定。若列没有 Renderer，就直接把 value 原样渲染出来，于是看到的是编码而非名称。

> 即：Editor 管"怎么编辑"，Renderer 管"怎么显示"，两者各司其职。Editor 的 DisplayField 不会自动影响单元格显示。

## 三、解决：给列加 Renderer

在 Column 上加 `<Renderer Fn="..."/>`，把 value（编码）翻译成名称。

### 3.1 完整示例

```xml
<ext:Column runat="server" Text="设备类型" DataIndex="EqupType_Code" Align="Center" Width="100">
    <Editor>
        <ext:ComboBox ID="add_error_type" runat="server" Editable="false" AllowBlank="false"
            ValueField="Mouldtypeid" DisplayField="Mouldtypename">
            <Store>
                <ext:Store runat="server" ID="typestore">
                    <Model>
                        <ext:Model runat="server">
                            <Fields>
                                <ext:ModelField Name="Mouldtypeid" />
                                <ext:ModelField Name="Mouldtypename" />
                            </Fields>
                        </ext:Model>
                    </Model>
                </ext:Store>
            </Store>
            <Listeners>
                <FocusLeave Handler="BindJiTai(this)" />
            </Listeners>
        </ext:ComboBox>
    </Editor>
    <!-- 关键：Renderer 把编码翻译成名称 -->
    <Renderer Fn="LawClassRenderer" />
</ext:Column>
```

### 3.2 Renderer 函数

```javascript
var LawClassRenderer = function (value) {
    if (!value) return '';   // 空值直接返回空串
    // 在 typestore 里按 ValueField 查找，返回 DisplayField
    var item = App.typestore.data.items.find(function (item, index) {
        return item.data.Mouldtypeid == value;
    });
    return item ? item.data.Mouldtypename : '';
};
```

要点：
- 函数接收 `value`（单元格当前值，即编码），返回要显示的文本（名称）。
- 先判空 `!value`，避免空单元格 `find` 报错。
- `find` 找不到时返回 `undefined`，再访问 `.data` 会抛错 → 必须判 `item ?`。
- `App.typestore` 是 ComboBox 绑定的 Store 的客户端引用（ID 对应 aspx 里 `ID="typestore"`）。

> ⚠️ 原始写法 `return !value ? '' : App.typestore.data.items.find(...).data.Mouldtypename;` 在 find 找不到时会因对 `undefined` 取 `.data` 而报错。建议加判空兜底，见上方改进版。

## 四、Renderer 通用模式：value → 名称 映射

本例是一个通用模式的特例：**列存编码，显示名称**。推广到任何"编码/字典列"：

```javascript
var xxxRenderer = function (value) {
    if (!value) return '';
    var item = App.<storeID>.data.items.find(function (it) {
        return it.data.<ValueField> == value;
    });
    return item ? item.data.<DisplayField> : value;  // 找不到时回退显示原值
};
```

| 占位 | 含义 |
|------|------|
| `<storeID>` | ComboBox 绑定的 Store 的客户端 ID |
| `<ValueField>` | 编码字段名（如 Mouldtypeid） |
| `<DisplayField>` | 名称字段名（如 Mouldtypename） |

## 五、注意

- **Editor 的 Store 必须在编辑前已加载**，否则 Renderer 查不到名称 → 单元格显示空或原值。可在页面 `AfterRender` 时预载 Store。
- 若 Store 数据量大，每次渲染都 `find` 全表遍历有性能开销。可预构建 `{编码:名称}` 映射表（Map/Object），Renderer 里 O(1) 查找：

```javascript
var typeMap = {};
App.typestore.data.items.forEach(function (it) {
    typeMap[it.data.Mouldtypeid] = it.data.Mouldtypename;
});
var LawClassRenderer = function (value) {
    return typeMap[value] || '';
};
```

- 只读展示列（非编辑列）若也要"编码显示成名称"，同样用此 Renderer 模式，只是不需要 `<Editor>`。

## 六、关联

- Renderer 基本写法（Fn vs Handler）：见 `extnet-grid-complete-guide.md` 第三节
- 动态列带 Renderer：见 `dynamic-column-grid.md`
- ComboBox 属性速查（ValueField/DisplayField 等）：见 `extnet-combobox-properties.md`
