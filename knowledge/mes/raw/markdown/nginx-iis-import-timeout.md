---
title: nginx反代IIS导入超时假报错（数据已导入）
category: 部署运维
module: 通用
factory: 通用
tags: [nginx, IIS, proxy_read_timeout, 超时, 假报错, Excel导入, 长请求, 负载均衡]
updated: 2026-08-21
status: active
---
# nginx反代IIS导入超时假报错（数据已导入）

> 导入等长请求超过 nginx 默认 proxy_read_timeout(60s) 时，nginx 先返回错误页（"Faithfully yours, nginx"），但 IIS 后台继续执行把数据导完——「报错但数据已导入」不是代码错误；按业务键判重时重复导入不产生重复数据。

## 一、现象与判断

- 前端收到 nginx 错误页，但数据实际已完整入库（刷新页面可见）
- 报错页含 "nginx" 字样 → 客户端与 IIS 之间存在 nginx 反代层（网关/负载均衡）
- IIS/ASP.NET 侧的 `executionTimeout`（web.config httpRuntime）是另一套独立超时，**改 IIS 拦不住 nginx 自己断连**

## 二、修复优先级

1. **首选：把请求做快**（治本）——批量写库、循环前预加载代替逐行查询，常规文件秒级完成，60s 窗口内根本触发不到
2. **需留余量**时改 nginx 站点配置的 location 块：

```nginx
location / {
    proxy_read_timeout 300s;   # 等后端响应超时，关键项
    proxy_send_timeout 300s;   # 上传大文件同样放宽
}
```

改完 `nginx -t` 校验语法，`nginx -s reload` 热加载。若 nginx 由其他团队管，把该段交给运维。

3. **上传大文件**还要配 `client_max_body_size 500m;`——nginx 默认 1MB 请求体，不放开大文件在 nginx 层就被 413 拒绝，根本到不了 IIS。

## 三、超时/大小链路核对清单（三层各自独立）

| 层 | 配置 | 说明 |
|---|---|---|
| nginx | client_max_body_size / proxy_*_timeout | 请求体上限、代理读写超时 |
| IIS | requestLimits maxAllowedContentLength（字节） | 上传大小 |
| ASP.NET | httpRuntime maxRequestLength(KB) / executionTimeout(秒) | 上传大小、请求执行时长 |

排查长请求假报错时三层对照检查，只改一层经常无效。EquipManage 现网 httpRuntime 已是 executionTimeout=1800、maxRequestLength=1048576（1GB），IIS 侧无需再动。

相关：[[bus-measure-import-full-solution]] [[measure-attachment-full-solution]]（勘误 2026-08-28：原链接 `upload-size-500mb` 目标不存在，改指此文第七节——上传大小 500MB 三层配置）
