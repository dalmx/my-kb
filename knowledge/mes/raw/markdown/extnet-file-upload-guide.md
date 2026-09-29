---
title: Ext.NET 文件上传完整方案（多文件上传 + FTP + 大小限制配置）
category: 技术-.NET
module: Ext.NET
factory: 通用
tags: [Ext.NET, 文件上传, FileUploadField, FTP, FluentFTP, 多文件, maxRequestLength, maxAllowedContentLength, Web.config, 踩坑]
status: active
source: https://www.cnblogs.com/xielong/p/10845675.html
updated: 2026-08-29
---
# Ext.NET 文件上传完整方案（多文件上传 + FTP + 大小限制配置）

> 合并说明： 本文由多文件上传实现与上传大小限制配置两篇同题文档合并而成，涵盖前端控件、后端FTP上传、以及 web.config 大小限制的完整方案。

---

## 一、多文件上传实现（Ext.NET FileUploadField + FluentFTP）

## 二、概述

在 Quality 项目中实现多文件上传功能，使用 Ext.NET 的 FileUploadField 控件配合 FluentFTP 上传到 FTP 服务器，并保存文件记录到数据库。

## 三、前端实现

### 2.1 文件上传控件配置

Ext.NET 的 FileUploadField 不直接支持 `Multiple` 属性，需要通过 `AfterRender` 事件为底层 input 元素添加 `multiple` 属性：

```aspx
<ext:FileUploadField ID="FileUploadField1" runat="server"
    ButtonText="选择PDF文件" FieldLabel="附件" LabelAlign="Right" LabelWidth="60"
    Width="460" IconCls="fa fa-folder-open" AllowBlank="false"
    ButtonOnly="false" Accept=".pdf">
    <Listeners>
        <AfterRender Handler="this.button.fileInputEl.dom.setAttribute('multiple', 'multiple');" />
        <Change Handler="validateFiles(this);" />
    </Listeners>
</ext:FileUploadField>
```

### 2.2 文件选择验证与显示

```javascript
var validateFiles = function(uploadField) {
    var files = uploadField.button.fileInputEl.dom.files;
    if (files && files.length > 0) {
        var names = [];
        for (var i = 0; i < files.length; i++) {
            var name = files[i].name;
            if (name.split('.').pop().toLowerCase() !== 'pdf') {
                Ext.Msg.alert('提示', '请选择PDF格式文件');
                uploadField.reset();
                return;
            }
            names.push(name);
        }
        Ext.get('divFileName').dom.innerHTML = '已选择 ' + files.length + ' 个文件：<br/>' + names.join('<br/>');
        App.ctnFileName.show();
    } else {
        App.ctnFileName.hide();
    }
};
```

### 2.3 文件名显示容器

使用原生 div 实现自动换行：

```aspx
<ext:Container ID="ctnFileName" runat="server" Hidden="true">
    <Content>
        <div id="divFileName" style="color:#28a745;font-size:13px;white-space:normal;word-break:break-all;line-height:1.6;"></div>
    </Content>
</ext:Container>
```

### 2.4 完整上传窗口示例

```aspx
<ext:Window ID="WinUpLoad" runat="server" Title="上传附件"
    Width="520" Height="250" Hidden="true" Modal="true" IconCls="fa fa-upload"
    BodyPadding="20" Layout="VBoxLayout">
    <Defaults>
        <ext:Parameter Name="margin" Value="0 0 12 0" Mode="Value" />
    </Defaults>
    <Items>
        <ext:Container runat="server" Layout="HBoxLayout">
            <Items>
                <ext:Component runat="server" Html="<i class='fa fa-file-pdf-o color-danger' style='font-size:18px;margin-right:10px;'></i>" Width="35" />
                <ext:Component runat="server" Html="<span style='color:#666;font-size:13px;'>请选择PDF格式文件上传（支持多选）</span>" Flex="1" />
            </Items>
        </ext:Container>
        <ext:FileUploadField ID="FileUploadField1" runat="server"
            ButtonText="选择PDF文件" FieldLabel="附件" LabelAlign="Right" LabelWidth="60"
            Width="460" IconCls="fa fa-folder-open" AllowBlank="false"
            ButtonOnly="false" Accept=".pdf">
            <Listeners>
                <AfterRender Handler="this.button.fileInputEl.dom.setAttribute('multiple', 'multiple');" />
                <Change Handler="var files=this.button.fileInputEl.dom.files; if(files&amp;&amp;files.length>0){var names=[]; for(var i=0;i<files.length;i++){var name=files[i].name; if(name.split('.').pop().toLowerCase()!=='pdf'){Ext.Msg.alert('提示','请选择PDF格式文件');this.reset();return;} names.push(name);} Ext.get('divFileName').dom.innerHTML='已选择 '+files.length+' 个文件：<br/>'+names.join('<br/>');App.ctnFileName.show();}else{App.ctnFileName.hide();}" />
            </Listeners>
        </ext:FileUploadField>
        <ext:Container ID="ctnFileName" runat="server" Hidden="true">
            <Content>
                <div id="divFileName" style="color:#28a745;font-size:13px;white-space:normal;word-break:break-all;line-height:1.6;"></div>
            </Content>
        </ext:Container>
        <ext:ProgressBar ID="Progress1" runat="server" Hidden="true" />
    </Items>
    <Buttons>
        <ext:Button ID="btnUploadSave" runat="server" Text="上传附件" IconCls="fa fa-upload" FormBind="true">
            <DirectEvents>
                <Click OnEvent="UploadClick" Before="App.Progress1.show();App.Progress1.updateProgress(0, '正在上传...');" />
            </DirectEvents>
        </ext:Button>
        <ext:Button ID="btnUploadClose" runat="server" Text="关闭" IconCls="fa fa-times">
            <Listeners>
                <Click Handler="#{WinUpLoad}.hide();#{FileUploadField1}.reset();#{ctnFileName}.hide();#{Progress1}.hide();" />
            </Listeners>
        </ext:Button>
    </Buttons>
</ext:Window>
```

## 四、后台实现（多文件上传处理方法）

```csharp
/// <summary>
/// 上传附件（支持多文件）
/// </summary>
public void UploadClick(object sender, DirectEventArgs e)
{
    try
    {
        // 1. 解析FTP配置
        string ftp = ConfigurationManager.AppSettings["ftp"];
        if (string.IsNullOrEmpty(ftp))
        {
            X.MessageBox.Show(new MessageBoxConfig()
            {
                Title = "错误",
                Message = "未配置FTP，格式user:password@ip",
                Buttons = MessageBox.Button.OK,
                Icon = MessageBox.Icon.ERROR
            });
            return;
        }

        int userIndex = ftp.IndexOf(":");
        int passwordIndex = ftp.LastIndexOf("@");
        string ftpuser = ftp.Substring(0, userIndex);
        string password = ftp.Substring(userIndex + 1, passwordIndex - userIndex - 1);
        string ftpipandport = ftp.Substring(passwordIndex + 1);
        string ftpip = ftpipandport.Split(':')[0];
        int ftpport = ftpipandport.Contains(":") ? int.Parse(ftpipandport.Split(':')[1]) : 0;

        // 2. 获取上传文件集合（多文件）
        var files = Request.Files;
        if (files == null || files.Count == 0)
        {
            X.MessageBox.Show(new MessageBoxConfig()
            {
                Title = "错误",
                Message = "请选择要上传的文件",
                Buttons = MessageBox.Button.OK,
                Icon = MessageBox.Icon.WARNING
            });
            return;
        }

        var billNo = hidden_bill_no.Value.ToString();
        int successCount = 0;
        int failCount = 0;

        // 3. 遍历上传每个文件
        using (FtpClient client = new FtpClient(ftpip, ftpuser, password, ftpport))
        {
            client.AutoConnect();
            string remoteDir = "/TyreCheckFiles/" + billNo + "/";
            if (!client.DirectoryExists(remoteDir))
            {
                client.CreateDirectory(remoteDir, true);
            }

            for (int i = 0; i < files.Count; i++)
            {
                var postedFile = files[i];
                if (postedFile == null || string.IsNullOrEmpty(postedFile.FileName))
                    continue;

                string fileName = Path.GetFileName(postedFile.FileName);
                string ext = Path.GetExtension(fileName).ToLower();
                if (ext != ".pdf")
                {
                    failCount++;
                    continue;
                }

                Stream fileStream = postedFile.InputStream;
                fileStream.Position = 0;
                var remotePath = "/TyreCheckFiles/" + billNo + "/" + fileName;

                FtpStatus status = client.UploadStream(fileStream, remotePath, FtpRemoteExists.Overwrite, true);
                if (status == FtpStatus.Success)
                {
                    var existFiles = fileManager.GetEntityList(new FqmTireCommissionTestItemsBillFile
                    {
                        BillNo = billNo,
                        FileName = fileName,
                        DeleteFlag = 0
                    });

                    if (existFiles == null || existFiles.Count == 0)
                    {
                        FqmTireCommissionTestItemsBillFile file = new FqmTireCommissionTestItemsBillFile
                        {
                            BillNo = billNo,
                            FileName = fileName,
                            FilePath = "/TyreCheckFiles/" + billNo + "/" + fileName,
                            FileDesc = fileName,
                            DeleteFlag = 0,
                            RecordUserId = Data.User.UserBarcode.ToString(),
                            RecordTime = DateTime.Now
                        };
                        fileManager.Insert(file);
                    }
                    successCount++;
                }
                else
                {
                    failCount++;
                }
            }
            client.Disconnect();
        }

        // 4. 显示结果
        string resultMsg = "";
        if (successCount > 0 && failCount == 0)
            resultMsg = string.Format("成功上传 {0} 个文件", successCount);
        else if (successCount > 0 && failCount > 0)
            resultMsg = string.Format("成功上传 {0} 个文件，{1} 个失败", successCount, failCount);
        else
            resultMsg = "上传失败";
        this.Progress1.UpdateProgress(1, resultMsg);
    }
    catch (Exception ex)
    {
        this.Progress1.UpdateProgress(1, "上传失败：" + ex.Message);
    }
}
```

## 五、关键点说明

| 要点 | 实现 |
|------|------|
| 多选 | `this.button.fileInputEl.dom.setAttribute('multiple', 'multiple')`（AfterRender） |
| 获取多文件 | 后台 `Request.Files` 集合遍历 |
| 前端格式验证 | `name.split('.').pop().toLowerCase() !== 'pdf'` |
| 后端格式验证 | `Path.GetExtension(fileName).ToLower() != ".pdf"` |
| FTP 上传 | FluentFTP `client.UploadStream(fileStream, remotePath, FtpRemoteExists.Overwrite, true)` |
| 文件名换行 | 原生 div + `white-space:normal;word-break:break-all` + `names.join('<br/>')` |

## 六、依赖

- Ext.NET 控件库
- FluentFTP NuGet 包
- 数据库表存储文件记录

---

## 七、上传文件大小限制配置（web.config）

## 八、问题

上传文件时抛出异常：

```text
HttpException (0x80004005): 超过了最大请求长度。
```

> 场景：表单提交上传文件，后端通过 `Request.Files` 获取文件。文件超过框架默认限制时触发。

## 九、根因

ASP.NET 对请求体大小有**两层限制**，需同时放开：

| 限制层 | 配置节 | 默认值 | 管辖范围 |
|--------|--------|--------|----------|
| ASP.NET 运行时 | `<httpRuntime maxRequestLength="..."/>` | **4096 KB（4MB）** | 整个请求体（含表单+文件） |
| IIS 请求过滤 | `<requestLimits maxAllowedContentLength="..."/>` | **30000000 字节（~28.6MB）** | IIS 层请求体内容长度 |

- 先到哪个限制就报哪个错。通常 4MB 的 `maxRequestLength` 先触发。
- **两层都要改**，只改一层仍会被另一层挡住。

## 十、配置方法

### 8.1 修改 httpRuntime（ASP.NET 层）

```xml
<configuration>
  <system.web>
    <!-- 单位：KB。此处设为 200MB -->
    <httpRuntime maxRequestLength="204800" executionTimeout="600" />
  </system.web>
</configuration>
```

### 8.2 修改 requestLimits（IIS 层）

```xml
<configuration>
  <system.webServer>
    <security>
      <requestFiltering>
        <!-- 单位：字节。此处设为 200MB = 200*1024*1024 -->
        <requestLimits maxAllowedContentLength="209715200" />
      </requestFiltering>
    </security>
  </system.webServer>
</configuration>
```

⚠️ 单位不同：`maxRequestLength` 是 **KB**，`maxAllowedContentLength` 是**字节**。

## 十一、单位换算速查（以 200MB 为例）

| 配置项 | 单位 | 值 |
|--------|------|----|
| `maxRequestLength` | KB | `204800`（200 × 1024） |
| `maxAllowedContentLength` | 字节 | `209715200`（200 × 1024 × 1024） |

## 十二、注意

- 改完 web.config 后 IIS 站点自动重启，无需手动重启。
- 若用了反向代理（如 Nginx），还需同步调整 `client_max_body_size`。
- `executionTimeout` 仅在 `compilation debug="false"` 时生效。
- 大文件上传还应考虑：前端分片、服务端流式读取、超时与内存占用。

## 十三、关联

- BOM 附件上传/删除/日志（业务实现）：见 `bom-report-attachment.md`
- PowerShell 写 .cs 编译踩坑：见 `powershell-write-cs-cs1056-pitfall.md`
- Ext.NET 事件机制（DirectEvents 上传按钮）：见 `extnet-event-mechanisms.md`
