# PantryOps Edge — Build Plan Overview

> **For agentic workers:** Each phase document in this folder is a self-contained implementation plan in the style of a superpowers executing-plan: numbered tasks with checkbox (`- [ ]`) steps that alternate write-failing-test → verify-fail → implement → verify-pass → commit. Implement task-by-task in order. Before starting a phase, invoke the ECC skills listed in its header (e.g. `/ecc:tdd-workflow`, `/ecc:fastapi-patterns`) — they load the patterns the phase's code must follow.

Specs cited by every phase (read them first, change them there — never restate in a plan):

- `documents/specs/architecture.md` — system shape, monorepo layout, layering, the 7 invariants, evidence-hierarchy enforcement, testing/commit rules
- `documents/specs/data-models.md` — SourcedField, quantity system, lifecycle, all 12 entities
- `documents/specs/api-spec.md` — every endpoint with request/response contracts
- `documents/specs/agents.md` — the 19 agents with purposes and forbidden actions

## Phase index

| Phase | Document | Focus | Key ECC skills |
| ----- | -------- | ----- | -------------- |
| 0 | [phase-0-product-definition.md](phase-0-product-definition.md) | Specs, README, ADRs | `ecc:plan`, `ecc:api-design` |
| 1 | [phase-1-mobile-shell-and-backend.md](phase-1-mobile-shell-and-backend.md) | FastAPI chassis + Expo shell | `ecc:fastapi-patterns`, `ecc:database-migrations`, `ecc:react-native-patterns`, `ecc:docker-patterns`, `ecc:tdd-workflow` |
| 2 | [phase-2-pantry-ledger-and-quantity.md](phase-2-pantry-ledger-and-quantity.md) | Ledger write path + quantity system | `ecc:python-patterns`, `ecc:postgres-patterns`, `ecc:python-testing`, `ecc:backend-patterns`, `ecc:tdd-guide` |
| 3 | [phase-3-shopping-checklist.md](phase-3-shopping-checklist.md) | Lists, cross-off, checklist-to-ledger | `ecc:fastapi-patterns`, `ecc:react-testing`, `ecc:python-testing`, `ecc:database-migrations` |
| 4 | [phase-4-active-assistance.md](phase-4-active-assistance.md) | Router, assistant, consent, auditor v1 | `ecc:agent-harness-construction`, `ecc:security-review`, `ecc:error-handling`, `ecc:react-native-patterns` |
| 5 | [phase-5-silent-check-in.md](phase-5-silent-check-in.md) | Job model + Celery pipeline skeleton | `ecc:redis-patterns`, `ecc:python-patterns`, `ecc:backend-patterns`, `ecc:python-testing` |
| 6 | [phase-6-vision-ocr-enrichment.md](phase-6-vision-ocr-enrichment.md) | Real detection/segmentation/OCR/barcode | `ecc:pytorch-patterns`, `ecc:eval-harness`, `ecc:python-testing`, `ecc:python-review` |
| 7 | [phase-7-product-nutrition-enrichment.md](phase-7-product-nutrition-enrichment.md) | Open Food Facts + USDA enrichment | `ecc:security-reviewer`, `ecc:error-handling`, `ecc:python-testing`, `ecc:api-design` |
| 8 | [phase-8-recipe-and-consumption.md](phase-8-recipe-and-consumption.md) | Recipes, confirm-cooked, deduction | `ecc:python-patterns`, `ecc:agent-harness-construction`, `ecc:python-testing`, `ecc:react-testing` |
| 9 | [phase-9-review-and-preference-memory.md](phase-9-review-and-preference-memory.md) | Reviews → preference rules | `ecc:python-patterns`, `ecc:python-testing`, `ecc:code-review` |
| 10 | [phase-10-evaluation-and-demo.md](phase-10-evaluation-and-demo.md) | Metrics, E2E demo, seeded data | `ecc:eval-harness`, `ecc:e2e-testing`, `ecc:verification-loop` |

Pre-merge review passes for any phase: `/ecc:fastapi-review` (backend routes/services), `/ecc:python-review` (general Python), `/ecc:database-reviewer` via `/ecc:code-review` (migrations and queries).

## Core rule (applies to every phase)

> User confirmation creates truth. Checklist confirms purchase. Vision and OCR create editable estimates. APIs enrich those estimates. The ledger stores sourced states. The LLM plans and explains from the ledger.

Structurally: every pantry write goes through `services/ledger.py::apply_update()`; every write carries source + confidence + status; user-confirmed values are never overwritten by estimates; no silent processing without consent; the LLM proposes, tools commit. The seven invariants in `architecture.md` §8 each get a dedicated test, and any phase that touches them must keep those tests green.

## MVP scope

The MVP (Manifest §20) is phases 0–9 at baseline quality; phase 10 proves it end to end. Out of scope entirely: delivery ordering, live store prices, fully-automatic exact recognition, exact expiry prediction, medical nutrition advice, multi-user households, smart fridge integration, and any background processing on photos the user did not intentionally upload.

## How the phases chain

```text
0 specs → 1 chassis (backend + mobile shell)
        → 2 ledger + quantity   (the heart — everything else calls apply_update)
        → 3 checklist           (first real writes via the ledger)
        → 4 active assistance   (first LLM agents + consent + auditor v1)
        → 5 silent check-in     (job model + pipeline as stubs)
        → 6 vision/OCR          (stubs become real models)
        → 7 product enrichment  (external APIs, source-attributed)
        → 8 recipes/consumption (read the ledger, deduct only on confirm)
        → 9 preference memory   (reviews adapt future lists)
        → 10 evaluation + demo  (nine-step demo, §22 metrics)
```

Each phase ends with a working, tested system — no phase leaves the build red.
