#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""通用工具函数"""

import contextlib
import datetime
import os
import sys
import time
from config import ALLOWED_KB_IDS, KB_ROOT, RUNTIME_LOG


def log(msg):
    """输出日志到 stderr（MCP 协议走 stdout），并 tee 到 runtime.log（毫秒时间戳+PID）。

    文件侧用 O_APPEND + 单次 os.write，多进程并发追加同一行不会交错；
    落盘失败静默忽略——日志绝不能影响业务。
    """
    line = f"[my-kb] {msg}"
    print(line, file=sys.stderr, flush=True)
    try:
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        entry = f"[{stamp}] [pid {os.getpid()}] {line}\n".encode("utf-8", "replace")
        fd = os.open(str(RUNTIME_LOG), os.O_WRONLY | os.O_CREAT | os.O_APPEND)
        try:
            os.write(fd, entry)
        finally:
            os.close(fd)
    except Exception:
        pass


@contextlib.contextmanager
def file_lock(lock_path, timeout=60):
    """跨进程文件锁（Windows msvcrt / POSIX fcntl 双平台；独立 .lock 文件）。

    等待至多 timeout 秒，超时放弃加锁继续执行并返回 locked=False——锁是防并发
    写坏的优化而非硬门槛，绝不死锁（与 chroma 开库锁同哲学）。用法：
    `with file_lock(p) as locked: ...`。
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(lock_path, "a+")
    locked = False
    try:
        deadline = time.time() + timeout
        try:
            import msvcrt
            while time.time() < deadline:
                try:
                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    locked = True
                    break
                except OSError:
                    time.sleep(0.2)
        except ImportError:
            import fcntl
            while time.time() < deadline:
                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    locked = True
                    break
                except OSError:
                    time.sleep(0.2)
        yield locked
    finally:
        if locked:
            try:  # best-effort 解锁：失败静默（句柄随 fh.close() 关闭，进程退出即释放）
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception:
                try:
                    import fcntl
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
        fh.close()


def validate_kb_id(kb_id):
    """校验 kb_id，返回合法的 kb_id；非法则抛 ValueError。"""
    if kb_id not in ALLOWED_KB_IDS:
        raise ValueError(f"非法 kb_id: {kb_id!r}，允许值: {sorted(ALLOWED_KB_IDS)}")
    return kb_id


def kb_vectordb_path(kb_id):
    """按 kb_id 解析对应向量库目录。"""
    return KB_ROOT / kb_id / "vectordb"


def kb_markdown_dir(kb_id):
    """按 kb_id 解析 raw/markdown 目录。"""
    return KB_ROOT / kb_id / "raw" / "markdown"


# Windows 保留设备名（CON.md / nul.tar.gz / com1.md 等在 Win 上行为不可预期；2026-10-09 P0 加固）
_WIN_RESERVED_NAMES = frozenset(
    ["CON", "PRN", "AUX", "NUL", "CLOCK$", "CONIN$", "CONOUT$"]
    + ["COM%d" % i for i in range(1, 10)]
    + ["LPT%d" % i for i in range(1, 10)]
)


def is_safe_filename(filename):
    """检查文件名是否安全（防路径遍历 / 盘符冒号 / Windows 保留名）。返回 True=安全。

    保留名按 MS 定义取第一个点前的段（NUL.tar.gz ≡ NUL），尾点/尾空格视为保留名；
    ":" 一律拒绝——Windows 下 md_dir / "C:x.md" 会重置盘符越界。
    """
    if ".." in filename or "/" in filename or "\\" in filename or ":" in filename:
        return False
    stem = filename.split(".", 1)[0].strip().rstrip(". ").upper()
    if stem in _WIN_RESERVED_NAMES:
        return False
    return True
