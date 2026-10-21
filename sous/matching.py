"""Ingredient-name matching shared by ranking, shopping lists, and allergy checks.

These are stateless pure functions rather than a class: they hold no state and
have a single obvious behaviour, so a class would add ceremony without value.
"""
from __future__ import annotations

from collections.abc import Iterable

# Allergen families: saying "dairy" should also catch "butter" and "parmesan".
_ALLERGEN_FAMILIES: dict[str, frozenset[str]] = {
    "dairy": frozenset({"milk", "butter", "cheese", "cream", "yogurt", "parmesan"}),
    "gluten": frozenset({"pasta", "flour", "bread", "soy sauce", "couscous", "wheat", "barley"}),
    "nut": frozenset({"almond", "cashew", "walnut", "pecan", "pistachio", "hazelnut"}),
    "tree nut": frozenset({"almond", "cashew", "walnut", "pecan", "pistachio", "hazelnut"}),
    "peanut": frozenset({"peanut"}),
    "egg": frozenset({"egg"}),
    "shellfish": frozenset({"shrimp", "prawn", "crab", "lobster"}),
    "fish": frozenset({"salmon", "tuna", "cod"}),
    "soy": frozenset({"soy sauce", "tofu"}),
}

# Ingredients that contain a family keyword but are not members of that family.
_ALLERGEN_EXCEPTIONS: dict[str, frozenset[str]] = {
    "dairy": frozenset({"coconut milk", "peanut butter", "almond milk", "oat milk"}),
}


def _singular(word: str) -> str:
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("oes") and len(word) > 4:
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def normalize(name: str) -> str:
    """Lower-case, trim, and singularise each word: 'Tomatoes ' -> 'tomato'."""
    return " ".join(_singular(word) for word in name.strip().lower().split())


def _tokens(name: str) -> frozenset[str]:
    return frozenset(normalize(name).split())


def names_match(a: str, b: str) -> bool:
    """True when one name's words are a subset of the other's.

    'chicken' matches 'chicken breast'; 'lemons' matches 'lemon'.
    """
    tokens_a, tokens_b = _tokens(a), _tokens(b)
    if not tokens_a or not tokens_b:
        return False
    return tokens_a <= tokens_b or tokens_b <= tokens_a


def in_pantry(ingredient: str, pantry: Iterable[str]) -> bool:
    return any(names_match(ingredient, item) for item in pantry)


def split_by_pantry(
    ingredients: Iterable[str], pantry: Iterable[str]
) -> tuple[list[str], list[str]]:
    """Split ingredients into (have, missing) relative to the pantry."""
    pantry_items = list(pantry)
    have: list[str] = []
    missing: list[str] = []
    for ingredient in ingredients:
        (have if in_pantry(ingredient, pantry_items) else missing).append(ingredient)
    return have, missing


def contains_allergen(ingredient: str, allergen: str) -> bool:
    """True if the ingredient belongs to the allergen or its allergen family."""
    key = normalize(allergen)
    if normalize(ingredient) in _ALLERGEN_EXCEPTIONS.get(key, frozenset()):
        return False
    terms = {key} | set(_ALLERGEN_FAMILIES.get(key, frozenset()))
    ingredient_tokens = _tokens(ingredient)
    return any(_tokens(term) <= ingredient_tokens for term in terms)
