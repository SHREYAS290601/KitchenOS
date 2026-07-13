# PantryOps Edge Phase 1: Mobile Shell and Backend Implementation Plan

> **For agentic workers:** Implement task-by-task with strict TDD: write the failing test, watch it fail, implement, watch it pass, commit. Steps use checkbox (`- [ ]`) syntax. REQUIRED ECC SKILLS before starting: `/ecc:tdd-workflow` (the red-green-commit loop every task follows), `/ecc:fastapi-patterns` (app factory + settings + health chassis), `/ecc:database-migrations` (Alembic env + create_all/migration parity), `/ecc:react-native-patterns` (Expo shell + AsyncStorage cache), `/ecc:docker-patterns` (compose stack + backend image).

**Goal:** Stand up the FastAPI backend chassis (app factory, config, DB, health, Alembic, auth placeholder) and an Expo React Native shell with a local checklist cache and typed API client — so every later phase has a tested place to live.

**Architecture:** Per `documents/specs/architecture.md` §2–§4. Single-package backend (no microservices), strict `routes → schemas → services → models` layering, app factory with no module-level engine, Postgres 16 + Redis 7 + MinIO via docker compose.

**Tech Stack:** Python 3.12, uv, FastAPI, SQLAlchemy 2.0 (sync, psycopg 3), Alembic, Pydantic v2 + pydantic-settings, pytest + httpx TestClient, PostgreSQL 16, Redis 7, MinIO, Docker. Mobile: Expo (React Native), TypeScript, expo-router, AsyncStorage, Jest + @testing-library/react-native.

**Out of scope for Phase 1** (later plans): pantry/shopping/vision models and routes, Celery workers (compose includes Redis now so Phase 5 needs no compose change), real auth, push notifications, camera.

**Prerequisites:** Docker Desktop running; `uv` installed; Node 20+ with `npx`; Python 3.12 available to uv.

---

## File structure (locked in by this plan)

```text
pantryops-edge/
├── pyproject.toml                 # backend package, uv-managed
├── uv.lock
├── docker-compose.yml             # postgres:16 + redis:7 + minio
├── .gitignore
├── alembic.ini
├── backend/
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   └── app/
│       ├── __init__.py
│       ├── main.py                # create_app() factory
│       ├── config.py              # Settings (PANTRYOPS_ env prefix)
│       ├── db.py                  # Base, make_engine, make_session_factory
│       ├── deps.py                # get_db, get_current_user (placeholder)
│       └── routes/
│           ├── __init__.py
│           └── health.py          # /healthz + /readyz
├── backend/Dockerfile
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_db.py
│   ├── test_app.py
│   └── test_migrations.py
└── mobile/
    ├── package.json
    ├── app.json
    ├── tsconfig.json
    ├── app/_layout.tsx
    ├── app/index.tsx              # Home: backend-reachable status
    ├── api/client.ts              # typed fetch wrapper
    ├── storage/checklistCache.ts  # AsyncStorage-backed cache
    └── __tests__/checklistCache.test.ts
```

One responsibility per file; routes never touch the engine directly (always `get_db`); nothing imports `main.py` except tests and uvicorn.

---

### Task 1: Repo scaffold + local infrastructure

**Files:**
- Create: `pyproject.toml`, `docker-compose.yml`, `.gitignore`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "pantryops-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn>=0.30",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "sqlalchemy>=2.0.30",
    "psycopg[binary]>=3.1",
    "alembic>=1.13",
]

[dependency-groups]
dev = ["pytest>=8", "httpx>=0.27"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--import-mode=importlib"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["backend/app"]
```

- [ ] **Step 2: Write `docker-compose.yml`** — postgres:16 (user/password/db `pantryops`, healthcheck `pg_isready`), redis:7 (healthcheck `redis-cli ping`), minio (console on 9001, healthcheck on `/minio/health/live`). Redis and MinIO now so Phases 4–5 need no compose change.

- [ ] **Step 3: Write `.gitignore`** — `__pycache__/, *.pyc, .venv/, .env, .pytest_cache/, dist/, node_modules/, .expo/, data/user_uploads/`

- [ ] **Step 4: Verify the stack comes up**

Run: `docker compose up -d && docker compose ps`
Expected: three services `running (healthy)`.

Run: `docker compose exec postgres psql -U pantryops -c "select 1"`
Expected: prints `1`.

- [ ] **Step 5: Commit** — `chore: repo scaffold with docker compose (postgres, redis, minio)`

---

### Task 2: Settings

**Files:**
- Create: `backend/app/__init__.py`, `backend/app/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test** — `tests/test_config.py`

```python
from backend.app.config import Settings


def test_settings_read_from_env(monkeypatch):
    monkeypatch.setenv("PANTRYOPS_DATABASE_URL", "postgresql+psycopg://pantryops:pantryops@localhost:5432/pantryops")
    monkeypatch.setenv("PANTRYOPS_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("PANTRYOPS_STORAGE_BACKEND", "minio")
    s = Settings()
    assert s.database_url.startswith("postgresql+psycopg://")
    assert s.storage_backend == "minio"
```

- [ ] **Step 2: Run to verify it fails** — `uv sync && uv run pytest tests/test_config.py -v` → FAIL (ImportError).

- [ ] **Step 3: Write `backend/app/config.py`** — `Settings(BaseSettings)` with `env_prefix="PANTRYOPS_"`; fields `database_url: str`, `redis_url: str`, `storage_backend: Literal["local", "minio", "s3"] = "local"`, `service_name: str = "pantryops"`.

- [ ] **Step 4: Run to verify it passes** — same command → PASS.

- [ ] **Step 5: Commit** — `feat(backend): env-driven settings with PANTRYOPS_ prefix`

---

### Task 3: DB helpers

**Files:**
- Create: `backend/app/db.py`
- Test: `tests/conftest.py`, `tests/test_db.py`

- [ ] **Step 1: Write `tests/conftest.py`** — session-scoped `engine` fixture that drops/creates the `pantryops` schema against `PANTRYOPS_TEST_DATABASE_URL` (default local compose URL); function-scoped `db` fixture that deletes all rows in reverse table order and yields a `Session` (mirror the GLP conftest pattern).

- [ ] **Step 2: Write the failing test** — `tests/test_db.py`: define a throwaway mapped class on `Base`, `create_all`, assert its table lands in the `pantryops` schema via `inspect(engine).get_table_names(schema="pantryops")`.

- [ ] **Step 3: Run to verify it fails** — `uv run pytest tests/test_db.py -v` → FAIL (ImportError).

- [ ] **Step 4: Write `backend/app/db.py`** — `Base(DeclarativeBase)` with `MetaData(schema="pantryops")`, `make_engine(url)` with `pool_pre_ping=True`, `make_session_factory(engine)` with `expire_on_commit=False`.

- [ ] **Step 5: Run to verify it passes.** (Connection refused → `docker compose up -d`.)

- [ ] **Step 6: Commit** — `feat(backend): schema-scoped base and engine helpers`

---

### Task 4: App factory + health router

**Files:**
- Create: `backend/app/main.py`, `backend/app/routes/__init__.py`, `backend/app/routes/health.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_app.py`:

```python
def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "pantryops"}


def test_readyz_503_when_db_unreachable(client_bad_db):
    assert client_bad_db.get("/readyz").status_code == 503
```

(`client` fixture: monkeypatch env, `TestClient(create_app())`.)

- [ ] **Step 2: Run to verify they fail** — FAIL (ImportError).

- [ ] **Step 3: Implement** — `routes/health.py` router with `/healthz` (static) and `/readyz` (runs `select 1` through the session factory, checks Redis with a short-timeout ping; 503 on either failure). `main.py::create_app()` builds `Settings`, engine, session factory on `app.state`, includes the router.

- [ ] **Step 4: Run to verify they pass** — `uv run pytest tests/test_app.py -v` → PASS.

- [ ] **Step 5: Commit** — `feat(backend): app factory with health and readiness`

---

### Task 5: Dependencies (get_db, auth placeholder)

**Files:**
- Create: `backend/app/deps.py`
- Test: append to `tests/test_app.py`

- [ ] **Step 1: Write the failing test** — a throwaway route depending on `get_db` and `get_current_user`; assert override works via `app.dependency_overrides` and that the default `get_current_user` returns the fixed dev user (`user_id = "dev-user-001"`).

- [ ] **Step 2: Verify fail → implement `deps.py`** — `get_db` generator from `app.state.session_factory` (close in `finally`); `get_current_user` returns a `DevUser` constant. Real auth is a later swap of this one dependency.

- [ ] **Step 3: Verify pass. Commit** — `feat(backend): db session and placeholder auth dependencies`

---

### Task 6: Alembic wired to metadata

**Files:**
- Create: `alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/<initial>.py`
- Test: `tests/test_migrations.py`

- [ ] **Step 1: `uv run alembic init backend/alembic`**; set the local URL in `alembic.ini`; in `env.py` target `Base.metadata`, override URL from `PANTRYOPS_DATABASE_URL` when set, add `include_schemas=True` and `version_table_schema="pantryops"`.

- [ ] **Step 2: Write the failing test** — `tests/test_migrations.py`: run `alembic upgrade head` against a scratch schema (subprocess), then compare the table/column set with `Base.metadata` via SQLAlchemy `inspect` — they must be identical.

- [ ] **Step 3: Generate the initial (empty-domain) migration** — `uv run alembic revision --autogenerate -m "initial"`; hand-review it (autogenerate misses JSONB defaults and check constraints — spec `architecture.md` §4).

- [ ] **Step 4: Verify pass** — `uv run pytest tests/test_migrations.py -v` → PASS.

- [ ] **Step 5: Commit** — `feat(backend): alembic wired to metadata with parity test`

---

### Task 7: Expo app shell

**Files:**
- Create: `mobile/` (via `npx create-expo-app@latest mobile --template blank-typescript`), `mobile/app/_layout.tsx`, `mobile/app/index.tsx`

- [ ] **Step 1: Scaffold** — create the Expo app, add expo-router, Jest + @testing-library/react-native, AsyncStorage.

- [ ] **Step 2: Home screen** — `app/index.tsx` renders the app name as a proper heading (`accessibilityRole="header"`) and a backend-status line. Placeholder tab stubs for Checklist / Pantry / Assist / Check-in / Settings.

- [ ] **Step 3: Verify** — `npx expo start` boots; the home screen renders on simulator or Expo Go.

- [ ] **Step 4: Commit** — `feat(mobile): expo shell with router and screen stubs`

---

### Task 8: Typed API client + reachability

**Files:**
- Create: `mobile/api/client.ts`
- Modify: `mobile/app/index.tsx`
- Test: `mobile/__tests__/client.test.ts`

- [ ] **Step 1: Write the failing test** — `client.ts` exposes `getHealth(): Promise<{status: string; service: string}>`; test with a mocked `fetch` for 200 and network-error paths (error surfaces as a typed failure, not a throw into the UI).

- [ ] **Step 2: Verify fail → implement** — small typed fetch wrapper with base URL from Expo config; no `any`.

- [ ] **Step 3: Wire into Home** — status region uses `accessibilityLiveRegion="polite"` and text (“Backend: reachable/unreachable”) — never color alone.

- [ ] **Step 4: Verify pass** — `npx jest mobile/__tests__/client.test.ts` → PASS.

- [ ] **Step 5: Commit** — `feat(mobile): typed api client with accessible reachability status`

---

### Task 9: Offline checklist cache

**Files:**
- Create: `mobile/storage/checklistCache.ts`
- Test: `mobile/__tests__/checklistCache.test.ts`

- [ ] **Step 1: Write the failing test** — with mocked AsyncStorage: `saveChecklist(list)` then `loadChecklist()` round-trips; `loadChecklist()` on empty storage returns `null`; `clearChecklist()` empties; corrupted JSON returns `null` instead of throwing.

- [ ] **Step 2: Verify fail → implement** — versioned key (`checklist.v1`), JSON serialization, defensive parse.

- [ ] **Step 3: Verify pass. Commit** — `feat(mobile): offline checklist cache`

---

### Task 10: Backend Dockerfile + smoke test

**Files:**
- Create: `backend/Dockerfile`

- [ ] **Step 1: Write the Dockerfile** — uv-based build stage, slim runtime stage, `CMD ["uvicorn", "backend.app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]`.

- [ ] **Step 2: Smoke test**

```bash
docker build -f backend/Dockerfile -t pantryops-backend .
docker run --rm -d --name pantryops -p 8000:8000 \
  -e PANTRYOPS_DATABASE_URL="postgresql+psycopg://pantryops:pantryops@host.docker.internal:5432/pantryops" \
  -e PANTRYOPS_REDIS_URL="redis://host.docker.internal:6379/0" \
  pantryops-backend
sleep 2 && curl -s http://localhost:8000/healthz
```

Expected: `{"status":"ok","service":"pantryops"}`. Clean up: `docker stop pantryops`.

- [ ] **Step 3: Commit** — `feat(backend): container image with factory entrypoint`

---

## Done criteria for Phase 1

- `uv run pytest` green (config, db, app, deps, migrations).
- Backend container answers `/healthz`; `/readyz` reflects DB + Redis reachability.
- Migrations and `create_all` provably agree (parity test).
- Expo app boots, shows accessible backend-reachability status, and the checklist cache round-trips offline.

## Next phase

[Phase 2 — Pantry Ledger and Quantity System](phase-2-pantry-ledger-and-quantity.md): SourcedField, the single ledger write path, the evidence-hierarchy matrix, and the append-only change log — the heart of the product.
