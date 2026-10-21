"""Shopping-list generation."""
from __future__ import annotations

from .matching import split_by_pantry
from .models import Recipe


class ShoppingListBuilder:
    """Diffs a recipe's ingredients against the pantry."""

    def split(self, recipe: Recipe, pantry: list[str]) -> tuple[list[str], list[str]]:
        """Return (have, missing) for the recipe."""
        return split_by_pantry(recipe.ingredients, pantry)
