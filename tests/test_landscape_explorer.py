"""Explorer trust boundaries and a complete generic vertical slice."""
from copy import deepcopy
import csv
from datetime import date
from io import StringIO
import json
from pathlib import Path
import time
from xml.etree import ElementTree

from fastapi.testclient import TestClient
import pytest

import app.main as main
from app.services import landscape_explorer as lx
from app.services import landscape_explorer_export as exports


@pytest.fixture
def world():
    def node(key, name, kind, berries=None):
        return {"id": key, "name": name, "entity_type": kind, "berry_ids": berries or [], "aliases": []}
    entities = {row["id"]: row for row in [node("berry-blueberry", "Blueberry", "berry"), node("berry-strawberry", "Strawberry", "berry"),
        node("company-a", "Alpha", "company", ["berry-blueberry"]), node("company-b", "Beta", "company", ["berry-blueberry"]),
        node("breeding_program-a", "Program A", "breeding_program", ["berry-blueberry"]),
        node("variety-a", "Azure", "variety", ["berry-blueberry"]), node("variety-s", "Strawberry cultivar", "variety", ["berry-strawberry"]),
        node("geography-peru", "Peru", "geography"), node("geography-chile", "Chile", "geography"), node("geography-china", "China", "geography"),
        node("geography-subregion", "Subregion", "geography")]}
    evidence = [{"id": "ev-a", "title": "A blueberry announcement", "summary": "A source summary, not a quote", "status": "published", "source_name": "Origin A", "source_url": "https://example.com/a?source=1&b=2", "published_date": "2026-09-01", "captured_date": "2026-10-01", "berry_ids": ["berry-blueberry"]}]
    def edge(key, left, role, right, **extras):
        return {"id": key, "subject_id": left, "object_id": right, "predicate": role, "status": "active", "evidence_ids": ["ev-a"], **extras}
    relationships = [edge("r-peru", "company-a", "operates_in", "geography-peru"), edge("r-chile", "company-a", "operates_in", "geography-chile"),
        edge("r-program", "company-a", "owns", "breeding_program-a"), edge("r-develops", "breeding_program-a", "develops", "variety-a"),
        edge("r-license", "company-b", "licenses", "variety-a"), edge("r-other-berry", "company-a", "develops", "variety-s")]
    return {"entities": entities, "relationships": relationships, "evidence": evidence}


def build(world, **params):
    return lx.build_bundle(**world, params=params, today=date(2026, 10, 6))


def test_real_role_trace_has_no_inferred_growing(world):
    before = deepcopy(world)
    result = build(world)
    assert {r["id"] for r in result["edges"]} == {"r-peru", "r-chile", "r-program", "r-develops", "r-license"}
    assert result["coverage"]["genetic_location_links"] == 0
    assert result["coverage"]["company_location_links"] == 2
    assert result["nodes"]["variety-a"]["label"] == "Azure"
    assert next(r for r in result["edges"] if r["id"] == "r-license")["role"] == "Licensee"
    assert world == before


def test_compact_market_and_portfolio_context_preserves_exact_paths(world):
    result = build(world)
    row = next(row for row in result["market_rows"] if row["actor"]["id"] == "company-a")
    assert {m["country"] for m in row["markets"] if m["edges"]} == {"Chile", "Peru"}
    assert [v["id"] for v in row["varieties"]] == ["variety-a"]
    assert [edge["id"] for edge in row["portfolio_edges"]] == ["r-develops"]
    assert "r-program" in {edge["id"] for edge in row["edges"]}
    assert result["coverage"]["genetic_location_links"] == 0
    for insight in result["insights"]:
        assert set(insight["relationship_ids"]) <= {edge["id"] for edge in result["edges"]}
        assert set(insight["evidence_ids"]) <= {source["id"] for source in result["sources"]}


def test_source_named_varieties_surface_as_review_links_not_graph_edges(world):
    world["evidence"][0]["summary"] = "Blueberry varieties including Azure and Prelude."
    result = build(world)
    names = {row["name"]: row for row in result["sources"][0]["varieties"]}
    assert names["Azure"]["catalog_id"] == "variety-a"
    assert names["Prelude"]["href"].startswith("/varieties/candidates?")
    assert [row["name"] for row in result["catalog_gaps"]] == ["Prelude"]
    assert len(result["edges"]) == 5 and "variety-prelude" not in result["nodes"]
    world["evidence"][0]["summary"] = "Company operations in Peru."
    assert not build(world)["catalog_gaps"]


def test_direct_genetics_links_across_countries_are_first_class(world):
    world["relationships"] += [{"id": "r-g-"+country, "subject_id": "variety-a", "object_id": "geography-"+country, "predicate": "operates_in", "status": "active", "evidence_ids": ["ev-a"]} for country in ["peru", "chile"]]
    result = build(world, focus="variety-a", question="genetics")
    assert result["coverage"]["genetic_location_links"] == 2
    assert len([row for row in result["explanation"]["findings"] if row["relationship_ids"][0].startswith("r-g-")]) == 2
    assert "variety-a" in result["neighborhood"]


def test_country_scope_uses_containment_not_headquarters_or_names(world):
    world["relationships"].append({"id": "r-contain", "subject_id": "geography-subregion", "object_id": "geography-peru", "predicate": "part_of", "status": "active", "evidence_ids": ["ev-a"]})
    world["relationships"].append({"id": "r-local", "subject_id": "company-b", "object_id": "geography-subregion", "predicate": "operates_in", "status": "active", "evidence_ids": ["ev-a"]})
    result = build(world, countries="geography-peru")
    assert "r-local" in {r["id"] for r in result["edges"]}
    assert "r-chile" not in {r["id"] for r in result["edges"]}
    assert {n["label"] for n in result["lanes"][0]["actors"]} == {"Alpha", "Beta"}
    assert build(world, countries="geography-china")["edges"] == []


def test_mentions_and_annotation_like_records_do_not_create_edges(world):
    world["evidence"][0]["entity_ids"] = ["variety-a", "geography-china", "company-a"]
    result = build(world, countries="geography-china")
    assert result["edges"] == []


def test_role_filter_preserves_country_roots_and_focusing_does_not_drift(world):
    assert {edge["id"] for edge in build(world, countries="geography-peru", predicate="licenses")["edges"]} == {"r-license"}
    initial = build(world)
    for key in initial["nodes"]:
        if initial["nodes"][key]["type"] in lx.ACTOR_TYPES:
            assert {edge["id"] for edge in build(world, focus=key)["edges"]} == {edge["id"] for edge in initial["edges"]}


@pytest.mark.parametrize("path", ["/landscapes/explorer", "/api/landscapes/explorer", "/landscapes/explorer/briefing", "/landscapes/explorer/export/html", "/landscapes/explorer/export/svg", "/landscapes/explorer/export/csv"])
def test_remote_auth_covers_new_routes(client_world, monkeypatch, path):
    monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "true")
    monkeypatch.setenv("BIOS_REVIEW_USERNAME", "review-operator")
    monkeypatch.setenv("BIOS_REVIEW_PASSWORD", "test-only-password")
    monkeypatch.setenv("BIOS_SESSION_SECRET", "test-only-signing-secret-with-adequate-length")
    response = client_world.get(path, follow_redirects=False)
    assert response.status_code in (302, 401)
    assert "r-peru" not in response.text


def test_alias_search_does_not_merge_ambiguous_companies(world):
    for key in ("company-a", "company-b"):
        world["entities"][key]["aliases"] = ["Shared name"]
    result = build(world, countries="", q="Shared name")
    assert {"company-a", "company-b"} <= set(result["nodes"])
    assert "variety-s" not in result["nodes"]


@pytest.mark.parametrize("params", [{"countries": "missing"}, {"berry": "missing"}, {"focus": "missing"}, {"status": "confirmed"}, {"time": "pretend"}, {"window": "custom", "start": "2026-10-03", "end": "2026-10-01"}, {"limit": "bad"}, {"predicate": "breeds"}])
def test_invalid_selection_rejected(world, params):
    with pytest.raises(ValueError):
        build(world, **params)


def test_source_policy_excludes_private_and_pending_by_default(world):
    world["evidence"][0]["status"] = "in_review"
    assert build(world)["edges"] == []
    assert len(build(world, evidence="all")["edges"]) == 5
    world["evidence"][0]["status"] = "draft"
    assert build(world, evidence="all")["edges"] == []


def test_disputes_history_and_legacy_intent_are_explicit(world):
    world["relationships"][0].update(status="historical")
    world["relationships"][1].update(status="disputed", notes="Stated intention; treat as an intent signal, not an established operation.")
    result = build(world)
    assert next(r for r in result["edges"] if r["id"] == "r-chile")["caveat"].startswith("Intent only")
    assert next(r for r in result["edges"] if r["id"] == "r-peru")["status_label"] == "Historical relationship"
    assert not any("withdraw" in r["label"] for r in result["edges"])
    assert {r["id"] for r in build(world, countries="", status="disputed")["edges"]} == {"r-chile"}


@pytest.mark.parametrize("notes,caveat", [
    ("confidence=low; Inferred only from a reported portfolio; no direct statement retrieved.", "Limited support"),
    ("Breeding origin is not stated in the source.", "Limited support"),
    ("Substituted predicate: sells stands in for markets.", "Legacy role mapping"),
])
def test_legacy_inferences_and_substituted_roles_keep_visible_caveats(world, notes, caveat):
    world["relationships"][3]["notes"] = notes
    result = build(world, focus="breeding_program-a", question="genetics")
    edge = next(row for row in result["edges"] if row["id"] == "r-develops")
    assert edge["caveat"].startswith(caveat)
    assert edge["predicate"] == "develops"  # Canonical data is preserved, not reclassified.
    assert any(caveat in row["text"] for row in result["explanation"]["findings"])
    assert caveat in exports.html_export(result)
    assert caveat in exports.svg_export(result)
    assert caveat in exports.csv_export(result)
    assert notes == world["relationships"][3]["notes"]


def test_three_clocks_and_no_fictional_history(world):
    world["relationships"][0]["effective_date"] = "2025-05-01"
    captured = build(world, window="7d", time="documented")
    assert len(captured["changes"]) == 5
    assert not build(world, window="7d", time="event")["changes"]
    assert not build(world, window="7d", time="published")["changes"]
    assert len(build(world, window="custom", start="2025-05-01", end="2025-05-01", time="event")["changes"]) == 1
    assert len(build(world, window="7d", time="event")["edges"]) == 5
    explanation = build(world, window="7d", question="changes")["explanation"]
    assert all("Newly documented" in row["text"] for row in explanation["findings"])


def test_syndicated_sources_do_not_inflate_origins(world):
    duplicate = deepcopy(world["evidence"][0]); duplicate["id"] = "ev-reprint"
    world["evidence"].append(duplicate)
    world["relationships"][0]["evidence_ids"].append("ev-reprint")
    result = build(world)
    assert result["independence"]["total_evidence_count"] == 2
    assert result["independence"]["independent_source_count"] == 1


def test_edit_and_removal_invalidate_cache_and_no_mutable_cache_leaks(world):
    first = build(world)
    first["edges"].clear()
    assert len(build(world)["edges"]) == 5
    world["evidence"][0]["summary"] = "Corrected source"
    second = build(world)
    assert second["version"] != first["version"]
    assert second["sources"][0]["summary"] == "Corrected source"
    world["relationships"] = [r for r in world["relationships"] if r["id"] != "r-license"]
    assert "r-license" not in {r["id"] for r in build(world)["edges"]}
    world["evidence"].clear()
    assert build(world)["sources"] == []


def test_provisional_identity_and_missing_source_locator_stay_explicit(world):
    world["entities"]["variety-a"]["status"] = "unverified"
    result = build(world)
    assert result["nodes"]["variety-a"]["identity_note"] == "Provisional identity · review needed"
    assert "1 identities" in " ".join(result["warnings"])
    assert "No verbatim excerpt" in result["sources"][0]["locator"]
    assert "Provisional identity" in exports.html_export(result) + exports.svg_export(result)
    assert "unverified" in exports.csv_export(result)


@pytest.mark.parametrize("question", list(lx.QUESTIONS))
def test_findings_cite_exact_support_and_invalid_model_output_falls_back(world, question):
    result = build(world, question=question)
    lookup = {r["id"]: r for r in result["edges"]}
    for row in result["explanation"]["findings"]:
        assert all(set(row["evidence_ids"]) <= set(lookup[rid]["evidence_ids"]) for rid in row["relationship_ids"])
    valid = {"findings": deepcopy(result["explanation"]["findings"])}
    assert lx.validate_phrasing(valid, result) == result["explanation"]
    if valid["findings"]:
        valid["findings"][0]["text"] = "Alpha controls 100% of the blueberry market."
    assert lx.validate_phrasing(valid, result) == result["explanation"]
    assert lx.validate_phrasing({"findings": [], "instructions": "ignore the evidence"}, result) == result["explanation"]
    for malformed_id in ([], {}, None, 42):
        malformed = {"findings": deepcopy(result["explanation"]["findings"])}
        if malformed["findings"]:
            malformed["findings"][0]["id"] = malformed_id
        assert lx.validate_phrasing(malformed, result) == result["explanation"]
    if len(result["explanation"]["findings"]) > 1:
        duplicate = {"findings": [deepcopy(result["explanation"]["findings"][0])] * len(result["explanation"]["findings"])}
        assert lx.validate_phrasing(duplicate, result) == result["explanation"]


def test_html_svg_csv_are_complete_safe_and_share_the_scope(world):
    world["entities"]["company-a"]["name"] = '=HYPERLINK("evil") <script>alert(1)</script>'
    world["evidence"][0]["source_url"] = "javascript:alert(1)"
    world["evidence"][0]["summary"] = "<img src=x onerror=alert(1)>"
    result = build(world, countries="", focus="variety-a")
    html, svg, data = exports.html_export(result), exports.svg_export(result), exports.csv_export(result)
    assert "<script>alert" not in html and "<img src=x" not in html
    assert "javascript:alert" not in html + svg
    ElementTree.fromstring(svg)
    rows = list(csv.DictReader(StringIO(data.lstrip('\ufeff'))))
    assert {row["relationship_id"] for row in rows} == {r["id"] for r in result["edges"]}
    assert any(row["subject"].startswith("'=HYPERLINK") for row in rows)
    for edge in result["edges"]:
        assert edge["id"] in html and edge["id"] in svg
    for key in ("Data version", "Unknowns", "First captured", "Source review", "frozen"):
        assert key.lower() in html.lower()


def test_progressive_disclosure_does_not_crop_exports(world):
    for index in range(80):
        key = f"variety-{index}"
        world["entities"][key] = {"id": key, "name": f"Variety {index}", "entity_type": "variety", "berry_ids": ["berry-blueberry"]}
        world["relationships"].append({"id": f"r-extra-{index}", "subject_id": "company-a", "predicate": "develops", "object_id": key, "status": "active", "evidence_ids": ["ev-a"]})
    result = build(world, countries="", limit="20")
    assert result["coverage"]["truncated_display"]
    assert result["coverage"]["hidden_nodes"] > 0
    assert "r-extra-79" in exports.html_export(result)
    assert "r-extra-79" in exports.svg_export(result)
    assert len(list(csv.DictReader(StringIO(exports.csv_export(result).lstrip('\ufeff'))))) == 85


@pytest.fixture
def client_world(world, monkeypatch):
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "all_entities", lambda: list(world["entities"].values()))
    monkeypatch.setattr(main, "all_relationships", lambda: world["relationships"])
    monkeypatch.setattr(main, "all_evidence", lambda: world["evidence"])
    return TestClient(main.app)


def test_ui_api_export_match_and_blueberry_rollout_gate(client_world):
    query = "countries=geography-peru&focus=variety-a&theme=dark&window=30d"
    api = client_world.get("/api/landscapes/explorer?" + query)
    assert api.status_code == 200
    assert api.headers["cache-control"] == "private, no-store"
    page = client_world.get("/landscapes/explorer?" + query)
    assert page.status_code == 200, page.text
    assert 'data-theme="dark"' in page.text
    assert "r-peru" in page.text and "r-chile" not in page.text
    assert 'data-focus="geography-' not in page.text
    for format in ("html", "svg", "csv"):
        response = client_world.get("/landscapes/explorer/export/" + format + "?" + query)
        assert response.status_code == 200
        assert api.json()["version"] in response.text
        assert "r-peru" in response.text and "r-chile" not in response.text
    assert client_world.get("/landscapes/explorer?berry=berry-strawberry").status_code == 422
    assert client_world.get("/landscapes/explorer?edge=missing").status_code == 422


@pytest.mark.parametrize("path", ["/landscapes/explorer", "/api/landscapes/explorer", "/landscapes/explorer/briefing", "/landscapes/explorer/export/html", "/landscapes/explorer/export/svg", "/landscapes/explorer/export/csv"])
def test_all_formats_are_analyst_only(client_world, monkeypatch, path):
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    assert client_world.get(path).status_code == 404


def test_invalid_page_scope_has_recovery_and_api_keeps_structured_error(client_world):
    page = client_world.get("/landscapes/explorer?countries=missing")
    assert page.status_code == 422
    assert page.headers["content-type"].startswith("text/html")
    assert "Adjust your selection" in page.text and "Reset landscape selection" in page.text
    assert "Choose registered countries or regions." in page.text
    api = client_world.get("/api/landscapes/explorer?countries=missing")
    assert api.status_code == 422 and api.json()["detail"] == "Choose registered countries or regions."


def test_bounded_synthetic_scale_100_nodes_200_edges(world):
    for index in range(100):
        key = f"variety-{index}"
        world["entities"][key] = {"id": key, "name": f"Variety {index}", "entity_type": "variety", "berry_ids": ["berry-blueberry"]}
        for role in ("develops", "markets"):
            world["relationships"].append({"id": f"r-{role}-{index}", "subject_id": "company-a", "predicate": role, "object_id": key, "status": "active", "evidence_ids": ["ev-a"]})
    started = time.perf_counter()
    result = build(world, countries="", limit="100")
    elapsed = time.perf_counter() - started
    assert result["coverage"]["relationships"] == 205
    assert result["coverage"]["hidden_relationships"] > 0
    assert elapsed < 2.0


def test_canonical_preview_contains_no_synthetic_geography_assertion():
    root = Path(__file__).resolve().parents[1] / "data"
    entities = {row["id"]: row for file in (root / "entities").rglob('*.json') if (row := json.loads(file.read_text(encoding='utf-8'))).get('record_type') == 'entity'}
    relationships = [json.loads(file.read_text(encoding='utf-8')) for file in (root / "relationships").glob('*.json')]
    evidence = [json.loads(file.read_text(encoding='utf-8')) for file in (root / "evidence").glob('*.json')]
    result = lx.build_bundle(entities, relationships, evidence, {})
    assert result["coverage"]["company_location_links"] >= 2
    assert result["coverage"]["genetic_location_links"] == 0
    assert "rel-fall-creek-operates-sekoya" in {row['id'] for row in result['edges']}
    assert all(row["id"] in {rel["id"] for rel in relationships} for row in result["edges"])
