---
title: Ext.NET 多文件上传实战踩坑与修正（Hidden Window 内）
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, 文件上传, FileUploadField, FTP, 踩坑, ProgressBar, 省略号, Hidden Window, 多选]
status: active
related: [multi-file-upload.md, extnet-file-upload-guide.md, bom-report-attachment.md, tyrecheck-attachment-crud.md]
updated: 2026-08-29
---
# Ext.NET 多文件上传实战踩坑与修正（Hidden Window 内）

> Hidden Window 内 FileUploadField 多选失效等 6 坑实战修正：multiple 属性要放 Window 的 Show 事件里设（延迟渲染导致 AfterRender 时序错位）；同步上传的进度条只能前端模拟跳动（上限 95% 等后端，勿用 EventMask——全屏遮罩会盖住弹窗内进度条）；VBoxLayout 下 ProgressBar / Container 须显式 Width，否则宽度塌缩、省略号失效；文件名列表 max-height 内部滚动 + ellipsis 截断 + HTML 转义防注入；成功反馈由后端 X.MessageBox + Notify 双提示并用 X.Js.Call 调前端函数关弹窗。

## 一、适用场景

在 `Hidden="true"` 的 `ext:Window` 弹窗内放 `FileUploadField` 实现多文件上传。基础写法见 `extnet-file-upload-guide.md`，但**基础写法在 Hidden Window 内多处不生效**。本文记录在 TyreCheckQueryNew（Quality 子系统）实际验证通过的 6 个坑及修正方案。

## 二、坑1：`AfterRender` 在 Hidden Window 内不生效 → 多选失效

**现象**：`FileUploadField` 放在 `Hidden="true"` 的 Window 里，`AfterRender` 里 `this.button.fileInputEl.dom.setAttribute('multiple','multiple')` 无效，选文件时仍只能单选。

**根因**：Ext.NET 对 Hidden Window 会**延迟渲染（lazy render）**内部控件，`AfterRender` 触发时底层 `<input type=file>` 元素可能尚未创建/就绪，`fileInputEl.dom` 为 null 或时序错位。

**修正**：把设置 multiple 的逻辑放到 **Window 的 `<Show>` 事件**里（每次打开窗口时底层 input 一定已渲染），并加 null 防护：

```javascript
var ensureMultiple = function (fuf) {
    try {
        if (fuf && fuf.button && fuf.button.fileInputEl && fuf.button.fileInputEl.dom) {
            fuf.button.fileInputEl.dom.setAttribute('multiple', 'multiple');
        }
    } catch (e) { }
}
```

```aspx
<ext:Window ID="WinUpLoad" runat="server" Hidden="true" ...>
    <Listeners>
        <Show Handler="ensureMultiple(App.FileUploadField1);" />
    </Listeners>
    ...
</ext:Window>
```

> FileUploadField 自身的 `AfterRender` 监听可保留作为兜底（双保险），但真正生效的是 Window.Show。

## 三、坑2：进度条不跳动 → HTTP 同步上传无法回推

**现象**：`ProgressBar` 上传过程中始终停在初始文案，不递增。

**根因**：`UploadClick` 是同步阻塞的 HTTP 请求，期间无法回推进度到浏览器。后端 `Progress.UpdateProgress()` 只能在请求返回时更新一次。

**修正**：**前端模拟跳动**（纯客户端动画，无并发风险，无需后端轮询）。

```javascript
var progressTimer1 = null;
// 启动：显示进度条，setInterval 每 200ms 递增，但永远不超过 95%（留余量等后端完成）
var startProgress = function (progressBar, step) {
    if (!progressBar) return;
    progressBar.show();
    progressBar.updateProgress(0, '正在上传...');
    var pct = 0;
    var timer = setInterval(function () {
        if (pct < 0.95) {
            var inc = step * (1 - pct);  // 越接近 95% 增量越小，模拟"越往后越慢"
            pct = Math.min(0.95, pct + inc);
            progressBar.updateProgress(pct, '正在上传... ' + Math.round(pct * 100) + '%');
        }
    }, 200);
    return timer;
};
// 完成：停定时器 + 推到 100%
var finishProgress = function (timer, progressBar, text) {
    if (timer != null) { clearInterval(timer); }
    if (progressBar) { progressBar.updateProgress(1, text || '上传完成'); }
};
```

DirectEvents 三段式（Before 启动 / Success 推满 / Failure 报错）：

```aspx
<ext:Button ID="btnUploadSave" runat="server" Text="上传附件" FormBind="true">
    <DirectEvents>
        <Click OnEvent="UploadClick"
            Before="progressTimer1 = startProgress(App.Progress1, 0.05);"
            Success="finishProgress(progressTimer1, App.Progress1, '上传完成');"
            Failure="finishProgress(progressTimer1, App.Progress1, '上传失败');" />
    </DirectEvents>
</ext:Button>
```

> ⚠️ 不要用 `<EventMask>`（全屏遮罩 z-index 高于 Window，会把弹窗内 ProgressBar 盖住，导致"看不到进度条"）。

## 四、坑3：进度条又小又窄 → VBoxLayout 下需显式设宽高

**现象**：`ext:ProgressBar` 在 VBoxLayout（垂直布局）里显示成一条窄线。

**根因**：VBoxLayout 下 ProgressBar 没设 `Width`/`Flex`，宽度自动塌缩。

**修正**：显式设 `Width`（与 FileUploadField 一致，弹窗宽 520 - BodyPadding 40 ≈ 460）和 `Height`：

```aspx
<ext:ProgressBar ID="Progress1" runat="server" Hidden="true" Width="460" Height="28" />
```

## 五、坑4：多选文件列表撑高弹窗 → 进度条被挤出可视区

**现象**：选了很多文件，文件名列表把进度条挤到弹窗固定高度之外，看不到进度条。

**根因**：Window 固定 `Height` + VBoxLayout 不滚动 + 文件名列表高度可变（随文件数增长）。

**修正**：给文件名列表 div 设 `max-height` + `overflow-y:auto`，列表在自身内部滚动，进度条固定在下方：

```aspx
<div id="divFileName" style="color:#28a745;font-size:13px;line-height:1.6;max-height:90px;overflow-y:auto;overflow-x:hidden;"></div>
```

## 六、坑5：文件名过长换行 → 用省略号截断

**现象**：长文件名自动换行，列表凌乱。

**根因**：原来 div 用 `white-space:normal;word-break:break-all` 强制换行。

**修正**：每个文件名用单独的 div 包裹，配 ellipsis 样式，`title` 悬停看全名：

```css
.file-name-ellipsis {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
```

**关键**：省略号生效要求**外层容器有明确宽度**。Ext.NET `Container` 在 VBoxLayout 下若不设 `Width`，宽度不确定，`overflow:hidden` + `text-overflow:ellipsis` 不生效。必须给 Container 设 `Width="460"`：

```aspx
<ext:Container ID="ctnFileName" runat="server" Hidden="true" Width="460">
    <Content>
        <div id="divFileName" style="..."></div>
    </Content>
</ext:Container>
```

JS 生成列表 HTML（含 HTML 转义，防文件名含 `< > & "` 等特殊字符破坏 HTML）：

```javascript
var escapeHtml = function (s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
};
var buildFileListHtml = function (files) {
    var names = [];
    for (var i = 0; i < files.length; i++) {
        var safe = escapeHtml(files[i].name);
        names.push('<div class="file-name-ellipsis" title="' + safe + '">' + safe + '</div>');
    }
    return '已选择 ' + files.length + ' 个文件：' + names.join('');
};
```

## 七、坑6：上传成功无反馈 → 后端需主动弹窗

**现象**：文件上传成功了，但用户看不到任何提示（进度条不醒目、弹窗不关闭）。

**根因**：后端只调 `Progress.UpdateProgress()` 更新进度条文案，没弹窗、没关弹窗。

**修正**：后端成功/失败分支用 `X.MessageBox.Show` + `X.Msg.Notify` 双重提示，成功后用 `X.Js.Call("前端函数")` 关弹窗（服务端决定是否关，可区分全成功/部分失败）：

```csharp
private void NotifyResult(string msg, bool isError) {
    X.Msg.Notify(new NotificationConfig {
        Title = isError ? "上传结果" : "上传成功",
        Html = msg,
        Icon = isError ? Icon.Error : Icon.Information
    }).Show();
    X.MessageBox.Show(new MessageBoxConfig {
        Title = isError ? "上传失败" : "上传成功",
        Message = msg,
        Buttons = MessageBox.Button.OK,
        Icon = isError ? MessageBox.Icon.ERROR : MessageBox.Icon.INFO
    });
}
// 全部成功后服务端调前端函数关弹窗：
X.Js.Call("closeWinUpLoad");
```

前端 `closeWinUpLoad`：关弹窗 + reset FileUploadField + 隐藏文件名/进度条 + 刷新列表。

## 八、弹窗尺寸参考（验证可用）

| 弹窗 | Width | Height | 内容构成 |
|------|-------|--------|---------|
| 单据上传 WinUpLoad | 520 | 340 | 提示行 + FileUploadField + 文件名列表(max90) + 进度条(28) + 按钮 |
| 批量上传 WinBatchUpLoad | 520 | 360 | 比单据多一行说明，略高 |

## 九、关联

- 基础多文件上传写法（Request.Files / FluentFTP UploadStream）：`extnet-file-upload-guide.md`
- 附件删除软删除方案（FtpFileView 数据源改 DB + DeleteFlag）：`tyrecheck-attachment-crud.md`
- BomReport 附件上传/删除/日志（同类参考，但 BomReport 是单文件上传）：`bom-report-attachment.md`
- Ext.NET FileUploadField 控件属性：`extnet-file-upload-guide.md`
