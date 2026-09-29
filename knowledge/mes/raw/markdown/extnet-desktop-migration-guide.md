---
title: Ext.NET Desktop 桌面页面开发与迁移指南
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, Desktop, 桌面框架, 进阶, 避坑]
status: active
updated: 2026-08-29
---
# Ext.NET Desktop 桌面页面开发与迁移指南

> 基于 Wongoing.Batch.WebSite 的 Desktop.aspx 实战开发，迁移至 Wongoing.Main.WebSite。
> 适用于 Ext.NET v4.7 + Triton 主题 + ASP.NET WebSite（CodeFile 动态编译）项目。

## 一、页面三件套结构

```text
Plugins/<子系统>/Desktop/
├── Desktop.aspx          ← 标记文件（~1900行，含内联 JS/CSS + ext:Desktop 控件）
├── Desktop.aspx.cs       ← 代码（~590行，Page_Load + BuildKanban + XlsxParser）
└── resources/
    ├── desktop.css       ← 快捷方式图标 + 右键菜单样式
    ├── wallpapers/       ← Blue.jpg, desk.jpg（预设壁纸）
    ├── *.png/gif         ← 快捷方式图标图片（window48x48.png 等）
    └── ...
```

外部资源依赖（根 resources/ 下）：
- `resources/css/font-awesome.min.css` + `resources/fonts/`（FontAwesome 字体）
- `resources/css/theme.css`、`extExtra.css`
- `resources/js/echarts.min.js`（看板折线图，**Main 项目原本没有，需新增**）

## 二、核心功能实现

### 2.1 桌面快捷方式（Shortcut）
- `<ext:DesktopModule>` 的 `<Shortcut Name="英文" IconCls="sc-icon sc-xxx" />`
- **Name 必须英文**（Ext.NET 用 Name 生成 DOM id `Name-shortcut`，中文会报非法 id）
- 渲染后用 JS `renameShortcuts()` 把英文文本替换成中文显示
- 9 个彩色图标用 `.sc-icon` + `::after` FontAwesome 字符实现（desktop.css）

### 2.2 快捷方式拖拽 + 网格吸附（关键功能）
- **拖拽**：mousedown/mousemove/mouseup 实时跟随（不用 HTML5 Drag API，太粗糙）
- **网格吸附**：松手时 `snapToGrid()` 吸附到固定网格格（92×102px），天然不重叠
- **位置持久化**：localStorage 按 `sc_pos_<工号>_<图标ID>` 存，按用户隔离
- **防闪烁**：加载时 `<style id="hide-shortcuts">` 隐藏图标 + 延迟显示
- **防 Ext.NET 重排**：override `desk.arrangeShortcuts`，窗口 resize 时跳过自动排列

```javascript
// 网格参数（固定常量，不随图标尺寸波动）
var GRID_CELL_W = 92, GRID_CELL_H = 102;
var GRID_OFFSET_X = 8, GRID_OFFSET_Y = 8;

var snapToGrid = function (el, x, y) {
    var cell = { w: GRID_CELL_W, h: GRID_CELL_H };
    // ...四舍五入到最近格，被占则螺旋找空格
};
```

### 2.3 右键菜单（桌面背景 + 图标）
- **桌面背景右键**：自定义 `Ext.menu.Menu`（刷新/平铺/层叠/显示桌面/还原/排列图标/壁纸设置/关于）
  - DesktopConfig **不支持** `<ContextMenu>` 子标签（无效，Ext.NET 默认只有英文 Tile/Cascade）
  - 用 DOM 捕获阶段 `addEventListener('contextmenu', fn, true)` + `stopImmediatePropagation` 拦截
- **图标右键**：打开 / 重命名
  - 重命名用 `Ext.Msg.prompt`，存 localStorage `sc_name_<工号>_<图标ID>`
  - 加载时 `renameShortcuts` 先默认映射，再覆盖自定义名
  - 图标 contextmenu 也用捕获阶段注册，阻止 Ext.NET 默认英文菜单

### 2.4 壁纸功能
- **预设壁纸**：`wallpapers` 数组（{url, name}），壁纸设置子菜单单选切换
- **用户上传**：`uploadCustomWallpaper()` → canvas 压缩（最大边1920, JPEG 0.85）→ Base64 存 localStorage（`wp_custom_<工号>`，限 4MB）
- **应用壁纸**：调用 Ext.NET 原生 `Ext.net.Desktop.desktop.setWallpaper(bg)`（最可靠），兜底设 backgroundImage
- 切换值 `wp_<工号>`：预设=url，自定义='custom'

### 2.5 任务栏定制
- 隐藏开始按钮（`.ux-start-button`，**注意带连字符**）、快速启动、托盘、时钟
- 只保留窗口标签栏（`.ux-desktop-windowbar`）
- QuickStartWidth/TrayWidth 设 0，清空 Items

### 2.6 拖动后图标可点击（避坑）
- **不能用 `pointerEvents='none'`**（破坏 Ext.NET mousedown→click 配对，导致图标永久点不开）
- 改用 `_suppressScId` 标记 + document click 捕获阶段拦截（仅被拖图标自身，一次性）

### 2.7 图标文字两行省略号
```css
.ux-desktop-shortcut-text {
    display: -webkit-box !important;
    -webkit-box-orient: vertical !important;
    -webkit-line-clamp: 2 !important;
    line-height: 16px !important;
    height: 34px !important;  /* 2行×16 + 2容差 */
    padding: 0 !important; margin: 0 !important; border: 0 !important;
    overflow: hidden !important;
}
```

## 三、迁移到其他子系统项目（以 Main 为例）

### 3.1 前提条件
目标项目必须是同构 WebSite（CodeFile 模式）+ Ext.Net.dll + Triton 主题。各子系统（Batch/Main/Quality/Semi...）均符合。

### 3.2 复制文件
```text
源: Plugins/Batch/Desktop/  →  目标: Plugins/Main/Desktop/
- Desktop.aspx（改 Inherits="Plugins_Main_Desktop_Desktop"）
- Desktop.aspx.cs（改类名 Plugins_Main_Desktop_Desktop）
- resources/（desktop.css + wallpapers + 图标 png）
```

### 3.3 资源路径
- 目录层级一致（`Plugins/<子系统>/Desktop/`），`../../../resources/` 前缀**无需改**
- 检查目标项目根 resources 是否有：font-awesome.min.css、theme.css、extExtra.css、echarts.min.js
- **echarts.min.js 通常缺失，需从源项目复制**

### 3.4 web.config 程序集引用（CS0246 ZipArchive 报错）
Desktop.aspx.cs 的 XlsxParser 用 `System.IO.Compression.ZipArchive` 解析 Excel。目标项目 web.config 需添加：
```xml
<compilation>
  <assemblies>
    <add assembly="System.IO.Compression, Version=4.0.0.0, Culture=neutral, PublicKeyToken=B77A5C561934E089"/>
    <add assembly="System.IO.Compression.FileSystem, Version=4.0.0.0, Culture=neutral, PublicKeyToken=B77A5C561934E089"/>
  </assemblies>
</compilation>
```

### 3.5 Session 依赖
- `Session["Barcode"]`（用户工号，用于 localStorage 隔离）
- 页面需登录态访问

## 四、踩坑记录

### 坑1：nul 保留名文件导致 IOException
- **现象**：打开页面报 `IOException: 文件名、目录名或卷标语法不正确`，堆栈在 `BuildManager.CheckTopLevelFilesUpToDate → get_CreationTimeUtc`
- **根因**：执行 shell 命令 `2>nul` 时，git-bash 把 `nul` 当普通文件名创建了（Windows 里 nul 是保留设备名）
- **删除**：常规 del/Remove-Item 无效（系统拦截），需用 `\\?\` 长路径前缀 + `[System.IO.File]::Delete()`
- **预防**：Windows 环境统一用 `2>/dev/null` 而非 `2>nul`

### 坑2：开始按钮 class 名
- Ext.NET 4.x 的开始按钮是 `.ux-start-button`（带连字符），不是 `.ux-startbutton`

### 坑3：右键菜单位置预渲染
- 不能用 `showAt(-9999,-9999)` 预渲染测尺寸（留下空框），改用「先 show 拿尺寸 → 超出视口再修正坐标」

### 坑4：菜单外层白框
- Ext.NET Menu 浮动结构是 `.x-menu.x-layer`（外层）+ `.x-menu-body`（内层），外层默认白底直角会露出
- 外层设 `background:transparent`，只在内层画背景+圆角

## 五、关键代码位置索引（Desktop.aspx 内）

| 功能 | 函数/位置 | 说明 |
|------|----------|------|
| 快捷方式拖拽 | `initShortcutDrag()` | mousedown/mousemove/mouseup |
| 网格吸附 | `snapToGrid()` | 固定网格 + 螺旋找空格 |
| 加载对齐校正 | `reAlignAllShortcuts()` | 修复旧版动态网格的不对齐 |
| 位置持久化 | `scGetPos/scSetPos` | localStorage 按工号隔离 |
| 桌面右键菜单 | `initDesktopContextMenu()` | 捕获阶段拦截 Ext.NET 默认菜单 |
| 图标右键菜单 | `showShortcutMenu()` | 打开/重命名 |
| 改名 | `renameShortcut()` + `renameShortcuts` | 存/读 localStorage |
| 壁纸上传 | `uploadCustomWallpaper()` | canvas 压缩 Base64 |
| 壁纸应用 | `applyWallpaper()` | setWallpaper API |
| 任务栏隐藏 | `renameShortcuts` 内 | 隐藏开始/快捷/托盘/时钟 |
| 防闪烁 | `showShortcutsCSS()` + `restoreShortcutPos()` | hide-shortcuts CSS + 防抖 |
| Excel 解析 | `XlsxParser`（Desktop.aspx.cs） | System.IO.Compression + Xml |

---

## 六、进阶开发（二期）— 见独立文档

> 以下功能在二期开发新增，完整指南见 **`extnet-desktop-advanced-guide.md`**（Ext.NET Desktop 桌面进阶开发）。

| 功能 | 要点 | 进阶文档章节 |
|------|------|------------|
| 右侧菜单树侧栏 | 官方 Slide panel 方案（浮动 Panel + alignTo + MouseDistanceSensor），**不要**把 Desktop 放进 BorderLayout | 一、右侧菜单树侧栏 |
| 菜单树数据移植 | TreeList + TreeStore，独立 Session key 自查权限（不复用 MainFrame 的 UserPageList） | 一.5 |
| TreeList 右键菜单 | TreeList **无 ItemContextMenu 事件**，用 document 事件委托 | 一.6 |
| 用户自定义快捷方式 | 纯客户端 DOM 动态添加（Ext.NET 无 addShortcut API），::after 伪元素图标 | 二、自定义快捷方式 |
| 图标选择器 | 内置 FontAwesome 图标+颜色自选，content 用 `\<hex>` 转义 | 二.5 |
| 菜单点击桌面弹窗 | 服务端 `Desktop.GetInstance().CreateWindow`（保证任务栏标签），不要 ShowMask | 三、桌面内弹窗 |
| 多窗口层叠不重叠 | 服务端计数器 X/Y += 24 | 三.3 |
| TaskBar 跳动根治 | 内层 `.x-box-target` 空态仅 1px，用 CSS **min-height**（不用 height，会与 ExtJS 布局引擎冲突） | 四、TaskBar 修复 |
| 登录模式选择 | Login.aspx 加经典/桌面 radio + 跳转分支 + localStorage 记忆 | 五、登录模式 |

**15 个避坑要点**（含 TreeList 无 ItemContextMenu、Node 无 AppendChild、Layout 是 string、TaskBar 用 min-height 等）见进阶文档第六章。