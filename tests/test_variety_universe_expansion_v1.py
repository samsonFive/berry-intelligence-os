"""Variety Universe Expansion V1: candidates, identity, coverage, static privacy."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.variety_universe.candidates import (
    apply_identity_decision,
    identity_issues_for_variety,
    load_variety_candidates,
)
from app.services.variety_universe.coverage import coverage_matrix
from app.services.variety_universe.identity import (
    STATE_CONFIRMED_SAME,
    STATE_DISTINCT,
    STATE_POSSIBLE_ALIAS,
    STATE_UNKNOWN,
    resolve_identity,
)
from app.services.variety_universe.registry_import import (
    build_candidate,
    import_registry_rows,
    load_registry_rows,
)


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "imports"
    / "variety-universe-eu-uk-sa-v1"
    / "registry_rows.json"
)


def _varieties() -> list[dict]:
    return [e for e in main.all_entities() if e.get("entity_type") == "variety"]


def test_existing_canonical_varieties_are_retained(tmp_path: Path) -> None:
    before = {e["id"] for e in _varieties()}
    assert "variety-last-call" in before
    assert len(before) >= 60
    import_registry_rows(load_registry_rows(FIXTURE), varieties=_varieties(), inbox_dir=tmp_path / "inbox")
    after = {e["id"] for e in _varieties()}
    assert after == before


def test_no_source_candidate_is_rejected() -> None:
    built = build_candidate(
        {"candidate_name": "Ghost Berry", "berry_id": "berry-blueberry"},
        varieties=_varieties(),
    )
    assert built["status"] == "rejected"
    assert built["identity_state"] == "rejected"


def test_exact_duplicate_is_possible_alias_not_new_canonical() -> None:
    last_call = next(v for v in _varieties() if v["id"] == "variety-last-call")
    built = build_candidate(
        {
            "candidate_name": last_call["name"],
            "berry_id": "berry-blueberry",
            "source_id": "source-cpvo-public-register",
            "source_url": "https://online.plantvarieties.eu/publicSearch?denomination=Last%20Call",
            "source_tier": "tier_1_registry",
            "jurisdiction": "EU (CPVO)",
        },
        varieties=_varieties(),
    )
    assert built["identity_state"] == STATE_POSSIBLE_ALIAS
    assert built["candidate_canonical_match"] == "variety-last-call"
    assert built["auto_confirmed"] is False


def test_breeder_code_and_trade_name_stay_distinct_without_human_merge() -> None:
    code = build_candidate(
        {
            "candidate_name": "FC11-164",
            "breeder_code": "FC11-164",
            "berry_id": "berry-blueberry",
            "source_id": "source-cpvo-public-register",
            "source_url": "https://online.plantvarieties.eu/publicSearch?denomination=FC11-164",
            "source_tier": "tier_1_registry",
            "jurisdiction": "EU (CPVO)",
        },
        varieties=_varieties(),
    )
    trade = build_candidate(
        {
            "candidate_name": "Last Call",
            "berry_id": "berry-blueberry",
            "source_id": "source-cpvo-public-register",
            "source_url": "https://online.plantvarieties.eu/publicSearch?denomination=Last%20Call",
            "source_tier": "tier_1_registry",
            "jurisdiction": "EU (CPVO)",
        },
        varieties=_varieties(),
    )
    assert code["identity_state"] == STATE_POSSIBLE_ALIAS
    assert code["candidate_canonical_match"] == "variety-fc11-164"
    assert trade["identity_state"] == STATE_POSSIBLE_ALIAS
    assert trade["candidate_canonical_match"] == "variety-last-call"
    assert code["candidate_canonical_match"] != trade["candidate_canonical_match"]
    assert code["auto_confirmed"] is False
    assert trade["auto_confirmed"] is False


def test_ambiguous_token_overlap_stays_unresolved() -> None:
    resolution = resolve_identity(
        {
            "candidate_name": "Fall Creek Last Call Selection Trial 11",
            "berry_id": "berry-blueberry",
        },
        _varieties(),
    )
    assert resolution["identity_state"] == STATE_UNKNOWN
    assert resolution["candidate_canonical_match"] is None
    assert resolution["auto_confirmed"] is False


def test_genuinely_new_variety_is_distinct() -> None:
    built = build_candidate(
        {
            "candidate_name": "Clery",
            "denomination": "Clery",
            "berry_id": "berry-strawberry",
            "source_id": "source-cpvo-public-register",
            "source_url": "https://online.plantvarieties.eu/publicSearch?denomination=Clery",
            "source_tier": "tier_1_registry",
            "jurisdiction": "EU (CPVO)",
            "application_number": "20021586",
            "grant_number": "16743",
            "applicant": "C.I.V. - Consorzio Italiano Vivaisti",
        },
        varieties=_varieties(),
    )
    assert built["identity_state"] == STATE_DISTINCT
    assert built["candidate_canonical_match"] is None


def test_missing_owner_and_missing_geography_are_allowed() -> None:
    built = build_candidate(
        {
            "candidate_name": "Natchez",
            "berry_id": "berry-blackberry",
            "source_id": "source-cpvo-public-register",
            "source_url": "https://online.plantvarieties.eu/publicSearch?denomination=Natchez",
            "source_tier": "tier_1_registry",
            "jurisdiction": "EU (CPVO)",
        },
        varieties=_varieties(),
    )
    assert built["breeder_owner"] == ""
    assert built["geography_id"] == ""
    assert built["status"] == "proposed"


def test_registration_and_multi_jurisdiction_rows_in_pilot_fixture() -> None:
    rows = load_registry_rows(FIXTURE)
    assert len(rows) >= 40
    eu = [r for r in rows if r.get("jurisdiction") == "EU (CPVO)" and r.get("application_number")]
    uk = [r for r in rows if r.get("jurisdiction") == "United Kingdom"]
    za = [r for r in rows if r.get("jurisdiction") == "South Africa"]
    assert eu
    assert uk
    assert za
    malling = [r for r in rows if r.get("candidate_name") == "Malling Centenary"]
    jurisdictions = {r.get("jurisdiction") for r in malling}
    assert "EU (CPVO)" in jurisdictions
    assert "United Kingdom" in jurisdictions


def test_commercial_deployment_is_proposed_not_trusted() -> None:
    rows = load_registry_rows(FIXTURE)
    sa = next(r for r in rows if r.get("jurisdiction") == "South Africa")
    assert sa.get("deployment")
    assert sa["deployment"]["status"] == "unknown"
    assert (sa.get("proposed_relationships") or [])[0]["status"] == "proposed"


def test_import_writes_inbox_only(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    result = import_registry_rows(load_registry_rows(FIXTURE), varieties=_varieties(), inbox_dir=inbox)
    assert result["written_count"] >= 40
    assert result["distinct_new"] >= 20
    assert (inbox / "variety_candidates").is_dir()
    trusted_ids = {e["id"] for e in _varieties()}
    for path in (inbox / "variety_candidates").glob("*.json"):
        assert path.stem not in trusted_ids


def test_identity_decision_does_not_write_canonical(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    import_registry_rows(load_registry_rows(FIXTURE), varieties=_varieties(), inbox_dir=inbox)
    candidates = load_variety_candidates(inbox)
    match = next(c for c in candidates if c.get("candidate_canonical_match") == "variety-last-call")
    updated = apply_identity_decision(match, decision=STATE_CONFIRMED_SAME, reviewer="analyst")
    assert updated["identity_state"] == STATE_CONFIRMED_SAME
    assert updated["human_gated"] is True
    assert "variety-last-call" in {e["id"] for e in _varieties()}
    last_call = next(e for e in _varieties() if e["id"] == "variety-last-call")
    assert "Clery" not in (last_call.get("aliases") or [])


def test_human_cannot_auto_confirm_without_match() -> None:
    candidate = {
        "id": "vcand-x",
        "identity_state": STATE_DISTINCT,
        "candidate_canonical_match": None,
    }
    try:
        apply_identity_decision(candidate, decision=STATE_CONFIRMED_SAME, reviewer="analyst")
    except Exception as exc:
        assert "canonical match" in str(exc)
    else:
        raise AssertionError("confirmed_same without match should fail")


def test_get_coverage_does_not_mutate_candidates(tmp_path: Path, monkeypatch) -> None:
    inbox = tmp_path / "inbox"
    import_registry_rows(load_registry_rows(FIXTURE), varieties=_varieties(), inbox_dir=inbox)
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    before = [p.read_text(encoding="utf-8") for p in sorted((inbox / "variety_candidates").glob("*.json"))]
    page = TestClient(app).get("/varieties/coverage")
    assert page.status_code == 200
    assert "Variety coverage" in page.text
    assert "completeness score" in page.text.lower() or "not a completeness score" in page.text
    after = [p.read_text(encoding="utf-8") for p in sorted((inbox / "variety_candidates").glob("*.json"))]
    assert after == before
    assert "name=\"decision\"" not in page.text


def test_get_candidates_does_not_mutate(tmp_path: Path, monkeypatch) -> None:
    inbox = tmp_path / "inbox"
    import_registry_rows(load_registry_rows(FIXTURE), varieties=_varieties(), inbox_dir=inbox)
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    before = [p.read_text(encoding="utf-8") for p in sorted((inbox / "variety_candidates").glob("*.json"))]
    page = TestClient(app).get("/varieties/candidates")
    assert page.status_code == 200
    assert "Clery" in page.text
    after = [p.read_text(encoding="utf-8") for p in sorted((inbox / "variety_candidates").glob("*.json"))]
    assert after == before


def test_coverage_matrix_counts_canonical_and_candidates(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    import_registry_rows(load_registry_rows(FIXTURE), varieties=_varieties(), inbox_dir=inbox)
    matrix = coverage_matrix(
        varieties=_varieties(),
        entities=main.all_entities(),
        relationships=main.all_relationships(),
        published_evidence=main.published_evidence(),
        facts=main.all_facts(),
        candidates=load_variety_candidates(inbox),
    )
    assert matrix["totals"]["canonical_varieties"] == len(_varieties())
    assert matrix["totals"]["candidates"] >= 40
    assert matrix["totals"]["unresolved_aliases"] >= 1
    blueberry = next(row for row in matrix["by_berry"] if row["id"] == "berry-blueberry")
    assert blueberry["canonical_varieties"] >= 40
    assert any(row["id"] == "eu" for row in matrix["by_geography"])
    assert any(row["known_canonical_varieties"] >= 1 for row in matrix["by_breeder"])


def test_variety_profile_compare_and_timeline_still_render() -> None:
    client = TestClient(app)
    detail = client.get("/entities/variety/variety-last-call")
    assert detail.status_code == 200
    assert "Last Call" in detail.text
    compare = client.get("/entities/variety/compare?ids=variety-last-call,variety-keepsake")
    assert compare.status_code == 200
    timeline = client.get("/entities/variety/variety-last-call")
    assert "Intelligence timeline" in timeline.text or "Recent intelligence" in timeline.text


def test_identity_issues_surface_on_live_profile(tmp_path: Path, monkeypatch) -> None:
    inbox = tmp_path / "inbox"
    import_registry_rows(load_registry_rows(FIXTURE), varieties=_varieties(), inbox_dir=inbox)
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    issues = identity_issues_for_variety("variety-last-call", load_variety_candidates(inbox))
    assert issues
    page = TestClient(app).get("/entities/variety/variety-last-call")
    assert page.status_code == 200
    assert "Unresolved identity issues" in page.text


def test_historical_vs_current_deployment_unknown_is_explicit() -> None:
    rows = load_registry_rows(FIXTURE)
    za = next(r for r in rows if r.get("jurisdiction") == "South Africa" and r.get("deployment"))
    assert za["deployment"]["status"] in {"unknown", "current", "historical"}
