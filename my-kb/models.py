#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""模型与向量库管理（共享模型服务客户端 + vectorstore 单例）

2026-08-21 架构改造：embedding/reranker 不再在各会话进程内加载，
统一走共享模型服务（model_service.py，单实例占 GPU），见 service_client.py。
2026-08-31 演进：chroma 向量库与 BM25 索引同样上移共享服务常驻
（DLP 拦 DLL 致会话进程冷启动 import 达 179s），本进程经 RemoteVectorstore
HTTP 转发；服务不可用/无向量端点时回退本地 chroma 慢路径（旧行为）。
retriever 的 BM25 通道按 vector_mode() 分流（remote=服务端常驻索引）。
"""

import contextlib
import threading
import time
from pathlib import Path

from config import (
    MODEL_NAME, RERANKER_MODEL, DEFAULT_KB_ID,
    DEFAULT_SEARCH_KB_IDS, ALLOWED_KB_IDS,
    _vectorstores, _embeddings, _reranker,
)
from service_client import (
    RemoteEmbeddings, RemoteReranker, ensure_model_service,
    ping_vector_supported, vector_query, vector_get,
    vector_add_documents, vector_delete, bm25_query,
)
from utils import log, validate_kb_id, kb_vectordb_path

# 加载全局锁：后台 preload 线程与工具调用触发的懒加载共用一把锁，
# 防止多线程同时初始化。RLock 可重入（preload 内部还会调 get_reranker）。
_load_lock = threading.RLock()

# 模型服务不可用时的重试冷却：失败后 cooldown 秒内直接降级，不反复等待
_SERVICE_RETRY_COOLDOWN = 300
_service_fail_ts = 0.0

# ---- 2026-08-31 向量检索上移共享服务 ----
# 远程模式（服务持有 chroma+BM25）：None=未探测 / True=转发 / False=本地降级。
# 一旦探测失败，冷却期内不再探测（与 _SERVICE_RETRY_COOLDOWN 同款哲学）。
_remote_vector_mode = None
_remote_vector_fail_ts = 0.0
_REMOTE_VECTOR_RETRY_COOLDOWN = 600


class WarmupBusyError(RuntimeError):
    """本地降级路径下，向量库正被 preload 线程加载（冷启动 1~3 分钟）。

    server.py 顶层接住后快速返回友好提示，替代原来在 _load_lock 上
    排队到 180s 客户端超时的行为。远程模式无此问题（无锁无导入）。
    """


def _ensure_service_with_cooldown(timeout=150):
    """ensure + 冷却：服务确认不可用时，冷却期内不再反复等待（快速降级）。"""
    global _service_fail_ts
    if time.time() - _service_fail_ts < _SERVICE_RETRY_COOLDOWN:
        return False
    if ensure_model_service(wait_ready=True, timeout=timeout):
        return True
    _service_fail_ts = time.time()
    return False


# ============================================================================
# 远程向量库（2026-08-31）：chroma 上移共享服务后的会话端转发对象。
# 实现 chroma 调用面中被本项目用到的子集（读：向量查询/全量get；写：add/delete），
# retriever/indexer 零改动。构造零成本——不导入 chroma，不碰 _load_lock。
# ============================================================================

class RemoteVectorstore:
    """chroma 同接口的远程转发器（duck typing，仅实现项目实际调用的方法）。

    collection="main"（缺省）转发主库；"sections" 转发 H2 章节粗索引 collection。
    S3①：所有远程调用向 note_remote_* 上报成败——连续失败达阈值时
    翻回本地模式并逐出缓存对象，检索自动回退本地慢路径。
    """

    def __init__(self, kb_id, collection="main"):
        self.kb_id = kb_id
        self.collection = collection

    def similarity_search_by_vector_with_relevance_scores(self, embedding, k, filter=None):
        try:
            hits = vector_query(self.kb_id, embedding, k, where=filter,
                                collection=None if self.collection == "main" else self.collection)
        except Exception as e:
            note_remote_vector_failure(e)
            raise
        note_remote_vector_success()
        return hits

    def get(self, where=None):
        try:
            results = vector_get(self.kb_id, where=where,
                                 collection=None if self.collection == "main" else self.collection)
        except Exception as e:
            note_remote_vector_failure(e)
            raise
        note_remote_vector_success()
        return results

    def add_documents(self, documents):
        try:
            r = vector_add_documents(self.kb_id, documents,
                                     collection=None if self.collection == "main" else self.collection)
        except Exception as e:
            note_remote_vector_failure(e)
            raise
        note_remote_vector_success()
        return r

    def delete(self, ids):
        try:
            r = vector_delete(self.kb_id, ids,
                              collection=None if self.collection == "main" else self.collection)
        except Exception as e:
            note_remote_vector_failure(e)
            raise
        note_remote_vector_success()
        return r


# ---- S3① 远程模式回收：粘性 True 无回收路径的问题 ----
_REMOTE_FAIL_STREAK_LIMIT = 2
_remote_fail_streak = 0


def note_remote_vector_success():
    """远程向量调用成功：清零连败计数。"""
    global _remote_fail_streak
    _remote_fail_streak = 0


def note_remote_vector_failure(err):
    """远程向量调用失败：连败达阈值翻回本地模式 + 逐出远程缓存对象。

    翻转后 _REMOTE_VECTOR_RETRY_COOLDOWN（600s）内探测直接判 False，
    检索走本地 chroma 慢路径；冷却到期自动重探远程（服务恢复则切回）。
    """
    global _remote_vector_mode, _remote_vector_fail_ts, _remote_fail_streak
    _remote_fail_streak += 1
    if _remote_vector_mode is True and _remote_fail_streak >= _REMOTE_FAIL_STREAK_LIMIT:
        _remote_vector_mode = False
        _remote_vector_fail_ts = time.time()
        evicted = [k for k, v in _vectorstores.items() if isinstance(v, RemoteVectorstore)]
        for k in evicted:
            _vectorstores.pop(k, None)
        log(f"向量转发连续失败 {_remote_fail_streak} 次（{err}），"
            f"回退本地 chroma 路径，{_REMOTE_VECTOR_RETRY_COOLDOWN}s 后重探远程"
            f"（已逐出远程缓存: {evicted or '无'}）")


def vector_mode():
    """当前向量库访问模式："remote"（服务转发）或 "local"（进程内 chroma）。

    retriever 的 BM25 通道据此选择：remote → 服务端 /bm25（索引常驻、写后失效），
    local → bm25_manager（进程内构建）。
    """
    return "remote" if _probe_remote_vector() else "local"


def _probe_remote_vector(force=False):
    """探测服务是否支持向量转发；结果粘性，失败后冷却期内直接 False。

    force=True 供 preload 显式重试（服务可能刚被拉起/升级）。
    """
    global _remote_vector_mode, _remote_vector_fail_ts
    if _remote_vector_mode is True:
        return True
    if not force and _remote_vector_mode is False:
        if time.time() - _remote_vector_fail_ts < _REMOTE_VECTOR_RETRY_COOLDOWN:
            return False
    if not _ensure_service_with_cooldown(timeout=60):
        _remote_vector_mode = False
        _remote_vector_fail_ts = time.time()
        log("向量服务探测失败（共享服务不可用），本进程回退本地 chroma 路径")
        return False
    if ping_vector_supported():
        _remote_vector_mode = True
        return True
    _remote_vector_mode = False
    _remote_vector_fail_ts = time.time()
    log("共享服务无向量端点（老版本或 chroma 导入失败），本进程回退本地 chroma 路径")
    return False


# ---- 2026-08-27 冷启动竞态加固（runtime.log 11:00 事件：双进程并发打开同一 Chroma，
# 构造卡 161s 顶满客户端 180s 超时）----
# 1) 跨进程互斥：打开 Chroma 前抢项目目录锁文件，串行化 sqlite 打开/迁移；
#    等锁超时则放弃串行化直接打开（回退现状行为，绝不死锁）。
# 2) 细粒度计时：import 与单库构造各打耗时，下次再卡能直接区分
#    "锁互等 / DLP 拦 DLL / DLP 拦文件 IO"。

_CHROMA_OPEN_LOCK_PATH = Path(__file__).resolve().parent / "chroma_open.lock"
_CHROMA_OPEN_LOCK_WAIT_SEC = 120


@contextlib.contextmanager
def _cross_process_chroma_lock(timeout=_CHROMA_OPEN_LOCK_WAIT_SEC):
    """跨进程文件锁（Windows msvcrt / POSIX fcntl），yield 是否真正持锁。"""
    fh = open(_CHROMA_OPEN_LOCK_PATH, "a+b")
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
                    time.sleep(0.5)
        except ImportError:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            locked = True
        if not locked:
            log(f"[chroma-lock] 等锁 {timeout}s 超时，放弃串行化直接打开")
        yield locked
    finally:
        if locked:
            try:
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            except (ImportError, OSError):
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        fh.close()


def _open_chroma_store(kb_id, create=False, embeddings=None, collection="main"):
    """打开（create=True 时按需创建目录）指定库的 Chroma：跨进程互斥 + 耗时计时。

    collection="sections" 时打开同一 persist 目录下的 <kb>_sections 命名 collection
    （与 model_service._open_store 同名约定）；缺省 main=langchain 默认 collection。
    """
    from langchain_chroma import Chroma
    vectordb_path = kb_vectordb_path(kb_id)
    if create:
        vectordb_path.mkdir(parents=True, exist_ok=True)
    cache_key = kb_id if collection == "main" else f"{kb_id}::sections"
    t0 = time.perf_counter()
    with _cross_process_chroma_lock():
        kwargs = {"persist_directory": str(vectordb_path),
                  "embedding_function": embeddings if embeddings is not None else get_embeddings()}
        if collection == "sections":
            kwargs["collection_name"] = f"{kb_id}_sections"
        store = Chroma(**kwargs)
        t_construct = time.perf_counter() - t0  # 含等锁时间
    dt_total = time.perf_counter() - t0
    _vectorstores[cache_key] = store
    note = ""
    if t_construct > 10:
        note = f"（构造含等锁 {t_construct:.1f}s ⚠>10s，需查 [chroma-lock] 日志区分锁等待/文件 IO）"
    elif dt_total > 3:
        note = f"（{dt_total:.1f}s）"
    log(f"已加载库: {cache_key}{note}")
    return store


def preload(kb_ids=None):
    """预加载：拉起共享模型服务 + 建立远程模型对象 + （按模式）加载向量库。

    kb_ids: 预加载哪些库；None 则预加载 DEFAULT_SEARCH_KB_IDS 中存在的库。
    在后台线程执行（server.py 入口），等待模型就绪不阻塞 stdio 握手。

    2026-08-31 远程模式（服务带 /vector_* 端点）：向量库与 BM25 均由服务
    常驻持有，本进程只建轻量转发对象——**不再 import langchain_chroma**，
    冷启动从 179s 级（DLP 拦 DLL）降到秒级。服务端预开库由 model_service
    的 preopen-stores 线程负责。服务不支持 /vector_* 时回退本地慢路径（旧行为）。
    """
    global _embeddings

    with _load_lock:
        log(f"模型在共享服务进程内加载（{MODEL_NAME} / {RERANKER_MODEL}），本进程仅 HTTP 转发")
        if _ensure_service_with_cooldown():
            log("共享模型服务就绪")
        else:
            log("共享模型服务未就绪：向量通道将降级 BM25，重排降级规则加权")

        if _embeddings is None:
            # 轻对象：真实模型在共享服务里，首次 embed 时走 HTTP
            _embeddings = RemoteEmbeddings()

        targets = kb_ids if kb_ids is not None else DEFAULT_SEARCH_KB_IDS
        targets = [k for k in targets if k in ALLOWED_KB_IDS and kb_vectordb_path(k).exists()]

        if _probe_remote_vector(force=True):
            log("向量检索与 BM25 已上移共享服务（chroma 服务端常驻），本进程零 chroma 导入")
            for kb_id in targets:
                _vectorstores[kb_id] = RemoteVectorstore(kb_id)
        else:
            log("共享服务无向量端点（老服务或导入失败），回退本地 chroma 路径")
            t_imp0 = time.perf_counter()
            from langchain_chroma import Chroma  # 首次 import 走 DLL/模块加载层，DLP 嫌疑点
            t_imp = time.perf_counter() - t_imp0
            if t_imp > 1.0:
                log(f"[preload-timing] import langchain_chroma 耗时 {t_imp:.1f}s（>1s：DLL/模块加载层慢，DLP 嫌疑）")
            for kb_id in targets:
                _open_chroma_store(kb_id, embeddings=_embeddings)

        # 预热 reranker 引用（远程对象，服务端 warmup 在服务内完成）
        get_reranker()
        log("预加载完成")

    if _remote_vector_mode is not True:
        # 预热 BM25 内存索引：全量拉库+jieba 分词较慢，放锁外（不阻塞懒加载），
        # 避免首次搜索才构建导致的首查延迟。远程模式 BM25 在服务端常驻，无需本进程预热。
        try:
            from bm25_manager import get_bm25_retriever, is_available
            if is_available():
                for cur_kb in list(_vectorstores.keys()):
                    if isinstance(_vectorstores[cur_kb], RemoteVectorstore):
                        continue  # 远程对象无 BM25 可预热（索引在服务端）
                    get_bm25_retriever(cur_kb)
                log("BM25 索引预热完成")
        except Exception as e:
            log(f"BM25 预热失败（忽略，首次搜索时按需构建）: {e}")


def get_embeddings():
    """获取全局远程嵌入对象（langchain Embeddings 接口，HTTP 转发）。"""
    global _embeddings
    with _load_lock:
        if _embeddings is None:
            _embeddings = RemoteEmbeddings()
        return _embeddings


def get_reranker():
    """获取全局远程重排对象（predict 接口兼容原 CrossEncoder）。
    共享服务不可用时返回 None，调用方应降级到规则重排。
    """
    global _reranker
    with _load_lock:
        if _reranker is None:
            if _ensure_service_with_cooldown(timeout=120):
                _reranker = RemoteReranker()
            else:
                log("模型服务不可用，reranker 降级到规则重排")
                return None
        return _reranker


def get_vectorstore(kb_id=None):
    """获取指定 kb_id 的向量库；kb_id=None 时返回默认库（向后兼容老调用）。

    远程模式：返回 RemoteVectorstore（HTTP 转发，零导入零锁）。
    本地降级模式：若目标库目录尚不存在，按需创建空 Chroma（首次写入时自动落地目录）。
    2026-08-31 快速失败：本地模式下若 preload 正在加载（_load_lock 被后台线程
    持有），立即抛 WarmupBusyError 而不是排队等锁——避免客户端 180s 超时。
    """
    target_kb = kb_id if kb_id is not None else DEFAULT_KB_ID
    return _get_store_object(target_kb, "main", create=True)


def get_section_vectorstore(kb_id=None):
    """获取 sections 章节粗索引 collection 的访问对象（远程转发 / 本地命名 collection 同构）。

    远程模式返回 RemoteVectorstore(collection="sections")；本地降级在主库同一
    persist 目录下打开 <kb>_sections 命名 collection（与 model_service._open_store 同名，
    两端读写同一份索引）。
    """
    target_kb = kb_id if kb_id is not None else DEFAULT_KB_ID
    return _get_store_object(target_kb, "sections", create=True)


def _get_store_object(kb_id, collection, create=False):
    """main/sections 两类 collection 访问对象的公共获取路径（缓存键带 collection）。"""
    target_kb = kb_id if kb_id is not None else DEFAULT_KB_ID
    validate_kb_id(target_kb)
    cache_key = target_kb if collection == "main" else f"{target_kb}::sections"
    if cache_key not in _vectorstores:
        if _probe_remote_vector():
            store = RemoteVectorstore(target_kb,
                                      collection=None if collection == "main" else collection)
            _vectorstores[cache_key] = store
            return store
        # 本地降级路径：非阻塞抢锁，抢不到=preload 正在冷启动
        if not _load_lock.acquire(blocking=False):
            raise WarmupBusyError(
                "知识库预热中（本地降级路径正在导入 chroma，冷启动约 1~3 分钟），"
                "请稍后重试；服务端向量模式正常时不走此路径")
        try:
            if cache_key not in _vectorstores:
                if collection == "sections":
                    _open_chroma_store(target_kb, create=create, collection="sections")
                else:
                    _open_chroma_store(target_kb, create=create)
        finally:
            _load_lock.release()
    return _vectorstores[cache_key]


def warmup_busy():
    """本地降级路径的 preload 是否正在进行（远程模式恒 False）。

    供检索入口快速失败用：busy 时直接抛 WarmupBusyError 返回"预热中"提示，
    替代在 _load_lock 上排队到客户端超时。判定=非阻塞抢锁，抢到立即释放。
    """
    if _remote_vector_mode is True:
        return False
    if _remote_vector_mode is None:
        return False  # 尚未探测：让正常路径去探测，避免误报
    acquired = _load_lock.acquire(blocking=False)
    if acquired:
        _load_lock.release()
        return False
    return True
