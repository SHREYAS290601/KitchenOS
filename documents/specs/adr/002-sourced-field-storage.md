# ADR 002: SourcedField as JSONB columns + append-only change log

**Status:** Accepted (2026-07-12)

## Context

Every meaningful pantry field (quantity, category, expiry, brand, …) carries field-level provenance: `value, source, confidence, status, editable, last_updated`. The evidence hierarchy ("never overwrite a user-confirmed value with an estimate") is enforced per field on every write, and the UI renders per-field badges from the same metadata. The storage shape must make reading an item with all its provenance a single-row fetch.

## Decision

Store each SourcedField as a **JSONB column on `pantry_item`** (one column per field, holding the full metadata object), and record every accepted write as a row in an **append-only `ledger_change_log`** table (item id, field name, old/new metadata, actor, timestamp). Current state is one row read; history is a separate table you only touch when auditing.

## Alternative rejected

- **Normalized `field_provenance` table** (one row per field per item) — reading one pantry item becomes a join and pivot across ~10 rows; every list screen pays that cost. Provenance is always read *with* its value, never queried independently at MVP scale, so normalization buys nothing.

## Consequences

- Validation lives in **Pydantic, not the database**: the SourcedField model validates shape, status enum, and confidence range before anything reaches SQLAlchemy. The DB guarantees only JSONB well-formedness.
- The ledger service (`services/ledger.py::apply_update()`) is the single place that writes both the JSONB column and the change-log row, in one transaction.
- Cross-field queries on provenance (e.g. "all fields with status=estimated") use JSONB operators; if that ever becomes hot, a generated column or index is the escape hatch — not a schema rewrite.
