# CLAUDE.md — PantryOps Edge (KitchenOS)

Instructions for Claude Code when working in this repo. Keep it simple; the detail lives in the docs below.

## What this project is

PantryOps Edge: a mobile-first grocery memory app. Users plan groceries, cross off what they bought, optionally upload post-shopping photos, and the app keeps a structured pantry ledger that powers recipes and the next shopping list.

## The one rule that governs everything

> User confirmation creates truth. Checklist confirms purchase. Vision and OCR create editable estimates. APIs enrich those estimates. The ledger stores sourced states. The LLM plans and explains from the ledger.

Concretely:

- Every pantry write goes through `services/ledger.py::apply_update()` — no exceptions.
- Every written field carries `source`, `confidence`, `status`. Unsourced writes are rejected.
- Never overwrite a `user_confirmed` / `user_edited` field with an estimate.
- No image is stored or processed without recorded consent.
- The LLM proposes; structured tools commit. It never mutates the ledger directly.
- Recipes never deduct inventory — only `confirm-cooked` does.
- Vague quantities ("used a lot of milk") get a scale question, never a guess.

## Where things are

| Path | What |
| ---- | ---- |
| `Manifest.md` | Product source of truth (29 sections) |
| `documents/plan/` | One implementation plan per build phase (0–10), TDD checkbox style |
| `documents/specs/architecture.md` | System shape, layering, invariants, testing/commit rules |
| `documents/specs/data-models.md` | SourcedField, quantity system, all entities |
| `documents/specs/api-spec.md` | REST contract |
| `documents/specs/agents.md` | The 19 agents and their forbidden actions |

## Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0 (sync, psycopg 3), Pydantic v2, Alembic, PostgreSQL 16, Celery + Redis, MinIO/S3. Managed with `uv`.
- **Mobile:** Expo (React Native), TypeScript, expo-router, AsyncStorage.
- **Vision:** RF-DETR (nano/small) detection, SAM3 segmentation, PaddleOCR-VL v1.6, barcode scanning.
- **LLM/agents:** deepseek/deepseek-v4-flash via OpenRouter; LangGraph + LangSmith orchestration (ADR 003).
- **Tests:** pytest + httpx TestClient (backend, real local Postgres, Celery eager); Jest + @testing-library/react-native (mobile).

## How to work

1. Follow the current phase document in `documents/plan/` task by task — strict TDD: failing test → verify fail → implement → verify pass → commit.
2. Invoke the ECC skills listed in the phase header before starting (e.g. `/ecc:tdd-workflow`, `/ecc:fastapi-patterns`, `/ecc:react-native-patterns`).
3. Specs win over plans; the manifest wins over specs. If they disagree, fix the doc first, then the code.
4. Commits: Conventional Commits with scope — `feat(ledger): …`, `test(vision): …`. One logical change per commit; migrations land with their model change.
5. UI must meet WCAG 2.1 AA: labels on all inputs, visible focus, live regions for async status, never color alone to convey meaning.
6. Run `docker compose up -d` (postgres, redis, minio) before backend tests: `uv run pytest`.

## Never do

- Write pantry state outside the ledger service.
- Mark an estimated field as confirmed.
- Run enrichment on non-consented images.
- Claim food is safe/unsafe, give medical advice, or state prices without a verified source.
- Edit a shipped Alembic migration.
