---
title: SQL Server 游标（CURSOR）使用
category: 技术-数据库
module: 通用
factory: 通用
tags: [SQL Server, 游标, CURSOR, FETCH, "@@FETCH_STATUS", 逐行处理, 语法速查]
status: active
updated: 2026-08-29
---
# SQL Server 游标（CURSOR）使用

> 游标（CURSOR）逐行遍历结果集的标准用法：声明→打开→FETCH→WHILE @@FETCH_STATUS=0 循环→关闭→释放六步流程，附完整实例（遍历加 10 分写入临时表）。要点：FETCH 出现两次的原理、临时表用完 DROP、大数据量优先集合操作。

## 一、作用

游标是一种**逐行遍历查询结果集**的机制，允许对每一行执行特定操作（计算、更新、删除、写入其他表等）。普通 SQL 是面向集合的，游标弥补了"需要逐行处理"的场景。

典型用途：
- 首次部署脚本：遍历设备数据，按类型往不同表写入/修改数据。
- 复杂逐行逻辑：每行需条件判断、循环、调用其他逻辑。
- 存储过程/触发器中精细处理。

## 二、使用流程（六步）

游标生命周期：**声明 → 打开 → 获取 → 循环 → 关闭 → 释放**。

```sql
-- 1. 声明游标（关联一个 SELECT）
DECLARE cursor_name CURSOR FOR
SELECT column1, column2, ... FROM table_name WHERE condition;

-- 2. 打开游标
OPEN cursor_name;

-- 3. 获取第一行数据到变量
FETCH NEXT FROM cursor_name INTO @var1, @var2, ...;

-- 4. 循环遍历
WHILE @@FETCH_STATUS = 0
BEGIN
    -- 对当前行执行操作
    FETCH NEXT FROM cursor_name INTO @var1, @var2, ...;  -- 取下一行
END

-- 5. 关闭游标
CLOSE cursor_name;

-- 6. 释放游标
DEALLOCATE cursor_name;
```

## 三、@@FETCH_STATUS 状态值

| 值 | 含义 |
|----|------|
| `0` | FETCH 成功，已获取下一行 |
| `-1` | FETCH 失败或无更多数据 |
| `-2` | 游标已到末尾或未打开 |

> `WHILE @@FETCH_STATUS = 0` 即"只要成功取到数据就继续循环"。

## 四、为什么 FETCH 出现两次

- **第一次**（循环前）：获取第一行，决定是否进入循环。
- **第二次**（循环体末尾）：获取下一行，驱动下一次循环判断。

两次配合实现"取一行→处理→取下一行→…→取不到则退出"。

## 五、完整实例：学生成绩加 10 分

```sql
-- 声明变量
DECLARE @UserName VARCHAR(10),
        @Subject VARCHAR(10),
        @Score DECIMAL(10, 2),
        @Score1 DECIMAL(10, 2);

-- 临时表存处理结果
CREATE TABLE #Student1 (username VARCHAR(10), subject VARCHAR(10), score DECIMAL(10, 2));

-- 声明游标
DECLARE Student CURSOR FOR
SELECT UserName, Subject, Score FROM dbo.StudentScores;

-- 打开游标
OPEN Student;

-- 获取第一行
FETCH NEXT FROM Student INTO @UserName, @Subject, @Score;

-- 循环
WHILE @@FETCH_STATUS = 0
BEGIN
    SET @Score1 = @Score + 10;                              -- 每行加 10 分
    INSERT #Student1 VALUES(@UserName, @Subject, @Score1);  -- 存入临时表
    FETCH NEXT FROM Student INTO @UserName, @Subject, @Score;  -- 取下一行
END

-- 关闭并释放
CLOSE Student;
DEALLOCATE Student;

-- 查看结果
SELECT * FROM #Student1;
DROP TABLE #Student1;   -- 用完删除临时表，否则同窗口再次执行报已存在
```

> 本例把处理结果写入临时表，也可用 `UPDATE` 直接改原表。用临时表便于反复测试。

## 六、注意

- **性能**：游标逐行处理，大数据量时性能差。能用集合操作（UPDATE/DELETE 带 JOIN、CTE）替代就别用游标。
- **必须关闭+释放**：游标占用资源，用完 CLOSE + DEALLOCATE，否则连接期间资源不释放。
- 临时表配合游标时，用完 DROP，否则同窗口重复执行报"表已存在"。
- 游标适合"项目首次部署脚本"等一次性场景；在线高频业务逻辑尽量用集合操作。

## 七、关联

- 查询正在执行的语句 / 死锁处理：见 `sql-running-queries-and-deadlock.md`
- FOR XML PATH 列转行 / 分页查询：见 `sql-xml-path-and-paging.md`
- SQL Server 性能排查：见 `sql-server-performance-troubleshooting.md`
