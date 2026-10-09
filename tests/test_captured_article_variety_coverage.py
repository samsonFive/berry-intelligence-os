"""Captured news contributes private identity leads without a second action."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import feed_first_reader as reader
from app.services.feed_first_live import save_bundle
from app.services.variety_universe.article_sources import available_article_sources, MAX_CAPTURE_BYTES
from app.services.variety_universe.candidates import persist_variety_candidates
from app.services.variety_universe.corpus_discovery import build_discovered_candidates


def story(item_id="ev-article-coverage", **changes):
    row = {"id": item_id, "status": "published", "source_type": "company_website",
           "source_name": "Acceptance publisher", "title": "Genetics portfolio",
           "source_url": "https://example.test/" + item_id,
           "summary": "A publisher describes its breeding portfolio.",
           "berry_ids": ["berry-blueberry"], "entity_ids": []}
    return {**row, **changes}


def capture(inbox, record, text, **changes):
    payload = {"item_id": record["id"], "requested_url": record["source_url"],
               "ok": True, "availability": "partial", "passages": [text]}
    reader.save_capture(inbox, record["id"], {**payload, **changes})


def scan(records, entities=None, candidates=None):
    entities = entities or []
    return build_discovered_candidates(
        varieties=[row for row in entities if row.get("entity_type") == "variety"],
        entities=entities, published_evidence=[], facts=[],
        source_text_records=records, existing_candidates=candidates or [])


def test_exact_capture_and_retained_text_are_automatic_but_trust_stays_separate(tmp_path):
    published = story()
    raw = story("ev-unreviewed", article={"full_text": "Blackberry varieties include Local Black."})
    save_bundle(tmp_path, {"today": "2026-10-08", "records": [raw]})
    capture(tmp_path, published, "Blueberry varieties include Captured Blue.")
    capture(tmp_path, story("ev-orphan"), "Blueberry varieties include Orphan Blue.")
    original = deepcopy(published)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*.json")}
    selected, counts = available_article_sources([published], tmp_path)
    assert counts == {"known_sources": 2, "readable_sources": 2, "reviewed_sources": 1,
                      "unreviewed_sources": 1, "reader_captures": 1, "oversized_sources": 0}
    report = scan(selected)
    candidates = {row["candidate_name"]: row for row in report["candidates"]}
    assert set(candidates) == {"Captured Blue", "Local Black"}
    assert candidates["Captured Blue"]["knowledge"]["source_publication_reviewed"] is True
    assert candidates["Local Black"]["knowledge"]["source_publication_reviewed"] is False
    assert all(not row["auto_confirmed"] and not row["human_gated"] for row in candidates.values())
    assert published == original and before == {p: p.read_bytes() for p in tmp_path.rglob("*.json")}


@pytest.mark.parametrize("changes", [
    {"requested_url": "https://example.test/other"}, {"requested_url": None},
    {"item_id": "ev-other"}, {"ok": False}, {"passages": [{"text": "Hidden Lead"}]},
])
def test_wrong_identity_failed_or_malformed_capture_is_not_article_input(tmp_path, changes):
    row = story()
    capture(tmp_path, row, "Blueberry varieties include Hidden Lead.", **changes)
    selected, counts = available_article_sources([row], tmp_path)
    assert selected == [] and counts["readable_sources"] == 0


def test_summary_wall_oversized_text_and_oversized_capture_are_excluded(tmp_path):
    summary = story("ev-summary")
    summary["article"] = {"full_text": summary["summary"]}
    wall = story("ev-wall", article={"full_text": "Verify you are a human. Blueberry varieties include Wall Lead."})
    large = story("ev-large", article={"full_text": "x" * 200_001})
    cached = story("ev-large-cache")
    path = reader.capture_path(tmp_path, cached["id"])
    path.parent.mkdir(parents=True)
    path.write_text("x" * (MAX_CAPTURE_BYTES + 1), encoding="utf-8")
    selected, counts = available_article_sources([summary, wall, large, cached], tmp_path)
    assert selected == [] and counts["oversized_sources"] == 1


def test_existing_operator_text_and_source_identity_win_over_refresh(tmp_path):
    row = story(article={"full_text": "Blueberry varieties include My Stored Lead.", "author": "Operator"})
    original = deepcopy(row)
    capture(tmp_path, row, "Blueberry varieties include Refreshed Lead.")
    selected, counts = available_article_sources([row], tmp_path)
    assert selected[0]["article"] == original["article"] and row == original
    assert counts["reader_captures"] == 0
    assert scan(selected)["candidates"][0]["candidate_name"] == "My Stored Lead"


def test_same_name_keeps_each_article_review_status_and_primary_source():
    reviewed = story(article={"full_text": "Blueberry varieties include Shared Lead."})
    unreviewed = story("ev-unreviewed", status="unreviewed",
                       article={"full_text": "Blueberry varieties include Shared Lead."})
    for records in ([reviewed, unreviewed], [unreviewed, reviewed]):
        row = scan(records)["candidates"][0]
        assert row["knowledge"]["source_publication_reviewed"] == (records[0]["status"] == "published")
        sources = row["knowledge"]["article_text_sources"]
        assert {(s["evidence_id"], s["publication_reviewed"]) for s in sources} == {
            (reviewed["id"], True), (unreviewed["id"], False)}
        assert row["source_url"] == records[0]["source_url"]
        assert not row["proposed_relationships"] and not row["auto_confirmed"]


def test_audit_defaults_to_published_summaries_and_private_opt_in_is_body_free(tmp_path):
    from scripts.audit_variety_catalog_coverage import audit
    data = tmp_path / "data"
    for folder in ("entities", "evidence", "facts"):
        (data / folder).mkdir(parents=True)
    row = story()
    (data / "evidence" / "source.json").write_text(json.dumps(row), encoding="utf-8")
    inbox = tmp_path / "inbox"
    body = "Blueberry varieties include Audited Lead. Private original article passage."
    capture(inbox, row, body)
    assert audit(data)["source_named_identities"] == 0
    report = audit(data, inbox_dir=inbox)
    assert report["source_named_identities"] == 1
    assert report["sources"][0]["names"][0]["named_in_article"] is True
    assert report["sources"][0]["publication_reviewed"] is True
    assert report["article_sources"]["reader_captures"] == 1
    assert body not in json.dumps(report) and "Private original article passage" not in json.dumps(report)


@pytest.mark.parametrize("selected_inbox", ["private", "public"])
def test_private_audit_cli_refuses_an_output_outside_inbox(tmp_path, selected_inbox):
    script = Path(__file__).resolve().parents[1] / "scripts" / "audit_variety_catalog_coverage.py"
    # Local pytest scratch space itself lives under the private repo inbox.
    # Target the actual public-build folder to exercise the boundary on both
    # Windows locally and Linux CI, rather than assuming tmp_path is public.
    output = script.parents[1] / "generated" / ("rejected-private-audit-" + uuid4().hex + ".json")
    assert not output.exists()
    inbox = tmp_path / "inbox" if selected_inbox == "private" else output.parent
    result = subprocess.run([sys.executable, str(script), "--inbox-dir", str(inbox),
                             "--output", str(output)], capture_output=True, text=True, timeout=30)
    assert result.returncode != 0 and "Captured-article reports must stay" in result.stderr
    assert not output.exists()


def setup(monkeypatch, tmp_path, records, entities=None):
    entities = entities or []
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "empty-data")
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "published_evidence", lambda: records)
    monkeypatch.setattr(main, "all_entities", lambda: entities)
    monkeypatch.setattr(main, "all_facts", lambda: [])
    monkeypatch.setattr(main, "all_relationships", lambda: [])
    monkeypatch.setattr(reader, "capture_item", lambda *a, **k: pytest.fail("GET must never fetch"))
    return TestClient(main.app)


def test_default_queue_reader_and_coverage_share_names_without_get_writes(monkeypatch, tmp_path):
    row = story()
    entities = [{"id": "variety-known", "entity_type": "variety", "name": "Known Blue",
                 "berry_ids": ["berry-blueberry"]}]
    client = setup(monkeypatch, tmp_path, [row], entities)
    capture(tmp_path, row, "Blueberry varieties include Known Blue, New Blue and Rejected Blue.")
    rejected = scan([story(article={"full_text": "Blueberry varieties include Rejected Blue."})])["candidates"][0]
    rejected.update(status="rejected", identity_state="rejected", human_gated=True,
                    reviewer="Human", review_notes="Keep this decision")
    persist_variety_candidates([rejected], inbox_dir=tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*.json")}
    _varieties, candidates, report = main.variety_candidate_universe()
    assert {c["candidate_name"] for c in candidates} == {"Rejected Blue", "New Blue"}
    assert next(c for c in candidates if c["candidate_name"] == "Rejected Blue")["review_notes"] == "Keep this decision"
    assert next(c for c in candidates if c["candidate_name"] == "Rejected Blue")["corpus_article_text_sources"][0]["evidence_id"] == row["id"]
    assert report["article_sources"]["readable_sources"] == 1
    queue = client.get("/varieties/candidates")
    assert queue.status_code == 200 and "New Blue" in queue.text and "included automatically" in queue.text
    reader_page = client.get(f'/api/intelligence/{row["id"]}/reader?personal=1')
    assert reader_page.status_code == 200 and "Varieties in this article · 3 named" in reader_page.text
    assert '/entities/variety/variety-known' in reader_page.text and "New Blue · Needs catalog review" in reader_page.text
    coverage = client.get("/varieties/coverage")
    assert coverage.status_code == 200 and "Article names · 1 readable source checked" in coverage.text
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*.json")}
    kept = client.post(f'/varieties/discover-source/{row["id"]}', follow_redirects=False)
    assert kept.status_code == 303
    from app.services.variety_universe.candidates import load_variety_candidates
    assert {c["candidate_name"] for c in load_variety_candidates(tmp_path)} == {"Rejected Blue", "New Blue"}
    assert all(p.read_bytes() == original for p, original in before.items())
    after = {p: p.read_bytes() for p in tmp_path.rglob("*.json")}
    assert client.post(f'/varieties/discover-source/{row["id"]}', follow_redirects=False).status_code == 303
    assert after == {p: p.read_bytes() for p in tmp_path.rglob("*.json")}
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    monkeypatch.setattr("app.services.variety_universe.article_sources.available_article_sources",
                        lambda *a, **k: pytest.fail("Public must never read private article inputs"))
    assert main.variety_candidate_universe()[1] == []
    public = client.get(f'/api/intelligence/{row["id"]}/reader?personal=1')
    assert "New Blue" not in public.text and "Varieties in this article" not in public.text
