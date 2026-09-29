---
title: Playwright 浏览器自动化上手指南（Python 版，MES 页面冒烟回归）
category: 技术-前端
module: Playwright
tags: [Playwright, 浏览器自动化, 自动化测试, 冒烟测试, 回归测试, 网页测试, Ext.NET 页面测试, 截图存证, 抓取网页数据, Python, chromium, headless, 下载验证, pip镜像]
updated: 2026-09-26
status: active
---
# Playwright 浏览器自动化上手指南（Python 版，MES 页面冒烟回归）

> 用代码驱动真 Chromium 模拟人操作浏览器（打开/点击/输入/截图/下载），并断言结果。2026-09-20 上手并全链路验证通过，用于 MES「查询+导出」类页面的部署后冒烟回归，替代手工点页面验证。

## 一、是什么、跟相邻工具的关系

- **本质**：脚本写"打开页面→点查询→等表格出数据→点导出"，机器开真浏览器执行并检查结果；几秒完成一次手工回归。
- **vs ZCode browser-use 技能**：底层同源（都是 Playwright），但 browser-use 绑在 ZCode 会话里；本篇是独立 python 脚本，不依赖 AI、可无限重复执行，因此能挂进部署清单/CI。
- **vs curl/requests**：Playwright 是真浏览器，Ext.NET 这类全靠 JS 渲染的页面照样对付（curl 只拿原始 HTML，还踩过缺 Accept-Language 头 500 的坑，见 `mix-smallmaterial-weigh-query-refactor.md` 踩坑实录）。
- **典型用途**：回归冒烟（主用途）、部署后截图存证、从只有页面没有接口的老系统抓数、批量表单操作（有写副作用，慎用）。

## 二、环境事实（2026-09-20 实测安装）

| 项 | 事实 |
|---|---|
| Python | 3.11.9（`C:\Python311`） |
| 安装命令 | `python -m pip install playwright -i <镜像源>`（09-20 当时用清华源秒装；**镜像按 `machine-network-mirror-matrix.md` 用前速测现选**，清华 09-26 起已 403） |
| 浏览器 | `python -m playwright install chromium`，装在 `%LOCALAPPDATA%\ms-playwright`（标准缓存位置，不算乱塞 C 盘） |
| 本机样例 | `ZCodeProject\playwright-smoke\`：`demo_page.html`（模拟报表页靶）+ `smoke_test.py`（跑通示范）+ `mes_smoke_template.py`（真实 MES 改造模板，TODO 已标） |

## 三、安装坑：pip 默认源超时（网络坑已收拢）

09-20 原始记录：pip 默认 pypi.org 直连 5 分钟无输出（卡在下载），换清华镜像秒装。**但 09-26 实测清华 TUNA 已 403**——本机网络策略动态变化，旧口径"建议一次性配好全局镜像"作废。镜像选源、双栈速测、按进程差异等全部收拢到 **`machine-network-mirror-matrix.md`**（当前 pip 首选华为源）。

## 四、验证方法（防假阳性纪律）

冒烟 PASS 必须三层证据齐全，缺一不可：
1. **脚本断言**：元素计数（`expect(page.locator(...)).to_have_count(10)`）、导出文件存在且非空；
2. **截图存证**：`page.screenshot()` 存 `shots/`，人工过目页面真实渲染；
3. **产物核对**：导出的 CSV 打开看内容（表头+数据行+BOM），不是"文件存在就算过"。

退出码 0/1（`sys.exit(main())`），可直接做部署清单门禁。失败时 `except` 里强制截图（`FAIL.png`）留证据。

## 五、Ext.NET 页面选择器口径（Ext.NET 4.7 = Ext JS 6.2 classic）

- **GridPanel 行**：`.x-grid-item`（6.2 classic；旧版 4.x 才是 `.x-grid-row`）。
- **按钮**：优先服务端 ID `#btnQuery`（Ext.NET 默认客户端 ID=服务端 ID）；拿不到再 `text=查 询`——**注意全角空格**。
- **日期 DateField**：`fill()` 后值可能不触发框架 change，必要时补 `page.dispatch_event(sel, "change")`。
- **导出**：Ext.NET 导出多为流式下载，`with page.expect_download() as dl:` 捕获后 `dl.value.save_as()`。
- **等加载**：`page.wait_for_selector(".x-grid-item", timeout=15000)` + `wait_for_load_state("networkidle")`。

## 六、实战纪律（打真实 MES 页面必读）

1. **登录互踢**：同账号两处登录互踢会话（Mix 项目实测，见 `mix-smallmaterial-weigh-query-refactor.md`）——专用测试账号、错峰跑；模板用 `storage_state` 缓存登录态（`mes_login_state.json`），登一次后重跑免登录，少一层互踢风险。
2. **只读原则**：只对"查询+导出"类页面跑；保存/删除/审核按钮绝不碰。
3. **节流**：脚本内置 sleep，控制频率，别把冒烟跑成压测；生产库上尤甚。
4. **先 --headed 肉眼跑**：`python xxx.py --headed` 确认选择器都对，再转 headless 进部署清单。

## 七、遗留项

- `mes_smoke_template.py` **未在真实 MES 页面实测**（BASE_URL/账号/选择器全是 TODO 占位），首次使用需按目标项目逐项核。
- 登录页若有验证码，模板未覆盖（需人工介入或测试环境关验证码）。

## 八、关联

- `machine-network-mirror-matrix.md` —— 安装镜像选源权威版（三节收拢至此）
- `mix-smallmaterial-weigh-query-refactor.md` —— 登录互踢实录、curl 探页 Accept-Language 坑（本篇多条纪律的出处）
- `vue3-vite-getting-started.md` —— 同日上手的姊妹篇；Vue3 demo 的冒烟就用 Playwright 验的（两技术串联）
- `js-setinterval-settimeout.md` —— 同属技术-前端；页面内自动刷新的轻量方案（与本篇"外部驱动浏览器"互补）
- create-report 技能 —— 报表页规范（冒烟的测试对象）
