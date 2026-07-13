# PantryOps Edge Phase 6: Vision/OCR Enrichment Implementation Plan

> **For agentic workers:** Implement task-by-task with strict TDD: write the failing test, watch it fail, implement, watch it pass, commit. Steps use checkbox (`- [ ]`) syntax. REQUIRED ECC SKILLS before starting: `/ecc:pytorch-patterns` (detector/segmenter model integration), `/ecc:eval-harness` (detection/OCR/count metrics on samples), `/ecc:python-testing` (fixture-based vision tests, no live downloads in unit tests), `/ecc:python-review` (keep `vision/` interfaces clean behind the pipeline).

**Goal:** Replace the Phase-5 stub step bodies with real object detection, segmentation/cropping, OCR extraction, and optional barcode reading — every result persisted as its §14 evidence record and reaching the ledger as editable estimates with correct source precedence.

**Architecture:** Per `documents/specs/architecture.md` §9 (precedence: barcode > label_ocr > product_detection > segmentation) and `documents/specs/agents.md` #7–#10, #18. Real models live behind the `vision/` interfaces so **the Phase-5 pipeline shape is unchanged** — only step bodies change. Detection yields category/count only, never brand (§15.7). OCR fields are candidates with confidence, never silently corrected (§15.9). The Barcode Agent returns nothing rather than inventing a value (§15.10). The Source Attribution Agent (§15.18) guarantees every field has value + source + confidence + status before it reaches `apply_update()`.

**Tech Stack:** Roboflow RF-DETR (rf-detr-nano, rf-detr-small if accuracy needs it) for grocery detection, SAM3 segmentation, PaddleOCR-VL v1.6 (`PaddleOCRVL(pipeline_version="v1.6")`), pyzbar for barcodes, Pillow/OpenCV preprocessing. Unit tests run on **recorded fixtures** in `tests/fixtures/vision/` — model-inference tests are marked `-m integration` and excluded from the default run.

**Out of scope for Phase 6** (later plans): external product/nutrition APIs (Phase 7), recipe/consumption (Phase 8), receipt-specific parsing beyond raw OCR (post-MVP; CORD experiments live in `evaluation/` only).

**Prerequisites:** Phase 5 complete (pipeline runs stubs end to end); `data/samples/` seeded with a handful of grocery photos, label crops, and one barcode image; model weights downloadable once via `scripts/fetch_models.py` (never inside tests).

---

## File structure (locked in by this plan)

```text
backend/app/
├── vision/
│   ├── preprocessing.py            # resize/normalize/crop helpers
│   ├── detector.py                 # RF-DETR wrapper → labels, bboxes, counts
│   ├── segmenter.py                # SAM3 masks + crops → storage/
│   ├── ocr.py                      # PaddleOCR-VL v1.6 wrapper → raw text + structured candidates
│   └── barcode.py                  # pyzbar wrapper → value or None
├── models/
│   ├── vision_detection.py         # §14.5
│   ├── segmentation_result.py      # §14.6
│   └── ocr_result.py               # §14.7
├── schemas/vision.py               # AnalyzeRequest/Result, DetectionOut, OcrFieldsOut
├── agents/
│   ├── edge_vision.py              # §15.7 — category/count, never brand
│   ├── segmentation.py             # §15.8 — regions only
│   ├── ocr_label.py                # §15.9 — estimates only
│   ├── barcode.py                  # §15.10 — no invented barcodes
│   └── source_attribution.py       # §15.18 — provenance guarantee
├── routes/vision.py                # POST /vision/analyze
└── evaluation/
    ├── metrics.py                  # §22 vision metrics
    ├── test_vision.py              # detection precision/recall, count error (integration)
    └── test_ocr.py                 # OCR field accuracy (integration)

backend/alembic/versions/<vision_models>.py
tests/
├── fixtures/vision/                # recorded model outputs + sample crops
├── test_detector.py
├── test_segmenter.py
├── test_ocr.py
├── test_barcode.py
├── test_source_attribution.py
└── test_vision_api.py
scripts/fetch_models.py
```

Rule for the whole phase: `vision/` modules take an image (bytes/array) and return typed results — they never touch the DB or the ledger. Persistence happens in the pipeline steps; ledger writes happen only via Source Attribution → `apply_update()`.

---

### Task 1: Preprocessing helpers + fixtures

**Files:**
- Create: `backend/app/vision/preprocessing.py`, `tests/fixtures/vision/` (sample images), `scripts/fetch_models.py`
- Test: `tests/test_detector.py` (start with preprocessing cases)

- [ ] **Step 1: Write the failing tests** — `resize_max_side(img, 1280)` preserves aspect ratio; `crop_bbox(img, [120, 80, 210, 190])` returns the exact region; normalize handles RGBA and grayscale inputs without raising.

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/test_detector.py -v` → FAIL (ImportError).

- [ ] **Step 3: Implement `preprocessing.py`** (Pillow-based, no model deps) and commit 3–5 small sample images + expected-output JSON into `tests/fixtures/vision/`. Write `scripts/fetch_models.py` (downloads RF-DETR/SAM3/PaddleOCR-VL weights to `data/models/`, idempotent).

- [ ] **Step 4: Verify pass. Commit** — `feat(vision): preprocessing helpers and recorded test fixtures`

---

### Task 2: Detector + VisionDetection model + Edge Vision Agent

**Files:**
- Create: `backend/app/vision/detector.py`, `backend/app/models/vision_detection.py`, `backend/app/agents/edge_vision.py`, migration
- Test: `tests/test_detector.py` (extend)

- [ ] **Step 1: Write the failing tests** — unit (fixture-driven, detector injected as a fake returning recorded outputs): `detect(img)` returns `[Detection(label, bbox, confidence)]`; count estimate for 4 recorded tomato boxes is 4; **the Detection type has no brand field** (assert on the schema — §15.7 forbidden). Integration (`@pytest.mark.integration`): real RF-DETR on a sample grocery photo returns ≥1 detection with confidence ∈ (0,1].

- [ ] **Step 2: Run to verify they fail** — default run FAIL on unit tests; integration excluded (`addopts` gains `-m "not integration"`).

- [ ] **Step 3: Implement** — `detector.py::Detector` protocol + `RfDetrDetector` impl (lazy weight load from `data/models/`); `models/vision_detection.py` per §14.5 (label, bbox JSONB, confidence, model_name); `agents/edge_vision.py` wraps detect → typed proposal with count estimates, no ledger access. Migration for the three vision tables lands here (hand-review JSONB defaults).

- [ ] **Step 4: Verify pass** — `uv run pytest tests/test_detector.py -v` then once: `uv run pytest -m integration tests/test_detector.py -v`.

- [ ] **Step 5: Commit** — `feat(vision): grocery detector with category/count-only agent`

---

### Task 3: Segmenter + crops to storage

**Files:**
- Create: `backend/app/vision/segmenter.py`, `backend/app/models/segmentation_result.py`, `backend/app/agents/segmentation.py`
- Test: `tests/test_segmenter.py`

- [ ] **Step 1: Write the failing tests** — given an image + bbox, `segment()` returns a mask and a crop; the pipeline-facing helper persists mask + crop via the `storage/` abstraction and returns `mask_uri`/`crop_uri` (§14.6); the agent emits region metadata only — assert its output schema has no classification/label field (§15.8 forbidden).

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — `Segmenter` protocol + SAM3 impl (integration-only), plus a bbox-crop fallback used when no GPU (config flag `PANTRYOPS_VISION_SEGMENTER=sam3|bbox`). Fake segmenter for unit tests.

- [ ] **Step 4: Verify pass. Commit** — `feat(vision): segmentation with crops persisted to object storage`

---

### Task 4: OCR + structured candidates

**Files:**
- Create: `backend/app/vision/ocr.py`, `backend/app/models/ocr_result.py`, `backend/app/agents/ocr_label.py`
- Test: `tests/test_ocr.py`

- [ ] **Step 1: Write the failing tests** — fixture crop of `"CHOBANI GREEK YOGURT 32 OZ"` → `raw_text` preserved verbatim and `structured_fields == {"brand": "Chobani", "product_name": "Greek Yogurt", "package_size": "32 oz"}` with per-field confidence; a low-confidence garbled fixture yields candidates with `confidence < 0.5` and **unchanged raw text** (no silent correction — §15.9); every candidate carries `status="estimated"`, never `user_confirmed`.

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — `ocr.py::Ocr` protocol + `PaddleOcrVl` impl (PaddleOCR-VL v1.6 `predict()` pipeline, integration) + fixture-replay fake; rule-based field structurer (brand = first line match against known-brand list, size = regex `\d+\s?(oz|g|ml|lb|l)\b`, remainder → product_name candidate). `models/ocr_result.py` per §14.7. Agent returns candidates as SourcedFields with `source="label_ocr"`.

- [ ] **Step 4: Verify pass. Commit** — `feat(vision): ocr with structured estimate candidates, raw text preserved`

---

### Task 5: Barcode — nothing over guessing

**Files:**
- Create: `backend/app/vision/barcode.py`, `backend/app/agents/barcode.py`
- Test: `tests/test_barcode.py`

- [ ] **Step 1: Write the failing tests** — fixture with a clean EAN-13 → exact value decoded; **blurred/unreadable fixture → `None`, never a fabricated value** (assert result is None, §15.10 forbidden); invalid checksum → `None`.

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — pyzbar wrapper with checksum validation; agent emits `{barcode, confidence}` or nothing.

- [ ] **Step 4: Verify pass. Commit** — `feat(vision): barcode reader that returns nothing rather than inventing`

---

### Task 6: Source Attribution Agent

**Files:**
- Create: `backend/app/agents/source_attribution.py`
- Test: `tests/test_source_attribution.py`

- [ ] **Step 1: Write the failing tests** — given candidates for the same field from OCR (`brand=Chobani, 0.84`) and detection-derived category, the merged output keeps **both provenances** (winner applied, loser retained as candidate history); any candidate missing source/confidence/status is rejected with a clear error (invariant 2); merging never drops a provenance (§15.18 forbidden: "must not merge values without retaining provenance").

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — pure function over SourcedField lists using the precedence table from `architecture.md` §9; output is the ordered proposal batch for `apply_update()`.

- [ ] **Step 4: Verify pass. Commit** — `feat(agents): source attribution with provenance-preserving merge`

---

### Task 7: Wire real steps into the Phase-5 pipeline

**Files:**
- Modify: `backend/app/workers/steps.py`, `backend/app/agents/background_enrichment.py`
- Test: `tests/test_pipeline_stubs.py` (extend), `tests/test_vision_api.py` (start)

- [ ] **Step 1: Write the failing tests** — a check-in over fixture images (fake models injected) produces: VisionDetection + SegmentationResult + OCRResult rows linked to the job's images; estimated pantry fields applied via `apply_update()` where **barcode beats OCR beats detection** for the same field (assert the winning source per §15.12); a field whose stored status is `user_confirmed` stays untouched with the candidate filed `conflicting`; low-confidence fields set `needs_user_review=True` and the job status becomes `needs_review`.

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — replace stub bodies inside the `@job_step` decorators with calls into `vision/` + persistence; `background_enrichment.py` now feeds real candidates through Source Attribution → ledger. Pipeline signature, ordering, and status bookkeeping unchanged from Phase 5.

- [ ] **Step 4: Verify pass** — full suite: `uv run pytest -v`.

- [ ] **Step 5: Commit** — `feat(workers): real vision pipeline behind unchanged step interfaces`

---

### Task 8: POST /vision/analyze

**Files:**
- Create: `backend/app/schemas/vision.py`, `backend/app/routes/vision.py`
- Modify: `backend/app/main.py`
- Test: `tests/test_vision_api.py` (extend)

- [ ] **Step 1: Write the failing tests** — each `image_type` (`product_label | receipt | pantry | grocery_check_in`) routes to the right vision path and returns estimates with confidence; the response contains **no ledger mutation** (assert pantry rows unchanged after the call — per `api-spec.md`, this endpoint never writes); unknown image_type → 422.

- [ ] **Step 2: Run to verify they fail** — FAIL (404).

- [ ] **Step 3: Implement** — thin route: load image via storage, dispatch by type, serialize typed results.

- [ ] **Step 4: Verify pass. Commit** — `feat(vision): on-demand analyze endpoint, read-only`

---

### Task 9: Evaluation metrics on samples

**Files:**
- Create: `backend/app/evaluation/metrics.py`, `backend/app/evaluation/test_vision.py`, `backend/app/evaluation/test_ocr.py`, `data/samples/manifest.json`
- Test: (these ARE the tests — all `@pytest.mark.integration`)

- [ ] **Step 1: Write `data/samples/manifest.json`** — per sample image: expected labels, counts, OCR fields, barcode values (synthetic ground truth, hand-verified).

- [ ] **Step 2: Implement `metrics.py`** — detection precision/recall, classification accuracy, count-estimate error, OCR field-extraction accuracy, barcode match rate (§22 vision metrics), each returning a float + per-sample breakdown.

- [ ] **Step 3: Write the metric suites** — `test_vision.py` / `test_ocr.py` run real models over `data/samples/`, print the metric table, and assert floor thresholds (start permissive: detection recall ≥ 0.5, OCR brand accuracy ≥ 0.6 — tighten in Phase 10).

- [ ] **Step 4: Run once** — `uv run pytest -m integration backend/app/evaluation -v` → PASS with printed metrics.

- [ ] **Step 5: Commit** — `feat(evaluation): vision and ocr metric suites over sample manifest`

---

## Done criteria for Phase 6

- Default `uv run pytest` green with zero model downloads or live inference (fixtures only); `-m integration` suite green locally with real models.
- A fixture check-in produces detection/segmentation/OCR rows and ledger estimates with barcode > OCR > detection precedence; user-confirmed fields provably untouched.
- Detector output structurally cannot carry a brand; barcode returns None over guessing; OCR raw text is never silently corrected.
- §22 vision metrics computed over `data/samples/` with floor thresholds asserted.

## Next phase

[Phase 7 — Product/Nutrition Enrichment](phase-7-product-nutrition-enrichment.md): Open Food Facts and USDA fill in what vision estimated — source-attributed, validated, and never guessed.
