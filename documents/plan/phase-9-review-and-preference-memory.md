# PantryOps Edge Phase 9: Review and Preference Memory Implementation Plan

> **For agentic workers:** Implement task-by-task with strict TDD: write the failing test, watch it fail, implement, watch it pass, commit. Steps use checkbox (`- [ ]`) syntax. REQUIRED ECC SKILLS before starting: `/ecc:python-patterns` (structured preference-rule generalization), `/ecc:python-testing` (first-use gate + overgeneralization tests), `/ecc:code-review` (verify the planner integration respects strong negative rules before merging).

**Goal:** Capture product reviews after first use, generalize them into structured preference rules at the correct scope, and apply avoid/prefer/suggest-alternative logic so future shopping lists adapt.

**Architecture:** Per `documents/specs/architecture.md` invariant 6: **reviews are not strong preferences before first use** — pre-first-use input is stored as `preference_hint`, never `product_review` (Manifest §13, Guardrail 11). Preference rules use the structured schema in `documents/specs/data-models.md` §4.11 — never hardcoded strings. The Preference Review Agent (`documents/specs/agents.md` #15) must not overgeneralize brand → category unless the user says so (Guardrail 12). The Shopping Planner from Phase 3 now consumes active rules.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, pytest + httpx TestClient.

**Out of scope for Phase 9** (later or never): multi-user preference sharing (out of MVP, Manifest §4), long-term preference decay, sentiment analysis beyond the structured review flow, preference UI beyond the review endpoint (mobile review screen ships with the Phase 10 demo polish if time allows).

**Prerequisites:** Phases 1–8 complete — in particular the item lifecycle (`review_eligible`/`reviewed` states from Phase 2) and the Shopping Planner context builder (Phase 3).

---

## File structure (locked in by this plan)

```text
backend/app/
├── models/preference_rule.py     # data-models.md §4.11
├── schemas/preferences.py
├── pantry/preferences.py         # rule application: avoid/prefer/suggest_alternative
├── agents/preference_review.py
├── services/preferences.py       # first-use gate + rule creation
├── routes/reviews.py
backend/alembic/versions/<preference_rules>.py
tests/
├── test_preference_model.py
├── test_preference_service.py
├── test_review_api.py
├── test_preference_application.py
└── test_overgeneralization.py
```

---

### Task 1: PreferenceRule model + migration

**Files:**
- Create: `backend/app/models/preference_rule.py`, `backend/alembic/versions/<preference_rules>.py`
- Test: `tests/test_preference_model.py`

- [ ] **Step 1: Write the failing test** — round-trip the full §4.11 shape:

```python
def test_preference_rule_roundtrip(db):
    rule = PreferenceRule(
        target_scope="brand", target_value="Fage",
        applies_to={"canonical_item": "Greek yogurt", "subcategory": "plain yogurt"},
        sentiment="negative", reason="too sour", strength="strong",
        future_action="avoid", created_from="user_review_after_first_use", active=True,
    )
    db.add(rule); db.commit()
    assert db.query(PreferenceRule).one().future_action == "avoid"


def test_scope_and_action_are_constrained(db):
    with pytest.raises((IntegrityError, ValueError)):
        db.add(PreferenceRule(target_scope="vibes", target_value="x", sentiment="negative",
                              strength="strong", future_action="avoid")); db.commit()
```

- [ ] **Step 2: Run to verify it fails** — `uv run pytest tests/test_preference_model.py -v` → FAIL (ImportError).

- [ ] **Step 3: Implement** — ORM with enum-constrained `target_scope` (`product|brand|category|ingredient|cuisine|store|package_size`), `sentiment`, `strength`, `future_action` (`avoid|prefer|remind|suggest_alternative|ask_before_buying`), `created_from`, JSONB `applies_to`. Generate + hand-review the migration.

- [ ] **Step 4: Run to verify it passes**; migration-parity test stays green.

- [ ] **Step 5: Commit** — `feat(preferences): structured preference rule model`

---

### Task 2: First-use gate

**Files:**
- Create: `backend/app/services/preferences.py`
- Test: `tests/test_preference_service.py`

- [ ] **Step 1: Write the failing tests** — invariant 6 becomes code:

```python
def test_review_after_first_use_creates_rule(db, yogurt_item_used_once):
    result = record_review(db, item=yogurt_item_used_once, text="too sour", after_first_use=True)
    assert result.kind == "preference_rule"
    assert db.query(PreferenceRule).count() == 1


def test_review_before_first_use_is_only_a_hint(db, yogurt_item_never_used):
    result = record_review(db, item=yogurt_item_never_used, text="heard it's sour", after_first_use=False)
    assert result.kind == "preference_hint"
    assert db.query(PreferenceRule).filter_by(created_from="user_review_after_first_use").count() == 0


def test_hint_upgrades_only_after_actual_first_use(db, yogurt_item_never_used):
    record_review(db, item=yogurt_item_never_used, text="heard it's sour", after_first_use=False)
    mark_first_use(db, yogurt_item_never_used)          # consumption event from Phase 8
    result = record_review(db, item=yogurt_item_never_used, text="confirmed, too sour", after_first_use=True)
    assert result.kind == "preference_rule"
```

- [ ] **Step 2: Run to verify they fail** — FAIL (ImportError).

- [ ] **Step 3: Implement** — `record_review()` checks first-use status from consumption history (Phase 8's `ConsumptionEvent`), not from the caller's claim alone: `after_first_use=True` with zero consumption events for the item downgrades to a hint with a `needs_verification` note. Hints are stored on a `preference_hint` table (or `kind` column) with no `strength`.

- [ ] **Step 4: Run to verify they pass.**

- [ ] **Step 5: Commit** — `feat(preferences): first-use gate downgrading early reviews to hints`

---

### Task 3: Preference Review Agent — correct-scope generalization

**Files:**
- Create: `backend/app/agents/preference_review.py`
- Test: `tests/test_overgeneralization.py`

- [ ] **Step 1: Write the failing tests** — Guardrail 12 as assertions:

```python
def test_brand_dislike_stays_brand_scoped(db):
    rule = PreferenceReviewAgent().run(review_ctx(
        text="This yogurt was too sour. Don't recommend this brand again.",
        item=fage_greek_yogurt))
    assert rule.target_scope == "brand" and rule.target_value == "Fage"
    assert rule.applies_to["canonical_item"] == "Greek yogurt"


def test_brand_dislike_never_becomes_category_dislike(db):
    rule = PreferenceReviewAgent().run(review_ctx(
        text="too sour, avoid this brand", item=fage_greek_yogurt))
    assert rule.target_scope != "category"


def test_explicit_category_dislike_is_allowed(db):
    rule = PreferenceReviewAgent().run(review_ctx(
        text="I just don't like plain yogurt at all, any brand", item=fage_greek_yogurt))
    assert rule.target_scope == "category"
```

- [ ] **Step 2: Run to verify they fail** — FAIL (ImportError).

- [ ] **Step 3: Implement** — the agent maps review text + item record to a rule **proposal**; scope widens beyond the reviewed product/brand only when the text explicitly generalizes ("any brand", "all yogurt"). Default scope: the narrowest entity the review names. The proposal is committed by `services/preferences.py`, not the agent (invariant 5 pattern).

- [ ] **Step 4: Run to verify they pass.**

- [ ] **Step 5: Commit** — `feat(preferences): review agent with scope-preserving generalization`

---

### Task 4: Reviews endpoint

**Files:**
- Create: `backend/app/routes/reviews.py`, `backend/app/schemas/preferences.py`
- Test: `tests/test_review_api.py`

- [ ] **Step 1: Write the failing tests** — `POST /reviews` per `api-spec.md`: with `after_first_use: true` and consumption history → 201, rule persisted at brand scope; with `after_first_use: false` → 201 but `kind: preference_hint` in the response; item lifecycle moves `review_eligible → reviewed`; 404 on unknown `pantry_item_id`.

- [ ] **Step 2: Run to verify they fail** — FAIL (404, route missing).

- [ ] **Step 3: Implement** — route validates, delegates to `record_review()`, serializes the created rule or hint.

- [ ] **Step 4: Run to verify they pass** — `uv run pytest tests/test_review_api.py -v`.

- [ ] **Step 5: Commit** — `feat(preferences): reviews endpoint with first-use gating`

---

### Task 5: Rule application (avoid / prefer / suggest_alternative)

**Files:**
- Create: `backend/app/pantry/preferences.py`
- Test: `tests/test_preference_application.py`

- [ ] **Step 1: Write the failing tests** — one per `future_action`:

```python
def test_avoid_filters_candidate(active_avoid_fage_rule):
    verdict = apply_rules(candidate=item("Greek yogurt", brand="Fage"), rules=[active_avoid_fage_rule])
    assert verdict.action == "exclude" and verdict.rule_id == active_avoid_fage_rule.preference_id


def test_avoid_does_not_hit_other_brands(active_avoid_fage_rule):
    verdict = apply_rules(candidate=item("Greek yogurt", brand="Chobani"), rules=[active_avoid_fage_rule])
    assert verdict.action == "allow"


def test_suggest_alternative_annotates(suggest_alt_rule):
    verdict = apply_rules(candidate=item("Greek yogurt", brand="Fage"), rules=[suggest_alt_rule])
    assert verdict.action == "annotate" and "alternative" in verdict.note


def test_inactive_rule_is_ignored(inactive_rule):
    assert apply_rules(candidate=item("Greek yogurt", brand="Fage"), rules=[inactive_rule]).action == "allow"
```

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — pure resolution function: matches candidate against `target_scope`/`target_value`/`applies_to`; `avoid` (strong) → exclude, `avoid` (weak/medium) → annotate, `prefer` → boost rank, `suggest_alternative` → annotate with alternatives, `ask_before_buying` → flag for confirmation. Deterministic, no LLM, no session.

- [ ] **Step 4: Run to verify they pass.**

- [ ] **Step 5: Commit** — `feat(preferences): deterministic rule application`

---

### Task 6: Shopping Planner integration (the demo step 9 behavior)

**Files:**
- Modify: `backend/app/agents/shopping_planner.py`, `backend/app/services/shopping.py`
- Test: `tests/test_preference_application.py` (append)

- [ ] **Step 1: Write the failing test** — Manifest §27 step 9 end to end:

```python
def test_next_list_avoids_disliked_brand_and_suggests_alternative(client, db, fage_avoid_rule):
    r = client.post("/shopping-lists", json={"goal": "weekly groceries"})
    items = r.json()["items"]
    yogurt = next(i for i in items if i["canonical_name"] == "Greek yogurt")
    assert "Fage" not in (yogurt.get("brand_note") or "")
    assert yogurt["reason"]  # reason mentions the avoided brand / alternative suggestion
```

- [ ] **Step 2: Run to verify it fails** — planner ignores rules today.

- [ ] **Step 3: Implement** — planner context builder loads active rules; `apply_rules()` runs per candidate; strong-negative exclusions are a hard filter (the Phase 3 forbidden-action test `never ignore strong negative preference rules` now has real teeth — re-run it).

- [ ] **Step 4: Run to verify it passes** — plus Phase 3's planner suite stays green.

- [ ] **Step 5: Commit** — `feat(shopping): planner consumes preference rules`

---

### Task 7: Auditor extension — overgeneralization check

**Files:**
- Modify: `backend/app/agents/auditor.py`
- Test: `tests/test_overgeneralization.py` (append)

- [ ] **Step 1: Write the failing test** — a rule proposal whose `target_scope` is wider than the review text supports (category rule from brand-only text) is flagged by the auditor; the correctly-scoped rule passes.

- [ ] **Step 2: Run to verify it fails.**

- [ ] **Step 3: Implement** — auditor compares proposal scope against the review evidence packet; wider-than-evidence → `needs_review`, rule stored inactive until the user confirms.

- [ ] **Step 4: Run to verify it passes.**

- [ ] **Step 5: Commit** — `feat(auditor): preference overgeneralization check`

---

## Done criteria for Phase 9

- Reviews after verified first use produce correctly-scoped, structured rules; pre-first-use input provably stays a hint (invariant 6 test green).
- Brand dislike never widens to category without explicit user text; auditor catches wider-than-evidence proposals.
- All five `future_action` behaviors tested; inactive rules ignored.
- The Phase 3 planner now demonstrably avoids a strongly-disliked brand and annotates alternatives (demo step 9).
- Phases 2–8 suites still green.

## Next phase

[Phase 10 — Evaluation and Demo](phase-10-evaluation-and-demo.md): seeded demo user, sample data, §22 metric suites, and the nine-step end-to-end demo test.
