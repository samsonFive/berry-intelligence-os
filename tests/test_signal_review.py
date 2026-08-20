"""Presentation for untrusted Signal candidates. Does not rewrite generation."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.signal_candidates import persist_candidates
from app.services.signal_review import (
    apply_and_persist_decision,
    emerging_signals,
    present_candidate,
    present_independence,
    present_review,
    present_stored_relationships,
    triage_groups,
)
from app.services.story_threads import THREAD_LINK_PREDICATES


PRIORITY = {
    dimension: {"level": "none", "rationale": ""}
    for dimension in ("reading", "testing", "commercial_position", "monitoring")
}


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _isolate(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    (tmp_path / "inbox" / "evidence").mkdir(parents=True, exist_ok=True)
    (tmp_path / "inbox" / "signal_candidates").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "configuration").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "signals").mkdir(parents=True, exist_ok=True)
    _write(tmp_path / "data" / "configuration" / "sources.json", [])


def _evidence(evidence_id: str, **overrides) -> dict:
    record = {
        "id": evidence_id,
        "record_type": "evidence",
        "status": "published",
        "review_state": "published",
        "source_type": "news_search",
        "title": f"Title {evidence_id}",
        "summary": "Published evidence fixture.",
        "why_it_matters": "Analyst-facing rationale.",
        "source_name": "Fruitnet",
        "source_url": f"https://example.invalid/{evidence_id}",
        "published_date": "2026-08-01",
        "captured_date": "2026-08-01",
        "submitted_by": "reviewer",
        "reviewed_by": "reviewer",
        "reviewed_at": "2026-08-01",
        "priority": deepcopy(PRIORITY),
        "entity_ids": ["company-hortifrut"],
        "berry_ids": ["berry-blueberry"],
        "tags": ["tier-1"],
        "evidence_links": [],
        "source_authority": "medium",
    }
    record.update(overrides)
    return record


def _candidate(**overrides) -> dict:
    record = {
        "id": "sigcand-multi-source-corroboration-hortifrut",
        "record_type": "signal_candidate",
        "status": "proposed",
        "pattern_type": "multi_source_corroboration",
        "primary_entity_id": "company-hortifrut",
        "entity_ids": ["company-hortifrut"],
        "berry_ids": ["berry-blueberry"],
        "supporting_evidence_ids": ["ev-a", "ev-b"],
        "independence": {
            "total_evidence_count": 2,
            "independent_source_count": 2,
            "clusters": [
                {"evidence_ids": ["ev-a"], "origin_label": "Hortifrut Newsroom"},
                {"evidence_ids": ["ev-b"], "origin_label": "FreshPlaza"},
            ],
        },
        "signal_confidence": "medium",
        "reason": "2 Evidence records naming company-hortifrut from 2 independently-originating sources.",
        "does_not_prove": [
            "that the underlying development is commercially significant",
            "market adoption, revenue impact, or strategic intent beyond what each source states",
        ],
        "reviewer": None,
        "review_notes": None,
    }
    record.update(overrides)
    return record


def _entities() -> dict[str, dict]:
    return {
        "company-hortifrut": {
            "id": "company-hortifrut",
            "entity_type": "company",
            "name": "Hortifrut",
            "status": "active",
        },
        "company-planasa": {
            "id": "company-planasa",
            "entity_type": "company",
            "name": "Planasa",
            "status": "active",
        },
    }


def _seed_repos(records: list[dict]) -> None:
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    for entity in _entities().values():
        payload = {"record_type": "entity", **entity}
        repos.entities.create(payload)
    for record in records:
        repos.evidence.create(record)


def test_duplicates_is_a_displayable_thread_link_predicate() -> None:
    assert "duplicates" in THREAD_LINK_PREDICATES


def test_emerging_signals_are_capped_and_skip_deferred() -> None:
    evidence = {
        "ev-a": _evidence("ev-a"),
        "ev-b": _evidence("ev-b", source_name="The Packer", published_date="2026-08-05"),
    }
    cards = []
    for index in range(10):
        candidate = _candidate(
            id=f"sigcand-{index}",
            status="proposed" if index < 9 else "deferred",
            signal_confidence="high" if index < 3 else "medium",
        )
        cards.append(
            present_candidate(candidate, evidence_by_id=evidence, entities=_entities(), today=date(2026, 8, 20))
        )
    emerging = emerging_signals(cards)
    assert 3 <= len(emerging) <= 7
    assert all(row["status"] == "proposed" for row in emerging)
    assert emerging[0]["confidence_label"] == "High"
    assert "0." not in emerging[0]["confidence_label"]


def test_emerging_brief_prefers_recent_review_now_over_stale_high_counts() -> None:
    recent = present_candidate(
        _candidate(id="sigcand-recent", signal_confidence="medium"),
        evidence_by_id={
            "ev-a": _evidence("ev-a", published_date="2026-08-18"),
            "ev-b": _evidence("ev-b", source_name="The Packer", published_date="2026-08-19"),
        },
        entities=_entities(),
        today=date(2026, 8, 20),
    )
    stale = present_candidate(
        _candidate(
            id="sigcand-stale-high",
            signal_confidence="high",
            independence={"total_evidence_count": 6, "independent_source_count": 6, "clusters": []},
        ),
        evidence_by_id={
            "ev-old-a": _evidence("ev-old-a", published_date="2019-01-01"),
            "ev-old-b": _evidence("ev-old-b", source_name="The Packer", published_date="2019-01-10"),
        },
        entities=_entities(),
        today=date(2026, 8, 20),
    )
    ordered = emerging_signals([stale, recent], limit=7)
    assert ordered[0]["id"] == "sigcand-recent"


def test_same_origin_three_documents_are_one_origin() -> None:
    evidence = {
        "ev-newsroom": _evidence(
            "ev-newsroom",
            source_name="Hortifrut Newsroom",
            source_id="source-hortifrut-newsroom",
            title="Hortifrut expands genetics platform",
        ),
        "ev-plaza": _evidence(
            "ev-plaza",
            source_name="FreshPlaza",
            title="Hortifrut genetics platform reprint",
        ),
        "ev-daily": _evidence(
            "ev-daily",
            source_name="HortiDaily",
            title="Hortifrut genetics platform reprint daily",
        ),
    }
    candidate = _candidate(
        supporting_evidence_ids=["ev-newsroom", "ev-plaza", "ev-daily"],
        independence={
            "total_evidence_count": 3,
            "independent_source_count": 1,
            "clusters": [
                {
                    "evidence_ids": ["ev-newsroom", "ev-plaza", "ev-daily"],
                    "origin_label": "Hortifrut Newsroom",
                }
            ],
        },
        pattern_type="primary_source_plus_followup",
        signal_confidence="low",
    )
    view = present_independence(candidate, evidence)
    assert view["headline"] == "3 documents · 1 independent origin"
    assert view["same_origin_collapsed"] is True
    assert view["clusters"][0]["origin_label"] == "Hortifrut Newsroom"
    assert [row["source_name"] for row in view["clusters"][0]["reprints"]] == ["FreshPlaza", "HortiDaily"]
    card = present_candidate(candidate, evidence_by_id=evidence, entities=_entities())
    assert card["triage_bucket"] == "same_origin_weak"


def test_relationships_are_stored_links_only() -> None:
    records = [
        _evidence(
            "ev-a",
            evidence_links=[
                {"predicate": "duplicates", "target_evidence_id": "ev-b", "status": "proposed"},
                {"predicate": "invented", "target_evidence_id": "ev-b", "status": "proposed"},
            ],
        ),
        _evidence("ev-b", source_name="FreshPlaza"),
    ]
    rows = present_stored_relationships(records, {record["id"]: record for record in records})
    assert [row["predicate_label"] for row in rows] == ["DUPLICATES"]


def test_review_now_requires_independent_origins() -> None:
    evidence = {
        "ev-a": _evidence("ev-a", published_date="2026-08-18"),
        "ev-b": _evidence("ev-b", source_name="The Packer", published_date="2026-08-19"),
    }
    strong = present_candidate(_candidate(), evidence_by_id=evidence, entities=_entities(), today=date(2026, 8, 20))
    weak = present_candidate(
        _candidate(
            id="sigcand-weak",
            pattern_type="primary_source_plus_followup",
            signal_confidence="low",
            independence={"total_evidence_count": 3, "independent_source_count": 1, "clusters": []},
        ),
        evidence_by_id=evidence,
        entities=_entities(),
        today=date(2026, 8, 20),
    )
    stale = present_candidate(
        _candidate(
            id="sigcand-stale",
            signal_confidence="high",
            supporting_evidence_ids=["ev-old-a", "ev-old-b"],
        ),
        evidence_by_id={
            "ev-old-a": _evidence("ev-old-a", published_date="2020-01-01"),
            "ev-old-b": _evidence("ev-old-b", source_name="The Packer", published_date="2020-01-10"),
        },
        entities=_entities(),
        today=date(2026, 8, 20),
    )
    groups = {group["key"]: group for group in triage_groups([strong, weak, stale])["buckets"]}
    assert strong["id"] in {row["id"] for row in groups["review_now"]["entries"]}
    assert weak["id"] in {row["id"] for row in groups["same_origin_weak"]["entries"]}
    assert stale["id"] in {row["id"] for row in groups["review_soon"]["entries"]}


def test_confirm_persists_candidate_and_does_not_write_trusted_signal(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    data = tmp_path / "data" / "signals"
    data.mkdir(parents=True)
    candidate = _candidate()
    persist_candidates([candidate], inbox_dir=inbox)
    updated = apply_and_persist_decision(
        candidate,
        decision="confirm",
        reviewer="analyst",
        notes="Boundaries accepted.",
        inbox_dir=inbox,
    )
    assert updated["status"] == "confirmed"
    saved = json.loads((inbox / "signal_candidates" / f"{candidate['id']}.json").read_text(encoding="utf-8"))
    assert saved["status"] == "confirmed"
    assert saved["reviewer"] == "analyst"
    assert list(data.glob("*.json")) == []
    persist_candidates([{**candidate, "status": "proposed"}], inbox_dir=inbox)
    saved_again = json.loads((inbox / "signal_candidates" / f"{candidate['id']}.json").read_text(encoding="utf-8"))
    assert saved_again["status"] == "confirmed"


def test_brief_and_reviewer_show_does_not_prove_before_confirm(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    _seed_repos(
        [
            _evidence("ev-a", title="Hortifrut newsroom genetics platform", source_name="Hortifrut Newsroom"),
            _evidence("ev-b", title="Trade coverage of Hortifrut genetics", source_name="The Packer", published_date="2026-08-10"),
        ]
    )
    persist_candidates([_candidate()], inbox_dir=main.INBOX_DIR)
    client = TestClient(app)
    brief = client.get("/brief")
    assert brief.status_code == 200
    html = brief.text
    assert "Emerging signals" in html
    assert "Emerging signal" in html
    assert "Does not prove" in html
    assert "Review signal" in html
    assert "0." not in html.split("Confidence")[1][:80]
    review = client.get("/signals/candidates/sigcand-multi-source-corroboration-hortifrut")
    assert review.status_code == 200
    body = review.text
    assert body.index("This does not prove") < body.index('value="confirm"')
    assert "Independence analysis" in body
    assert "Developing story" in body or "Related developing stories" in body or "Story thread" in body
    assert "CONFIRM" in body.upper() or "Confirm" in body
    assert "data/signals" not in body
    decision = client.post(
        "/signals/candidates/sigcand-multi-source-corroboration-hortifrut/decision",
        data={"decision": "defer", "reviewer": "analyst", "notes": "Need a second origin.", "return_to": "/brief"},
        follow_redirects=False,
    )
    assert decision.status_code == 303
    saved = json.loads(
        (main.INBOX_DIR / "signal_candidates" / "sigcand-multi-source-corroboration-hortifrut.json").read_text()
    )
    assert saved["status"] == "deferred"
    assert list((tmp_path / "data" / "signals").glob("*.json")) == []
    company = client.get("/entities/company/company-hortifrut")
    assert company.status_code == 200
    assert "Open signals" in company.text
    assert "Deferred" in company.text


def test_company_open_signals_and_watch_copy(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    monitoring = deepcopy(PRIORITY)
    monitoring["reading"] = {"level": "high", "rationale": "Watch Hortifrut."}
    monitoring["monitoring"] = {"level": "high", "rationale": "Watch Hortifrut."}
    _seed_repos(
        [
            _evidence(
                "ev-a",
                title="Hortifrut newsroom genetics platform",
                source_name="Hortifrut Newsroom",
                priority=monitoring,
            ),
            _evidence(
                "ev-b",
                title="Trade coverage of Hortifrut genetics",
                source_name="The Packer",
                published_date="2026-08-10",
                priority=monitoring,
            ),
        ]
    )
    persist_candidates([_candidate()], inbox_dir=main.INBOX_DIR)
    from app.services.morning_brief import build_morning_brief

    brief = build_morning_brief(
        inbox_dir=main.INBOX_DIR,
        published=main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR).evidence.list(),
        drafts=[],
        signals=[],
        entities=_entities(),
        berry_labels={"berry-blueberry": "Blueberry"},
        mark_seen=False,
    )
    assert brief["emerging_signals"]
    assert brief["emerging_signals"][0]["label"].startswith("Hortifrut:")
    watches = brief["watch_activity"]
    assert watches
    hortifrut = next(row for row in watches if row["id"] == "company-hortifrut")
    assert hortifrut["emerging_signal_count"] == 1
    assert "emerging signal" in hortifrut["happened"]
    assert "source" in hortifrut["happened"]


def test_static_brief_omits_inbox_candidates(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    persist_candidates([_candidate(id="sigcand-must-not-leak")], inbox_dir=tmp_path / "inbox")
    from app.services.morning_brief import build_morning_brief

    brief = build_morning_brief(
        inbox_dir=tmp_path / "inbox",
        published=[],
        drafts=[],
        signals=[],
        entities=_entities(),
        mark_seen=False,
        include_signal_candidates=False,
    )
    assert brief["emerging_signals"] == []
    assert "sigcand-must-not-leak" not in json.dumps(brief)
