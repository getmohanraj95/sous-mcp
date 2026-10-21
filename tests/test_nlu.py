"""Rule-based intent parser used by the simulator."""
from __future__ import annotations

from simulator.nlu import Intent, IntentParser, RecipeRef

PARSER = IntentParser()
KNOWN = [
    RecipeRef("lemon-spinach-chicken", "Lemon Spinach Chicken"),
    RecipeRef("chickpea-spinach-curry", "Chickpea Spinach Curry"),
]


def test_pantry_with_restriction_and_allergy() -> None:
    parsed = PARSER.parse("I have chicken breast, spinach, lemon and garlic, and I'm dairy-free and allergic to peanuts")
    assert parsed.intent is Intent.UPDATE_PANTRY
    assert parsed.arguments["items"] == ["chicken breast", "spinach", "lemon", "garlic"]
    assert parsed.arguments["restrictions"] == ["dairy-free"]
    assert parsed.arguments["allergies"] == ["peanuts"]


def test_find_recipes_with_servings() -> None:
    parsed = PARSER.parse("What can I cook tonight for four people?")
    assert parsed.tool_name == "find_recipes"
    assert parsed.arguments == {"servings": 4}


def test_shopping_list_by_ordinal_and_title() -> None:
    assert PARSER.parse("What am I missing for the second one?", KNOWN).arguments == {"recipe_id": "chickpea-spinach-curry"}
    assert PARSER.parse("what do I need for the curry", KNOWN).arguments == {"recipe_id": "chickpea-spinach-curry"}


def test_schedule_uses_focus_and_extracts_time() -> None:
    parsed = PARSER.parse("Schedule it for tomorrow at 7pm for 4 people", KNOWN, "lemon-spinach-chicken")
    assert parsed.tool_name == "schedule_meal"
    assert parsed.arguments == {"recipe_id": "lemon-spinach-chicken", "when": "tomorrow at 7pm", "servings": 4}


def test_schedule_without_time_asks_for_it() -> None:
    parsed = PARSER.parse("Put it on the meal plan", KNOWN, "lemon-spinach-chicken")
    assert parsed.tool_name is None
    assert parsed.clarification


def test_recipe_intent_without_context_asks_which() -> None:
    assert PARSER.parse("What am I missing?").clarification


def test_remove_and_view() -> None:
    assert PARSER.parse("I'm out of lemon").arguments == {"remove": ["lemon"]}
    assert PARSER.parse("What's in my pantry?").intent is Intent.VIEW_PANTRY


def test_unknown() -> None:
    assert PARSER.parse("tell me a joke").intent is Intent.UNKNOWN
