"""Conversation state and turn handling for the simulator."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .bridge import MCPBridge
from .nlu import Intent, IntentParser, ParsedIntent, RecipeRef
from .renderer import HELP_TEXT, Reply, ResponseRenderer

FALLBACK_TEXT = (
    "I didn't catch that. Try: I have eggs and tomatoes, what can I cook, "
    "what am I missing for the first one, or schedule it for tomorrow at 7pm."
)


@dataclass
class Turn:
    """One exchange shown in the transcript."""

    utterance: str
    speech: str
    card: dict[str, Any] | None = None
    tool: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConversationState:
    """What the simulated assistant remembers between turns."""

    turns: list[Turn] = field(default_factory=list)
    known_recipes: list[RecipeRef] = field(default_factory=list)
    focus_recipe_id: str | None = None


class DialogueManager:
    """Parse -> call the MCP tool -> render, for one single-user demo session."""

    def __init__(
        self,
        bridge: MCPBridge,
        parser: IntentParser | None = None,
        renderer: ResponseRenderer | None = None,
    ) -> None:
        self._bridge = bridge
        self._parser = parser or IntentParser()
        self._renderer = renderer or ResponseRenderer()
        self.state = ConversationState()

    def reset(self) -> None:
        self.state = ConversationState()

    async def handle(self, utterance: str) -> Turn:
        parsed = self._parser.parse(utterance, self.state.known_recipes, self.state.focus_recipe_id)
        reply, tool = await self._respond(parsed)
        turn = Turn(utterance=utterance.strip(), speech=reply.speech, card=reply.card, tool=tool)
        self.state.turns.append(turn)
        return turn

    async def _respond(self, parsed: ParsedIntent) -> tuple[Reply, dict[str, Any] | None]:
        if parsed.intent is Intent.HELP:
            return Reply(HELP_TEXT), None
        if parsed.clarification:
            return Reply(parsed.clarification), None
        if parsed.tool_name is None:
            return Reply(FALLBACK_TEXT), None

        outcome = await self._bridge.call_tool(parsed.tool_name, parsed.arguments)
        self._remember(outcome.name, outcome.arguments, outcome.structured, outcome.is_error)
        reply = self._renderer.render(outcome, view_only=parsed.intent is Intent.VIEW_PANTRY)
        tool = {"name": outcome.name, "arguments": outcome.arguments, "is_error": outcome.is_error}
        return reply, tool

    def _remember(self, name: str, arguments: dict[str, Any], data: dict[str, Any], is_error: bool) -> None:
        if is_error:
            return
        if name == "find_recipes" and data.get("recipes"):
            self.state.known_recipes = [RecipeRef(r["recipe_id"], r["title"]) for r in data["recipes"]]
            self.state.focus_recipe_id = data["recipes"][0]["recipe_id"]
        elif name in {"build_shopping_list", "schedule_meal"}:
            self.state.focus_recipe_id = arguments.get("recipe_id", self.state.focus_recipe_id)
