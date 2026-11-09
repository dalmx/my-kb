#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""索引管理：单文件索引 / 批量索引 / 重建 / 脏数据清理"""

import hashlib
import json
import re
from pathlib import Path
from langchain_core.documents import Document

from config import KB_ROOT, DEFAULT_KB_ID, CHUNK_SIZE, CHUNK_OVERLAP
from models import get_vectorstore
from preprocessing import process_document
from utils import log, validate_kb_id, is_safe_filename, kb_markdown_dir

# 文档级哈希侧车（2026-11-09 性能治理第一步）：{kb_id::filename: 指纹}，
# 内容+索引参数均未变则跳过整篇重嵌入（幂等重存/重复 index_file 场景）。
# 放服务目录不入 git（基线只跟踪 knowledge/，运行时缓存随生成随用）；残留 stale 键无害
# （下次同名文件内容变即失配照常索引，delete/move 不主动清理）
_HASH_SIDE_CAR = Path(__file__).resolve().parent / "index_hash.json"


def _load_hash_map():
    """读哈希侧车（hit_counts.json 同款 best-effort；失败返回空 dict=全量重嵌兜底）。"""
    try:
        return json.loads(_HASH_SIDE_CAR.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_hash_map(m):
    try:
        _HASH_SIDE_CAR.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass  # 侧车写失败不影响索引（下次多余重嵌而已）


def _content_fingerprint(content, overrides):
    """内容指纹：排除 frontmatter 的 updated 行（save/append 无条件刷今天，
    不排除则哈希永不命中）+ 拼接索引参数（参数变则须重嵌刷新元数据）。"""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", content, flags=re.S)
    if m:
        fm = re.sub(r"^updated\s*:.*$", "", m.group(1), flags=re.M)
        body = content[m.end():]
    else:
        fm, body = "", content
    ov = json.dumps({k: overrides.get(k) for k in sorted(overrides)}, ensure_ascii=False)
    return hashlib.sha256((fm + "\x00" + body + "\x00" + ov).encode("utf-8", "replace")).hexdigest()


def _find_raw_file(kb_id, filename):
    """在 raw/markdown 和 raw/pdf 中查找文件，返回 Path 或 None。"""
    for sub_dir in ["markdown", "pdf"]:
        p = KB_ROOT / kb_id / "raw" / sub_dir / filename
        if p.exists():
            return p
    return None


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


def index_file(filename, kb_id=DEFAULT_KB_ID, category=None, module=None, tags=None, use_hash_cache=True):
    """索引单个文件（add-then-prune 先写后剪，2026-10-30 换序防消失）。返回 (success, message)。
    使用 preprocessing.process_document 做两阶段分块。
    use_hash_cache=True（默认）走文档级哈希快路径：内容+参数未变跳过重嵌入；
    force 全量重建传 False——只跳过检查、成功后仍刷新侧车。
    语义注记：跳过时向量块 updated 保持旧值 = "最后内容变更日"语义，可接受。
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

    # 哈希快路径：内容（排除 updated 行）与索引参数均未变 → 跳过分块/嵌入/写库
    _hkey = f"{kb_id}::{filename}"
    _fp = _content_fingerprint(content, overrides)
    if use_hash_cache and _load_hash_map().get(_hkey) == _fp:
        log(f"索引跳过（内容哈希未变）: {filename}")
        return True, f"索引跳过（库 {kb_id}）: 内容与上次索引一致（哈希命中），未重嵌入\n- 文件: {filename}"

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

    # add-then-prune 换序（2026-10-30 防消失）：远程模式由服务端 /vector_write 在推理锁
    # 临界区内先写后剪；本地降级路径 add_texts 生成随机 uuid4（无法同号覆写），故先取
    # 旧 id、写入后按旧 id 清理——两种模式中断在任何时点文档都不消失，下次成功索引自愈
    from models import vector_mode
    old_ids = []
    if vector_mode() == "local":
        results = vectorstore.get(where={"source": filename})
        old_ids = list(results.get("ids", []))

    # 写入
    documents = [Document(page_content=c.page_content, metadata=dict(c.metadata))
                 for c in chunks]
    vectorstore.add_documents(documents)
    if old_ids:
        vectorstore.delete(ids=old_ids)
    meta = chunks[0].metadata
    log(f"添加 {len(chunks)} 个文档块到库 {kb_id}（{meta.get('source')}）")

    # 成功后刷新哈希侧车（重读防覆盖并发更新；force 重建也走到这里）
    try:
        hm = _load_hash_map()
        hm[_hkey] = _fp
        _save_hash_map(hm)
    except Exception:
        pass

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
            overrides = {}
            if category:
                overrides["category"] = category
            if module:
                overrides["module"] = module
            success, msg = index_file(filename, kb_id, use_hash_cache=not force, **overrides)
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
            success, msg = index_file(filename, kb_id, use_hash_cache=False)
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
