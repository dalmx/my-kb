---
title: SQL Server 表分区 + 数据库日志收缩（DBA 运维）
category: 部署运维
module: 通用
factory: 通用
tags: [SQL Server, 表分区, Partition Function, Partition Scheme, filegroup, SHRINKFILE, 日志收缩, DBA, 运维]
status: active
updated: 2026-08-29
---
# SQL Server 表分区 + 数据库日志收缩（DBA 运维）

> DBA 运维双主题：①表分区三步法（建文件组+文件 → 分区函数定边界 → 分区方案映射），附 TraceDB 按父条码年月前缀分区的完整项目脚本（RANGE RIGHT、Other 兜底分区）；②日志收缩标准流程（切 SIMPLE 恢复模式 → DBCC SHRINKFILE TRUNCATEONLY → 切回 FULL），含"为何必须先切简单模式"的原理解释。

## 一、表分区（Table Partitioning）

### 1.1 作用

将大表按某个字段（分区键）拆分到多个文件组（filegroup）/文件（.ndf），实现：
- 按月分区海量数据（如追溯数据），查询只扫相关分区提速。
- 分区切换（SWITCH）快速归档/清理旧数据。
- 各分区可放不同物理磁盘，均衡 IO。

### 1.2 三步建分区

**① 建文件组 + 文件** → **② 建分区函数（定义边界）** → **③ 建分区方案（映射分区→文件组）** → 建表时指定分区方案。

### 1.3 项目实例：TraceDB 按父条码（年月）分区

完整脚本（来自项目 TraceDB）：

```sql
-- ============ 第一步：建文件组 + 文件（以 2801~2812 即 2028年1~12月 为例）============
alter database [TraceDB] add filegroup MOLDING_RAWG_2801
alter database [TraceDB] add filegroup MOLDING_RAWG_2802
-- ... 每个月一个 filegroup ...

alter database [TraceDB] add file
(name=N'MOLDING_RAWF_2801', filename=N'D:\DB\MOLDING_RAWF_2801.ndf', size=5Mb, filegrowth=5mb)
to filegroup MOLDING_RAWG_2801
-- ... 每个月一个文件，指向对应 filegroup ...

-- 最后加一个 Other 文件组，承载分区函数边界外的数据
alter database TraceDB add filegroup MOLDING_RAWG_Other
alter database TraceDB add file
(name=N'MOLDING_RAWF_Other', filename=N'D:\DB\MOLDING_RAWF_Other.ndf', size=5Mb, filegrowth=5mb)
to filegroup MOLDING_RAWG_Other
GO

-- ============ 第二步：建分区函数（定义边界值）============
USE [TraceDB]
GO
CREATE PARTITION FUNCTION PF_PARENT_BARCODE AS RANGE RIGHT
FOR VALUES (
    N'240100000000', N'240200000000', N'240300000000', N'240400000000',
    N'240500000000', N'240600000000', N'240700000000', N'240800000000',
    -- ... 每个月一个边界值，格式 YYMM + 00000000（条码前缀）...
    N'281100000000', N'281200000000'
)
GO

-- ============ 第三步：建分区方案（边界 → 文件组映射）============
USE [TraceDB]
GO
CREATE PARTITION SCHEME [PS_PARENT_BARCODE] AS PARTITION [PF_PARENT_BARCODE]
TO (
    [MOLDING_RAWG_2401], [MOLDING_RAWG_2402], ..., [MOLDING_RAWG_2412],
    [MOLDING_RAWG_2501], ..., [MOLDING_RAWG_2512],
    [MOLDING_RAWG_2601], ..., [MOLDING_RAWG_2612],
    [MOLDING_RAWG_2701], ..., [MOLDING_RAWG_2712],
    [MOLDING_RAWG_2801], ..., [MOLDING_RAWG_2812],
    [MOLDING_RAWG_Other]    -- 最后一个对应超出最大边界的值
)
GO
```

### 1.4 关键概念

| 概念 | 说明 |
|------|------|
| **文件组 filegroup** | 逻辑容器，可包含多个文件 |
| **.ndf 文件** | 辅数据文件，实际存数据的物理文件 |
| **分区函数 Partition Function** | 定义分区边界值（按哪个值的范围切分） |
| **分区方案 Partition Scheme** | 把每个分区映射到对应文件组 |
| **RANGE RIGHT** | 边界值归入"右侧"分区（即 `>=` 边界值进下个分区） |
| **RANGE LEFT** | 边界值归入"左侧"分区 |

### 1.5 项目分区键设计

本例分区键是 `PARENT_BARCODE`（父条码），边界值用 `YYMM + 00000000` 形式：
- `240100000000` = 2024年1月条码的起点
- 条码字符串天然可排序，按年月前缀分区，每月一个分区。

### 1.6 建表时使用分区方案

```sql
CREATE TABLE trc_molding_semis (
    -- 字段定义...
    PARENT_BARCODE varchar(20) NOT NULL
)
ON [PS_PARENT_BARCODE](PARENT_BARCODE);   -- 指定分区方案和分区键列
```

### 1.7 注意

- **分区列必须是主键的一部分**（若表有主键）。
- 文件组/文件数量 = 分区数量 + 1（最后一个是 Other，承载超边界值）。
- RANGE RIGHT 是常用选择：边界值归入"大于等于它"的分区。
- 新增月份需：新建文件组+文件 → 修改分区方案 NEXT USED → 修改分区函数 SPLIT RANGE。

---

## 二、数据库日志收缩（DBCC SHRINKFILE）

### 2.1 场景

数据库日志文件（.ldf）膨胀过大，需收缩释放磁盘空间。

### 2.2 操作脚本（XTDQGDB 为数据库名）

```sql
USE [master]
GO
ALTER DATABASE XTDQGDB SET RECOVERY SIMPLE WITH NO_WAIT
GO
ALTER DATABASE XTDQGDB SET RECOVERY SIMPLE   -- 切到简单恢复模式
GO
USE XTDQGDB
GO
DBCC SHRINKFILE (N'XTDQGDB_log', 2, TRUNCATEONLY)   -- 收缩日志到 2MB
GO
USE [master]
GO
ALTER DATABASE XTDQGDB SET RECOVERY FULL WITH NO_WAIT
GO
ALTER DATABASE XTDQGDB SET RECOVERY FULL   -- 还原为完全恢复模式
GO
```

### 2.3 为什么要先切简单恢复模式

| 恢复模式 | 日志行为 | 能否直接收缩 |
|---------|---------|-------------|
| **FULL**（完全） | 保留所有事务日志，支持时间点恢复 | ❌ 活跃日志不能截断，收缩无效 |
| **SIMPLE**（简单） | 自动回收不再需要的日志空间 | ✅ 可收缩 |

> 完全模式下日志会持续增长（直到备份），直接 SHRINKFILE 通常无效。需先切简单模式 → 收缩 → 再切回完全模式。

### 2.4 步骤说明

1. 切到 master 库（操作恢复模式需在 master 上下文）
2. 设为 **SIMPLE** 恢复模式 → 日志可被截断
3. `DBCC SHRINKFILE(日志逻辑名, 目标大小MB, TRUNCATEONLY)` 收缩
4. 切回 **FULL** 恢复模式（恢复正常的日志链）

### 2.5 注意

- **`TRUNCATEONLY`**：只释放文件末尾未使用空间，不移动数据页，速度快但收缩有限。
- 不加 `TRUNCATEONLY`：会移动数据页来释放更多空间，慢但收缩彻底。
- **收缩后必须切回 FULL**，否则失去时间点恢复能力（生产库重要！）。
- **不宜频繁收缩**：日志反复增长+收缩会产生物理碎片。根治办法是合理设置日志初始大小+增量，并定期做日志备份（FULL 模式下备份会截断日志）。
- 日志文件的**逻辑名**（此处 `XTDQGDB_log`）可在 `sys.database_files` 查到，不一定是 `库名_log`。

## 三、关联

- SQL Server 性能排查：见 `sql-server-performance-troubleshooting.md`
- SQL Server Agent 运维：见 `sql-agent-cannot-start.md`
- APPLY / MERGE / 多维汇总等 SQL 语法：见 `sql-outer-apply-cross-apply.md` 等
