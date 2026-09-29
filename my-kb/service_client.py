#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""模型服务客户端：拉起/探测共享服务 + 远程模型对象（embeddings / reranker）。

- ensure_model_service()：服务在跑→直接用；没跑→抢文件锁拉起（防多会话重复拉起），
  等待模型就绪。SessionStart hook 用 wait_ready=False 快速返回。
- RemoteEmbeddings：实现 langchain Embeddings 接口，替代进程内 HuggingFaceEmbeddings，
  Chroma 构造时传入即可，分批调用防大 payload。
- RemoteReranker：predict(pairs) 鸭子类型兼容原 CrossEncoder，retriever.py 零改动。
- 服务中途死亡时自动重新拉起并重试一次，调用方无感。
"""

import contextlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from config import (
    MODEL_SERVICE_HOST, MODEL_SERVICE_PORT, MODEL_SERVICE_LOG,
)

_SERVICE_DIR = Path(__file__).resolve().parent
_SERVICE_SCRIPT = _SERVICE_DIR / "model_service.py"
_SERVICE_LOCK = _SERVICE_DIR / ".service.lock"
_BASE_URL = f"http://{MODEL_SERVICE_HOST}:{MODEL_SERVICE_PORT}"

# 与 ZCode config.json my-kb env 保持一致（服务进程环境里必须有，跳过 HF 在线检查）
_SERVICE_ENV_KEYS = ("HF_ENDPOINT", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")

# _call_model 拉起失败冷却（S3②）
_ENSURE_FAIL_COOLDOWN_SEC = 120
_ensure_fail_cooldown_until = 0.0

# S4 写入幂等：chunk id = uuid5(命名空间, source::序号)，跨进程稳定，
# 客户端超时重试同一批文档时服务端 delete-then-add 不会产生重复块
import uuid
_CHUNK_NS = uuid.uuid5(uuid.NAMESPACE_URL, "my-kb/chunk/v1")


def _request(path, payload=None, timeout=60):
    """GET/POST 一次 HTTP 请求。连接失败/HTTP 错误时抛异常。"""
    if payload is None:
        req = urllib.request.Request(_BASE_URL + path, method="GET")
    else:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            _BASE_URL + path, data=body, method="POST",
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _ping_ready():
    """服务是否已就绪（连不上 / 加载中 / 报错都算未就绪）。"""
    try:
        return bool(_request("/ping", timeout=3).get("ready"))
    except Exception:
        return False


def _service_alive():
    """服务进程是否存在（端口有 HTTP 响应即可，ready 与否都算活）。

    模型加载窗口期内 /ping 返回 ready=False 但端口已监听，说明已有实例
    正在启动，此时不能再拉第二个（曾因锁内只查 ready 导致 3 实例并存）。
    """
    try:
        _request("/ping", timeout=3)
        return True
    except urllib.error.HTTPError:
        return True  # 有 HTTP 响应即说明端口上有活的服务
    except Exception:
        return False


@contextlib.contextmanager
def _service_lock():
    """跨进程拉起锁（Windows msvcrt，锁首字节）。抢不到（~10s 超时）抛 OSError。"""
    import msvcrt
    with open(_SERVICE_LOCK, "a+") as lf:
        msvcrt.locking(lf.fileno(), msvcrt.LK_LOCK, 1)
        try:
            yield
        finally:
            try:
                msvcrt.locking(lf.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass


def _spawn_service():
    """detached 拉起模型服务（不随本进程退出而死），日志追加到 model_service.log。"""
    from utils import log
    env = dict(os.environ)
    env.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    env.setdefault("HF_HUB_OFFLINE", "1")
    env.setdefault("TRANSFORMERS_OFFLINE", "1")

    base_flags = (subprocess.DETACHED_PROCESS
                  | subprocess.CREATE_NEW_PROCESS_GROUP
                  | subprocess.CREATE_NO_WINDOW)
    MODEL_SERVICE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_SERVICE_LOG, "a", encoding="utf-8") as log_fh:
        argv = [sys.executable, "-u", str(_SERVICE_SCRIPT)]
        # 优先脱离 ZCode 的 job（防会话退出连带杀掉共享服务）；
        # job 禁止 breakaway 时降级普通 detached（服务可能随 ZCode 退出，懒启动会自愈）
        for flags in (base_flags | subprocess.CREATE_BREAKAWAY_FROM_JOB, base_flags):
            try:
                subprocess.Popen(
                    argv, stdin=subprocess.DEVNULL,
                    stdout=log_fh, stderr=subprocess.STDOUT,
                    creationflags=flags, close_fds=True,
                    cwd=str(_SERVICE_DIR), env=env,
                )
                return
            except OSError:
                continue
    log("模型服务进程拉起失败（Popen 两种模式均失败）")


def _wait_ready(timeout, progress_cb=None):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _ping_ready():
            return True
        time.sleep(1.0)
        if progress_cb:
            progress_cb()
    return _ping_ready()


def ensure_model_service(wait_ready=True, timeout=150):
    """确保共享模型服务在跑且就绪。

    wait_ready=False：拉起后立即返回（SessionStart hook 预热用）。
    返回 True=就绪。失败返回 False（调用方走各自的降级路径）。
    """
    if _ping_ready():
        return True
    try:
        with _service_lock():
            # 锁内复查用"存活"而非"就绪"：先来者还在加载模型（ready=False）
            # 时同样算在跑，避免重复拉起
            if not _service_alive():
                _spawn_service()
            if wait_ready:
                return _wait_ready(timeout)
        # with 块正常退出且 wait_ready=False（hook 预热）：拉起即返回，不等加载
    except OSError:
        # 未抢到锁（另一会话正在拉起）：不重复拉，仅在需要时等它就绪
        pass
    if wait_ready:
        return _wait_ready(timeout)
    return _ping_ready()


def _call_model(path, payload, timeout=120):
    """调用模型端点；服务死亡时自动拉起重试一次，仍失败才抛异常（调用方降级）。

    S3② 冷却：拉起失败（服务崩溃循环/加载失败）后 _ENSURE_FAIL_COOLDOWN_SEC
    内不再重复"等 120s 拉起"，直接抛——故障期每次调用白等 120s 的问题。
    拉起成功（常见瞬断：空闲自杀后首调）则正常重试，不受冷却影响。
    """
    global _ensure_fail_cooldown_until
    try:
        return _request(path, payload, timeout=timeout)
    except Exception:
        if time.time() < _ensure_fail_cooldown_until:
            raise
        if not ensure_model_service(wait_ready=True, timeout=120):
            _ensure_fail_cooldown_until = time.time() + _ENSURE_FAIL_COOLDOWN_SEC
            raise
        return _request(path, payload, timeout=timeout)


def split_via_service(body):
    """远程切分文档（/split 端点，服务端 splitter 常驻热加载，会话进程零 torch）。

    返回 chunk dict 列表（page_content + metadata）；服务不可用返回 None，
    调用方（preprocessing.split_document）回退本地懒加载路径。
    """
    try:
        resp = _call_model("/split", {"body": body})
        return resp.get("chunks")
    except Exception:
        return None


# ============================================================================
# 远程模型对象（接口兼容原有进程内实现，业务代码零改动）
# ============================================================================

class RemoteEmbeddings:
    """langchain Embeddings 兼容的远程嵌入（duck typing 即可，不强制继承基类）。

    embed_documents 内部按 32 条分批，防大 payload（全量索引时几千块）。
    """

    def embed_documents(self, texts):
        all_embs = []
        for i in range(0, len(texts), 32):
            batch = [str(t) for t in texts[i:i + 32]]
            resp = _call_model("/embed", {"texts": batch})
            all_embs.extend(resp["embeddings"])
        return all_embs

    def embed_query(self, text):
        resp = _call_model("/embed", {"texts": [str(text)]})
        return resp["embeddings"][0]


class RemoteReranker:
    """CrossEncoder.predict 鸭子类型兼容的远程重排器。"""

    def predict(self, pairs):
        resp = _call_model("/rerank", {"pairs": [[str(p[0]), str(p[1])] for p in pairs]})
        return resp["scores"]


# ============================================================================
# 向量库 / BM25 转发（2026-08-31 上移共享服务：chroma 单点持有，会话零导入）
# ============================================================================

def ping_vector_supported(timeout=5):
    """服务是否就绪且带向量检索能力（老服务 /ping 无 vector 字段 → False）。"""
    try:
        info = _request("/ping", timeout=timeout)
        return bool(info.get("ready") and info.get("vector"))
    except Exception:
        return False


def vector_query(kb_id, embedding, k, where=None, collection=None):
    """远程向量检索：返回 [(Document, distance)]，与会话端旧调用逐位同构。

    collection="sections" 查 H2 章节粗索引 collection；缺省 None=主库（字段不发，
    老版本服务兼容）。
    """
    from langchain_core.documents import Document
    payload = {"kb_id": kb_id, "embedding": [float(x) for x in embedding],
               "k": int(k), "where": where}
    if collection:
        payload["collection"] = collection
    resp = _call_model("/vector_query", payload)
    return [(Document(page_content=content, metadata=meta or {}), score)
            for content, meta, score in resp["hits"]]


def vector_get(kb_id, where=None, collection=None):
    """远程拉取（旧 vs.get()）：返回 {"ids","documents","metadatas"}。

    S7：where 透传 chroma get(where=...)，按源删块等场景免全量拉取。
    """
    payload = {"kb_id": kb_id}
    if where:
        payload["where"] = where
    if collection:
        payload["collection"] = collection
    return _call_model("/vector_get", payload)


def vector_add_documents(kb_id, documents, collection=None):
    """远程写入文档块（服务端嵌入）。S4：附确定性 uuid5 ids，重试幂等。"""
    payload = {"kb_id": kb_id, "action": "add",
               "documents": [{"page_content": d.page_content, "metadata": d.metadata} for d in documents],
               "ids": [str(uuid.uuid5(_CHUNK_NS, f"{(d.metadata or {}).get('source', '')}::{i}"))
                       for i, d in enumerate(documents)]}
    if collection:
        payload["collection"] = collection
    return _call_model("/vector_write", payload, timeout=300)


def vector_delete(kb_id, ids, collection=None):
    """远程按 id 删除（服务端同时失效 BM25 缓存）。"""
    payload = {"kb_id": kb_id, "action": "delete", "ids": list(ids)}
    if collection:
        payload["collection"] = collection
    return _call_model("/vector_write", payload, timeout=300)


def bm25_query(kb_id, query, k):
    """远程 BM25 召回：返回按相关性降序的 Document 列表（前 k 条）。"""
    from langchain_core.documents import Document
    resp = _call_model("/bm25", {"kb_id": kb_id, "query": str(query), "k": int(k)})
    return [Document(page_content=d["page_content"], metadata=d.get("metadata") or {})
            for d in resp["docs"]]


if __name__ == "__main__":
    # 手动入口 / hook 入口：拉起服务（不等就绪，快速返回）
    from utils import log
    ok = ensure_model_service(wait_ready="--wait" in sys.argv)
    log(f"模型服务{'已就绪' if ok else '拉起中（后台加载模型）'}: {_BASE_URL}")
