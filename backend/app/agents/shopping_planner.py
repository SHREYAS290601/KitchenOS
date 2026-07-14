"""Shopping Planner Agent v1 — deterministic rules (agents.md §2).

Forbidden (Manifest §15.2, enforced by tests that survive the LLM swap):
marking items bought; recommending restricted items; ignoring strong
negative preference rules.
"""

from typing import Literal

from pydantic import BaseModel, Field

LOW_CAPACITY_BUCKETS = {"1/4", "empty"}
LOW_COUNT_THRESHOLD = 1


class PantryView(BaseModel):
    """The slim, read-only slice of the ledger the planner sees."""

    canonical_name: str
    category: str
    quantity_type: str = "unknown"
    quantity_value: str | int | None = None
    unit_label: str | None = None


class FrequentItem(BaseModel):
    canonical_name: str
    category: str


class PreferenceRule(BaseModel):
    """Stub interface — Phase 9 supplies real rules through the same shape."""

    strength: Literal["strong", "weak"]
    kind: Literal["avoid", "prefer"]
    target_kind: Literal["brand", "product", "category"]
    target: str
    applies_to: str
    alternative: str | None = None


class PlannerContext(BaseModel):
    goal: str
    pantry: list[PantryView] = Field(default_factory=list)
    frequent_items: list[FrequentItem] = Field(default_factory=list)
    cuisine_preferences: list[str] = Field(default_factory=list)
    dietary_restrictions: list[str] = Field(default_factory=list)
    protein_goal: str | None = None
    budget: float | None = None
    preference_rules: list[PreferenceRule] = Field(default_factory=list)


class PlannedItem(BaseModel):
    canonical_name: str
    category: str
    desired_quantity: int | None = None
    unit_label: str | None = None
    reason: str
    priority: Literal["high", "medium", "low"]
    status: Literal["planned"] = "planned"
    crossed_off: Literal[False] = False
    alternatives: list[str] = Field(default_factory=list)


class PlannerProposal(BaseModel):
    items: list[PlannedItem]


def _restricted_terms(restrictions: list[str]) -> list[str]:
    """"no beef" -> "beef"; keep whole phrases too so "no red meat" blocks both."""
    terms = []
    for restriction in restrictions:
        phrase = restriction.lower().removeprefix("no ").strip()
        if phrase:
            terms.append(phrase)
    return terms


def _is_restricted(name: str, category: str, terms: list[str]) -> bool:
    haystack = f"{name} {category}".lower()
    return any(term in haystack for term in terms)


def _is_low(view: PantryView) -> bool:
    if view.quantity_type == "capacity_bucket":
        return view.quantity_value in LOW_CAPACITY_BUCKETS
    if view.quantity_type == "count":
        try:
            return int(view.quantity_value) <= LOW_COUNT_THRESHOLD
        except (TypeError, ValueError):
            return False
    return False


class ShoppingPlannerAgent:
    def run(self, context: PlannerContext) -> PlannerProposal:
        terms = _restricted_terms(context.dietary_restrictions)
        frequent_names = {f.canonical_name for f in context.frequent_items}
        items: dict[str, PlannedItem] = {}

        for view in context.pantry:
            if not _is_low(view):
                continue
            reason = f"running low ({view.quantity_value} left)"
            if view.canonical_name in frequent_names:
                reason += " and a frequent restock"
            items[view.canonical_name] = PlannedItem(
                canonical_name=view.canonical_name,
                category=view.category,
                unit_label=view.unit_label,
                reason=reason,
                priority="high",
            )

        for frequent in context.frequent_items:
            if frequent.canonical_name in items:
                continue
            items[frequent.canonical_name] = PlannedItem(
                canonical_name=frequent.canonical_name,
                category=frequent.category,
                reason="frequent restock in your purchase history",
                priority="medium",
            )

        allowed = [
            item
            for item in items.values()
            if not _is_restricted(item.canonical_name, item.category, terms)
        ]

        for item in allowed:
            for rule in context.preference_rules:
                if rule.strength != "strong" or rule.kind != "avoid":
                    continue
                if rule.applies_to.lower() not in item.canonical_name.lower():
                    continue
                if rule.alternative and rule.alternative not in item.alternatives:
                    item.alternatives.append(rule.alternative)

        return PlannerProposal(items=allowed)
