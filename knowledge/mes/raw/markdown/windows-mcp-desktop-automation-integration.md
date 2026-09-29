---
status: active
title: windows-mcp 桌面自动化 MCP 接入
category: 部署运维
module: 通用
tags: [windows-mcp, MCP, 桌面自动化, Computer Use, UIA, DeskBox, 窗口管理, Python 3.14, F盘Python, ZCode配置, GitBash传参坑]
updated: 2026-09-26
---

# windows-mcp 桌面自动化 MCP 接入

> CursorTouch/Windows-MCP：让 MCP 客户端直接操控 Windows 桌面（UIA 无视觉依赖、坐标交互、20 个工具含窗口感知/键鼠模拟/剪贴板/进程/注册表）。2026-09-26 装入 F:\Python314 并接入 ZCode，Snapshot 实测能拿到窗口句柄/Z序/状态，可作 DeskBox（F:\aiobject）的外部感知与验证手段。

## 一、项目定位与能力

- 仓库：https://github.com/CursorTouch/Windows-MCP（MIT，Claude Desktop 扩展 200 万+ 用户，PyPI 包名 `windows-mcp`）
- 技术路线：**UI Automation（a11y 树）+ 坐标交互**，不依赖视觉模型，任何 LLM 可用；动作延迟 0.2~0.5s；截屏后端 dxcam→mss→pillow 自动降级
- 20 个工具：交互（Click/Type/Scroll/Move/Shortcut/Wait/WaitFor/MultiSelect/MultiEdit）、感知（Screenshot/Snapshot/DisplayInventory）、系统（App/PowerShell/FileSystem/Clipboard/Process/Notification/Registry/Scrape）
- Snapshot 输出：光标位置、虚拟桌面、焦点窗口、**打开窗口清单（名称/深度=Z序/状态 Maximized|Minimized|Normal/宽高/句柄 Handle）**、UIA 树（含可点击元素坐标）
- 官方限制：不能选中段落内特定文字段；Type 为整段输入不适合 IDE 写码；中文系统须禁用 App 工具（按开始菜单名启动依赖英文系统）

## 二、本机安装实录（2026-09-26）

- Python 3.14.7（windows-mcp 0.8.5 实测要求 ≥3.13，最新 0.8.6 已要 ≥3.14）→ 用户级安装到 `F:\Python314`（InstallAllUsers=0，不动 PATH/launcher/文件关联）
- 安装包装自 **USTC python 镜像**（12 秒拉完 33MB，2.7MB/s）：`https://mirrors.ustc.edu.cn/python/3.14.7/python-3.14.7-amd64.exe`
- 静默安装**必须走 .ps1 脚本文件**（见第四节坑 1），包本体 pip 装：`F:/Python314/python.exe -m pip install -i https://mirrors.huaweicloud.com/repository/pypi/simple/ windows-mcp`
- ensurepip 补 pip（静默安装后 No module named pip）：`python -m ensurepip --upgrade` → pip 26.2.1
- 入口：`F:\Python314\Scripts\windows-mcp.exe`，子命令 `serve`（stdio 默认；SSE/streamable-http 网络模式带 Bearer/IP白名单/TLS/OAuth2）
- 关键 serve 参数：`--tools`/`--exclude-tools`（逗号分隔，前者覆盖后者）、`--auth-key`、`--ip-allowlist`、`--config`（默认 ~/.windows-mcp/config.toml）
- 下载通道全程踩坑（uv 栈卡死/清华 403/带宽 180 倍差）已收拢到 **`machine-network-mirror-matrix.md`**（该文档为网络选源权威版）

## 三、ZCode 配置（2026-09-26 生效待重启验证）

```json
"windows": {
  "type": "stdio",
  "command": "F:/Python314/Scripts/windows-mcp.exe",
  "args": ["serve", "--exclude-tools", "App"],
  "env": {"ANONYMIZED_TELEMETRY": "false"}
}
```

- 备份：`ZCodeProject/windows-mcp/config-backup-20260926.json`
- App 工具按官方要求禁用（中文系统）；启动应用可用 PowerShell 工具 `Start-Process` 替代
- `ANONYMIZED_TELEMETRY=false` 关默认 PostHog 遥测
- 重启 ZCode 后新会话出现 `mcp__windows__*` 工具；连不上先查 `~/.zcode/cli/log/*.jsonl` 的 `mcp.server.failed`

## 四、安装坑（网络类已收拢，此处留本工具特有坑）

1. **Git Bash 行内传 Windows 安装器参数，反斜杠被吃**：`TargetDir=F:\\Python314` 到达安装器变成 `F:Python314`，弹"Could not access network location F:Python314"（与 schtasks `/参数`→`F:/Git/参数` 同根因，MSYS 参数转换）。**解法：一律写 .ps1/.cmd 脚本执行，脚本内用 $env:USERPROFILE 拼中文路径防编码**。
2. **静默安装后无 pip**：`/quiet` 组合参数装完 `No module named pip`，`python -m ensurepip --upgrade` 补齐（得 pip 26.2.1）。
3. 网络坑（uv 栈卡死、清华 403、直连 15KB/s vs 镜像 2.7MB/s、双栈诊断法）→ 全部收拢至 `machine-network-mirror-matrix.md`。

## 五、验证方法（防假阳性）

- `ZCodeProject/windows-mcp/smoke_stdio.py`：手动拼参数冒烟（initialize→tools/list→DisplayInventory）
- `ZCodeProject/windows-mcp/verify_config.py`：**从 config.json 读 windows 条目原样拉起**（与 ZCode 实际启动完全一致），断言 serverInfo、19 工具、App 已排除、Snapshot 返回真实桌面
- 实测结果：握手 8.1s（Python 冷启动），DisplayInventory 识别 2560x1440/DPI 120/缩放 125%；Snapshot 抓到焦点窗口 ZCode（Maximized 2578×1458 handle=134242）、Chrome/微信等窗口清单、UIA 树含任务栏按钮（action:click）

## 六、DeskBox（F:\aiobject）适配点

- Snapshot 的窗口清单字段（**Handle/Depth=Z序/Status**）可直接做 DeskBox 归置结果的**外部断言源**：脚本调 Snapshot → 校验目标窗口位置/状态，替代人工看屏幕
- DisplayInventory 的 DPI/缩放感知（实测 125%）可用于 DeskBox 坐标换算复核
- Click/Move/Shortcut 可模拟用户拖动窗口，验证吸附/堆叠行为（自动化回归）
- 后续可写独立验证脚本：Snapshot→找窗口→断言 bounds，接入 DeskBox 自测套件（34.x 版本 41 项自测之外的桌面级验收）

## 七、遗留项

- 重启 ZCode 后 `mcp__windows__*` 实际生效待验证（本轮仅 stdio 原样拉起验证）
- App 工具中文系统禁用为官方口径，若未来 0.9+ 支持中文开始菜单可解禁
- 0.8.6（最新）未上华为源，暂用 0.8.5；升级时重复第二节 pip 命令即可
- PowerShell/Registry 工具暴露面大（ZCode 自身 Bash 已有同等能力，未额外排除）；如需收紧加 `--exclude-tools "PowerShell,Registry"`

## 八、关联

- `machine-network-mirror-matrix.md` —— 本次安装触发的网络实测，坑已收拢
- `genoffice-ai-office-suite-evaluation.md` —— 同类工具接入先例（GenOffice MCP）
