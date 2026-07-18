# PantryOps Edge Phase 6: Vision/OCR Enrichment Implementation Plan

> **For agentic workers:** Implement task-by-task with strict TDD: write the failing test, watch it fail, implement, watch it pass, review, then commit. Steps use checkbox (`- [ ]`) syntax. Use the available ECC `tdd-workflow`, `mle-workflow`, `eval-harness`, `security-review`, `coding-standards`, and `verification-loop` skills. Unit work must remain independent of heavyweight model runtimes.

**Goal:** Replace the Phase-5 stub step bodies with real object detection, segmentation/cropping, OCR extraction, and optional barcode reading. Every result is persisted as immutable evidence. Only evidence with an unambiguous checklist-purchase target may become a ledger proposal; unmatched evidence remains reviewable and never mutates pantry truth.

**Architecture:** Per `documents/specs/architecture.md` §9 and `documents/specs/agents.md` #7–#10, #18. The pipeline is corrected to **detection → segmentation → OCR → barcode → enrichment → audit**, because segmentation consumes persisted detection boxes. Real models live behind lazy `vision/` interfaces. Detection yields category/count only, never brand (§15.7). OCR fields are candidates with per-field confidence and unchanged raw text (§15.9). The Barcode Agent persists exact decoded evidence or nothing (§15.10); barcode-derived product fields remain Phase 7. Source Attribution validates and orders candidates, while `services/ledger.py::apply_update()` remains the only precedence/conflict authority.

**Tech Stack:** Pillow for the base preprocessing contract. Optional, isolated profiles provide RF-DETR, SAM3, PaddleOCR-VL v1.6, and a barcode decoder. RF-DETR begins as a documented COCO-grocery-subset baseline unless a versioned grocery checkpoint is supplied. SAM3 is GPU/gated-checkpoint integration only; deterministic bbox crops are the default fallback. PaddleOCR-VL must use explicit local model directories or a dedicated service and may not auto-download. Barcode support requires an explicit Python 3.12/native-runtime smoke test. Unit tests run on committed synthetic/redistributable fixtures; opt-in CPU/GPU integration profiles are excluded from the default run.

**Out of scope for Phase 6** (later plans): external product/nutrition APIs (Phase 7), recipe/consumption (Phase 8), receipt-specific parsing beyond raw OCR (post-MVP; CORD experiments live in `evaluation/` only).

**Prerequisites:** Phase 5 complete (pipeline runs stubs end to end). Synthetic unit fixtures are created in Task 1. Human-authored evaluation samples and labels are created in Task 9. Model assets are acquired only by an explicit, selectable, checksum-validating command after versions, licenses, and checkpoint digests are recorded; gated assets require user-provided authentication.

---

## File structure (locked in by this plan)

```text
backend/app/
├── vision/
│   ├── preprocessing.py            # resize/normalize/crop helpers
│   ├── contracts.py                # immutable typed result DTOs
│   ├── errors.py                   # typed runtime/asset errors
│   ├── detector.py                 # RF-DETR wrapper → labels, bboxes, counts
│   ├── segmenter.py                # SAM3 masks + crops → storage/
│   ├── ocr.py                      # PaddleOCR-VL v1.6 wrapper → raw text + structured candidates
│   └── barcode.py                  # pyzbar wrapper → value or None
├── models/
│   ├── vision_detection.py         # §14.5
│   ├── segmentation_result.py      # §14.6
│   ├── ocr_result.py               # §14.7
│   ├── barcode_result.py           # durable barcode evidence for Phase 7
│   ├── vision_candidate_review.py  # unmatched/ambiguous provenance
│   └── vision_candidate_outcome.py # immutable applied/conflict/reject decision
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
├── fixtures/vision/                # synthetic images + recorded model outputs
├── test_detector.py
├── test_segmenter.py
├── test_ocr.py
├── test_barcode.py
├── test_source_attribution.py
└── test_vision_api.py
scripts/generate_vision_fixtures.py
scripts/fetch_models.py               # explicit only after asset manifest is pinned
```

Rule for the whole phase: adapter entry points accept bounded bytes through the
central safe decoder; pure preprocessing helpers accept `PIL.Image.Image`; model
adapters return typed results. Vision modules never touch the DB or ledger.
Persistence happens in pipeline steps; ledger writes happen only via Source
Attribution → `apply_update()`.

Model inference must not hold a database connection or advisory lock. Workers use a
short claim/lease transaction, infer outside the transaction, re-check consent, and
persist idempotently. Every evidence row records job/image/region linkage, engine and
version, checkpoint digest when applicable, and an idempotency key. Derived masks and
crops inherit source-image ownership, consent, and retention.

---

### Task 0: Repair contracts before model or persistence work

**Files:**
- Modify: `Manifest.md`, `documents/specs/architecture.md`, `documents/specs/agents.md`,
  `documents/specs/data-models.md`, `documents/specs/api-spec.md`, this plan

- [x] **Step 1: Audit the Phase-5 pipeline and Phase-6 model contracts.**
- [x] **Step 2: Correct execution order** to detection → segmentation and document
  bbox fallback behavior.
- [x] **Step 3: Separate consent session from optional shopping-list context.**
  Ambiguous/unmatched evidence persists for review and never selects an arbitrary
  pantry item.
- [x] **Step 4: Add durable barcode and candidate-review contracts.** Barcode-derived
  product fields remain Phase 7; ledger precedence remains centralized.
- [x] **Step 5: Define derived-asset retention, idempotency, offline model assets,
  lazy runtime profiles, and the no-open-DB-connection-during-inference boundary.**

---

### Task 1: Vision foundation — preprocessing, offline contracts, and fixtures

**Files:**
- Create: `backend/app/vision/preprocessing.py`, `backend/app/vision/contracts.py`,
  `backend/app/vision/errors.py`, `tests/fixtures/vision/`,
  `scripts/generate_vision_fixtures.py`
- Modify: `pyproject.toml`, `.gitignore`
- Test: `tests/test_preprocessing.py`, `tests/test_vision_contracts.py`,
  `tests/test_vision_fixtures.py`

- [x] **Step 1: Write the failing preprocessing tests** — `resize_max_side(img, 1280)`
  preserves aspect ratio without upscaling or mutation; strict integer
  `[x_min, y_min, x_max, y_max]` crop returns the exact region and rejects invalid
  bounds; normalize returns a new RGB image, applies EXIF orientation, and composites
  RGBA/indexed transparency on white. The central decoder accepts only bounded,
  single-frame JPEG/PNG inputs and rejects unsafe dimensions, modes, formats,
  encoded size, and Pillow decompression-bomb signals.

- [x] **Step 2: Run to verify they fail** — ImportError for the absent vision module.

- [x] **Step 3: Implement the pure Pillow preprocessing helpers.**

- [x] **Step 4: Add immutable result DTOs and typed `ModelAssetsUnavailable`.**
  Detector/OCR estimates require non-null confidence; deterministic region evidence
  may use `confidence=None`. Geometry records dimensions, coordinate space, transform,
  preprocessing version, canonical input SHA-256, engine version, and checkpoint
  digest. Learned engines require the digest; fixtures do not. Imports perform no
  heavyweight initialization.
- [x] **Step 5: Register and default-exclude `integration`, `integration_cpu`, and
  `integration_gpu`.** The default test run requires no network, native barcode
  runtime, model package, weights, or GPU.
- [x] **Step 6: Create three deterministic synthetic PNG fixtures plus a manifest**
  containing provenance/license, SHA-256, decoded pixel SHA-256, dimensions, mode,
  coordinate convention, and expected outputs.
- [x] **Step 7: Verify with 100% branch coverage for the foundation modules.**
- [x] **Step 8: Review and commit** — `feat(vision): add offline vision foundation`

`scripts/fetch_models.py` is intentionally not bundled into this task. It becomes a
separate RED/GREEN checkpoint only after each asset has a pinned source revision,
license, expected checksum, and a defined authentication/error contract. It must be
manual, per-model selectable, atomic, idempotent, and never run on import or test
collection.

---

### Task 1A: Pinned asset manifest, acquisition, and dependency profiles

**Files:**
- Create: `documents/model-assets/phase-6.json`, `scripts/fetch_models.py`
- Modify: `pyproject.toml`
- Test: `tests/test_model_assets.py`

- [ ] **Step 1: Select exact redistributable artifacts** and record model/package
  version, immutable source revision/URL, license, expected bytes, SHA-256, runtime
  profile, hardware requirement, and gated-auth requirement. The committed manifest
  lives outside ignored `data/models/`.
- [ ] **Step 2: Write failing fetcher tests** for per-model selection, HTTPS host
  allowlisting, maximum download size, checksum verification before atomic rename,
  idempotent verified reuse, cleanup after interruption, archive/symlink traversal
  rejection, and a clear gated-model authentication failure. Credentials come only
  from environment/keychain and never enter the manifest, command line, or logs.
- [ ] **Step 3: Add isolated, pinned dependency groups** for detector CPU, SAM3 GPU,
  OCR, and barcode. Prove `uv` resolves each Python 3.12 profile independently; do not
  add heavyweight runtimes to the base backend environment.
- [ ] **Step 4: Implement the explicit fetcher.** It never runs on import, app
  startup, test collection, or adapter construction.
- [ ] **Step 5: Security review, verify, and commit** —
  `build(vision): pin offline model asset profiles`

This task must be green before any real-model integration in Tasks 3–5. Gated or
unredistributable assets may remain an explicit prerequisite; their absence must not
block default tests or the bbox/raw-evidence fallbacks.

---

### Task 2: Evidence persistence, target context, and retention

**Files:**
- Create: `backend/app/models/vision_detection.py`,
  `backend/app/models/segmentation_result.py`, `backend/app/models/ocr_result.py`,
  `backend/app/models/barcode_result.py`,
  `backend/app/models/vision_candidate_review.py`,
  `backend/app/models/vision_candidate_outcome.py`, one Alembic migration
- Modify: check-in/image/job schemas and models, `ledger_change_log.py`,
  `backend/app/services/ledger.py`, retention service
- Test: model/migration parity, check-in ownership/target validation, retry idempotency,
  derived-asset retention

- [ ] **Step 1: Write failing persistence tests** for all four evidence types and
  append-only candidate reviews/outcomes. Evidence and candidate rows require
  job/image/region linkage, canonical input SHA-256, engine/version/checkpoint
  metadata, and a unique idempotency key bound to the input digest. Outcomes derive
  that immutable input/idempotency linkage through their unique `candidate_id`.
  Applied outcomes pass `candidate_id` into `apply_update()` and link to the ledger
  change written in the same transaction; conflict/rejected outcomes remain durable
  without a ledger change. Database constraints enforce one terminal outcome per candidate,
  `ledger_change_id IS NOT NULL` exactly for `applied`, matching candidate IDs across
  outcome/change rows, evidence digest equality with the owning image, and a non-null
  checkpoint digest for learned engines.
- [ ] **Step 2: Write failing target-resolution tests.** A user-owned optional
  `shopping_list_id` may resolve through
  `ShoppingList → ShoppingItem → ShoppingConfirmationEvent → PantryItem.source_event_id`.
  Automatic matching is an exact normalized detector-label match among bought items;
  a user-selected shopping item is also allowed after ownership/confirmation checks.
  OCR/free text never selects a target. Zero or multiple matches abstain and produce
  an unmatched/ambiguous review candidate with no pantry mutation.
- [ ] **Step 3: Write failing retention tests** proving revocation and every deletion
  policy remove original, crop, and mask objects idempotently, including retry cleanup.
- [ ] **Step 4: Implement all ORM models and a single parity-tested migration.**
  Re-check consent before derived persistence. Never hold a DB connection or advisory
  lock while external inference runs. The canonical input digest is private,
  user-scoped audit metadata: never expose/log it or use it across users, and remove
  it on full evidence privacy deletion. Define explicit FK deletion behavior for
  images, evidence, candidates, outcomes, and nullable ledger references.
- [ ] **Step 5: Verify and commit** —
  `feat(vision): persist idempotent vision evidence and review candidates`

---

### Task 3: Detector + Edge Vision Agent

**Files:**
- Create: `backend/app/vision/detector.py`, `backend/app/agents/edge_vision.py`
- Test: `tests/test_detector.py`

- [ ] **Step 1: Write failing fixture-replay tests** — `detect(img)` returns immutable
  detections; four boxes yield count four; the type structurally has no brand field.
- [ ] **Step 2: Implement** a lazy `Detector` protocol and RF-DETR adapter using only
  explicit local assets. Missing assets raise `ModelAssetsUnavailable`; constructors
  never auto-download. Document the COCO-grocery-subset baseline and require a
  versioned checkpoint before claiming grocery-specific accuracy.
- [ ] **Step 3: Add opt-in CPU integration smoke** for the pinned local RF-DETR
  checkpoint and record package/checkpoint versions in output evidence.
- [ ] **Step 4: Verify and commit** —
  `feat(vision): add category-and-count detector adapter`

---

### Task 4: Segmenter + retained crops

**Files:**
- Create: `backend/app/vision/segmenter.py`, `backend/app/agents/segmentation.py`
- Test: `tests/test_segmenter.py`

- [ ] **Step 1: Write the failing tests** — given an image + bbox, `segment()` returns a mask and a crop; the pipeline-facing helper persists mask + crop via the `storage/` abstraction and returns `mask_uri`/`crop_uri` (§14.6); the agent emits region metadata only — assert its output schema has no classification/label field (§15.8 forbidden).

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — `Segmenter` protocol + deterministic bbox-crop fallback.
  The SAM3 adapter is GPU integration-only, accepts persisted detections, uses an
  explicitly pinned gated checkpoint, and fails closed when access/assets/hardware
  are unavailable. Persisted mask/crop writes inherit retention metadata.

- [ ] **Step 4: Verify pass. Commit** — `feat(vision): segmentation with crops persisted to object storage`

---

### Task 5A: OCR + structured candidates

**Files:**
- Create: `backend/app/vision/ocr.py`, `backend/app/agents/ocr_label.py`
- Test: `tests/test_ocr.py`

- [ ] **Step 1: Write the failing tests** — fixture crop of
  `"CHOBANI GREEK YOGURT 32 OZ"` preserves `raw_text` verbatim and returns immutable
  per-field candidates for brand, product name, and package size; a low-confidence
  garbled fixture retains unchanged raw text; every candidate carries
  `source="label_ocr"` and `status="estimated"`, never `user_confirmed`.

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — `ocr.py::Ocr` protocol + fixture-replay fake.
  PaddleOCR-VL v1.6 is an isolated integration using explicit local directories or a
  configured service; construction must not trigger vendor downloads. Preserve raw
  text separately from normalized, per-field candidates. `package_size` remains
  evidence until the pantry schema supports it.

- [ ] **Step 4: Verify pass. Commit** — `feat(vision): ocr with structured estimate candidates, raw text preserved`

---

### Task 5B: Barcode — durable evidence, nothing over guessing

**Files:**
- Create: `backend/app/vision/barcode.py`, `backend/app/agents/barcode.py`
- Test: `tests/test_barcode.py`

- [ ] **Step 1: Write the failing tests** — fixture with a clean EAN-13 → exact value decoded; **blurred/unreadable fixture → `None`, never a fabricated value** (assert result is None, §15.10 forbidden); invalid checksum → `None`.

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — decoder wrapper with checksum validation; the agent
  persists a `BarcodeResult` with native decoder metadata or nothing. Do not present
  pyzbar/zbar quality as a calibrated confidence and do not perform Phase-7 product
  matching here. Add an opt-in Python 3.12/native-library smoke test.

- [ ] **Step 4: Verify pass. Commit** — `feat(vision): barcode reader that returns nothing rather than inventing`

---

### Task 6: Target resolution + Source Attribution validation

**Files:**
- Create: `backend/app/agents/source_attribution.py`
- Test: `tests/test_source_attribution.py`

- [ ] **Step 1: Write the failing tests** — every candidate retains evidence linkage;
  missing source/confidence/status is rejected; unmatched and ambiguous candidates
  remain review records; resolved candidates are deterministically ordered and sent
  independently to the ledger so both winner and loser provenance survive.

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — pure validation/order functions plus deterministic
  purchase-context resolution. Do not copy the precedence table or select a winner;
  `apply_update()` remains the sole precedence/conflict authority.

- [ ] **Step 4: Verify pass. Commit** —
  `feat(agents): validate and route provenance-preserving candidates`

---

### Task 7: Wire real steps into the Phase-5 pipeline

**Files:**
- Modify: `backend/app/models/background_job.py`, `backend/app/workers/pipeline.py`,
  `backend/app/workers/steps.py`, `backend/app/agents/background_enrichment.py`,
  `backend/app/agents/auditor.py`
- Test: `tests/test_pipeline_stubs.py` (extend), `tests/test_vision_api.py` (start)

- [ ] **Step 1: Write the failing tests** — a check-in over fixture images (fake
  models injected) produces detection, segmentation, OCR, barcode, and candidate
  evidence linked to the job's images. Only an unambiguously resolved shopping item
  produces ledger proposals; unmatched/ambiguous evidence sets `needs_review`.
  User-confirmed fields remain untouched and rejected estimates remain conflicting.
  Retries create no duplicate evidence or proposals. The Auditor runs over every
  proposal batch before any call to `apply_update()` and can block/downgrade it.

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — reorder the durable steps to detection → segmentation
  → OCR → barcode → product-enrichment no-op, then replace stub bodies with
  claim/infer/persist calls. Claim and consent-check in a short transaction, release
  the DB connection for inference, re-check consent, and persist idempotently.

- [ ] **Step 4: Verify pass** — full suite: `uv run pytest -v`.

- [ ] **Step 5: Commit** — `feat(workers): wire the ordered vision evidence pipeline`

---

### Task 8: POST /vision/analyze

**Files:**
- Create: `backend/app/schemas/vision.py`, `backend/app/routes/vision.py`
- Modify: `backend/app/main.py`
- Test: `tests/test_vision_api.py` (extend)

- [ ] **Step 1: Write the failing tests** — each `image_type` routes correctly;
  authenticated ownership, undeleted state, and current consent are required;
  rate-limit/timeout/model-unavailable errors are typed; responses contain
  source/status/confidence where meaningful and no storage paths; evidence
  persistence is idempotent and pantry rows remain unchanged; unknown type → 422.

- [ ] **Step 2: Run to verify they fail** — FAIL (404).

- [ ] **Step 3: Implement** — thin bounded route: authorize and re-check consent,
  load through storage, dispatch, persist evidence idempotently, and serialize typed
  results without raw exceptions or opaque storage URIs.

- [ ] **Step 4: Verify pass. Commit** — `feat(vision): on-demand analyze endpoint, read-only`

---

### Task 9: Evaluation metrics on samples

**Files:**
- Create: `backend/app/evaluation/metrics.py`, `backend/app/evaluation/test_vision.py`, `backend/app/evaluation/test_ocr.py`, `data/samples/manifest.json`
- Test: (these ARE the tests — all `@pytest.mark.integration`)

- [ ] **Step 1: Write `data/samples/manifest.json`** — per sample image:
  human-authored expected labels, boxes/masks or crop-containment labels, counts, OCR
  fields, and barcode values. Record source/license, file digest, coordinate
  convention, and model/checkpoint metadata.

- [ ] **Step 2: Implement `metrics.py`** — IoU matching, detection precision/recall,
  classification accuracy, count-estimate error, segmentation crop usefulness, OCR
  field accuracy, and exact barcode success (§22), each with a per-sample breakdown.

- [ ] **Step 3: Write the metric suites** — freeze at least 40 independent images
  with at least 10 examples in each declared slice (single product, multi-item pantry,
  readable barcode, difficult label/OCR). Assert detection precision ≥ 0.70 and
  recall ≥ 0.50, useful crop rate ≥ 0.80, OCR brand accuracy ≥ 0.60, exact barcode
  success ≥ 0.95 on readable barcodes, zero invalid/fabricated barcodes, zero
  unmatched ledger writes, zero user-confirmed overwrites, zero retry duplicates, and
  the p95 latency budget declared for each runtime profile. A threshold miss is
  do-not-ship, not a warning. Print the metric table and per-sample breakdown.

- [ ] **Step 4: Run once** — `uv run pytest -m integration backend/app/evaluation -v` → PASS with printed metrics.

- [ ] **Step 5: Commit** — `feat(evaluation): vision and ocr metric suites over sample manifest`

---

## MLE iteration compact

- **Product objective:** turn user-consented grocery images into reviewable evidence
  that reduces manual pantry entry without silently inventing product truth.
- **Data contract:** synthetic unit fixtures are committed and immutable. Integration
  samples must be redistributable or privately access-controlled, human-labeled, and
  split by shopping session so near-duplicate frames cannot cross train/eval
  boundaries. Personal uploads never become training data by default.
- **Baselines:** bbox crop fallback, COCO-grocery-subset RF-DETR, raw OCR, and exact
  checksum-valid barcode decoding. Each advanced model must beat its corresponding
  baseline on the same frozen evaluation manifest.
- **Metrics:** detection precision/recall at documented IoU, category accuracy, count
  absolute error, crop usefulness, per-field OCR accuracy, exact barcode success,
  abstention/review rate, inference latency, and duplicate-evidence rate.
- **Promotion gates:** deterministic default tests green; no network/download during
  import or unit tests; no regression in user-confirmed ledger invariants; evaluation
  floors met with per-sample breakdown; checkpoint/license/digest recorded; CPU/GPU
  resource and latency budgets documented.
- **Runtime/rollback:** model selection is configuration-driven and adapters fail
  closed. Retain the previous artifact manifest and bbox/raw-evidence fallbacks so a
  bad model can be disabled without a schema or ledger rollback.
- **Monitoring:** log only IDs, timings, model metadata, abstentions, and aggregate
  metrics. Never log raw image bytes, OCR label contents, local paths, secrets, or
  unredacted model exceptions.

---

## Done criteria for Phase 6

- Default `uv run pytest` green with no model packages, weights, native barcode
  runtime, GPU, network, live inference, or collection warnings.
- Opt-in CPU/GPU profiles report prerequisites clearly and are green only in their
  documented environments with pinned local assets.
- A fixture check-in produces durable detection/segmentation/OCR/barcode/candidate
  evidence. Only unambiguously resolved purchase context reaches the ledger; user-
  confirmed fields are provably untouched and retries produce no duplicates.
- Revocation/retention deletes originals, crops, and masks idempotently.
- Detector output structurally cannot carry a brand; barcode returns None over guessing; OCR raw text is never silently corrected.
- §22 vision metrics, including segmentation crop usefulness, are computed over
  human-authored `data/samples/` ground truth with floor thresholds asserted.

## Next phase

[Phase 7 — Product/Nutrition Enrichment](phase-7-product-nutrition-enrichment.md): Open Food Facts and USDA fill in what vision estimated — source-attributed, validated, and never guessed.
