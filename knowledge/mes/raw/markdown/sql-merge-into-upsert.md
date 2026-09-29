---
title: SQL Server MERGE INTO — 存在则更新/不存在则插入（UPSERT）
category: 技术-数据库
module: 通用
factory: 通用
tags: [SQL Server, MERGE INTO, UPSERT, WHEN MATCHED, WHEN NOT MATCHED, iBATIS, 语法速查]
status: active
updated: 2026-08-29
---
# SQL Server MERGE INTO — 存在则更新/不存在则插入（UPSERT）

> MERGE INTO 用一条语句完成 UPSERT（存在则 UPDATE、不存在则 INSERT）：MERGE INTO target USING source ON 匹配键 + WHEN MATCHED/NOT MATCHED 分支。附 iBATIS 库位信息 Upsert 项目实例（#xxx# 占位符构造 source）。硬性要求：语句必须以分号结尾；并发下比"先查后改"安全（原子操作）。

## 一、作用

`MERGE INTO` 一条语句完成 **"存在则 UPDATE、不存在则 INSERT"**（即 UPSERT），避免先 SELECT 判断再分别写 UPDATE/INSERT 的两步操作。

典型用途：
- 主数据同步：外部数据导入，已有则更新、没有则新增。
- 状态/计数更新：按业务键累加或覆盖。
- 接口落库：上游推送的记录Upsert 进本地表。

## 二、基本结构

```sql
MERGE INTO 目标表 AS target              -- 要更新/插入的表
USING (数据来源) AS source                -- 提供"新数据"的子查询/表
ON target.键 = source.键                 -- 匹配条件（判断是否已存在）
WHEN MATCHED THEN                        -- 已存在 → 更新
    UPDATE SET 列 = source.列, ...
WHEN NOT MATCHED THEN                    -- 不存在 → 插入
    INSERT (列...) VALUES (source.列...);
```

执行逻辑：
1. 对 source 的每一行，按 `ON` 条件去 target 找匹配。
2. 找到匹配（MATCHED）→ 执行 `UPDATE SET`。
3. 没找到匹配（NOT MATCHED）→ 执行 `INSERT`。

> ⚠️ MERGE 语句**必须以分号 `;` 结尾**，否则 SQL Server 报语法错误。

## 三、项目实例：库位信息 Upsert（iBatis mapper）

```sql
MERGE INTO HPP_SM_LOCATION AS target
USING (
    SELECT
        #LOCATION_CODE# AS LOCATION_CODE,
        #LOCATION_NAME# AS LOCATION_NAME,
        #AREA_CODE# AS AREA_CODE,
        #User# AS User
) AS source
ON target.LOCATION_CODE = source.LOCATION_CODE
   AND source.AREA_CODE = target.AREA_CODE
WHEN MATCHED THEN
    UPDATE SET
        LOCATION_NAME = source.LOCATION_NAME,
        RECORD_TIME = GETDATE(),
        RECORD_USER_ID = source.User,
        DELETE_FLAG = 0
WHEN NOT MATCHED THEN
    INSERT (
        AREA_CODE, LOCATION_CODE, LOCATION_NAME,
        LOCATION_TYPE, MATERIAL_CODE, LED_ID, LED_Index,
        CAPACITY, USE_STATE, RECORD_USER_ID, RECORD_TIME,
        DELETE_FLAG, REMARK, ROW_VERSION
    )
    VALUES (
        source.AREA_CODE, source.LOCATION_CODE, source.LOCATION_NAME,
        NULL, NULL, NULL, NULL,
        NULL, NULL, source.User, GETDATE(),
        0, NULL, NULL
    );
```

### 要点解析

| 部分 | 说明 |
|------|------|
| `USING (...) AS source` | 把传入参数（iBatis 的 `#LOCATION_CODE#` 占位符）构造成一行虚拟数据作为 source |
| `ON target.键 = source.键` | 匹配键是 `LOCATION_CODE` + `AREA_CODE`（联合键） |
| `WHEN MATCHED → UPDATE` | 已存在：更新名称、记录时间、操作人，并把 `DELETE_FLAG` 复位为 0（软删除恢复） |
| `WHEN NOT MATCHED → INSERT` | 不存在：插入完整行，非传入字段填 NULL/默认值 |
| `DELETE_FLAG = 0` | 更新时把删除标记复位——即使之前被软删，重新导入也恢复 |

> iBatis 占位符 `#xxx#`：运行时由 iBatis.Net 替换为参数化值，防 SQL 注入。`source` 构造的目的是让 MERGE 有统一的数据来源结构。

## 四、匹配条件（ON）的要点

- `ON` 决定"什么算已存在"，通常是业务主键/唯一键。
- 可用**联合键**（多个 AND 条件），如本例 `LOCATION_CODE + AREA_CODE`。
- ON 的匹配列在 source 和 target 两边都要有，故 source 子查询要 SELECT 出这些列。

## 五、更多 WHEN 分支

MERGE 还支持其他分支（按需使用）：

```sql
MERGE INTO target T
USING source S
ON T.id = S.id
WHEN MATCHED AND T.version < S.version THEN   -- 带附加条件的更新
    UPDATE SET ...
WHEN MATCHED THEN                              -- 其余匹配不处理
    UPDATE SET ...
WHEN NOT MATCHED BY TARGET THEN                -- target 没有则插入
    INSERT ...
WHEN NOT MATCHED BY SOURCE THEN                -- source 没有则（可删除 target）
    DELETE;
```

| 分支 | 含义 |
|------|------|
| `WHEN MATCHED THEN UPDATE` | target 有对应行 → 更新 |
| `WHEN MATCHED AND <条件>` | 满足附加条件才更新 |
| `WHEN NOT MATCHED THEN INSERT` | target 无对应行 → 插入 |
| `WHEN NOT MATCHED BY SOURCE THEN DELETE` | source 没有但 target 有 → 删除（数据同步清理用） |

## 六、与"先查后改"的对比

| 方式 | 写法 | 数据库交互 |
|------|------|-----------|
| 先 SELECT 判断 + UPDATE/INSERT | C# 里查一次，再分别执行 | 至少 2 次往返，并发下可能重复插入 |
| MERGE INTO | 一条 SQL | 1 次往返，原子操作 |

> MERGE 是**原子操作**，并发场景下比"先查后改"更安全，不会出现两个请求都判断为"不存在"然后都插入的问题。

## 七、注意

- **必须以分号 `;` 结尾**，这是 MERGE 的硬性要求。
- `ON` 的匹配列在两边类型需一致，否则隐式转换影响性能或匹配结果。
- MERGE 在大表上性能取决于 `ON` 条件是否能走索引；target 表的匹配键应有索引。
- `WHEN MATCHED` 的 UPDATE 不能更新 `ON` 里用到的列（匹配键），否则语义混乱。
- iBatis mapper 里写 MERGE 时，参数用 `#xxx#` 占位符传入 source 子查询，保持参数化。

## 八、关联

- APPLY（CROSS/OUTER）用法：见 `sql-outer-apply-cross-apply.md`
- SQL Server 性能排查与优化：见 `sql-server-performance-troubleshooting.md`
- iBatis result mapping 性能：见 `ibatis-result-mapping-performance.md`
