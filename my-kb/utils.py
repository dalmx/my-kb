#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""通用工具函数"""

import datetime
import os
import sys
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


def is_safe_filename(filename):
    """检查文件名是否安全（防路径遍历）。返回 True=安全。"""
    if ".." in filename or "/" in filename or "\\" in filename:
        return False
    return True
