---
title: agency-agents 角色卡采用与改造规范
category: 部署运维
module: 通用
tags: [agency-agents, 角色卡, 多agent, dispatch-agent, mas, CC副手, checker, security, expert-test, onboard, 代理编制, AI人设, agent persona]
updated: 2026-09-11
status: active
---

# agency-agents 角色卡采用与改造规范

> 开源角色卡库 agency-agents 的采用决策与首批四卡改造实录：不做全量安装，按 mas.py 纯角色卡制重落地为 checker/security/expert-test/onboard 四张项目卡，并沉淀"原卡→项目卡"的改造规范供后续添卡复用。

## 一、源库是什么

- 仓库 msitarzewski/agency-agents（MIT 许可），230+ 专业 agent 人设卡，按 18 个部门组织（engineering/testing/security/design 等），口号 "A complete AI agency at your fingertips"
- 本质是纯 .md 人设库（非框架），官方提供 14 种工具的安装适配（含 integrations/claude-code，甚至有 zcode 适配目录）
- **本地克隆**：`ZCodeProject/agency-agents/src/`（shallow clone，325 个 md；中文 fork jnMetaCode/agency-agents-zh 未采用，277 卡本土营销向居多）

## 二、采用决策

- **不走官方安装器、不做全量安装**：本编制是自研 mas.py 角色卡机制（`pi-handoff/roles/*.md`，META 行定 agent/model/tools），不是 CC 原生 subagent——装进 ~/.claude/agents 会与编制脱节，故只取"人设内容"重落地
- **只补新职能、不叠审查仪式**（防过度仪式原则）：首批 4 卡全部是新职能或显式 opt-in 加审，没有一张是"每单必过"的新关卡
- 挑卡标准：心态/方法论可迁移（evidence-first、facts-only），且填补现有 6 卡（exec/reviewer/designer/scribe/expert-extnet/expert-sql）的真实缺口

## 三、首批四卡（2026-09-11 入编）

| slug | 角色 | 源卡 | 职责 | 档位 | 触发路由 |
|---|---|---|---|---|---|
| checker | 验收质询员 | testing-reality-checker | 高风险交付加审：默认 NEEDS WORK、逐条声明逐条核对、抽样复跑、存量数据反查 | CC glm-5.3 readonly | 改表结构/批量写/协议框架代码/上线前/自述与审查结论有出入 |
| security | 安全审查员 | security-appsec-engineer | 注入（iBATIS $ vs #）/越权/上传/敏感信息四主线，阻断/加固分级，给修法不只给标记 | CC glm-5.3 readonly | 涉安全敏感面（上传/权限/外部输入/连接串） |
| expert-test | 测试设计专家 | testing-evidence-collector | 交付后出验收清单+用户实测 SQL（禁连库的配套：验证 SQL 交用户执行） | CC glm-5.3 readonly | 报表/SQL 修复/交互改动的用户验收前 |
| onboard | 代码库导览员 | engineering-codebase-onboarding-engineer | 只陈述代码可证事实，三级说明（一句话定位/五分钟概览/深潜） | CC glm-5.3 readonly | 陌生项目/模块上手（Main 双项目同构差异、XYMES 遗留库） |

均已通过 `mas.read_role_card` 解析验证（META 行格式正确、tools 档位合法）；dispatch-agent 技能的编制行/路由表/审查分级已同步注册。

## 四、原卡→项目卡改造规范

源卡是英文+Laravel/Playwright/云原生特化的，**直接翻译不可用**，必须重落地。改造模板：

1. **格式壳**（mas.py 硬约定）：首行 `# 角色卡：<中文名>（<slug>）`，第二行 `META: {"name","desc","color","agent","model","tools"}`；agent ∈ claude/pi，tools ∈ exec/readonly
2. **心态保留、机械重写**：源卡的核心信条（如 Reality Checker 的"默认 NEEDS WORK、零问题是红旗、首版默认 2-3 轮修订"）原样继承；工具链命令（Playwright 截图、Laravel 路径）全部替换为 MES 项目族的等价物（KB 检索、iBATIS 语句、用户实测 SQL）
3. **必加项目纪律**：不连数据库（全局禁令）、先检索知识库、不给人情分/不脑补、被沙箱拦就如实写"复跑被拒"
4. **必加群内互发礼仪节**（对齐 designer 卡）：msg.py 只问事实/要澄清/索证据、不下指令、一次说全、三轮封顶
5. **验证**：`python -c "import sys; sys.path.insert(0,'bin'); import mas; print(mas.read_role_card('<slug>'))"` 解析通过才算卡合格

## 五、如何再添卡

1. 从 `ZCodeProject/agency-agents/src/<部门>/` 挑候选（engineering 33+ 张最肥，testing/security 次之）
2. 按第四节规范改造写入 `pi-handoff/roles/<slug>.md`
3. read_role_card 验证 + dispatch-agent 技能注册（编制行+路由表）
4. 群模式冒烟一次（低成本任务验证 META 生效、readonly 档确实无 acceptEdits）

## 六、经验与坑

- **源卡两类最有价值**：evidence-first 类（Reality Checker/Evidence Collector——反幻想验收心态）与 facts-only 类（Onboarding Engineer——只陈述可证事实）；报告模板类（大量 markdown 骨架）基本是 Laravel 语境，参考价值低
- 源卡 frontmatter（name/description/color/emoji/vibe）与 mas.py META 不是一回事——前者仅元数据，后者含 agent/model/tools 调度信息，改造时必须新造 META 行
- 152k+ stars 的热门库 ≠ 拿来即用：230 卡里真正适配自研编制的是少数，采用价值在"人设内容池"而非"安装即得 230 个员工"
