# Culinary AI Project

An agentic, privacy-first pipeline for a solo French cooking channel. Turns ideas → scripts → shoot cards → edits → QC → platform-ready packages. Filmed on iPhone 11; no AI voices or synthetic humans.

## Agent Roster

| Agent | Role | Status |
|---|---|---|
| **Julien** | Recipe & idea curator | Live (claude-haiku) |
| **Marcel** | Scriptwriter (TUTORIAL + PERSONAL variants) | Live (claude-sonnet-4-6) |
| **Camille** | Production guidance — shoot card, props, shotlist, multi-angle specs | Live (claude-haiku) |
| **Pierre** | Video editing rules, texture inserts, assembly notes | Live (claude-haiku) |
| **Colette** | QC, culinary fact-check, release packet, platform adaptation | Live (claude-sonnet-4-6) |
| **Armand** | Inventory, grocery planning, budget ($100/week) | Live (claude-haiku) |
| **Etienne** | Analytics, retention curves, weekly insights report | Live (claude-haiku) |
| **Lucien** | Cross-platform adaptation (TikTok, IG Reels) | Stub |

Pipeline flow: `Julien → Marcel → Camille → (film) → Pierre → Colette → Lucien → publish`

## Quick Setup

```bash
# 1. Start infrastructure
cd infra && docker-compose up -d

# 2. Create .env at repo root with your keys (see Environment section below)

# 3. Run migrations
cd infra && alembic upgrade head

# 4. Start the API
uvicorn services.orchestration.api:app --reload
# → http://localhost:8000        (dashboard)
# → http://localhost:8000/health (health check)
# → http://localhost:8000/docs   (API explorer)
```

## Environment

```
ANTHROPIC_API_KEY=sk-ant-...        # required for live agents; stubs work without it
PGHOST=localhost
PGPORT=5432
PGUSER=postgres
PGPASSWORD=postgres
PGDATABASE=culinary
```

`.envrc` uses direnv `use dotenv` to load `.env` automatically.

## API Endpoints (30+)

### Core pipeline
| Method | Path | Description |
|---|---|---|
| GET | `/health` | DB status, migration version, API key presence |
| GET | `/ideas/draft` | Run Julien, return one IdeaCard |
| GET | `/pipeline/short/preview` | Full short pipeline, no DB write |
| POST | `/pipeline/short/run` | Full short pipeline, persist, return `{run_id, video_id}` |
| POST | `/pipeline/long/run` | Full long pipeline, persist |
| GET | `/pipeline/run/{run_id}` | Retrieve a saved run |

### Videos
| Method | Path | Description |
|---|---|---|
| GET | `/videos` | List all videos (newest first) |
| GET | `/videos/{video_id}` | Video + scripts detail |
| POST | `/videos/{video_id}/approve` | Approve video, trigger platform adaptation |
| POST | `/videos/{video_id}/request-changes` | Send feedback, revert to SCRIPT |
| POST | `/pipeline/short/qc/{video_id}` | Run Colette QC + generate release packet |

### Armand (inventory & budget)
| Method | Path | Description |
|---|---|---|
| GET | `/armand/grocery-list/{week_id}` | Shopping list for the week |
| POST | `/armand/plan` | Plan recipes for a week, update budget |
| GET/POST | `/armand/ingredients` | List or create ingredients |
| GET/PUT | `/armand/ingredients/{id}` | Get or update ingredient |
| GET | `/armand/recipes` | List recipes |
| POST | `/armand/recipes` | Create recipe |
| GET | `/armand/recipes/{recipe_id}` | Recipe detail |

### Etienne (analytics)
| Method | Path | Description |
|---|---|---|
| GET | `/etienne/report/{week_id}` | Weekly insights report |
| POST | `/etienne/metrics/{video_id}` | Ingest platform metrics |
| GET | `/etienne/metrics/{video_id}` | Get metrics for a video |

### Observability
| Method | Path | Description |
|---|---|---|
| GET | `/observability/costs` | LLM spend this week, breakdown by agent |
| GET | `/observability/slo` | 4 SLOs: budget, LLM reliability, throughput, latency |
| GET | `/observability/latency` | p50/p95 per endpoint (last 7 days) |

### Dashboard & utilities
| Method | Path | Description |
|---|---|---|
| GET | `/` | Dashboard HTML (read-only, static cards) |
| GET | `/dashboard/summary` | Budget + pipeline status + production queue JSON |
| GET | `/calendar.ics` | ICS calendar feed of scheduled videos |

## Current Status — Weeks 1–11 Complete

### Built this far
- **Agents:** Julien, Marcel, Camille, Pierre, Colette, Armand, Etienne all live with Claude API + stub fallbacks
- **Pipeline:** Full short + long video pipeline, idea → scripts → shoot card → QC → release packet → platform adaptation
- **DB schema:** 13 tables across 5 migrations — `pipeline_runs`, `videos`, `scripts`, `sources`, `ingredients`, `recipes`, `recipe_ingredients`, `ledger_weeks`, `purchases`, `video_metrics`, `llm_calls`, `request_log` + `chapters` JSONB on scripts
- **Observability:** LLM token/cost tracking (`llm_tracker.py`), request timing middleware, 4 SLO definitions, `/observability/*` endpoints
- **Dashboard:** `apps/dashboard/index.html` — 7 read-only cards: budget, pipeline status, production queue, weekly insights, grocery list, LLM costs, SLO health
- **Hardening:** Input validation (UUID params, date formats, retention %, negative prices), DB retry logic with exponential backoff, FastAPI lifespan handler, enhanced `/health`, try/except on all critical endpoints
- **Runbooks:** Documented in `CLAUDE.md` — DB down, API key missing, migration failure, high LLM costs kill switch, full DB restore, migration rollback
- **Tests:** 46 tests across `test_agents.py`, `test_observability.py`, `test_hardening.py`

**Declared, not yet wired:** LangGraph (orchestration DAGs), Celery (job queue), Qdrant (style memory vector DB)

**Not started yet:** Lucien (cross-platform adaptation), interactive dashboard UI

## Remaining Work

### Week 12: Scale polish
- Target: ≤15 min active time per short video end-to-end
- Lucien agent implementation (TikTok/IG Reels cross-platform adaptation)
- Pipeline timing optimisation, parallelise agent calls where possible
- Batch scheduling: queue multiple ideas and run overnight

### Week 13+: Interactive Dashboard (UX overhaul — HIGH PRIORITY)
The current dashboard is read-only cards. The product vision is a **fully interactive management app** for a solo content creator. Everything below should be buildable in a single session.

**What needs to exist:**
- **Video pipeline board** — Kanban-style view of all videos by status (IDEA → SCRIPT → SHOT → EDIT → QC → READY → SCHEDULED → PUBLISHED). Click a card to open detail. Drag to advance status (or button).
- **Approve / Request changes UI** — One-click approve button per video. Rejection flow with a text field for feedback, directly calling `POST /videos/{id}/request-changes`.
- **Script editor** — Inline viewer for TUTORIAL and PERSONAL script variants. Read-only with a "Regenerate" button that re-runs Marcel.
- **Agent controls** — Per-agent cost budget cap, enable/disable toggle (sets API key kill switch per agent), last-run timestamp and token count.
- **Ingredient & recipe CRUD** — Add/edit/delete ingredients with price and stock level. Create and link recipes. Drives the grocery planner.
- **Grocery planner** — Select recipes for the week, see projected cost vs $100 budget, generate shopping list.
- **Analytics view** — Per-video retention %, views over time chart (Chart.js), weekly report with recommendations.
- **Observability panel** — Live SLO status dots, cost bar chart by agent, p95 latency per endpoint.
- **Design language** — Dark theme (already started), system-ui font, high-contrast cards, clear affordances, no dead-end states. Every list item should be actionable. Mobile-friendly (content creators work on phones).

**Tech approach (suggested):**
- Keep it a single `apps/dashboard/index.html` (no build step, no framework)
- Use vanilla JS + fetch API — all data already served by the existing FastAPI endpoints
- Add any missing CRUD endpoints (`DELETE /armand/ingredients/{id}`, `PUT /videos/{id}/status`, etc.) in the same session
- Modal dialogs for forms, toast notifications for success/error

## 12-Week Roadmap

| Week | Milestone | Status |
|---|---|---|
| 1 | Repo scaffolding, local dev, hello-world pipeline | Done |
| 2 | DB schemas, event contracts, asset conventions | Done |
| 3 | Julien, Marcel, Camille v1 — idea → scripts → shoot card | Done |
| 4 | Pierre (editing rules) + Colette (QC + release packet) | Done |
| 5 | Lucien (cross-platform) + one-click approval gate | Done |
| 6 | Armand — inventory & budget via receipt OCR + price scraping | Done |
| 7 | Dashboard planner, ICS calendar feed, grocery lists | Done |
| 8 | Etienne — analytics, retention curves, weekly 1-pager | Done |
| 9 | Long-form flow (SHORT+LONG), chapter outlines, multi-angle | Done |
| 10 | Observability, SLOs, cost dashboards | Done |
| 11 | Hardening, runbooks, disaster playbooks | Done |
| 12 | Scale polish — target: ≤15 min active time per short | Remaining |
| 13+ | Interactive dashboard UX overhaul | Remaining |

**Definition of done:** 3 Shorts/week, ≤$100 grocery budget, all posts gated behind a single approval click, entire idea→release-packet cycle ≤72 hours.
