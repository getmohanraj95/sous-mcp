"""Exercises the real MCP protocol (initialize, tools/list, tools/call) in memory."""
from __future__ import annotations

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from server import create_server

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def test_tools_list_advertises_four_tools_with_output_schemas() -> None:
    async with create_connected_server_and_client_session(create_server()._mcp_server) as client:
        tools = (await client.list_tools()).tools
        assert {t.name for t in tools} == {"update_pantry", "find_recipes", "build_shopping_list", "schedule_meal"}
        assert all(t.outputSchema for t in tools)


async def test_full_conversation_returns_structured_content() -> None:
    async with create_connected_server_and_client_session(create_server()._mcp_server) as client:
        pantry = await client.call_tool(
            "update_pantry", {"items": ["chicken breast", "spinach", "lemon"], "restrictions": ["dairy-free"]}
        )
        assert pantry.structuredContent["pantry"] == ["chicken breast", "spinach", "lemon"]

        found = (await client.call_tool("find_recipes", {"servings": 2})).structuredContent
        top = found["recipes"][0]
        assert top["recipe_id"] == "lemon-spinach-chicken"
        assert top["missing"] == ["olive oil", "garlic"]

        shopping = (await client.call_tool("build_shopping_list", {"recipe_id": top["recipe_id"]})).structuredContent
        assert shopping["missing"] == ["olive oil", "garlic"]

        meal = (await client.call_tool(
            "schedule_meal", {"recipe_id": top["recipe_id"], "when": "tomorrow at 7pm", "servings": 4}
        )).structuredContent
        assert meal["scheduled"]["servings"] == 4
        assert len(meal["upcoming"]) == 1


async def test_empty_pantry_and_unknown_recipe() -> None:
    async with create_connected_server_and_client_session(create_server()._mcp_server) as client:
        empty = (await client.call_tool("find_recipes", {})).structuredContent
        assert empty["pantry_empty"] is True

        bad = await client.call_tool("build_shopping_list", {"recipe_id": "nope"})
        assert bad.isError
        assert "Unknown recipe_id" in bad.content[0].text


async def test_input_validation_rejects_bad_servings() -> None:
    async with create_connected_server_and_client_session(create_server()._mcp_server) as client:
        await client.call_tool("update_pantry", {"items": ["eggs"]})
        result = await client.call_tool("find_recipes", {"servings": 0})
        assert result.isError


async def test_sessions_are_isolated() -> None:
    server = create_server()
    async with create_connected_server_and_client_session(server._mcp_server) as first:
        await first.call_tool("update_pantry", {"items": ["eggs"]})
    async with create_connected_server_and_client_session(server._mcp_server) as second:
        view = (await second.call_tool("update_pantry", {})).structuredContent
        assert view["pantry"] == []
