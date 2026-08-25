"""Analyst Review Session: navigation only, not a trust object."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.queries.pending_review import JsonPendingDraftSnapshotProvider, PendingReviewQueryService
from app.services.review_events import append_review_event
from app.services.review_session import (
    CONTINUE_PATH,
    create_session,
    list_recent_sessions,
    load_session,
    present_session,
    reconcile_session,
    skip_current,
    stop_session,
)

PRIORITY = {
    dimension: {"level": "none", "rationale": ""}
    for dimension in ("reading", "testing", "commercial_position", "monitoring")
}
ENTITIES = {
    "company-planasa": {"id": "company-planasa", "entity_type": "company", "name": "Planasa"},
}
SOURCES = {
    "source-planasa": {
        "id": "source-planasa",
        "label": "Planasa Newsroom",
        "linked_competitor_ids": ["company-planasa"],
    }
}


def _pub(index: int, **overrides) -> dict:
    record = {
        "id": f"pending-{index:04d}",
        "record_type": "evidence",
        "evidence_role": "publication_artifact",
        "status": "pending",
        "source_id": "source-planasa",
        "source_name": "Planasa Newsroom",
        "source_type": "company_website",
        "title": f"Planasa blueberry production update {index}",
        "published_date": "2026-08-20",
        "captured_date": "2026-08-20",
        "summary": "Untrusted pending summary.",
        "berry_ids": ["berry-blueberry"],
        "entity_ids": [],
        "relevance_tier": "direct",
        "media_format": "web_article",
        "priority": deepcopy(PRIORITY),
        "article": {"paragraphs": [{"text": "SECRET FULL ARTICLE BODY MUST NOT PERSIST"}]},
        "source_completeness": {"class": "FULL_ARTICLE"},
    }
    record.update(overrides)
    return record


def _write(folder: Path, record: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{record['id']}.json").write_text(json.dumps(record), encoding="utf-8")


def _artifact(evidence_id: str, status: str = "pending", **overrides) -> dict:
    row = {
        "source_fidelity_artifact_schema_version": 1,
        "evidence_id": evidence_id,
        "match_class": "EXACT_IDENTITY_MATCH",
        "identity_proof": ["EXACT_IDENTITY_MATCH"],
        "review": {"status": status},
        "reacquired_at": "2026-08-10T00:00:00+00:00",
        "source_name": "Planasa Newsroom",
        "source_chars": 4000,
        "artifact_type": "article",
        "paragraphs": [{"text": "SECRET RECOVERED BODY MUST NOT PERSIST"}],
    }
    row.update(overrides)
    return row


def _trusted(evidence_id: str) -> dict:
    return {
        "id": evidence_id,
        "status": "published",
        "title": f"Trusted {evidence_id}",
        "berry_ids": ["berry-raspberry"],
        "entity_ids": ["company-planasa"],
        "source_id": "source-planasa",
        "source_name": "Planasa Newsroom",
    }


def _atomic(index: int, parent: str, **overrides) -> dict:
    record = {
        "id": f"atomic-{index:04d}",
        "record_type": "evidence",
        "evidence_role": "atomic_evidence",
        "status": "draft",
        "parent_evidence_id": parent,
        "captured_date": "2026-08-01",
        "summary": "Proposed statement",
        "transcript_excerpt": "SECRET ATOMIC EXCERPT SHOULD NOT PERSIST",
        "berry_ids": ["berry-blueberry"],
        "priority": deepcopy(PRIORITY),
    }
    record.update(overrides)
    return record


def _service(inbox: Path) -> PendingReviewQueryService:
    return PendingReviewQueryService(JsonPendingDraftSnapshotProvider(inbox))


def _create(inbox: Path, queue: str, size: int, **kwargs):
    pubs = kwargs.pop("published", [])
    atomics = kwargs.pop("atomic_drafts", [])
    artifacts = kwargs.pop("fidelity_artifacts", None)
    return create_session(
        inbox,
        queue=queue,
        size=size,
        pending_service=_service(inbox),
        entities=ENTITIES,
        sources=SOURCES,
        published=pubs,
        atomic_drafts=atomics,
        berry_labels={"berry-blueberry": "Blueberry"},
        fidelity_artifacts=artifacts,
        **kwargs,
    )


def test_create_publication_session_bounded_and_deterministic(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    for index in range(12):
        _write(inbox / "evidence", _pub(index))
    first = _create(inbox, "publication", 10)
    second = _create(inbox, "publication", 10)
    assert len(first["items"]) == 10
    assert [row["id"] for row in first["items"]] == [row["id"] for row in second["items"]]
    assert all(row["kind"] == "publication" for row in first["items"])
    assert "/review/" in first["items"][0]["href"]
    dumped = json.dumps(first)
    assert "SECRET FULL ARTICLE BODY" not in dumped
    assert "article" not in dumped


def test_create_source_fidelity_session_from_21_pilot_inventory(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    published = []
    artifacts = []
    for index in range(21):
        evidence_id = f"ev-pilot-{index:02d}"
        published.append(_trusted(evidence_id))
        artifacts.append(_artifact(evidence_id, source_chars=5000 - index))
    session = _create(inbox, "source_fidelity", 10, published=published, fidelity_artifacts=artifacts)
    assert len(session["items"]) == 10
    assert session["items"][0]["kind"] == "source_fidelity"
    assert session["items"][0]["href"].startswith("/source-fidelity/")
    assert "SECRET RECOVERED BODY" not in json.dumps(session)
    again = _create(inbox, "source_fidelity", 10, published=published, fidelity_artifacts=artifacts)
    assert [row["id"] for row in session["items"]] == [row["id"] for row in again["items"]]


def test_create_atomic_batch_session(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    drafts = [
        _atomic(0, "parent-a"),
        _atomic(1, "parent-a"),
        _atomic(2, "parent-a"),
        _atomic(3, "parent-b"),
        _atomic(4, "parent-b"),
        _atomic(5, "parent-c"),
    ]
    session = _create(inbox, "atomic", 5, atomic_drafts=drafts)
    assert [row["id"] for row in session["items"]] == ["parent-a", "parent-b", "parent-c"]
    assert session["items"][0]["proposition_count"] == 3
    assert "kind=atomic" in session["items"][0]["href"]
    assert "SECRET ATOMIC EXCERPT" not in json.dumps(session)


def test_save_does_not_complete_real_decision_does_and_skip_is_local(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    _write(inbox / "evidence", _pub(0))
    session = _create(inbox, "publication", 5)
    item_id = session["items"][0]["id"]
    draft = json.loads((inbox / "evidence" / f"{item_id}.json").read_text(encoding="utf-8"))
    draft["title"] = "Edited but not published"
    (inbox / "evidence" / f"{item_id}.json").write_text(json.dumps(draft), encoding="utf-8")
    after_save = reconcile_session(inbox, load_session(inbox), drafts=[draft], artifacts=[])
    assert item_id not in after_save["completed"]
    skipped = skip_current(inbox, after_save)
    assert item_id in skipped["skipped"]
    unchanged = json.loads((inbox / "evidence" / f"{item_id}.json").read_text(encoding="utf-8"))
    assert unchanged["status"] == "pending"
    draft["status"] = "rejected"
    draft["review_state"] = "rejected"
    (inbox / "evidence" / f"{item_id}.json").write_text(json.dumps(draft), encoding="utf-8")
    done = reconcile_session(inbox, load_session(inbox), drafts=[draft], artifacts=[])
    assert item_id in done["completed"]
    assert done["outcomes"][item_id] == "rejected"


def test_resume_external_reconcile_and_complete(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    _write(inbox / "evidence", _pub(0))
    _write(inbox / "evidence", _pub(1))
    session = _create(inbox, "publication", 5)
    pointer = json.loads((inbox / "review_sessions" / "current.json").read_text(encoding="utf-8"))
    assert pointer["session_id"] == session["session_id"]
    assert load_session(inbox)["current_id"] == session["items"][0]["id"]
    first = session["items"][0]["id"]
    (inbox / "evidence" / f"{first}.json").unlink()
    append_review_event(
        inbox,
        workflow="publication_review",
        object_id=first,
        object_type="publication_draft",
        action="publish",
        prior_state="pending",
        new_state="published",
        actor="analyst",
        subject={"id": first},
    )
    remaining_draft = json.loads((inbox / "evidence" / f"{session['items'][1]['id']}.json").read_text(encoding="utf-8"))
    remaining_draft["status"] = "rejected"
    remaining_draft["review_state"] = "rejected"
    reconciled = reconcile_session(
        inbox,
        load_session(inbox),
        drafts=[remaining_draft],
        artifacts=[],
    )
    assert first in reconciled["completed"]
    assert reconciled["outcomes"][first] == "published"
    assert remaining_draft["id"] in reconciled["completed"]
    view = present_session(reconciled)
    assert view["status"] == "complete"
    assert view["outcomes"]["published"] == 1
    assert view["outcomes"]["rejected"] == 1
    stopped = stop_session(inbox, reconciled)
    assert stopped["status"] == "stopped"


def test_review_session_routes_have_no_trust_actions(monkeypatch, tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    data = tmp_path / "data"
    published = []
    artifacts = []
    for index in range(21):
        evidence_id = f"ev-pilot-{index:02d}"
        published.append(_trusted(evidence_id))
        artifacts.append(_artifact(evidence_id))
        _write(inbox / "source_fidelity" / "artifacts", {**artifacts[-1], "id": evidence_id})
        (inbox / "source_fidelity" / "artifacts" / f"{evidence_id}.json").write_text(
            json.dumps(artifacts[-1]), encoding="utf-8"
        )
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "DATA_DIR", data)
    monkeypatch.setattr(main, "entity_index", lambda: ENTITIES)
    monkeypatch.setattr(main, "load_sources", lambda: list(SOURCES.values()))
    monkeypatch.setattr(main, "published_evidence", lambda: published)
    monkeypatch.setattr(main, "list_drafts", lambda: [])
    client = TestClient(main.app)
    ops = client.get("/review-ops")
    assert ops.status_code == 200
    assert "Start review session" in ops.text
    assert 'name="decision"' not in ops.text
    assert "Affirm source artifact" not in ops.text
    started = client.post(
        "/review-ops/session",
        data={"queue": "source_fidelity", "size": "10"},
        follow_redirects=False,
    )
    assert started.status_code == 303
    overview = client.get("/review-ops/session")
    assert overview.status_code == 200
    assert "SOURCE FIDELITY SESSION" in overview.text
    assert "10 remaining" in overview.text or "of 10" in overview.text
    assert 'action="/review/' not in overview.text
    assert "Affirm" not in overview.text
    cont = client.get("/review-ops/session/continue", follow_redirects=False)
    assert cont.status_code == 303
    assert cont.headers["location"].startswith("/source-fidelity/")
    assert "return_to=" in cont.headers["location"]
    resumed = client.get("/review-ops")
    assert "Resume review session" in resumed.text
    css = (Path(main.BASE_DIR) / "app" / "static" / "app.css").read_text(encoding="utf-8")
    assert ".review-session-form" in css
    assert "@media(max-width:834px)" in css
    from urllib.parse import quote
    stored = load_session(inbox)
    assert "paragraphs" not in json.dumps(stored)
    assert quote(CONTINUE_PATH, safe="") in stored["items"][0]["href"]


def test_empty_atomic_session_shows_explicit_disabled_extraction_copy(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    session = _create(inbox, "atomic", 5, atomic_drafts=[])
    assert session["status"] == "empty"
    view = present_session(session)
    assert view["empty_message"] == "No Atomic review batches available. Extraction remains disabled."


def test_empty_publication_session_has_queue_specific_copy(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    session = _create(inbox, "publication", 5)
    assert session["status"] == "empty"
    view = present_session(session)
    assert "publications" in view["empty_message"]


def test_recent_sessions_excludes_active_and_sorts_newest_first(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    _write(inbox / "evidence", _pub(0))
    _write(inbox / "evidence", _pub(1))

    first = _create(inbox, "publication", 5)
    stop_session(inbox, first)
    # Force distinct, ordered timestamps rather than relying on real-clock
    # second-level precision, which two fast-running creates could tie.
    first_path = inbox / "review_sessions" / f"{first['session_id']}.json"
    first_blob = json.loads(first_path.read_text(encoding="utf-8"))
    first_blob["created_at"] = "2026-01-01T00:00:00+00:00"
    first_path.write_text(json.dumps(first_blob), encoding="utf-8")

    _write(inbox / "evidence", _pub(2))
    second = _create(inbox, "atomic", 5, atomic_drafts=[])  # empty -> status "empty", not active
    second_path = inbox / "review_sessions" / f"{second['session_id']}.json"
    second_blob = json.loads(second_path.read_text(encoding="utf-8"))
    second_blob["created_at"] = "2026-06-01T00:00:00+00:00"
    second_path.write_text(json.dumps(second_blob), encoding="utf-8")

    history = list_recent_sessions(inbox)
    ids = [row["session_id"] for row in history]
    assert first["session_id"] in ids
    assert second["session_id"] in ids
    assert ids.index(second["session_id"]) < ids.index(first["session_id"])

    # A currently-active session must never appear in the history list --
    # Review Operations already shows it via its own separate resume card.
    third = _create(inbox, "publication", 5)
    assert third["status"] == "active"
    history_after = list_recent_sessions(inbox)
    assert third["session_id"] not in [row["session_id"] for row in history_after]


def test_recent_sessions_bounded_to_history_limit(tmp_path: Path) -> None:
    from app.services.review_session import HISTORY_LIMIT

    inbox = tmp_path / "inbox"
    for _ in range(HISTORY_LIMIT + 3):
        session = _create(inbox, "atomic", 5, atomic_drafts=[])
        assert session["status"] == "empty"
    history = list_recent_sessions(inbox)
    assert len(history) == HISTORY_LIMIT


def test_review_operations_route_shows_session_history(monkeypatch, tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    data = tmp_path / "data"
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "DATA_DIR", data)
    monkeypatch.setattr(main, "entity_index", lambda: ENTITIES)
    monkeypatch.setattr(main, "load_sources", lambda: list(SOURCES.values()))
    monkeypatch.setattr(main, "published_evidence", lambda: [])
    monkeypatch.setattr(main, "list_drafts", lambda: [])
    client = TestClient(main.app)

    session = _create(inbox, "atomic", 5, atomic_drafts=[])
    assert session["status"] == "empty"

    page = client.get("/review-ops")
    assert page.status_code == 200
    assert "Session history" in page.text
    assert "ATOMIC" in page.text
