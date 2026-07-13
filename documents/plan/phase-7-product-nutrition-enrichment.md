# PantryOps Edge Phase 7: Product/Nutrition Enrichment Implementation Plan

> **For agentic workers:** Implement task-by-task with strict TDD: write the failing test, watch it fail, implement, watch it pass, commit. Steps use checkbox (`- [ ]`) syntax. REQUIRED ECC SKILLS before starting: `/ecc:security-reviewer` (external API responses are untrusted input — validate/sanitize before use), `/ecc:error-handling` (timeouts/retries/no-match paths), `/ecc:python-testing` (recorded-fixture API clients, no live calls in unit tests), `/ecc:api-design` (normalization contract to SourcedFields).

**Goal:** Enrich estimated pantry items with Open Food Facts and USDA FoodData Central — brand, product name, package size, dietary info, nutrition — every field source-attributed and confidence-labeled, never inventing a match and never making a health claim.

**Architecture:** Per `documents/specs/architecture.md` §9 (api_enrichment sits below all vision sources in precedence) and `documents/specs/data-models.md` §4.9. **All fetched external data is untrusted**: responses are schema-validated and sanitized before any field leaves the client module. A match requires a reliable key — barcode first, confident OCR name second — otherwise the service returns "no match", never a guess (§15.11 forbidden actions; Manifest §24 guardrails 1, 3, 9, 13). Enrichment writes estimates through `apply_update()` and structurally cannot overwrite user-confirmed or higher-precedence fields (invariant 3).

**Tech Stack:** httpx (timeouts + bounded retries), Pydantic v2 response schemas, recorded JSON fixtures in `tests/fixtures/products/` (captured once via a `scripts/record_product_fixtures.py` helper), respx for transport mocking. Open Food Facts API (§18.1), USDA FoodData Central API (§18.2, key via `PANTRYOPS_USDA_API_KEY`).

**Out of scope for Phase 7** (later plans): recipes/consumption (Phase 8), reviews/preferences (Phase 9), receipt-price enrichment (Store/Cost agent — post-MVP polish), live store prices (out of MVP entirely, Manifest §4).

**Prerequisites:** Phase 6 complete: check-in pipeline produces OCR/barcode candidates; `apply_update()` precedence matrix green; Auditor v1 from Phase 4 in place.

---

## File structure (locked in by this plan)

```text
backend/app/
├── products/
│   ├── open_food_facts.py          # OFF client: barcode + name lookup, validated
│   ├── usda.py                     # USDA client: generic nutrition/category, validated
│   └── normalization.py            # external payloads → SourcedFields
├── models/product_enrichment.py    # §14.8 per-field sourced enrichment record
├── schemas/enrichment.py           # OffProduct, UsdaFood, EnrichmentResult
├── services/enrichment.py          # barcode-first orchestration, "no match" over guess
└── agents/product_enrichment.py    # §15.11 — sourced fields only, no health claims

backend/alembic/versions/<enrichment_record>.py
scripts/record_product_fixtures.py
tests/
├── fixtures/products/              # recorded OFF/USDA JSON responses
├── test_open_food_facts.py
├── test_usda.py
├── test_normalization.py
├── test_enrichment_service.py
└── test_enrichment_agent.py
```

Rule for the whole phase: `products/` clients return validated typed objects or raise a typed error — raw JSON never crosses the module boundary. Ledger writes happen only via the agent → Source Attribution → `apply_update()` path.

---

### Task 1: Open Food Facts client

**Files:**
- Create: `backend/app/products/__init__.py`, `backend/app/products/open_food_facts.py`, `backend/app/schemas/enrichment.py`, `tests/fixtures/products/off_*.json`, `scripts/record_product_fixtures.py`
- Test: `tests/test_open_food_facts.py`

- [ ] **Step 1: Write the failing tests** — with respx-mocked transport replaying fixtures:

```python
def test_barcode_lookup_returns_validated_product(off_client, respx_mock):
    respx_mock.get(url__regex=r".*/product/0894700010137.*").respond(
        json=load_fixture("off_yogurt.json"))
    p = off_client.by_barcode("0894700010137")
    assert p.brand == "Chobani"
    assert p.product_name == "Greek Yogurt"
    assert p.source == "open_food_facts"


def test_malformed_response_rejected_not_passed_through(off_client, respx_mock):
    respx_mock.get(url__regex=r".*/product/.*").respond(json={"status": 1, "product": {"brands": ["<script>x</script>"]}})
    with pytest.raises(ExternalDataError):
        off_client.by_barcode("0000000000000")


def test_timeout_raises_typed_error(off_client, respx_mock):
    respx_mock.get(url__regex=r".*").mock(side_effect=httpx.TimeoutException("slow"))
    with pytest.raises(ProductSourceUnavailable):
        off_client.by_barcode("0894700010137")
```

Also: unknown barcode (OFF `status: 0`) → returns `None` (not an error, not a guess); oversized response (> 1 MB) rejected.

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/test_open_food_facts.py -v` → FAIL (ImportError).

- [ ] **Step 3: Implement** — `OpenFoodFactsClient` on httpx: 5 s timeout, 2 bounded retries on 5xx only, response parsed into a strict Pydantic `OffProduct` schema (`extra="ignore"`, string fields length-capped and control-character-stripped — untrusted input). Record real fixtures once with `scripts/record_product_fixtures.py`.

- [ ] **Step 4: Run to verify they pass.**

- [ ] **Step 5: Commit** — `feat(products): open food facts client with validated, sanitized responses`

---

### Task 2: USDA FoodData Central client

**Files:**
- Create: `backend/app/products/usda.py`, `tests/fixtures/products/usda_*.json`
- Test: `tests/test_usda.py`

- [ ] **Step 1: Write the failing tests** — same posture as Task 1: generic-food search ("greek yogurt") returns a validated `UsdaFood` with nutrition fields and `source="usda"`; missing API key → typed config error at client construction, not at call time; empty search results → `None`; malformed nutrient payloads rejected.

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — `UsdaClient` mirroring the OFF client's timeout/retry/validation posture; nutrition mapped to a fixed nutrient subset (protein, carbs, fat, kcal per 100 g) — nothing else crosses the boundary.

- [ ] **Step 4: Verify pass. Commit** — `feat(products): usda client for generic-food nutrition`

---

### Task 3: Normalization to SourcedFields

**Files:**
- Create: `backend/app/products/normalization.py`
- Test: `tests/test_normalization.py`

- [ ] **Step 1: Write the failing tests** — an `OffProduct` maps to SourcedFields where every field carries `source="api_enrichment"`, a confidence derived from match quality (barcode match → 0.9 base; name match → scaled by search score), and `status="estimated"`; package sizes normalize (`"32 OZ"` → `"32 oz"`, `"946ml"` → `"946 ml"`); a field absent from the payload yields **no SourcedField at all** (never a null-value estimate); nutrition fields carry `nutrition_source="open_food_facts_or_usda"` per §14.8.

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — pure functions, no I/O; unit/label normalization table shared with `pantry/quantity.py`.

- [ ] **Step 4: Verify pass. Commit** — `feat(products): normalization of external payloads to sourced estimates`

---

### Task 4: Enrichment service — barcode first, "no match" over guessing

**Files:**
- Create: `backend/app/services/enrichment.py`
- Test: `tests/test_enrichment_service.py`

- [ ] **Step 1: Write the failing tests** —

```python
def test_barcode_match_preferred_over_ocr_name(service, fixtures):
    result = service.enrich(barcode="0894700010137", ocr_name="greek yogurt")
    assert result.matched_by == "barcode"


def test_low_confidence_ocr_name_returns_no_match(service):
    # OCR name candidate below the confidence floor (0.7) must not be used as a key
    result = service.enrich(barcode=None, ocr_name="grk ygrt", ocr_confidence=0.4)
    assert result.status == "no_match"      # §15.11: never invent a match


def test_source_unavailable_degrades_to_no_match_with_retry_flag(service, respx_mock):
    ...
    assert result.status == "source_unavailable"
    assert result.retriable is True
```

Also: barcode miss + confident OCR name → USDA/OFF name search fallback; both miss → `no_match`.

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — `enrich(barcode, ocr_name, ocr_confidence)`: barcode → OFF; else OCR name (confidence ≥ 0.7) → OFF search then USDA; else `no_match`. Every branch returns a typed `EnrichmentResult`; nothing fabricated on the unavailable path — the pipeline step marks the job step `failed`-retriable instead.

- [ ] **Step 4: Verify pass. Commit** — `feat(enrichment): barcode-first matching that returns no-match over guesses`

---

### Task 5: ProductEnrichmentRecord model

**Files:**
- Create: `backend/app/models/product_enrichment.py`, migration
- Test: append to `tests/test_enrichment_service.py`

- [ ] **Step 1: Write the failing test** — round-trip a record per `data-models.md` §4.9: per-field JSONB SourcedFields (brand, product_name), `barcode` nullable, `nutrition_source`, `dietary_info_source`, linked `pantry_item_id`; migration parity test still green.

- [ ] **Step 2: Verify fail → implement** — model + hand-reviewed migration.

- [ ] **Step 3: Verify pass. Commit** — `feat(enrichment): per-field sourced enrichment record`

---

### Task 6: Product Enrichment Agent — sourced fields only, no health claims

**Files:**
- Create: `backend/app/agents/product_enrichment.py` (replaces the Phase-5/6 stub body)
- Test: `tests/test_enrichment_agent.py`

- [ ] **Step 1: Write the failing tests** — every field in the agent's proposal carries source + confidence + status (reject-on-missing is invariant 2, but assert here at the agent boundary too); dietary info is passed through verbatim from the source (`"vegetarian"` label from OFF) and the proposal text **never contains safety/health phrasing** (assert against a denylist: "safe to eat", "healthy", "good for", "will help" — guardrails 1/3); a `no_match` result produces zero proposals, not empty-value fields.

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — agent orchestrates service → normalization → ProductEnrichmentRecord persist → SourcedField proposal batch for Source Attribution. Returns typed proposals only.

- [ ] **Step 4: Verify pass. Commit** — `feat(agents): product enrichment agent, sourced fields only`

---

### Task 7: Ledger integration through the hierarchy

**Files:**
- Modify: `backend/app/workers/steps.py` (enrichment step body), `backend/app/agents/background_enrichment.py`
- Test: append to `tests/test_enrichment_agent.py`

- [ ] **Step 1: Write the failing tests** — after a fixture check-in: `brand` set by label OCR (0.84) is **not** replaced by an api_enrichment candidate (lower precedence per `architecture.md` §9) — the candidate lands as history; a `user_confirmed` brand stays untouched with the api candidate filed `conflicting` (invariant 3); an empty item (`brand.status="unknown"`) **is** filled by api_enrichment; every applied change produced exactly one `ledger_change_log` row with `source="api_enrichment"`.

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — wire the real enrichment into the pipeline's `product_enrichment_step`; all writes via Source Attribution → `apply_update()`. Step interface unchanged from Phase 5.

- [ ] **Step 4: Verify pass** — full suite: `uv run pytest -v`.

- [ ] **Step 5: Commit** — `feat(enrichment): pipeline enrichment writing through the evidence hierarchy`

---

### Task 8: Auditor extension — unsourced fields and price claims

**Files:**
- Modify: `backend/app/agents/auditor.py`
- Test: append to `tests/test_auditor.py` (from Phase 4)

- [ ] **Step 1: Write the failing tests** — a proposal batch containing a field without a source is blocked with a violation naming the field (guardrail 9); an assist/enrichment output containing a live-price or availability claim ("costs $4.99 at Walmart", "in stock at") without a verified source is blocked (guardrail 13); a clean enrichment batch passes untouched.

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — two new auditor checks appended to the Phase-4 checklist; auditor remains the last gate before commit/response.

- [ ] **Step 4: Verify pass. Commit** — `feat(auditor): unsourced-field and price-claim checks`

---

## Done criteria for Phase 7

- OFF and USDA clients validated/sanitized end to end; unit suite green with zero live network calls (respx + fixtures only).
- Matching is barcode-first, OCR-name (≥ 0.7) fallback, and provably returns `no_match` rather than guessing; source outages degrade to retriable step failures, never fabricated data.
- Enriched fields reach the ledger as `api_enrichment` estimates that fill unknowns but never displace OCR/barcode/user values; every write logged.
- No health/safety claims and no unverified price claims can pass the auditor (both covered by tests).

## Next phase

[Phase 8 — Recipe and Consumption](phase-8-recipe-and-consumption.md): recommend from the ledger, deduct only on confirm-cooked, and trigger low-stock reorder flags.
