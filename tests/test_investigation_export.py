"""Output completeness, preview-basis conflicts and synthetic isolation."""
from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pypdf import PdfReader
import pytest

from app import investigation_export_routes as routes
from app.services import investigation_api as api
from app.services import investigation_export as export


@pytest.fixture
def export_world(monkeypatch):
    def entity(key, name, kind, **extra):
        return {"id": key, "name": name, "entity_type": kind, "status": "active", "aliases": [],
                "berry_ids": ["berry-blueberry"] if kind in {"company", "variety"} else [], **extra}
    entities = {row["id"]: row for row in [entity("berry-blueberry", "Blueberry", "berry"),
        entity("geography-china", "China", "geography"), entity("company-a", "Alpha Genetics", "company", roles=["breeder"]),
        entity("company-b", "Beta Growers", "company", roles=["grower"]), entity("variety-a", "Azure", "variety")]}
    sources = [{"id": f"source-{index}", "title": f"Retained blueberry development {index}", "status": "published",
                "source_name": "Recorded publisher", "source_url": f"https://example.com/source-{index}",
                "source_type": "trade_press", "published_date": "2026-11-01", "captured_date": "2026-11-02",
                "summary": "Recorded source summary; source approval is not blanket claim approval.",
                "berry_ids": ["berry-blueberry"], "entity_ids": ["company-a", "geography-china"],
                "article": {"text": "UNSELECTED BODY MUST NOT APPEAR"}} for index in range(13)]
    relationships = [{"id": "edge-location", "subject_id": "company-a", "object_id": "geography-china", "predicate": "operates_in",
                      "status": "active", "notes": "Variety validation programme", "evidence_ids": ["source-0"]},
                     {"id": "edge-breeder", "subject_id": "company-a", "object_id": "variety-a", "predicate": "develops",
                      "status": "active", "notes": "Recorded breeder relationship", "evidence_ids": ["source-1"]},
                     {"id": "edge-license", "subject_id": "company-b", "object_id": "variety-a", "predicate": "licenses",
                      "status": "disputed", "notes": "License review remains required", "evidence_ids": ["source-2"]}]
    world = api.World(SimpleNamespace(all_facts=lambda: [], all_signals=lambda: [], all_assessments=lambda: []),
                      entities, relationships, sources, {}, _news={row["id"]: row for row in sources})

    def developments(world, context, bundle, *, all_cards=False):
        cards = [{"id": row["id"], "headline": row["title"], "deck": row["summary"], "source_name": row["source_name"],
                  "published_at": row["published_date"], "source_reviewed": True, "trusted": False} for row in world.evidence]
        return {"heading": "Developments across this scope", "basis": "scope", "cards": cards if all_cards else cards[:6],
                "matching_count": len(cards), "sources": [api.source_metadata(row) for row in world.evidence]}
    monkeypatch.setattr(api, "developments_data", developments)
    return world


def selectors(**extra):
    return {"ctx_v": "1", "berry": "berry-blueberry", "countries": "geography-china", **extra}


def test_preview_is_complete_and_selector_source_body_safe(export_world):
    before = deepcopy(export_world.evidence)
    result = export.preview(export_world, selectors(), ["relationships", "portfolio", "developments"])
    assert next(row for row in result["sections"] if row["id"] == "developments")["row_count"] == 13
    assert {source["id"] for source in result["sources"]} == {f"source-{index}" for index in range(13)}
    assert "UNSELECTED BODY" not in str(result)
    assert export_world.evidence == before
    assert len(result["content_hash"]) == 64


def test_changed_record_or_output_choice_rejects_stale_preview(export_world):
    selected = ["relationships"]
    original = export.preview(export_world, selectors(), selected)["content_hash"]
    export_world.relationships[0]["notes"] = "Registered office; growing is not established"
    with pytest.raises(export.ContentChangedError, match="changed after preview"):
        export.pdf(export_world, selectors(), selected, False, original)
    fresh = export.preview(export_world, selectors(), selected)["content_hash"]
    assert fresh != original
    with pytest.raises(export.ContentChangedError):
        export.pdf(export_world, selectors(), ["relationships", "geography"], False, fresh)


def test_changed_source_metadata_rejects_stale_preview(export_world):
    selected = ["relationships"]
    digest = export.preview(export_world, selectors(), selected)["content_hash"]
    export_world.evidence[0]["published_date"] = "2026-11-03"
    export_world.evidence[0]["title"] = "Corrected source title and publication date"
    with pytest.raises(export.ContentChangedError, match="changed after preview"):
        export.pdf(export_world, selectors(), selected, False, digest)


def test_sensory_lens_never_includes_demo_without_explicit_annex(export_world, monkeypatch):
    def forbidden():
        raise AssertionError("Ordinary output must not load the synthetic fixture")
    monkeypatch.setattr(export, "_load_demo", forbidden)
    result = export.build_payload(export_world, selectors(lens="sensory"), ["relationships"], False)
    assert "demo_annex" not in result and "demo-specimen" not in str(result)


def test_pdf_includes_tail_rows_sources_and_distinct_dates(export_world):
    selected = ["relationships", "portfolio", "geography", "comparison", "developments"]
    context = selectors(cohort_companies="company-a,company-b")
    preview = export.preview(export_world, context, selected)
    data, digest = export.pdf(export_world, context, selected, False, preview["content_hash"])
    reader = PdfReader(BytesIO(data))
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert data.startswith(b"%PDF-") and digest == preview["content_hash"]
    assert "Retained blueberry development 12" in text and "source-12" in text
    assert "Variety validation programme" in text and "Disputed / review required" in text
    assert "2026-11-01" in text and "2026-11-02" in text
    assert "UNSELECTED BODY" not in text and "demo-specimen" not in text
    assert len(reader.pages) > 1


def test_explicit_demo_annex_is_labeled_and_hash_bound(export_world):
    selected = ["readout"]
    ordinary = export.preview(export_world, selectors(), selected)
    with_demo = export.preview(export_world, selectors(), selected, True)
    assert ordinary["content_hash"] != with_demo["content_hash"]
    assert with_demo["synthetic_annex"]["metric"]["id"] == "overall_liking"
    data, _ = export.pdf(export_world, selectors(), selected, True, with_demo["content_hash"])
    text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(data)).pages)
    assert "SYNTHETIC ANNEX / FICTITIOUS SPECIMENS" in text
    assert "Synthetic overall liking / 1-9" in text and "Specimen Amber" in text


def test_demo_annex_exports_only_the_saved_selected_specimens(export_world):
    specimens = export._load_demo()["specimens"]
    chosen = [specimens[0], specimens[-1]]
    context = selectors(demo_specimens=",".join(row["id"] for row in chosen))
    preview = export.preview(export_world, context, ["readout"], True)
    assert preview["synthetic_annex"]["specimen_count"] == 2
    assert preview["synthetic_annex"]["specimen_labels"] == [row["label"] for row in chosen]
    data, _ = export.pdf(export_world, context, ["readout"], True, preview["content_hash"])
    text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(data)).pages)
    assert all(row["label"] in text for row in chosen)
    assert specimens[1]["label"] not in text


def test_unavailable_demo_selection_never_silently_becomes_all(export_world):
    context = selectors(demo_specimens="demo-specimen-unavailable-rehearsal")
    with pytest.raises(ValueError, match="selected demo specimens are unavailable"):
        export.preview(export_world, context, ["readout"], True)
    ordinary = export.preview(export_world, context, ["readout"], False)
    assert ordinary["synthetic_annex"] is None and ordinary["include_demo"] is False


@pytest.mark.parametrize("sections", [[], ["readout", "readout"], ["unknown"], ["sensory"]])
def test_unsupported_or_duplicate_sections_fail_without_partial_output(export_world, sections):
    with pytest.raises(ValueError, match="supported export sections"):
        export.preview(export_world, selectors(), sections)


def test_export_rejects_unknown_context_and_missing_preview(export_world):
    with pytest.raises(ValueError, match="only supported"):
        export.preview(export_world, selectors(private_notes="must not enter output"), ["readout"])
    with pytest.raises(ValueError, match="Preview the exact"):
        export.pdf(export_world, selectors(), ["readout"], False, None)


def test_preview_declares_actual_module_geography_and_complete_section_sources(export_world):
    result = export.preview(export_world, selectors(geo_basis="source_geography"), ["geography", "developments"])
    assert result["scope"]["geographic_basis"] == "source_geography"
    assert result["scope"]["standing_geographic_basis"] == "company_connections"
    assert result["scope"]["developments_geographic_basis"] == "source_geography"
    news = next(section for section in result["sections"] if section["id"] == "developments")
    assert len(news["source_ids"]) == 13


def test_related_story_context_survives_export_without_relabeling_stored_link_unreviewed(export_world, monkeypatch):
    original = api.developments_data
    def with_context(*args, **kwargs):
        model = original(*args, **kwargs)
        model["cards"][0]["scope_match"] = {"kind": "related_context", "primary_label": "Alpha Genetics",
            "subject_labels": ["Beta Growers"], "basis": "recorded_link"}
        return model
    monkeypatch.setattr(api, "developments_data", with_context)
    context = selectors(lens="comparison", cohort_companies="company-a,company-b")
    preview = export.preview(export_world, context, ["developments"])
    data, _ = export.pdf(export_world, context, ["developments"], False, preview["content_hash"])
    text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(data)).pages)
    assert "About Alpha Genetics / Context for Beta Growers" in text
    assert "Company link not reviewed" not in text


def test_route_preview_pdf_conflict_and_private_gate(export_world, monkeypatch):
    application = FastAPI()
    routes.register(application)
    monkeypatch.setattr(routes, "_private", lambda: None)
    monkeypatch.setattr(api, "load_world", lambda: export_world)
    body = {"context": selectors(), "section_ids": ["relationships"], "include_demo": False}
    with TestClient(application) as client:
        preview = client.post("/api/investigations/v1/export/preview", json=body)
        assert preview.status_code == 200 and preview.headers["cache-control"] == "private, no-store"
        body["expected_content_hash"] = preview.json()["content_hash"]
        response = client.post("/api/investigations/v1/export/pdf", json=body)
        assert response.status_code == 200 and response.headers["content-type"] == "application/pdf"
        export_world.relationships[0]["notes"] = "Updated authorized basis"
        assert client.post("/api/investigations/v1/export/pdf", json=body).status_code == 409
        def deny():
            raise HTTPException(403, "Private workspace required")
        monkeypatch.setattr(routes, "_private", deny)
        assert client.post("/api/investigations/v1/export/preview", json=body).status_code == 403
