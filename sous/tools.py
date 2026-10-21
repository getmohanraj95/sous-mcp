"""MCP tool registrations for Sous.

Each tool is a thin adapter: it derives the session key, delegates to the
domain services, and returns a plain dict. FastMCP publishes that dict as
`structuredContent`, which is what the Alexa+ data-only rendering flow uses
to build native visuals. Errors are raised as ToolError so clients receive a
proper `isError: true` result instead of a success payload with an error string.
"""
from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from .models import Recipe
from .services import SousServices

Servings = Annotated[int, Field(ge=1, le=20, description="Number of people to cook for.")]
RecipeId = Annotated[str, Field(min_length=1, description="A recipe_id returned by find_recipes.")]


def session_key(ctx: Context) -> str:
    """Stable per-session key for in-memory state.

    The Streamable HTTP transport binds one ServerSession object to each
    MCP-Session-Id, so the object's identity scopes state to one conversation.
    With an external store (Redis/DynamoDB), key on the MCP-Session-Id header.
    """
    return str(id(ctx.session))


def _recipe_or_error(services: SousServices, recipe_id: str) -> Recipe:
    recipe = services.recipes.get(recipe_id)
    if recipe is None:
        raise ToolError(f"Unknown recipe_id '{recipe_id}'. Call find_recipes to get valid ids.")
    return recipe


def register_tools(mcp: FastMCP, services: SousServices) -> None:
    """Attach all Sous tools to a FastMCP server instance."""

    @mcp.tool(
        name="update_pantry",
        title="Update pantry",
        description=(
            "Add or remove ingredients the user has on hand, and optionally set dietary "
            "restrictions (e.g. vegan, dairy-free) or allergies (e.g. peanut, dairy) for "
            "this conversation. Call with no arguments to read the current pantry. "
            "Call this before find_recipes."
        ),
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True),
    )
    def update_pantry(
        ctx: Context,
        items: Annotated[list[str] | None, Field(description="Ingredients to add.")] = None,
        remove: Annotated[list[str] | None, Field(description="Ingredients to remove.")] = None,
        restrictions: Annotated[
            list[str] | None, Field(description="Replaces the dietary restrictions.")
        ] = None,
        allergies: Annotated[list[str] | None, Field(description="Replaces the allergies.")] = None,
    ) -> dict[str, Any]:
        sid = session_key(ctx)
        added = services.pantry.add(sid, items or [])
        removed = services.pantry.remove(sid, remove or [])
        profile = services.pantry.update_profile(sid, restrictions, allergies)
        unsupported = sorted(set(profile.restrictions) - services.recipes.supported_tags)
        return {
            "pantry": services.pantry.items(sid),
            "added": added,
            "removed": removed,
            "dietary_profile": profile.to_dict(),
            "unsupported_restrictions": unsupported,
        }

    @mcp.tool(
        name="find_recipes",
        title="Find recipes",
        description=(
            "Suggest recipes that best use the pantry, filtered by the dietary "
            "restrictions and allergies on file for this conversation. Each result "
            "lists the ingredients the user has and the ones they are missing."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    )
    def find_recipes(
        ctx: Context,
        servings: Servings = 2,
        max_results: Annotated[int, Field(ge=1, le=5, description="How many recipes.")] = 3,
    ) -> dict[str, Any]:
        sid = session_key(ctx)
        pantry = services.pantry.items(sid)
        profile = services.pantry.profile(sid)
        if not pantry:
            return {
                "pantry_empty": True,
                "servings": servings,
                "ranking_backend": "none",
                "dietary_profile": profile.to_dict(),
                "recipes": [],
            }
        ranked = services.recipes.find(pantry, profile, max_results=max_results)
        results = []
        for item in ranked:
            have, missing = services.shopping.split(item.recipe, pantry)
            results.append(
                {
                    "recipe_id": item.recipe.recipe_id,
                    "title": item.recipe.title,
                    "match_score": round(item.score, 2),
                    "have": have,
                    "missing": missing,
                    "tags": list(item.recipe.tags),
                    "steps": list(item.recipe.steps),
                    "base_servings": item.recipe.base_servings,
                }
            )
        return {
            "pantry_empty": False,
            "servings": servings,
            "ranking_backend": services.recipes.ranking_backend,
            "dietary_profile": profile.to_dict(),
            "recipes": results,
        }

    @mcp.tool(
        name="build_shopping_list",
        title="Build shopping list",
        description="List the ingredients still needed for a recipe, given the current pantry.",
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    )
    def build_shopping_list(ctx: Context, recipe_id: RecipeId) -> dict[str, Any]:
        sid = session_key(ctx)
        recipe = _recipe_or_error(services, recipe_id)
        have, missing = services.shopping.split(recipe, services.pantry.items(sid))
        return {"recipe_id": recipe.recipe_id, "title": recipe.title, "have": have, "missing": missing}

    @mcp.tool(
        name="schedule_meal",
        title="Schedule a meal",
        description="Put a recipe on the meal plan for a date or time, e.g. 'tomorrow at 7pm'.",
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False),
    )
    def schedule_meal(
        ctx: Context,
        recipe_id: RecipeId,
        when: Annotated[str, Field(min_length=1, description="When to cook, in natural language.")],
        servings: Servings = 2,
    ) -> dict[str, Any]:
        sid = session_key(ctx)
        recipe = _recipe_or_error(services, recipe_id)
        meal = services.scheduler.schedule(sid, recipe, when, servings)
        return {
            "scheduled": meal.to_dict(),
            "upcoming": [m.to_dict() for m in services.scheduler.upcoming(sid)],
        }
