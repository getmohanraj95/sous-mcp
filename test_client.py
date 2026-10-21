"""End-to-end smoke test for a running Sous server over Streamable HTTP.

    python server.py          # terminal 1
    python test_client.py     # terminal 2

Walks the full MCP lifecycle: initialize -> tools/list -> tools/call.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

DEFAULT_URL = "http://127.0.0.1:8000/mcp"


async def call(session: ClientSession, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    result = await session.call_tool(name, arguments)
    print(f"\n--- tools/call {name} {json.dumps(arguments)}")
    if result.isError:
        print("ERROR:", result.content[0].text if result.content else "unknown error")
        return {}
    print(json.dumps(result.structuredContent, indent=2))
    return result.structuredContent or {}


async def run(url: str) -> None:
    async with streamablehttp_client(url) as (read_stream, write_stream, get_session_id):
        async with ClientSession(read_stream, write_stream) as session:
            init = await session.initialize()
            print(f"Connected to {init.serverInfo.name}, protocol {init.protocolVersion}")
            print(f"MCP-Session-Id: {get_session_id()}")

            tools = await session.list_tools()
            print("Tools:", ", ".join(tool.name for tool in tools.tools))

            await call(
                session,
                "update_pantry",
                {"items": ["chicken breast", "spinach", "lemon", "garlic"], "restrictions": ["dairy-free"]},
            )
            found = await call(session, "find_recipes", {"servings": 2})
            if not found.get("recipes"):
                return
            top = found["recipes"][0]["recipe_id"]
            await call(session, "build_shopping_list", {"recipe_id": top})
            await call(session, "schedule_meal", {"recipe_id": top, "when": "tomorrow at 7pm", "servings": 4})
            await call(session, "build_shopping_list", {"recipe_id": "does-not-exist"})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL, help="Sous MCP endpoint URL.")
    asyncio.run(run(parser.parse_args().url))


if __name__ == "__main__":
    main()
