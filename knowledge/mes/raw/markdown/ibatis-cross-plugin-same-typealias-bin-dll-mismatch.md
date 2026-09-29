---
status: active
title: iBATIS 跨插件同名 typeAlias 覆盖与 bin DLL 错配（no Set member 报错实录）
category: 技术-.NET
module: iBATIS
tags: [iBATIS, typeAlias, 同名别名, 跨插件, bin DLL 错配, refresh, packages, SbeEquipMajorType, EquipDeptId, no Set member, 排障, MES通用]
updated: 2026-09-10
---

# iBATIS 跨插件同名 typeAlias 覆盖与 bin DLL 错配（no Set member 报错实录）

> 启动报 `There is no Set member named 'Xxx' in class 'Yyy'`，重新生成解决方案后消失。根因不是代码写错，而是"跨插件同名实体别名互相覆盖"叠加"网站 bin 里插件 Entity/Mapper DLL 新旧错配"两个机制耦合；重新生成只是靠别名覆盖顺序的巧合把错误掩盖，错配本身仍留在 bin 里。

## 一、报错现象

Mould（模具）子系统网站启动，登录页 `Plugins_Main_Login` 首次触发 `DbHelper.Ini` 构建 iBATIS 模型时报：

```text
ConfigurationException: In ResultMap (Wongoing.Main.Mapper.BasicMapper.SbeEquipMajorType.R_SbeEquipMajorType)
can't build the result property: EquipDeptId.
Cause: There is no Set member named 'EquipDeptId' in class 'SbeEquipMajorType'
```

重新生成（rebuild）解决方案后报错消失。报错 resultMap 名挂在 **Main 插件**名下，而排障的子系统是 Mould——症状与"自己改的代码"对不上号，是此坑的典型特征。

## 二、根因机制（两个条件叠加）

### 2.1 条件一：跨插件同名 typeAlias 覆盖

`dbVersion.config` 把多个插件注册到**同一个 dbName**（同一 DataMapper 实例、共享全局别名注册表）：

```xml
<DbMapper pluginName="Main" dbName="Default"/>
<DbMapper pluginName="Mould" dbName="Default"/>
```

Main 与 Mould 的 Mapper 各自嵌有一份 `BasicMapper/SbeEquipMajorType.xml`，注册了**同一个别名**、指向**各自 Entity 程序集**：

```xml
<!-- Wongoing.Main.Mapper.dll 内嵌 -->
<typeAlias alias="SbeEquipMajorType" type="Wongoing.Main.Entity.BasicEntity.SbeEquipMajorType, Wongoing.Main.Entity" />
<!-- Wongoing.Mould.Mapper.dll 内嵌 -->
<typeAlias alias="SbeEquipMajorType" type="Wongoing.Mould.Entity.BasicEntity.SbeEquipMajorType, Wongoing.Mould.Entity" />
```

同名别名后注册者覆盖先注册者（顺序=DbMapper 配置顺序）。因此 Main 的 resultMap 实际绑定的实体类**取决于当时 bin 里哪份 Mapper DLL 参与了注册**，而不是 Main 自己的实体——这是"张冠李戴"的来源。

### 2.2 条件二：bin 里插件 Entity/Mapper DLL 错配

网站 bin 里的 Main 插件 DLL（二进制验证，grep 属性名字符串）：

| DLL | 时间戳 | 含 EquipDeptId |
|---|---|---|
| bin/Wongoing.Main.Entity.dll | 2025-07-17 | ❌ 无 |
| bin/Wongoing.Main.Mapper.dll | 2025-10-15 | ✅ resultMap 有映射 |
| @packages/P.Main/Wongoing.Main.Entity.dll | 2025-08-01 | ✅ 有（但 .refresh 没刷进 bin） |

Main.Mapper（新，映射了 EquipDeptId）配 Main.Entity（旧，实体无该属性）→ 只要别名解析落到 Main.Entity 上必炸。

### 2.3 报错与"自愈"时序

- 报错时刻：AppDomain 加载的 Mapper 组合使别名 `SbeEquipMajorType` 落到 Main.Entity 旧版（典型：bin 里 Mould.Mapper.dll 为旧版/缺失，未注册覆盖别名）。
- rebuild 后：Mould 四件套重新编译刷入 bin，Mould.Mapper 注册的同名别名覆盖 Main → Main 的 resultMap 绑到 Mould.Entity.SbeEquipMajorType（有 EquipDeptId）→ 不报错。**修好的是巧合，不是错配**。

## 三、排障手法（不连库、纯文件层）

1. 报错 resultMap 的 namespace 指明是哪个插件的 Mapper（本例 `Wongoing.Main.Mapper` ≠ 排障子系统）。
2. 二进制 grep 验证 DLL 是否含属性/映射：.NET 元数据 #Strings 堆里属性名是明文，`python: needle.encode() in open(dll,'rb').read()` 即可，不用反编译。
3. 核对 `bin` 与 `@packages/<插件>` 的同名 DLL 时间戳是否成套；`.refresh` 文件（UTF-16 编码）指向 packages，但机制只在特定构建动作时刷新，不可依赖。
4. 查 `dbVersion.config` 确认哪些插件共享同一 dbName——共享即共享别名注册表，同名实体别名必冲突。

## 四、整改与预防

- **消除现存错配**：手动把 `@packages\P.Main\Wongoing.Main.Entity.dll`（含属性版）拷进网站 bin；服务器发布目录同样核对 Main 插件五件套 DLL 时间戳成套性。插件 DLL 必须整包同步，禁止单拷 Mapper 不拷 Entity。
- **同步纪律**：Main 插件实体加字段（如 EQUIP_DEPT_ID）后，引用了同名实体的子系统（Mould/Semi/Batch 等）必须同步本侧实体，否则 Main 名下 resultMap 报 no Set member，误导排查方向。
- **长期方案**：子系统 Mapper 的别名加插件前缀（如 `Mould_SbeEquipMajorType`）避免跨插件覆盖；动别名牵连 XML 全量引用，需按项目排期评估，新实体可直接按此规范。

## 五、适用范围

MES 项目族通用（Mould 实证，2026-09）：凡子系统引用 `@packages\P.Main` 且与 Main 挂同一 dbName 的，均存在同名别名覆盖机制；子系统自带与 Main 同名的实体（SbeEquipMajorType/SbeDevice 等基础数据实体是重灾区）。
