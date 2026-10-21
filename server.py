"""Entry point for the Sous MCP server (Streamable HTTP, MCP spec 2025-11-25).

Run:
    python server.py                         deterministic overlap ranking
    SOUS_RANKER=bedrock python server.py     Amazon Bedrock ranking

Environment variables:
    HOST, PORT               Bind address (default 127.0.0.1:8000).
    SOUS_RANKER              "overlap" (default) or "bedrock".
    SOUS_BEDROCK_MODEL_ID    Bedrock model or inference-profile ID.
    AWS_REGION               Region where that model is enabled.

Keep HOST on 127.0.0.1 for local use, per the transport spec's DNS-rebinding
guidance; bind 0.0.0.0 only behind a reverse proxy you control.
"""
from __future__ import annotations

import logging
import os

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from sous import __version__
from sous.ranking import BedrockRanker, OverlapRanker, RecipeRanker
from sous.services import SousServices
from sous.tools import register_tools

logger = logging.getLogger("sous")

DEFAULT_BEDROCK_MODEL_ID = "amazon.nova-lite-v1:0"

INSTRUCTIONS = (
    "Sous is an AI sous-chef. Typical flow: update_pantry with what the user has "
    "(and any restrictions or allergies), then find_recipes, then "
    "build_shopping_list or schedule_meal for the recipe the user picks. "
    "Pantry and dietary profile persist for the rest of the conversation."
)


def build_ranker() -> RecipeRanker:
    """Choose the ranking strategy from environment configuration."""
    mode = os.environ.get("SOUS_RANKER", "overlap").strip().lower()
    if mode == "bedrock":
        model_id = os.environ.get("SOUS_BEDROCK_MODEL_ID", DEFAULT_BEDROCK_MODEL_ID)
        try:
            ranker = BedrockRanker(model_id=model_id, region_name=os.environ.get("AWS_REGION"))
        except Exception as exc:  # noqa: BLE001 - e.g. boto3 missing or no region configured
            logger.warning("Bedrock ranking unavailable (%s); using overlap ranking.", exc)
            return OverlapRanker()
        logger.info("Ranking with Amazon Bedrock model %s", model_id)
        return ranker
    if mode != "overlap":
        logger.warning("Unknown SOUS_RANKER=%r; using overlap ranking.", mode)
    return OverlapRanker()


def create_server(
    services: SousServices | None = None,
    host: str | None = None,
    port: int | None = None,
) -> FastMCP:
    """Build the Sous FastMCP server. Arguments exist mainly for tests."""
    mcp = FastMCP(
        name="Sous",
        instructions=INSTRUCTIONS,
        host=host or os.environ.get("HOST", "127.0.0.1"),
        port=port or int(os.environ.get("PORT", "8000")),
    )
    register_tools(mcp, services or SousServices.with_ranker(build_ranker()))

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "name": "Sous", "version": __version__})

    return mcp


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    create_server().run(transport="streamable-http")


if __name__ == "__main__":
    main()
