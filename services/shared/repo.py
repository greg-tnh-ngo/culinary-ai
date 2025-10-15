# services/shared/repo.py
from __future__ import annotations
from sqlalchemy.orm import Session
from services.shared.db import SessionLocal
from services.shared.models import PipelineRun

def save_pipeline_run(kind: str, idea: dict, scripts: list[dict], shoot_card: dict) -> int:
    with SessionLocal() as session:  
        row = PipelineRun(
            kind=kind,
            idea=idea,
            scripts={"items": scripts},
            shoot_card=shoot_card,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id

def get_pipeline_run(run_id: int) -> dict | None:
    with SessionLocal() as session:
        row = session.get(PipelineRun, run_id)
        if not row:
            return None
        return {
            "id": row.id,
            "kind": row.kind,
            "idea": row.idea,
            "scripts": row.scripts,
            "shoot_card": row.shoot_card,
            "created_at": row.created_at.isoformat(),
        }
