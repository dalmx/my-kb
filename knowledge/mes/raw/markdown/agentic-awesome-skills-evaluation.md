---
status: active
title: Agentic Awesome Skills 调研评估
category: 技术-AI
module: 通用
tags: [agentic-awesome-skills, AAS, SKILL.md, agent技能, 技能分发, AAS Core, Claude Code, Codex, Cursor, 技能生态, 调研评估]
updated: 2026-09-26
---

# Agentic Awesome Skills 调研评估

> sickn33/agentic-awesome-skills 是目前最大的 AI coding agent 技能分发库（2,457+ 个 SKILL.md 剧本、~44k stars、npm v18.4.0）。2026-09-26 调研结论：其"agent 自选 + 先审后装 + 装前审计"的设计值得借鉴，但本机 GitHub 直连不通，npx 安装器又依赖 GitHub shallow clone 拉技能内容，大概率装不上；想用对口技能只能人工搬运写法。

## 一、是什么：定位与规模

- **仓库**：`github.com/sickn33/agentic-awesome-skills`，独立社区项目，与 Anthropic/OpenAI/Google 无官方关系；许可 MIT（代码）+ CC BY 4.0（文档）。
- **规模**（2026-09-26 调研时点）：2,457+ 个 SKILL.md 技能（v18 README 口径；v14.4.0 时代为 1,958、AAS Core 发布时 2,005+，数字随版本涨）；~44k GitHub stars（SkillsLLM 收录页显示 46.9k，各信源 43~47k 不等）。
- **npm 包**：`agentic-awesome-skills`，v18.4.0（调研当日 15 小时前发布），累计 57 个版本，迭代极快。
- **本质是分发层**：不是模型、不是 IDE，而是把各家技能库收编成统一目录的聚合器。每个技能 = 一份带上下文、约束、输出格式、分步指导的 SKILL.md，装进 agent 监听的目录后由 agent 加载执行。
- **曾用关联名**：antigravity-awesome-skills（Bright Coding 等旧文仍用此名指同一仓库），README 中 Antigravity 仍是默认安装目标之一。
- **与 awesome-claude-skills 的区别**：后者是"精选清单、手动拷贝、仅 Claude Code"；AAS 是"可安装、多工具、版本锁定"的分发基础设施（官方有专文对比 `docs/users/agentic-awesome-skills-vs-awesome-claude-skills.md`）。

## 二、核心设计：AAS Core（15.x 起的形态）

新版本重心从"技能库"升级为**本地 agent-first 控制平面**，流程四步：

1. Codex/Claude（装了 AAS 的本地只读 MCP）先检查目标项目；
2. agent 用 `search_skills` / `read_skill_file` 等工具搜完整本地目录，**自己挑**确切技能 ID——AAS 不排名不推荐，选择权在 agent（agent-owned selection）；
3. 只读的 `compose_stack` 在内存中校验选择，落成 `aas-stack.json` 技能栈清单 + 选择证据 sidecar；
4. `aas` CLI 做校验和**不可变安装计划预览**，人工审查后才实际安装。

官方明确边界：**结构校验 ≠ 语义适配认证**；apply/回滚仍是实验性。"agent 自选 + manifest 可复现 + 先审后装"是它区别于普通 awesome 清单的主要卖点。

## 三、四个消费面与宿主兼容

| 消费面 | 用途 |
|---|---|
| AAS Core MCP | Claude Code / Codex 一等公民路径（agent 自选技能栈） |
| 专项插件（13 个已发布） | 每包 8~10 技能：Web App Builder、Security Engineer、Documents & Presentations、Data Analytics、Agent & MCP Builder、QA & Test Automation、DevOps & Cloud、Accessibility、API Platform、SaaS Launch、AI Product & Evaluation Ops 等 |
| Bundles / Workflows | 角色推荐组合（Security Engineer、OSS Maintainer、Web Wizard…）+ 有序执行剧本（ship SaaS MVP、安全审计、AI agent systems、QA 浏览器自动化、DDD） |
| 全量直装 | `npx agentic-awesome-skills --<tool>`，见下 |

安装旗标（npx 方式）：

```bash
npx agentic-awesome-skills --claude   # 也支持 --cursor / --codex / --gemini / --kiro / --agy / --antigravity / --path <目录>
npx agentic-awesome-skills --skills <id1,id2>        # 精确选装
npx agentic-awesome-skills --category <类> --risk safe,none   # 按分类+风险过滤
npx agentic-awesome-skills --release <版本> --pin    # 版本锁定
npx agentic-awesome-skills --dry-run                 # 只预览不落盘
npx agentic-awesome-skills audit --skills <id>       # 离线安全审计
```

- **兼容 11+ 宿主**：Claude Code、Cursor、Codex CLI、Gemini CLI、Antigravity IDE/CLI、Kiro、GitHub Copilot（`gh skill install` 预览）、OpenCode、Autohand Code、AdaL CLI、自定义路径。
- Claude Code / Codex 走 AAS Core MCP 预览路径，其余宿主 npx 直装到各自技能目录。
- **Antigravity 目标有保护**：默认拒绝整库安装，必须 `--skills` 过滤或显式 `--all`（防上下文过载崩溃循环）。

## 四、内容来源与风险分级

**聚合来源**（统一目录模式）：

- 官方源：anthropics/skills、openai/skills、microsoft/skills、google-gemini/gemini-skills、huggingface/skills、supabase、neon、weaviate、cloudflare、vercel-labs、expo
- 社区源：obra/superpowers、travisvn 与 karanb192 的 awesome-claude-skills、VoltAgent/awesome-agent-skills、addyosmani/agent-skills、mattpocock/skills、emilkowalski/skills
- 大批量集：rmyndharis/antigravity-skills（300+ 企业技能）、BagelHole DevOps-Security（163 技能）、Claude-BugHunter（83 个攻防技能）
- 中文社区贡献少量：travel-planner（中文优先）、product-decision-agent（中文产品判断）、humanize-chinese、yunqu-ai 微信公众号技能

**风险分级**：目录给每个技能标风险级，含 `critical` 与 `offensive`（后者标 `AUTHORIZED USE ONLY`，83 个攻防类技能属于此类）。`audit` 子命令可离线扫描技能的命令/网络/凭据/文件系统/破坏性信号——官方口径是"审查辅助，不是安全证书"。

## 五、本机适配评估（2026-09-26 实测）

**网络实测（当日下午）**：

| 通道 | 结果 |
|---|---|
| 本地 WebFetch github.com / raw.githubusercontent.com | 超时（UND_ERR_CONNECT_TIMEOUT） |
| jsDelivr CDN 镜像 | 超时 |
| git ls-remote 直连 | Connection was aborted，未配代理 |
| 本机代理端口（7890/1080/10808 等常见口） | netstat 无监听 |
| 服务端搜索（Z.ai WebSearch / web reader） | 通（本次调研主通道） |

**结论：本机大概率装不上**。npm 安装器默认对 GitHub 做 shallow partial clone（需 Git 2.25+）拉取 `skills/` 目录树——**npm 包里不含技能内容**，GitHub 不通则 npx 装到一半挂在 clone 步骤。想用需先解决代理。

**官方承认的头号坑：上下文过载**——技能装多了撑爆 agent 上下文、拖慢启动甚至崩溃循环（有 `agent-overload-recovery`、Windows 截断恢复专档）。正确姿势：按插件包或 `--category` 小批量装。

**可借鉴点**（即使不装也值得学）：装前审计（audit 扫描第三方技能的命令/网络/凭据信号）、技能风险分级、manifest 可复现安装——这套纪律适用于任何第三方技能/MCP 引入。

## 六、调研方法与信源（防幻觉纪律）

- 本机 GitHub 全通道不通，调研靠**服务端 WebSearch 多轮检索 + web reader 抓取非 GitHub 域**完成；信息主源为 npm 包页（v18.4.0 README 全文），GitHub Pages 站点与 Bright Coding 评测（v14.4.0 时点）作交叉验证。
- 未实际安装、未跑 npx——所有"装不上"结论是网络实测 + README 机制描述的推断，不是安装失败的实录。
- 信源清单：
  - github.com/sickn33/agentic-awesome-skills（本体，本机不可达）
  - npmjs.com/package/agentic-awesome-skills（README 主源）
  - sickn33.github.io/agentic-awesome-skills（SPA 壳，仅定位描述）
  - prompts.brightcoding.dev 博客深度评测（旧版 1,958 技能时点）
  - skillsllm.com/skill/agentic-awesome-skills（stars 数据）

## 七、与现有体系的关系

互补而非替代：ZCode 技能/插件市场（如 ui-ux-pro-max）管生态内技能；`dispatch-agent` + agency-agents 角色卡（见 `agency-agents-adoption-guide.md`）管"谁来干"；AAS 管"按什么剧本干"（任务剧本层）。Pi 侧插件生态盘点见 `pi-extension-ecosystem-and-selection.md`，同类"外部生态调研"文档。

## 八、遗留项

1. **想试装需先解决 GitHub 网络**（代理），装时按插件/`--skills` 小批量，先 `--dry-run`，攻防类技能除非授权场景不装。
2. **可搬运候选**：即使不装整库，systematic-debugging、security 审计类技能的 SKILL.md 写法可人工拷贝参考（需网络通后取，或让有网环境的人导出）。
3. **未实测**：本机从未跑过 npx 安装器与 AAS Core MCP，上述安装细节均出自 README，实装时以实际输出为准。
4. 版本数字随迭代快涨（14→18 仅数月），引用本文数字时注意时点（2026-09-26）。
