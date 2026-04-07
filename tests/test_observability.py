# tests/test_observability.py
"""Observability, SLO, and cost tracking tests.

Kept in a separate file from test_agents.py because that file removes
ANTHROPIC_API_KEY from the environment at module load time, which would
interfere with cost calculation tests.
"""


def test_llm_tracker_computes_cost():
    from services.shared.llm_tracker import compute_cost

    # Haiku: 1000 input, 500 output
    # (1000 * 0.80 + 500 * 4.00) / 1_000_000 = 0.0028
    cost = compute_cost("claude-haiku-4-5-20251001", 1000, 500)
    assert abs(float(cost) - 0.0028) < 1e-7

    # Sonnet: 2000 input, 1000 output
    # (2000 * 3.00 + 1000 * 15.00) / 1_000_000 = 0.021
    cost2 = compute_cost("claude-sonnet-4-6", 2000, 1000)
    assert abs(float(cost2) - 0.021) < 1e-7

    # Unknown model falls back to sonnet rates
    # (1000 * 3.00 + 1000 * 15.00) / 1_000_000 = 0.018
    cost3 = compute_cost("unknown-model-xyz", 1000, 1000)
    assert abs(float(cost3) - 0.018) < 1e-7


def test_observability_cost_endpoint():
    from fastapi.testclient import TestClient
    from services.orchestration.api import app
    client = TestClient(app)
    res = client.get("/observability/costs")
    assert res.status_code == 200
    data = res.json()
    assert "total_cost_usd" in data
    assert "by_agent" in data
    assert "since" in data
    assert isinstance(data["by_agent"], list)
    assert isinstance(data["total_cost_usd"], float)


def test_observability_slo_endpoint():
    from fastapi.testclient import TestClient
    from services.orchestration.api import app
    client = TestClient(app)
    res = client.get("/observability/slo")
    assert res.status_code == 200
    slos = res.json()
    assert isinstance(slos, list)
    assert len(slos) == 4
    names = {s["name"] for s in slos}
    assert "budget" in names
    assert "llm_reliability" in names
    assert "pipeline_throughput" in names
    assert "short_pipeline_latency" in names
    for slo in slos:
        assert "passing" in slo
        assert isinstance(slo["passing"], bool)
        assert "current_value" in slo
        assert "description" in slo


def test_request_log_middleware():
    import time
    from fastapi.testclient import TestClient
    from services.orchestration.api import app
    from services.shared.db import SessionLocal
    from services.shared.models import RequestLog

    client = TestClient(app)

    with SessionLocal() as session:
        before = session.query(RequestLog).count()

    client.get("/health")

    # asyncio.create_task fires in background — poll up to 2s for flush
    deadline = time.time() + 2.0
    count_after = before
    while time.time() < deadline and count_after == before:
        with SessionLocal() as session:
            count_after = session.query(RequestLog).count()
        if count_after == before:
            time.sleep(0.05)

    assert count_after > before, "Expected at least one new request_log row after GET /health"
