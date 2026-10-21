"""Rule-based intent parser: a deliberately simple stand-in for Alexa+ reasoning.

Real Alexa+ uses an LLM to pick tools and arguments from what the customer
says. This parser only exists so the simulator can drive the real MCP server
from typed or spoken sentences. It is documented as rule-based, by design.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Intent(str, Enum):
    UPDATE_PANTRY = "update_pantry"
    VIEW_PANTRY = "view_pantry"
    FIND_RECIPES = "find_recipes"
    SHOPPING_LIST = "build_shopping_list"
    SCHEDULE_MEAL = "schedule_meal"
    HELP = "help"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RecipeRef:
    """A recipe the conversation already knows about (from find_recipes)."""

    recipe_id: str
    title: str


@dataclass
class ParsedIntent:
    """Parser output: which tool to call and with what arguments."""

    intent: Intent
    arguments: dict[str, Any] = field(default_factory=dict)
    clarification: str | None = None

    @property
    def tool_name(self) -> str | None:
        if self.clarification is not None:
            return None
        return {
            Intent.UPDATE_PANTRY: "update_pantry",
            Intent.VIEW_PANTRY: "update_pantry",
            Intent.FIND_RECIPES: "find_recipes",
            Intent.SHOPPING_LIST: "build_shopping_list",
            Intent.SCHEDULE_MEAL: "schedule_meal",
        }.get(self.intent)


_RESTRICTIONS = {
    "vegan": "vegan",
    "vegetarian": "vegetarian",
    "pescatarian": "pescatarian",
    "dairy-free": "dairy-free",
    "dairy free": "dairy-free",
    "gluten-free": "gluten-free",
    "gluten free": "gluten-free",
}
_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
_ORDINALS = {"first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2, "top": 0}
_DAYS = r"monday|tuesday|wednesday|thursday|friday|saturday|sunday"
_CLOCK = r"\d{1,2}(?::\d{2})?\s*(?:am|pm)"
_WHEN = re.compile(
    rf"\b((?:tonight|today|tomorrow(?:\s+(?:morning|lunch|evening|night))?|this\s+(?:evening|weekend)"
    rf"|(?:next\s+|on\s+)?(?:{_DAYS}))(?:\s+(?:at\s+)?{_CLOCK})?|at\s+{_CLOCK})\b"
)
_SERVINGS = re.compile(r"\bfor\s+(\d{1,2}|" + "|".join(_NUMBER_WORDS) + r")(?:\s+(?:people|persons|servings|of us|guests))\b")
_ALLERGY = re.compile(r"\b(?:allergic to|allergy to|allergies to)\s+([a-z ,\-]+?)(?:[.!?]|$|\band\s+i\b)")
_STOPWORDS = {"the", "a", "an", "for", "with", "and", "of", "one", "recipe", "to", "it", "that", "this", "me", "my"}

_HELP = re.compile(r"\b(help|what can you do|how does this work)\b")
_SCHEDULE = re.compile(r"\b(schedule|calendar|meal plan|plan\s+(?:it|that|the))\b")
_SHOPPING = re.compile(r"\b(missing|need to buy|shopping list|what do i need|grocer(?:y|ies)|buy for)\b")
_VIEW = re.compile(r"\b(what'?s in my (?:pantry|kitchen|fridge)|what do i have|show (?:me )?my pantry|my pantry)\b")
_FIND = re.compile(r"\b(what can i (?:cook|make)|what should i (?:cook|make)|recipes?|suggest|ideas?|cook tonight|make for dinner|dinner)\b")
_REMOVE = re.compile(r"\b(?:i'?m out of|i ran out of|ran out of|remove|i used up|used up|no more)\s+(.+)")
_ADD = re.compile(r"\b(?:i have|i've got|i got|i bought|add|there'?s)\s+(.+)")
_DIET_CLAUSE = re.compile(r"\b(?:and\s+|but\s+)?(?:i'?m|i am|we'?re|we are|keep it|make it)\b.*$")


class IntentParser:
    """Maps one utterance to a Sous tool call using ordered regex rules."""

    def parse(
        self,
        utterance: str,
        known_recipes: Sequence[RecipeRef] = (),
        focus_recipe_id: str | None = None,
    ) -> ParsedIntent:
        text = " ".join(utterance.lower().strip().split())
        if not text:
            return ParsedIntent(Intent.UNKNOWN)

        if _HELP.search(text):
            return ParsedIntent(Intent.HELP)
        if _SCHEDULE.search(text):
            return self._schedule(text, known_recipes, focus_recipe_id)
        if _SHOPPING.search(text):
            return self._recipe_intent(Intent.SHOPPING_LIST, text, known_recipes, focus_recipe_id)
        if _VIEW.search(text) and not _ADD.search(text):
            return ParsedIntent(Intent.VIEW_PANTRY)
        if _FIND.search(text) and not _ADD.search(text):
            arguments: dict[str, Any] = {}
            servings = self._servings(text)
            if servings:
                arguments["servings"] = servings
            return ParsedIntent(Intent.FIND_RECIPES, arguments)

        removed = _REMOVE.search(text)
        if removed:
            return ParsedIntent(Intent.UPDATE_PANTRY, {"remove": self._split_items(removed.group(1))})

        arguments = self._dietary(text)
        added = _ADD.search(text)
        if added:
            items_text = _ALLERGY.sub("", _DIET_CLAUSE.sub("", added.group(1)))
            items = self._split_items(items_text)
            if items:
                arguments["items"] = items
        if arguments:
            return ParsedIntent(Intent.UPDATE_PANTRY, arguments)
        return ParsedIntent(Intent.UNKNOWN)

    def _schedule(
        self, text: str, known: Sequence[RecipeRef], focus: str | None
    ) -> ParsedIntent:
        parsed = self._recipe_intent(Intent.SCHEDULE_MEAL, text, known, focus)
        if parsed.clarification:
            return parsed
        when = _WHEN.search(text)
        if not when:
            return ParsedIntent(
                Intent.SCHEDULE_MEAL, parsed.arguments, clarification="When would you like to cook it?"
            )
        parsed.arguments["when"] = when.group(1).strip()
        servings = self._servings(text)
        if servings:
            parsed.arguments["servings"] = servings
        return parsed

    def _recipe_intent(
        self, intent: Intent, text: str, known: Sequence[RecipeRef], focus: str | None
    ) -> ParsedIntent:
        recipe_id = self.resolve_recipe(text, known, focus)
        if recipe_id is None:
            return ParsedIntent(
                intent,
                clarification="Which recipe? Ask me what you can cook first, then pick one.",
            )
        return ParsedIntent(intent, {"recipe_id": recipe_id})

    @staticmethod
    def resolve_recipe(text: str, known: Sequence[RecipeRef], focus: str | None) -> str | None:
        """Resolve 'the first one', 'that', or a title fragment to a recipe_id."""
        words = re.findall(r"[a-z0-9']+", text)
        for word in words:
            if word in _ORDINALS and _ORDINALS[word] < len(known):
                return known[_ORDINALS[word]].recipe_id

        content = {w for w in words if w not in _STOPWORDS}
        best: tuple[int, str] | None = None
        for ref in known:
            title_words = set(re.findall(r"[a-z0-9']+", ref.title.lower())) - _STOPWORDS
            overlap = len(content & title_words)
            if overlap and (best is None or overlap > best[0]):
                best = (overlap, ref.recipe_id)
        if best:
            return best[1]
        return focus  # "it", "that", or no recipe named: use the recipe in focus

    @staticmethod
    def _servings(text: str) -> int | None:
        match = _SERVINGS.search(text)
        if not match:
            return None
        value = match.group(1)
        return int(value) if value.isdigit() else _NUMBER_WORDS[value]

    @staticmethod
    def _dietary(text: str) -> dict[str, Any]:
        arguments: dict[str, Any] = {}
        restrictions = sorted({canonical for phrase, canonical in _RESTRICTIONS.items() if phrase in text})
        if restrictions:
            arguments["restrictions"] = restrictions
        allergy = _ALLERGY.search(text)
        if allergy:
            arguments["allergies"] = IntentParser._split_items(allergy.group(1))
        return arguments

    @staticmethod
    def _split_items(text: str) -> list[str]:
        parts = re.split(r",|\band\b|&|\bplus\b", text)
        items = []
        for part in parts:
            cleaned = re.sub(r"^(?:some|a few|a|an|the|half a|half an)\s+", "", part.strip(" .!?"))
            if cleaned:
                items.append(cleaned)
        return items
