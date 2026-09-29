---
status: active
updated: 2026-09-10
title: pi-handoff 群聊台加固实录（2026-09-10）：长消息全文兜底链、同秒段消歧、mas 状态机修复与自启动三级降级
category: 部署运维
module: 通用
factory: 通用
tags: [pi-handoff, 多agent协作, Claude Code, 消息截断, 全文兜底链, 展开全文, 转录段消歧, 计划任务自启动]
---

# pi-handoff 群聊台加固实录（2026-09-10）：长消息全文兜底链、同秒段消歧、mas 状态机修复与自启动三级降级

> pi-handoff 多 agent 群聊台 2026-09-10 一日修复的可复用沉淀：长消息"报告看不全"的三级兜底链（侧车/转录段/终稿）与其"存量数据必须反查"教训、同秒两条长消息的前缀打分消歧（含换行同规格坑）、mas 两枚单进程冒烟测不出的状态机 bug、CC 大上下文首响延迟的思考心跳治理、PowerShell 变量大小写撞名与非提权环境自启动三级降级、CC 沙箱盘符白名单的运维口径，以及"讨论→群内派活→群内审查→终审代跑"闭环范式的双 CC 互相揪错实证。

## 一、与现有文档的关系（查重结论）

检索 my-kb：「pi-handoff 多agent 群聊 headless 权限 群模式」「群聊台 消息 截断 full 全文 兜底」「Claude Code 后台运行 事件线 console 群模式运维」多查询融合检索，top1 命中 `cc-headless-permission-and-group-ops.md`（部署运维/通用，2026-09-01）相关性 0.9961。**判定：独立新篇**，理由：

| 对比项 | cc-headless-permission-and-group-ops.md（既有） | 本文（新篇） |
|---|---|---|
| 主线 | CC 成员**接入**群模式的权限放行（allowedTools 命令前缀）与协作运维语义（冷启动/排队/打回回路） | 群聊台**本体机制**的加固：消息协议全文兜底链、broker 状态机、自启动部署、沙箱运维口径 |
| 时间断面 | 2026-09-01 | 2026-09-10 |

两者互补不重叠：本文第五章的"CC 2.1.250 Windows 下 shell 工具真名是 PowerShell"即既有篇权限结论的延续应用（代码内注释原文），首响延迟治理是对既有篇"冷启动慢"的深化（从启动期延伸到每轮首 token 期）。本文不替代既有篇任何结论。另 `stair-structure-retrieval-experiment.md` 第六章记有 2026-09-08 的 CC 只读审查档 F 盘受限经验，本文第七章引用为旁证。

## 二、长消息"报告看不全"：事件线 500 截断 + 全文三级兜底链

**机制事实（源码钉死）**：事件线（`.events.jsonl`）里的 text 统一截断 500 字——`bus.py` 常量 `TEXT_TRUNC = 500`（注释："事件里 text 的截断长度"）。截断是否发生由 `mas.py` 的 `emit_timeline` 打**精确标记**：`if len(raw) > bus.TEXT_TRUNC: ev["full"] = True`（注释："精确截断标记：前端据此挂'展开全文'（旧事件无此标，靠长度启发式）"）。

全文可从**一个 UI 入口 + 三级数据源**取回（素材原口径"四处可取"中的"页面展开按钮"实为 UI 入口，背后串行兜底三级数据源）：

1. **全文侧车**：`<member>.tools.jsonl` 按 seq 存全文（`bus.py` 的 `append_tool_full` / `read_tool_full`，单条上限 `FULL_TEXT_CAP = 200_000`，同 seq 的 start/end 取最后一条）；
2. **成员转录段**：`read_transcript_section(group, name, ts, tol=1, prefix="")` 按事件 ts 回成员转录 md（`## <名> | <ts>` 段头）捞对应 assistant 段全文。容差 1 秒的依据（注释原文）："mas 的 emit_timeline 与 log_md 是相邻两次 bus.ts() 调用，可能跨秒错位 → 容差 tol 秒"；
3. **.last.txt 终稿**：仅 assistant 适用，且要求事件截断文恰为其**前缀**才采信——"成员 resume 后 last.txt 是新终稿，前缀不匹配即不采信"。终稿上限 `LAST_TRUNC = 50_000`（`agent_claude.py` B1 注释："result 文本只喂 .last.txt（终审交付摘要），用 LAST_TRUNC 大上限；事件线仍维持 TEXT_TRUNC=500 不变"）。

UI 入口：页面气泡"展开全文"按钮带 seq+ts 调 `/api/toolfull`，`console.py` 先查侧车 `read_tool_full`，miss 且带 ts 再走 `read_msg_full_fallback`（转录段 → .last.txt）。

**兜底链的降级纪律**（`read_msg_full_fallback` 注释）：每级都要**比事件线截断文更长**才采信——识别"这一级也是截断的"就继续降级，防把截断文当全文返回。

**关键教训——机制上线前的存量数据必须反查**：全文侧车 2026-09-08 才上线，之前落的长消息侧车无条目；且"旧版转录落的也是截断文（2026-09-08 前）"。幸而 mas 从第一天起就把 assistant 全文写进成员转录，按事件 ts 回转录捞段即可复活旧报告（`bus.py` 注释实例：stair-review seq 110 审查报告）。推广：任何"新机制只覆盖增量"的设计，都要为存量数据留一条反查路径。

## 三、同秒两条长 assistant 段：前缀打分消歧（含换行同规格坑）

**问题**：同秒两条长消息时按 ts 回转录会命中多段候选，旧行为"delta 相等不更新、先到先得"会捞错段（`bus.py` `read_transcript_section` 消歧补丁注释，2026-09-10 遗留 #1）。

**解法——前缀打分**：利用"事件截断文恰是段全文的前 TEXT_TRUNC(500) 字"这一性质做消歧。tol 窗内全部候选按 `(前缀不匹配, 不比截断文长, delta, 段位置)` 打分取最小——前缀命中优先于 delta，跨秒错位的正确段也能被纠偏。兜底确定性："多段同为前缀（前 500 字相同）取先遇到的一段——数据面无法再消歧，确定性优先"。

**换行同规格坑**（审查员实测复现，注释留档）：段侧返回前 `strip("\n")`，base（事件截断文）侧须同样 `lstrip("\n")`——否则全文以换行开头时 `startswith` 必失配。教训：两侧比较的归一化必须**同规格**，只归一一边等于没归一。

## 四、mas 两枚真 bug：单进程冒烟测不出的集成语义

两枚均在 `mas.py` `handle_event`，2026-09-10 修复，注释留档：

1. **full 标记永不置位**：适配器（`agent_claude.py`）发出 assistant 事件时 text 已预截 500（`"text": full[:bus.TEXT_TRUNC]`），mas 若把这个截断值喂 `emit_timeline`，`len(raw) > TEXT_TRUNC` 永假 → full 标记永不置位、全文也不落侧车。修法（注释原文）："emit_timeline 必须喂全文……截断与标记统一在 emit_timeline 做"；且仅当 `text_full` 严格长于 `text` 才落侧车。教训：**截断与标记必须在同一处做**，分开两处必漂移。
2. **start 事件盖掉 working**：CC 空闲重连会重发 init/start（`agent_claude.py` 每次 init 都 `{"type":"start"}`），mas 旧版对 start 无条件置 ready → busy 成员被盖回"空闲"，"注入后页面 3 分钟显示'空闲'，像没反应"。修法：`self.set_state("working" if self.busy else "ready", force=True)`——状态机对**重复/乱序事件**必须幂等且带当前态条件。

**共性教训**：两枚 bug 都在 broker 消费侧，单进程冒烟（只测 adapter 本身）测不出——集成语义（跨进程事件流 + 状态机交互）必须有 broker 级测试。

## 五、CC 首响延迟治理：思考心跳 + 编排原则

**现象**：大上下文续会话（当日实测约 28 万 token 量级——素材口径，源码不可核）续会话首 token 前模型思考可达分钟级（`agent_claude.py` 注释："大上下文续会话首 token 前模型可思考数分钟"；`mas.py`："大上下文续会话首响可达分钟级"）。而**注入链路本身是即时的**：`mas.py` 收件去抖静默窗 `COALESCE_SEC = 2.5` 秒后合并注入，CC 适配器 `send()` 直写 stdin（毫秒级）——延迟全在模型侧，不在协议侧。

**治理一（可折叠"思考"卡）**：CC 的 thinking 块此前被丢弃 → 页面全程零动静像挂了。现 adapter 侧 10 秒节流上报（`now - _last_think_emit >= 10`），mas 映射为 tool 事件复用既有渲染成可折叠"思考"卡（两处注释均标 2026-09-10）。教训：**长静默期必须有可见心跳**，否则观感等于故障。

**治理二（编排原则）**：实现类追活优先起新成员（自包含任务书秒级开工），不硬等大上下文成员——新成员走 `compose_initial` 自包含注入（角色卡+群信息+任务），续会话成员则背着全量上下文慢思考。此为当日编排经验（素材口径），机制依据见 `mas.py`。

## 六、运维坑两枚：PowerShell 撞名与非提权自启动三级降级（`install_autostart.ps1`）

1. **PowerShell 变量大小写撞名**：PS 变量名大小写不敏感，脚本 param 是 `$Action`（带 `ValidateSet`），局部若命名 `$action` 再赋值，**就是给 param 赋值**，值不在 ValidateSet 枚举内即触发校验报错。脚本注释留档："变量名用 taskAction：PS 变量大小写不敏感，$action 会与本脚本 param $Action（带 ValidateSet）撞名——赋 task 对象即触发校验报错（2026-09-10 安装实测踩中）"。当日静态审查双方均漏检、执行才现形（素材口径）——PowerShell 这类大小写不敏感语言的变量遮蔽，静态审读很难盯出来。
2. **非提权终端建计划任务全被拒 → 三级降级**：本机实测（脚本注释原文）"非管理员终端下前两级均 0x80070005/拒绝访问——CIM 与 schtasks 都要提权，合规软件环境；第三级启动文件夹零提权等效"。降级链：① `Register-ScheduledTask`（CIM）→ ② `schtasks /Create` → ③ 启动文件夹 `.lnk`（`WScript.Shell` COM，零提权）。卸载脚本对计划任务与快捷方式**双机制都清**。当日实测杀掉 console 后能自动复活（素材口径 1 秒内；触发与登录会话相关，具体复活时延待核）。

## 七、CC 沙箱按盘符/路径白名单：运维口径"被拒则留代跑"

已钉死部分：放行粒度是**工具+命令前缀**（`mas.py` `ROLE_TOOLS`，如 `PowerShell(python:*)`）；且"CC 2.1.250 在 Windows 上没有 Bash 工具，shell 工具真名是 PowerShell——放行 Bash(python:*) 等于给不存在的工具放行"（注释原文，2026-09-01 实验矩阵结论，延续既有篇）。

盘符/路径维度（当日实测观察，机制细节待核）：C 盘工作目录下 python 全放行、自测真跑；F 盘全拦只读（历史观察，`stair-structure-retrieval-experiment.md` 第六章旁证："readonly 审查档 F: 盘只放行只读工具、文件写入全拦"）。

**运维口径（本节可复用结论）**：不管沙箱规则怎么变，任务书仍应写"**被拒则留代跑**"——不假设成员一定能执行，执行类验证列清单交有权限方代跑。

## 八、群模式 CC 闭环范式与双 CC 互相揪错实证

当日跑通的闭环：**讨论共识 → msg 群内派活（上下文接力）→ 群内审查 → ZCode 终审代跑**。

双 CC 互相揪错实证（均源码留档）：
- 审查员抓出**前缀换行失配**：`bus.py` 消歧补丁注释"审查员-1 实测复现"（本文第三章）；
- 执行者点破 **solo 侧车撞号链**：页面长消息全文侧车原先统一写 `live-user.tools.jsonl`（跨 solo 会话共享一个文件），而各 solo 事件流 seq **独立编号**、`read_tool_full` 同 seq 取最后一条——两个会话出现同 seq 长消息时，旧会话"展开全文"会捞到**新会话的全文**（静默错误数据）。修法=侧车挂目标成员名下（`live-<成员>.tools.jsonl`，与事件流同前缀、seq 同源，无跨会话共享），`console.py` `/api/send` 直达分支（2026-09-10）。背景依据：`bus.py` `append_group_event` A1 注释"重号会打乱全文侧车按 seq 的查找；跳空无害"——seq 不重号是侧车按 seq 查找的前提（A1 自愈初始化是更早的另一项修复，与本次撞号修复相互独立）。

范式要点：讨论产出共识文案、派活用 msg 上下文接力（不重述背景）、审查独立复跑取证、终审握有代跑权——与既有篇"群打回秒级回路"互补，构成完整协作环。

## 九、待人工确认

1. **category/module/factory 建议**：`部署运维 / 通用 / 通用`——与既有 `cc-headless-permission-and-group-ops.md`、`stair-structure-retrieval-experiment.md` 同构（pi-handoff 属自研工具/体系建设，非 MES 业务子系统，不适用业务 module 枚举）。备选：若知识库后续为 pi-handoff 单列技术类目可迁移。
2. **独立新篇 vs 追加章节**：判独立新篇（理由见第一章查重表）。若终审认为应并入既有篇，建议作为其"2026-09-10 加固"追加章节，并同步改既有篇 tags。
3. **待核项**（草稿中已标注，不作为钉死断言）：
   - "约 28 万 token 续会话"为当日实测口径，源码不可核；
   - 素材口径"协议 2 秒即注入"与源码去抖常量 `COALESCE_SEC = 2.5` 秒的对应关系（已按 2.5s 表述）；
   - "杀掉 console 后 1 秒复活"的复活时延与触发条件（登录会话相关）；
   - CC 沙箱按盘符白名单的精确机制（官方未文档化，仅实测观察）；
   - `bus.py` A1 修复（solo seq 自愈）的具体完成时点（注释未标日期，本文未断言其在 9-10 当日）。
4. **结构口径**：素材"全文四处可取"已按源码实况表述为"一个 UI 入口（展开全文按钮）+ 三级数据源（侧车/转录段/终稿）"，与素材原口径的对应关系请终审核对。