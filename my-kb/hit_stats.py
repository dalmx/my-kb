#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""按 source 命中计数：检索的最终返回结果呈现过哪些文档，累计次数与最近命中时间。

淘汰决策的数据源（零命中 + 孤岛 + 较旧 = 淘汰候选，最终决策留人工）：
  - retriever 每次检索（search / search_multi）在 MMR 选完后调用 record_hits
  - get_hit_stats 工具展示命中分布与零命中文档
  - graph_tools.get_orphans 结合引用图交叉出淘汰候选

存储格式（hit_counts.json，原子写入）：
  {"counting_since": "YYYY-MM-DD", "total_searches": N,
   "sources": {文件名: {"hits": N, "last_hit": "ISO时间"}}}
"""

import contextlib
import datetime
import json
import os

from config import HIT_STATS_ENABLED, HIT_STATS_PATH
from utils import log


@contextlib.contextmanager
def _file_lock(lock_path):
    """跨进程文件锁（Windows msvcrt，锁首字节）。

    多个 my-kb 进程（每个 ZCode 会话一个）并发写 hit_counts.json 时，
    读-改-写必须互斥，否则丢计数。独立 .lock 文件避免原子替换使锁失效。
    """
    import msvcrt
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+") as lf:
        msvcrt.locking(lf.fileno(), msvcrt.LK_LOCK, 1)
        try:
            yield
        finally:
            try:
                msvcrt.locking(lf.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass


def _empty_stats():
    return {
        "counting_since": datetime.date.today().isoformat(),
        "total_searches": 0,
        "sources": {},
    }


def load_hit_stats(path=None):
    """读取命中统计。文件不存在/损坏时返回空白初始结构（绝不中断检索）。"""
    p = path or HIT_STATS_PATH
    if not p.exists():
        return _empty_stats()
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not isinstance(data.get("sources"), dict):
            raise ValueError("结构不符")
        return data
    except Exception as e:
        log(f"命中统计文件读取失败，按空统计处理: {e}")
        return _empty_stats()


def _save(data, path=None):
    p = path or HIT_STATS_PATH
    tmp = p.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def record_hits(sources):
    """记录一次检索的命中（sources = 本次返回结果中的唯一文件名集合）。

    统计含义：该文档被检索"呈现给 AI"。同一文档在一次结果中出现多条块
    只算一次。失败只记日志，绝不影响检索本身。
    """
    if not HIT_STATS_ENABLED:
        return
    try:
        with _file_lock(HIT_STATS_PATH.with_suffix(".lock")):
            data = load_hit_stats()
            now = datetime.datetime.now().isoformat(timespec="seconds")
            data["total_searches"] = int(data.get("total_searches", 0)) + 1
            for src in set(sources):
                if not src:
                    continue
                entry = data["sources"].setdefault(src, {"hits": 0, "last_hit": ""})
                entry["hits"] = int(entry.get("hits", 0)) + 1
                entry["last_hit"] = now
            _save(data)
    except Exception as e:
        log(f"命中统计写入失败（忽略）: {e}")


def get_hits_map():
    """返回 {文件名: hits}，供 get_orphans 交叉淘汰候选。"""
    return {
        src: int(e.get("hits", 0))
        for src, e in load_hit_stats().get("sources", {}).items()
    }


def format_hit_stats(top_limit=20):
    """命中统计报告：计数起点、累计检索次数、高命中 Top N、零命中文档（跨库）。"""
    from graph_tools import all_kb_md_filenames

    data = load_hit_stats()
    hits_map = get_hits_map()
    on_disk = all_kb_md_filenames()  # {filename: kb_id}，跨所有库

    days = None
    try:
        since = datetime.date.fromisoformat(str(data.get("counting_since", "")))
        days = (datetime.date.today() - since).days
        since_s = f"{since}（已积累 {days} 天）"
    except ValueError:
        since_s = str(data.get("counting_since", "?"))

    lines = [
        f"按 source 命中统计（计数自 {since_s}，"
        f"累计有结果检索 {data.get('total_searches', 0)} 次）:"
    ]

    last_hit = {s: str(e.get("last_hit", "")) for s, e in data.get("sources", {}).items()}
    top = [(s, h) for s, h in sorted(hits_map.items(), key=lambda x: -x[1]) if h > 0][:top_limit]
    lines.append(f"\n高命中 Top {len(top)}（被检索呈现次数最多）:")
    if top:
        for s, h in top:
            lines.append(f"  {s} (库 {on_disk.get(s, '?')}) — {h} 次，最近 {last_hit.get(s, '?')[:10]}")
    else:
        lines.append("  （尚无命中记录）")

    zero_hit = sorted(s for s in on_disk if hits_map.get(s, 0) == 0)
    lines.append(f"\n零命中文档（{len(zero_hit)} 个，自计数起点起从未被检索呈现）:")
    if days is not None and days < 14:
        lines.append(f"  ⚠️ 计数刚开始 {days} 天，零命中不代表无用，仅供参考")
    if zero_hit:
        for s in zero_hit:
            lines.append(f"  {s} (库 {on_disk[s]})")
    else:
        lines.append("  （无）")

    stale_entries = sorted(set(hits_map) - set(on_disk))
    if stale_entries:
        lines.append(f"\n已不在库的统计残留（{len(stale_entries)} 个，改名/删除后遗留，可忽略）:")
        for s in stale_entries[:10]:
            lines.append(f"  {s}")

    lines.append("\n使用建议: 配合 get_orphans 看淘汰候选（零命中+孤岛+较旧）；淘汰决策始终留人工。")
    return "\n".join(lines)
