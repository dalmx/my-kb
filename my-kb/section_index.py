#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""H2 章节级粗索引（STAIR"ToC=寻址方案"的向量版，2026-09-08 实验）

每个 (source, h1, h2) 章节聚合主库 chunk 生成一条粗粒度索引，存于独立 collection
（<kb>_sections，与主库同一 persist 目录）。检索时（SECTION_INDEX_ENABLED=True，
retriever 查询侧）用同一查询向量 + 同一 where 查 sections top-K，命中章节旗下的
chunk 在规则重排层获得固定加成——把"整节强相关"的结构信号喂给排序，救回
单块弱但章节强的候选（对症概览类/跨章节问题）。

章节文本 = title + h1 + h2 + 旗下 h3 标题 + 首块预览（短文本粗匹配够用，不建 BM25）。
metadata 镜像主库 chunk（category/module/tags/factory...），where 过滤同样生效。

写入侧维护（活库同步，防索引漂移）：
- indexer.index_file 成功后 → rebuild_for_source 增量重建该 source 的 sections
- server.delete_source / purge 清理 → delete_source_sections
- 一次性全量：python section_index.py --rebuild [--kb mes]
均以 SECTION_INDEX_ENABLED 门控：flag 关闭期间零开销，也不产生 section
（翻 True 前必须先全量 --rebuild，见 config.py 注释）。
"""

import sys
from pathlib import Path

from langchain_core.documents import Document

from config import SECTION_INDEX_ENABLED
from utils import log, validate_kb_id

# 章节首块正文预览长度（拼进 section 文本供粗匹配）
SECTION_PREVIEW_CHARS = 300


def _chunk_docs_from_results(results):
    """chroma get() 结果 → Document 列表（与 bm25 构建同构的转换）。"""
    docs = []
    for text, meta in zip(results.get("documents", []), results.get("metadatas", [])):
        if text:
            docs.append(Document(page_content=text, metadata=meta or {}))
    return docs


def sections_from_chunks(chunk_docs):
    """主库 chunk 聚合生成章节 Document 列表。分组键 (h1, h2)；h2 为空=文首摘要区，
    也生成一条（doc 级粗匹配语义锚点）。"""
    groups = {}   # (h1, h2) -> {"meta", "h3s", "preview", "n"}
    order = []
    for c in chunk_docs:
        m = c.metadata or {}
        h1 = str(m.get("h1") or "")
        h2 = str(m.get("h2") or "")
        h3 = str(m.get("h3") or "")
        key = (h1, h2)
        if key not in groups:
            groups[key] = {"meta": dict(m), "h3s": [], "preview": "", "n": 0}
            order.append(key)
        g = groups[key]
        g["n"] += 1
        if h3 and h3 not in g["h3s"]:
            g["h3s"].append(h3)
        if not g["preview"] and c.page_content:
            g["preview"] = c.page_content.strip()[:SECTION_PREVIEW_CHARS]

    docs = []
    for key in order:
        g = groups[key]
        m = dict(g["meta"])
        m["h1"], m["h2"] = key[0], key[1]
        m["n_chunks"] = g["n"]
        head = "  ".join(p for p in (str(m.get("title") or ""), key[0], key[1]) if p)
        parts = [head]
        if g["h3s"]:
            parts.append("小节: " + "、".join(g["h3s"]))
        if g["preview"]:
            parts.append(g["preview"])
        docs.append(Document(page_content="\n".join(parts), metadata=m))
    return docs


def _delete_sections(store, source):
    """从 sections store 删除指定 source 的全部条目（不查 flag，供维护路径直用）。

    返回删除条数；失败返回 -1——调用方应跳过后续 add（P2，CC 审查 20260908：
    删除失败仍 add 时，节数比旧批次少的尾部 uuid5(id=source::i) 会残留）。
    """
    try:
        results = store.get(where={"source": source})
        ids = list(results.get("ids", []))
        if ids:
            store.delete(ids=list(ids))
        return len(ids)
    except Exception as e:
        log(f"sections 删除失败 (source={source}): {e}")
        return -1


def delete_source_sections(kb_id, source):
    """删除指定 source 的全部 sections。返回删除条数（flag 关闭时跳过返回 0）。"""
    if not SECTION_INDEX_ENABLED:
        return 0
    from models import get_section_vectorstore
    return _delete_sections(get_section_vectorstore(kb_id), source)


def rebuild_for_source(kb_id, source):
    """按 source 增量重建 sections（先删后建）。返回生成的节数；flag 关闭时跳过返回 0。"""
    if not SECTION_INDEX_ENABLED:
        return 0
    from models import get_vectorstore
    try:
        main = get_vectorstore(kb_id)
        results = main.get(where={"source": source})
        chunk_docs = _chunk_docs_from_results(results)
        store = get_section_vectorstore(kb_id)
        if _delete_sections(store, source) < 0:
            # P2：删除失败跳过 add，防 uuid5 尾部残留
            log(f"sections 增量重建跳过 add（旧条目删除失败）: source={source}")
            return 0
        docs = sections_from_chunks(chunk_docs)
        if docs:
            store.add_documents(docs)
        log(f"sections 增量重建: {source} → {len(docs)} 节")
        return len(docs)
    except Exception as e:
        log(f"sections 增量重建失败 (source={source}): {e}")
        return 0


def rebuild_all(kb_id):
    """全量重建 sections（不计 flag 门控——显式 CLI/维护入口）。
    返回 (文件数, 节数)。"""
    validate_kb_id(kb_id)
    from models import get_vectorstore, get_section_vectorstore
    main = get_vectorstore(kb_id)
    results = main.get()
    by_source = {}
    for c in _chunk_docs_from_results(results):
        src = c.metadata.get("source", "")
        if src:
            by_source.setdefault(src, []).append(c)

    store = get_section_vectorstore(kb_id)
    # P1（CC 审查 20260908）：先清孤儿——sections 里存在而主库已无 chunk 的 source
    # （删除/合并/改名期间 flag 关闭漏维护的存量），rebuild_all 是唯一兜得住它们的入口
    try:
        sec_results = store.get()
        sec_sources = {m.get("source") for m in sec_results.get("metadatas", []) if m and m.get("source")}
        stale_sources = sec_sources - set(by_source)
        for stale in stale_sources:
            _delete_sections(store, stale)
        if stale_sources:
            log(f"sections 孤儿清理: {sorted(stale_sources)}")
    except Exception as e:
        log(f"sections 孤儿清理失败（忽略，继续重建）: {e}")

    total_sections = 0
    for source, chunk_docs in sorted(by_source.items()):
        try:
            if _delete_sections(store, source) < 0:
                continue  # P2：删除失败跳过 add，防 uuid5 尾部残留
            docs = sections_from_chunks(chunk_docs)
            if docs:
                store.add_documents(docs)
                total_sections += len(docs)
        except Exception as e:
            log(f"sections 全量重建失败 (source={source}): {e}")
    log(f"sections 全量重建完成: {len(by_source)} 文件 → {total_sections} 节")
    return len(by_source), total_sections


def sections_stats(kb_id):
    """sections collection 统计（文件数/节数），供验证。"""
    from models import get_section_vectorstore
    store = get_section_vectorstore(kb_id)
    results = store.get()
    sources = {m.get("source") for m in results.get("metadatas", []) if m}
    return len(sources), len(results.get("ids", []))


if __name__ == "__main__":
    try:  # Windows 控制台中文输出防御
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    import argparse
    ap = argparse.ArgumentParser(description="H2 章节级粗索引维护")
    ap.add_argument("--rebuild", action="store_true", help="全量重建 sections")
    ap.add_argument("--stats", action="store_true", help="查看 sections 统计")
    ap.add_argument("--kb", default="mes", help="知识库 ID（默认 mes）")
    args = ap.parse_args()

    if args.rebuild:
        n_src, n_sec = rebuild_all(args.kb)
        print(f"sections 全量重建完成: {n_src} 文件 → {n_sec} 节")
    elif args.stats:
        n_src, n_sec = sections_stats(args.kb)
        print(f"sections 统计: {n_src} 文件 / {n_sec} 节")
    else:
        print("用法: python section_index.py --rebuild [--kb mes] | --stats")
