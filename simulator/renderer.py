"""Turns structured MCP tool results into spoken replies and visual cards.

This mirrors the Alexa+ data-only rendering flow: the server returns only
structured data, and the client decides how to say it and how to show it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .bridge import ToolOutcome

HELP_TEXT = (
    "Tell me what's in your kitchen, like: I have chicken, spinach and lemon, and I'm dairy-free. "
    "Then ask what you can cook, what you're missing for a recipe, or schedule it for tomorrow at 7pm."
)


@dataclass(frozen=True)
class Reply:
    """What the simulated assistant says and shows for one turn."""

    speech: str
    card: dict[str, Any] | None = None


def join_naturally(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} and {items[-1]}"


class ResponseRenderer:
    """Builds a Reply for each Sous tool's structured output."""

    def render(self, outcome: ToolOutcome, view_only: bool = False) -> Reply:
        if outcome.is_error:
            return Reply(outcome.error_text or "Something went wrong.", {"type": "error", "message": outcome.error_text})
        handler = {
            "update_pantry": self._pantry,
            "find_recipes": self._recipes,
            "build_shopping_list": self._shopping,
            "schedule_meal": self._scheduled,
        }.get(outcome.name)
        if handler is None:
            return Reply("Done.")
        if outcome.name == "update_pantry":
            return self._pantry(outcome.structured, view_only)
        return handler(outcome.structured)

    @staticmethod
    def _pantry(data: dict[str, Any], view_only: bool = False) -> Reply:
        pantry = data.get("pantry", [])
        profile = data.get("dietary_profile", {})
        parts: list[str] = []
        if view_only:
            parts.append(f"You have {join_naturally(pantry)}." if pantry else "Your pantry is empty.")
        else:
            if data.get("added"):
                parts.append(f"Added {join_naturally(data['added'])}.")
            if data.get("removed"):
                parts.append(f"Removed {join_naturally(data['removed'])}.")
            if not parts:
                parts.append("Got it.")
        if profile.get("restrictions"):
            parts.append(f"I'll keep everything {join_naturally(profile['restrictions'])}.")
        if profile.get("allergies"):
            parts.append(f"I'll avoid {join_naturally(profile['allergies'])}.")
        if data.get("unsupported_restrictions"):
            parts.append(
                f"I don't have recipes tagged {join_naturally(data['unsupported_restrictions'])} yet."
            )
        card = {
            "type": "pantry",
            "items": pantry,
            "restrictions": profile.get("restrictions", []),
            "allergies": profile.get("allergies", []),
        }
        return Reply(" ".join(parts), card)

    @staticmethod
    def _recipes(data: dict[str, Any]) -> Reply:
        if data.get("pantry_empty"):
            return Reply("Your pantry is empty. Tell me what you have first, like: I have eggs and tomatoes.")
        recipes = data.get("recipes", [])
        if not recipes:
            return Reply(
                "Nothing in my recipes fits your current restrictions and allergies.",
                {"type": "recipes", "items": [], "servings": data.get("servings"), "backend": data.get("ranking_backend")},
            )
        top = recipes[0]
        total = len(top["have"]) + len(top["missing"])
        speech = f"Your best match is {top['title']}: you have {len(top['have'])} of {total} ingredients."
        if top["missing"]:
            speech += f" You'd need {join_naturally(top['missing'])}."
        if len(recipes) > 1:
            speech += f" I also found {join_naturally([r['title'] for r in recipes[1:]])}."
        card = {
            "type": "recipes",
            "items": recipes,
            "servings": data.get("servings"),
            "backend": data.get("ranking_backend"),
        }
        return Reply(speech, card)

    @staticmethod
    def _shopping(data: dict[str, Any]) -> Reply:
        missing = data.get("missing", [])
        if not missing:
            speech = f"You already have everything for {data['title']}."
        else:
            speech = f"For {data['title']} you still need {join_naturally(missing)}."
        card = {"type": "shopping_list", "title": data["title"], "missing": missing, "have": data.get("have", [])}
        return Reply(speech, card)

    @staticmethod
    def _scheduled(data: dict[str, Any]) -> Reply:
        meal = data["scheduled"]
        speech = f"{meal['title']} is on your meal plan for {meal['when']}, serving {meal['servings']}."
        card = {"type": "meal_plan", "scheduled": meal, "upcoming": data.get("upcoming", [])}
        return Reply(speech, card)
