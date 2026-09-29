---
status: active
updated: 2026-09-28
title: ZCode 开源仓库与遥测数据出口审计
category: 技术-AI
module: 通用
tags: [ZCode, 开源, 遥测, 数据安全, 数据出口, 上报, 审计, OTLP, telemetry, RepoWiki, 偷传代码, zai-org, codeload, git clone, 源码审计, Z.ai, 隐私]
---

# ZCode 开源仓库与遥测数据出口审计

> 2026-09-28 智谱将 ZCode 开源至 github.com/zai-org/ZCode（Apache 2.0）。本文=源码+本机安装产物+运行痕迹三方对照的数据出口审计结论：本机 CLI 侧无代码/项目内容上传通道，遥测链路处于停用态，唯一代码出网通道是模型 API 本身。

## 一、背景与总结论

- **背景**：2026-09 ZCode 陷"偷传代码"风波（Repo Wiki 功能生成并上传本地仓库快照），09-21 智谱道歉整改并开源，v3.14.0 移除 Repo Wiki 并清空云端存储桶，README 标注开源同步至 v3.14.3（2026-09-23）。
- **审计问题**：本机正在跑的官方 ZCode 到底往哪里传什么？
- **总结论（三方实证）**：
  1. **RepoWiki 在 v3.14.3 源码零残留**（`repo.?wiki` 全仓 grep 无命中）——官方"已移除"声明属实；
  2. **遥测体系存在但本机处于停用态**：数仓事件上报端点 `ZCODE_TELEMETRY_REPORT_ENDPOINT` 开源源码默认不注入、本机 CLI bundle 也未注入 → `telemetryCore.ts:368` 的出口检查直接 return，事件不出网；
  3. **本机代码/项目内容的唯一出网通道 = 模型 API 本身**（`api.z.ai/api/anthropic`，coding plan 业务必需，所有 LLM coding 工具的本质，非遥测）；
  4. 遥测 schema 是 strict 设计，源码注释明写"避免新增 runtime 字段时把 prompt、工具输入或 provider URL 意外外带"。

## 二、表事实：仓库结构与关键文件

- **仓库**：`https://github.com/zai-org/ZCode`，pnpm monorepo（TS），39MB tarball。
- **获取方式**：本机 github.com git 协议半通（握手过、大流量被掐），**codeload.github.com tarball 直下可用**（13s/39MB）——两条通道互为备份，网络漂移时先速测再选路。
- **源码落位**：`ZCodeProject/zcode/src/`（解压自 `ZCode-main.tar.gz`）。
- **结构**：`apps/zcode-cli/`（Agent CLI 与运行时源码，本机日常跑的就是它）+ `packages/`（client/desktop/server/services/shared/ui/provider 等）+ `third-party/`。
- **关键文件**：

| 文件 | 作用 |
| --- | --- |
| `apps/zcode-cli/packages/telemetry/src/bootstrap.ts` | OTLP exporter 初始化（标准 `OTEL_EXPORTER_OTLP_*_ENDPOINT` 变量，未配置不建 exporter） |
| `packages/services/src/telemetry/telemetryCore.ts:368` | 数仓事件出口硬检查：`!ENABLED \|\| !REPORT_ENDPOINT` 即 return |
| `packages/shared/src/env.ts:50-58` | `ZCODE_TELEMETRY_ENABLED` 编译期写死 true（功能开关）；`ZCODE_TELEMETRY_REPORT_ENDPOINT`/`ZCODE_ARMS_RUM_ENDPOINT` 运行时注入，注释明写"未配置即停用，构建产物不内嵌" |
| `apps/zcode-cli/packages/bootstrap/src/telemetry-bootstrap.ts` | 遥测引导：OTLP Header 等私密配置不进 Tool/MCP 子进程环境 |
| `apps/zcode-cli/packages/adapters/src/device/cli-device-mid.ts` | 设备身份 deviceMid，存 `~/.zcode/v2/telemetry-state.json`，用于反馈与 provider 请求头 |
| `packages/shared/src/zcode-protocol-v4/telemetry.ts:263` | 对话遥测事实 schema（discriminatedUnion + strict） |

## 三、遥测架构与开关语义（口径）

- **双开关设计**：`ZCODE_TELEMETRY_ENABLED`（编译期，源码=true）只是功能开关；**真正决定出网的是运行时端点注入**——官方分发版可能注入、开源自建版默认无 → 不上报。env.ts:48 注释自证："写死 false 会让运行时已配置的数仓/ARMS 永远空转"。
- **对话遥测内容边界**：只收集元数据——turn/toolCall/permission 生命周期事件、token 计数（pre/postCompactTokenCount）、模型名、状态枚举、时间戳、session/message ID。schema strict + superRefine 校验，无 prompt 正文/工具输入/文件内容字段。
- **`zcode.z.ai/api/v1` ≠ 遥测端点**：它是 OAuth 授权基址（`apps/zcode-cli/packages/adapters/src/auth/cli-oauth.ts:4`），登录换 token 用。

## 四、本机出口清单实证（三方对照）

| 出口域名 | 用途 | 性质 | 源码依据 / 本机依据 |
| --- | --- | --- | --- |
| `api.z.ai/api/anthropic` | 模型 API（coding plan） | 业务必需，会话上下文含代码必然上行 | zcode-builtin.json 模板 + bundle |
| `zcode.z.ai/api/v1` | OAuth 登录/换 token | 仅认证流 | cli-oauth.ts:4 + bundle 上下文（crypto+poll token） |
| `cdn-zcode.z.ai` | 官方插件市场元数据+资产下载 | 下行为主 | marketplace.json/assets 路径 |
| 数仓事件上报 | token 计数等元数据 | **本机停用**（端点未注入） | telemetryCore.ts:368 + bundle 无注入值 + 日志无事件 |
| ARMS RUM（阿里云） | 桌面端真实用户监控 | **本机未见注入**（app.asar 无明文端点） | env.ts:57 同为运行时注入语义 |
| RepoWiki 快照上传 | 仓库快照上行 | **v3.14.3 已移除** | 全仓 grep 零命中 |
| `api.telegram.org` | bots/ 机器人频道功能 | 仅用户主动配 bot token 才跑 | telegramChannelRuntime.ts |
| vercel-storage.com | UI Rive 动画素材 | 纯下行 | persona.tsx |

- **运行痕迹旁证**：`~/.zcode/v2/telemetry-state.json` 的 `lastDailyActiveDate` 停留在 2026-07-21（deviceMid 创建日）再未滚动；本机 CLI 日志近三天 telemetry 关键词命中≈0——日活打点链路未在跑。

## 五、验证方法（可复现）

- 源码获取：`curl -L -o z.tar.gz https://codeload.github.com/zai-org/ZCode/tar.gz/refs/heads/main`（git clone 失败时的替代通道）。
- 遥测出口检查：grep `ZCODE_TELEMETRY_REPORT_ENDPOINT` 赋值与 `OTEL_EXPORTER_OTLP` 于安装产物（如 `F:/zcode/resources/glm/zcode.cjs`）——无注入值即停用。
- 域名清单提取：`grep -rhoE "https://[a-zA-Z0-9.-]+" --include="*.ts" apps packages | sort | uniq -c`。
- RepoWiki 残留：`grep -rniE "repo.?wiki"` 全仓。
- 运行痕迹：`~/.zcode/cli/log/zcode-YYYY-MM-DD.jsonl` grep telemetry + `telemetry-state.json` 的 lastDailyActiveDate 滚动检查。
- 防假阳性：bundle 压缩后变量名变形，grep 变量名赋值会漏——必须补域名形式扫描；`zcode.z.ai` 命中先读源码定角色再定性（本次即 OAuth 误判风险点）。

## 六、遗留项与待钉死

1. **"登录后服务端动态下发端点"静态审计无法排除**——理论上官方版可经 OAuth/配置接口下发端点使遥测激活。彻底钉死需抓包（本机防火墙/代理侧观察 zcode 进程对外连接）或动态插桩，未做。
2. 桌面端 app.asar 只做了明文域名扫描，未解包逐模块审。
3. `ZCODE_TELEMETRY_USER_ID_HASH` 等身份字段随模型请求头上行（provider 请求头伴随流量），与模型 API 同通道，无法单独关闭——定性为业务伴随元数据。
4. 反哺素材（会话持久化 rollout/上下文压缩/插件加载优先级/workflow 调度）尚未展开读，本文只完成安全审计面。

## 七、与自家体系关系

- 后续 ZCode 黑盒问题（persist_failed/MCP 假超时/console 掉线）排查时，直接对照 `ZCodeProject/zcode/src/` 源码定位，不再盲猜。
- 自研 bin/ 总线与 memory 体系的工业级参考实现就位（Agent CLI 全源码），按需定点读。
