# PantryOps Edge Phase 8: Recipe and Consumption Implementation Plan

> **For agentic workers:** Implement task-by-task with strict TDD: write the failing test, watch it fail, implement, watch it pass, commit. Steps use checkbox (`- [ ]`) syntax. REQUIRED ECC SKILLS before starting: `/ecc:python-patterns` (matcher + deduction logic), `/ecc:agent-harness-construction` (Recipe Planner + Auditor availability check as testable agents), `/ecc:python-testing` (no-deduct-until-confirm + capacity step-down tests), `/ecc:react-testing` (accessible recipe screen).

**Goal:** Recommend recipes from the pantry ledger with available/missing ingredient split, deduct inventory only on user-confirmed cooking through the ledger write path, and fire low-stock/reorder lifecycle triggers.

**Architecture:** Per `documents/specs/architecture.md` §7–§9 and invariant 7: **recipes never auto-deduct**. The Recipe Planner Agent (`documents/specs/agents.md` #13) reads the ledger and preferences, prefers use-soon items, respects restrictions, and produces recommendations only. Deduction happens exclusively on `POST /recipes/{id}/confirm-cooked` (`documents/specs/api-spec.md`), writes a `ConsumptionEvent` (`documents/specs/data-models.md` §4.10), and applies every quantity change via `services/ledger.py::apply_update()`. The Auditor verifies every recommended recipe cites only ledger-available ingredients before output (Manifest §23 mitigation).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, pytest + httpx TestClient. Mobile: Expo React Native, Jest + @testing-library/react-native.

**Out of scope for Phase 8** (later plans): preference learning from reviews (Phase 9 — the planner consumes rules; it does not create them), next-list generation tuning (Phase 9/10), calorie/macro medical-grade planning (out of MVP entirely, Manifest §4), Store/Cost expense reports.

**Prerequisites:** Phases 1–7 complete: ledger write path (`apply_update`), quantity validators, checklist flow, consent, background jobs, vision estimates, and product enrichment all green.

---

## File structure (locked in by this plan)

```text
backend/app/
├── recipes/
│   ├── __init__.py
│   ├── recommender.py        # rank recipes by use-soon + preferences
│   ├── matcher.py            # ingredient ↔ ledger availability match
│   └── deduction.py          # compute deductions from a confirmed cook
├── models/
│   ├── recipe.py             # Recipe + RecipeIngredient
│   └── consumption_event.py  # ConsumptionEvent (data-models.md §4.10)
├── schemas/recipes.py
├── agents/recipe_planner.py
├── services/
│   ├── recipes.py            # recommend orchestration
│   └── consumption.py        # confirm-cooked deduction + low-stock flags
├── routes/recipes.py
backend/alembic/versions/<recipes_consumption>.py
tests/
├── test_matcher.py
├── test_recommender.py
├── test_recipe_api.py
├── test_confirm_cooked.py
├── test_low_stock.py
└── test_recipe_auditor.py
mobile/screens/RecipesScreen.tsx
mobile/__tests__/RecipesScreen.test.tsx
```

---

### Task 1: Recipe models + migration

**Files:**
- Create: `backend/app/models/recipe.py`, `backend/app/models/consumption_event.py`, `backend/alembic/versions/<recipes_consumption>.py`
- Test: `tests/test_matcher.py` (model round-trip section)

- [ ] **Step 1: Write the failing test** — round-trip a `Recipe` with `RecipeIngredient` rows (`canonical_name`, `required_quantity`, `quantity_type`, `optional` flag) and a `ConsumptionEvent` with `items_used` JSONB matching data-models.md §4.10; assert `source` is one of `user_message | recipe_confirmation`.

- [ ] **Step 2: Run to verify it fails** — `uv run pytest tests/test_matcher.py -v` → FAIL (ImportError).

- [ ] **Step 3: Implement the models; generate + hand-review the migration** — `uv run alembic revision --autogenerate -m "recipes and consumption events"`.

- [ ] **Step 4: Run to verify it passes**, then run the migration-parity test from Phase 1 — both green.

- [ ] **Step 5: Commit** — `feat(recipes): recipe and consumption event models`

---

### Task 2: Ingredient matcher

**Files:**
- Create: `backend/app/recipes/matcher.py`
- Test: `tests/test_matcher.py` (append)

- [ ] **Step 1: Write the failing tests** — key assertions:

```python
def test_matcher_splits_available_and_missing(db, seeded_pantry):
    # pantry: eggs count=6, rice bucket=3/4, milk bucket=empty
    result = match_ingredients(db, ingredients=[
        Ing("eggs", 2, "count"), Ing("rice", "1/4", "capacity_bucket"),
        Ing("milk", "1/4", "capacity_bucket"), Ing("paneer", 1, "count"),
    ])
    assert [i.canonical_name for i in result.available] == ["eggs", "rice"]
    assert [i.canonical_name for i in result.missing] == ["milk", "paneer"]  # empty bucket = missing


def test_matcher_is_quantity_aware(db, seeded_pantry):
    # eggs count=1 cannot satisfy a 2-egg requirement
    result = match_ingredients(db, ingredients=[Ing("eggs", 2, "count")])
    assert result.missing and result.missing[0].reason == "insufficient_quantity"
```

- [ ] **Step 2: Run to verify they fail** — FAIL (`match_ingredients` not defined).

- [ ] **Step 3: Implement `matcher.py`** — reads ledger via read-only queries (no writes); `empty`/`used_up` items count as missing; capacity buckets compare ordinally (`3/4 ≥ 1/4`); unknown quantity items match as `available_unverified` so the planner can flag them.

- [ ] **Step 4: Run to verify they pass.**

- [ ] **Step 5: Commit** — `feat(recipes): quantity-aware ingredient matcher`

---

### Task 3: Recommender + Recipe Planner Agent

**Files:**
- Create: `backend/app/recipes/recommender.py`, `backend/app/agents/recipe_planner.py`
- Test: `tests/test_recommender.py`

- [ ] **Step 1: Write the failing tests** — the agent's forbidden actions (`agents.md` #13) become assertions:

```python
def test_planner_never_recommends_restricted_food(db, seeded_pantry_with_beef):
    recs = RecipePlannerAgent().run(ctx(restrictions=["no beef"]))
    assert all("beef" not in r.ingredient_names for r in recs.recipes)


def test_planner_prefers_use_soon_items(db, seeded_pantry_with_expiring_spinach):
    recs = RecipePlannerAgent().run(ctx())
    assert "spinach" in recs.recipes[0].ingredient_names  # expiring item ranked first


def test_planner_never_claims_unavailable_as_available(db, seeded_pantry):
    recs = RecipePlannerAgent().run(ctx())
    for r in recs.recipes:
        assert set(r.available_ingredients).isdisjoint(set(r.missing_ingredients))


def test_recommendation_mutates_nothing(db, seeded_pantry, change_log_count):
    RecipePlannerAgent().run(ctx())
    assert change_log_count() == 0  # invariant 7: no writes from recommendation
```

- [ ] **Step 2: Run to verify they fail** — FAIL (ImportError).

- [ ] **Step 3: Implement** — `recommender.py` ranks matched recipes: use-soon items first, preference rules applied (avoid/prefer from Phase 9 rules if present, no-op until then), restriction filter is a hard exclusion before ranking. `recipe_planner.py` wraps it as an agent returning a typed proposal — read-only context, no session writes.

- [ ] **Step 4: Run to verify they pass** — the mutation test proves recommendation touches no ledger row.

- [ ] **Step 5: Commit** — `feat(recipes): planner agent with restriction filter and use-soon ranking`

---

### Task 4: Recommend endpoint + auditor gate

**Files:**
- Create: `backend/app/routes/recipes.py`, `backend/app/schemas/recipes.py`, `backend/app/services/recipes.py`
- Modify: `backend/app/agents/auditor.py`
- Test: `tests/test_recipe_api.py`, `tests/test_recipe_auditor.py`

- [ ] **Step 1: Write the failing tests** — `POST /recipes/recommend` (api-spec.md) returns 200 with `available_ingredients`, `missing_ingredients`, `expected_inventory_impact` per recipe; and the auditor gate:

```python
def test_auditor_blocks_recipe_citing_missing_item(db):
    bad = RecipeProposal(name="omelette", available_ingredients=["eggs", "butter"])  # butter not in ledger
    verdict = AuditorAgent().run(audit_ctx(proposal=bad))
    assert verdict.blocked and "butter" in verdict.reason
```

- [ ] **Step 2: Run to verify they fail** — FAIL (404 / ImportError).

- [ ] **Step 3: Implement** — `services/recipes.py` orchestrates matcher → planner → auditor; a blocked recipe is dropped (or annotated `needs_review`), never silently served. Route validates with `schemas/recipes.py`, delegates, serializes.

- [ ] **Step 4: Run to verify they pass** — `uv run pytest tests/test_recipe_api.py tests/test_recipe_auditor.py -v`.

- [ ] **Step 5: Commit** — `feat(recipes): recommend endpoint with auditor availability gate`

---

### Task 5: Deduction engine

**Files:**
- Create: `backend/app/recipes/deduction.py`, `backend/app/services/consumption.py`
- Test: `tests/test_confirm_cooked.py`

- [ ] **Step 1: Write the failing tests** — both quantity types:

```python
def test_count_deduction(db, pantry_eggs_6):
    plan = compute_deduction(db, used=[Used("eggs", amount_used=2)])
    assert plan[0].new_quantity_value == 4


def test_capacity_bucket_step_down(db, pantry_rice_three_quarters):
    plan = compute_deduction(db, used=[Used("rice", new_quantity_value="1/2")])
    assert plan[0].new_quantity_value == "1/2"  # user states the new bucket; we never interpolate


def test_deduction_below_zero_clamps_and_flags(db, pantry_eggs_1):
    plan = compute_deduction(db, used=[Used("eggs", amount_used=3)])
    assert plan[0].new_quantity_value == 0 and plan[0].needs_user_confirmation
```

- [ ] **Step 2: Run to verify they fail** — FAIL (ImportError).

- [ ] **Step 3: Implement** — counts decrement arithmetically; capacity buckets accept the user-stated new bucket (fail-safe scale — never computed interpolation); over-deduction clamps to zero/empty and sets `needs_user_confirmation`. Pure functions; no session writes here.

- [ ] **Step 4: Run to verify they pass.**

- [ ] **Step 5: Commit** — `feat(recipes): deduction engine for counts and capacity buckets`

---

### Task 6: Confirm-cooked endpoint (the only deduction path)

**Files:**
- Modify: `backend/app/routes/recipes.py`, `backend/app/services/consumption.py`
- Test: `tests/test_confirm_cooked.py` (append)

- [ ] **Step 1: Write the failing tests** —

```python
def test_confirm_cooked_deducts_via_ledger(client, db, pantry_eggs_6):
    r = client.post(f"/recipes/{recipe_id}/confirm-cooked",
                    json={"used_items": [{"pantry_item_id": eggs_id, "amount_used": 2}]})
    assert r.status_code == 200
    item = get_item(db, eggs_id)
    assert item.quantity_value["value"] == 4
    assert db.query(ConsumptionEvent).count() == 1
    log = db.query(LedgerChangeLog).filter_by(pantry_item_id=eggs_id).one()
    assert log.source == "recipe_confirmation"  # went through apply_update


def test_recommend_then_no_confirm_deducts_nothing(client, db, pantry_eggs_6):
    client.post("/recipes/recommend", json={"meal_type": "dinner"})
    assert get_item(db, eggs_id).quantity_value["value"] == 6  # invariant 7 end-to-end
```

- [ ] **Step 2: Run to verify they fail** — FAIL (404).

- [ ] **Step 3: Implement** — `services/consumption.py::confirm_cooked()` builds the deduction plan, writes one `ConsumptionEvent`, and applies each quantity change through `ledger.apply_update()` (source `recipe_confirmation`) in one transaction.

- [ ] **Step 4: Run to verify they pass** — and re-run the Phase 2 invariant suite: `uv run pytest tests/test_ledger_service.py -v` stays green.

- [ ] **Step 5: Commit** — `feat(recipes): confirm-cooked deduction through the ledger write path`

---

### Task 7: Low-stock and reorder triggers

**Files:**
- Modify: `backend/app/services/consumption.py`, `backend/app/pantry/lifecycle.py`
- Test: `tests/test_low_stock.py`

- [ ] **Step 1: Write the failing tests** — bucket at `1/4` → lifecycle `low_quantity`; bucket at `empty` or count at 0 → `used_up` then `reorder_candidate`; a `reorder_candidate` item appears in the next Shopping Planner input set (assert via the planner context builder from Phase 3).

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — threshold check runs inside `confirm_cooked()` and the ad-hoc consumption path after deduction; transitions go through `lifecycle.py` (illegal transitions still rejected).

- [ ] **Step 4: Run to verify they pass.**

- [ ] **Step 5: Commit** — `feat(pantry): low-stock and reorder lifecycle triggers`

---

### Task 8: RecipesScreen (mobile)

**Files:**
- Create: `mobile/screens/RecipesScreen.tsx`
- Test: `mobile/__tests__/RecipesScreen.test.tsx`

- [ ] **Step 1: Write the failing tests** — WCAG 2.1 AA assertions are part of the component tests:

```tsx
it("labels available and missing ingredients with text, not color alone", () => {
  const { getByText } = render(<RecipesScreen recipes={[fixtureRecipe]} />);
  expect(getByText("Available: eggs, rice")).toBeTruthy();
  expect(getByText("Missing: milk")).toBeTruthy();
});

it("confirm-cooked action has an accessible name and role", () => {
  const { getByRole } = render(<RecipesScreen recipes={[fixtureRecipe]} />);
  expect(getByRole("button", { name: /I cooked this/i })).toBeTruthy();
});
```

- [ ] **Step 2: Run to verify they fail** — `npx jest mobile/__tests__/RecipesScreen.test.tsx` → FAIL.

- [ ] **Step 3: Implement** — recipe cards with textual Available/Missing prefixes (color is supplementary only), confirm-cooked button (`accessibilityRole="button"`, visible focus), result state announced via `accessibilityLiveRegion="polite"`.

- [ ] **Step 4: Run to verify they pass.**

- [ ] **Step 5: Commit** — `feat(mobile): accessible recipes screen with confirm-cooked flow`

---

## Done criteria for Phase 8

- Recommendation provably mutates nothing (change-log-count test green); deduction happens only via `confirm-cooked` through `apply_update()` with a `ConsumptionEvent` per cook.
- Count decrement, capacity step-down, and over-deduction clamping all tested.
- `low_quantity` → `used_up` → `reorder_candidate` transitions fire and feed the Shopping Planner.
- Auditor blocks any recipe citing a ledger-missing ingredient.
- RecipesScreen passes accessibility assertions (text labels, accessible names, live region).
- Phase 2 invariant suite still green.

## Next phase

[Phase 9 — Review and Preference Memory](phase-9-review-and-preference-memory.md): reviews after first use become structured preference rules that adapt future shopping lists.
