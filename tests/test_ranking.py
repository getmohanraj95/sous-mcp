"""Bedrock ranking with a fake client; no AWS account needed."""
from __future__ import annotations

import json
from typing import Any

import pytest

from sous.models import DietaryProfile
from sous.ranking import BedrockRanker
from sous.recipes import RecipeEngine

PANTRY = ["chicken breast", "spinach", "lemon"]


class FakeBedrockClient:
    def __init__(self, reply: str | Exception) -> None:
        self._reply = reply
        self.calls: list[dict[str, Any]] = []

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if isinstance(self._reply, Exception):
            raise self._reply
        return {"output": {"message": {"content": [{"text": self._reply}]}}}


def test_uses_model_scores_and_ignores_unknown_ids() -> None:
    reply = json.dumps({"scores": [
        {"recipe_id": "chickpea-spinach-curry", "score": 0.95},
        {"recipe_id": "lemon-spinach-chicken", "score": 0.2},
        {"recipe_id": "made-up", "score": 1.0},
    ]})
    ranker = BedrockRanker("test-model", client=FakeBedrockClient(reply))
    engine = RecipeEngine(ranker=ranker)
    results = engine.find(PANTRY, DietaryProfile(restrictions=["dairy-free"]))
    assert results[0].recipe.recipe_id == "chickpea-spinach-curry"
    assert engine.ranking_backend == "bedrock"


def test_never_sends_dietary_profile_to_model() -> None:
    client = FakeBedrockClient(json.dumps({"scores": [{"recipe_id": "shakshuka", "score": 1}]}))
    RecipeEngine(ranker=BedrockRanker("m", client=client)).find(["eggs"], DietaryProfile(allergies=["peanut"]))
    sent = client.calls[0]["messages"][0]["content"][0]["text"]
    assert "peanut" not in sent
    assert "allergies" not in sent and "restrictions" not in sent


@pytest.mark.parametrize("reply", ["not json", '{"scores": []}', RuntimeError("throttled")])
def test_falls_back_to_overlap_on_failure(reply: str | Exception) -> None:
    engine = RecipeEngine(ranker=BedrockRanker("m", client=FakeBedrockClient(reply)))
    results = engine.find(PANTRY, DietaryProfile())
    assert results[0].recipe.recipe_id == "lemon-spinach-chicken"
    assert engine.ranking_backend == "fallback"


def test_parse_scores_strips_code_fences_and_clamps() -> None:
    text = '```json\n{"scores": [{"recipe_id": "a", "score": 3}]}\n```'
    assert BedrockRanker.parse_scores(text, {"a"}) == {"a": 1.0}


def test_server_falls_back_when_bedrock_cannot_be_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    import server
    from sous.ranking import OverlapRanker

    monkeypatch.setenv("SOUS_RANKER", "bedrock")
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    monkeypatch.setenv("AWS_CONFIG_FILE", "/nonexistent")
    assert isinstance(server.build_ranker(), OverlapRanker)
