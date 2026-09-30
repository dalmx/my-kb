---
category: 业务-通用
factory: 通用
module: Batch
status: active
tags:
- RECORD_USER_ID
- Session
- Data.User
- UserBarcode
- 登录会话
- 家族级bug
- 记录人
title: 硫化工序作业日报样式-3（表单式填报看板）实现方案
updated: '2026-09-19'
---

# 硫化工序作业日报样式-3（表单式填报看板）实现方案

> SQ-PK01 样式-3 第 7 个日报族页面：30 列纸表还原 + 实时查硫化计划自动取数 + 手输 H/D 宽表落库。零存储过程零定时任务（修理日报路线）。判定符号 ⊗ 的 GBK 陷阱、BOM 参数取仕样时间、IISExpress 双实例路由排障是本文三大新知。
> 页面：`Plugins/Batch/Report/CuringDailyReport3.aspx(.cs)`（Batch 项目）｜手输表：`CPP_CURING_DAILY3_DATA`

## 一、与兄弟日报的关键差异（家族第 7 页）

| 维度 | 本页（样式-3） | 样式-1（CuringDailyReport） | 修理日报 |
|---|---|---|---|
| 数据载体 | **H/D 宽表**（D=日期×班×机台×侧，H=日期×班签字） | 字段级长表 FIELD_KEY | 长表 FIELD_KEY |
| 自动项 | **页面实时查计划**（零快照零 proc） | 存储过程+定时任务写快照 | 读硫化快照 |
| 判定交互 | 点检判定 √/×/⊗ **点选即存**；温度判定**手输** | 无此结构 | cdr-yn 点选 |
| 行结构 | 机台×左/右两行（机台/规格/合计 rowspan=2） | 固定格子 | 点检双机并排 |

适用：固定维度网格（机台×侧）且自动项可实时从业务表取的表单日报；变长规格行场景仍用一检/仕上的 H/D 按规格行模式。

## 二、表事实（schema 实证）

### CPP_CURING_DAILY3_DATA（手输宽表，建表 SQL 在 `Batch/sql/CppCuringDaily3Data_建表.sql`）
- 维度：`ROW_TYPE('H'/'D') + REPORT_DATE(DATE) + SHIFT_CODE(VARCHAR 2,'01'早/'03'夜) + EQUIP_CODE(VARCHAR 30,H行''占位) + EQUIP_POSITION(VARCHAR 2,'L'/'R',H行''占位)`
- **唯一索引** `(REPORT_DATE, SHIFT_CODE, ROW_TYPE, EQUIP_CODE, EQUIP_POSITION)`（即查询索引，前导 REPORT_DATE）
- D 行手输列：`REAL_TIME INT`（实际时间·秒）、`TIME_JUDGE NVARCHAR(2)`（√/×/⊗）、`T1~T4_{A,B,C,D} DECIMAL(5,1)`（4组温度）、`T1~T4_JUDGE NVARCHAR(2)`（温度判定，手输）、`SCRAP_TEXT NVARCHAR(200)`
- H 行：`OPERATOR/LEADER VARCHAR(50)`
- 审计：`RECORD_USER_ID/RECORD_TIME/ROW_VERSION(timestamp,不映射)`
- **判定 5 列必须 NVARCHAR**：⊗(U+2297) 不在 GBK 字符集（详见 §五踩坑1）；已按旧版 VARCHAR 建表的跑建表文件末尾【已建表补丁】ALTER 段

### 取数链（SelectPlanData@CppCuringDaily3Data，线上实证 2026-09-18 早班 172 行/总计 7770）
```sql
FROM CPP_CURING_PLAN p
INNER JOIN CPP_CURING_PLAN_DETAIL d ON d.PLAN_ID = p.PLAN_ID  -- varchar 直连（台账+线上双确认）
LEFT JOIN SBM_MATERIAL m ON m.MATERIAL_CODE = d.MATERIAL_CODE AND m.MAJOR_TYPE_ID = '03'  -- 规格名
LEFT JOIN SBM_BOM_MASTER bm ON d.BOM_ID = bm.BOM_ID           -- 仕样时间走 BOM 参数（见 §三）
LEFT JOIN SBM_BOM_PARAM bp ON bm.BOM_CODE = bp.BOM_CODE AND bm.BOM_VERSION = bp.BOM_VERSION
     AND bm.TYRE_MATERIAL_CODE = bp.TYRE_MATERIAL_CODE
     AND bp.ParamCode = 'CURE_TIME' AND bp.DeleteFlag = 0     -- 该表列名驼峰式
WHERE p.PLAN_DATE = @PLAN_DATE        -- varchar(10) 等值，传 yyyy-MM-dd 字符串勿转 datetime
  AND p.SHIFT_CODE = @SHIFT_CODE      -- '01'早/'03'夜
  AND d.DELETE_FLAG = 0 AND d.PLAN_AMOUNT > 0
GROUP BY 机台,侧,规格  → 外层 STRING_AGG(规格,N'、') + MAX(仕样时间) + SUM(PLAN_QTY) + SUM(SUM()) OVER(PARTITION 机台) AS 合计
```

## 三、口径规则

- **仕样时间 = SBM_BOM_PARAM.CURE_TIME**（存储单位分钟），**显示单位秒**（`CAST(ParamValue AS float)*60`，与 CuringProductionQuery 的 Stdtime 同式）；多规格机台取总秒最长者（纸表备注2：以时间长的规格为准）。勿走 CPP_SULF_SPEC_BOOK（规格书 SF_TIME_MIN 路线已被用户否定）。
- 硫化条数 = `SUM(PLAN_AMOUNT)` 计划口径（非 REAL_AMOUNT）；合计 = 整机 L+R；总计页面累加不入 SQL。
- 判定符号：**√(U+221A)/×(U+00D7)/⊗(U+2297)**——纸表印"U"但现场实际画圈叉⊗，页面与备注统一 ⊗；DB 已存旧值"U"回填时归一化显示为⊗。
- 交互口径（用户拍板）：**仅硫化时间点检的判定是 √/×/⊗ 点选**；4 组温度确认的判定是**手输文本框**。
- 温度校验：<160℃ 前端红字提示不阻断（仕样标准 160℃以上印在表头）。
- 备注区布局：左右列统一 17/13 列分界；示意图格 rowspan=4 竖跨备注 1~4 行（防撑高单行）。

## 四、实现要点（页面/保存/权限）

- **30 列纸表结构**：colgroup 30 个 col（3.8/5.8/2.1/4.7/4.7/2.95×21/3.4/4.7/4.7/4.3，总和≈100%）；机台/规格/合计 rowspan=2、报废 colspan=2 每行独立、**总计行仅右侧 4 格带框**（左 26 列 cdr-nb 无框）；行数随计划动态（每机台固定 L+R 两行，缺侧留空行保合并结构）。
- **保存**：`SaveSingle(inputId, valText)` DirectMethod——`txt_op/txt_ld`→H 行签字；`txt_{机台}_{侧}_{key}`→D 行白名单 23 项映射列名（两次 LastIndexOf('_') 解析，机台含下划线安全+长度≤30 无空格校验）。语句 `UpsertDField/UpsertHSign`：`$ColumnName$` 只取白名单值（注入面闭环，reviewer 对抗构造验证过）；IF EXISTS/UPDATE/ELSE/INSERT + `CASE WHEN 空串 THEN NULL`（实体 isNotNull 无法写 NULL 的家族解法）；调用 `mgr.InsertByStatement`（一检先例）。
- **权限探针**：隐藏 btnSave 探针（ActionId 1/2→btnSearch/btnSave），未授权 `_canEdit=false` 短路全部保存通道；勿写死 ACTION_ID。
- **查询反馈**：Search() 前 `Ext.net.Mask.show({msg})`，LoadReportCore 注入脚本末尾 `Ext.net.Mask.hide()`（幂等），failure 回调兜底 hide+提示。
- 实体四件套 CppCuringDaily3Data（Entity/Data/Business/Mapper 四项目 6 文件 + 双 xml 同名）；csproj：.cs 用 Compile、xml 用 EmbeddedResource；aspx 不注册（Website 项目动态编译）。

## 五、踩坑与根因（跨页可复用）

1. **⊗ 不在 GBK 字符集 → varchar 存储转换失败**。症状极具迷惑性：判定 √、×（GBK 各 2 字节恰好存进 varchar(2)）保存成功、**⊗ 必失败**——"只有最后一次保存失败"。解法：判定列 NVARCHAR；通用规则→ [[sql-server-table-design-principles]] 新增节。
2. **Ext.NET DirectMethod 的 `{showMask:true}` config 不生效**（v4 实测）→ 显式 `Ext.net.Mask.show()/hide()` 手法。
3. **Ext.NET 按钮原生 role 定位 click 超时**（登录页/工具栏均遇）→ `evaluate` 里 `document.getElementById('btnX').click()` 或 `App.direct.X()` 直调；textbox 也可能"no click point"（页面被遮罩/会话失效 302）。
4. **IISExpress 多实例 http.sys 路由错乱**：两个实例注册同端口，请求路由给后注册者——表现为"日志断流、会话丢失、保存失败的假象"。判别：日志行数不增长 + `netstat -ano` 端口 LISTENING PID=4（http.sys）。解法：`taskkill //F //IM iisexpress.exe` 清光重起唯一实例。Bin 换 dll 掉登录态属预期。
5. **"切条件不刷新"假象**：两班计划数据碰巧完全相同（172 行/7770）→ 页面无视觉变化被误判不刷新。排障纪律：先查站点日志 SQL 参数（@param1=01→03 已变）再怀疑前端。
6. **模板代码 schema 陷阱**：Curing 项目 `CppCuringPlanDetail.xml` 存在旧模板语句（`A.OBJID=B.PLAN_ID`、`SHIFT_ID/EQUIP_ID`、`MATERIAL_ID`）与台账 DDL 及线上在用语句（`p.PLAN_ID=d.PLAN_ID`、`SHIFT_CODE/EQUIP_CODE`、`MATERIAL_CODE`）**冲突**——写计划相关 SQL 以线上在用语句（GetEquipStateVisual、PROC_CPP_SELECT_DAY_PLAN）+台账为准，勿抄模板注释代码。
7. **Git Bash grep（ugrep）对部分文件静默零命中**（aspx.cs UTF-16、IISExpress 日志"binary"判定）→ 一律 `command grep -a`；日志 grep 不到先用 file/首字节判断编码。
8. **验证方法**（防假阳性纪律）：MSBuild 必须 `//t:Rebuild`（Build 增量假阳性）+ `grep -ac 新类型 产物dll`；aspx.cs 用 Framework csc 单文件自检（CS0103 属预期）；浏览器实测走 IISExpress 起站（`iisexpress /path:<WebSite> /port:12909 /clr:v4.0`）+ admin/manager@CHQY + evaluate 驱动 Ext.NET 控件 + DOM getBoundingClientRect 量几何（截图给视觉模型会误读，DOM 数字优先）。

## 六、部署清单（上线完整件目，按序）

1. 用户连库执行 `Batch/sql/CppCuringDaily3Data_建表.sql`（新库直接建；已按旧版建表跑末尾【已建表补丁】ALTER 段改判定列 NVARCHAR——**不执行则 ⊗ 判定保存必失败**）
2. VS 生成解决方案刷新 WebSite/Bin（Entity/Data/Business/Mapper 四 dll；命令行编译需手拷，Bin 刷新后登录态失效属预期）
3. 系统管理挂菜单 + 授权 btnSearch/btnSave 两 Action（权限探针，授权即生效）
4. 无定时任务、无存储过程（实时取数路线）

## 七、遗留项（待用户拍板/执行）

- 建表 SQL + ALTER 补丁待用户连库执行；执行后首测三条保存路径（判定⊗/温度小数/清空回NULL）
- 取值 SQL 草稿待确认①~⑩仍开放（`Curing/页面设计/SQ-PK01样式-3-取值SQL草稿.sql`，集中在 SelectPlanData 一条语句）
- 挂菜单+授权待用户操作
- 家族级改进点：无权限时后注入的输入框未置灰（readOnly 只在 initPerm 打一次，修理日报同款行为）
- OBJID BIGINT vs 实体 int?（家族先例同款，量级无虞）
- 设计稿 HTML（`Curing/页面设计/SQ-PK01样式-3-硫化工序作业日报.html`）保留纸表原文"恢复后U"，页面口径为 ⊗——两件制品口径有意不一致

## 八、关联文档

- 家族基准：[[curing-daily-report-implementation]]（样式-1 长表快照路线）、[[repair-daily-report-implementation]]（实时取数+权限探针路线本页沿用）、[[first-inspection-daily-report-implementation]]（H/D 行模式与 InsertByStatement Upsert 先例）
- 建表 Unicode 陷阱：[[sql-server-table-design-principles]]
- 表结构：私有库表结构台账（计划两表/SBM_BOM 参数；CPP_CURING_DAILY3_DATA 建表后再实证入台账）
- 班次编码与转换：[[shift-date-to-timerange-impl]]

---

## 九、追加踩坑（2026-09-19 收尾发现）：RECORD_USER_ID 恒为 0 —— Session["User"] 全项目无人写入

**根因**：登录成功写的是框架基类容器 `this.Data.User`（Login.aspx.cs:131 `this.Data.User.UserId = currUser.ObjId`），**全项目没有任何代码写 `Session["User"]`**——修理日报(:201)/样式-1(:226)/样式-3(初版) 三页抄同一段 `(SsbUser)Session["User"]).ObjId` 模板，Session 恒 null → try-catch 兜底 → **RECORD_USER_ID 线上一直是 '0'**（家族级隐性 bug，样式-3 用户查数据才暴露）。

**正解**：框架基类属性链 `this.Data.User.UserBarcode`（工号 string，闭源 Wongoing.Web.UI.dll 提供、源码 grep 不到）；未登录用 try-catch 兜底 '0'。已在样式-3 修正并实测（日志 @param5=admin）。**兄弟页 RepairDailyReport/CuringDailyReport 同款待用户拍板修**（各一行）。

**教训**：抄先例代码不能只对"写法一致"，要对**运行时事实**——reviewer 核了"与先例逐字同"放行，但先例本身就是坏的；凡是 Session 取值类代码，先 grep 全树确认该键确有写入点。

---


**2026-09-19 补记**：兄弟两页已同款修正（RepairDailyReport / CuringDailyReport 各一行改 `this.Data.User.UserBarcode`，csc 自检 0 错误）——三页取值已统一，上文"待用户拍板修"作废。