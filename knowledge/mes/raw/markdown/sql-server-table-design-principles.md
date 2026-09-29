---
category: 技术-数据库
factory: 通用
module: 通用
status: active
tags:
- Unicode
- NVARCHAR
- GBK
- 字符集
- 符号存储
- 判定符号
- ALTER
- 建表
title: SQL Server 建表设计原则与最佳实践
updated: '2026-09-19'
---

# SQL Server 建表设计原则与最佳实践

> 面向 MES 项目族（Ppt_/Ppm_/BPM_/CPP_ 系列业务表）的建表规范，综合 Microsoft Learn 官方文档、Brent Ozar 等业界最佳实践，并结合本系统排查案例（隐式类型转换、STRING_AGG 内存授予）整理。原则按"设计期 > 结构期 > 索引期 > 维护期"排列，新建表逐条对照。

## 一、整体设计原则

### 1.1 范式与反范式的平衡

- **设计阶段按第三范式（3NF）建模**：消除重复数据、避免更新异常；关联字段类型必须一致，类型不一致会导致隐式转换、索引失效（见 [[sql-server-performance-troubleshooting]] 中隐式转换案例）。
- **读多写少的统计/报表表适度反范式**：冗余低频变化的字段（如物料名称冗余进流水表），用空间换 JOIN。判断标准：字段变化频率极低（周/月级）且被高频查询冗余引用。

### 1.2 主键设计（代理键 vs 自然键）

| 场景 | 推荐 | 理由 |
|------|------|------|
| 业务唯一键稳定不变（如胎号） | 直接做主键 | 少一次代理键映射，JOIN 直接 |
| 业务键可能变、或键很长 | `IDENTITY(1,1)` 代理键 | 键窄、聚集索引小、页拆分开销小 |
| 跨库同步/分布式 | `bigint IDENTITY` 或雪花/雪花序列 | 避免 GUID 做聚集键 |

- **主键要窄**：主键列是每个非聚集索引的"行定位器"，`int`(4B) > `bigint`(8B) > `uniqueidentifier`(16B 且随机分布导致页拆分、索引碎片）。**避免随机 GUID（`NEWID()`）做主键**——尤其不能做聚集主键；确需 GUID（跨库同步等场景）时，用 `NEWSEQUENTIALID()` 生成有序 GUID、或主键设为非聚集（聚集键另选窄列）是可接受的正当方案，默认仍优先 `int IDENTITY`。（2026-08-28 勘误：原文"严禁 uniqueidentifier 做主键"过强，精确说法是避免随机 GUID 做聚集索引键。）
- **聚集索引不一定是主键**：高频范围查询（按时间、按流水号）的表，聚集索引放在时间/流水列上更合理；但**聚集键必须唯一**（否则 SQL Server 隐式追加 uniquifier，每行多 4 字节）。

### 1.3 聚集索引的选择

- 流水类表（记录/履历）：**聚集在时间列** `record_time`——按时间顺序插入无页拆分，时间范围查询天然顺序 IO。
- 主档类表（主数据）：聚集在主键（自然键或代理键均可）。
- 严禁无聚集索引的堆表长期运行（除非临时中转表）——堆表碎片不可控、行定位器是 RID（每次移动都要更新所有非聚集索引）。

## 二、字段类型设计

### 2.1 类型选型速查（本系统常用）

| 业务场景 | 推荐类型 | 避免 | 说明 |
|---------|---------|------|------|
| 编码/状态码（Mkind_code、DeleteFlag 类） | `char(n)` | 用数字存状态还配 varchar | 定长、无隐式转换；状态码语义靠 CHECK 约束 |
| 业务编码（胎号、条码、批号） | `varchar(n)` | `nvarchar` | 无中文需求一律 varchar，省一半空间 |
| 名称/文本 | `varchar(n)` 留 20% 余量 | `varchar(max)` 滥用 | max 类型不能做索引键、统计信息弱 |
| 金额/重量/长度 | `decimal(18,4)` / `decimal(18,2)` | **float/real** | float 二进制存储有精度误差，会算错账 |
| 日期时间 | `datetime2(3)` / `date` | `varchar` 存日期、`datetime` | datetime2 精度更细、范围更大；datetime 只精确到 3ms 且 1753 年下限 |
| 计数/ID | `int` | `bigint` 滥用 | 表行数 < 21 亿时 int 足够 |
| 布尔 | `bit` | `char(1)` Y/N | bit 8 个共享 1 字节 |
| 大量文本（配方 JSON、备注大文本） | `varchar(max)` 但单独放表/列 | 主表堆 max 列 | 行溢出会拖慢全表扫描 |

### 2.2 类型设计核心原则

1. **能用定长用定长**：`char` 行存储紧凑（无长度前缀），且避免可变长隐式转换（排查案例中 `CONVERT_IMPLICIT varchar(12)` 就是类型不匹配产物）。
2. **能窄则窄**：字段越窄 → 数据页塞越多行 → 扫描 IO 越小 → 索引越小。
3. **NULL 决策果断**：能 NOT NULL 就 NOT NULL（NULL 需要位图开销，索引与统计信息处理更麻烦）；确实可空则补 `DEFAULT`，避免应用到处判空。
4. **同一字段全库同型同长**：`Mater_code` 在 A 表 `varchar(20)`、B 表 `varchar(30)`，JOIN 必然隐式转换 + 长度转换（性能与正确性双输）。

## 三、约束设计

| 约束 | 为什么必须有 |
|------|-------------|
| `PRIMARY KEY` | 唯一性 + 行定位，每表必设 |
| `NOT NULL` | 配合 PK 形成完整实体，减少应用判空 |
| `DEFAULT` | 记录时间 `DEFAULT GETDATE()`、创建人 `DEFAULT SUSER_SNAME()`，杜绝应用漏填 |
| `CHECK` | 状态字段限定枚举（`Mkind_code IN ('1','2','3')`），挡脏数据在入口 |
| `FOREIGN KEY` | 业务强关联（流水→主档）必建；纯报表冗余字段不必建 FK（写放大、锁竞争） |

> 注意：**约束名必须显式命名**（`PK_表名`、`FK_表名_被引表`、`CK_表名_字段`），否则默认自动名（如 `DF__xxx__5A`）在删改约束时无法定位。索引名同理 `IX_表名_字段` / `UX_表名_字段`。

## 四、索引设计（详见 [[sql-server-performance-troubleshooting]] 索引章节）

- **不是越多越好**：每次增删改都维护索引，多一个索引多一份写放大（手册索引原则 1）。
- **哪些字段建**：数据量 1 万以内不建；`where/order by/join` 字段按需建；**高区分度字段才建**（`deleteFlag` 99% 是 0 的不建单列索引，见手册索引原则 4）。
- **复合索引列序**：等值列在前、范围列在后；最左前缀生效。
- **覆盖索引 INCLUDE**：只 SELECT 不过滤的列放 INCLUDE，消除 Key Lookup（手册索引原则 8，含示例）。
- **填充因子 FILLFACTOR**：读多写少表 100；**高频插入/更新表设 70~90**（留页内空间减少页拆分）；重建索引时设置。
- **统计信息**：重建索引自动更新统计信息，**重组索引不会**，需单独 `UPDATE STATISTICS`（手册索引原则 11）；大表默认自动更新阈值高，配合维护计划定期全量更新。

## 五、字符集与排序规则（Collation）

- 全库统一排序规则：有中文需求的库用 `Chinese_PRC_CI_AS`（大小写不敏感、区分重音）——**本系统默认**；需要区分大小写的业务字段单独 `COLLATE` 指定。
- **建库时定好，后期改代价极大**（所有字符串列、索引、约束都要重建）。
- 字段级/表达式级 `COLLATE` 冲突会导致 JOIN 无法走索引（隐式转换同族问题）。

## 六、文件组、分区与归档

- 单表预估 > 5000 万行且持续增长 → 按时间做**分区表**（按月/按季），配合分区切换实现秒级归档/清理。
- 即使不分区，也保证新数据按时间**聚集**写入（配合 1.3 聚集索引），避免旧数据碎片摊薄 IO。
- 大历史表（如生产实绩）建立归档策略：明细归档到历史库/历史表，在线表只保留热数据——比"大表 + 复杂索引"成本低得多。

## 七、审计字段与软删除

- 流水/履历表统一带审计列：`CREATE_TIME DATETIME2(3) DEFAULT GETDATE()`、`CREATE_USER VARCHAR(50)`；更新类表加 `UPDATE_TIME`、`UPDATE_USER`。
- **软删除**（`DELETE_FLAG`）仅在"删除后需保留追溯"的合规场景使用；普通业务优先物理删除或归档表——软删除字段大量为 0 时会污染索引与统计（见 4 节高区分度原则），且所有查询都要带 `DELETE_FLAG=0` 条件。

## 八、临时表规范（衔接 STRING_AGG 案例）

- 复杂报表/多级聚合：**明细先 SELECT INTO 临时表**（自动生成统计信息、行数确定），再在其上聚合——实测内存授予 250MB→8MB（见 [[sql-server-performance-troubleshooting]] 实战案例）。
- 临时表命名 `#` 前缀（局部）/`##`（全局）；会话级局部临时表用完自动清理，不必显式 DROP，但长事务中建议用完即删。
- 表变量 `@tbl` 无统计信息、适用小数据量（<100 行）场景；大数据量聚合一律临时表。

## 九、命名规范

| 对象 | 规范 | 示例 |
|------|------|------|
| 表 | 业务域前缀 + 表名（Ppt_、Ppm_、Bpm_） | `Ppt_Weigh` |
| 主键约束 | `PK_表名` | `PK_Ppt_Weigh` |
| 外键约束 | `FK_表名_被引表` | `FK_Ppt_Weigh_Pmt_Material` |
| 唯一约束/索引 | `UX_表名_字段` | `UX_Pmt_Material_MaterCode` |
| 普通索引 | `IX_表名_字段` | `IX_Ppt_Lot_RecordTime` |
| 检查约束 | `CK_表名_字段` | `CK_Ppt_Lot_Status` |
| 字段 | 驼峰或全大写下划线，全库统一；禁止中文/保留字 | `Mater_Code`、`Record_Time` |

> 建表后立即在 `sys.extended_properties` 写表/字段中文说明——MES 系统字段含义多，没人能靠猜记住。

## 十、建表 DDL 模板（本系统风格）

```sql
CREATE TABLE [dbo].[Ppt_Example] (
    [ID]            INT IDENTITY(1,1) NOT NULL,               -- 代理主键
    [Plan_Id]       VARCHAR(30)   NOT NULL,                   -- 计划号（与关联表同型同长）
    [Mater_Code]    CHAR(10)      NOT NULL,                   -- 物料编码（定长状态类）
    [Record_Time]   DATETIME2(3)  NOT NULL DEFAULT GETDATE(), -- 记录时间（聚集索引候选）
    [Real_Weight]   DECIMAL(18,4) NULL,                       -- 实际重量（金额/重量类）
    [Delete_Flag]   CHAR(1)       NOT NULL DEFAULT '0',       -- 删除标记（配合 CHECK）
    [Create_User]   VARCHAR(50)   NOT NULL DEFAULT SUSER_SNAME(),
    CONSTRAINT [PK_Ppt_Example] PRIMARY KEY NONCLUSTERED ([ID]),
    CONSTRAINT [CK_Ppt_Example_DeleteFlag] CHECK ([Delete_Flag] IN ('0','1')),
    CONSTRAINT [CK_Ppt_Example_PlanId] CHECK ([Plan_Id] <> '')
);
GO
-- 聚集索引放时间列（流水类）
CREATE CLUSTERED INDEX [IX_Ppt_Example_RecordTime]
    ON [dbo].[Ppt_Example] ([Record_Time])
    WITH (FILLFACTOR = 90);
GO
-- 高频查询覆盖索引示例
CREATE NONCLUSTERED INDEX [IX_Ppt_Example_PlanId]
    ON [dbo].[Ppt_Example] ([Plan_Id])
    INCLUDE ([Mater_Code], [Real_Weight]);
GO
-- 中文注释（扩展属性）
EXEC sys.sp_addextendedproperty
    @name = N'MS_Description', @value = N'示例流水表',
    @level0type = N'SCHEMA', @level0name = N'dbo',
    @level1type = N'TABLE',  @level1name = N'Ppt_Example';
GO
```

## 十一、建表前检查清单（逐条过）

1. 有主键？键类型够窄（int/varchar 短编码优先，不用 GUID）？
2. 聚集索引选对了？（流水按时间，主档按主键）
3. 所有字段选最小够用类型？日期没存 varchar？金额没存 float？编码没乱用 nvarchar？
4. 可空字段是否尽量 NOT NULL + DEFAULT？
5. 状态/类型字段加了 CHECK 约束？
6. 与已有表关联的字段类型、长度是否完全一致？
7. 表/字段中文注释是否已写？
8. 索引规划做了吗？（高频 where/join/order by 字段、覆盖 INCLUDE、FILLFACTOR）
9. 大表考虑分区/归档了吗？统计信息维护计划覆盖到了吗？
10. 约束名、索引名是否按规范显式命名？

## 十二、关联

- 性能排查全流程（隐式转换、参数嗅探、统计信息、内存授予案例）：见 [[sql-server-performance-troubleshooting]]
- 索引覆盖与 INCLUDE：见 [[sql-server-performance-troubleshooting]] 索引章节
- 生产实绩看板作业的临时表复用套路：见 [[pb-daily-job-architecture]]

---

## 十二、Unicode 字符集陷阱：GBK 外字符必须 NVARCHAR（2026-09-19 实证）

**症状范式**：某列存符号/特殊字符，"部分值保存成功、特定字符必失败"——例如判定符号 √(U+221A)、×(U+00D7) 在 GBK 字符集内各占 2 字节，`VARCHAR(2)` 恰好能存；**⊗(U+2297 圈叉) 不在 GBK 字符集**，varchar 列写入直接转换失败。SQ-PK01 样式-3 硫化日报 TIME_JUDGE 列实证：√/× 保存成功、⊗ 必败（"只有最后一次保存失败"的迷惑性症状）。

**规则**：
- 列可能存**符号、特殊 unicode、emoji、日文/韩文假名**等非常规中文内容时，一律 `NVARCHAR`——不要赌字符恰好在当前排序规则字符集内（中文库存中文没事的侥幸是坑）
- 已建表补丁：`ALTER TABLE x ALTER COLUMN c NVARCHAR(n) NULL`（列上无索引/约束时直接改，GBK 内旧值自动转换保留）
- 中文字符串字面量拼接用 `N'...'` 前缀（如 `STRING_AGG(col, N'、')`）
- 检查字符是否在 GBK：Python `'⊗'.encode('gbk')` 抛 UnicodeEncodeError 即不在（√/× 能编码即安全）

**案例**：[[curing-daily3-report-implementation]] §五踩坑1（判定列 VARCHAR(2)→NVARCHAR(2) + 已建表 ALTER 补丁段）。