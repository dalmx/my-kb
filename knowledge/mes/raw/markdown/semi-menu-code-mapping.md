---
category: 业务-通用
module: Semi
status: active
tags:
- 部材
- 菜单
- 代码映射
- McUI
- 蓝图
- Semi
- 页面清单
- 报表中心
- 回收胶
title: 部材工序菜单与代码映射
updated: '2026-09-07'
---

# 部材工序菜单与代码映射

> 2026-08-23 实测自运行系统（localhost:52450，admin 账号全菜单）。列出部材工序 8 个分类 42 个页面与代码文件（aspx / McUI XML）的对应关系，以及两个外部模块页面。做新报表/改页面/查功能时先查此表。

## 一、映射总表

页面根目录：`P.Semi/Wongoing.Semi.WebSite`；McUI XML 在 `Plugins/Semi/McUI/@McUI/`（URL 规则 `/MCUI/CRUD|REPORT/XXX.ASPX` → `Crud/Report + XXX.xml`）。

| 分类 | 菜单页面 | 代码 |
|------|---------|------|
| 基础管理 | 库区维护 | McUI: CrudSMArea.xml |
| 基础管理 | 库位维护 | Storage/SMLocation.aspx |
| 计划管理 | 部材计划 | ProductPlan/SemiPlan.aspx |
| 计划管理 | 计划执行 | ProductPlan/SemiPlanExecute.aspx |
| 计划管理 | 生产监控 | ProductPlan/SemiProduceMonitor.aspx（6个Tab） |
| 计划管理 | 部材日计划统计 | McUI: ReportHppSemiPlanTotal.xml |
| 计划管理 | 部材计划日志 | ProductPlan/SemiPlanLog.aspx |
| 计划管理 | 部材支援计划 | ProductPlan/MaterOutPlan.aspx |
| 生产管理 | 部材日志管理 | McUI: ReportHppSemiOperateLog.xml |
| 生产管理 | 部材生产信息 | McUI: ReportHppProduction.xml |
| 生产管理 | 周期产量统计 | Produce/SemiProduceMaterial.aspx |
| 生产管理 | 返回品产出信息 | Report/ReturnProductOutput.aspx |
| 生产管理 | 部材报废记录 | McUI: ReportHppSemiScrapLog.xml |
| 生产管理 | 部材设备报警记录 | Report/EquipAlarmRecord.aspx |
| 工艺管理 | 部材工艺曲线 | Technology/SemiCurveReport.aspx |
| 工艺管理 | 物料设备标准维护 | Technology/SemiEquipByMaterParam.aspx |
| 工艺管理 | 计划CPK分析 | Report/PlanCpkAnalysis.aspx(+Detail) |
| 库存管理 | 部材原材料实时库存 | Material/SemisRawMaterial.aspx |
| 库存管理 | 部材实时库存 | Report/MaterialRealTimeStock.aspx |
| 库存管理 | 半制品盘点单 | Storage/SemiStockCountTask.aspx |
| 库存管理 | 库位查询 | Storage/SemiKwQuery.aspx |
| 质量管理 | 超期部材报警 | Material/SemiMaterialWarning.aspx |
| 质量管理 | 检验项目维护 | McUI: CrudHppCheckItem.xml |
| 质量管理 | 部材质检管理 | Quality/QuaCtrl.aspx |
| 报表中心 | 个人产量统计 | Produce/PersonalProduceAnalyse.aspx |
| 报表中心 | 部材产量报表 | Report/SemiProduceAnalyseReport.aspx（7种视图） |
| 报表中心 | 部材产出物料统计 | Report/SemisProductionMaterial.aspx |
| 报表中心 | 部材产出机台物料统计 | Report/SemisProductionEquipMaterial.aspx |
| 报表中心 | 部材产出按班组分物料统计 | Report/SemisProductionClass.aspx |
| 报表中心 | 部材员工产量统计 | McUI: ReportHppSemiProductionWithWorker.xml |
| 报表中心 | 部材员工产量按物料统计 | McUI: ReportHppSemiProductionWithWorkerMaterial.xml |
| 报表中心 | 部材班组产量统计 | McUI: ReportHppSemiProductionWithClass.xml |
| 报表中心 | 消耗产出统计报表 | **Batch 项目** Plugins/Batch/Report/ConsumptionOutput.aspx |
| 报表中心 | BIC检测记录 | Report/BicMeasuredRecord.aspx |
| 回收胶管理 | 回收胶产出信息 | McUI: ReportHppRubberReturn.xml |
| 回收胶管理 | 回收胶产出统计 | Produce/SemiReturnRubber.aspx |
| 回收胶管理 | 返回胶出入库统计 | Storage/SemiReturnRubberInOutStat.aspx |
| 回收胶管理 | 回收胶物流记录 | Report/SemiReturnRubberLogistics.aspx |
| 回收胶管理 | 回收胶率 | Report/SemiReturnRubberRatio.aspx |
| 回收胶管理 | 回收胶消耗统计 | Report/SemiRubberConsumption.aspx |
| 回收胶管理 | 混合回收胶消耗统计 | **Mix 项目** Plugins/Mix/ReturnRubber/ReturnRubberConsumeStat.aspx |
| 回收胶管理 | 回收胶实时库存 | Report/SemiReturnRubberRealTimeStock.aspx |

## 二、注意事项

- 消耗产出统计报表、混合回收胶消耗统计两个页面**不在 Semi 仓库**，本地 Semi 站点直接访问会 404（跨项目部署）。
- 菜单由 `SSP_PAGE_MENU` 表配置（SysMenu/SetPageMenu.aspx 维护），代码里有但菜单未开放的页面：SemiProduceAbnormalManager（异常品）、RfidBindingSuccessRate（RFID绑定率）、SemiProduceTimeStatics（生产用时）、ReportHppLoadArtAutoUnbindLog、ReportHppMaterialNeed（物料需求）、ReqortEquipSpareUsage（备品备件）等。
- 蓝图（部件生产模块-蓝图.doc）第 6 章"生产模块平台详细设计业务功能"已按本表重建（2026-08-23，完善版见项目 `蓝图修改/` 目录），8 分组 42 页 + 其他平台功能 13 项，含实拍参考页面截图。

## 三、关联文档

- `mcui-crud-page-extension-guide.md` —— McUI 配置驱动 CRUD 框架（三件套+JS扩展）
- `semi-business-overview.md` —— 部材业务总览
- `consumption-output-report.md` —— 消耗产出统计报表实现细节

---

## 四、2026-09-07 新增待挂菜单页面

| 分类建议 | 菜单页面 | 代码 |
|------|---------|------|
| 基础管理 | 帘布大卷棉线颜色维护 | BasicInfo/CurdCottonColor.aspx（+ .cs） |

- **用途**：维护物料小类为 帘布大卷(01101)/带束层大卷(01111) 的物料棉线颜色（红/黄/白），值存 `SBM_MATERIAL.REMARK`，选项来自字典 `DIC_SEMI_COTTON_COLOR`（初始化脚本 `sql/DIC_SEMI_COTTON_COLOR.sql`，需先手动执行）。
- **权限点**：查询 btn_search / 修改 Edit / 导出 btnExport。
- 完整套路见 `semi-sbm-material-field-maintain-page.md`。