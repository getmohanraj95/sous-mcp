"""FastAPI web app: a simulated Alexa+ client for the Sous MCP server.

    python server.py           # terminal 1: the real MCP server
    python -m simulator        # terminal 2: open http://127.0.0.1:8100

Intent parsing is rule-based (see nlu.py). Every tool call is a real MCP
request over Streamable HTTP to the Sous server.
"""
from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .bridge import BridgeUnavailableError, MCPBridge
from .dialogue import DialogueManager

logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_SERVER_URL = "http://127.0.0.1:8000/mcp"


class TurnRequest(BaseModel):
    utterance: str = Field(min_length=1, max_length=500)


def create_app(server_url: str | None = None) -> FastAPI:
    bridge = MCPBridge(server_url or os.environ.get("SOUS_MCP_URL", DEFAULT_SERVER_URL))
    dialogue = DialogueManager(bridge)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            await bridge.ensure_connected()
        except BridgeUnavailableError as exc:
            logger.warning("%s (will retry on first message)", exc)
        yield
        await bridge.close()

    app = FastAPI(title="Sous: Alexa+ simulator", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    def snapshot() -> dict[str, Any]:
        info = bridge.info
        return {
            "connected": bridge.connected,
            "server_url": bridge.server_url,
            "server_name": info.server_name,
            "server_version": info.server_version,
            "protocol_version": info.protocol_version,
            "session_id": info.session_id,
            "tools": info.tools,
            "trace": [event.to_dict() for event in bridge.trace],
            "turns": [turn.to_dict() for turn in dialogue.state.turns],
        }

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/state")
    async def state() -> dict[str, Any]:
        try:
            await bridge.ensure_connected()
        except BridgeUnavailableError:
            pass
        return snapshot()

    @app.post("/api/turn")
    async def turn(request: TurnRequest) -> dict[str, Any]:
        try:
            result = await dialogue.handle(request.utterance)
        except BridgeUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"turn": result.to_dict(), "state": snapshot()}

    @app.post("/api/reset")
    async def reset() -> dict[str, Any]:
        """Start a fresh MCP session: new MCP-Session-Id, empty pantry."""
        await bridge.close()
        bridge.trace.clear()
        dialogue.reset()
        try:
            await bridge.ensure_connected()
        except BridgeUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return snapshot()

    return app
