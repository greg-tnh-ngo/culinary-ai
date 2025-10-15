# services/orchestration/api.py
from fastapi import FastAPI, HTTPException
from services.agents.julien.main import curate_stub
from services.agents.marcel.main import write_scripts
from services.agents.camille.main import make_shoot_card

# NEW: DB bits
from services.shared.db import ping_db
from services.shared.repo import save_pipeline_run, get_pipeline_run

app = FastAPI(title="Culinary AI")

@app.get("/health")
def health_check():
    # show DB status so you know infra is up
    return {"status": "ok", "db": "up" if ping_db() else "down"}

@app.get("/ideas/draft")
def draft_idea():
    return curate_stub().model_dump()

@app.get("/pipeline/short/preview")
def pipeline_short_preview():
    idea = curate_stub().model_dump()
    scripts = [s.model_dump() for s in write_scripts(idea)]
    tutorial_body = next((s["body"] for s in scripts if s["variant"] == "TUTORIAL"), scripts[0]["body"])
    shoot = make_shoot_card(tutorial_body).model_dump()
    return {"idea": idea, "scripts": scripts, "shoot_card": shoot}

# NEW: run and persist (uses SessionLocal under the hood via repo.py)
@app.post("/pipeline/short/run")
def pipeline_short_run():
    idea = curate_stub().model_dump()
    scripts = [s.model_dump() for s in write_scripts(idea)]
    tutorial_body = next((s["body"] for s in scripts if s["variant"] == "TUTORIAL"), scripts[0]["body"])
    shoot = make_shoot_card(tutorial_body).model_dump()
    run_id = save_pipeline_run("SHORT", idea, scripts, shoot)
    return {"run_id": run_id}

# NEW: retrieve a saved run by id
@app.get("/pipeline/run/{run_id}")
def pipeline_get(run_id: int):
    row = get_pipeline_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="run not found")
    return row
