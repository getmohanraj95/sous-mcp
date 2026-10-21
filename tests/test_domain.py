"""Domain logic: matching, dietary filtering, pantry, ranking order."""
from __future__ import annotations

from sous.matching import contains_allergen, names_match, split_by_pantry
from sous.models import DietaryProfile
from sous.pantry import PantryStore
from sous.recipes import RecipeEngine


def test_names_match_handles_plurals_and_partial_names() -> None:
    assert names_match("chicken", "chicken breast")
    assert names_match("Lemons", "lemon")
    assert names_match("tomatoes", "tomato")
    assert not names_match("chicken", "chickpeas")


def test_split_by_pantry() -> None:
    have, missing = split_by_pantry(["chicken breast", "spinach", "lemon"], ["chicken", "spinach"])
    assert have == ["chicken breast", "spinach"]
    assert missing == ["lemon"]


def test_dairy_free_restriction_keeps_dairy_free_recipes() -> None:
    results = RecipeEngine().find(["chicken breast", "spinach", "lemon"], DietaryProfile(restrictions=["dairy-free"]))
    ids = [r.recipe.recipe_id for r in results]
    assert ids[0] == "lemon-spinach-chicken"
    assert "lemon-butter-salmon" not in ids


def test_allergen_families() -> None:
    assert contains_allergen("parmesan", "dairy")
    assert contains_allergen("peanut butter", "peanuts")
    assert not contains_allergen("coconut milk", "dairy")
    assert not contains_allergen("peanut butter", "dairy")


def test_allergy_excludes_recipes() -> None:
    profile = DietaryProfile(allergies=["peanut", "egg"])
    ids = {r.recipe.recipe_id for r in RecipeEngine().find(["rice noodles", "eggs"], profile, max_results=8)}
    assert "peanut-noodle-bowl" not in ids
    assert "shakshuka" not in ids and "veggie-fried-rice" not in ids


def test_unknown_restriction_yields_no_recipes() -> None:
    assert RecipeEngine().find(["eggs"], DietaryProfile(restrictions=["keto"])) == []


def test_pantry_store_dedupes_and_removes() -> None:
    store = PantryStore()
    assert store.add("s1", ["Eggs", "eggs ", "egg", "Spinach"]) == ["eggs", "spinach"]
    assert store.remove("s1", ["spinach", "kale"]) == ["spinach"]
    assert store.items("s1") == ["eggs"]
    assert store.items("s2") == []


def test_update_profile_only_replaces_given_lists() -> None:
    store = PantryStore()
    store.update_profile("s1", restrictions=["Vegan"], allergies=["peanut"])
    profile = store.update_profile("s1", restrictions=["vegetarian"])
    assert profile.restrictions == ["vegetarian"]
    assert profile.allergies == ["peanut"]
