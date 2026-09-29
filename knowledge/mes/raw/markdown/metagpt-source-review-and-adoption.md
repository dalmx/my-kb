---
category: 技术-AI
factory: 通用
module: 通用
status: active
tags:
- MetaGPT
- 轮次熔断
- 计轮熔断
- max-turns
- CC参数实证
- circuit-break
- agent_claude
- 回归测试
title: MetaGPT 源码调研与自研多 agent 体系借鉴落地
updated: '2026-09-26'
---

# MetaGPT 源码调研与自研多 agent 体系借鉴落地

> 用户想了解 MetaGPT 多智能体框架，经"简介 → 借鉴评估 → 源码逐文件复核 → 三条落地"四步收口：自研体系（ZCode 大脑+CC/Pi+dispatch-agent）已覆盖其大部分机制，真正补位的是三条任务书模板级改进（交付回执、--max-turns 熔断、歧义即停），已改入 dispatch-agent 技能；exp_pool 与固定 SOP 流水线看清不搬。本文是机制依据与决策记录的终态权威版。

## 一、调研背景与结论总览

- **触发**：2026-09-26 用户"了解一下 metagpt" → 两轮分析（框架简介、借鉴评估） → 用户要求"查源码再分析一遍" → 源码逐文件复核（修正两处初版误判） → 用户拍板落地三条。
- **MetaGPT 一句话**：ICLR 2024 论文框架（DeepWisdom/深度赋智，现 FoundationAgents 维护），"AI 软件公司"——SOP 编码为提示序列，产品经理→架构师→项目经理→工程师→QA 流水线，输入一行需求产出 PRD/设计/代码。GitHub 70.6k star（网络信息）。
- **总量级结论**：自研体系与其大部分机制**殊途同归**（订阅路由、无状态角色、修复闭环、审查-修订、轮次熔断），真正补位的缺口只有三条，全部落在任务书模板层；**不搬**固定 SOP 流水线（绿地项目专用，与存量 MES 维护场景互补不适用）、exp_pool（自动缓存经验会放大错误，与 KB"终审+人工拍板收敛"路线冲突，同 Jev 评估的零 LLM 原则）。
- **现状注意**：开源版重心已转向商业产品 MGX 与 RoleZero 动态范式（README 新闻停在 2025-03；镜像 main 2025-10-04 为常规维护）；0.8.x 有代码注入漏洞 CVE-2026-19060（阿里云漏洞库网络信息，未实测）。

## 二、源码获取方法（可复用）

- GitHub 直连 `git clone` 与 codeload zip 下载均断流（curl 56 connection reset，国内网络典型症状）；`git ls-remote` 可通——**大对象传输才断，元数据握手正常**。
- cnpmjs.org 不适用（它是 npm 包镜像，不镜像 GitHub git 仓库；MetaGPT 是 Python 项目）。
- **成功路径**：Gitee 社区镜像 `fork-others/MetaGPT`（仓库自述镜像自 FoundationAgents/MetaGPT）+ 稀疏检出，只拉 `metagpt/` 源码包（9.5M），绕开文档/资源大文件：

```bash
git clone --depth 1 --filter=blob:none --sparse --branch main https://gitee.com/fork-others/MetaGPT <目标目录>
cd <目标目录> && git sparse-checkout set metagpt
```

- 整库 clone（即使 --depth 1）同样断流——仓库含大量文档图片，单 commit blobs 体积大。
- 版本锚定：镜像 HEAD `fc6e843` 2025-10-04（分析基线，行号引用均以此版为准）；源码副本留 `ZCodeProject/metagpt/src`。

## 三、核心机制源码实证

以下断言全部基于实读文件与行号（`metagpt/` 包内相对路径）。

### 3.1 消息与订阅路由（与自研 bus/mas 同构）

- Message 以 `cause_by`（动作类型字符串）为路由标签；Role._watch() 订阅动作类型集合（roles/role.py:284），_observe() 从私有 msg_buffer 按 `cause_by in watch` 过滤进自己的 memory（role.py:399-418）。
- Environment.publish_message 按 member_addrs 地址投递到各角色私有缓冲（environment/base_env.py:175-195）；`history` Memory 仅 debug 留痕。注意：**不是共享黑板**——是地址投递+订阅过滤（见第四节修正记录）。

### 3.2 结构化交付两层——changed_*_filenames 是精髓

- 交付物本体（PRD/代码摘要等）是 markdown 文档落盘给人读；**每条输出消息携带 instruct_content 结构化元数据给机器读**。
- 每个动作完成时消息必带变更文件清单字段：WritePRDOutput 带 `changed_prd_filenames`（actions/write_prd.py:174）、SummarizeCodeOutput 带 `changed_src_filenames`+`changed_code_plan_and_change_filenames`（roles/engineer.py:204-216）、WriteTestOutput 带 `changed_test_filenames`（roles/qa_engineer.py:166-174）——**下游与编排方不 diff 就知道改了什么**。
- 大对象不进消息：RFC 135 后消息只传文件名引用，内容落 FileRepository/ProjectRepo。

### 3.3 ActionNode 结构化输出与审查-修订

- ActionNode = key/expected_type/instruction/example 节点树（actions/action_node.py:135-176），输出强制 [CONTENT] 标签包裹（FORMAT_CONSTRAINT，action_node.py:53）+ tenacity 自动重试 + llm_output_postprocess 后处理；支持 json/markdown/xml 三种 schema。
- 内置审查-修订循环：REVIEW_TEMPLATE 逐 key 对照需求找不匹配给 comment，REVISE_TEMPLATE 按 comment 改（action_node.py:75-125）；ReviewMode/ReviseMode 分 HUMAN/HUMAN_REVIEW/AUTO 三档。

### 3.4 无状态角色（与"追活起新成员"同款）

- Engineer/QaEngineer 均 `enable_memory = False`（roles/engineer.py:104、qa_engineer.py:54）——角色不背对话记忆，状态全放 git 仓库与文件库，消息传引用。
- Memory 本体=消息列表+cause_by 倒排索引（memory/memory.py:20-35），无向量检索；"注意力"=get_by_actions(watch) 按订阅过滤（role.py:115-118）。

### 3.5 熔断家族（防跑飞的多层上限）

| 熔断点 | 位置 | 默认值 |
|---|---|---|
| 预算（美元） | Team._check_balance 抛 NoMoneyException（team.py:98-100）；CostManager 每调用记账（utils/cost_manager.py:35） | $10 |
| 团队轮次 | Team.run(n_round)（team.py:123） | 3 |
| QA 测试修复轮次 | test_round_allowed（qa_engineer.py:47），超限发"Exceeding rounds, stop" | 5 |
| 代码摘要回炉 | max_auto_summarize_code（engineer.py:176） | 配置 |
| react 循环 | max_react_loop（role.py:113；RoleZero 放宽至 role_zero.py:71） | 1 / 50 |

### 3.6 修复闭环与收件人解析

- QA 按 cause_by 驱动自环状态机：WriteTest→RunCode→DebugError→RunCode…（qa_engineer.py:161-205），全部 send_to=SELF；RunCode 结果由 `parse_recipient(result.summary)` 从 LLM 输出解析收件人，路由 Engineer(Alex) 或自留（qa_engineer.py:125-148）。
- Engineer 侧状态机 WriteCode→SummarizeCode→（_is_pass 用 LLM 判日志有无待办，IS_PASS_PROMPT，engineer.py:63）→不通过回炉（engineer.py:152-165）。

### 3.7 RoleZero 动态范式（新版默认）

- RoleZero（roles/di/role_zero.py）="think and act dynamically"：Editor/Browser/Terminal 工具 + BM25ToolRecommender 按任务推荐工具子集（role_zero.py:110）；**ask_human/reply_to_human 是注册工具**（role_zero.py:54）——把"问人"工具化；**Plan.append_task/reset_task/replace_task 也是工具**（role_zero.py:121-125）——计划执行中可被 LLM 修改。
- 固定 SOP 降级为可选兼容：`use_fixed_sop` 默认 False（role_zero.py:98）；ProductManager 继承 RoleZero 而非直接走流水线（roles/product_manager.py:21）。方向与自研"ZCode 大脑动态路由"一致——官方也承认写死流水线不是终态。

### 3.8 exp_pool 经验池（看清不搬）

- ActionNode.fill 被 exp_cache 装饰（action_node.py:596）自动缓存输入→输出；exp_pool/ 含 scorers、perfect_judges 评估经验质量，experience_retriever 检索注入上下文。
- 不搬理由：错误输出一旦入池被复用即放大；自研 KB 路线（ZCode 终审+用户拍板+save_markdown 综合收敛）慢但质量受控，与 Jev 评估（jev-decision-model-evaluation.md）同一条零 LLM 原则。

### 3.9 增量模式与文件级依赖

- WritePRD 三分支：_is_bugfix → bugfix 文档走 FixBug；get_related_docs 相关 → 增量更新；否则新建（write_prd.py:159-171）。
- 每次落盘带 dependencies（设计文档+任务文档+增量计划，engineer.py:139-146）——变更可按依赖传播。自研 KB 的 get_related 引用图已是跨文档等价物，更强。

## 四、对照自研体系判定（口径规则）

**判定优先级**：先问"自研是否已有等价物"（有则不动）→ 再问"缺口是否值得搬"（搬则最小形态落任务书模板，不加代码不加关卡）→ 与"零 LLM 原则/防过度仪式"冲突的明确不搬。

- **已殊途同归（不动）**：订阅路由（bus/mas inbox ≈ cause_by+watch）；无状态角色（十二期经验"实现类追活优先起新成员、不背旧会话上下文" ≈ enable_memory=False）；修复闭环（终审打回+checker ≈ QA 自环）；审查-修订（reviewer 卡+打回 ≈ REVIEW/REVISE 模板）；轮次熔断（msg.py 三轮封顶、DeskBox 六轮停战 ≈ test_round_allowed）。
- **值得搬（已落地，见第五节）**：changed_* 消息字段 → 交付回执；invest 预算熔断 → --max-turns；ask_human 工具化 → 歧义即停。
- **看清不搬**：固定 SOP 流水线（绿地专用，MES 存量维护用不上且其角色不读项目惯例——四层参考优先级体系的反面）；exp_pool（见 3.8）；Action 组件层（编制规模 YAGNI）；BM25ToolRecommender（mas.py tools 档位已够）。
- **修正记录（防幻觉，防旧版结论被引用）**：初版分析称"每个动作输出被 pydantic schema 强约束"——不准，文档本体是 markdown，机器强约束在消息 instruct_content 元数据层（3.2）；初版称"共享 Memory 黑板"——不准，真实是地址投递+私有缓冲+订阅过滤（3.1）。

## 五、落地记录（改动清单，无部署）

改动对象：`~/.zcode/skills/dispatch-pi/SKILL.md`（dispatch-agent 技能，任务书流程权威源），三行模板级改动，零代码、零新增关卡：

1. **交付回执**（一次性任务书模式列表新增条）：任务书"报告路径"节必须要求报告末尾附固定四段——① 变更文件清单（新建/修改全列）② 逐文件一句话改动摘要 ③ 自测脚本路径+实测输出原文（禁只写"通过"）④ 未做项及原因；ZCode 终审拿 ① 对 git status/实际产出路径机械比对，对不上直接打回。对标 changed_*_filenames（3.2），把"终审必须真跑自测"从纪律变结构，直接对着"26/7 文件未兑现零变化承诺"历史坑。
2. **CC 命令模板加 `--max-turns 50`**：轮次熔断防跑飞烧 token，50 对齐 RoleZero max_react_loop，正常重活远用不到。仅覆盖一次性任务书模式；群模式走 mas.py 不受影响（要熔断需改 bin/ 代码，未做）；Pi 无同类实证参数未加。
3. **歧义即停**（任务书"边界"节标准条款）：需求存在两种以上合理解读即停，歧义+自己倾向的解法列入回执 ④，由 ZCode 转.User 拍板。对标 ask_human 工具化（3.7）的文本版；headless 无审批人，猜错打回重来的成本远高于停下来问。

生效方式：技能每次派活时读取，首次派活即生效，无需重启。

## 六、遗留项

- 源码副本 `ZCodeProject/metagpt/src`（9.5M）去留待用户拍板。
- 群模式（mas.py 起成员）无成本/轮次熔断——需改 bin/ 代码，本次范围外。
- Pi（pi coding agent）有无轮次上限参数未考证。
- MetaGPT 实跑体验（pip install metagpt，Python 3.9-3.11 + node/pnpm，config2.yaml 配智谱 openai 兼容端点理论可行）未做，需要时再说。

## 七、验证方法与信息来源

- **源码实证**：第三节全部断言基于实读文件+行号，基线=镜像 HEAD fc6e843（2025-10-04），副本在 ZCodeProject/metagpt/src。
- **网络信息（未实测，已标注）**：70.6k star、ICLR 2024、MGX 商业化、CVE-2026-19060（GitHub 仓库页+阿里云漏洞库+搜索引擎）。
- **防幻觉纪律**：源码断言只写实读过的行号；两处初版误判在第四节显式纠偏，防错误版本被后续引用；未部署未实跑部分不冒充实证。
- **分工指针**：任务书流程与三条改动的执行细节=dispatch-agent 技能（~/.zcode/skills/dispatch-pi/SKILL.md）；群运维经验=cc-headless-permission-and-group-ops.md；角色卡规范=agency-agents-adoption-guide.md；同类调研先例（零 LLM 原则出处）=jev-decision-model-evaluation.md。

---



## 八、修正补记（2026-09-26 晚）：--max-turns 版本考证被推翻，群模式熔断改 adapter 计轮落地

**触发**：用户拍板做遗留项 2（群模式熔断）。动手前 `claude --help` 实证发现——**CC 2.1.250 根本没有 `--max-turns` 参数**（help 全量检索无 turn/limit 项；官方新版 docs 确有该参数、仅打印模式生效、且注明 stream-json 下行为另有规定，但本机锁定版本无）。第五节落地记录 2 里"--max-turns 50"为未实证的错误假设，照抄会直接启动失败——已修正。教训同第四节修正记录一脉：**CLI 参数必须本机 help 实证再写，官方文档领先本机锁定版**。

**真实落地（adapter 计轮熔断，不依赖 CC 版本）**：

- `pi-handoff/bin/agent_claude.py`：_read_loop 的 result 分支计数（CC 每轮一条 result），到 `config.json` 新键 `cc_max_turns`（默认 50，0=关）即熔断——先发 error(circuit-break) 再 settled（保证 mas 先置 _turn_failed 语义链）然后 terminate 树杀进程；计数随进程生命周期（T2 回试重启归零，但重试另有每回合 1 次硬上限，不构成绕过）。
- 与 mas 交互已核对：熔断 error 到达时 got_result=True，挡住 _try_retry_turn（mas.py:479），不误触发回合重试；任务状态保持 done（最后一轮 result 本身完成），熔断语义=成员额度用尽，时间线留 circuit-break 记录、成员 exited，ZCode 轮询可见。
- 一次性任务书模式不走 adapter，暂无轮次熔断（ZCode 起 CC 的 Bash 调用自带墙钟 timeout 兜底）；SKILL.md 的 CC 命令模板已改为"勿加 --max-turns"警示。
- 验证方法：`bin/test_circuit_break.py` 回归件两场景 flash 真跑全过——A 默认 50 单轮不误伤（事件序 start/session/working/assistant/result/settled，无 circuit-break）；B max_turns=1 单轮后即杀（事件序精确 result→error(circuit-break)→settled，1.5s 后进程确认死亡）。非单进程纸面推演，是真实子进程实测。

**遗留项更新**：第六节第 2 条（群模式无熔断）已闭环；新增说明——若 CC 将来升级到含 --max-turns 的版本（升级须三连通冒烟），可评估换回 CLI 参数（注意其 stream-json 特殊规定），adapter 计轮作为语义更可控的方案继续保留亦可。