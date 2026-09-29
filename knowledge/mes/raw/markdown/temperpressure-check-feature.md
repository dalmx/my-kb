---
category: 业务-通用
module: Curing
status: active
tags:
- 点检
- 参数快照
- TemperPressureTrend
- InsertByStatement
- PageAction
- 权限配置
- ECharts
- 横轴标签
- 抽稀
- CPP_STEAM_PLATFORM_CHECK
- Curing
- 温度压力趋势
- 点检人
- 点检时间
- 弹窗
title: 温度压力趋势图点检功能与 ECharts 横轴优化
updated: '2026-09-08'
---

# 温度压力趋势图点检功能与 ECharts 横轴优化

> Curing 子系统 TemperPressureTrend 页面（ReportCenter）新增"参数快照式点检"功能与 ECharts 横轴标签优化（分行+最大数量抽稀）的开发要点：Manager 基类 InsertByStatement 写库先例、标准工具栏按钮的 PageAction 权限配置、Mapper xml 改后 Rebuild+手动同步 Bin 的发布纪律。

## 一、功能概览

页面：`Plugins/Curing/ReportCenter/TemperPressureTrend.aspx(.cs)`，ECharts 双图（上温度/下压力），数据源 TB_SteamPlatform_Wanda_HourRpt 小时报表（每地沟每天 24 点）。2026-09-08 指标精简为 5 项（2 温度+3 压力，SQL 别名层中文名），同日新增点检：

- **点检**（btnCheck）：后台按当前地沟查**最新一条**点位参数（TOP 1 ORDER BY RECORD_TIME DESC，与页面查询区间解耦——点检永远反映点检时刻的"最新"），连同点检人（`this.Data.User.UserBarcode`）、点检时间（服务器 DateTime.Now）插入 CPP_STEAM_PLATFORM_CHECK 快照表。
- **查看点检**（btnViewCheck）：弹窗 ext:Window+GridPanel，按当前地沟查最近 200 条（点检时间倒序），地沟列 Renderer 转"1号地沟/总计"。

## 二、参数快照式点检（区别于加硫点检的图快照）

| 对比项 | 加硫点检（CuringCheck） | 蒸汽平台点检（本页） |
|---|---|---|
| 快照对象 | 整沟排曲线拼接大图 → FTP，表存 IMAGE_PATH | 5 项点位参数值直接存列（END_STEAM_TEMP 等 DECIMAL 列） |
| 权限形态 | 分组头 HTML 按钮 → 隐藏探针 Button（见 curing-check-dev-notes.md 四.3） | 标准 Toolbar ext:Button → 框架 setPageControls 直接控制 |
| 表 | CPP_CURING_CHECK | CPP_STEAM_PLATFORM_CHECK（建表脚本 P.Curing/数据库脚本/，OBJIDENTITY 主键+审计字段+CHECK_TIME/TRENCH 复合索引，DDL 交用户执行） |

快照列存英文列名、SELECT 时 AS 中文别名返回前端（与页面明细表口径一致）；SNAPSHOT_TIME 记快照来源的报表记录时间，与 CHECK_TIME（点检动作时间）分开存。

## 三、Manager 基类通用写库方法（IBaseManager）

Curing 各 `I XxxManager : IBaseManager<T>` 继承框架通用方法，**无需为单表功能铺 Entity/Data/Business/Mapper 七步全栈**，页面 aspx.cs 里借现有 Manager 直接调（蒸汽平台无专属 Manager，借 CppCuringProductionManager，语句加进其 Mapper xml）：

```csharp
DataTable dt = manager.GetDataTableByStatement("SelectXxx@Ns", param);   // 查询
manager.InsertByStatement("InsertXxx@Ns", new Dictionary<string, object> {
    { "COL1", v1 }, { "COL2", v2 } });                                    // 插入
manager.UpdateByStatement(...); manager.DeleteByStatement(...);          // 更新/删除
```

DirectMethod 返回 JSON 沿用页面既有约定 `new { error, message/rows }` + 前端 `JSON.parse`。

## 四、新增按钮权限配置（标准按钮）

aspx.cs 权限类 `__ : Wongoing.Web.UI.___` 加 PageAction，**ActionName 必须与按钮 ID 完全一致**：

```csharp
点检 = new PageAction() { ActionId = 3, ActionName = "btnCheck" };
查看点检 = new PageAction() { ActionId = 4, ActionName = "btnViewCheck" };
public PageAction 点检 { get; private set; }
public PageAction 查看点检 { get; private set; }
```

首次有权限用户访问页面后框架自动写入 SSP_PAGE_ACTION，**管理员须在角色管理把"点检/查看点检"授权给目标角色**，否则无权用户按钮被 Disabled（交付时提醒）。ActionId 接本页现有最大值 +1。

## 五、ECharts 横轴：日期时间分行 + 最大数量抽稀

- **分行**：记录时间是 `CONVERT(varchar(16), RECORD_TIME, 120)` → "yyyy-MM-dd HH:mm" 字符串，axisLabel.formatter 按最后一个空格拆 `\n` 两行（日期上/时间下），去掉 rotate:30；grid.bottom 加大（60）容纳两行标签+dataZoom slider。
- **抽稀语义**：用户明确否定"百分比"方案（百分比→标签数随数据量线性变密），采用**最大数量**语义：`xLabelMaxCount` 常量（本页定格 29），`interval = total <= max ? 0 : Math.ceil(total/max) - 1`——任何数据量标签数恒定不超标。一天 24 点全显，一周 168 点隔 5 显 1。
- 本页三个点检语句同样走 `$TRENCH$` 动态拼列名，后台 ValidateTrench 白名单（1~6/Total，非法回退 1）提取成私有方法供查询/点检共用，防 SQL 注入。

## 六、发布纪律（Mapper xml 改动）

Mapper xml 是 csproj 的 **EmbeddedResource**：改 xml 必须先 Rebuild（`//t:Rebuild`，Build 增量会假阳性）并 `grep -a "新语句id" bin/Debug/*.dll` 验证产物；**WebSite/Bin 无 .refresh 自动刷新**（部分 dll 有、Mapper 没有），须手动 cp 新 dll/pdb 到 `Wongoing.Curing.WebSite/Bin/`。aspx/aspx.cs 是网站项目动态编译，部署即生效。

## 七、关联

- `curing-check-dev-notes.md`：加硫点检（图快照+FTP+分组头权限探针）、UserBarcode、建表脚本交用户执行惯例
- `temperpressure-trend-echarts`（auto-memory）：本页 ECharts 选型与三处样式旧账
- `main-permission-system.md`：权限体系全貌（SSP_PAGE_ACTION/角色授权）


## 八、弹窗风格与 Curing 项目对齐（2026-09-08 补）

Curing 项目 Window 弹窗主流属性模式（TyreOutStroageLockInfo/PersonalProduceHourQuery/CuringBladderBindMaterial 等页统计）：

```aspx
<ext:Window ID="winXxx" runat="server" IconCls="fa fa-XXX" Closable="true" Title="..."
    Width="..." Height="..." Resizable="true" Hidden="true" Modal="true" Layout="FitLayout">
```

- **图标**：`IconCls="fa fa-XXX"`，不用老式 `Icon="ApplicationViewList"` 枚举；查看明细类弹窗用 `fa fa-file-text`（10 处）、上传类 `fa-upload`、编辑类 `fa-pencil-square`
- **不设** Maximizable / CloseAction（默认 Hide 即可）；UI 属性仅编辑表单类弹窗偶用 Primary，查看类不设
- 弹窗内 GridPanel 加 `Cls="border-top"`（winDetail 先例）+ `View(EnableTextSelection)`
- 工具栏按钮 fa 图标按项目用量选主流：确认/执行类 `fa-check-circle`（66 处）> 裸 fa-check（0 处）；统计法 `grep -ro "fa fa-XXX" --include='*.aspx' . | wc -l`（注意按完整 class 名，避免子串误计）
- Semi 平台的弹窗规范（extnet-window-style-standard.md）与 Curing 细节有差异（如 Semi 要求确定/关闭按钮、资源键 Title），跨子系统复用前以**本子系统页面统计**为准

---


## 九、弹窗颜色终局：Curing 两种标题栏色，用户认知的"系统色"是 Primary 深蓝（2026-09-08）

用户两轮反馈"弹窗颜色不对"、实测排查结论：

| 弹窗风格 | 标题栏色 | 系统内代表 | 用法 |
|---|---|---|---|
| 无 UI（default） | 浅蓝 `rgb(95,162,221)` | WinUpLoad(Excel导入)、winDetail(日志明细)、winFreeze | 查看类弹窗，数量最多 |
| `UI="Primary"` | 深蓝 `rgb(45,108,162)` | WinModify(账期维护)、planModify(修改行项目)、monthPlanAdd(新增) | 修改/新增类弹窗 |

- 本页点检记录弹窗最初无 UI（浅蓝），与系统查看类弹窗实测**完全同色**，用户仍认为"颜色不对"——**用户认知的"系统弹窗色"是 Primary 深蓝**（经 AskUserQuestion 用户拍板选深蓝），最终 `UI="Primary"` 落盘，刷新后 computed style `rgb(45,108,162)` 与 WinModify 完全一致（端到端验证通过）
- **排查方法论升级**：样式争议不要停留在属性对齐层面猜测，用内置浏览器 evaluate 读 `getComputedStyle` 对比 computed 值——`Ext.ComponentQuery.query('window')` 列出页面全部弹窗逐个读色，5 分钟定位"系统里本来就存在两种色"；css 规则可用 `document.styleSheets` 遍历 selectorText 定位（`.x-window-header-primary => rgb(45,108,162)`）
- **extExtra.css 不含弹窗颜色定义**（第八节 css 404 修复是必要卫生但不是弹窗色的原因）；弹窗标题栏色完全由 Ext.NET UI 机制（Triton 主题 axd 资源）决定
- 用户手开的页签（user tab）claim 后 screenshot 可能报 guest surface 错误，用 evaluate 读 computed style 替代视觉验证

---


## 十、补充：Ext.Msg 提示框不吃 Window 的 UI（2026-09-08）

用户反馈"点检的弹窗没改"的最终定位：`Ext.Msg.confirm/alert` 是 **Ext.MessageBox 单例**（ui=default 浅蓝），Window 上的 `UI="Primary"` 管不到它——点"点检"按钮第一眼看到的确认框仍是浅蓝。项目无 MessageBox 样式覆盖先例，解法是**本页 head 内嵌 style**（只影响本页，不动全站 extExtra.css）：

```css
/* 本页提示框(Ext.Msg 确认/提示)标题栏统一为系统 Primary 深蓝 #2d6ca2，与点检记录弹窗一致 */
.x-message-box .x-window-header { background-color: #2d6ca2 !important; }
.x-message-box .x-window-header .x-title-text { color: #ffffff; }
.x-message-box .x-window-header .x-tool-img { background-color: #2d6ca2; }
```

- 深蓝值 `#2d6ca2` = Triton `.x-window-header-primary` 的 rgb(45,108,162)；标题文字色用白色——与 Primary 弹窗的 `.x-title-text` 实测同色（header 容器的 color 是深灰 rgb(64,64,64)，别被它误导，以 `.x-title-text` 的 computed color 为准）
- 用户视角的"弹窗"包含 Window 弹窗 **和** Ext.Msg 提示框两层——颜色统一诉求交付前两层都要核