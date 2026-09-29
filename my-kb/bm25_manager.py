#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""BM25 关键词索引管理（内存索引，与向量库并行的稀疏召回通道）。

设计：
- BM25Retriever 是内存索引，按 kb_id 懒加载。
- 数据来源：从 Chroma 全量拉取（get()）→ 重建为 BM25Retriever。
- 失效策略：index_file / delete_source / rebuild 等写操作后调用 invalidate(kb_id)，
  下次搜索时按需重建。避免每次写入都重建（批量索引只失效一次）。
- 中文分词：BM25 默认按空格切分，中文无效。用 jieba 预处理文档文本后再建索引。
"""

from config import (
    KB_ROOT, ALLOWED_KB_IDS, DEFAULT_KB_ID,
    _bm25_retrievers, BM25_POOL_K,
)
from models import get_vectorstore
from utils import log, validate_kb_id


def _jieba_tokenize(text):
    """BM25 preprocess_func：用 jieba 分词（中文必须分词否则 BM25 失效）。"""
    import jieba
    return [w for w in jieba.lcut(text) if w.strip()]


def _build_bm25_for_kb(kb_id):
    """从向量库全量拉取文档，构建该库的 BM25 索引。返回 BM25Retriever 或 None。

    Document 保留原始文本（page_content 不变），分词通过 preprocess_func 在
    BM25 内部计算时进行。这样召回的 Document 可直接用于显示和后续重排。
    """
    from langchain_community.retrievers import BM25Retriever

    vs = get_vectorstore(kb_id)
    results = vs.get()
    docs_data = results.get("documents", [])
    metadatas = results.get("metadatas", [])

    if not docs_data:
        return None

    from langchain_core.documents import Document
    docs = []
    for text, meta in zip(docs_data, metadatas):
        if not text:
            continue
        d = Document(page_content=text, metadata=meta or {})
        docs.append(d)

    if not docs:
        return None

    retriever = BM25Retriever.from_documents(docs, k=BM25_POOL_K, preprocess_func=_jieba_tokenize)
    log(f"已构建 BM25 索引: {kb_id} ({len(docs)} 块)")
    return retriever


def get_bm25_retriever(kb_id=None):
    """获取指定 kb_id 的 BM25 索引（懒加载）。
    索引不存在（库为空）时返回 None，调用方应跳过 BM25 通道。
    """
    target_kb = kb_id if kb_id is not None else DEFAULT_KB_ID
    validate_kb_id(target_kb)
    if target_kb not in _bm25_retrievers:
        try:
            r = _build_bm25_for_kb(target_kb)
            _bm25_retrievers[target_kb] = r  # 可能为 None（空库），缓存避免反复重建
        except Exception as e:
            log(f"BM25 索引构建失败（降级到纯向量）: {e}")
            _bm25_retrievers[target_kb] = None
    return _bm25_retrievers[target_kb]


def invalidate(kb_id=None):
    """标记某库的 BM25 索引失效，下次搜索时重建。
    kb_id=None 时失效所有库（用于批量操作后）。
    """
    if kb_id is None:
        _bm25_retrievers.clear()
        return
    _bm25_retrievers.pop(kb_id, None)


def is_available():
    """检查 BM25 依赖是否可用（rank_bm25 + jieba）。"""
    try:
        import rank_bm25  # noqa: F401
        import jieba  # noqa: F401
        return True
    except ImportError:
        return False
