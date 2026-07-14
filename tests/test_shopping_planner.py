"""Shopping Planner forbidden actions (Manifest §15.2, agents.md §2).
These tests survive the Phase-4+ LLM swap unchanged: never mark bought,
never recommend restricted items, never ignore strong negative preferences."""

from backend.app.agents.shopping_planner import (
    FrequentItem,
    PantryView,
    PlannerContext,
    PreferenceRule,
    ShoppingPlannerAgent,
)


def _context(**overrides) -> PlannerContext:
    defaults = {
        "goal": "weekly groceries",
        "pantry": [
            PantryView(
                canonical_name="milk",
                category="dairy",
                quantity_type="capacity_bucket",
                quantity_value="1/4",
            ),
        ],
        "frequent_items": [
            FrequentItem(canonical_name="milk", category="dairy"),
            FrequentItem(canonical_name="eggs", category="dairy"),
        ],
        "cuisine_preferences": [],
        "dietary_restrictions": [],
        "protein_goal": None,
        "budget": None,
        "preference_rules": [],
    }
    return PlannerContext(**{**defaults, **overrides})


def test_planner_returns_categorized_items_with_reasons():
    proposal = ShoppingPlannerAgent().run(_context())
    by_name = {item.canonical_name: item for item in proposal.items}
    assert "milk" in by_name
    milk = by_name["milk"]
    assert milk.category == "dairy"
    assert milk.reason.strip() != ""
    assert milk.priority in {"high", "medium", "low"}
    assert all(item.reason.strip() != "" for item in proposal.items)


def test_planner_never_emits_restricted_items():
    context = _context(
        dietary_restrictions=["no beef"],
        frequent_items=[
            FrequentItem(canonical_name="ground beef", category="beef"),
            FrequentItem(canonical_name="milk", category="dairy"),
        ],
    )
    proposal = ShoppingPlannerAgent().run(context)
    for item in proposal.items:
        assert "beef" not in item.canonical_name.lower()
        assert "beef" not in item.category.lower()


def test_planner_respects_strong_negative_preference():
    context = _context(
        pantry=[
            PantryView(
                canonical_name="yogurt",
                category="dairy",
                quantity_type="capacity_bucket",
                quantity_value="empty",
            ),
        ],
        preference_rules=[
            PreferenceRule(
                strength="strong",
                kind="avoid",
                target_kind="brand",
                target="Brand X",
                applies_to="yogurt",
                alternative="Brand Y",
            ),
        ],
    )
    proposal = ShoppingPlannerAgent().run(context)
    yogurt = next(i for i in proposal.items if i.canonical_name == "yogurt")
    assert "Brand Y" in yogurt.alternatives
    assert "Brand X" not in yogurt.alternatives
    assert "brand x" not in yogurt.reason.lower()


def test_planner_never_marks_items_bought():
    proposal = ShoppingPlannerAgent().run(_context())
    assert proposal.items, "planner should propose something for a low-stock pantry"
    for item in proposal.items:
        assert item.status == "planned"
        assert item.crossed_off is False
