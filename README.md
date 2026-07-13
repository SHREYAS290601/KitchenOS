# PantryOps Edge

PantryOps Edge is a mobile-first, checklist-confirmed, edge-vision grocery memory app that helps users plan groceries, confirm purchases, enrich product details from images/OCR/barcodes, track pantry quantities, recommend recipes, and improve future shopping lists from usage and reviews.

## The seven questions it answers

```text
What should I buy?
What did I actually buy?
What do I currently have?
What can I cook?
What is running low?
What did I dislike last time?
What should go on my next shopping list?
```

## Core identity

> **A mobile grocery operating system powered by checklist confirmation, edge vision, editable estimates, structured pantry memory, and LLM planning.**

The one rule that governs everything:

> **User confirmation creates truth. Checklist confirms purchase. Vision and OCR create editable estimates. APIs enrich those estimates. The ledger stores sourced states. The LLM plans and explains from the ledger.**

## Documentation map

| Document | Question it answers |
| -------- | ------------------- |
| [Manifest.md](Manifest.md) | What is this product? (source of truth, 29 sections) |
| [documents/plan/](documents/plan/00-overview.md) | What do I build next? (phases 0–10, TDD checkbox plans) |
| [documents/specs/architecture.md](documents/specs/architecture.md) | How is the system shaped? (layers, invariants, testing rules) |
| [documents/specs/data-models.md](documents/specs/data-models.md) | What are the entities? (SourcedField, quantity system) |
| [documents/specs/api-spec.md](documents/specs/api-spec.md) | What is the REST contract? |
| [documents/specs/agents.md](documents/specs/agents.md) | What may each of the 19 agents do — and never do? |
| [documents/specs/adr/](documents/specs/adr/001-job-queue.md) | Why were the big technical choices made? |
| [CLAUDE.md](CLAUDE.md) | How should agents work in this repo? |

## MVP scope (Manifest §20)

1. React Native mobile app shell
2. Hosted backend
3. Pantry ledger with field-level source metadata
4. Shopping-list generation
5. Checklist cross-off purchase confirmation
6. Fail-safe quantity system
7. Ad-hoc quantity update flow
8. Active while-shopping question flow
9. Image upload with consent
10. Post-shopping grocery check-in
11. Background enrichment job model
12. OCR/label extraction baseline
13. Object detection or grocery classification baseline
14. Editable estimated fields
15. Recipe recommendation from ledger
16. Recipe confirmation and inventory deduction
17. Product review after first use
18. Generalized preference rules
19. Audit layer

## Quickstart

There is no runnable code yet. Implementation starts with [Phase 1 — Mobile Shell and Backend](documents/plan/phase-1-mobile-shell-and-backend.md), which scaffolds the FastAPI backend, Expo mobile shell, and the Postgres/Redis/MinIO docker compose stack. Once Phase 1 lands, this section will hold the real setup commands (`docker compose up -d`, `uv run pytest`, `npx expo start`).
