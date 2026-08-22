"""Claim Testing V2: disposition overlay, evidence chain, no Fact publication."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.analyst_queue import load_state
from app.services.claim_testing import (
    build_testing_detail,
    build_testing_workspace,
    evidence_chain,
    independence_note,
)
from app.services import variety_footprint as footprint_mod
from app.services.story_threads import group_story_threads


PRIORITY = {
    dimension: {"level": "none", "rationale": ""}
    for dimension in ("reading", "testing", "commercial_position", "monitoring")
}


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _isolate(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    (tmp_path / "inbox" / "evidence").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "evidence").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "entities").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "facts").mkdir(parents=True, exist_ok=True)


def _published(record_id: str, **overrides) -> dict:
    record = {
        "id": record_id,
        "record_type": "evidence",
        "status": "published",
        "review_state": "published",
        "source_type": "trade_press",
        "source_name": "FreshPlaza",
        "source_id": "source-freshplaza",
        "source_url": "https://example.invalid/" + record_id,
        "title": f"Trusted {record_id}",
        "published_date": "2026-08-10",
        "captured_date": "2026-08-10",
        "summary": "Exact source wording for the claim under test.",
        "why_it_matters": "Shelf-life numbers have no method.",
        "submitted_by": "reviewer",
        "reviewed_by": "reviewer",
        "reviewed_at": "2026-08-10",
        "priority": deepcopy(PRIORITY),
        "berry_ids": ["berry-blueberry"],
        "entity_ids": ["company-hortifrut", "variety-example-blue", "geography-peru"],
        "fact_ids": [],
        "evidence_links": [],
    }
    record.update(overrides)
    return record


def _entity(entity_id: str, entity_type: str, name: str) -> dict:
    return {
        "id": entity_id,
        "record_type": "entity",
        "entity_type": entity_type,
        "name": name,
        "status": "active",
    }


def _seed(repos, records: list[dict], entities: list[dict] | None = None, facts: list[dict] | None = None) -> None:
    for entity in entities or [
        _entity("company-hortifrut", "company", "Hortifrut"),
        _entity("variety-example-blue", "variety", "Example Blue"),
        _entity("geography-peru", "geography", "Peru"),
    ]:
        repos.entities.create(entity)
    for fact in facts or []:
        repos.facts.create(fact)
    for record in records:
        repos.evidence.create(record)


def test_live_testing_queue_is_v2_and_preserves_trust_copy() -> None:
    page = TestClient(app).get("/queues/testing")
    assert page.status_code == 200
    html = page.text
    assert "v2-page" in html
    assert "v2-testing" in html
    assert "Claim testing" in html
    assert "not Learner Mode" in html
    assert "do not publish a Fact" in html.casefold() or "not a Fact" in html
    assert "not model-qualification" in html
    assert "Needs testing" in html
    assert "Decide" in html
    assert ">Claim testing<" in html
    assert 'id="v2ReaderOffcanvas"' in html
    assert "Example breeder announces" in html
    assert "Patent published" not in html
    assert "Learner topic" not in html
    assert "Explain this concept" not in html or "not built" in html


def test_live_claim_detail_keeps_source_wording_and_entity_routes() -> None:
    page = TestClient(app).get("/queues/testing/ev-producereport-blugenix-2026")
    assert page.status_code == 200
    html = page.text
    assert "Source claim" in html
    assert "Normalized claims" in html
    assert "Supporting evidence" in html
    assert "Contradicting evidence" in html
    assert "Analyst conclusion" in html
    assert "not a Fact" in html.casefold() or "NOT A FACT" in html
    assert "Costa claims a shelf life of 27 days" in html
    assert "Exact source wording" not in html or "Reports the launch of BluGenix" in html
    assert "Reports the launch of BluGenix" in html
    assert "/entities/company/company-costa-group-holdings" in html
    assert "/entities/variety/variety-eterna" in html
    assert "data-open-reader" in html
    assert "Open full reader" in html
    assert "Creates a Fact?" in html
    assert "No" in html
    assert "Learner Mode" in html
    assert "No supporting Evidence links are recorded" in html
    assert "No contradicting Evidence links are recorded" in html


def test_testing_queue_404_for_untagged_evidence() -> None:
    response = TestClient(app).get("/queues/testing/ev-sample-patent-published")
    assert response.status_code == 404


def test_pass_does_not_publish_or_mutate_evidence(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    priority = deepcopy(PRIORITY)
    priority["testing"] = {"level": "high", "rationale": "Shelf life needs a trial."}
    _seed(
        repos,
        [_published("ev-test-claim", title="Claim fixture one", priority=priority, fact_ids=["fact-test-claim"])],
        facts=[
            {
                "id": "fact-test-claim",
                "record_type": "fact",
                "statement": "Breeder claims 40-day shelf life.",
                "classification": "claim",
                "confidence": "low",
                "status": "active",
                "reviewer": "fixture",
                "created_at": "2026-08-10",
                "evidence_ids": ["ev-test-claim"],
            }
        ],
    )
    client = TestClient(app)
    page = client.get("/queues/testing")
    assert "Claim fixture one" in page.text
    assert "Need testing" in page.text or "need testing" in page.text
    posted = client.post(
        "/queues/testing/ev-test-claim",
        data={"action": "pass", "reviewer": "analyst-fixture", "return_to": "/queues/testing/ev-test-claim"},
        follow_redirects=False,
    )
    assert posted.status_code == 303
    assert posted.headers["location"] == "/queues/testing/ev-test-claim"
    hidden = client.get("/queues/testing")
    assert "Claim fixture one" not in hidden.text
    detail = client.get("/queues/testing/ev-test-claim")
    assert detail.status_code == 200
    assert "Pass" in detail.text
    assert "Creates a Fact?" in detail.text
    assert "Breeder claims 40-day shelf life." in detail.text
    assert repos.evidence.get("ev-test-claim")["status"] == "published"
    assert repos.facts.get("fact-test-claim")["classification"] == "claim"
    assert load_state(main.INBOX_DIR)["testing"]["ev-test-claim"]["state"] == "pass"


def test_evidence_chain_keeps_support_and_contradiction_distinct(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    priority = deepcopy(PRIORITY)
    priority["testing"] = {"level": "high", "rationale": "Needs independent trial."}
    source = _published(
        "ev-source-claim",
        title="Source claim article",
        priority=priority,
        evidence_links=[
            {
                "predicate": "corroborates",
                "target_evidence_id": "ev-support-1",
                "status": "accepted",
                "notes": "Same trial cited.",
            }
        ],
    )
    support = _published(
        "ev-support-1",
        title="Independent trial write-up",
        source_name="Fruitnet",
        source_id="source-fruitnet",
    )
    contradiction = _published(
        "ev-contradict-1",
        title="Later article disputes the figure",
        source_name="The Packer",
        source_id="source-packer",
        evidence_links=[
            {
                "predicate": "contradicts",
                "target_evidence_id": "ev-source-claim",
                "status": "proposed",
                "notes": "Different season, lower shelf life.",
            }
        ],
    )
    same_source = _published(
        "ev-same-source",
        title="Reprint of the same claim",
        source_name="FreshPlaza",
        source_id="source-freshplaza",
        evidence_links=[
            {
                "predicate": "corroborates",
                "target_evidence_id": "ev-source-claim",
                "status": "accepted",
            }
        ],
    )
    _seed(repos, [source, support, contradiction, same_source])
    client = TestClient(app)
    detail = client.get("/queues/testing/ev-source-claim")
    html = detail.text
    assert "Independent trial write-up" in html
    assert "Later article disputes the figure" in html
    assert "Reprint of the same claim" in html
    assert "Supporting evidence" in html
    assert "Contradicting evidence" in html
    assert "Same Source — not independent corroboration" in html
    assert "Linked Facts" in html
    assert "does not publish a Fact" in html
    assert "/entities/company/company-hortifrut" in html
    assert "/entities/variety/variety-example-blue" in html
    assert "data-open-reader" in html
    published = {row["id"]: row for row in [source, support, contradiction, same_source]}
    chain = evidence_chain(source, published)
    assert [row["id"] for row in chain["supporting"]] == ["ev-support-1", "ev-same-source"]
    assert [row["id"] for row in chain["contradicting"]] == ["ev-contradict-1"]
    assert independence_note(source, same_source)


def test_filters_use_real_entity_and_state_dimensions(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    high = deepcopy(PRIORITY)
    high["testing"] = {"level": "high", "rationale": "A"}
    low = deepcopy(PRIORITY)
    low["testing"] = {"level": "low", "rationale": "B"}
    _seed(
        repos,
        [
            _published("ev-a", title="Hortifrut claim", priority=high),
            _published(
                "ev-b",
                title="Other company claim",
                priority=low,
                entity_ids=["company-other", "geography-chile"],
                source_name="Produce Report",
            ),
        ],
        entities=[
            _entity("company-hortifrut", "company", "Hortifrut"),
            _entity("variety-example-blue", "variety", "Example Blue"),
            _entity("geography-peru", "geography", "Peru"),
            _entity("company-other", "company", "Other Co"),
            _entity("geography-chile", "geography", "Chile"),
        ],
    )
    client = TestClient(app)
    filtered = client.get("/queues/testing", params={"company": "company-hortifrut"})
    assert "Hortifrut claim" in filtered.text
    assert "Other company claim" not in filtered.text
    assert 'name="company"' in filtered.text
    assert 'name="variety"' in filtered.text
    assert "decorative" not in filtered.text


def test_testing_pages_skip_expensive_paths(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    priority = deepcopy(PRIORITY)
    priority["testing"] = {"level": "medium", "rationale": "Check it."}
    _seed(repos, [_published("ev-cheap", title="Cheap claim", priority=priority)])
    brief_calls: list[str] = []
    semantics_calls: list[str] = []
    search_calls: list[str] = []
    footprint_calls: list[str] = []
    thread_calls: list[str] = []
    discovered_calls: list[str] = []

    original_brief = main.build_morning_brief
    original_semantics = main.annotate_feed_semantics
    original_search = main.build_search_documents
    original_fp = footprint_mod.variety_footprint
    original_threads = group_story_threads
    original_discovered = main.list_discovered_items

    def wrap_brief(*args, **kwargs):
        brief_calls.append(str(kwargs.get("mode") or "full"))
        return original_brief(*args, **kwargs)

    def wrap_semantics(*args, **kwargs):
        semantics_calls.append("called")
        return original_semantics(*args, **kwargs)

    def wrap_search(*args, **kwargs):
        search_calls.append("called")
        return original_search(*args, **kwargs)

    def wrap_fp(*args, **kwargs):
        footprint_calls.append("called")
        return original_fp(*args, **kwargs)

    def wrap_threads(*args, **kwargs):
        thread_calls.append("called")
        return original_threads(*args, **kwargs)

    def wrap_discovered(*args, **kwargs):
        discovered_calls.append("called")
        return original_discovered(*args, **kwargs)

    monkeypatch.setattr(main, "build_morning_brief", wrap_brief)
    monkeypatch.setattr(main, "annotate_feed_semantics", wrap_semantics)
    monkeypatch.setattr(main, "build_search_documents", wrap_search)
    monkeypatch.setattr(footprint_mod, "variety_footprint", wrap_fp)
    monkeypatch.setattr("app.services.variety_workspace.variety_footprint", wrap_fp)
    monkeypatch.setattr("app.services.story_threads.group_story_threads", wrap_threads)
    monkeypatch.setattr(main, "list_discovered_items", wrap_discovered)
    client = TestClient(app)
    assert client.get("/queues/testing").status_code == 200
    assert client.get("/queues/testing/ev-cheap").status_code == 200
    assert brief_calls == []
    assert semantics_calls == []
    assert search_calls == []
    assert footprint_calls == []
    assert thread_calls == []
    assert discovered_calls == []


def test_workspace_builder_preserves_real_states_only() -> None:
    priority = deepcopy(PRIORITY)
    priority["testing"] = {"level": "high", "rationale": "Try it."}
    records = [_published("ev-one", priority=priority)]
    state = {"testing": {"ev-one": {"state": "defer", "reviewer": "a", "updated_at": "2026-08-22"}}}
    page = build_testing_workspace(
        records=records,
        state=state,
        entities={
            "company-hortifrut": _entity("company-hortifrut", "company", "Hortifrut"),
            "variety-example-blue": _entity("variety-example-blue", "variety", "Example Blue"),
            "geography-peru": _entity("geography-peru", "geography", "Peru"),
        },
        berry_labels=main.BERRIES,
        show_completed=True,
    )
    keys = [bucket["key"] for bucket in page["buckets"]]
    assert keys == ["needs_testing", "pass", "fail", "defer"]
    assert "supported" not in keys
    assert "contradicted" not in keys
    assert page["buckets"][-1]["count"] == 1
    detail = build_testing_detail(
        records[0],
        state=state,
        entities={"company-hortifrut": _entity("company-hortifrut", "company", "Hortifrut")},
        berry_labels=main.BERRIES,
    )
    assert detail["analyst_conclusion"]["creates_fact"] is False
    assert detail["analyst_conclusion"]["state"] == "defer"
