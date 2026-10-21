"""Recipe ranking strategies for RecipeEngine.

    OverlapRanker  deterministic pantry-coverage scoring, no dependencies.
    BedrockRanker  Amazon Bedrock (Converse API) scoring, with automatic
                   fallback to OverlapRanker on any AWS or parsing failure.

Safety: dietary and allergy filtering happens in RecipeEngine BEFORE ranking,
so a ranker can only reorder recipes that are already safe. For the same
reason, and for data minimisation, BedrockRanker never sends the user's
restrictions or allergies to the model.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from .matching import split_by_pantry
from .models import Recipe

logger = logging.getLogger(__name__)


class RecipeRanker(Protocol):
    """Contract every ranking strategy satisfies."""

    def rank(self, recipes: list[Recipe], pantry: list[str]) -> dict[str, float]:
        """Return a score in [0.0, 1.0] for every recipe_id in `recipes`."""
        ...


class OverlapRanker:
    """Scores a recipe by the fraction of its ingredients already in the pantry."""

    def rank(self, recipes: list[Recipe], pantry: list[str]) -> dict[str, float]:
        return {recipe.recipe_id: self.score(recipe, pantry) for recipe in recipes}

    @staticmethod
    def score(recipe: Recipe, pantry: list[str]) -> float:
        if not recipe.ingredients:
            return 0.0
        have, _ = split_by_pantry(recipe.ingredients, pantry)
        return len(have) / len(recipe.ingredients)


class BedrockRanker:
    """Ranks recipes with a foundation model on Amazon Bedrock via the Converse API."""

    _SYSTEM_PROMPT = (
        "You are the ranking component of a home-cooking assistant. Given the "
        "ingredients a person has and a list of candidate recipes, score each "
        "recipe from 0.0 to 1.0 for how good a choice it is to cook right now: "
        "strongly favour recipes that use what they already have and need few "
        "extra purchases; break ties toward simpler recipes. Respond with JSON "
        'only, no prose and no markdown, exactly in this shape: {"scores": '
        '[{"recipe_id": "<id>", "score": <number>}]}. Include every recipe_id '
        "you were given and no others."
    )

    def __init__(
        self,
        model_id: str,
        region_name: str | None = None,
        fallback: RecipeRanker | None = None,
        client: Any | None = None,
        max_tokens: int = 512,
    ) -> None:
        self._model_id = model_id
        self._max_tokens = max_tokens
        self._fallback = fallback or OverlapRanker()
        self._client = client or self._build_client(region_name)
        self.last_source = "none"

    @property
    def model_id(self) -> str:
        return self._model_id

    @staticmethod
    def _build_client(region_name: str | None) -> Any:
        # Imported lazily so overlap mode never requires boto3 to be installed.
        import boto3
        from botocore.config import Config

        return boto3.client(
            "bedrock-runtime",
            region_name=region_name,
            config=Config(
                connect_timeout=5,
                read_timeout=15,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        )

    def rank(self, recipes: list[Recipe], pantry: list[str]) -> dict[str, float]:
        if not recipes:
            return {}
        fallback_scores = self._fallback.rank(recipes, pantry)
        try:
            model_scores = self._invoke(recipes, pantry)
        except Exception as exc:  # noqa: BLE001 - any failure must degrade gracefully
            logger.warning("Bedrock ranking failed, using fallback ranker: %s", exc)
            self.last_source = "fallback"
            return fallback_scores

        logger.info("Ranked %d recipes with Bedrock model %s", len(recipes), self._model_id)
        self.last_source = "bedrock"
        return {
            recipe.recipe_id: model_scores.get(recipe.recipe_id, fallback_scores[recipe.recipe_id])
            for recipe in recipes
        }

    def _invoke(self, recipes: list[Recipe], pantry: list[str]) -> dict[str, float]:
        payload = {
            "pantry": sorted(pantry),
            "recipes": [
                {
                    "recipe_id": recipe.recipe_id,
                    "title": recipe.title,
                    "ingredients": list(recipe.ingredients),
                }
                for recipe in recipes
            ],
        }
        response = self._client.converse(
            modelId=self._model_id,
            system=[{"text": self._SYSTEM_PROMPT}],
            messages=[{"role": "user", "content": [{"text": json.dumps(payload)}]}],
            inferenceConfig={"maxTokens": self._max_tokens, "temperature": 0.0},
        )
        text = "".join(
            block.get("text", "") for block in response["output"]["message"]["content"]
        )
        return self.parse_scores(text, {recipe.recipe_id for recipe in recipes})

    @staticmethod
    def parse_scores(text: str, valid_ids: set[str]) -> dict[str, float]:
        """Parse and validate model output; ignores unknown ids, clamps scores."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").removeprefix("json").strip()
        data = json.loads(cleaned)
        scores: dict[str, float] = {}
        for entry in data["scores"]:
            recipe_id = str(entry["recipe_id"])
            if recipe_id in valid_ids:
                scores[recipe_id] = min(max(float(entry["score"]), 0.0), 1.0)
        if not scores:
            raise ValueError("Model returned no usable scores.")
        return scores
