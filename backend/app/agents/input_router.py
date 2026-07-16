import re
from typing import Literal

from pydantic import BaseModel, Field

from backend.app.agents.llm import LLMClient


class RouterContext(BaseModel):
    text: str
    has_image: bool = False
    checklist_item_id: str | None = None


class RouteDecision(BaseModel):
    intent: Literal[
        "shopping_assist", "consumption_update", "recipe_request",
        "checklist_action", "general_question"
    ]
    agents: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)
    phase_status: str | None = None


def _item_candidate(text: str) -> str | None:
    lowered = re.sub(r"[^a-z0-9\s-]", "", text.lower())
    patterns = [
        r"(?:this|the)\s+([a-z-]+)$",
        r"(?:of|some|lot of)\s+([a-z-]+)$",
        r"buy\s+(?:this\s+)?([a-z-]+)$",
        r"off\s+([a-z-]+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            return match.group(1)
    return None


class InputRouterAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, context: RouterContext) -> RouteDecision:
        # The hosted structured classifier plugs in here. Phase 4 always has a
        # deterministic fallback so routing remains available during outages.
        try:
            return self.llm.complete_structured(
                f"[ROUTE]\n{context.model_dump_json()}", RouteDecision
            )
        except Exception:
            return self._fallback(context)

    @staticmethod
    def _fallback(context: RouterContext) -> RouteDecision:
        text = context.text.lower()
        candidate = _item_candidate(context.text)
        payload: dict[str, object] = {}
        if candidate:
            payload["item_candidate"] = candidate
        if context.checklist_item_id or "cross off" in text:
            if context.checklist_item_id:
                payload["checklist_item_id"] = context.checklist_item_id
            return RouteDecision(intent="checklist_action", agents=["checklist_confirmation"], payload=payload)
        if any(term in text for term in ("used ", "left", "remaining")):
            return RouteDecision(intent="consumption_update", agents=["consumption_update"], payload=payload)
        if any(term in text for term in ("cook", "recipe", "meal")):
            return RouteDecision(intent="recipe_request", agents=["recipe_planner"], payload=payload, phase_status="coming_in_phase_8")
        if context.has_image or any(term in text for term in ("buy", "should i", "which product")):
            return RouteDecision(intent="shopping_assist", agents=["while_shopping_assistant"], payload=payload)
        return RouteDecision(intent="general_question", agents=["while_shopping_assistant"], payload=payload)
