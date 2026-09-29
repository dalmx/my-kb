#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""共享模型服务：单实例加载 embedding + reranker，所有 my-kb 会话进程经 HTTP 复用。

为什么存在：stdio 模式下每个 ZCode 会话 spawn 一个独立 server 进程，各自把
bge-large + bge-reranker 加载进 GPU（单进程 ~2.6GB 显存），多会话并发时显存
翻倍且推理互相争抢导致超时。本服务把模型收敛为单实例：

- 生命周期：SessionStart hook / 首次使用时被拉起（detached，不随会话退出），
  空闲 MODEL_SERVICE_IDLE_EXIT_SEC 自动退出释放显存
- 端点（只监听 127.0.0.1）：
    GET  /ping    → {"ready": bool, "vector": bool}（ready=模型加载+warmup 完成；
                    vector=向量检索端点可用，客户端据此决定转发还是本地降级）
    POST /embed   {"texts": [...]}        → {"embeddings": [[...], ...]}
    POST /rerank  {"pairs": [[q, d], ..]} → {"scores": [...]}
    POST /vector_query {"kb_id","embedding","k","where"} → {"hits": [[content, meta, distance], ..]}
    POST /vector_get   {"kb_id"}           → {"ids","documents","metadatas"}（全量拉取）
    POST /vector_write {"kb_id","action":"add"/"delete",...} → 写 chroma 并失效 BM25 缓存
    POST /bm25         {"kb_id","query","k"} → {"docs": [{content, metadata}, ...]}
- 2026-08-31 向量检索上移：chroma 实例与 BM25 索引收敛到本服务单进程持有
  （此前每个会话进程 import langchain_chroma，DLP 拦 DLL 冷启动实测 179s 顶满
  180s 客户端超时；上移后服务常驻导入一次，会话进程零 chroma/torch 导入，
  同时消除多进程并发开同一 chroma 的锁竞争）。chroma 打开失败不致命：
  /vector_* /bm25 返回 503，客户端自动回退本地慢路径（即旧行为）。
- 降级：reranker 加载失败时服务继续运行（/rerank 返回 503，调用方降级规则重排），
  与原 get_reranker 的降级哲学一致
- 手动调试：python model_service.py（日志到 stderr）
"""

import os

# 与 ZCode config.json my-kb env 保持一致：模型已全在本地缓存，跳过在线检查
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import json
import contextlib
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from config import (
    MODEL_NAME, RERANKER_MODEL, detect_device,
    MODEL_SERVICE_HOST, MODEL_SERVICE_PORT, MODEL_SERVICE_IDLE_EXIT_SEC,
    BM25_POOL_K,
)
from utils import log, validate_kb_id, kb_vectordb_path

# 与 models.py 会话端同一把跨进程开库互斥锁（S2：滚动升级窗口期与新/旧进程互斥）
_CHROMA_OPEN_LOCK_PATH = Path(__file__).resolve().parent / "chroma_open.lock"

_state = {"ready": False, "started_at": time.time(), "last_request": time.time()}
_infer_lock = threading.Lock()  # torch 推理串行化（GPU 本就串行，避免并发内部状态问题)
_embeddings_model = None
_reranker_model = None

# ---- 向量库 / BM25（2026-08-31 上移到服务进程单点持有）----
_stores = {}            # {kb_id: Chroma 实例}
# RLock（CC 审查 B1 修复）：_get_bm25 持锁内会调 _open_store 再取同一把锁，
# threading.Lock 非重入曾致 /bm25 首调即永久死锁（复现脚本 6s 卡死实测）
_store_open_lock = threading.RLock()     # 串行化 chroma 打开/BM25 重建
_bm25_retrievers = {}   # {kb_id: BM25Retriever}（vector_write 后失效重建）
_bm25_gen = {}          # {kb_id: int} 写入代际（S1：构建期间有写则丢弃重建，防陈旧索引）
_chroma_import_ok = None  # None=未试 True/False=导入结果（失败则 /vector_* 持续 503）


def _invalidate_bm25(kb_id):
    """写后失效 BM25 缓存：pop 与代际自增同持锁，与 _get_bm25 构建临界区互斥。"""
    with _store_open_lock:
        _bm25_gen[kb_id] = _bm25_gen.get(kb_id, 0) + 1
        _bm25_retrievers.pop(kb_id, None)


@contextlib.contextmanager
def _cross_process_chroma_lock(timeout=120):
    """与 models.py 会话端共用的 chroma_open.lock 文件锁（CC 审查 S2 补齐）。

    滚动升级窗口内，旧代码会话进程（本地开 chroma、走此锁）与新服务同时开库，
    复刻 2026-08-27 双进程并发开库卡 161s 的事故条件；等锁超时则放弃串行化
    直接打开（与会话端同哲学：绝不死锁）。
    """
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
            log("[model-service] 等跨进程 chroma 锁超时，放弃串行化直接打开")
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


def _load_models():
    """后台线程：加载 embedding + reranker 并 warmup，成功后置 ready。

    2026-09-04 fp16 定案：4060 8GB 上 Qwen3-Embedding(2.4GB fp32) + reranker
    fp32 顶满显存触发 NVIDIA sysmem 回退，长文档 rerank 实测 49ms→2100ms；
    双 fp16 后参数 3.5→1.75GB。加载后显式验证参数 dtype，防 transformers
    4.56 起 torch_dtype→dtype 更名导致的 fp16 静默失效。
    """
    global _embeddings_model, _reranker_model
    import torch
    device = detect_device()
    use_fp16 = device == "cuda"
    try:
        from sentence_transformers import SentenceTransformer
        log(f"[model-service] 加载嵌入模型 {MODEL_NAME} (device={device}, fp16={use_fp16})...")
        st_kwargs = {"model_kwargs": {"dtype": torch.float16}} if use_fp16 else {}
        st = SentenceTransformer(MODEL_NAME, device=device, **st_kwargs)
        actual = next(st[0].auto_model.parameters()).dtype
        if use_fp16 and actual != torch.float16:
            raise RuntimeError(f"fp16 未生效（实际 {actual}），检查 transformers 版本")

        class _STEmbeddings:
            """SentenceTransformer 薄包装：langchain Embeddings duck-typing 接口。
            langchain_huggingface.HuggingFaceEmbeddings 不支持 client= 注入，
            而 model_kwargs 嵌套传 dtype 在其透传链路上有静默失效风险，故自包装。"""

            def __init__(self, st):
                self._st = st

            def embed_documents(self, texts):
                return self._st.encode([str(t) for t in texts],
                                       normalize_embeddings=True).tolist()

            def embed_query(self, text):
                # Qwen3-Embedding 官方要求：查询侧加 instruct 前缀（模型 prompts
                # 配置里的 "query" 项），文档侧不加——故仅此方法带 prompt_name，
                # 索引向量（embed_documents）不受影响，改前缀无需重建索引
                return self._st.encode(str(text), normalize_embeddings=True,
                                       prompt_name="query").tolist()

        _embeddings_model = _STEmbeddings(st)
    except Exception as e:
        # embedding 是向量检索的根基，加载失败则服务无意义
        log(f"[model-service] 嵌入模型加载失败，服务退出: {e}")
        os._exit(1)

    try:
        log(f"[model-service] 加载 reranker {RERANKER_MODEL} ...")
        if RERANKER_MODEL.startswith("Qwen/Qwen3-Reranker"):
            # Qwen3-Reranker 是因果语言模型，不能走 CrossEncoder；包装类
            # predict(pairs) 接口与 CrossEncoder 兼容，其余调用方零改动
            from qwen3_reranker import Qwen3Reranker
            _reranker_model = Qwen3Reranker(RERANKER_MODEL, device=device)
        else:
            from sentence_transformers import CrossEncoder
            ce_kwargs = {"automodel_args": {"dtype": torch.float16}} if use_fp16 else {}
            _reranker_model = CrossEncoder(RERANKER_MODEL, device=device, **ce_kwargs)
            actual = next(_reranker_model.model.parameters()).dtype
            if use_fp16 and actual != torch.float16:
                # CC 审查问题④修复：fp32 reranker 正是 2100ms sysmem 事故形态，
                # 慢跑比 503 降级（走规则重排）更有害——与嵌入路径同哲学，硬失败
                raise RuntimeError(f"CrossEncoder fp16 未生效（实际 {actual}）")
    except Exception as e:
        # reranker 失败可降级（调用方走规则重排），服务继续提供 embed
        log(f"[model-service] reranker 加载失败（/rerank 将返回 503）: {e}")
        _reranker_model = None

    try:
        with _infer_lock:
            _embeddings_model.embed_query("预热")
            if _reranker_model is not None:
                _reranker_model.predict([("预热", "预热")])
        log("[model-service] warmup 完成")
    except Exception as e:
        log(f"[model-service] warmup 出错（忽略）: {e}")

    _state["ready"] = True
    log("[model-service] 就绪，等待请求")


def _idle_watchdog():
    """空闲自动退出：释放 GPU 显存，下次使用时由调用方自动重新拉起。"""
    while True:
        time.sleep(60)
        idle = time.time() - _state["last_request"]
        if idle > MODEL_SERVICE_IDLE_EXIT_SEC:
            log(f"[model-service] 空闲 {int(idle)}s 超过 {MODEL_SERVICE_IDLE_EXIT_SEC}s，自动退出")
            os._exit(0)


# ============================================================================
# 向量库 / BM25（与模型推理共用本进程，chroma 单写者）
# ============================================================================

def _open_store(kb_id, collection="main"):
    """打开（含首次 import langchain_chroma）指定库的 Chroma；失败返回 None。

    collection="main"：默认 collection（langchain 默认名，存量向量都在此，不可改名）；
    collection="sections"：H2 章节级粗索引，同一 persist 目录下的 <kb>_sections collection。
    导入失败（DLP 拦 DLL 等）标记粘性失败，后续 /vector_* 快速 503，
    客户端回退本地路径；重启服务可重试。
    """
    global _chroma_import_ok
    cache_key = f"{kb_id}:{collection}"
    if cache_key in _stores:
        return _stores[cache_key]
    if _chroma_import_ok is False:
        return None
    with _store_open_lock:
        if cache_key in _stores:
            return _stores[cache_key]
        try:
            t0 = time.perf_counter()
            from langchain_chroma import Chroma
            if _chroma_import_ok is None:
                _chroma_import_ok = True
                log(f"[model-service] import langchain_chroma 耗时 {time.perf_counter() - t0:.1f}s（服务常驻，仅此一次）")
            with _cross_process_chroma_lock():
                if collection == "sections":
                    # sections 粗索引：同目录命名 collection，与主库互不干扰
                    store = Chroma(
                        persist_directory=str(kb_vectordb_path(kb_id)),
                        collection_name=f"{kb_id}_sections",
                        embedding_function=_embeddings_model,
                    )
                else:
                    # 主库：不传 collection_name（langchain 默认名），存量向量在此
                    store = Chroma(
                        persist_directory=str(kb_vectordb_path(kb_id)),
                        embedding_function=_embeddings_model,
                    )
        except ImportError as e:
            _chroma_import_ok = False
            log(f"[model-service] langchain_chroma 导入失败（/vector_* 持续 503，重启服务可重试）: {e}")
            return None
        except Exception as e:
            log(f"[model-service] chroma 打开失败（/vector_* 将 503）: {e}")
            return None
        _stores[cache_key] = store
        log(f"[model-service] 已加载库 {cache_key}（服务进程常驻）")
        return store


def _payload_collection(payload):
    """解析请求里的可选 collection 字段（main|sections 白名单），返回 (collection, err)。"""
    col = payload.get("collection") or "main"
    if col not in ("main", "sections"):
        return None, "collection 仅支持 main/sections"
    return col, None


def _jieba_tokenize(text):
    """BM25 preprocess_func：与 bm25_manager 保持一致（jieba 分词，中文必须分词）。"""
    import jieba
    return [w for w in jieba.lcut(text) if w.strip()]


def _get_bm25(kb_id):
    """获取服务端 BM25 索引（从 chroma 全量拉取构建，vector_write 后失效重建）。

    与 bm25_manager._build_bm25_for_kb 同构；此处不能复用 bm25_manager（它
    import models 会在服务进程内再开一份 chroma）。
    S1 代际护栏：构建读快照期间若有写入（gen 变化），丢弃本次构建重试一轮，
    防止"旧快照索引在写失效之后落缓存"造成的永久陈旧。
    """
    if kb_id in _bm25_retrievers:
        return _bm25_retrievers[kb_id]
    for _attempt in range(2):
        with _store_open_lock:
            if kb_id in _bm25_retrievers:
                return _bm25_retrievers[kb_id]
            store = _open_store(kb_id)  # RLock 可重入（B1 修复）
            if store is None:
                _bm25_retrievers[kb_id] = None
                return None
            try:
                from langchain_community.retrievers import BM25Retriever
                from langchain_core.documents import Document
                gen_before = _bm25_gen.get(kb_id, 0)
                results = store.get()
                docs = [Document(page_content=t, metadata=m or {})
                        for t, m in zip(results.get("documents", []), results.get("metadatas", [])) if t]
                if not docs:
                    if _bm25_gen.get(kb_id, 0) == gen_before:
                        _bm25_retrievers[kb_id] = None
                        return None
                    continue  # 构建期间有写，重试
                retriever = BM25Retriever.from_documents(
                    docs, k=BM25_POOL_K, preprocess_func=_jieba_tokenize)
                if _bm25_gen.get(kb_id, 0) != gen_before:
                    continue  # 构建期间有写，丢弃本次索引重建
                _bm25_retrievers[kb_id] = retriever
                log(f"[model-service] 已构建 BM25 索引: {kb_id} ({len(docs)} 块，服务常驻)")
                return retriever
            except Exception as e:
                log(f"[model-service] BM25 构建失败（该库 BM25 通道降级）: {e}")
                _bm25_retrievers[kb_id] = None
                return None
    return None


def _preopen_stores():
    """模型就绪后后台预开默认库：首次 import 保温 DLL 缓存 + 首查免开库延迟。

    等待 ready 是因为 Chroma 构造要挂 embedding_function（add_documents 用），
    且预开本身不急——不阻塞任何请求路径。
    """
    deadline = time.time() + 600
    while not _state["ready"] and time.time() < deadline:
        time.sleep(2.0)
    try:
        from config import DEFAULT_SEARCH_KB_IDS, ALLOWED_KB_IDS
        for kb_id in DEFAULT_SEARCH_KB_IDS:
            if kb_id in ALLOWED_KB_IDS and kb_vectordb_path(kb_id).exists():
                _open_store(kb_id)
                _get_bm25(kb_id)
    except Exception as e:
        log(f"[model-service] 预开库失败（忽略，按需懒开）: {e}")


class _Handler(BaseHTTPRequestHandler):
    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/ping":
            # vector 标志：客户端据此决定向量检索走转发还是本地降级（老服务无此字段）
            self._json({"ready": _state["ready"], "vector": _chroma_import_ok is not False})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        _state["last_request"] = time.time()
        if not _state["ready"]:
            self._json({"error": "model not ready"}, 503)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception as e:
            self._json({"error": f"bad request: {e}"}, 400)
            return

        try:
            if self.path == "/embed":
                texts = [str(t) for t in payload.get("texts", [])]
                if not texts:
                    self._json({"error": "texts 为空"}, 400)
                    return
                with _infer_lock:
                    # 服务端分批编码，防止直连调用方一次塞超大列表撑爆内存
                    embs = []
                    for i in range(0, len(texts), 32):
                        embs.extend(_embeddings_model.embed_documents(texts[i:i + 32]))
                self._json({"embeddings": embs})
            elif self.path == "/split":
                # 文档切分上移（2026-08-23）：服务端 splitter 常驻热加载，
                # 会话进程写库不再 import torch（冷机实测本地首切 torch 达 122s 超时）。
                # 纯正则 CPU 工作，不占 _infer_lock；必须调 _split_local 防回环。
                body = str(payload.get("body", ""))
                if not body:
                    self._json({"error": "body 为空"}, 400)
                    return
                from preprocessing import _split_local
                chunks = _split_local(body)
                self._json({"chunks": [{"page_content": c.page_content,
                                        "metadata": c.metadata} for c in chunks]})
            elif self.path == "/rerank":
                if _reranker_model is None:
                    self._json({"error": "reranker unavailable"}, 503)
                    return
                pairs = [(str(p[0]), str(p[1])) for p in payload.get("pairs", []) if len(p) >= 2]
                if not pairs:
                    self._json({"error": "pairs 为空"}, 400)
                    return
                with _infer_lock:
                    scores = [float(s) for s in _reranker_model.predict(pairs)]
                self._json({"scores": scores})
            elif self.path == "/vector_query":
                kb_id = validate_kb_id(payload.get("kb_id", ""))
                collection, col_err = _payload_collection(payload)
                if collection is None:
                    self._json({"error": col_err}, 400)
                    return
                store = _open_store(kb_id, collection)
                if store is None:
                    self._json({"error": "vector store unavailable"}, 503)
                    return
                emb = payload.get("embedding")
                k = int(payload.get("k", 10))
                where = payload.get("where")
                if not isinstance(emb, list) or not emb:
                    self._json({"error": "embedding 非法"}, 400)
                    return
                try:
                    hits = store.similarity_search_by_vector_with_relevance_scores(emb, k=k, filter=where)
                except TypeError:
                    # 与会话端旧代码同构：老版本 langchain_chroma 不认 filter 关键字
                    hits = store.similarity_search_by_vector_with_relevance_scores(emb, k=k)
                self._json({"hits": [[d.page_content, d.metadata, float(s)] for d, s in hits]})
            elif self.path == "/vector_get":
                kb_id = validate_kb_id(payload.get("kb_id", ""))
                collection, col_err = _payload_collection(payload)
                if collection is None:
                    self._json({"error": col_err}, 400)
                    return
                store = _open_store(kb_id, collection)
                if store is None:
                    self._json({"error": "vector store unavailable"}, 503)
                    return
                where = payload.get("where")
                results = store.get(where=where) if where else store.get()
                self._json({"ids": results.get("ids", []),
                            "documents": results.get("documents", []),
                            "metadatas": results.get("metadatas", [])})
            elif self.path == "/vector_write":
                kb_id = validate_kb_id(payload.get("kb_id", ""))
                collection, col_err = _payload_collection(payload)
                if collection is None:
                    self._json({"error": col_err}, 400)
                    return
                action = payload.get("action")
                if action not in ("add", "delete"):
                    self._json({"error": "action 仅支持 add/delete"}, 400)
                    return
                if not kb_vectordb_path(kb_id).exists():
                    kb_vectordb_path(kb_id).mkdir(parents=True, exist_ok=True)
                store = _open_store(kb_id, collection)
                if store is None:
                    self._json({"error": "vector store unavailable"}, 503)
                    return
                if action == "add":
                    docs_in = payload.get("documents", [])
                    if not docs_in:
                        self._json({"error": "documents 为空"}, 400)
                        return
                    texts = [str(d.get("page_content", "")) for d in docs_in]
                    metas = [d.get("metadata") or {} for d in docs_in]
                    # S4 幂等：客户端传确定性 uuid5 ids（source+序号）时 delete-then-add，
                    # 超时重试不会重复写入；无 ids（老客户端）退回旧 add_documents 行为
                    ids = [str(i) for i in payload.get("ids", []) if i]
                    with _infer_lock:
                        # CC 审查 B2 修复：add_texts 内部在服务端模型上做嵌入推理，
                        # 必须与 /embed /rerank 同走 _infer_lock（torch 推理全串行化不变量）
                        if ids and len(ids) == len(texts):
                            store.delete(ids=ids)
                            store.add_texts(texts, metadatas=metas, ids=ids)
                        else:
                            store.add_texts(texts, metadatas=metas)
                    # BM25 只建在主库上；sections 写入不触发主库 BM25 重建
                    if collection == "main":
                        _invalidate_bm25(kb_id)
                    self._json({"added": len(texts)})
                else:
                    ids = [str(i) for i in payload.get("ids", [])]
                    if not ids:
                        self._json({"error": "ids 为空"}, 400)
                        return
                    store.delete(ids=ids)  # 公开 API；会话端已统一 delete(ids=)，同风格
                    if collection == "main":
                        _invalidate_bm25(kb_id)
                    self._json({"deleted": len(ids)})
            elif self.path == "/bm25":
                kb_id = validate_kb_id(payload.get("kb_id", ""))
                query = str(payload.get("query", ""))
                k = int(payload.get("k", 20))
                if not query:
                    self._json({"error": "query 为空"}, 400)
                    return
                retriever = _get_bm25(kb_id)
                if retriever is None:
                    self._json({"error": "bm25 unavailable"}, 503)
                    return
                docs = retriever.invoke(query)[:k]
                self._json({"docs": [{"page_content": d.page_content,
                                      "metadata": d.metadata} for d in docs]})
            else:
                self._json({"error": "not found"}, 404)
        except Exception as e:
            log(f"[model-service] 处理 {self.path} 出错: {e}")
            self._json({"error": str(e)}, 500)

    def log_message(self, fmt, *args):
        # 静默默认访问日志（stderr 留给生命周期日志）
        pass


class _ModelHTTPServer(ThreadingHTTPServer):
    # HTTPServer 默认 allow_reuse_address=1，Windows 的 SO_REUSEADDR 允许多进程
    # 绑同一端口（曾因此 3 实例并存、各占一份 GPU/显存）。显式关闭后，
    # 第二个实例 bind 即报 WSAEADDRINUSE，端口绑定本身成为跨进程互斥锁
    allow_reuse_address = False


def main():
    log(f"[model-service] 启动 {MODEL_SERVICE_HOST}:{MODEL_SERVICE_PORT}")
    httpd = None
    # 绑定失败重试：要么另一实例已在跑（重试耗尽后退出，调用方 ping 命中先来者），
    # 要么上一实例刚退出、端口短暂未释放（等一下就能绑上）
    for attempt in range(15):
        try:
            httpd = _ModelHTTPServer((MODEL_SERVICE_HOST, MODEL_SERVICE_PORT), _Handler)
            break
        except OSError as e:
            log(f"[model-service] 端口绑定失败（第 {attempt + 1}/15 次，2s 后重试）: {e}")
            time.sleep(2)
    if httpd is None:
        log("[model-service] 端口持续被占，判定已有实例在跑，本实例退出")
        os._exit(0)
    httpd.daemon_threads = True

    threading.Thread(target=_load_models, daemon=True, name="model-load").start()
    threading.Thread(target=_idle_watchdog, daemon=True, name="idle-watchdog").start()
    threading.Thread(target=_preopen_stores, daemon=True, name="preopen-stores").start()

    log("[model-service] 监听中，后台加载模型...")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
