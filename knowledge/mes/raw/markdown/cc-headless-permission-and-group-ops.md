---
category: 部署运维
factory: 通用
module: 通用
status: active
tags:
- Claude Code
- CC headless
- allowedTools
- 权限墙
- 命令前缀放行
- 多agent协作
- pi-handoff
- 冷启动
title: Claude Code headless 权限放行与多 Agent 群模式协作运维经验
updated: '2026-09-01'
---

# Claude Code headless 权限放行与多 Agent 群模式协作运维经验

> CC（Claude Code）成员以 headless 方式接入 pi-handoff 群模式时，`--allowedTools "Bash"` 并不放行外部命令——无审批人等于一律拒绝，必须按 `Bash(python:*)` 这类命令前缀逐项放行；另沉淀 CC 旗舰端点冷启动慢、运行中消息排队语义、群打回秒级回路三条协作运维经验（证据链：2026-08-28 群 e2etool 的 wordcount.py 任务：CC 旗舰成员执行 → 审查"部分通过" → 打回 → 修订）。

## 一、与现有文档的关系（查重结论）

检索 my-kb：以「allowedTools / CC headless / 权限放行」「CC 群模式 协作 冷启动」检索，**无同主题文档**（仅命中权限控制、MCP 内存排坑等不同侧面）。相近主题两篇，均为互补关系：

| 文档 | 讲什么 | 与本文关系 |
|---|---|---|
| python-mcp-memory-and-port-mutex-pitfalls.md（库内，部署运维） | my-kb MCP 进程内存/端口/写库冷启动 torch 懒加载（122s 实录） | 本文第三章从 **CC 成员接入视角** 补充"启动期"成本与 `--strict-mcp-config` 跳过手段 |
| draft-kb-zcode-pi-task-dispatch.md（ZCode↔Pi 任务书分发草稿，未入库） | ZCode↔Pi 双 Agent 任务书分发与证据式审查协议 | 本文讲 **CC 成员** 接入同群的工具权限与运行语义，成员引擎不同、坑不同 |

## 二、核心踩坑：headless 下 `--allowedTools "Bash"` 不放行外部命令

### 2.1 现象（任务实录）

CC 成员（headless 启动，无交互审批人）执行任何外部 exe 一律被拦，报错原文一致：

```text
This PowerShell command contains multiple operations.
The following part requires approval: python --version
```

实测被拦面（exec 与 review 两个成员、两个权限档均复现）：

- `python --version` / `python -c` / `py --version` / 脚本直跑 → 全拦
- `git status --porcelain`（审查员查未申报改动时）→ 拦
- `cmd /c echo probe-ok`（外部程序试探）→ 拦
- `python msg.py ...`（**审查员发群消息质询**）→ 拦 → 质询通道瘫痪，审查只能标"未能核实"
- 派子代理（general-purpose）在其自己的上下文跑 → **同样被拦**（权限策略随会话继承，不随子代理重置）

对照组：`Get-ChildItem` 等 PowerShell cmdlet 正常放行——证明拦截对象是"外部 exe 的命令前缀审批"，不是 shell 整体故障。

另有一个微观坑：含 `$var` 双引号展开的命令串会被权限钩子拒绝，改成字符串拼接即可（同日实录）。

### 2.2 根因

headless 会话**无审批人**，一切"requires approval"等于直接拒绝。`--allowedTools "Bash"` 只把 Bash 工具本身加入允许清单；Windows/PowerShell 下外部 exe 仍按**命令前缀**逐个审批。即：放行粒度不是工具，而是命令前缀。

### 2.3 正确写法：命令前缀逐项放行（已落入 mas.py ROLE_TOOLS）

```python
ROLE_TOOLS = {
    # CC 的 --allowedTools "Bash" 在 headless 下不放行外部命令（无审批人=拒绝，实测踩坑），
    # 必须按命令前缀逐个放行；权限墙≠能力缺失，成员会如实申报
    "exec": ["Read", "Write", "Edit", "Glob", "Grep",
             "Bash(python:*)", "Bash(py:*)", "Bash(pip:*)", "Bash(git:*)",
             "Bash(ls:*)", "Bash(dir:*)", "Bash(cd:*)", "Bash(type:*)", "Bash(cat:*)",
             "mcp__my-kb__search_knowledge", "..."],
    "readonly": ["Read", "Glob", "Grep",
                 "Bash(python:*)", "Bash(git:*)", "Bash(ls:*)", "..."],
}
```

```bash
# 启动参数拼装（mas.py）
--allowedTools "Read Write Edit ... Bash(python:*) Bash(py:*) ..."
```

要点：**readonly 档也必须含 `Bash(python:*)`**——审查员要跑 `msg.py` 发群消息，否则审查员在群里"变哑巴"，质询通道随权限墙一起瘫（本任务实测发生了）。

### 2.4 行为面经验

- **权限墙 ≠ 能力缺失**：执行成员会如实申报"无法完成"，并给出待执行命令与预期输出，请人工在放行环境补跑——这是正确姿态；继续找路子执行就变成绕过用户权限配置，止步是对的。
- 修复位置在**拉起层**（mas.py 拼启动参数），不是改 CC 全局配置——按成员角色裁剪工具面，权责清晰、角色互不越界。

## 三、CC 旗舰（bigmodel anthropic 端点）冷启动慢：不需知识库就跳过 MCP

- 接入拓扑：CC 2.1.250，`anthropic_base_url` 指向 `https://open.bigmodel.cn/api/anthropic`，旗舰模型 glm-5.3。
- 实测：CC 旗舰**冷启动 + 首轮响应可达 3 分钟量级**（分派方转述；其中 my-kb MCP 懒加载占大头——与库内 my-kb 文档记录的 torch/transformers 懒加载冷启动 122s 同源同因）。
- mas.py 对策：任务不需要知识库时加 `--strict-mcp-config` 跳过 MCP 加载，源码注释明示"省 30-60s 启动；my-kb 懒加载很重"：

```python
if self.args.no_mcp:                       # mas.py CLI: --no-mcp
    # 任务不需要知识库时跳过 MCP 加载（省 30-60s 启动；my-kb 懒加载很重）
    extra += ["--strict-mcp-config"]
```

- 经验：给 CC 成员派不需要知识库的任务时，任务书/拉起命令应显式带 `--no-mcp`，把 30-60 秒以上的一次性启动成本直接省掉。

## 四、CC 成员运行中消息 = 排队语义，不是真插话

agent_claude.py 源码注释钉死的语义（本群实测）：

```python
# mode ∈ prompt|steer|followup（claude 的 steer=排队语义！）
# steer 的真实语义是排队（本轮结束后处理），不是 Pi 那种工具间隙真插话。
# CC 无独立 steer/followup 指令：运行中写入即排队，语义差异由 mas 层标注
```

运维含义：

- 给 **CC 成员**"插话"改变不了它**当前这一轮**的行为，消息只会排在轮末被消费；要立即中止只能走 abort（CC interrupt 控制协议，失败回落 terminate）。
- 同一群里 Pi 成员是工具间隙真插话、CC 成员是排队——**两种成员对同名 `msg` 的响应时机不同**，编排打回/纠偏时要按成员引擎预期时效，不能一概而论。

## 五、群打回回路时效实测

- 时间线（本任务实录）：review-1 出"部分通过"审查报告（最终回复 20:47:42）→ msg 打回 → exec-1 收到打回清单即开工（转录留痕"收到打回清单。逐项处理"）→ 交修订摘要（20:58:27）。全程约 11 分钟，其中**消息投递为秒级**（分派方实测转述），耗时大头是被打回项的重做本身。
- 机制：`msg.py` → 群事件总线 → broker inbox 轮询 → 对**在线**成员 `agent.send` 直接注入会话，成员转录留痕（`▶ review-1 → exec-1（msg）`）；离线成员的消息滞留 inbox，等其被拉起才消费。
- 经验：群模式"打回→在线成员直接改"是可行且快的闭环，比"拉起新会话重跑"省一轮上下文重建；代价是修订者要自己对照打回清单逐项自证。

## 六、入库审核记录（2026-08-28 用户拍板）

1. **分类定稿**：category=部署运维、module=通用、factory=通用（随库内 python-mcp-memory-and-port-mutex-pitfalls.md 同域惯例）。
2. **存疑点核实情况**（ZCode 终审补记）：
   - "冷启动+首轮 3 分钟"与"投递秒级"为编排方（ZCode）实测转述，量级可信，原始计时未单独落盘。
   - **修订后终审结论补全**：wordcount.py 已由 ZCode 独立复跑验证通过（正常文件 20 字符/4 单词/1 行；不存在文件友好提示且退出码 1），任务 e2e-1 终审通过（approved），打回项 2（冗余文件 _selftest_runner.py 删除）已验证。
   - 报错文案为 Windows/PowerShell 形态；Linux/macOS 文案未验证，但 2.3 前缀放行写法跨平台有效。
   - wordcount.py 本体质量、last.txt 曾混入 usage JSON（当轮已修）属任务个例，不入库。
3. **安全提示**：pi-handoff/config.json 内含 anthropic_auth_token 明文，本文刻意未收录；该文件若纳入 git 或共享目录需注意脱敏。
4. **tags 取舍**：`Claude Code` 与 `CC`、`多agent协作` 与 `群模式` 为同义，各保留一种写法。


## 七、2026-09-01 复测修正：Windows 上 CC 的 shell 工具真名是 PowerShell（放行规则必须按真名写）

> 本章修正第二章的旧结论并补三项实测。背景：pi-handoff 全面评审后做 B13/B11 实测，发现成员侧 python 通道整体失效，实验矩阵定位根因后修复复验。

### 7.1 第二章结论修正（重要）

第二章记录"`--allowedTools` 按命令前缀放行（如 `Bash(python:*)`）实证有效"——**该写法在 CC 2.1.250 + Windows 上已失效**。根因：

- **CC 2.1.250 在 Windows 上没有 Bash 工具，shell 工具真名是 `PowerShell`**（成员自述"本环境是 Windows(win32)，没有 Bash 工具，只有 PowerShell 工具"，行为佐证一致）。
- 给不存在的工具名放行 = 名单与实际工具不匹配 = 全部不放行。表现为成员侧任何带参数外部命令被拦：`This PowerShell command contains multiple operations. The following part requires approval: python --version`（连 `python --version` 都拦；无参数单 cmdlet 如 `Get-Date` 是内置安全命令可过，易误导排查方向）。
- **正确写法：`--allowedTools "PowerShell(python:*)"`**——实验矩阵实锤（同任务同模型）：acceptEdits + `Bash` 整名 → 拦；`PowerShell(python:*)` → 一发即过（`Python 3.11.9` 原样返回）。
- 工程落地建议双放 `Bash(python:*) + PowerShell(python:*)` 同前缀（防将来 CC 版本工具名回摆；多余规则无害）。已落码 pi-handoff/bin/mas.py 的 ROLE_TOOLS。

### 7.2 B13 定案：中文消息编码链清白，历史"乱码风险"实测不存在

- PowerShell → native argv → python 的中文传参链在这台机器（Python 3.11.9）**逐字符完好**：msg.py 直发"中文+符号 §≈±①☆→✓"落盘 events.jsonl 与源串完全一致（人工 PowerShell 链路与 CC 成员链路分别验证，双通过）。
- 此前"成员互发全靠 zcode 代发"的实况，根因不是编码而是 7.1 的工具名放行失效；修复后 mas 拉起的 CC 成员直发中文消息一次成功（22 秒全链路）。

### 7.3 B11 定案：CC abort（interrupt 协议）生效，秒级

- 对正在干活的 CC 成员投 `kind=abort` 信封 → **1 秒内**当前 tool use 被拒（"The user doesn't want to proceed with this tool use"）→ 本轮以 `subtype=error_during_execution` 终止 → 成员正常收敛 `settled`。
- 结论：CC 2.1.250 的 interrupt 协议有效，mas 的 STOP 120s 看门狗纯属兜底；运维上对 CC 成员的"中止"可预期即时响应。

### 7.4 附带实证与教训

- mas 硬杀后 status 残留的收敛分支（stop.py"进程双死→改写 exited"）真场景生效：实验群收尾一次收敛。
- **教训**：`--allowedTools` 放行无效时，先让成员自报"本会话有哪些工具"（工具名清单），再核对放行名单——工具名不匹配比权限语义更隐蔽；"无参数单 cmdlet 可过"是天然对照组，别把它误读成"沙箱整体封死"。