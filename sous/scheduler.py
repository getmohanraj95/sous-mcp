"""Meal scheduling."""
from __future__ import annotations

from .models import Recipe, ScheduledMeal


class MealScheduler:
    """Records scheduled meals per session.

    In-memory for the demo. Wire `schedule` to a real calendar API later;
    the return contract stays the same, so tools.py never changes.
    """

    def __init__(self) -> None:
        self._scheduled: dict[str, list[ScheduledMeal]] = {}

    def schedule(self, session_id: str, recipe: Recipe, when: str, servings: int) -> ScheduledMeal:
        meal = ScheduledMeal(recipe.recipe_id, recipe.title, when.strip(), servings)
        self._scheduled.setdefault(session_id, []).append(meal)
        return meal

    def upcoming(self, session_id: str) -> list[ScheduledMeal]:
        return list(self._scheduled.get(session_id, []))
