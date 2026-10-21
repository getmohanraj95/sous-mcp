"""MCP client bridge used by the simulator.

Plays the Alexa+ client role over real Streamable HTTP:
initialize -> tools/list -> tools/call. The session lives inside one
dedicated background task, because the SDK's transport contexts must be
entered and exited by the same task.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)


class BridgeUnavailableError(RuntimeError):
    """Raised when the MCP server cannot be reached."""


@dataclass(frozen=True)
class TraceEvent:
    """One MCP request as shown in the simulator's protocol panel."""

    method: str
    detail: str
    ok: bool
    elapsed_ms: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ToolOutcome:
    """Result of one tools/call."""

    name: str
    arguments: dict[str, Any]
    structured: dict[str, Any]
    is_error: bool
    error_text: str | None = None


@dataclass
class ConnectionInfo:
    server_name: str = ""
    server_version: str = ""
    protocol_version: str = ""
    session_id: str | None = None
    tools: list[dict[str, Any]] = field(default_factory=list)


class MCPBridge:
    """Owns one long-lived MCP client session to the Sous server."""

    def __init__(self, server_url: str, connect_timeout: float = 10.0, trace_size: int = 40) -> None:
        self.server_url = server_url
        self._connect_timeout = connect_timeout
        self._session: ClientSession | None = None
        self._task: asyncio.Task[None] | None = None
        self._ready = asyncio.Event()
        self._stop = asyncio.Event()
        self._error: BaseException | None = None
        self._lock = asyncio.Lock()
        self.info = ConnectionInfo()
        self.trace: deque[TraceEvent] = deque(maxlen=trace_size)

    @property
    def connected(self) -> bool:
        return self._session is not None

    async def ensure_connected(self) -> None:
        """Connect if needed. Safe to call on every request."""
        async with self._lock:
            if self._session is not None:
                return
            self._ready, self._stop, self._error = asyncio.Event(), asyncio.Event(), None
            self._task = asyncio.create_task(self._run(), name="mcp-bridge")
            try:
                await asyncio.wait_for(self._ready.wait(), timeout=self._connect_timeout)
            except asyncio.TimeoutError as exc:
                await self._cancel_task()
                raise BridgeUnavailableError(f"Timed out connecting to {self.server_url}") from exc
            if self._error is not None or self._session is None:
                await self._cancel_task()
                raise BridgeUnavailableError(
                    f"Could not reach the Sous MCP server at {self.server_url}. "
                    "Start it with: python server.py"
                ) from self._error

    async def _run(self) -> None:
        try:
            started = time.perf_counter()
            async with streamablehttp_client(self.server_url) as (read, write, get_session_id):
                async with ClientSession(read, write) as session:
                    init = await session.initialize()
                    self._record("initialize", f"protocol {init.protocolVersion}", True, started)

                    started = time.perf_counter()
                    listed = await session.list_tools()
                    self._record("tools/list", f"{len(listed.tools)} tools", True, started)

                    self.info = ConnectionInfo(
                        server_name=init.serverInfo.name,
                        server_version=init.serverInfo.version,
                        protocol_version=str(init.protocolVersion),
                        session_id=get_session_id(),
                        tools=[
                            {
                                "name": tool.name,
                                "title": tool.title or tool.name,
                                "description": tool.description or "",
                                "read_only": bool(tool.annotations and tool.annotations.readOnlyHint),
                            }
                            for tool in listed.tools
                        ],
                    )
                    self._session = session
                    self._ready.set()
                    await self._stop.wait()
        except Exception as exc:  # noqa: BLE001 - surfaced to callers via _error
            logger.warning("MCP bridge stopped: %s", exc)
            self._error = exc
        finally:
            self._session = None
            self._ready.set()

    async def close(self) -> None:
        """Close the session (the server discards that session's state)."""
        self._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                await self._cancel_task()
        self._task = None
        self.info = ConnectionInfo()

    async def _cancel_task(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        self._task = None

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolOutcome:
        await self.ensure_connected()
        assert self._session is not None
        if name not in {tool["name"] for tool in self.info.tools}:
            raise ValueError(f"Server does not advertise a tool named '{name}'.")
        started = time.perf_counter()
        try:
            result = await self._session.call_tool(name, arguments)
        except Exception as exc:
            self._record("tools/call", f"{name} failed: {exc}", False, started)
            self._session = None
            raise BridgeUnavailableError(f"Lost connection to the Sous server: {exc}") from exc

        error_text = None
        if result.isError:
            error_text = " ".join(
                getattr(block, "text", "") for block in result.content
            ).strip() or "The tool reported an error."
        self._record("tools/call", name, not result.isError, started)
        return ToolOutcome(name, arguments, result.structuredContent or {}, result.isError, error_text)

    def _record(self, method: str, detail: str, ok: bool, started: float) -> None:
        elapsed = int((time.perf_counter() - started) * 1000)
        self.trace.append(TraceEvent(method, detail, ok, elapsed))
