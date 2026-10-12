"""Private publication bodies connect to identity discovery and selected reading."""
from copy import deepcopy
import json

import pytest

from app import main
from app.services import analyst_queue, feed_first_reader as reader, personal_digest
from app.services.feed_first_live import save_bundle
from app.services.variety_universe.article_sources import available_article_sources, article_source_records
from app.services.variety_universe.candidates import load_variety_candidates, persist_variety_candidates
from tests.test_captured_article_variety_coverage import story, capture, scan, setup


def draft(item_id="ev-pending-portfolio", **changes):
    return story(item_id, **{"status": "in_review", "evidence_role": "publication_artifact",
                 "article": {"full_text": "Blackberry varieties include Draft Lead and Human Lead."}, **changes})


def write_draft(inbox, row):
    path = inbox / "evidence" / (row["id"] + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row), encoding="utf-8")
    return path


@pytest.mark.parametrize("status,role", [
    ("rejected", "publication_artifact"), ("archived", "publication_artifact"),
    ("published", "publication_artifact"), ("in_review", "atomic_evidence"),
])
def test_rejected_archived_spoofed_published_and_atomic_bodies_stay_out(tmp_path, status, role):
    row = draft()
    row.update(status=status, evidence_role=role)
    selected, counts = available_article_sources([], tmp_path, pending=[row])
    assert selected == [] and counts["known_sources"] == 0


def test_pending_stored_text_and_matching_capture_keep_unreviewed_provenance(tmp_path):
    stored = draft()
    captured = draft("ev-pending-capture", article={})
    capture(tmp_path, captured, "Blueberry varieties include Captured Draft Lead.")
    original = deepcopy(stored)
    selected, counts = available_article_sources([], tmp_path, pending=[stored, captured])
    assert counts["known_sources"] == counts["readable_sources"] == counts["unreviewed_sources"] == 2
    assert counts["reviewed_sources"] == 0 and counts["reader_captures"] == 1
    assert stored == original and stored["status"] == "in_review"
    assert all(not row["knowledge"]["source_publication_reviewed"] for row in scan(selected)["candidates"])
    assert {c["candidate_name"] for c in scan(selected)["candidates"]} == {
        "Draft Lead", "Human Lead", "Captured Draft Lead"}


def test_pending_display_names_the_configured_publisher_without_rewriting_the_draft(tmp_path):
    row = draft(source_name="Site-restricted news search -- Acceptance Publisher")
    original = deepcopy(row)
    selected, _ = available_article_sources([], tmp_path, pending=[row])
    assert selected[0]["source_name"] == "Acceptance Publisher" and row == original


def test_canonical_and_conflicting_source_identities_never_borrow_pending_prose(tmp_path):
    published = story(article={"full_text": "Blueberry varieties include Canonical Lead."})
    same_id = draft(published["id"])
    cached = story("ev-retained-conflict", article={"full_text": "Blueberry varieties include Retained Lead."})
    save_bundle(tmp_path, {"today": "2026-10-08", "records": [cached]})
    conflict = draft(cached["id"], source_url="https://example.test/different")
    selected, counts = available_article_sources([published], tmp_path, pending=[same_id, conflict])
    assert counts["reviewed_sources"] == 1
    assert {c["candidate_name"] for c in scan(selected)["candidates"]} == {"Canonical Lead", "Retained Lead"}
    assert article_source_records([published], tmp_path, pending=[same_id])[published["id"]]["article"] == published["article"]


@pytest.mark.parametrize("state", ["rejected", "archived"])
def test_terminal_publication_review_removes_same_id_cache_but_never_canonical(tmp_path, state):
    row = draft(review_state=state)
    save_bundle(tmp_path, {"today": "2026-10-08", "records": [row]})
    selected, counts = available_article_sources([], tmp_path, pending=[row])
    assert selected == [] and counts["known_sources"] == 0
    published = story(row["id"], article={"full_text": "Blueberry varieties include Canonical Lead."})
    selected, counts = available_article_sources([published], tmp_path, pending=[row])
    assert counts["reviewed_sources"] == 1
    assert [c["candidate_name"] for c in scan(selected)["candidates"]] == ["Canonical Lead"]


def test_pending_reader_default_discovery_keep_and_digest_preserve_human_gates(monkeypatch, tmp_path):
    row = draft()
    path = write_draft(tmp_path, row)
    client = setup(monkeypatch, tmp_path, [])
    rejected = scan([draft(article={"full_text": "Blackberry varieties include Human Lead."})])["candidates"][0]
    rejected.update(status="rejected", identity_state="rejected", human_gated=True,
                    reviewer="Human", review_notes="Keep this review decision")
    held = persist_variety_candidates([rejected], inbox_dir=tmp_path)[0]
    before = {p: p.read_bytes() for p in tmp_path.rglob("*.json")}
    _, candidates, report = main.variety_candidate_universe()
    assert {c["candidate_name"] for c in candidates} == {"Draft Lead", "Human Lead"}
    assert report["article_sources"]["unreviewed_sources"] == 1
    # The selected Reader must not scan every draft body or rebuild the universe.
    monkeypatch.setattr(main, "list_drafts", lambda: pytest.fail("Selected Reader scanned draft backlog"))
    monkeypatch.setattr(main, "variety_candidate_universe", lambda: pytest.fail("Selected Reader rebuilt universe"))
    for url in (f'/intelligence/{row["id"]}?personal=1', f'/api/intelligence/{row["id"]}/reader?personal=1'):
        response = client.get(url)
        assert response.status_code == 200
        assert "Varieties in this article · 2 named" in response.text and "Unreviewed" in response.text
        assert row["article"]["full_text"] in response.text
    assert client.get("/digest").status_code == 200
    assert row["title"] not in client.get("/digest").text
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*.json")}
    assert client.post(f'/varieties/discover-source/{row["id"]}', follow_redirects=False).status_code == 303
    assert {c["candidate_name"] for c in load_variety_candidates(tmp_path)} == {"Draft Lead", "Human Lead"}
    assert all(not c["auto_confirmed"] for c in load_variety_candidates(tmp_path))
    assert held.read_bytes() == before[held] and path.read_bytes() == before[path]
    persisted = {p: p.read_bytes() for p in tmp_path.rglob("*.json")}
    assert client.post(f'/varieties/discover-source/{row["id"]}', follow_redirects=False).status_code == 303
    assert persisted == {p: p.read_bytes() for p in tmp_path.rglob("*.json")}
    saved = client.post(f'/digest/stories/{row["id"]}', json={"action": "save"})
    assert saved.status_code == 200 and row["title"] in client.get("/digest").text
    assert path.read_bytes() == before[path] and held.read_bytes() == before[held]
    reading = client.post(f'/digest/stories/{row["id"]}', json={"action": "start"})
    assert reading.status_code == 200
    assert analyst_queue.reading_state(row["id"], analyst_queue.load_state(tmp_path)) == "in_progress"
    assert json.loads(path.read_text())["status"] == "in_review"


def test_pending_capture_is_explicit_then_available_to_queue_without_approval(monkeypatch, tmp_path):
    row = draft(article={})
    path = write_draft(tmp_path, row)
    original = path.read_bytes()
    client = setup(monkeypatch, tmp_path, [])
    def acquire(inbox, record, **kwargs):
        assert record["id"] == row["id"] and record["status"] == "unreviewed"
        capture(inbox, record, "Blackberry varieties include Newly Captured Lead.")
        return reader.load_capture(inbox, record["id"])
    monkeypatch.setattr(reader, "capture_item", acquire)
    response = client.post(f'/api/digest/{row["id"]}/capture')
    assert response.status_code == 200 and "Newly Captured Lead" in response.text
    assert "Unreviewed" in response.text
    assert {c["candidate_name"] for c in main.variety_candidate_universe()[1]} == {"Newly Captured Lead"}
    assert path.read_bytes() == original and load_variety_candidates(tmp_path) == []


def test_selected_reader_uses_canonical_text_despite_a_same_id_pending_version(monkeypatch, tmp_path):
    published = story(article={"full_text": "Blueberry varieties include Canonical Lead."})
    pending = draft(published["id"], article={"full_text": "Blackberry varieties include Private Conflicting Lead."})
    write_draft(tmp_path, pending)
    client = setup(monkeypatch, tmp_path, [published])
    response = client.get(f'/api/intelligence/{published["id"]}/reader?personal=1')
    assert response.status_code == 200 and "Canonical Lead" in response.text
    assert "Private Conflicting Lead" not in response.text and "Source reviewed" in response.text


def test_digest_uses_saved_pending_operator_edits_and_does_not_rehydrate_rejected_text(monkeypatch, tmp_path):
    row = draft(title="Operator edited article title")
    path = write_draft(tmp_path, row)
    cached = {**row, "title": "Older cached title"}
    save_bundle(tmp_path, {"today": "2026-10-08", "records": [cached]})
    client = setup(monkeypatch, tmp_path, [])
    assert client.post(f'/digest/stories/{row["id"]}', json={"action": "save"}).status_code == 200
    result = client.get("/digest")
    assert row["title"] in result.text and cached["title"] not in result.text
    row["review_state"] = "rejected"
    write_draft(tmp_path, row)
    original = path.read_bytes()
    assert client.post(f'/varieties/discover-source/{row["id"]}', follow_redirects=False).status_code == 404
    assert row["title"] not in client.get("/digest").text and cached["title"] not in client.get("/digest").text
    assert main.variety_candidate_universe()[2]["article_sources"]["readable_sources"] == 0
    assert path.read_bytes() == original


def test_rejected_pending_not_discoverable_and_no_private_reader_in_public(monkeypatch, tmp_path):
    row = draft()
    write_draft(tmp_path, row)
    client = setup(monkeypatch, tmp_path, [])
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    monkeypatch.setattr(main, "get_draft", lambda *a: pytest.fail("Public read private draft"))
    assert client.get(f'/api/intelligence/{row["id"]}/reader?personal=1').status_code == 404
    assert client.post(f'/varieties/discover-source/{row["id"]}').status_code == 403
    monkeypatch.undo()
    row["status"] = "rejected"
    write_draft(tmp_path, row)
    client = setup(monkeypatch, tmp_path, [])
    assert client.get(f'/api/intelligence/{row["id"]}/reader?personal=1').status_code == 404
    assert client.post(f'/varieties/discover-source/{row["id"]}').status_code == 404


def test_private_audit_includes_active_draft_names_but_not_original_bodies(tmp_path):
    from scripts.audit_variety_catalog_coverage import audit
    data = tmp_path / "data"
    for folder in ("entities", "evidence", "facts"):
        (data / folder).mkdir(parents=True)
    inbox = tmp_path / "inbox"
    row = draft()
    write_draft(inbox, row)
    rejected = draft("ev-rejected")
    rejected["status"] = "rejected"
    write_draft(inbox, rejected)
    report = audit(data, inbox_dir=inbox)
    assert report["source_named_identities"] == 2 and report["reviewed_sources_scanned"] == 0
    assert report["sources"][0]["publication_reviewed"] is False
    assert row["article"]["full_text"] not in json.dumps(report)
    assert audit(data)["source_named_identities"] == 0


@pytest.mark.parametrize("text,name", [
    ("The publisher reveals the name of the new variety: it will be called Test‑Viva and is a raspberry release.", "Test‑Viva"),
    ("Our new blackberry cultivar is named Black Pearl. Production claims are unreviewed.", "Black Pearl"),
    ("The new blueberry variety will be called Blue Echo.", "Blue Echo"),
])
def test_explicit_single_release_declaration_preserves_the_name_without_roles_or_aliases(text, name):
    report = scan([draft(article={"full_text": text})])
    assert [row["candidate_name"] for row in report["candidates"]] == [name]
    candidate = report["candidates"][0]
    assert candidate["knowledge"]["source_publication_reviewed"] is False
    assert not candidate["proposed_relationships"] and not candidate["auto_confirmed"]
    assert not candidate.get("breeder_code")


@pytest.mark.parametrize("text", [
    "The name of the new variety: it will be called Unknown Crop.",
    "The name of the new variety: it will be called Mixed Crop, for raspberry and blackberry programmes.",
    "It is not confirmed that the new blueberry variety will be called Unconfirmed Blue.",
    "Perhaps the name of the new variety: it will be called Speculative Blue, a blueberry release.",
    "Our new raspberry programme is called Company North.",
])
def test_naming_without_one_crop_or_an_actual_variety_assertion_does_not_create_a_lead(text):
    assert scan([draft(article={"full_text": text})])["candidates"] == []
