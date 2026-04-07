# tests/test_hardening.py
"""
Error-path, input-validation, and hardening tests.

Kept separate from test_agents.py (which removes ANTHROPIC_API_KEY at import).
No real LLM calls are made by any test in this file.
"""
import pytest
from fastapi.testclient import TestClient
from services.orchestration.api import app

client = TestClient(app)


# ── /health enhanced shape ───────────────────────────────────────────────────

def test_health_has_required_keys():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "db" in data
    assert "migrations" in data
    assert "api_key_present" in data


def test_health_api_key_present_is_bool():
    res = client.get("/health")
    data = res.json()
    assert isinstance(data["api_key_present"], bool)


def test_health_db_field_is_string():
    res = client.get("/health")
    data = res.json()
    assert data["db"] in ("ok", "down")


def test_health_status_is_ok_or_degraded():
    res = client.get("/health")
    data = res.json()
    assert data["status"] in ("ok", "degraded")


# ── UUID validation on video endpoints ──────────────────────────────────────

def test_video_get_bad_uuid_returns_422():
    res = client.get("/videos/not-a-uuid")
    assert res.status_code == 422
    assert "detail" in res.json()


def test_video_approve_bad_uuid_returns_422():
    res = client.post("/videos/not-a-uuid/approve")
    assert res.status_code == 422


def test_etienne_metrics_bad_uuid_returns_422():
    payload = {"platform": "youtube", "views": 100, "retention_pct": 50.0}
    res = client.post("/etienne/metrics/not-a-uuid", json=payload)
    assert res.status_code == 422


# ── retention_pct validation ─────────────────────────────────────────────────

def test_retention_pct_above_100_returns_422():
    import uuid
    video_id = str(uuid.uuid4())
    payload = {"platform": "youtube", "views": 100, "retention_pct": 150.0}
    res = client.post(f"/etienne/metrics/{video_id}", json=payload)
    assert res.status_code == 422


def test_retention_pct_negative_returns_422():
    import uuid
    video_id = str(uuid.uuid4())
    payload = {"platform": "youtube", "views": 0, "retention_pct": -5.0}
    res = client.post(f"/etienne/metrics/{video_id}", json=payload)
    assert res.status_code == 422


def test_retention_pct_at_boundary_100_is_valid():
    """100.0 should pass Pydantic validation (the endpoint may 404, but not 422)."""
    import uuid
    video_id = str(uuid.uuid4())
    payload = {"platform": "youtube", "views": 0, "retention_pct": 100.0}
    res = client.post(f"/etienne/metrics/{video_id}", json=payload)
    assert res.status_code != 422


# ── week_id date format validation ───────────────────────────────────────────

def test_etienne_report_bad_date_returns_422():
    res = client.get("/etienne/report/2030-13-99")
    assert res.status_code == 422


def test_armand_grocery_bad_date_returns_422():
    res = client.get("/armand/grocery-list/not-a-date")
    assert res.status_code == 422


# ── negative price validation ────────────────────────────────────────────────

def test_ingredient_negative_price_returns_422():
    payload = {"name": "Test Ingredient", "avg_price_per_unit": -1.50}
    res = client.post("/armand/ingredients", json=payload)
    assert res.status_code == 422


# ── lifespan smoke test ───────────────────────────────────────────────────────

def test_lifespan_startup_does_not_crash():
    """Verifies the lifespan handler ran without exception (health returns 200)."""
    res = client.get("/health")
    assert res.status_code == 200
