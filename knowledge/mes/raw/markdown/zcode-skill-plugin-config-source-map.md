---
category: 部署运维
module: 通用
status: active
tags:
- 命令 shadow
- hook 链
- 信任门控
- mcpb
- 重放脚本
- 幂等
- 锚点
- 遗留清账
title: ZCode 技能/插件/配置扩展机制源码图（开源 v3.14.3 实证）
updated: '2026-09-28'
---

# ZCode 技能/插件/配置扩展机制源码图（开源 v3.14.3 实证）

> 2026-09-28 从 ZCode 开源源码（ZCodeProject/zcode/src/）实证的扩展机制全景：技能根优先级链、同名歧义语义（非静默 shadow）、插件加载与官方市场、配置合并层级、MCP tools/list 的 resultType 协议修订（mcpb 本地补丁的依据）。替代 zcode-guide 技能的文档级描述。

## 一、技能发现：根目录优先级链（adapters/src/skills/roots.ts）

`resolveDefaultSkillRoots` 按 priority 升序分配（步长 10，数字小=先解析）：

1. **extraRoots（config skills.roots 配置的额外根）**：priority 10 起，scope=project/source=zcode；
2. **user 级**：`~/.zcode/skills`（20）→ `~/.agents/skills`（30）——**合并共存而非 fallback**（源码注释：用户可能同时装原生 .zcode 与兼容 .agents 技能，同级 .zcode 优先）；
3. **project 级目录链**：从 cwd 逐层向上到 git worktree 根（有 .git 的最近祖先），**内层目录优先于外层**；每层先 `.zcode/skills` 后 `.agents/skills`；
4. **extraResolvedRoots 追加**：插件技能根（FIRST_PLUGIN_PRIORITY=1000 起，plugins/index.ts:104，每插件递增）+ 内置 bundled skills 根（bootstrap/src/skills.ts:121 注入）。

## 二、同名技能语义：发现层不去重，消费层歧义报错

- **发现层**（adapters/src/skills/index.ts:71-89）：按 priority 升序遍历根，`selected` Map **以 path 为键**——同名不同路径的技能全部保留（源码注释："同名技能可能来自不同技能生态或版本，不能只按 name 去重；路径才是安装项身份"）。
- **消费层**（core/src/runtime/methods/subagent.ts:809-826）：按 name/qualifiedName 过滤，`matches.length > 1` 时**抛"Skill name is ambiguous; use the fully qualified skill name"**（recoverable），并列出全部 `plugin:skill` 全名——**同名不静默 shadow，必须消歧**。插件技能在系统提示里展示为 qualified name 并声明 bare alias 可加载；subagent 按 bare alias 调用时绑定回过滤后的 metadata 防误加载。
- **禁用**：config 的 skillOverrides → disabledPaths（发现层按路径过滤）；官方插件"卸载"=user config 写 suppressedBuiltins 标记，发现层按 manifest 权威 id 过滤（不依赖缓存物理删除，plugins/index.ts:155-157）。

## 三、配置合并层级（adapters/src/config/config-factory.ts）

合并顺序（后应用=更高优先级）：内置默认 → user config → project config → **CLI overrides 最高**（:47/:202）。例外：**MCP server 发现是扩展特有规则——user config 遮蔽 project config**（:391 注释），模型/权限/UI 字段不受影响。

## 四、MCP tools/list 的 resultType 协议修订（mcpb 补丁依据）

- ZCode 用 `@modelcontextprotocol/client` **2.0.0**（adapters/package.json:105，npm SDK 非本体代码）——该修订引入分页式 tools/list，**result 必须带 resultType 字段，缺失即拒收（"missing required resultType"）**。
- 本机 project-management mcpb 包（server.mjs:1128-1133）手写 JSON-RPC 实现老修订，本地补丁加 `resultType: 'complete'` 后可用；**上游化对象=mcpb 包仓库**（一行字段），非 ZCode；升级 .mcpb 会丢补丁（vendor 包覆盖），重打即可（补丁位置 server.mjs tools/list result 对象）。
- ZCode 侧 MCP 连接池/租约/假超时机制见 KB python-mcp-memory-and-port-mutex-pitfalls.md 第十节。

## 五、验证方法

- 技能根优先级：读 `adapters/src/skills/roots.ts`（PRIORITY_STEP=10 常量与 skillRootsForBase 顺序即语义）；
- 同名歧义：装两个同名技能（不同根），Skill 调用 bare alias 应报 ambiguous 并列全名；
- resultType 缺失拒收：手写 MCP server 的 tools/list 不带 resultType，ZCode 日志应现 "missing required resultType"。

## 六、遗留项

1. hook 机制（adapters/src/plugins/hook-sources.ts 存在）未深挖触发链；
2. 斜杠命令（/command）的 shadowing 规则未实证（zcode-guide:diagnosing-commands 是文档级）；
3. marketplace 安装链路（plugins/marketplace.ts + cdn-zcode.z.ai/marketplace.json）只定位未逐行；
4. mcpb 上游 PR 未提（用户拍板是否提给包仓库）。

## 七、与自家体系关系

- 自写技能（create-report、dispatch-agent 等）装在 user 级 `~/.zcode/skills`——与插件技能同名冲突时会歧义报错，改名或用 qualified name 即解；
- 后续 ZCode 插件/技能排障先查本图源码行号，不再依赖文档级 zcode-guide。

---


## 八、遗留清账：命令 shadow 语义、hook 链、mcpb 重放脚本（2026-09-28 同日）

**命令同名语义与技能相反（重要差异）**：`adapters/src/commands/index.ts:61-81`——发现层按 **name** 键控 Map，priority 升序遍历=**高优先级先入、后到同名直接 ignored**（诊断码 `custom_command_duplicate_name`，warning 级）——**命令是真正的静默 shadow**（先到先得），而技能是同名共存+调用时歧义报错。排障口诀：技能撞名看 ambiguous 报错，命令撞名看 duplicate warning 日志。命令根目录优先级与技能完全同构（`adapters/src/commands/roots.ts`，PRIORITY_STEP=10 同款：extraRoots→user `.zcode/commands`+`.agents/commands`→project 目录链→插件注入根）。

**hook 执行链（定位级）**：事件枚举 6 个（contracts/src/hooks/workspace-hook-trust.ts:188——SessionStart/UserPromptSubmit/PreToolUse/PermissionRequest/PostToolUse/PostToolUseFailure/Stop）；执行器家族在 `core/src/hooks/`（configured-runner 带 timeoutMs/maxOutputBytes 约束经 executionPort.run）；**有完整的 workspace-hook 信任门控体系**（trust-coordinator/trust-evaluation/trust-records/runtime-admission——hook 不是裸执行的，有信任记录与准入）；插件 hook 源发现=plugins/hook-sources.ts。matcher 逐行匹配语义未挖（无排障需求）。

**mcpb resultType 补丁处置终局**：包无公开上游（manifest 仅 author="Project Management Team" 无 repository）——**提 PR 不成立**，落地=本地重放脚本 `mcp/project-management/repatch_resulttype.py`：幂等检测（组合形态 `cacheScope: 'private', resultType: 'complete' }` 防注释误报）+ 锚点唯一性（整行含 `tools: publishedTools` 特征，防误伤 server/discover 响应的同款字段）+ 形态变化拒绝盲改提示人工。三场景实测：真重打/幂等跳过/模拟升级丢补丁全链路恢复，node --check 过。**升级 .mcpb 后跑一下该脚本即完成补丁重打**。