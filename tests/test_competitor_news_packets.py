from datetime import UTC, datetime, timedelta
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker

from app import main
from app.services import competitor_news_packets as packets, feed_first, personal_digest
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.providers import MemoryProvider

ENTITIES = {
    "company-a": {"id": "company-a", "name": "Alpha Berries", "aliases": [], "entity_type": "company", "status": "active"},
    "company-b": {"id": "company-b", "name": "Beta Berries", "aliases": [], "entity_type": "company", "status": "active"},
    "variety-z": {"id": "variety-z", "name": "Zed", "entity_type": "variety", "status": "active"},
    "geography-us": {"id": "geography-us", "name": "United States", "entity_type": "geography", "attributes": {"iso_3166_1_alpha_2": "US"}},
}


def source(**changes):
    return {"id": "ev-packet", "title": "Alpha Berries and Beta Berries launch Zed", "summary": "Source summary, not a verified fact.",
            "source_url": "https://example.com/news?campaign=Original&x=2", "source_name": "Publisher",
            "source_type": "trade_press", "published_date": "2026-09-29", "captured_date": "2026-09-30",
            "status": "published", "entity_ids": ["company-a", "company-b", "variety-z"],
            "berry_ids": ["berry-blueberry"], "geography_ids": ["geography-us"], **changes}


def scope(review="all"):
    return {"entity_ids": ["company-a", "company-b"], "start": "2026-09-01", "end": "2026-09-30", "review": review}


def job(tmp_path, review="all"):
    group = personal_digest.edit_list(tmp_path, action="create", name="Competitors", company_ids=["company-a", "company-b"], allowed_companies=set(ENTITIES))
    return packets.create_job(tmp_path, list_id=group, start="2026-09-01", end="2026-09-30", review=review, entities=ENTITIES)


def live_hit(**changes):
    return DiscoveryHit(**{"title": "Alpha Berries introduces blueberry cultivar", "url": "https://example.com/new", "source_domain": "example.com",
                        "published_date": "2026-09-30", "snippet": "Source snippet", "query_id": "alpha", "query_text": "alpha", "geography": "global",
                        "berry": "blueberry", "topic": "variety", "provider": "memory", **changes})


def test_rows_preserve_urls_and_use_separate_competitor_relationship_rows():
    rows, validation = packets.build_rows([source()], scope(), ENTITIES)
    assert len(rows) == 4
    assert {row["competitor_id"] for row in rows} == {"company-a", "company-b"}
    assert {row["external_record_id"] for row in rows} == {"ev-packet"}
    assert all(set(row) == set(packets.FIELDS) for row in rows)
    assert all(row["source_url"] == source()["source_url"] for row in rows)
    assert all(row["country"] == ["United States"] and row["region"] == [] for row in rows)
    assert all(row["event_date"] is None and row["imported_at"] is None for row in rows)
    assert all(not row["publish_to_landscape"] for row in rows)
    assert not validation["errors"]


def test_reviewed_means_publication_not_atomic_and_live_cannot_assert_review():
    records = [source(), source(id="ev-live", source_url="https://example.com/live", live=True, review_state="reviewed"),
               source(id="ev-auto", source_url="https://example.com/auto", auto_captured=True, validated=False)]
    reviewed, _ = packets.build_rows(records, scope("reviewed"), ENTITIES)
    assert {row["external_record_id"] for row in reviewed} == {"ev-packet"}
    assert all(row["verification_status"] == "source_reviewed" for row in reviewed)
    all_news, _ = packets.build_rows(records, scope(), ENTITIES)
    assert len(all_news) == 12
    assert {row["record_status"] for row in all_news} == {"approved", "unreviewed"}


def test_duplicates_prefer_reviewed_without_upgrading_live_text():
    live = source(id="live-other", live=True, summary="Raw alternative", source_url="https://example.com/news?x=2&campaign=Original")
    rows, validation = packets.build_rows([live, source()], scope(), ENTITIES)
    assert {row["external_record_id"] for row in rows} == {"ev-packet"}
    assert all(row["summary"] == source()["summary"] for row in rows)
    assert validation["warnings"][0]["code"] == "duplicate"


def test_undated_unknown_related_and_provisional_go_to_exception_report():
    entities = {key: {**row} for key, row in ENTITIES.items()}
    entities["company-a"]["status"] = "unverified"
    row = source(entity_ids=["company-a", "unknown-related"])
    rows, validation = packets.build_rows([row, source(id="ev-undated", published_date="bad")], scope(), entities)
    assert len(rows) == 1 and rows[0]["related_entity_id"] is None
    assert {warning["code"] for warning in validation["warnings"]} == {"missing_date", "unknown_entity", "identity_pending"}


def test_capture_export_history_schema_and_idempotent_retry(tmp_path):
    created = job(tmp_path)
    provider = MemoryProvider(hits=[live_hit()])
    packets.capture_job(tmp_path, created["id"], ENTITIES, [source()], provider)
    ready = packets.load_job(tmp_path, created["id"])
    assert ready["status"] == "ready" and ready["capture"]["queries_done"] == 2
    assert packets.export_history(tmp_path)["last_generated"] == {}
    exported = packets.commit_export(tmp_path, created["id"])
    assert exported["status"] == "exported"
    assert not list(packets.export_validator().iter_errors(exported["packet"]))
    assert exported["packet"]["generated_at"].endswith("Z")
    assert packets.commit_export(tmp_path, created["id"])["generated_at"] == exported["generated_at"]
    assert len(packets.export_history(tmp_path)["exports"]) == 1
    # A torn receipt can be recovered without regenerating / acquiring a source.
    (tmp_path / "news_packets/history.json").unlink()
    packets.commit_export(tmp_path, created["id"])
    assert len(packets.export_history(tmp_path)["exports"]) == 1
    assert len(personal_digest.retained_news(tmp_path)) == 1


def test_failed_capture_never_exports_or_advances_last_generated(tmp_path):
    class Broken:
        def discover(self, query):
            raise RuntimeError("secret authorization token must not be persisted")
    created = job(tmp_path)
    packets.capture_job(tmp_path, created["id"], ENTITIES, [source()], Broken())
    failed = packets.load_job(tmp_path, created["id"])
    assert failed["status"] == "failed" and len(failed["capture"]["errors"]) == 2
    assert "secret" not in json.dumps(failed)
    with pytest.raises(ValueError, match="successful fresh capture"):
        packets.commit_export(tmp_path, created["id"])
    assert not packets.export_history(tmp_path)["last_generated"]


def test_stale_capture_requires_new_capture_and_schema_failure_is_not_committed(tmp_path):
    created = job(tmp_path)
    packets.capture_job(tmp_path, created["id"], ENTITIES, [source()], MemoryProvider(hits=[]))
    with pytest.raises(ValueError, match="15 minutes"):
        packets.commit_export(tmp_path, created["id"], now=datetime.now(UTC) + timedelta(minutes=20))
    ready = packets.load_job(tmp_path, created["id"])
    ready["records"][0]["publish_to_landscape"] = True
    packets.atomic_json(packets.path_for(tmp_path, created["id"]), ready)
    with pytest.raises(ValueError, match="schema"):
        packets.commit_export(tmp_path, created["id"])
    assert packets.load_job(tmp_path, created["id"])["status"] == "ready"
    assert not packets.export_history(tmp_path)["exports"]


def test_query_dates_inclusive_and_no_paid_provider(tmp_path):
    queries = list(packets.queries_for(scope(), ENTITIES))
    assert len(queries) == 2
    assert '"Alpha Berries"' in queries[0].text
    assert "after:2026-08-31 before:2026-10-01" in queries[0].text
    assert all(query.berry is None for query in queries)


def test_csv_template_exact_fields_and_formula_guard():
    assert packets.csv_file([], packets.FIELDS).splitlines()[0].split(",") == list(packets.FIELDS)
    assert "'=SUM(1)" in packets.csv_file([{"message": "=SUM(1)"}], ["message"])


def test_registry_all_77_names_resolve_in_real_database_without_merging():
    root = Path(__file__).resolve().parents[1]
    from app.composition import get_repositories
    entities = {row["id"]: row for row in get_repositories(root / "data", root / "schemas").entities.list()}
    rows = packets.registry(root / "data", entities)
    assert len(rows) == 77
    assert not [row for row in rows if row["missing"] or not row["entity_ids"]]
    assert next(row for row in rows if row["name"] == "AgroBerries / BerryWorld")["entity_ids"] == ["company-agroberries", "company-berryworld"]
    assert entities["person-mario-aguas-alvarado"]["entity_type"] == "person"
    assert entities["company-genetics-uruguay"]["status"] == "unverified"


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "all_entities", lambda: list(ENTITIES.values()))
    monkeypatch.setattr(main, "all_evidence", lambda: [source()])
    monkeypatch.setattr(main, "published_evidence", lambda: [source()])
    monkeypatch.setattr(main, "list_pending_drafts", lambda: [])
    monkeypatch.setattr(packets, "GoogleNewsRssProvider", lambda: MemoryProvider(hits=[live_hit()]))
    group = personal_digest.edit_list(main.INBOX_DIR, action="create", name="Competitors", company_ids=["company-a", "company-b"], allowed_companies=set(ENTITIES))
    return TestClient(main.app), group


def test_route_capture_preview_export_and_gets_do_not_collect_or_mutate(workspace):
    client, group = workspace
    before = list(main.INBOX_DIR.rglob("*"))
    assert client.get("/news-packets").status_code == 200
    assert client.get("/news-packets/template.csv").status_code == 200
    assert list(main.INBOX_DIR.rglob("*")) == before
    response = client.post("/news-packets/capture", data={"list_id": group, "start": "2026-09-01", "end": "2026-09-30", "review": "all"}, follow_redirects=False)
    assert response.status_code == 303
    url = response.headers["location"]
    assert "Ready to export" in client.get(url).text
    assert client.get(url + "/download.json").status_code == 409
    assert client.post(url + "/export", follow_redirects=False).status_code == 303
    packet = client.get(url + "/download.json")
    assert packet.status_code == 200 and packet.headers["cache-control"] == "no-store"
    assert packet.json()["records"]
    stamp_before = packets.export_history(main.INBOX_DIR)
    assert client.get(url).status_code == 200
    client.get(url + "/download.json")
    assert packets.export_history(main.INBOX_DIR) == stamp_before


def test_invalid_scope_cross_site_and_readonly_are_rejected(workspace, monkeypatch):
    client, group = workspace
    data = {"list_id": group, "start": "2026-09-01", "end": "2026-09-30", "review": "all"}
    assert client.post("/news-packets/capture", data={**data, "review": "trust_everything"}).status_code == 400
    assert client.post("/news-packets/capture", data={**data, "start": "bad"}).status_code == 400
    assert client.post("/news-packets/capture", data=data, headers={"Origin": "https://attacker.invalid"}).status_code == 403
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    assert client.post("/news-packets/capture", data=data).status_code == 403
    assert client.post("/news-packets/setup").status_code == 403
    assert client.get("/news-packets/packet-" + "f" * 32).status_code == 404


def test_fresh_screening_excludes_stock_quotes_and_unrelated_public_institutions(tmp_path):
    entities = {**ENTITIES, "university": {"id": "university", "name": "University of Everywhere", "entity_type": "company", "roles": ["public_research_institution"]}}
    current = job(tmp_path)
    hits = [live_hit(), live_hit(title="Alpha Berries stock price quote and history", url="https://example.com/stock"),
            live_hit(title="University of Everywhere holds finance summit", snippet="Annual accounting event", berry=None, url="https://example.com/event"),
            live_hit(title="Alpha Berries raises funding to expand blueberry farms", url="https://example.com/funding")]
    packets.capture_job(tmp_path, current["id"], entities, [], MemoryProvider(hits=hits))
    captured = packets.load_job(tmp_path, current["id"])
    assert captured["status"] == "ready"
    assert {row["source_url"] for row in captured["records"]} == {"https://example.com/new", "https://example.com/funding"}
    assert captured["capture"]["screened_results"] > 0


def test_historical_receipt_retry_does_not_move_last_generated_backwards(tmp_path):
    for batch, when in [("new", "2026-10-01T09:00:00Z"), ("old", "2026-09-30T18:00:00Z"), ("old", "2026-09-30T18:00:00Z")]:
        packets.record_export_receipt(tmp_path, {"batch_id": batch, "generated_at": when, "scope": {"list_id": "list-test"}, "rows": 1})
    history = packets.export_history(tmp_path)
    assert history["last_generated"]["list-test"] == "2026-10-01T09:00:00Z"
    assert len(history["exports"]) == 2


def test_manual_capture_reports_real_health_without_creating_drafts(tmp_path):
    from app.services.pipeline_health import build_pipeline_health
    created = job(tmp_path)
    packets.capture_job(tmp_path, created["id"], ENTITIES, [], MemoryProvider(hits=[live_hit()]))
    root = Path(__file__).resolve().parents[1]
    health = build_pipeline_health(data_dir=root / "data", inbox_dir=tmp_path, config_path=root / "data/configuration/collection_pipelines.json")
    report = next(row for row in health["pipelines"] if row["pipeline"] == "competitor_news_export")
    assert report["outcome"] == "SUCCESS" and report["last_attempt"] and report["last_success"]
    assert not report["scheduled"] and report["drafts_created"] == 0 and report["items_discovered"] == 1
