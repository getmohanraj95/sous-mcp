"""Core data models for the Sous MCP server.

Plain dataclasses keep the domain decoupled from MCP and from any storage
backend; `to_dict` methods produce the structured tool output Alexa+ renders.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .matching import contains_allergen, normalize


@dataclass(frozen=True)
class Recipe:
    """A recipe in the catalog."""

    recipe_id: str
    title: str
    ingredients: tuple[str, ...]
    steps: tuple[str, ...]
    base_servings: int
    tags: tuple[str, ...] = ()


@dataclass
class DietaryProfile:
    """Standing dietary constraints for a session.

    restrictions: tags a recipe MUST carry (e.g. "vegan", "dairy-free").
    allergies:    allergens no ingredient may contain (e.g. "peanut", "dairy").
    """

    restrictions: list[str] = field(default_factory=list)
    allergies: list[str] = field(default_factory=list)

    def allows(self, recipe: Recipe) -> bool:
        """True if the recipe satisfies every restriction and avoids every allergen."""
        recipe_tags = {tag.lower() for tag in recipe.tags}
        if any(restriction.lower() not in recipe_tags for restriction in self.restrictions):
            return False
        return not any(
            contains_allergen(ingredient, allergen)
            for allergen in self.allergies
            for ingredient in recipe.ingredients
        )

    def to_dict(self) -> dict[str, Any]:
        return {"restrictions": list(self.restrictions), "allergies": list(self.allergies)}


@dataclass(frozen=True)
class RankedRecipe:
    """A recipe paired with its fit score for the current pantry."""

    recipe: Recipe
    score: float


@dataclass(frozen=True)
class ScheduledMeal:
    """A recipe scheduled for a specific time."""

    recipe_id: str
    title: str
    when: str
    servings: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "recipe_id": self.recipe_id,
            "title": self.title,
            "when": self.when,
            "servings": self.servings,
        }


def normalize_names(names: list[str] | None) -> list[str]:
    """Trim, lower-case, de-duplicate, and drop empty entries, preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for raw in names or []:
        cleaned = " ".join(raw.strip().lower().split())
        if cleaned and normalize(cleaned) not in seen:
            seen.add(normalize(cleaned))
            result.append(cleaned)
    return result
