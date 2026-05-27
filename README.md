# culinary-ai

I ran a YouTube channel called Simpliste — French educational content for high schoolers, solo, no budget. It didn't die from lack of ideas. It died from production overhead. The cascade is always the same for solo creators: no script ready means you can't film, filming unprepared means messy footage, messy footage means editing takes forever, by the time you publish you're already behind on the next one.

When I decided to start a French cooking channel, I didn't want to solve that problem with willpower. I wanted to solve it with a system.

culinary-ai is a production operations pipeline for a solo content creator. It turns an idea into a publish-ready package — script, shoot card, editing notes, QC report, platform adaptation — with a single approval gate between you and the internet. Filmed on an iPhone 11. No AI voices, no synthetic humans.

**Hard constraints it was designed around:**
- $100/week grocery budget
- 3 Shorts/week publishing cadence
- ≤72 hours from idea to release-ready package
- ≤15 minutes of active pipeline time per video (target)
- One person operating it

---

## How the pipeline works

Each stage maps to a specific bottleneck in the solo creator workflow:

| Agent | Bottleneck it solves | Model |
|---|---|---|
| **Julien** | Idea curation — what to make this week | claude-haiku |
| **Marcel** | Scripting — TUTORIAL + PERSONAL variants | claude-sonnet-4-6 |
| **Camille** | Shoot preparation — shot list, props, angles | claude-haiku |
| **Pierre** | Editing — assembly notes, texture inserts | claude-haiku |
| **Colette** | QC — culinary fact-check, release packet | claude-sonnet-4-6 |
| **Armand** | Inventory & budget — grocery planning, ledger | claude-haiku |
| **Etienne** | Analytics — retention curves, weekly report | claude-haiku |
| **Lucien** | Cross-platform — TikTok/IG Reels adaptation | stub |

**Flow:** `Julien → Marcel → Camille → (film) → Pierre → Colette → Lucien → publish`

The human step is the filming. Everything else is the system's job.

---

## Why these design decisions

**Two model tiers.** Sonnet handles the tasks where quality matters most — scripting (Marcel) and QC (Colette). Haiku handles the structured, deterministic tasks. This keeps LLM costs low without compromising the output that the viewer actually sees.

**A single approval gate.** `POST /videos/{id}/approve`. You review the release packet, you click approve. Nothing goes to Colette without passing QC. Nothing gets published without a human decision. The system handles volume; the creator handles judgment.

**Hard budget constraints baked into the DB.** Armand tracks every purchase against a $100/week ledger. The dashboard surfaces budget vs. spend in real time. The constraint isn't a guideline — it's enforced at the data layer.

**Observability from day one.** Every LLM call is tracked — tokens, cost, latency, agent. Four SLOs defined: budget adherence, LLM reliability, throughput, p95 latency. This isn't over-engineering; it's what happens when you've run a channel and know that invisible costs kill projects.

**Stub fallbacks on every agent.** The pipeline runs without an API key. Stubs return deterministic outputs so the system stays testable and the dashboard stays functional during development.

---

## Architecture

```
culinary-ai/
├── services/
│   ├── agents/          # Julien, Marcel, Camille, Pierre, Colette, Armand, Etienne
│   ├── orchestration/   # FastAPI app, pipeline runners, LLM tracker
│   └── observability/   # SLO definitions, cost tracking, latency middleware
├── infra/
│   ├── docker-compose.yml
│   └── alembic/         # 5 migrations, 13 tables
├── apps/
│   └── dashboard/       # Read-only HTML dashboard, 7 cards
└── tests/               # 46 tests across agents, observability, hardening
```

**DB schema (13 tables):** `pipeline_runs`, `videos`, `scripts`, `sources`, `ingredients`, `recipes`, `recipe_ingredients`, `ledger_weeks`, `purchases`, `video_metrics`, `llm_calls`, `request_log` + `chapters` JSONB on scripts.

**API:** 30+ endpoints across pipeline, video management, inventory, analytics, observability. Full docs at `/docs` when running locally.

---

## Current status

11 of 13 weeks complete. All agents live with Claude API + stub fallbacks. Full short + long video pipeline operational. 46 tests passing. Dashboard read-only.

**Remaining:** Lucien (cross-platform adaptation), interactive dashboard UX, pipeline parallelisation, batch scheduling.

**Declared but not yet wired:** LangGraph (orchestration DAGs), Celery (job queue), Qdrant (style memory vector DB).

---

## Run it locally

```bash
# 1. Start infrastructure
cd infra && docker-compose up -d

# 2. Create .env at repo root
cp .env.example .env
# Add your ANTHROPIC_API_KEY — pipeline runs on stubs without it

# 3. Run migrations
cd infra && alembic upgrade head

# 4. Start the API
uvicorn services.orchestration.api:app --reload
# → http://localhost:8000        (dashboard)
# → http://localhost:8000/docs   (API explorer)
# → http://localhost:8000/health (health check)
```

---

## Stack

- **Python** + FastAPI + Uvicorn
- **PostgreSQL** + Alembic (migrations)
- **Anthropic SDK** — claude-sonnet-4-6, claude-haiku
- **Docker Compose** — local infrastructure
- **pytest** — 46 tests

---

*Named after the French culinary tradition of giving names to things that matter.*
