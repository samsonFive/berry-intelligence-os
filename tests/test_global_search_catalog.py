"""Search the information catalog without review-based ranking or buckets."""

from app.services.global_search import SearchPools, search_global
from app.services.information_catalog import normalize_information


def _record(record_id, title, *, status="published", origin="data", **extra):
    return normalize_information({
        "id": record_id,
        "record_type": "evidence",
        "status": status,
        "title": title,
        "summary": "Summer harvest details",
        "published_date": "2026-11-12",
        **extra,
    }, origin=origin)


def _rows(payload):
    return [row for group in payload["groups"] if group["id"] == "intelligence"
            for row in [*group["in_context"], *group["also_global"]]]


def test_catalog_has_one_intelligence_group_and_no_review_rank_penalty():
    pools = SearchPools(evidence=[
        _record("ev-reviewed", "Zulu observation"),
        _record("ev-unreviewed", "Alpha observation", status="draft", origin="inbox", confidence="medium"),
    ])
    payload = search_global("harvest", pools, include_private=True, sort="relevance")
    rows = _rows(payload)
    assert [row["id"] for row in rows] == ["ev-unreviewed", "ev-reviewed"]
    assert rows[0]["rank"] == rows[1]["rank"]
    assert {row["review_status"] for row in rows} == {"reviewed", "unreviewed"}
    assert rows[0]["confidence"] == "medium"
    assert rows[0]["confidence_label"]
    assert rows[0]["state_label"] == "Unreviewed"
    assert [group["id"] for group in payload["groups"]] == ["intelligence"]


def test_unified_input_is_authoritative_and_empty_catalog_stays_empty():
    legacy = _record("ev-legacy", "Legacy harvest")
    pools = SearchPools(evidence=[], published_evidence=[legacy], pending_drafts=[legacy])
    assert _rows(search_global("harvest", pools, include_private=True)) == []


def test_private_export_boundary_is_independent_of_review_flags():
    pools = SearchPools(evidence=[
        _record("ev-public", "Public harvest", information={"review_status": "unreviewed"}),
        _record("ev-inbox", "Inbox harvest", origin="inbox"),
        _record("ev-draft", "Draft harvest", status="draft"),
    ])
    public = _rows(search_global("harvest", pools, include_private=False))
    live = _rows(search_global("harvest", pools, include_private=True))
    assert [row["id"] for row in public] == ["ev-public"]
    assert {row["id"] for row in live} == {"ev-public", "ev-inbox", "ev-draft"}
