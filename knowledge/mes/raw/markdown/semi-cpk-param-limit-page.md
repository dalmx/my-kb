---
category: 业务-通用
module: Semi
status: active
tags:
- 部材
- CPK
- 限值维护
- 物料参数
- SearchBox
- 桥表
- 物料CPK参数限值
- HPP_SEMI_CPK_PARAM_LIMIT
- 机台生产物料表
title: 物料CPK参数限值维护页（SemiCpkParamLimit）实现套路
updated: '2026-09-11'
---

# 物料CPK参数限值维护页（SemiCpkParamLimit）实现套路

> 为 PlanCpkAnalysisDetail 使用的 CPK 限值建独立维护页：新建 HPP_SEMI_CPK_PARAM_LIMIT 表按"物料号+参数"存五项限值（规格上/下限+均值UCL/LCL+极差UCL），页面从物料出发经桥表推机台再取机台下参数，明细页选参数后自动带出。仿 Molding SpliceParamLimit 模式，2026-09-08 交付（同日按用户要求删除机台/配置状态查询条件，查询区=物料/参数/物料关键字三项）。

## 一、功能与数据模型

维护页：`Plugins/Semi/Technology/SemiCpkParamLimit.aspx`（标题"物料CPK参数限值维护"），PageAction：查询(1,btnQuery)/新增(2,btnAdd)/编辑(3,Edit)/删除(4,Delete)/导出(5,btnExport)。

新表 `HPP_SEMI_CPK_PARAM_LIMIT`（建表脚本 `Semi/SQL/TABLE_HPP_SEMI_CPK_PARAM_LIMIT.sql`，用户手动执行）：

| 列 | 说明 |
|----|------|
| MATERIAL_CODE + PARAM_CODE | 唯一过滤索引（WHERE DELETE_FLAG=0）；物料号=HPP_PLAN_DETAIL.MATERIAL_CODE，参数=HPP_SEMI_PROCESS_MOINTOR.PARAM_CODE（与机台绑定表/InfluxDB 列名同域） |
| USL / LSL | 规格上/下限，必填、上限>下限 |
| UCL / LCL / RANGE_UCL | 均值控制上/下限、极差上限，选填 |
| 其余 | REMARK/RECORD_USER_ID(WORK_BARCODE)/RECORD_TIME/DELETE_FLAG(0,1)/FACTORY_ID/ROW_VERSION |

**与旧链路完全解耦**：SBE_EQUIP_PARAM_STANDARD_LIMIT（winCPK 弹窗）和存储过程 PROC_SEMI_SELECT_CPK_PARAM_LIMIT 一行未动，两套并行。保存用"先删后插"（Delete+Insert），天然支持选填限值清空；唯一性预检 GetEntityList(物料+参数+DeleteFlag=0)。

## 二、核心链路：物料→机台→参数（业务口径）

```text
物料 SBM_MATERIAL.MINOR_TYPE_ID
→ 桥表 HPP_PARAM_EQUIP_MATERTYPE（MATERIAL_MINOR_TYPE_ID → EQUIP_MINOR_TYPE_CODE，DELETE_FLAG=0）
→ 机台 SBE_EQUIP（MINOR_TYPE_ID 匹配机台细类，WORK_SHOP='02'，DELETE_FLAG=0）
→ 机台绑定参数 HPP_SEMI_PROCESS_MOINTOR_EQUIP（EQUIP_CODE → PARAM_CODE，仅 DELETE_FLAG=0）
→ 参数定义 HPP_SEMI_PROCESS_MOINTOR（仅 DELETE_FLAG=0）
```

三个业务要点（用户拍板，勿改）：
1. **物料细类和机台细类两套编码没有互指外键**，唯一桥梁是 HPP_PARAM_EQUIP_MATERTYPE（"机台生产物料表"）；物料侧另一变体 HPP_PARAM_EQUIP_CODE_MATERTYPE 按 EQUIP_CODE 直连。
2. **HPP_SEMI_PROCESS_MOINTOR.MINOR_TYPE_CODE 实际无值**——参数侧不要用细类过滤（CHECK_TYPE='01'、IS_USE=0 也被用户否掉），参数定义/绑定表只过滤 DELETE_FLAG=0。
3. **限值是物料+参数维度**：同参数绑多台机台共享一份限值（表无机台列）；机台只用于导航（确定该物料能配哪些参数），**页面不展示机台条件**（初版有"机台/配置状态"两个查询条件，用户要求删除）。

列表查询两种模式：①选了物料=可配参数全量行（链路结果 LEFT JOIN 新表，未配置行空白可补配，支持参数下拉过滤）；②未选物料=新表已有记录（物料编码/名称关键字模糊）。桥表无数据时选物料后参数下拉为空并提示。

## 三、物料 Search 形式选择：McUI SearchBox 套路

全站统一的搜索选择弹窗，不是控件而是"通用宿主页+三件套配置"约定，手写 Ext.NET 页面可直接复用（先例 MaterialRealTimeStock.aspx / SemiPlan.aspx）：

```javascript
// 1) 只读 TextField + Clear/Search 双 Trigger；2) 全局窗口+iframe；3) 固定名回调接选中
var materialSearchTarget = 'Q'; // 自己加：标记当前回填目标（Q=查询区 E=编辑窗）
Ext.create("Ext.window.Window", {
    id: "McUI_SearchBox_SearchBoxSemiSbmMaterial_Window", height: 460, hidden: true, width: 600,
    html: "<iframe src='/McUI/SearchBox/SearchBoxSemiSbmMaterial.aspx?majorlst=01&closable=1' width=100% style='height:100%' scrolling=no frameborder=0></iframe>",
    closable: true, title: "请选择物料", modal: true
})
var McUI_SearchBox_SearchBoxSemiSbmMaterial_Request = function (record) {
    // record.data.MATERIAL_CODE 写 Hidden、MATERIAL_NAME 回显只读框，回调里直接做联动刷新
}
```

要点：回调函数名必须一字不差（`McUI_SearchBox_<配置名>_Request`）；**iframe URL 要带 `majorlst=01`（与 SemiPlan 一致）**——SearchBoxSemiSbmMaterial.js 的 viewportAfterRender 对长度为 2 的 majorlst 自动"大类预设 01 半制品+锁定只读"，细类联动只列该大类，不带参数则是全量物料；弹窗内是查询面板（名称/ERP/PDM 模糊+大类/细类）+点【查询信息】+行首【确认】/双击，**不是输入联想**（全站无 QueryMode=Remote 先例）。

## 四、四层文件与编译部署

按 Molding BpmSpliceParamLimit 同款克隆四层：`Wongoing.Semi.Entity/BasicEntity/HppSemiCpkParamLimit.cs`、`Wongoing.Semi.Mapper/BasicMapper|BusinessMapper/HppSemiCpkParamLimit.xml`、Business Interface+Implements Manager、Data Interface+Implements Service；csproj 各加条目（Mapper 两个 xml 是 EmbeddedResource）。**SqlMap.config/SqlMapSemi.config 无 sqlMap 清单**——框架从 Mapper 程序集内嵌资源自动发现，无需注册。BusinessMapper 共 3 个语句：SelectParamListByMaterial（联动）、SelectByMaterial（模式①）、SelectAll（模式②）。

编译：`MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*" /d/VSIDE/MSBuild/Current/Bin/MSBuild.exe Wongoing.MESWeb.Semi.2013.sln /p:Configuration=Debug /v:minimal /m /nologo`。sln 全量编译会把 Entity/Business/Data/Mapper 的 DLL 自动刷进 Wongoing.Semi.WebSite/Bin 且预编译 WebSite（校验 aspx/cs 语法）；**但单独编 Mapper.csproj 只输出到自身 bin/Debug，要手动 cp 到 WebSite/Bin**。Mapper XML 要带 UTF-8 BOM（对齐兄弟文件，PowerShell 默认编码读无 BOM 文件会假报 XML 注释错）。

## 五、明细页自动带出（算法零改动）

PlanCpkAnalysisDetail 已有 HdMaterialCode（主页 OpenCPKDetail URL 早已传 MaterialCode）。只加两处：
1. `.aspx` head 加 `onCbbParamSelect`：cbbParam Select 事件 → `App.direct.GetParamLimit(HdMaterialCode, 选中行 record.get('ParamCode'))` → 预填 txtSpecUSL/txtSpecLSL/txtUSL/txtLSL/txtRUCL 五框（无记录则清空五框）。
2. `.cs` 加 `[DirectMethod] GetParamLimit(materialCode, paramCode)`：HppSemiCpkParamLimitManager.GetEntityList(物料+参数+DeleteFlag=0) 返回 `{found,usl,lsl,ucl,lcl,rangeUcl}`。

带出值可手改/清空；清空后规格限回落存储过程取数、控制限按数据计算——原有 AnalyzeCPK/导出/评级一行未动。

## 六、踩坑与要点

- **JS 引用的每个 App.<ID> 必须在页面标记里声明**——初版漏声明 hdMaterialCodeQ（存物料编码的 Hidden），点查询即报 `Cannot read properties of undefined (reading 'getValue')`；交付前用"JS 引用 App.* 清单 vs 页面 ID 清单求差集"自查。
- 参数下拉联动是服务端重绑（DirectMethod 里 store.DataBind + combo.ClearValue），禁用态切换放前端 JS success 回调里 `setDisabled`（服务端 SetDisabled protected 不可访问）。
- 查询条件联动三处同步：前端传参、后台 where 字典+Session 缓存（导出复用）、BusinessMapper 动态条件——漏一处就"条件不生效"；**删查询条件时三处+DirectMethod 一起删**，`<isEqual>` 这类条件留在 mapper 而调用方不再传参会直接抛错（属性缺失），宁删勿留。
- SearchBox 选完物料的回调里同步清空参数下拉并置灰，防止残留上一个物料的参数选项。

---

---

## 七、2026-09-08 三次变更（交付当天）

1. **表格不再显示"物料编码"列**（MATERIAL_CODE 仍是 ModelField 隐藏键，编辑保存/导出导入都用它）；物料名称列加宽 200。
2. **新增 Excel 导入**（与成型 SpliceParamLimit 完全同款）：导出 Excel 列头即导入模板（必填列 物料编码*/参数编码*/规格上限*/规格下限*，导出列头已同步加星号）；按 物料编码+参数编码 匹配，存在则先删后插更新、不存在新增；预加载判重→每批500批量删（Mapper 语句 DeleteLimitByObjIds，无@后缀=本实体 Manager 内部解析）→BatchInsert 单事务，失败逐行重试按 Excel 行号报错（DataTable 索引+2）；NPOI 读表用 IRow 接口防 xlsx 强转 HSSFRow 崩溃。权限项加 导入(6,btnImport)，导入窗=FileUploadField+ValidityChange 联动确定按钮+DirectEvents(Timeout 180000/EventMask/Success 三件套：关窗+reset+刷新)。

---

---

## 八、导入导出改用物料名称定位（2026-09-08 用户拍板）

- **导出**不再含"物料编码"列：列头为 物料名称*、参数编码*、参数名称、规格上限*、规格下限*、均值UCL、均值LCL、极差UCL、备注、记录人、记录时间（带*为导入必填）。
- **导入**按"物料名称+参数编码"匹配：预加载 SBM_MATERIAL（DeleteFlag=0）建 名称→编码 字典（忽略大小写、Trim）；名称不存在→按行报错"物料名称[xxx]不存在"；**同名多码**→报错"对应多个物料编码，请改用页面维护"（不允许歧义导入）；解析出编码后仍按 MATERIAL_CODE+PARAM_CODE 先删后插 upsert，入库数据不含名称。
- SbmMaterial（Semi 侧实体）字段：MaterialName/MaterialCode 为 string、DeleteFlag 为 **long?**（=0 赋值兼容）。

---

---

## 九、页面更名 + 下拉交集误报排查（2026-09-08）

- **页面更名**：维护页标题 物料CPK参数限值维护 → **部材SPC参数维护**（winLimit→部材SPC参数编辑、winImport→导入部材SPC参数、导出文件名→部材SPC参数；类名/文件名/表名不变）。明细页提示语同步。
- **"有维护记录却提示未维护"排查**：明细页下拉=机台绑定参数(PROC_SBE_SELECT_PARAM_BYEQUIP) ∩ 该物料限值表记录（按 PARAM_CODE），**交集为空即提示**。库里有记录仍提示 → 多半是维护的参数编码与机台绑定编码对不上。加固：比对 ParamCode 和 ObjId 两列（过程的 ObjId 即 InfluxDB 列名、与参数编码同域）；提示拆两种——机台未绑定任何参数 / 维护参数与机台绑定参数无交集。诊断 SQL（用户执行）：`EXEC PROC_SBE_SELECT_PARAM_BYEQUIP '机台号'` 看返回编码；对比 `SELECT PARAM_CODE FROM HPP_SEMI_PROCESS_MOINTOR_EQUIP WHERE EQUIP_CODE='机台号' AND DELETE_FLAG=0` 与 `SELECT PARAM_CODE FROM HPP_SEMI_CPK_PARAM_LIMIT WHERE MATERIAL_CODE='物料号' AND DELETE_FLAG=0`。

---

---

## 十、补齐 CL 两列（2026-09-11 用户问"CL为什么没加"后对齐成型七字段）

- **表**：HPP_SEMI_CPK_PARAM_LIMIT 增加 MEAN_CL（均值CL）/RANGE_CL（极差CL），脚本 `SQL/ALTER_HPP_SEMI_CPK_PARAM_LIMIT_ADD_CL.sql`（用户手动执行，先跑再刷新）；建表脚本同步补列。
- **全链路**：实体+BasicMapper（resultMap/parameterMap/where/insert/update 六处，本表唯一写入方是维护页故直接进通用片段无刷空风险）+BusinessMapper 两个列表 SELECT + 维护页（表格两列/编辑窗 numMeanCL、numRangeCL/保存/导出导入列）+ 明细页（txtMeanCL/txtRangeCL 两输入框，自动带出，AnalyzeCPK 签名 +2 参数）。
- **覆盖语义（与成型一致）**：均值CL 有值→覆盖 xbarSData.xbarSTotalAve（图线+图顶标注）；极差CL 有值→覆盖 xbarRData.rangeAve；**CL 仅覆盖图线显示，不参与 CPK 计算**；均值 UCL/LCL 仍要求成对覆盖，极差仅 UCL 可覆盖、LCL 恒 0。
- 明细页新增框挂在"极差UCL"容器旁新 Container（ColumnWidth .17），ExportCPK 导出路径未加 CL（导出的是数据/CPK表，CL 不影响）。

---

---

## 十一、明细页联动与布局（2026-09-11 补充）

- 明细页（PlanCpkAnalysisDetail）查询区已重排：参数下拉提前到主条件区（.36 宽），七个限值框（含均值CL/极差CL）收进可折叠 FieldSet"限值设置（选参数后自动带出，可手改）"默认收起——详见 [[plan-cpk-analysis-page-analysis]] 第十节（含图表自适应重绘四触发面与 Ext.NET Resize 监听 `this.on('resize', fn)` 错写坑）。
- CL 覆盖实现要点：明细页 AnalyzeCPK 签名为 7 个可空参数（UCL/LCL/RUCL/SpecUSL/SpecLSL/**MeanCL/RangeCL**）；MeanCL 覆盖 xbarSData.xbarSTotalAve（图线+图顶标注），RangeCL 覆盖 xbarRData.rangeAve，均不参与 CPK 计算；均值 UCL/LCL 仍成对覆盖。注意 **ExportCPK（导出CPK按钮 DirectEvent 的 ExtraParams）没有 CL 参数**——导出走数据/CPK 表，CL 不影响，属预期。
- 上位机复刻交付物：`Semi/docs/均值控制图与极差控制图复刻逻辑.md` + `Semi/docs/复刻配套代码/`（全部相关源码副本，含 Entity 与 ALTER 脚本）。