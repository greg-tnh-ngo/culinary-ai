# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Pre-approved permissions

The following Bash command prefixes are pre-approved in `.claude/settings.local.json` — you do not need to ask the user before running them:

| Prefix | Covers |
|---|---|
| `git:*` | All git operations |
| `gh:*` | GitHub CLI (PRs, issues) |
| `ls:*`, `cat:*`, `find:*`, `grep:*`, `echo:*`, `sleep:*` | Basic shell utilities |
| `python:*`, `python3:*` | Python interpreter |
| `poetry:*`, `poetry run:*` | Poetry commands including `poetry run pytest`, `poetry run alembic` |
| `ruff:*`, `black:*`, `mypy:*` | Linting and type checking |
| `alembic:*` | Migration commands (`alembic upgrade head`, `alembic current`, `alembic downgrade -1`) |
| `.venv/bin/python:*`, `.venv/bin/python3:*` | Direct venv Python |
| `.venv/bin/pytest:*`, `.venv/bin/pip:*` | Pytest and pip via venv |
| `docker-compose:*` | Start/stop/inspect infra containers |
| `uvicorn:*` | Start the API server |
| `curl:*` | API endpoint spot-checks |

Anything not in this list (destructive operations, pushing to remote, etc.) should still be confirmed with the user first.

## Commands

```bash
# Start infrastructure (Postgres + Redis)
cd infra && docker-compose up -d

# Run migrations (must be run from infra/)
cd infra && alembic upgrade head
cd infra && alembic revision --message "your_message"

# Run the API
uvicorn services.orchestration.api:app --reload

# Lint & format
black .
ruff check . --fix
mypy services/

# Tests
pytest tests/
```

## Environment

Create a `.env` file at the repo root. Required keys:

```
ANTHROPIC_API_KEY=sk-ant-...   # agents fall back to stubs if absent
DATABASE_URL=postgresql://postgres:postgres@localhost/culinary  # default
```

`.envrc` uses direnv `use dotenv` to load this automatically.

## Architecture

**Entry point:** `services/orchestration/api.py` — FastAPI app, the only place endpoints are defined.

**Agent pipeline** (data flows left to right):
```
julien.curate_stub() → IdeaCard
  → marcel.write_scripts(idea) → [ScriptOut]
    → camille.make_shoot_card(script_body) → ShootCard
```

Each agent lives in `services/agents/<name>/main.py` and exposes a single public function.

**Agent status:**
- `julien` — live: calls `claude-haiku` to generate `IdeaCard`; stubs if no API key
- `marcel` — live: calls `claude-sonnet-4-6` for TUTORIAL + PERSONAL scripts; includes structured `verification` (temps, ratios, claims); JSON retry loop on parse failure
- `camille` — live: prop catalog + stage-direction shotlist extraction; optional `claude-haiku` prop enrichment; stubs if no API key
- `pierre` — editing directive (`EditDirective`), texture inserts, transition notes, haiku
- `colette` — culinary QC (`QCResult`), release packet (`ReleasePacket`), platform assets, sonnet, `tracked_create` wired
- `armand` — grocery list (`GroceryList`), budget planning, haiku
- `etienne` — weekly analytics report (`WeeklyReport`), haiku
- `lucien` — cross-platform adaptation (`PlatformPacket`), TikTok + Instagram variants, haiku

**API endpoints:**
- `GET /health`
- `GET /ideas/draft` — run Julien only, return a single IdeaCard (no DB write)
- `GET /pipeline/short/preview` — run full pipeline, return result without persisting
- `POST /pipeline/short/run` — run full pipeline, persist to DB, return `{run_id, video_id}`
- `GET /pipeline/run/{run_id}` — retrieve a saved pipeline run
- `GET /videos` — list all videos (newest first)
- `GET /videos/{video_id}` — get a video with its scripts

**DB layer** (`services/shared/`):
- `db.py` — SQLAlchemy engine + `SessionLocal`; reads config from `.env` via `pydantic-settings`
- `models.py` — ORM models: `PipelineRun`, `Video`, `Script`, `Source`, `Ingredient`, `Recipe`, `RecipeIngredient`, `LedgerWeek`, `Purchase`
- `repo.py` — `save_pipeline_run()`, `get_pipeline_run()`, `create_video()`, `update_video_status()`, `save_script()`, `get_video()`, `list_videos()`

**Key model fields:**
- `Video`: `id` (UUID), `title`, `stream` (SHORT/LONG/SHORT+LONG), `status` (IDEA→SCRIPT→SHOT→EDIT→QC→READY→SCHEDULED→PUBLISHED)
- `Script`: `id`, `video_id`, `variant` (TUTORIAL/PERSONAL), `body`, `verification` (JSONB)
- `ScriptOut` (Pydantic): `variant`, `body`, `hook_options: List[str]`, `verification: Optional[Dict]`

**Declared-but-not-yet-wired dependencies** (in `pyproject.toml`, not imported anywhere yet):
- `langgraph 0.0.63` — planned for orchestration DAGs (IdeaFlow, PostFlow, BudgetFlow)
- `celery 5.3.6` — planned for background job queue
- `qdrant-client 1.8.2` — planned vector DB for brand-voice style memory
- Do **not** wire these up until the relevant milestone; the agents currently call the Anthropic SDK directly

**Important gotchas:**
- `infra/db.py` is a legacy stub — do not use it; the live DB code is in `services/shared/db.py`
- `infra/infra/` is a stray duplicate directory — do not create files there
- Alembic migrations are hand-written (`target_metadata = None` in `infra/alembic/env.py` — no auto-generate)
- All active agents share the same LLM init pattern: import `anthropic`, read `_cfg.ANTHROPIC_API_KEY`, set `_LLM_AVAILABLE`; always fall back to `_stub_impl()` on failure
- `Decimal(str(float_val))` not `Decimal(float_val)` — matches precision pattern throughout repo
- `test_agents.py` removes `ANTHROPIC_API_KEY` from `os.environ` at module load — keep observability and hardening tests in separate files (`test_observability.py`, `test_hardening.py`)
- `with_retry` in `db.py` only retries `OperationalError` — `IntegrityError`/`ProgrammingError` are bugs, not retried
- Deferred imports inside `finally` blocks in `llm_tracker.py` avoid circular imports — do not move them to module level

## Migration history

| Revision | File | What it adds |
|---|---|---|
| `a1b2c3d4e5f6` | `add_week2_tables.py` | `videos`, `scripts`, `sources`, `ingredients`, `recipes`, `recipe_ingredients`, `ledger_weeks`, `purchases` |
| `d4e5f6a7b8c9` | `add_week7_fields.py` | `planned_recipe_ids` JSONB on `ledger_weeks` |
| `e5f6a7b8c9d0` | `add_video_metrics.py` | `video_metrics` table |
| `f6a7b8c9d0e1` | `add_script_chapters.py` | `chapters` JSONB on `scripts` |
| `a8b9c0d1e2f3` | `add_observability_tables.py` | `llm_calls`, `request_log` |
| `b7c8d9e0f1a2` | `add_idea_draft_to_videos.py` | `idea_draft` JSONB nullable on `videos` |

## What was completed (Weeks 1–11)

**Agents (all in `services/agents/<name>/main.py`):**
- `julien` — idea generation (`IdeaCard`), haiku, stub fallback
- `marcel` — TUTORIAL + PERSONAL scripts (`ScriptOut`), chapters (`Chapter`), sonnet, JSON retry loop, `tracked_create` wired
- `camille` — shoot card, prop catalog, shotlist from stage directions, 3-angle specs (`AngleSpec`), haiku, `tracked_create` wired
- `pierre` — editing directive (`EditDirective`), texture inserts, transition notes, haiku
- `colette` — culinary QC (`QCResult`), release packet (`ReleasePacket`), platform assets, sonnet, `tracked_create` wired
- `armand` — grocery list (`GroceryList`), budget planning, haiku
- `etienne` — weekly analytics report (`WeeklyReport`), haiku

**Shared services:**
- `services/shared/llm_tracker.py` — `compute_cost()` + `tracked_create()` (token/cost tracking, persists to `llm_calls`)
- `services/shared/repo.py` — 30+ functions; 10 critical writes wrapped with `with_retry`
- `services/shared/db.py` — engine, `SessionLocal`, `ping_db`, `with_retry`

**API (`services/orchestration/api.py`):**
- 30+ endpoints, `BaseHTTPMiddleware` request timing, lifespan handler
- Input validation: `_validate_uuid`, `_validate_date`, Pydantic validators on `retention_pct` + `avg_price_per_unit`
- try/except on all critical endpoints; raw exceptions never exposed to clients

**Dashboard (`apps/dashboard/index.html`):**
- 7 interactive tabs: Overview (read-only cards), Videos (Kanban), Ingredients CRUD, Recipes CRUD, Grocery planner, Analytics (Chart.js), Agents panel
- Vanilla JS, fetch API, dark theme, native `<dialog>` modals, localStorage tab persistence, toast notifications

**Tests:** 46 total — `test_agents.py` (28), `test_observability.py` (4), `test_hardening.py` (14)

## Tasks remaining for next session

### Week 14+: Future enhancements
- Targeted script regeneration: `POST /videos/{id}/regenerate-scripts` — re-run Marcel only without a full pipeline run
- langgraph DAG orchestration (IdeaFlow, PostFlow, BudgetFlow) — not yet wired
- Celery background job queue — not yet wired
- Qdrant vector DB for brand-voice style memory — not yet wired

## Runbooks

### DB Down
**Symptoms**
- `GET /health` returns `{"db": "down"}` or HTTP 500
- All `POST /pipeline/*` and `GET /videos/*` return 500
- Logs show `sqlalchemy.exc.OperationalError`

**Recovery steps**
1. `cd infra && docker-compose ps` — verify the postgres container is running
2. If stopped: `docker-compose up -d postgres`
3. If running but unreachable: `docker-compose port postgres 5432` — check port binding
4. Confirm: `psql postgresql://postgres:postgres@localhost/culinary -c "SELECT 1"`
5. Hit `GET /health` again — `db` should return `"ok"` once the connection pool recovers
6. If pool doesn't recover: `pkill -f uvicorn && uvicorn services.orchestration.api:app --reload`

### API Key Missing
**Fallback behavior**
- All agents fall back to `_stub_impl()` — API continues to serve requests
- `GET /health` returns `"api_key_present": false`
- No LLM calls are made; all output is deterministic stub data
- This is NOT a fatal condition — the API keeps running

**Recovery steps**
1. Set `ANTHROPIC_API_KEY=sk-ant-...` in `.env`
2. Restart: `uvicorn services.orchestration.api:app --reload`
3. Confirm: `curl http://localhost:8000/health | python3 -m json.tool` → `"api_key_present": true`

### Migration Failure
**Symptoms**
- `alembic upgrade head` exits non-zero
- `GET /health` returns `"migrations": null` or shows an outdated revision
- API returns 500 on first DB-touching request

**Rollback steps**
1. `cd infra && alembic current` — identify current revision
2. `alembic downgrade -1` — roll back one step
3. Fix the migration file in `infra/alembic/versions/`
4. `alembic upgrade head` — re-apply
5. `alembic current` — should show the head revision

### High LLM Costs (Kill Switch)
**Symptoms**
- `GET /observability/costs` shows unexpectedly high `total_cost_usd`
- `GET /observability/slo` shows `budget` SLO failing

**Kill switch procedure**
1. In `.env`, rename `ANTHROPIC_API_KEY` → `ANTHROPIC_API_KEY_DISABLED`
2. Restart the API — all agents fall back to stubs immediately
3. Identify root cause: `GET /observability/costs` shows which agent is driving spend
4. Re-enable by restoring the key name once the issue is resolved

## Disaster Playbooks

### Full DB Restore from Backup

**Prerequisites:** A dump file at `backup.sql` (produced by `pg_dump culinary > backup.sql`).

```bash
# 1. Stop the API
pkill -f uvicorn

# 2. Drop and recreate the DB
psql postgresql://postgres:postgres@localhost -c "DROP DATABASE culinary;"
psql postgresql://postgres:postgres@localhost -c "CREATE DATABASE culinary;"

# 3. Restore from dump
psql postgresql://postgres:postgres@localhost/culinary < backup.sql

# 4. Re-run migrations to confirm schema is at head
cd infra && alembic upgrade head

# 5. Restart the API
uvicorn services.orchestration.api:app --reload

# 6. Verify
curl http://localhost:8000/health
```

### Rollback Last Migration

```bash
cd infra

# Check current revision
alembic current

# Roll back one migration
alembic downgrade -1

# Confirm
alembic current

# Restart API if the reverted schema is already deployed
pkill -f uvicorn && uvicorn services.orchestration.api:app --reload
```
