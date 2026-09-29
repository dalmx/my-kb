---
category: 业务-通用
module: Curing
status: active
tags:
- 加硫曲线圆饼图
- CuringCurvePieChart
- 机台
- 沟排
- 极坐标
- ECharts
- polar
- date_bin
- InfluxDB
- 降采样
- Curing
- 曲线饼图
- 圆饼图
- 24小时
- 上位机圆图
- 时间指针
- 双刻度
- 半径角度顺序
- 几何缩放
- 标准区间带
title: 加硫曲线圆饼图页面（CuringCurvePieChart）
updated: '2026-09-23'
---

# 加硫曲线圆饼图页面（CuringCurvePieChart）

> Curing 子系统"加硫曲线圆饼图"页面（Plugins/Curing/Technology/CuringCurvePieChart.aspx(.cs)）：按沟排/机台+日期查询，画法照硫化机上位机实时圆图（双刻度铺满整圆+24 整点刻度+红色当前时间指针+压力标准区间绿带），支持滚轮几何放大与全屏放大。2026-09-23 定稿并收敛（本版为终态权威版，取代此前 18 节过程记录）。ECharts 极坐标通用坑见 [[chart-table-report-template]] 第八节；InfluxDB 聚合降采样见 [[curing-check-dev-notes]] 第十一节。

## 一、功能概述（终态）

- **双模式查询**：选了机台→单机台自适应大图（宽 min(区域宽-28,1000)×0.72，下限 560）；机台留空、只选沟排→整沟机台紧凑卡片网格（340px 卡/图 336×252，卡头只留机台号+机台名+【放大】），滚动查看全部；两者都空提示"请选择机台或沟排"。
- **圆图（照上位机）**：浅蓝圆盘底 + 双刻度铺满整圆（淡蓝环=压力 0~4MPa 固定，环 0.8/1.6/2.4/3.2；淡橙环=温度 0~TMAX 自适应，环 50 间隔；合模力 0~1900kN 第三刻度无环）+ 圆周外沿 24 个整点刻度（0~23 纯数字，0/6/12/18 加深锚点，顶部 0 起、每 15° 一个）+ 绿色压力标准区间环带（2.0~2.4 与 1.27~1.47 MPa，同参考页日曲线标色、淡绿同点检页）+ 红色当前时间指针（仅查当天）。
- **角度=时间**：一天=自然日 0:00~23:59:59（与上位机"当天 0 时起"一致），圆周一圈 24 小时均分（每小时 15°），数据点真实分钟精度。
- **通道**：默认**全部 16 条**（与 CuringTechnalogyReport 同通道同色序），顶部 chips 图例点击对全部图显隐。
- **交互**：圆图上滚轮=以鼠标为锚**几何放大**（最大 6 倍，矢量重绘），按住拖动平移，双击复位；卡片【放大】→ 该机全屏弹层（点空白/ESC 关闭，弹层内同样可缩放）；悬停曲线点显示通道名+真实值+时刻。
- 权限：查询 btnSearch 一个动作。

## 二、表事实与数据链路

- 机台清单：`SbeEquipManager.GetEntityList(new SbeEquip{DeleteFlag=0, MajorTypeId="06", EquipCode/EquipUuid=...}, "EQUIP_CODE")`——**GetEntityList 返回 IList&lt;T&gt; 不是 List&lt;T&gt;**（写 List 报 CS0266）；机台下拉初始全量（实测 252 台），选沟排后 `BindEquipByGroove(equipUuid)` DirectMethod 重绑（空=全量，照抄 CuringTechnalogyReport）；沟排下拉用既有 `SelectDistinctEquipUuid@SbeEquip`（12 沟，沟 1 实测 21 台）。
- 曲线数据：InfluxDB `Sulf` 库，measurement=机台号，16 通道列同 CuringCheck（INNER_PRESS/DINGXING_PRESS/REBAN_TEMP/MOTAO_TEMP/INNER_TEMP/CLOSE_POWER/PCI_PRESS 左右×）。
- **零新增 Mapper 语句、零 csproj/dll 改动**，纯 aspx/aspx.cs（WebSite 运行时编译）。
- 实测 J101 全天：720 桶（2 分钟/桶）无缺口、分钟 0~1438、数值合理（内压 0.78~2.2MPa、右热板 181℃ 等）。
- 上位机对照（源码 Curve/RealTimeCircleDiagram）：同为自然日 0 时起；画图在 Mesnac.Controls.Sulf.PolarCurve 控件（源码不在仓库）；上位机数据列 13 条含 NowStep 工步、带通道勾选列表；上位机差异项（数值面板/工步/自动刷新/直角切换/报警状态）用户 2026-09-23 确认**不搬**。

## 三、口径规则

- **一天=自然日 0:00~23:59:59**（曾用 8:00 工厂日口径，按上位机源码改为自然日）。
- **降采样=2 分钟桶**（date_bin+avg，满天 720 桶）；缺值 coalesce(avg,0)（同参考页 `||0`）；点集 double[17]（分钟数+16 通道）紧凑 JSON。
- **径向刻度**：压力 0-4 / 合模力 0-1900 固定（同参考页 yAxis），温度 **TMAX=max(100, ceil(当日全部温度通道最大值/50)×50)** 自适应（同参考页温度轴随数据，用户确认）；TMAX 跨全部机台、含默认关通道计算（开关通道刻度不跳）。
- **默认全部 16 条通道显示**（用户定稿；当初压到 6 条是因数据顺序 bug 误判"挤"）；模套≈热板同值叠线属数据形态。
- **标准区间带**：2.0~2.4 / 1.27~1.47 MPa（参考页日曲线 markArea 同区间），色淡绿 rgba(144,238,144,0.45)（同点检页口径）。

## 四、InfluxDB 查询双路径（详见 curing-check-dev-notes 第十一节）

主路径 `QuerySqlSync("Sulf", sql)` 直发 date_bin 聚合（一台一次请求，多台并行 10）；回退 QueryInfluxParallel（60 分钟分段）+ C# 端 2 分钟桶取每桶最后一行；统一转 double[17]。

## 五、前端实现要点（ECharts 4.1.0，画法照上位机）

- **一个圆 = 三个 polar 同圆心同半径叠加**（radiusAxis 0-4 / 0-1900 / 0-TMAX 各铺满整圆；ECharts4 单 polar 只能挂一个 radiusAxis，双 radiusAxis 抛 NPE 不渲染）。
- **⚠️ 数据顺序=[半径, 角度]**：通道曲线 `data=[通道值, 当分钟数]`、刻度环 `data=[恒定刻度值, k*60]`、tooltip 取 data[0]=值 data[1]=分钟——写反则分钟爆半径、通道值当角度（温度 34~200 恰落 0~50°，即"曲线聚 0~3 时"的病根）。
- **几何常量按图尺寸现算**：CX=w/2、CY=h×0.58、R=0.62×min(w,h)/2，**必须在 setOption 前赋值**（graphic 刻度/指针/标准带、CSS 圆盘底、polar center/radius 像素值全用它）；单机大图/多卡小图/放大弹层同一段代码不同 w/h；dpr≠1 时 graphic/CSS 仍是逻辑像素。
- **圆盘底用 CSS**（canvas 透明）：`radial-gradient(circle Rpx at CXpx CYpx, #f2f8fc 97%, transparent)`；graphic 画填充圆会盖住曲线（graphic 在 series 之上），ring 环带因半透明可垫底。
- **刻度环**：silent 线系列 `[[恒值, k*60] for k=0..24]` 闭合成圆（压力蓝 #c9dcf0 宽 1.2、温度橙 #f0dcc9）；环上数字 graphic 11px 布不同分角（压力 0°/45°/90°/135°、温度 [180,225,270,315,135] 循环）。
- **24 整点小时刻度 graphic 自绘**：文字=String(h)，位置 `x=CX+(R+13)·sin(h·15°)、y=CY−(R+13)·cos(h·15°)`，**textAlign:'center' + textBaseline:'middle'**（文字中心精确落点，勿手工加像素偏移）；字号 R<100 用 9px 否则 11px；0/6/12/18 fill #666 其余 #999。
- **标准区间带**：v4 极坐标 markArea 不可用 → graphic `{type:'ring', shape:{cx,cy,r:r0…}, style:{fill:'rgba(144,238,144,.45)'}}`，r=v/4×R；放在刻度数字/指针之前（垫底层）。
- **滚轮几何缩放 attachGeomZoom(chart, div, machine, isToday, w, h)**：wheel（passive:false）以鼠标为锚更新圆心/半径（`C'=P−(P−C)×(R'/R)`，限 1~6×基准）→ 临时写全局 CX/CY/R → `chart.setOption(buildMachineOption(...), true)` 整体 notMerge 重建（全部矢量跟随不糊）→ 恢复全局 + 同步 CSS 圆盘底；拖动平移（未放大时忽略）、双击复位；放大弹层同挂。
- **放大弹层 openBigAt(idx)**：`__lastPie.machines[idx]` 按卡片 data-bidx 取机台重建全屏大图（w=min(窗口宽-60,1200)）；按钮 `$(document).on('click','.pie-zoombtn')` 委托+data-bidx（弹层关闭钮同 class 无 data-bidx，handler 空值守卫）。
- **滚动容器**：Ext 面板 Content 里必须 `position:absolute;left/top/right/bottom:0;overflow:auto`（height:100% 不生效、内容被裁无滚动条）；chips 条 sticky 顶置。
- 多图统一图例：每图 legend show:false + `setOption({legend:{selected}})` 批量驱动；angleAxis splitLine 关（无辐条，上位机同款）。

## 六、踩坑清单（收敛）

1. **[半径,角度]顺序写反**：症状=曲线聚 0~3 时方向/全是放射刺/"线不是圆形"——3 点小样定位法（[[2,0],[2,720],[2,1438]] 应落 (0°,50%)(180°,50%)(359°,50%)）是唯一可靠判定法。
2. **v4 极坐标数值角度轴不认 axisLabel.interval**：自动排布出 1~2 小时间隔的一堆标签再螺旋径向避让（"23时贴着 0 时"元凶）——凡标签密度/位置有要求一律 graphic 自绘。
3. **graphic 文字默认锚点是文本框左上角**：手工 y+N 偏移会造成整圈刻度偏移不同轴——一律 textAlign:'center'+textBaseline:'middle'。
4. **"折线 shape.points 含越界坐标属正常"是误判**：那是数据顺序错误的半径爆炸值，顺序正确后顶点全在圆内（此误判曾在模板文档记录，已勘误）。
5. **v4 convertToPixel 不支持 polar**；zr displayList（getZr().storage.getDisplayList）才是渲染真相入口。
6. **重构函数时同名 var 残留**（var 提升覆盖按索引取值）——重构后搜一遍同名声明。
7. **自动视觉分析多次幻觉**（报不存在的刻度、误称空圆/圆心聚团）——渲染验证优先 canvas getImageData 像素取证（角度/半径分桶、外圆横竖直径量等、圆外像素计数）。
8. **"局部放大"先确认时间窗还是几何**（本页时间窗版整体废弃，几何版才是用户要的）；**"同值叠线"**（模套≈热板）只画一条曾是默认，终态全显由用户拍板。
9. Ext 面板滚动容器坑（见五）；GetEntityList 返回 IList（见二）。

## 七、验证方法（防假阳性）

- **角度映射**：查昨天全天→canvas 像素按小时方向分桶，24 个小时方向均匀有曲线（修复前聚 0~3 时）；**3 点小样定位法**查维度顺序。
- **刻度环同心**：0/6/12/18 四锚点到圆心距离相等（终态 ±91px/117% 半径）；24 刻度 15° 均分。
- **标准带**：zr 两个 ring 半径与 v/4×R 公式一致 + 圆周采样绿色像素。
- 常规断言：卡片数=canvas 数、系列 24+2ring、legend on=16、首点分钟=0、机台联动（沟1→21台）、弹层按 data-bidx 开对应机台。
- 渲染核验用卡片近景截图；整页小图/自动视觉分析结论需交叉验证。

## 八、部署清单

1. 拷贝 `CuringCurvePieChart.aspx` + `.aspx.cs`（UTF-8 带 BOM）到服务器 WebSite `Plugins/Curing/Technology/`；无 dll/无需编译。
2. **挂菜单**（Curing 加硫工序）；**授权**"查询"(btnSearch)。

## 九、遗留项

- 挂菜单/授权待用户执行；服务器部署后建议实测一次 date_bin 聚合路径。
- chips 为单通道开关，无"按刻度组选"；上位机数值面板/NowStep 工步/自动刷新/直角切换/报警状态——2026-09-23 用户确认不做。
- 迭代史（16 条挤→10 条→6 条→[半径,角度]修复→双刻度整圆→单机台→双模式→24 刻度等 18 轮）过程细节已收敛，如需查过程看 git/会话记录。

---



## 十、两级精度：预览 2 分钟聚合，放大看原始点（2026-09-23 追加）

- **需求原话**："两秒一个点 预览时2分钟一个 放大看时两秒一个点"。
- **实现**：新增 `LoadPieRaw(equipCode, dateStr)` DirectMethod——QueryInfluxParallel（60 分钟分段）拉全天原始数据，**2 秒桶取桶内最后值**（实测 J101 全天 14,902 点，InfluxDB 实际密度约 5~6 秒/点且空闲段不记录，并非满 43,200）；点集首元素=分钟数带毫秒小数（角度轴数值型支持小数），tooltip 分钟带小数时显示到秒。
- **前端**：预览（卡片/单机大图）不动，仍 2 分钟聚合；**点【放大】弹层后异步 LoadPieRaw**，载入即以当前弹层几何重建（m.rawPts 缓存在机台对象上，关弹层再开不重查）；弹层标题显示"2秒原始 N 点"。buildMachineOption 数据源 `m.rawPts || m.pts` + `m.stride` 抽稀（src[j+=stride]）。
- **抽稀策略**：弹层常态 stride=2（约一半点，重建 ~680ms）；**滚轮放大超 1.2× 自动 stride=1 画全部原始点**（attachGeomZoom.apply 里 `machine.stride = st.r > baseR*1.2 ? 1 : 2`，闭包持有 machine 引用天然生效）；**滚轮重建加 60ms 合并节流**（全量重建数百 ms，逐帧重建会卡）。
- 教训：阈值定 1.6 时两档滚轮 1.56× 差一点不触发（实测踩坑）——交互阈值要按实际档位（1.25/档）校准。

---



## 十一、放大上限 6×→20×（2026-09-23 追加）

用户要求"放大程度再大"：attachGeomZoom 半径上限 `baseR*6` → `baseR*20`（滚轮 1.25×/档，从基准到顶约 13 档）。实测 15 档滚轮后 radius=1560px=20×基准(78) 精确封顶。第五节"限 1~6×基准"以本节为准（20×）。

---



## 十二、放大上限再提 20×→50×（2026-09-23 追加）

用户"再大点"：`baseR*20` → `baseR*50`（实测 25 档滚轮 radius=3900px=50×基准精确封顶）。第十一节"20×"以本节为准。