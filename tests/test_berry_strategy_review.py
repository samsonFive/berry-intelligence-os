"""Scope, citation and approval boundaries for the four-crop Strategy Review."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import berry_strategy_review as strategy, living_workspaces as living
from app.services.berry_strategy_priorities import CRITERIA, load_opportunities
from app.services.global_berry_coverage import public_coverage


@pytest.fixture
def opportunities():
    cases = (
        ("blackberry", "north-america", (2, 1, 1, 1)),
        ("raspberry", "europe", (5, 5, 5, 4)),
        ("blueberry", "asia-pacific", (3, 3, 3, 2)),
        ("strawberry", "latin-america", (2, 2, 2, 2)),
    )
    return [
        {
            "id": f"fixture-{crop}-opportunity",
            "crop": crop,
            "region": region,
            "geography": "Fixture district",
            "target": "Private target sentinel",
            "entity_ids": [f"company-fixture-{crop}"],
            "title": f"Synthetic {crop} opportunity",
            "horizon": "Monitor",
            "roles": ["propagation"],
            "benefit": "Compare the measured outcomes.",
            "risk": "The comparison needs a second observation.",
            "confidence": "Low",
            "next_step": "Private diligence sentinel",
            "scores": {criterion: [rating, "Fixture score rationale."] for criterion, rating in zip(CRITERIA, ratings)},
            "frameworks": ["porter", "value_chain"],
            "contrary_source_ids": [f"fixture-{crop}-update"],
            "tension": "A second source limits the initial interpretation.",
            "sources": [
                [f"fixture-{crop}-circular", "Synthetic nursery circular", f"https://example.org/{crop}/circular",
                 "2026-06-15", "The nursery published a plant list.", ["propagation"]],
                [f"fixture-{crop}-update", "Synthetic nursery update", f"https://example.org/{crop}/update",
                 "2026-09-15", "The nursery confirmed a delivery window.", ["propagation"]],
            ],
        }
        for crop, region, ratings in cases
    ]


def snapshot(crop="", region="", *, opportunities=(), **filters):
    coverage = public_coverage(Path("data"), crop=crop, region=region, role=filters.get("role", ""))
    model = {"filters": {"crop": crop, "region": region, **filters}, "coverage": coverage}
    return strategy.snapshot_for(model, opportunities=opportunities)


def test_shortlist_is_scoped_and_missing_evidence_is_explicit(opportunities):
    full = snapshot(opportunities=opportunities)
    assert [row["crop"] for row in full["priorities"]] == ["raspberry", "blueberry", "strawberry", "blackberry"]
    assert [row["score"] for row in full["priorities"]] == [19, 11, 8, 5]
    assert 0 < len(full["gaps"]) < 160
    europe = snapshot("raspberry", "europe", opportunities=opportunities)
    assert [row["id"] for row in europe["priorities"]] == ["fixture-raspberry-opportunity"]
    assert all(row["crops"] == ["raspberry"] and row["regions"] == ["europe"] for row in europe["sources"].values())
    assert not snapshot("raspberry", "asia-pacific", opportunities=opportunities)["priorities"]
    recent = snapshot("raspberry", "europe", start="2026-07-01", opportunities=opportunities)
    assert "fixture-raspberry-update" in recent["sources"] and not recent["priorities"]
    assert not snapshot("raspberry", "europe", role="retail", opportunities=opportunities)["priorities"]
    assert not snapshot("raspberry", "europe", q="unmatched sentinel", opportunities=opportunities)["sources"]
    result = strategy.prepare(europe, focal="company-fixture-raspberry")
    assert not result["frameworks"]["vrio"]["entries"]
    assert "approved internal capability evidence" in result["frameworks"]["vrio"]["gap"]


def test_missing_private_shortlist_keeps_public_evidence_available(tmp_path):
    opportunities = load_opportunities(tmp_path)
    assert not opportunities
    basis = snapshot("raspberry", "europe", opportunities=opportunities)
    assert not basis["priorities"]
    assert basis["sources"]
    assert strategy.prepare(basis)["frameworks"]["value_chain"]["entries"]


def test_gateway_sends_only_public_snapshot_and_rejects_out_of_scope_ids(opportunities):
    observations = [
        {"id": "fixture-public-disclosure", "title": "Public nursery bulletin", "source_url": "https://example.org/bulletin",
         "claim": "The nursery described a limited catalog.", "crop": "raspberry", "region": "europe"},
        {"id": "fixture-public-limits", "title": "Public nursery catalog", "source_url": "https://example.org/catalog",
         "claim": "The catalog did not specify supply dates.", "crop": "raspberry", "region": "europe"},
    ]
    raspberry = next(row for row in opportunities if row["crop"] == "raspberry")
    raspberry["sources"][1][0] = "fixture-public-disclosure"
    model = {"filters": {"crop": "raspberry", "region": "europe"}, "coverage": {"observations": observations},
             "events": [{"crops": ["raspberry"], "regions": ["europe"], "sources": [
        {"id": "ev-private", "title": "Protected record", "summary": "Sensitive corpus context sentinel",
         "source_url": "https://example.com/source", "verification_state": "verified_primary"},
        {"id": "ev-disputed", "title": "Disputed record", "summary": "Disputed sentinel",
         "source_url": "https://example.com/disputed", "verification_state": "disputed"},
        {"id": "ev-other-region", "title": "Outside the region", "summary": "Another region's source was grouped into this event",
         "source_url": "https://example.com/other-region", "verification_state": "verified_primary", "regions": ["asia-pacific"]},
    ]}]}
    basis = strategy.snapshot_for(model, opportunities=opportunities)
    assert "ev-private" in basis["sources"] and "ev-disputed" not in basis["sources"]
    assert "ev-other-region" not in basis["sources"]
    assert "fixture-raspberry-circular" in basis["sources"]

    def completion(prompt, **kwargs):
        assert "Sensitive corpus context sentinel" not in prompt
        assert "ev-private" not in prompt
        assert "ev-disputed" not in prompt
        assert "Private target sentinel" not in prompt
        assert "Private diligence sentinel" not in prompt
        assert "Fixture score rationale" not in prompt
        assert "fixture-raspberry-opportunity" not in prompt
        assert "fixture-raspberry-circular" not in prompt
        assert "The nursery published a plant list." not in prompt
        assert "The nursery confirmed a delivery window." not in prompt
        packet = json.loads(prompt.split("\n", 1)[1])
        assert packet["scope"]["region"] == "europe"
        assert {row["id"] for row in packet["evidence"]} == {"fixture-public-disclosure", "fixture-public-limits"}
        return SimpleNamespace(provider="fixture", model="fixture", parsed={"assessments": [{
            "framework": "porter", "text": "Check access terms.", "limits": "Terms need confirmation.",
            "source_ids": ["fixture-public-disclosure"], "contrary_ids": ["fixture-public-limits"], "confidence": "Low",
        }]})

    accepted = strategy.prepare(basis, completer=completion)
    inference = accepted["frameworks"]["porter"]["entries"][-1]
    assert inference["kind"] == "AI inference"
    assert inference["contrary_ids"] == ["fixture-public-limits"]

    def wrong_source(prompt, **kwargs):
        result = completion(prompt, **kwargs)
        result.parsed["assessments"][0]["source_ids"] = ["ev-private"]
        return result

    rejected = strategy.prepare(basis, completer=wrong_source)
    assert rejected["method"] == "Local cited draft"
    assert "failed citation checks" in rejected["notice"]


def test_review_revisions_keep_basis_and_require_fresh_evidence(tmp_path, opportunities):
    store = living.Store(tmp_path)
    basis = snapshot("blackberry", "north-america", opportunities=opportunities)
    draft = strategy.save_draft(store, strategy.prepare(basis), "Analyst", 0)
    with pytest.raises(living.Conflict):
        strategy.save_draft(store, strategy.prepare(basis), "Analyst", 0)
    corrected = strategy.record_decision(store, basis, "Analyst", 1, "correct", "Check current propagators.",
                                         "value_chain", ["fixture-blackberry-circular"])
    approved = strategy.record_decision(store, basis, "Reviewer", 2, "approve", "Monitor only.")
    assert approved["state"] == "approved" and approved["corrections"] == corrected["corrections"]
    assert approved["snapshot"] == draft["snapshot"]
    assert [row["version"] for row in store.history(draft["id"])] == [3, 2, 1]
    basis["sources"]["fixture-blackberry-circular"]["summary"] += " Correction to underlying evidence."
    with pytest.raises(living.Conflict):
        strategy.record_decision(store, basis, "Reviewer", 3, "approve", "")


def test_overview_crop_routes_and_review_workflow(monkeypatch, tmp_path, opportunities):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.delenv("BIOS_BERRY_STRATEGY_PUBLIC_AI", raising=False)
    monkeypatch.setattr(main, "entity_index", lambda: {
        "company-fixture-raspberry": {"id": "company-fixture-raspberry", "name": "Fixture Nursery",
                                      "entity_type": "company", "berry_ids": ["berry-raspberry"]}
    })
    monkeypatch.setattr(main, "all_relationships", list)
    monkeypatch.setattr(main, "published_evidence", list)
    client = TestClient(main.app)
    empty = client.get("/landscapes/global/raspberry")
    assert empty.status_code == 200 and "Strategy Review" in empty.text
    assert "Synthetic raspberry opportunity" not in empty.text
    payload = tmp_path / "berry_strategy" / "opportunities.json"
    payload.parent.mkdir()
    payload.write_text(json.dumps(opportunities), encoding="utf-8")
    for crop in ("", "blueberry", "strawberry", "raspberry", "blackberry"):
        page = client.get("/landscapes/global" + (f"/{crop}" if crop else ""))
        assert page.status_code == 200 and "Strategy Review" in page.text
        assert "Ranked hypotheses" in page.text and "Insufficient evidence" in page.text
        for opportunity in opportunities:
            assert (opportunity["title"] in page.text) == (not crop or opportunity["crop"] == crop)
    assert not (tmp_path / "living_workspaces" / "workspace.sqlite3").exists()
    base = "/strategy-reviews/berries/raspberry"
    suffix = "?region=europe"
    response = client.post(base + "/refresh" + suffix, data={"version": "0", "method": "local", "focal": "company-fixture-raspberry"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].endswith("/raspberry?region=europe#berry-strategy-review")
    approval = client.post(base + "/review" + suffix, data={"version": "1", "action": "approve"}, follow_redirects=False)
    assert approval.status_code == 303
    approved = client.get(approval.headers["location"])
    assert "Approved priorities for this evidence snapshot" in approved.text
    assert "Synthetic raspberry opportunity" in approved.text
    history = client.get(base + "/history" + suffix + "&version=1")
    assert history.status_code == 200 and "Revision 2" in history.text and "Ranked hypotheses" in history.text
    assert client.post(base + "/refresh" + suffix, data={"version": "2", "method": "ai"}).status_code == 403
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    public = client.get("/landscapes/global/raspberry")
    assert "Strategy Review" not in public.text and "Synthetic raspberry opportunity" not in public.text
    assert client.get(base + "/history" + suffix).status_code == 403
