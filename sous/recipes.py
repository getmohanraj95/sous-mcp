"""Recipe catalog and the engine that filters and ranks it."""
from __future__ import annotations

from .models import DietaryProfile, RankedRecipe, Recipe
from .ranking import BedrockRanker, OverlapRanker, RecipeRanker

DEFAULT_CATALOG: tuple[Recipe, ...] = (
    Recipe(
        recipe_id="lemon-spinach-chicken",
        title="Lemon Spinach Chicken",
        ingredients=("chicken breast", "spinach", "lemon", "olive oil", "garlic"),
        steps=(
            "Season the chicken and sear it in olive oil for 6 to 7 minutes a side.",
            "Add sliced garlic and wilt the spinach in the same pan.",
            "Finish with lemon juice and serve.",
        ),
        base_servings=2,
        tags=("dairy-free", "gluten-free", "high-protein", "quick"),
    ),
    Recipe(
        recipe_id="chickpea-spinach-curry",
        title="Chickpea Spinach Curry",
        ingredients=("chickpeas", "coconut milk", "spinach", "onion", "curry powder", "garlic"),
        steps=(
            "Soften the onion and garlic in a little oil.",
            "Stir in curry powder, chickpeas, and coconut milk; simmer 10 minutes.",
            "Fold in the spinach until just wilted.",
        ),
        base_servings=4,
        tags=("vegan", "vegetarian", "dairy-free", "gluten-free"),
    ),
    Recipe(
        recipe_id="lemon-butter-salmon",
        title="Lemon Butter Salmon",
        ingredients=("salmon fillet", "butter", "lemon", "garlic", "parsley"),
        steps=(
            "Pan-sear the salmon skin-side down for 4 minutes until crisp, then flip.",
            "Melt butter with garlic and lemon juice and spoon it over the fillet.",
            "Garnish with parsley.",
        ),
        base_servings=2,
        tags=("pescatarian", "gluten-free", "high-protein", "quick"),
    ),
    Recipe(
        recipe_id="garlic-tomato-pasta",
        title="Garlic Tomato Pasta",
        ingredients=("pasta", "tomatoes", "garlic", "olive oil", "basil", "parmesan"),
        steps=(
            "Boil the pasta in salted water until al dente.",
            "Cook garlic in olive oil, add chopped tomatoes, and simmer 8 minutes.",
            "Toss with the pasta, basil, and grated parmesan.",
        ),
        base_servings=2,
        tags=("vegetarian", "quick"),
    ),
    Recipe(
        recipe_id="veggie-fried-rice",
        title="Veggie Fried Rice",
        ingredients=("cooked rice", "eggs", "frozen peas", "carrot", "soy sauce", "spring onion"),
        steps=(
            "Scramble the eggs in a hot wok and set aside.",
            "Stir-fry diced carrot and peas, then add the rice.",
            "Season with soy sauce, return the eggs, and top with spring onion.",
        ),
        base_servings=2,
        tags=("vegetarian", "dairy-free", "quick"),
    ),
    Recipe(
        recipe_id="black-bean-tacos",
        title="Black Bean Tacos",
        ingredients=("black beans", "corn tortillas", "avocado", "lime", "onion", "coriander"),
        steps=(
            "Warm the black beans with diced onion and a pinch of salt.",
            "Toast the tortillas in a dry pan.",
            "Fill with beans, sliced avocado, coriander, and a squeeze of lime.",
        ),
        base_servings=4,
        tags=("vegan", "vegetarian", "dairy-free", "gluten-free", "quick"),
    ),
    Recipe(
        recipe_id="shakshuka",
        title="Shakshuka",
        ingredients=("eggs", "tomatoes", "onion", "bell pepper", "garlic", "cumin"),
        steps=(
            "Soften onion, pepper, and garlic; add cumin and chopped tomatoes.",
            "Simmer for 10 minutes until thick.",
            "Make wells, crack in the eggs, cover, and cook 5 to 6 minutes.",
        ),
        base_servings=2,
        tags=("vegetarian", "dairy-free", "gluten-free"),
    ),
    Recipe(
        recipe_id="peanut-noodle-bowl",
        title="Peanut Noodle Bowl",
        ingredients=("rice noodles", "peanut butter", "soy sauce", "lime", "cucumber", "carrot"),
        steps=(
            "Soak or boil the rice noodles and rinse in cold water.",
            "Whisk peanut butter, soy sauce, lime juice, and a splash of warm water.",
            "Toss with the noodles, shredded carrot, and cucumber.",
        ),
        base_servings=2,
        tags=("vegan", "vegetarian", "dairy-free"),
    ),
)


class RecipeEngine:
    """Filters recipes by dietary profile, then ranks them with a pluggable ranker.

    Filtering is deterministic and always runs first; the ranker (overlap or
    Amazon Bedrock) only orders recipes that are already safe for the user.
    """

    def __init__(
        self,
        catalog: tuple[Recipe, ...] | list[Recipe] | None = None,
        ranker: RecipeRanker | None = None,
    ) -> None:
        self._catalog: tuple[Recipe, ...] = tuple(catalog) if catalog is not None else DEFAULT_CATALOG
        self._ranker: RecipeRanker = ranker or OverlapRanker()

    @property
    def ranking_backend(self) -> str:
        """Which strategy produced the most recent ranking ('overlap', 'bedrock', 'fallback')."""
        if isinstance(self._ranker, BedrockRanker):
            return self._ranker.last_source
        return "overlap"

    @property
    def supported_tags(self) -> set[str]:
        return {tag for recipe in self._catalog for tag in recipe.tags}

    def find(
        self,
        pantry: list[str],
        profile: DietaryProfile,
        max_results: int = 3,
    ) -> list[RankedRecipe]:
        eligible = [recipe for recipe in self._catalog if profile.allows(recipe)]
        if not eligible:
            return []
        scores = self._rank(eligible, pantry)
        ranked = sorted(eligible, key=lambda r: (-scores.get(r.recipe_id, 0.0), r.title))
        return [RankedRecipe(recipe, scores.get(recipe.recipe_id, 0.0)) for recipe in ranked[:max_results]]

    def get(self, recipe_id: str) -> Recipe | None:
        key = recipe_id.strip().lower()
        return next((recipe for recipe in self._catalog if recipe.recipe_id == key), None)

    def _rank(self, recipes: list[Recipe], pantry: list[str]) -> dict[str, float]:
        return self._ranker.rank(recipes, pantry)
