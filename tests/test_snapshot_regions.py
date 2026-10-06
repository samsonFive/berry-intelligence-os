import json

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import map_regions, map_workspace
from app.services.global_explorer import IntelligenceQuery, snapshot_model
from app.services.report_builder import pdf_export
from tests.test_map_workspace import ENTITIES, RECORDS, REL, FACTS, BERRIES, payload


def options(tmp_path, params=None, authoring=True):
    return map_workspace.snapshot_regions(IntelligenceQuery(("geography-peru",), berry_ids=("berry-blueberry",)),
        ENTITIES, REL, RECORDS, {"entity_tiers": {"company-grower": "tier1"}, "entity_favorites": {"company-grower": True}},
        params or {}, inbox_dir=tmp_path, authoring=authoring)


def test_snapshot_locations_are_explicit_shared_scoped_and_do_not_write(tmp_path):
    saved = map_regions.edit(tmp_path, payload=payload(source_id=RECORDS[0]["id"], notes="PRIVATE TRIAL QUALIFICATION"), entities=ENTITIES, relationships=REL, records=RECORDS)
    before = (tmp_path / map_regions.FILENAME).read_bytes()
    rows = options(tmp_path, {"layer": "varieties", "company": "company-grower", "tier": "tier1", "favorites": "1", "region_status": "proposed", "activity": "Trial", "region_asof": "2026-01-01"})
    assert [row["id"] for row in rows] == [saved["id"]]  # Unknown effective date is not fabricated.
    assert rows[0]["source_date"] == "2026-08-01" and rows[0]["observed_on"] == ""
    query = IntelligenceQuery(("geography-peru",), berry_ids=("berry-blueberry",))
    default = snapshot_model(query, RECORDS, ENTITIES, REL, BERRIES, ["locations"], facts=FACTS, location_options=rows)
    assert not default["selected_location_rows"] and not default["has_private_locations"]
    selected = snapshot_model(query, RECORDS, ENTITIES, REL, BERRIES, ["locations"], facts=FACTS, location_options=rows, location_ids=[saved["id"]])
    assert selected["selected_location_rows"][0]["notes"] == "PRIVATE TRIAL QUALIFICATION" and selected["has_private_locations"]
    assert not selected["packet"]["recent_developments"] and not selected["coverage"]["counts"]
    assert pdf_export._cutoff_date(selected["packet"]) == "2026-08-01"
    assert selected["packet"]["source_trace"][0]["source_url"] == RECORDS[0]["source_url"]
    omitted = snapshot_model(query, RECORDS, ENTITIES, REL, BERRIES, ["overview"], facts=FACTS, location_options=rows, location_ids=[saved["id"]])
    assert not omitted["selected_location_rows"] and not omitted["has_private_locations"]
    assert not options(tmp_path, {"layer": "varieties", "region_status": "active"})
    assert not options(tmp_path, {"layer": "varieties", "company": "company-other"})
    assert not options(tmp_path, {"layer": "varieties", "tier": "tier2"})
    assert (tmp_path / map_regions.FILENAME).read_bytes() == before


def test_public_options_never_read_private_and_stale_selection_cannot_export(tmp_path, monkeypatch):
    monkeypatch.setattr(map_regions, "load", lambda *_: pytest.fail("Readonly snapshots must not read private annotations"))
    rows = options(tmp_path, authoring=False)
    assert [row["id"] for row in rows] == [REL[0]["id"]] and rows[0]["source_date"] == RECORDS[0]["published_date"]
    with pytest.raises(ValueError, match="no longer available"):
        snapshot_model(IntelligenceQuery(), RECORDS, ENTITIES, REL, BERRIES, ["locations"], location_options=rows, location_ids=["private-entry"])


@pytest.mark.parametrize("params", [{"layer": "unsupported"}, {"region_status": "reviewed"}, {"activity": "Patent territory"},
                                      {"region_entity": "variety-one", "layer": "companies"}, {"region_asof": "2025"}, {"list": "missing"}])
def test_invalid_snapshot_location_scope_is_rejected(tmp_path, params):
    with pytest.raises(ValueError):
        options(tmp_path, params)


def test_selected_location_pdf_retains_activity_status_dates_notes_and_source_without_internal_ids(tmp_path, monkeypatch):
    saved = map_regions.edit(tmp_path, payload=payload(source_id=RECORDS[0]["id"], notes="Trial only; no commercial scale.\nEffective date unknown. " + "Long limitation. " * 180), entities=ENTITIES, relationships=REL, records=RECORDS)
    rows = options(tmp_path, {"layer": "varieties"})
    model = snapshot_model(IntelligenceQuery(("geography-peru",)), RECORDS, ENTITIES, REL, BERRIES, ["locations"], location_options=rows, location_ids=[saved["id"]])
    text = []
    original = pdf_export.Paragraph
    def paragraph(value, style, **kwargs):
        text.append(value)
        return original(value, style, **kwargs)
    monkeypatch.setattr(pdf_export, "Paragraph", paragraph)
    assert pdf_export.render_report_pdf(model["report"], model["packet"], model["coverage"]).startswith(b"%PDF")
    rendered = "\n".join(text)
    assert all(value in rendered for value in ["Example Blue", "Lima", "Trial", "Proposed", "User annotation", "2026-08-01", "Effective date unknown.", "Long limitation.", RECORDS[0]["source_url"]])
    assert "geography-peru" not in rendered and saved["id"] not in rendered and "variety-one" not in rendered
    assert "Source published" in rendered and "Observed / effective: Unknown" in rendered


def test_browser_routes_keep_selection_and_return_scope_and_mark_private_export(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "entity_index", lambda: ENTITIES)
    monkeypatch.setattr(main, "published_evidence", lambda: RECORDS)
    monkeypatch.setattr(main, "all_relationships", lambda: REL)
    monkeypatch.setattr(main, "all_facts", lambda: FACTS)
    saved = map_regions.edit(tmp_path, payload=payload(notes="PRIVATE SELECTED LIMITATION"), entities=ENTITIES, relationships=REL, records=RECORDS)
    client = TestClient(main.app)
    scope = "?countries=geography-peru&berry=berry-blueberry&layer=varieties&region_entity=variety-one&activity=Trial&region_status=proposed"
    page = client.get("/explorer" + scope)
    assert page.status_code == 200 and 'data-snapshot' in page.text and 'region_entity=variety-one' in page.text
    default = client.get("/explorer/snapshot" + scope + "&sections=locations")
    assert default.status_code == 200 and "PRIVATE SELECTED LIMITATION" not in default.text
    response = client.get("/explorer/snapshot" + scope + "&sections=locations&locations=" + saved["id"])
    assert response.status_code == 200 and "PRIVATE SELECTED LIMITATION" in response.text
    assert 'name="region_entity" value="variety-one"' in response.text and 'name="locations"' in response.text
    captured = []
    render = main.render_report_pdf
    def capture(*args, **kwargs):
        captured.append(kwargs["confidentiality"])
        return render(*args, **kwargs)
    monkeypatch.setattr(main, "render_report_pdf", capture)
    before = (tmp_path / map_regions.FILENAME).read_bytes()
    exported = client.get("/explorer/snapshot.pdf" + scope + "&sections=locations&locations=" + saved["id"])
    assert exported.status_code == 200 and exported.content.startswith(b"%PDF")
    assert captured == ["Internal / Confidential · includes unreviewed annotations"]
    assert (tmp_path / map_regions.FILENAME).read_bytes() == before
    map_regions.edit(tmp_path, payload={"id": saved["id"], "revision": saved["revision"], "action": "remove"}, entities=ENTITIES, relationships=REL, records=RECORDS)
    assert client.get("/explorer/snapshot.pdf" + scope + "&sections=locations&locations=" + saved["id"]).status_code == 422
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    assert client.get("/explorer/snapshot" + scope + "&sections=locations&locations=" + saved["id"]).status_code == 422
