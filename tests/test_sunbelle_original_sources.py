"""New source references preserve queue identity and separate human decisions."""
from copy import deepcopy
from pathlib import Path

from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios


DATA = Path(__file__).resolve().parents[1] / "data"
PREFIX = "portfolio-sunbelle-info-"


def test_sunbelle_checkpoint_preserves_previous_anchors_and_adds_only_erika():
    # This measures the SunBelle addition against its historical baseline. The
    # later cultivar register independently names Erika; removing her earlier
    # anchor and rebuilding from that later source is not a replay of this step.
    sources = [s for s in load_portfolio_observations(DATA)
               if not s["id"].startswith("portfolio-register52-2024-")]
    before = [s for s in sources if not s["id"].startswith(PREFIX)]
    _, old = reconcile_portfolios(sources=before, varieties=[], entities=[], candidates=[])
    rows, new = reconcile_portfolios(sources=sources, varieties=[], entities=[], candidates=[])
    by_name = {(c["berry_id"], c["candidate_name"]): c for c in new}
    assert all(by_name[(c["berry_id"], c["candidate_name"])]["id"] == c["id"] for c in old)
    assert len(new) == len(old) + 1
    assert set(by_name) - {(c["berry_id"], c["candidate_name"]) for c in old} == {("berry-raspberry", "Erika")}
    aketzali = by_name["berry-blackberry", "Aketzali"]
    assert {r["id"] for r in aketzali["portfolio_sources"]} == {
        "portfolio-blackventure-original-lowchill", PREFIX + "blackberry-origin"}
    erika = by_name["berry-raspberry", "Erika"]
    assert erika["source_url"] == "https://www.sunbelle.info/raspberries/19"
    assert not erika["human_gated"] and not erika["auto_confirmed"]
    assert not erika["aliases"] and not erika["proposed_relationships"]
    assert not erika["registration"]["official_registry_source"]
    batch = [s for s in rows if s["id"].startswith(PREFIX)]
    assert len(batch) == 3 and sum(len(s["names"]) for s in batch) == 2
    assert all(not s.get("published_date") for s in batch)
    assert all(not n.get("photos") for s in batch for n in s["names"])
    blueberry = next(s for s in batch if s["id"] == PREFIX + "blueberry-origin-gap")
    assert blueberry["capture_status"] == "partial" and blueberry["needs_follow_up"]


def test_current_erika_keeps_sunbelle_anchor_and_later_register_reference():
    _, candidates = reconcile_portfolios(sources=load_portfolio_observations(DATA), varieties=[], entities=[], candidates=[])
    erika = next(c for c in candidates if c["candidate_name"] == "Erika" and c["berry_id"] == "berry-raspberry")
    assert erika["source_id"] == PREFIX + "raspberry-origin"
    assert erika["source_url"] == "https://www.sunbelle.info/raspberries/19"
    assert {PREFIX + "raspberry-origin", "portfolio-register52-2024-raspberry-main"} <= {s["id"] for s in erika["portfolio_sources"]}
    assert not erika["human_gated"] and not erika["auto_confirmed"]


def test_new_source_cannot_replace_existing_human_identity_notes_or_photo_choice():
    sources = load_portfolio_observations(DATA)
    before = [s for s in sources if not s["id"].startswith(PREFIX)]
    _, old = reconcile_portfolios(sources=before, varieties=[], entities=[], candidates=[])
    human = deepcopy(next(c for c in old if c["candidate_name"] == "Aketzali" and c["berry_id"] == "berry-blackberry"))
    human.update(human_gated=True, status="rejected", identity_state="rejected",
                 review_notes="Operator decision", reviewer="Human",
                 aliases=["Operator spelling"], photos=[{"operator": "Retain choice"}])
    expected = deepcopy(human)
    rows, new = reconcile_portfolios(sources=list(reversed(sources)), varieties=[], entities=[], candidates=[human])
    saved = next(c for c in new if c["id"] == human["id"])
    for key in ("status", "identity_state", "human_gated", "review_notes", "reviewer", "aliases", "photos", "registration"):
        assert saved[key] == expected[key]
    assert human == expected
    for s in rows:
        for name in s["names"]:
            if name["candidate_name"] == "Aketzali" and name["berry_id"] == "berry-blackberry":
                assert name["candidate_id"] == human["id"]
                assert name["status"] == "previously_rejected" and not name["catalog_id"]
