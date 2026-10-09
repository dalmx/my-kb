#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""my-kb MCP 端到端冒烟：按 ZCode 同款 stdio 方式拉起 server.py，真实调用工具。

用途：改 server.py 后、重启 ZCode 前的离线验证（装饰器错位事故 2026-09-29 后立规）。
    C:/Python311/python.exe F:/rag/scripts/smoke_mcp_calltool.py
判据：list_tools 数量 > 0；三个工具调用均无 isError 且返回正文含预期关键字。
"""
import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = "F:/rag/projects/my-kb/server.py"


async def main():
    env = dict(os.environ)
    env.update({
        "HF_ENDPOINT": "https://hf-mirror.com",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    })
    params = StdioServerParameters(
        command=r"C:/Python311/python.exe", args=["-u", SERVER], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            print(f"[1] list_tools: {len(names)} 个 -> {'OK' if len(names) >= 15 else 'FAIL'}")

            for label, tool, args, expect in [
                ("[2] get_knowledge_info", "get_knowledge_info", {}, "文档块数量"),
                ("[3] search_knowledge", "search_knowledge",
                 {"query": "表结构台账", "n_results": 3}, "置信度"),
                ("[4] list_sources", "list_sources", {}, ".md"),
            ]:
                r = await session.call_tool(tool, args)
                text = "".join(c.text for c in r.content if hasattr(c, "text"))
                head = text.strip().splitlines()[0][:60] if text.strip() else "(空)"
                ok = (not r.is_error) and (expect in text)
                print(f"{label}: {'OK' if ok else 'FAIL'}  isError={r.is_error}  首行={head}")
                if not ok:
                    print(text[:500])
                    sys.exit(1)
    print("SMOKE DONE: 全部通过")


if __name__ == "__main__":
    asyncio.run(main())
