---
category: 部署运维
module: 通用
status: active
tags:
- Pi
- 扩展
- 插件
- extension
- pi install
- web search
- pi-lens
- pi-web-access
- keyless
- DuckDuckGo
- headless
- 副手
- 选型
- 生态盘点
- agent_pi
title: Pi 扩展生态盘点与选型（Pi 副手能力增强）
updated: '2026-09-11'
---

# Pi 扩展生态盘点与选型（Pi 副手能力增强）

> 本机 Pi（0.84.1，GLM glm-5.3-flash，bin/agent_pi.py headless 派活）的能力增强插件盘点：生态很大（awesome-pi.site 目录 + composio 评测，2026-09-11 快照），但对本套"ZCode 大脑 + CC 旗舰 + Pi 轻活"架构，值得装的只有联网搜索与代码质量反馈两类；架构层（子代理/记忆/编排/交互式 TUI）一律不装，交互式插件会卡死 headless 派活。

## 一、结论：只补短板，不动架构

| 判定 | 插件 | 理由 |
|---|---|---|
| ✅ 值得装 | `pi-lens`（74.5k/月） | 实时 LSP/lint/格式化反馈注入编辑，35+ 语言，直接提升 Pi 写码轻活交付质量 |
| ✅ 值得装 | `pi-web-surf` | 零配置免 key DuckDuckGo（重火力换 `pi-web-access`，内置 keyless DDG + 可配 Brave/Tavily/Exa） |
| ⚠️ 可选 | `pi-mcp-adapter` / `pi-mcp-extension` | 让 Pi 直连 MCP（含 my-kb）；架构上目前是 ZCode 检索后写进任务书，装=给 Pi 开后门，需拍板 |
| ⚠️ 可选 | `cc-safety-net`（26.9k/月） | 拦 destructive 命令/秘密文件；本套 Pi 由 ZCode 受控派活，属锦上添花 |
| ❌ 不装 | 见第四节清单 | headless 卡死 / 架构重叠 / GLM 不适用 |

## 二、生态全景（按类别，2026-09-11 来源快照）

来源：awesome-pi.site/extensions/ 目录 + composio.dev/content/top-pi-extensions 评测。下载量均为该目录展示值。

- **联网搜索/抓取**：pi-web-access（403.6k/月，搜索+URL/PDF/YouTube/GitHub，多 provider）、pi-web-search（18.1k/月，provider 原生：Gemini/Grok/OpenAI/Anthropic，**GLM 不适用**）、pi-web-surf（免 key DDG 起步）、pi-lynx（免 key：DDG Lite + Brave HTML + Reddit）、pi-websearch（code-yeongyu，DDG HTML 端点最简实现）
- **代码反馈/编辑**：pi-lens（74.5k/月，LSP+lint+format）、pi-hashline-edit-pro（14.8k/月，哈希锚定编辑防漂移）、pi-pr-review（7.6k/月）
- **后台任务**：pi-background-tasks（107.7k/月，持久 shell 任务）
- **子代理/编排**：@tintinweb/pi-subagents（47.7k/月）、pi-fabric（22.2k/月）等
- **记忆**：pi-memory（38.8k/月）、pi-hermes-memory（31.1k/月）等
- **安全/沙箱**：@trim21/personal-pi-extensions（44.1k/月，bwrap 沙箱，**Linux only**）、cc-safety-net、pi-redact-all
- **交互式提问/UI**：@juicesharp/rpiv-advisor（151.5k/月）、pi-ask-user（8.6k/月）——**TUI 交互，headless 致命**
- **规划/任务**：pi-goal-x（57.2k/月）、pi-tasks 系列
- **Provider/Auth**：pi-acp（282.4k/月）、pi-provider-litellm、pi-claude-bridge（28.8k/月）
- **上下文管理**：billion-context-pi（24.4k/月）、pi-mega-compact（11.7k/月）、pi-cache-optimizer
- **MCP**：pi-mcp-extension（11.5k/月）、context7-pi（5.2k/月）
- **知识/RAG**：@zosmaai/pi-llm-wiki（10.9k/月，Karpathy 模式——**my-kb 已评估不转，见 llm-wiki-karpathy 相关记录**）
- **方法论技能**：bigpowers（61.7k/月）、pi-workflow-roles（38.0k/月）
- **Composio top-10 另荐**：context-mode（工具输出沙箱化+SQLite 记忆）、Piolium（安全审计多阶段）、Plannotator（计划模式+浏览器批注）

## 三、本机实况与安装方式（0.84.1 实测）

2026-09-11 本机实测 `pi --version`=0.84.1，`pi --help` 确认命令齐备：

```bash
pi install <source> [-l]    # 装扩展并写 settings；-l=仅当前项目局部
pi remove / pi uninstall    # 卸载
pi list                     # 列已装扩展
pi config [-l]              # TUI 启停包内资源
pi update [source|self|pi]  # 更新
```

- 安装后需 `/restart` 或重启 Pi 会话生效；**默认全局生效（含群模式 Pi 成员、headless agent_pi.py）**，试装先用 `-l` 在测试目录局部验证
- 版本纪律：生态按最新 core 演进，若扩展要求新版 core 才触发既定 0.85.1 升级流程（bench counting 冒烟，见 pi-agent-glm-setup 记忆）
- 安全纪律（composio 评测原话警告）：扩展以 full-system access 运行——锁版本、审源码再装，与"自研协议代码必须反查"同精神

## 四、明确不装清单与理由

1. **交互式 TUI 类**（rpiv-advisor / pi-ask-user / 主题 / pi-vim / Powerline 状态栏）：headless 派活无终端可交互，模型调用 ask 工具即卡死或报错，属绝对禁区
2. **子代理/编排类**（pi-subagents / pi-fabric / doompi-team）：与 mas 编排架构重叠，且 flash 定位轻活不该当大脑——编排权在 ZCode
3. **记忆类**（pi-memory / pi-hermes-memory / gentle-engram）：架构上 Pi 是无状态一次性执行者，记忆/沉淀由 ZCode 层（auto-memory + my-kb）负责，装=打破设计
4. **Provider 类**（pi-claude-bridge / pi-nvidia-nim / pi-multiprovider）：GLM 直连已定案，CC 独立成编制，桥接属重复建设
5. **pi-llm-wiki**：my-kb 架构评估已定论不转 Karpathy 模式
6. **Composio**（1000+ SaaS 应用集成）：MES 本地开发场景无关

## 五、装后冒烟口径

1. `pi list` 确认装入 → 派一个带 lint 场景的小代码任务，验证 pi-lens 诊断确实注入（回看会话转录里有无 LSP/lint 事件）
2. 联网插件：派"搜某个 npm 包最新版本"任务，验证免 key DDG 真出结果
3. headless 回归：正常派一单轻活，确认无卡死、无等待输入超时

---


## 六、安装实录（2026-09-11，四件全装 + 实弹验证）

**装入清单**：`pi-lens` 4.1.6（peer 声明兼容 `^0.84.1`，与本机锁定版匹配）、`pi-web-surf` 1.0.1、`cc-safety-net` 2.3.4（keywords 含 `pi-package`，多平台安全工具，peer 的 `@opencode-ai/plugin` 是其 OpenCode 变体，不影响 Pi 侧）。**`pi-mcp-adapter` 2.29.0 早已在位**——settings.json 的 packages 里本来就有，且 `~/.pi/agent/mcp.json` 已接好 my-kb（python server.py）——Pi 直连知识库的配置其实早就在了，此前未被发现。

**headless 实测工具清单**（`pi -p` 让模型自报）：read/bash/edit/write + mcpScript/mcp/mcp__my_kb + lens 八件（lens_diagnostics、symbol_search、effective_config、project_report、module_report、read_symbol、read_enclosing、pi_lens_activate_tools）+ internet_search/internet_scrape。cc-safety-net 不暴露工具（拦截器设计，正常）。

**实弹验证结果**：
- **cc-safety-net 通过**：pi 派 `cat .env` 被规则 `secret.basename.env` 在执行前拦截，且 guard 禁止换 read 等工具绕行；headless 下自动拒绝、不卡死。`status` 命令显示 destructive/secrets 防护 ok（其提示"Not active"仅指 Claude Code 侧插件变体，与 Pi 无关）
- **my-kb 直连端到端打通**：Pi 真调 search_knowledge 命中「Ext.NET 场景路由总表」0.9985
- **internet_scrape 可用**（站点依赖）：静态站（TUNA 镜像站）完整出 title+markdown；JS 渲染页（npmmirror）只有 title；反爬站（baidu）返回空——均属正常行为
- **internet_search 当前无可用后端**，三层坑：①pi-web-surf 依赖外部 `ketch` Go 二进制（非 npm 依赖，需从 GitHub release 下 `ketch_*_windows_x86_64.zip`，SHA256 对官方 checksums.txt 校验后放 `~/AppData/Roaming/npm/`）；②ketch 默认后端是 brave（要 key），须 `ketch config set backend ddg`；③本网络 DDG 被墙（html.duckduckgo.com i/o timeout）。**补通待办**：注册 Brave 免费 API key（brave.com/search/api）后 `ketch config set brave_api_key <key>` 即恢复搜索；或接受现状——搜索需求走 ZCode（内置 WebSearch）架构上本就覆盖

**回滚资产**：装前 settings 备份在 `ZCodeProject/tmp/pi-settings-backup-20260911.json`；卸载用 `pi remove npm:<包名>`。

**对第一节结论的修正**：pi-web-surf"零配置免 key"的说法仅对海外网络成立；本机网络环境下它是"scrape 可用 + search 待 Brave key"。