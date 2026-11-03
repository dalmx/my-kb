#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""my-kb MCP streamable-http 常驻服务入口（2026-11-03 启动优化）

stdio 模式每会话 spawn 一次 python：实测连接 ~1.9s = python 启动 50ms +
import 692ms（mcp 协议库占大头、不可省）+ 握手。本入口把 server.py 的同一
Server 对象挂到本机 HTTP 常驻进程，ZCode 以 type:http 直连——零 spawn 零
import，连接 ≈ HTTP 往返。

生命周期：SessionStart hook 以 --ensure 拉起（msvcrt 锁 + 端口探测防双拉，
与 service_client 同款模式）；常驻不空闲退出——本进程不含模型/向量库（都在
model_service），仅 ~150MB 转发层、不占 GPU 显存，与 model_service 空闲退出
的动机不同；进程崩溃由下个会话 hook 自愈拉起（stdio 的 ZCode 自动重拉不再
适用，为已知体验差异）。

用法：
  python http_entry.py            # 服务模式（前台常驻，锁内跑 uvicorn）
  python http_entry.py --ensure   # 探测/拉起后立即返回（hook 用）
"""

import contextlib
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from config import MYKB_HTTP_HOST, MYKB_HTTP_PORT, RUNTIME_LOG

_DIR = Path(__file__).resolve().parent
_LOCK_FILE = _DIR / ".mykb_http.lock"
_BASE_URL = f"http://{MYKB_HTTP_HOST}:{MYKB_HTTP_PORT}"


def _alive(timeout: float = 3.0) -> bool:
    """端口上是否已有实例（有 HTTP 响应即算活——对齐 service_client._service_alive
    口径：HTTPError 也算活，防外来进程占端口时误判双拉）。"""
    try:
        urllib.request.urlopen(_BASE_URL + "/ping", timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


@contextlib.contextmanager
def _lock():
    """跨进程单实例锁（与 service_client._service_lock 同款）。"""
    import msvcrt
    with open(_LOCK_FILE, "a+") as lf:
        msvcrt.locking(lf.fileno(), msvcrt.LK_LOCK, 1)
        try:
            yield
        finally:
            try:
                msvcrt.locking(lf.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass


def _spawn_detached():
    """detached 拉起服务模式进程（同 service_client._spawn_service 模式）。"""
    from utils import log
    env = dict(os.environ)
    # 与 service_client._spawn_service 一致：服务进程环境里必须有，跳过 HF 在线检查
    env.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    env.setdefault("HF_HUB_OFFLINE", "1")
    env.setdefault("TRANSFORMERS_OFFLINE", "1")
    base_flags = (subprocess.DETACHED_PROCESS
                  | subprocess.CREATE_NEW_PROCESS_GROUP
                  | subprocess.CREATE_NO_WINDOW)
    with open(RUNTIME_LOG, "a", encoding="utf-8") as log_fh:
        argv = [sys.executable, "-u", str(_DIR / "http_entry.py")]
        for flags in (base_flags | subprocess.CREATE_BREAKAWAY_FROM_JOB, base_flags):
            try:
                subprocess.Popen(
                    argv, stdin=subprocess.DEVNULL,
                    stdout=log_fh, stderr=subprocess.STDOUT,
                    creationflags=flags, close_fds=True,
                    cwd=str(_DIR), env=env,
                )
                return
            except OSError:
                continue
    log("mykb http 服务拉起失败（Popen 两种模式均失败）")


# ============================================================================
# ASGI 应用（import server 构建 Server 对象 + 全部 handler，复用零改动）
# ============================================================================

def _build_app():
    import server as server_mod
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Mount, Route
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    # json_response=True：无 SSE 长连接（每会话挂流占连接），协议内合法降级
    # security_settings（2026-11-03 MiMo 审查 P1）：SDK 默认关 DNS-rebinding 防护，
    # 恶意网页经 rebind 到 127.0.0.1 可同源调写工具——显式开启并白名单本机主机头
    from mcp.server.transport_security import TransportSecuritySettings
    manager = StreamableHTTPSessionManager(
        app=server_mod.server, event_store=None, json_response=True,
        security_settings=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=["127.0.0.1:18739", "localhost:18739"],
        ))

    async def _mcp(scope, receive, send):
        await manager.handle_request(scope, receive, send)

    async def _ping(request):
        return JSONResponse({"ok": True, "pid": os.getpid()})

    async def _lifespan(app):
        async with manager.run():
            _start_preload_thread()
            yield

    return Starlette(
        routes=[Route("/ping", _ping), Mount("/mcp", app=_mcp)],
        lifespan=_lifespan,
    )


def _start_preload_thread():
    """后台预热（共享服务探测 + vector 通道粘性探测），复用 server.py 的
    看门狗思路：preload 挂死 240s 后全线程栈落盘自退，hook 拉起自愈。"""
    import faulthandler
    import traceback
    from utils import log
    from models import preload

    def _guard():
        try:
            dump_fh = open(RUNTIME_LOG, "a", encoding="utf-8")
        except Exception:
            dump_fh = None
        try:
            faulthandler.dump_traceback_later(240, exit=True, file=dump_fh)
            preload()
            log("mykb http 服务预加载完成")
        except Exception:
            log(f"mykb http preload 线程异常: {traceback.format_exc(limit=6)}")
        finally:
            faulthandler.cancel_dump_traceback_later()
            if dump_fh is not None:
                dump_fh.close()

    threading.Thread(target=_guard, daemon=True, name="model-preload").start()


def _serve():
    from utils import log
    log(f"mykb http 服务启动: {_BASE_URL}/mcp (pid={os.getpid()})")
    import uvicorn
    app = _build_app()
    uvicorn.run(app, host=MYKB_HTTP_HOST, port=MYKB_HTTP_PORT,
                log_config=None, access_log=False, lifespan="on")


if __name__ == "__main__":
    if "--ensure" in sys.argv:
        # hook 入口：已活秒退；未活则锁内复查后 detached 拉起，立即返回
        from utils import log
        if _alive():
            log(f"mykb http 服务已在运行: {_BASE_URL}")
            sys.exit(0)
        try:
            with _lock():
                if not _alive():
                    _spawn_detached()
            log(f"mykb http 服务已拉起: {_BASE_URL}")
        except OSError:
            log("mykb http --ensure 抢锁失败（另一进程正在拉起），跳过")
        sys.exit(0)

    # 服务模式：锁内常驻（锁即单实例互斥，双拉/双绑都被挡住）
    try:
        with _lock():
            _serve()
    except OSError:
        from utils import log
        log("mykb http 服务模式抢锁失败（已有实例），退出")
        sys.exit(0)
