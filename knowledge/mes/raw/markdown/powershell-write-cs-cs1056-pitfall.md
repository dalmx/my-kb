---
title: PowerShell 写入含中文 .cs 文件导致 CS1056 的踩坑与修复
category: 技术-.NET
module: 通用
factory: 通用
tags: [PowerShell, CS1056, 编码, UTF-8]
status: active
date: 2026-06-22
updated: 2026-08-29
---
# PowerShell 写入含中文 .cs 文件导致 CS1056 的踩坑与修复

> 根因：PowerShell 默认按 ANSI/GBK 读取 .ps1 脚本，UTF-8 脚本里的中文被误解码成西里尔字母（U+04xx 区间，长得像英文 O/a/e），经 here-string 进入 .cs 触发 CS1056。正解：脚本保持纯 ASCII、中文全部 \uXXXX 转义，运行时解码后用 UTF8Encoding(true) 带 BOM 写入；附逐字符码点诊断脚本与判别口诀（CS1056 报错行在注释/中文字符串 → 先查西里尔错位）。

## 一、现象

在 Windows 中文环境下，通过 PowerShell here-string（`@'...'@`）写入一个**包含中文注释/中文字符串**的 `.cs` 文件后，C# 编译器报：

```text
CS1056: 意外的字符"?"（或某个看不见的字符）
```

且报错行号指向的代码看起来完全正常（往往是注释行或中文字符串行）。

## 二、根因（关键）

PowerShell **默认按 ANSI（中文 Windows 上是 GBK / CP936）读取 `.ps1` 脚本本身**，而不是 UTF-8。当脚本文件里出现中文（注释、提示信息）时：

1. `Write` 工具把 .ps1 保存为 UTF-8；
2. PowerShell 用 GBK 去读这个 UTF-8 脚本 → 把某些 UTF-8 中文字节序列**误解码成西里尔字母**（Cyrillic，如 `ф` U+0444、`О` U+041E，长得像英文字母 O）；
3. 这些西里尔字符通过 here-string 进入写入的 .cs 文件；
4. C# 编译器遇到非 ASCII、非合法标识符字符 → `CS1056`。

**核心：问题出在 PowerShell 读取 .ps1 脚本的编码，而不是 here-string 本身或写入文件的编码。**

## 三、诊断方法（定位非法字符）

写一个纯 ASCII 的诊断脚本（递归用文件名定位，避免在脚本里写中文路径）：

```powershell
$candidates = Get-ChildItem -Path 'E:\' -Recurse -Filter 'SemisRawMaterial.aspx.cs' -ErrorAction SilentlyContinue
$target = ($candidates | Select-Object -First 1).FullName
$bytes = [System.IO.File]::ReadAllBytes($target)
$txt = [System.Text.Encoding]::UTF8.GetString($bytes, 3, $bytes.Length - 3)  # 跳过 BOM
$found = 0
for ($i = 0; $i -lt $txt.Length; $i++) {
    $c = [int]$txt[$i]
    # 允许: 制表符/换行/可打印ASCII(32-126)/CJK及全角(>=0x2000)
    $ok = ($c -eq 9) -or ($c -eq 10) -or ($c -eq 13) -or ($c -ge 32 -and $c -le 126) -or ($c -ge 0x2000)
    if (-not $ok) {
        $lineNo = (($txt.Substring(0, $i)) -split "`n").Length
        Write-Host ('SUSPECT line=' + $lineNo + ' U+' + ('{0:X4}' -f $c))
        $found++
    }
}
Write-Host ('SUSPECT_COUNT=' + $found)
```

输出示例（确认元凶）：
```text
SUSPECT line=32 U+0444     # Cyrillic ф
SUSPECT line=159 U+041E    # Cyrillic О（大写，像英文 O）
```

**判定标准**：U+0400~U+04FF 区间是西里尔字母，CJK 中文在 U+4E00 以上，全角符号在 U+2000 以上。落到西里尔区就是 here-string 编码错位。

## 四、修复方案（推荐：ASCII + \uXXXX 转义）

**让脚本文件只含 ASCII**，所有中文字符串用 `\uXXXX` Unicode 转义表示，脚本运行时再解码还原。这样 PowerShell 用任何编码读 .ps1 都不会出错。

```powershell
# 解码 \uXXXX 转义为真实 unicode
function Decode-U($s) {
    $rx = [System.Text.RegularExpressions.Regex]::new('\\u([0-9a-fA-F]{4})')
    $cb = [System.Text.RegularExpressions.MatchEvaluator]{
        param($m); [char]([Convert]::ToInt32($m.Groups[1].Value, 16))
    }
    $rx.Replace($s, $cb)
}

# 脚本里中文全部写成 \uXXXX（纯 ASCII）
$raw = @'
using Ext.Net;
...
public partial class Foo : Page {
    // \u6743\u9650\u5b9a\u4e49  (= "权限定义")
    X.Msg.Alert("\u63d0\u793a", "\u672a\u67e5\u8be2\u5230\u4fe1\u606f").Show();  // "提示"/"未查询到信息"
}
'@

$content = Decode-U $raw
$utf8Bom = New-Object System.Text.UTF8Encoding($true)
[System.IO.File]::WriteAllText($target, $content, $utf8Bom)
```

**常用中文 \uXXXX 对照**（这次踩坑用到的）：
| 中文 | 转义 |
|------|------|
| 提示 | `\u63d0\u793a` |
| 合计 | `\u5408\u8ba1` |
| 重量 | `\u91cd\u91cf` |
| 物料名称 | `\u7269\u6599\u540d\u79f0` |
| 未查询到信息 | `\u672a\u67e5\u8be2\u5230\u4fe1\u606f` |
| 半部件胶料_骨架材料信息 | `\u534a\u90e8\u4ef6\u80f6\u6599_\u9aa8\u67b6\u6750\u6599\u4fe1\u606f` |

中文转 \uXXXX 可用在线工具或 `python -c "print(''.join('\\u%04x'%ord(c) for c in '提示'))"`。

## 五、写入后验证

```powershell
$bytes = [System.IO.File]::ReadAllBytes($target)
$txt = [System.Text.Encoding]::UTF8.GetString($bytes, 3, $bytes.Length - 3)
$found = 0
for ($i = 0; $i -lt $txt.Length; $i++) {
    $c = [int]$txt[$i]
    $ok = ($c -eq 9) -or ($c -eq 10) -or ($c -eq 13) -or ($c -ge 32 -and $c -le 126) -or ($c -ge 0x2000)
    if (-not $ok) { $found++ }
}
Write-Host ('FINAL_BAD=' + $found)   # 应为 0
```

期望输出 `FINAL_BAD=0`，且验证中文关键串确实存在（用同样的 `Decode-U` 反查）。

## 六、其他可行方案（备选）

1. **保存 .ps1 时加 UTF-8 BOM**：PowerShell 5.1 见到 BOM 会按 UTF-8 读脚本。但 `Write` 工具写的 .ps1 不一定带 BOM，不可靠。
2. **用 `powershell -EncodedCommand <Base64>`**：把整段脚本 Base64 编码后传入，PowerShell 按 UTF-16LE 解码，彻底绕开文件编码问题。适合脚本较长时。
3. **避免用 PowerShell 写中文**：改用 .NET 的 `File.WriteAllText` 配合 `UTF8Encoding(true)`，从 C# 侧生成 —— 但本项目无此条件。
4. **bash + iconv**：用 `iconv` 把 GBK 转换，但 Windows bash 环境不稳定。

**结论：方案四（ASCII + \uXXXX 转义）最稳，跨 PowerShell 版本/编码都安全。**

## 七、判别口诀

- `.cs` 报 CS1056 且报错行是注释/中文字符串 → **优先怀疑西里尔字母错位**
- 看到疑似英文 O、a、e、c、p、x、y 但编译不过 → 用诊断脚本查码点，U+04xx 区间就是元凶
- 凡是要用 PowerShell 写含中文的源码文件 → **一律 \uXXXX 转义，别图省事**

## 八、相关踩坑

- UTF-8 无 BOM 文件：Read 工具偶尔误报，PowerShell 用 `[System.IO.File]::ReadAllText` + UTF8 编码可正常读，见 `monthly-pass-rate-trend.md` 的"文件编码处理"一节。
- 本次的 `SemisRawMaterial.aspx.cs` 原本是 **UTF-8 with BOM (EF BB BF)**，写入时也要保持 BOM，用 `UTF8Encoding($true)`。


## 九、补充关联（反向链接）

| 文档 | 说明 |
|------|------|
| `windows-reserved-name-and-cmd-chinese-path-pitfall.md` | Windows 保留名/中文路径踩坑 |
| `openpyxl-xlsx-compat-fix.md` | openpyxl xlsx 兼容性修复 |
