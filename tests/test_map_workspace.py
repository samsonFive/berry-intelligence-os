import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import map_regions, map_workspace
from app.services.global_explorer import IntelligenceQuery, snapshot_model

ENTITIES = {
    "geography-peru": {"id": "geography-peru", "name": "Peru", "entity_type": "geography", "attributes": {"iso_3166_1_alpha_2": "PE"}},
    "geography-united-states": {"id": "geography-united-states", "name": "United States", "entity_type": "geography", "attributes": {"iso_3166_1_alpha_2": "US"}},
    "geography-lima": {"id": "geography-lima", "name": "Lima", "entity_type": "geography"},
    "company-grower": {"id": "company-grower", "name": "Acme Berry Grower", "entity_type": "company", "berry_ids": ["berry-blueberry"]},
    "company-other": {"id": "company-other", "name": "Other Grower", "entity_type": "company", "berry_ids": ["berry-strawberry"]},
    "variety-one": {"id": "variety-one", "name": "Example Blue", "entity_type": "variety", "berry_ids": ["berry-blueberry"]},
}
BERRIES = {"berry-blueberry": "Blueberry", "berry-strawberry": "Strawberry"}
RECORDS = [{"id": "ev-berry-news", "status": "published", "source_type": "trade_press", "title": "Acme Berry Grower announces new blueberries",
            "summary": "Blueberry genetics development", "entity_ids": ["company-grower", "variety-one"], "berry_ids": ["berry-blueberry"],
            "geography_ids": ["geography-lima"], "published_date": "2026-08-01", "source_name": "Berry News", "source_url": "https://example.org/blueberries"}]
REL = [{"id": "rel-grower-peru", "subject_id": "company-grower", "object_id": "geography-lima", "predicate": "operates_in", "status": "active", "evidence_ids": ["ev-berry-news"], "notes": "Source limits retained"},
       {"id": "rel-lima-peru", "subject_id": "geography-lima", "object_id": "geography-peru", "predicate": "part_of", "status": "active"},
       {"id": "rel-grower-variety", "subject_id": "company-grower", "object_id": "variety-one", "predicate": "develops", "status": "active"}]
FACTS = [{"id": "fact-news", "status": "active", "statement": "A reviewed statement", "evidence_ids": ["ev-berry-news"]}]


def payload(**overrides):
    return {"entity_id": "variety-one", "geography_id": "geography-lima", "activity": "Trial", "status": "proposed", "notes": "Manual trial note", **overrides}


def test_no_location_inference_from_news_roles_or_commercial_observations():
    rows = map_regions.catalog(ENTITIES, REL, RECORDS)
    assert len(rows) == 1 and rows[0]["activity"] == "Operations (unspecified)"
    records = [{**RECORDS[0], "commercial_observation": {"variety_entity_id": "variety-one", "origin_geography_id": "geography-peru"}}]
    assert not [r for r in map_regions.catalog(ENTITIES, REL, records) if r["kind"] == "variety"]


def test_manual_region_revision_history_removal_and_source_link(tmp_path):
    created = map_regions.edit(tmp_path, payload=payload(source_id="ev-berry-news"), entities=ENTITIES, relationships=REL, records=RECORDS)
    assert created["source_url"] == RECORDS[0]["source_url"]
    edited = map_regions.edit(tmp_path, payload=payload(id=created["id"], revision=1, notes="User correction", status="active"), entities=ENTITIES, relationships=REL, records=RECORDS)
    assert edited["revision"] == 2
    with pytest.raises(ValueError, match="changed in another"):
        map_regions.edit(tmp_path, payload=payload(id=created["id"], revision=1), entities=ENTITIES, relationships=REL, records=RECORDS)
    rows = map_regions.catalog(ENTITIES, REL, RECORDS, map_regions.load(tmp_path))
    row = next(r for r in rows if r["id"] == created["id"])
    assert row["basis"] == "User annotation · not reviewed" and row["notes"] == "User correction"
    map_regions.edit(tmp_path, payload={"id": created["id"], "revision": 2, "action": "remove"}, entities=ENTITIES, relationships=REL, records=RECORDS)
    state = map_regions.load(tmp_path)
    assert len(state["history"]) == 3 and state["history"][1]["before"]["notes"] == "Manual trial note"
    assert not [r for r in map_regions.catalog(ENTITIES, REL, RECORDS, state) if r["id"] == created["id"]]
    assert REL[0]["notes"] == "Source limits retained"  # canonical objects untouched


def test_canonical_override_is_private_and_unknown_sources_rejected(tmp_path):
    saved = map_regions.edit(tmp_path, payload=payload(id="rel-grower-peru", revision=0, entity_id="company-grower", activity="Growing"), entities=ENTITIES, relationships=REL, records=RECORDS)
    assert saved["revision"] == 1
    assert map_regions.catalog(ENTITIES, REL, RECORDS)[0]["activity"] == "Operations (unspecified)"
    assert map_regions.catalog(ENTITIES, REL, RECORDS, map_regions.load(tmp_path))[0]["activity"] == "Growing"
    for changes in ({"source_id": "missing"}, {"source_url": "http://127.0.0.1/private"}, {"source_url": "https://user:secret@example.org"}, {"source_url": "http://[bad"}, {"observed_on": "tomorrow"}, {"activity": "Sells berries"}):
        with pytest.raises(ValueError):
            map_regions.edit(tmp_path, payload=payload(**changes), entities=ENTITIES, relationships=REL, records=RECORDS)


def test_concurrent_additions_preserve_both_and_damaged_store_not_overwritten(tmp_path):
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(lambda note: map_regions.edit(tmp_path, payload=payload(notes=note), entities=ENTITIES, relationships=REL, records=RECORDS), ["one", "two"]))
    assert len(map_regions.load(tmp_path)["entries"]) == 2
    path = tmp_path / map_regions.FILENAME
    path.write_text("broken history", encoding="utf-8")
    with pytest.raises(ValueError):
        map_regions.edit(tmp_path, payload=payload(), entities=ENTITIES, relationships=REL, records=RECORDS)
    assert path.read_text(encoding="utf-8") == "broken history"


def test_shared_scope_region_time_independence_roles_and_source_privacy(tmp_path):
    map_regions.edit(tmp_path, payload=payload(), entities=ENTITIES, relationships=REL, records=RECORDS)
    kwargs = dict(query=IntelligenceQuery(("geography-peru",), berry_ids=("berry-blueberry",)), records=RECORDS, entities=ENTITIES,
                  relationships=REL, berries=BERRIES, facts=FACTS, state={"entity_tiers": {"company-grower": "tier1"}},
                  params={"layer": "varieties", "company": "company-grower", "tier": "tier1", "window": "custom", "start": "2026-01-01", "end": "2026-01-02"}, inbox_dir=tmp_path, authoring=True)
    model = map_workspace.model(**kwargs)
    assert model["matching"] == 0 and len(model["region_rows"]) == 1
    assert next(c for c in model["countries"] if c["id"] == "geography-peru")["region_count"] == 1
    assert map_workspace.model(**{**kwargs, "authoring": False})["region_rows"] == []
    assert map_workspace.model(**{**kwargs, "relationships": [r for r in REL if r.get("predicate") != "develops"]})["region_rows"] == []
    assert map_workspace.model(**{**kwargs, "params": {**kwargs["params"], "region_status": "active"}})["region_rows"] == []
    snapshot = snapshot_model(kwargs["query"], RECORDS, ENTITIES, REL, BERRIES, ["companies"], facts=FACTS)
    assert "Manual trial note" not in json.dumps(snapshot, default=str)


def test_statistics_keep_country_units_gaps_and_existing_mixed_trade_semantics():
    query = IntelligenceQuery(("geography-united-states", "geography-peru"), berry_ids=("berry-blueberry", "berry-strawberry"))
    trade = {**RECORDS[0], "id": "ev-trade", "trade_observation": {"reporter_geography_id": "geography-peru", "flow": "export", "hs_code": "081040", "berry_code_purity": "multi_berry_combined", "series": [{"period": "2025-11", "quantity": None}, {"period": "2025-12", "quantity": 0, "quantity_unit": "kg", "value_basis": "unspecified"}]}}
    result = map_workspace.statistics(query, ENTITIES, [trade])
    assert len(result["groups"]) == 2
    assert result["groups"][0]["metrics"][1] == {"label": "Harvested area", "value": 104700, "unit": "acres"}
    assert len(result["gaps"]) == 2
    assert result["trades"][0]["latest"]["quantity"] == 0
    assert result["trades"][0]["observation"]["berry_code_purity"] == "multi_berry_combined"
    assert not map_workspace.statistics(IntelligenceQuery(country_codes=("KW",)), ENTITIES, [trade])["groups"]
    assert not map_workspace.statistics(query, ENTITIES, [{**trade, "status": "draft"}])["trades"]


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "entity_index", lambda: ENTITIES)
    monkeypatch.setattr(main, "published_evidence", lambda: RECORDS)
    monkeypatch.setattr(main, "all_relationships", lambda: REL)
    monkeypatch.setattr(main, "all_facts", lambda: FACTS)
    return TestClient(main.app)


def test_editor_and_map_get_are_pure_and_invalid_post_protected(client, tmp_path, monkeypatch):
    assert client.get('/explorer?layer=companies').status_code == 200
    assert client.get('/profiles/variety-one/regions').status_code == 200
    assert not (tmp_path / map_regions.FILENAME).exists()
    assert client.get('/profiles/missing/regions').status_code == 404
    assert client.get('/explorer?layer=missing').status_code == 422
    assert client.post('/profiles/variety-one/regions', data=payload(), headers={"origin": "https://other.test"}).status_code == 403
    assert client.post('/profiles/variety-one/regions', data=payload()).status_code == 200
    page = client.get('/explorer?layer=varieties')
    assert 'Manual trial note' in page.text and 'User annotation' in page.text
    created = next(iter(map_regions.load(tmp_path)["entries"].values()))
    assert client.post('/profiles/company-grower/regions', data={"id": created["id"], "revision": 1, "action": "remove"}).status_code == 404
    assert client.post('/profiles/variety-one/regions', data=payload(id=created["id"], revision=0)).status_code == 409
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    assert client.post('/profiles/variety-one/regions', data=payload()).status_code == 403
    assert 'Manual trial note' not in client.get('/profiles/variety-one/regions').text


def test_news_map_scope_parity_with_return_filters(client):
    params = '?view=unreviewed&countries=geography-peru&berry=berry-blueberry&company=company-grower&window=custom&start=2026-07-01&end=2026-08-02&tz=America%2FLos_Angeles'
    page = client.get('/explorer' + params)
    assert '1 unreviewed records' in page.text
    assert '/intelligence/ev-berry-news?personal=1' in page.text
    assert 'window=custom' in page.text and 'start=2026-07-01' in page.text
    stats = client.get('/explorer?countries=geography-united-states&layer=companies&window=custom&start=2026-01-01&end=2026-01-02')
    assert '104,700' in stats.text and '2025 crop year' in stats.text


def test_statement_support_and_observed_by_do_not_promote_region(tmp_path):
    fact = {**FACTS[0], "entity_ids": ["variety-one"]}
    row = map_regions.edit(tmp_path, payload=payload(fact_id="fact-news", status="active", observed_on="2026-08-01"), entities=ENTITIES, relationships=REL, records=RECORDS, facts=[fact])
    assert row["fact_id"] == "fact-news" and row["source_id"] == "ev-berry-news"
    rows = map_regions.catalog(ENTITIES, REL, RECORDS, map_regions.load(tmp_path))
    assert "not reviewed" in next(r for r in rows if r["id"] == row["id"])["basis"]
    assert not map_regions.scoped(rows, IntelligenceQuery(), REL, {}, kind="variety", as_of="2026-07-01")
    assert map_regions.scoped(rows, IntelligenceQuery(), REL, {}, kind="variety", as_of="2026-08-01", entity_id="variety-one")
    with pytest.raises(ValueError, match="reviewed statement"):
        map_regions.edit(tmp_path, payload=payload(fact_id="fact-news"), entities=ENTITIES, relationships=REL, records=RECORDS, facts=[{**fact, "status": "draft"}])


def test_live_published_metadata_cannot_enter_trusted_snapshot():
    snapshot = snapshot_model(IntelligenceQuery(), [{**RECORDS[0], "live": True}], ENTITIES, REL, BERRIES, ["developments"], facts=FACTS)
    assert snapshot["packet"]["source_trace"] == []
