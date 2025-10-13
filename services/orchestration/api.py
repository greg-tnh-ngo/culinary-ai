from fastapi import FastAPI
from services.agents.julien.main import curate_stub
from services.agents.marcel.main import write_scripts
from services.agents.camille.main import make_shoot_card

app = FastAPI(title="Culinary AI")

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/ideas/draft")
def draft_idea():
    return curate_stub().model_dump()  # Julien stub

@app.get("/pipeline/short/preview")
def pipeline_short_preview():
    """Runs: Idea (Julien) -> Scripts (Marcel) -> Shoot Card (Camille)."""
    idea = curate_stub().model_dump()
    scripts = [s.model_dump() for s in write_scripts(idea)]
    # choose the tutorial variant body to feed Camille’s defaults
    tutorial_body = next((s["body"] for s in scripts if s["variant"] == "TUTORIAL"), scripts[0]["body"])
    shoot = make_shoot_card(tutorial_body).model_dump()
    return {"idea": idea, "scripts": scripts, "shoot_card": shoot}
