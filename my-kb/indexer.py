#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""索引管理：单文件索引 / 批量索引 / 重建 / 脏数据清理"""

from pathlib import Path
from langchain_core.documents import Document

from config import KB_ROOT, DEFAULT_KB_ID, CHUNK_SIZE, CHUNK_OVERLAP
from models import get_vectorstore
from preprocessing import process_document
from utils import log, validate_kb_id, is_safe_filename, kb_markdown_dir


def _find_raw_file(kb_id, filename):
    """在 raw/markdown 和 raw/pdf 中查找文件，返回 Path 或 None。"""
    for sub_dir in ["markdown", "pdf"]:
        p = KB_ROOT / kb_id / "raw" / sub_dir / filename
        if p.exists():
            return p
    return None


def _delete_source_chunks(vectorstore, source):
    """删除向量库中指定 source 的所有旧 chunk。

    S7：where 精确拉取（chroma 原生过滤），批量重建时免每文件一次全量 get；
    where 语义与原 python 侧 `m.get("source") == source` 等价（本地/远程同构）。
    """
    try:
        results = vectorstore.get(where={"source": source})
        ids = list(results.get("ids", []))
        if ids:
            vectorstore.delete(ids=list(ids))
            log(f"删除 {len(ids)} 个旧 chunk (source={source})")
    except Exception as e:
        log(f"删除旧 chunk 时出错（继续写入）: {e}")


def purge_orphan_sources(kb_id):
    """清理向量库中的孤儿 source（磁盘文件已不存在的残留块）。
    返回 (清理的source数, 清理的块数)。
    """
    vs = get_vectorstore(kb_id)
    results = vs.get()
    vs_sources = set()
    for m in results.get("metadatas", []):
        if m and "source" in m:
            vs_sources.add(m["source"])
    disk_files = set()
    for sub_dir in ["markdown", "pdf"]:
        dir_path = KB_ROOT / kb_id / "raw" / sub_dir
        if dir_path.exists():
            disk_files.update(f.name for f in dir_path.glob("*") if f.is_file())
    orphans = vs_sources - disk_files
    deleted = 0
    for orphan in orphans:
        ids = [results["ids"][i] for i, m in enumerate(results.get("metadatas", []))
               if m and m.get("source") == orphan]
        if ids:
            vs.delete(ids=ids)
            deleted += len(ids)
            log(f"清理孤儿 source: {orphan} ({len(ids)} 块)")
    # 清理后失效 BM25 索引
    if orphans:
        try:
            from bm25_manager import invalidate
            invalidate(kb_id)
        except Exception:
            pass
        # sections 章节粗索引同步清理（门控）
        for orphan in orphans:
            try:
                from section_index import delete_source_sections
                delete_source_sections(kb_id, orphan)
            except Exception:
                pass
    return len(orphans), deleted


def index_file(filename, kb_id=DEFAULT_KB_ID, category=None, module=None, tags=None):
    """索引单个文件（先删后加）。返回 (success, message)。
    使用 preprocessing.process_document 做两阶段分块。
    """
    validate_kb_id(kb_id)
    vectorstore = get_vectorstore(kb_id)

    if not filename:
        return False, "错误: 文件名不能为空"
    if not is_safe_filename(filename):
        return False, "错误: 文件名包含非法字符"

    file_path = _find_raw_file(kb_id, filename)
    if not file_path:
        return False, f"错误: 未找到文件 {filename}"

    # 读取文件
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        try:
            from langchain_community.document_loaders import PyPDFLoader
            loader_docs = PyPDFLoader(str(file_path)).load()
            content = "\n\n".join(d.page_content for d in loader_docs)
        except Exception as e:
            return False, f"错误: 读取PDF失败 - {e}"
    else:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            return False, f"错误: 读取文件失败 - {e}"

    # 构造 overrides
    overrides = {}
    if category is not None:
        overrides["category"] = category
    if module is not None:
        overrides["module"] = module
    if tags is not None:
        overrides["tags"] = tags

    # 预处理（frontmatter + 两阶段分块 + 元数据合并）
    if suffix == ".pdf":
        # PDF 无 frontmatter，直接分块
        from preprocessing import split_document, build_chunk_metadata
        chunks = split_document(content)
        meta = build_chunk_metadata(filename, {}, {}, overrides)
        for chunk in chunks:
            chunk.metadata = dict(meta)
    else:
        chunks = process_document(content, filename, overrides=overrides)

    if not chunks:
        return False, f"错误: 文件 {filename} 分块后无内容"

    # 先删后加
    _delete_source_chunks(vectorstore, filename)

    # 写入
    documents = [Document(page_content=c.page_content, metadata=dict(c.metadata))
                 for c in chunks]
    vectorstore.add_documents(documents)
    meta = chunks[0].metadata
    log(f"添加 {len(chunks)} 个文档块到库 {kb_id}（{meta.get('source')}）")

    # 失效 BM25 索引（下次搜索时按需重建）
    try:
        from bm25_manager import invalidate
        invalidate(kb_id)
    except Exception:
        pass

    # sections 章节粗索引增量维护（SECTION_INDEX_ENABLED 门控，flag 关闭时零开销）
    try:
        from section_index import rebuild_for_source
        rebuild_for_source(kb_id, filename)
    except Exception:
        pass

    return True, (f"索引成功（库 {kb_id}）:\n- 文件: {filename}\n- 分块数量: {len(chunks)}\n"
                  f"- 分类: {meta.get('category')}\n- 模块: {meta.get('module')}\n- 标签: {meta.get('tags')}")


def index_all_files(kb_id=DEFAULT_KB_ID, category=None, module=None, force=False):
    """批量索引。force=True 时先清理脏数据再全量重建。
    返回 (indexed_count, failed_list)。
    """
    validate_kb_id(kb_id)
    vectorstore = get_vectorstore(kb_id)

    # 扫描 raw 目录
    raw_path = KB_ROOT / kb_id / "raw"
    all_files = []
    for sub_dir in ["markdown", "pdf"]:
        dir_path = raw_path / sub_dir
        if dir_path.exists():
            for file in dir_path.glob("*"):
                if file.is_file() and file.suffix.lower() in [".md", ".pdf", ".txt"]:
                    all_files.append(file.name)

    # 获取已索引文件
    existing_results = vectorstore.get()
    indexed_files = set()
    for metadata in existing_results.get("metadatas", []):
        if metadata and "source" in metadata:
            indexed_files.add(metadata["source"])

    # force 模式先清理脏数据
    if force:
        purged_sources, purged_chunks = purge_orphan_sources(kb_id)
        if purged_sources:
            log(f"清理孤儿 source: {purged_sources} 个 ({purged_chunks} 块)")
            # 清理后重新获取
            existing_results = vectorstore.get()
            indexed_files = set()
            for metadata in existing_results.get("metadatas", []):
                if metadata and "source" in metadata:
                    indexed_files.add(metadata["source"])
        files_to_process = all_files
    else:
        files_to_process = [f for f in all_files if f not in indexed_files]

    if not files_to_process:
        return 0, [], "所有文件已索引，无需处理"

    indexed_count = 0
    failed = []
    for filename in files_to_process:
        try:
            # force 模式先删旧
            if force:
                _delete_source_chunks(vectorstore, filename)
            overrides = {}
            if category:
                overrides["category"] = category
            if module:
                overrides["module"] = module
            success, msg = index_file(filename, kb_id, **overrides)
            if success:
                indexed_count += 1
            else:
                failed.append(f"{filename}: {msg}")
        except Exception as e:
            failed.append(f"{filename}: {e}")

    return indexed_count, failed, ("重建" if force else "新索引")


def sync_rebuild(kb_id, force=True):
    """同步全量重建（供 rebuild_index_async 在线程池中调用）。"""
    log(f"[异步重建] 开始处理库 {kb_id} (force={force})")
    vectorstore = get_vectorstore(kb_id)

    # force 模式先清理脏数据
    if force:
        purged_sources, purged_chunks = purge_orphan_sources(kb_id)
        if purged_sources:
            log(f"[异步重建] 清理孤儿 source: {purged_sources} 个 ({purged_chunks} 块)")

    raw_path = KB_ROOT / kb_id / "raw"
    all_files = []
    for sub_dir in ["markdown", "pdf"]:
        dir_path = raw_path / sub_dir
        if dir_path.exists():
            for file in dir_path.glob("*"):
                if file.is_file() and file.suffix.lower() in [".md", ".pdf", ".txt"]:
                    all_files.append(file.name)
    log(f"[异步重建] 待处理 {len(all_files)} 个文件")

    indexed = 0
    failed = []
    for idx, filename in enumerate(all_files, 1):
        try:
            if force:
                _delete_source_chunks(vectorstore, filename)
            success, msg = index_file(filename, kb_id)
            if success:
                indexed += 1
            else:
                failed.append(f"{filename}: {msg}")
            if idx % 10 == 0:
                log(f"[异步重建] 进度 {idx}/{len(all_files)}")
        except Exception as e:
            failed.append(f"{filename}: {e}")

    log(f"[异步重建] 完成: 成功 {indexed}/{len(all_files)}, 失败 {len(failed)}")
    if failed:
        log(f"[异步重建] 失败详情: {failed}")

    # 全量重建后失效 BM25 索引
    try:
        from bm25_manager import invalidate
        invalidate(kb_id)
    except Exception:
        pass
