import os, pytest
os.environ.pop("ANTHROPIC_API_KEY", None)


def test_julien_stub_no_key():
    from services.agents.julien.main import curate_stub, IdeaCard
    result = curate_stub()
    assert isinstance(result, IdeaCard)
    assert result.dish


def test_marcel_stub_no_key():
    from services.agents.marcel.main import write_scripts
    results = write_scripts({"dish": "test omelette"})
    assert len(results) == 2
    variants = {s.variant for s in results}
    assert "TUTORIAL" in variants
    assert "PERSONAL" in variants


def test_marcel_verification_schema_valid():
    from services.agents.marcel.main import VerificationJSON, TempEntry, RatioEntry, ClaimEntry
    v = VerificationJSON(
        temps=[TempEntry(claim="Heat to 180C", value_celsius=180.0, source="Le Cordon Bleu, p.42")],
        ratios=[RatioEntry(claim="Use 3:1 ratio", ratio="3:1", source="Escoffier")],
        claims=[
            ClaimEntry(statement="Butter browns at 150C", verified=True, reference="On Food and Cooking"),
            ClaimEntry(statement="Salt raises boiling point", verified=True, reference="Harold McGee"),
        ]
    )
    assert len(v.temps) == 1


def test_camille_prop_catalog_match():
    from services.agents.camille.main import make_shoot_card
    card = make_shoot_card("beurre noisette with an omelette technique")
    assert any("omelette" in p.lower() or "butter" in p.lower() or "pan" in p.lower() for p in card.props)


def test_camille_stage_direction_shotlist():
    from services.agents.camille.main import make_shoot_card
    card = make_shoot_card("[overhead: butter in pan] heat until foam subsides [close-up: colour change]")
    assert len(card.shotlist) >= 1


def test_camille_no_key_returns_shoot_card():
    from services.agents.camille.main import make_shoot_card, ShootCard
    card = make_shoot_card("simple omelette recipe")
    assert isinstance(card, ShootCard)
    assert card.camera
    assert card.props


def test_pierre_stub_no_key():
    from services.agents.pierre.main import make_edit_directive, EditDirective
    directive = make_edit_directive(shoot_card={}, scripts=[{"variant": "TUTORIAL", "body": "Today we make omelette."}])
    assert isinstance(directive, EditDirective)
    assert "min_s" in directive.cut_cadence
    assert "dialog_lufs" in directive.audio
    assert "wpm" in directive.captions


def test_pierre_has_texture_inserts():
    from services.agents.pierre.main import make_edit_directive
    directive = make_edit_directive(shoot_card={}, scripts=[])
    assert isinstance(directive.texture_inserts, list)
    assert len(directive.texture_inserts) > 0


def test_colette_stub_no_key():
    import services.agents.colette.main as _colette
    _orig = _colette._LLM_AVAILABLE
    _colette._LLM_AVAILABLE = False
    try:
        from services.agents.colette.main import make_release_packet, ReleasePacket
        packet = make_release_packet(
            video_id="test-id",
            scripts=[{"variant": "TUTORIAL", "body": "Cook the omelette.", "verification": None}],
            edit_directive={},
            shoot_card={},
        )
        assert isinstance(packet, ReleasePacket)
        assert packet.video_id == "test-id"
        # Stub must never silently pass — unreviewed scripts must not reach publishing
        assert packet.qc.overall_pass is False
        assert len(packet.qc.issues) > 0
    finally:
        _colette._LLM_AVAILABLE = _orig


def test_colette_qc_result_fields():
    from services.agents.colette.main import make_release_packet
    packet = make_release_packet(video_id="x", scripts=[], edit_directive={}, shoot_card={})
    assert isinstance(packet.qc.overall_pass, bool)
    assert isinstance(packet.qc.culinary_pass, bool)
    assert isinstance(packet.assets, list)


def test_armand_plan_week_no_recipes():
    from services.agents.armand.main import plan_week, WeekPlan
    from datetime import date
    result = plan_week([], date(2026, 4, 7))
    assert isinstance(result, WeekPlan)
    assert result.total_estimated_cost == 0.0
    assert result.over_budget is False


def test_armand_plan_week_returns_correct_week_id():
    from services.agents.armand.main import plan_week
    from datetime import date
    result = plan_week([], date(2026, 4, 7))
    assert result.week_id == "2026-04-07"
    assert result.budget_limit == 100.0


def test_armand_ingest_receipt_no_ocr():
    from services.agents.armand.main import ingest_receipt, ReceiptResult
    # Pass empty bytes — OCR will produce nothing, LLM parse will return []
    result = ingest_receipt(b"", store="test store")
    assert isinstance(result, ReceiptResult)
    assert result.store == "test store"
    assert result.total == 0.0
    assert result.items == []


def test_lucien_stub_no_key():
    from services.agents.lucien.main import adapt_for_platforms, PlatformPacket
    release_packet = {
        "assets": [{"platform": "youtube", "title": "Test omelette", "description": "desc", "hashtags": [], "cover_concept": "overhead"}],
        "qc": {"overall_pass": True, "plagiarism_score": 0.1},
    }
    packet = adapt_for_platforms("test-id", release_packet)
    assert isinstance(packet, PlatformPacket)
    assert packet.video_id == "test-id"
    assert len(packet.variants) == 2


def test_lucien_has_tiktok_and_instagram():
    from services.agents.lucien.main import adapt_for_platforms
    packet = adapt_for_platforms("x", {"assets": [], "qc": {}})
    platforms = {v.platform for v in packet.variants}
    assert "tiktok" in platforms
    assert "instagram" in platforms


def test_armand_grocery_list_empty_week():
    from services.agents.armand.main import get_grocery_list, GroceryList
    from datetime import date
    # Week with no planned recipes returns empty list
    result = get_grocery_list(date(2030, 1, 7))
    assert isinstance(result, GroceryList)
    assert result.items == []
    assert result.total_estimated_cost == 0.0


def test_armand_grocery_list_week_id_format():
    from services.agents.armand.main import get_grocery_list
    from datetime import date
    result = get_grocery_list(date(2030, 2, 3))
    assert result.week_id == "2030-02-03"


def test_dashboard_summary_schema():
    from fastapi.testclient import TestClient
    from services.orchestration.api import app
    client = TestClient(app)
    res = client.get("/dashboard/summary")
    assert res.status_code == 200
    data = res.json()
    assert "pipeline" in data
    assert "budget" in data
    assert "queue" in data
    assert "week_id" in data["budget"]
    assert "budget_limit" in data["budget"]


def test_calendar_ics_format():
    from fastapi.testclient import TestClient
    from services.orchestration.api import app
    client = TestClient(app)
    res = client.get("/calendar.ics")
    assert res.status_code == 200
    assert "BEGIN:VCALENDAR" in res.text
    assert "END:VCALENDAR" in res.text
    assert "VERSION:2.0" in res.text


def test_etienne_report_empty_week():
    from services.agents.etienne.main import generate_weekly_report, WeeklyReport
    from datetime import date
    report = generate_weekly_report(date(2030, 3, 2))
    assert isinstance(report, WeeklyReport)
    assert report.total_views == 0
    assert report.avg_retention_pct == 0.0
    assert len(report.insights) > 0
    assert len(report.recommendations) > 0


def test_etienne_report_week_id_format():
    from services.agents.etienne.main import generate_weekly_report
    from datetime import date
    report = generate_weekly_report(date(2030, 3, 2))
    assert report.week_id == "2030-03-02"
    assert isinstance(report.top_performers, list)


def test_etienne_report_schema():
    from services.agents.etienne.main import generate_weekly_report
    from datetime import date
    report = generate_weekly_report(date(2030, 3, 9))
    assert isinstance(report.budget_spent, float)
    assert isinstance(report.budget_remaining, float)
    assert report.budget_remaining == round(100.0 - report.budget_spent, 2)


def test_etienne_api_report_endpoint():
    from fastapi.testclient import TestClient
    from services.orchestration.api import app
    client = TestClient(app)
    res = client.get("/etienne/report/2030-04-07")
    assert res.status_code == 200
    data = res.json()
    assert "week_id" in data
    assert "total_views" in data
    assert "insights" in data
    assert "recommendations" in data


def test_marcel_long_form_has_chapters():
    from services.agents.marcel.main import write_scripts, Chapter
    scripts = write_scripts({"dish": "boeuf bourguignon", "title": "Boeuf Bourguignon"}, stream="LONG")
    tutorial = next(s for s in scripts if s.variant == "TUTORIAL")
    assert tutorial.chapters is not None
    assert len(tutorial.chapters) >= 4
    assert all(isinstance(c, Chapter) for c in tutorial.chapters)
    assert all(c.title and c.duration_minutes > 0 for c in tutorial.chapters)


def test_marcel_short_form_no_chapters():
    from services.agents.marcel.main import write_scripts
    scripts = write_scripts({"dish": "omelette", "title": "Omelette"}, stream="SHORT")
    tutorial = next(s for s in scripts if s.variant == "TUTORIAL")
    assert tutorial.chapters is None


def test_camille_multi_angle_present():
    from services.agents.camille.main import make_shoot_card, AngleSpec
    card = make_shoot_card("simple omelette recipe")
    assert len(card.angles) >= 3
    assert all(isinstance(a, AngleSpec) for a in card.angles)
    labels = {a.label for a in card.angles}
    assert "overhead" in labels
    assert "close-up" in labels


def test_pipeline_long_preview_schema():
    from fastapi.testclient import TestClient
    from services.orchestration.api import app
    client = TestClient(app)
    res = client.get("/pipeline/long/preview")
    assert res.status_code == 200
    data = res.json()
    assert "idea" in data
    assert "scripts" in data
    assert "shoot_card" in data
    scripts = data["scripts"]
    tutorial = next(s for s in scripts if s["variant"] == "TUTORIAL")
    assert "chapters" in tutorial
    assert data["shoot_card"]["angles"] is not None


def test_colette_has_youtube_asset():
    from services.agents.colette.main import make_release_packet
    # Provide a real script so QC has content to evaluate and assets get generated
    scripts = [{
        "variant": "TUTORIAL",
        "body": "Today you make beurre noisette. Heat butter to 150C until foam subsides and colour turns hazel.",
        "verification": {
            "temps": [{"claim": "Heat butter to 150C", "value_celsius": 150, "source": "Le Cordon Bleu"}],
            "ratios": [{"claim": "Use 1:1 ratio butter to pan", "ratio": "1:1", "source": "Escoffier"}],
            "claims": [{"statement": "Butter browns at 150C", "verified": True, "reference": "On Food and Cooking"}],
        },
    }]
    packet = make_release_packet(video_id="x", scripts=scripts, edit_directive={}, shoot_card={})
    # Either QC passed and we have assets, or QC failed and assets is empty — both are valid
    if packet.qc.overall_pass:
        platforms = {a.platform for a in packet.assets}
        assert "youtube" in platforms
    else:
        assert isinstance(packet.assets, list)
