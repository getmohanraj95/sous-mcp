"""Container that wires the domain services together."""
from __future__ import annotations

from dataclasses import dataclass, field

from .pantry import PantryStore
from .ranking import RecipeRanker
from .recipes import RecipeEngine
from .scheduler import MealScheduler
from .shopping import ShoppingListBuilder


@dataclass
class SousServices:
    """All stateful domain services one server instance needs."""

    pantry: PantryStore = field(default_factory=PantryStore)
    recipes: RecipeEngine = field(default_factory=RecipeEngine)
    shopping: ShoppingListBuilder = field(default_factory=ShoppingListBuilder)
    scheduler: MealScheduler = field(default_factory=MealScheduler)

    @classmethod
    def with_ranker(cls, ranker: RecipeRanker | None = None) -> SousServices:
        return cls(recipes=RecipeEngine(ranker=ranker))
