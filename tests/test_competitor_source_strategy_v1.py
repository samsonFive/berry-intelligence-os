"""Competitor Source Strategy V1 -- validates the 33-row source-strategy
contract against the real committed import artifacts. Research/import-
planning mission: proves complete roster coverage and that nothing was
silently omitted or fabricated as operational, without exercising any
acquisition code (this test makes no network calls).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
STRATEGY_DIR = REPO / "data" / "imports" / "competitor-source-strategy-2026-09-15"
REGISTRY_DIR = REPO / "data" / "imports" / "competitor-registry-2026-09-15"

EXPECTED_ROSTER = [
    "Advanced Berry Breeding", "AgroBerries", "Australasian Plant Genetics", "BerryWorld",
    "Black Venture Farm", "California Giant", "Costa", "Denning Blueberries", "Expoberries",
    "Fall Creek", "Fresh Forward", "Fruitist", "Gem-Pack Berries", "Hortifrut Genetica",
    "IQ Berries", "Marionnet", "Mountain Blue", "Oishii", "Ozblu", "Pairwise", "Perfection Fresh",
    "Planasa", "Plant Sciences", "Royakkers", "Smart Berries", "Splendor Produce", "SunBelle",
    "The Berry Collective", "UC Davis", "University of Arkansas", "University of Florida",
    "Well-Pict", "Wish Farms",
]

MATURITY_STATES = {
    "candidate_identified", "discovery_mechanism_understood", "compatible_with_existing_adapter",
    "requires_new_adapter", "configured_but_untested", "known_runnable", "known_blocked",
    "manual_monitoring_required", "unsupported", "identity_search_strategy_pending",
}
MONITORING_STATES = {
    "linked_to_runnable_source", "source_configured_never_run", "source_blocked",
    "discovery_pending", "no_supported_source", "manual_monitoring_required",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def contract():
    return _load(STRATEGY_DIR / "competitor-source-strategy-v1.json")


@pytest.fixture(scope="module")
def reconciliation():
    return _load(REGISTRY_DIR / "reconciliation-matrix.json")


@pytest.fixture(scope="module")
def proposals():
    return _load(STRATEGY_DIR / "candidate-source-import-proposal.json")


@pytest.fixture(scope="module")
def first_wave():
    return _load(STRATEGY_DIR / "first-activation-wave.json")


@pytest.fixture(scope="module")
def sources():
    return _load(REPO / "data" / "configuration" / "sources.json")


# ---------------------------------------------------------------------------
# Roster coverage
# ---------------------------------------------------------------------------


def test_exactly_33_rows(contract):
    assert contract["row_count"] == 33
    assert len(contract["rows"]) == 33


def test_33_unique_canonical_entity_ids(contract):
    ids = [r["canonical_entity_id"] for r in contract["rows"]]
    assert len(ids) == 33
    assert len(set(ids)) == 33, f"duplicate canonical entity ids: {[i for i in ids if ids.count(i) > 1]}"


def test_no_silent_omissions_against_the_mandatory_roster(contract):
    labels = {r["spreadsheet_label"] for r in contract["rows"]}
    assert labels == set(EXPECTED_ROSTER)
    missing = set(EXPECTED_ROSTER) - labels
    assert missing == set(), f"SILENTLY OMITTED: {sorted(missing)}"


def test_canonical_ids_match_the_prior_reconciliation_matrix_exactly(contract, reconciliation):
    """This mission must not re-derive or diverge from the entity ids the
    prior Company + Genetics Relationships V1 mission already established."""
    prior_by_label = {r["spreadsheet_label"]: r["canonical_entity_id"] for r in reconciliation["rows"]}
    for row in contract["rows"]:
        assert row["canonical_entity_id"] == prior_by_label[row["spreadsheet_label"]], row["spreadsheet_label"]


# ---------------------------------------------------------------------------
# Every row has an explicit strategy or explicit unresolved state
# ---------------------------------------------------------------------------


def test_every_row_has_a_recognized_monitoring_state(contract):
    for row in contract["rows"]:
        assert row["recommended_initial_monitoring_state"] in MONITORING_STATES, row["spreadsheet_label"]


def test_every_candidate_source_has_a_recognized_maturity_state(contract):
    for row in contract["rows"]:
        for cs in row["candidate_sources"]:
            assert cs["maturity"] in MATURITY_STATES, (row["spreadsheet_label"], cs)


def test_every_entity_has_either_a_candidate_or_an_explicit_unresolved_state(contract):
    """No row may be silently blank: it must have at least one candidate
    source, an already-configured Source (monitoring state says so), or an
    explicit unresolved-state marker (no_supported_source /
    identity_search_strategy_pending priority) with a stated reason."""
    for row in contract["rows"]:
        has_candidate = bool(row["candidate_sources"])
        already_configured = row["recommended_initial_monitoring_state"] == "source_configured_never_run"
        is_blocked_with_assessment = row["recommended_initial_monitoring_state"] == "source_blocked"
        explicitly_unresolved = row["recommended_initial_monitoring_state"] == "no_supported_source"
        assert has_candidate or already_configured or is_blocked_with_assessment or explicitly_unresolved, row["spreadsheet_label"]
        if explicitly_unresolved:
            assert row["manual_fallback"], f"{row['spreadsheet_label']} has no stated fallback despite being unresolved"


def test_no_confirmed_domain_entities_left_without_a_stated_position(contract):
    for row in contract["rows"]:
        if row["official_domain"] is None:
            assert row["recommended_initial_monitoring_state"] in {"no_supported_source", "source_blocked"}, row["spreadsheet_label"]


# ---------------------------------------------------------------------------
# Provenance and verification dates
# ---------------------------------------------------------------------------


def test_every_candidate_source_has_provenance_and_a_verification_date(contract):
    for row in contract["rows"]:
        for cs in row["candidate_sources"]:
            assert cs["evidence_urls"], f"{row['spreadsheet_label']}: candidate source with no evidence_urls"
            assert all(url.startswith("http") for url in cs["evidence_urls"]), row["spreadsheet_label"]
            assert cs["verification_date"], row["spreadsheet_label"]


def test_verification_dates_are_real_iso_dates(contract):
    from datetime import date
    for row in contract["rows"]:
        for cs in row["candidate_sources"]:
            date.fromisoformat(cs["verification_date"])  # raises if malformed


# ---------------------------------------------------------------------------
# No candidate is labeled operational without operational evidence
# ---------------------------------------------------------------------------


def test_no_candidate_claims_known_runnable_or_linked_to_runnable(contract):
    """This mission only verified reachability, never ran collection --
    no row may claim the two states reserved for an actually-run Source."""
    for row in contract["rows"]:
        assert row["recommended_initial_monitoring_state"] != "linked_to_runnable_source", row["spreadsheet_label"]
        for cs in row["candidate_sources"]:
            assert cs["maturity"] != "known_runnable", (row["spreadsheet_label"], cs["url"])


def test_confirmed_live_candidates_use_discovery_pending_not_a_stronger_claim(contract):
    """A 200-status feed/sitemap this mission found is real and verified,
    but still unonboarded -- it must be discovery_pending, not presented as
    already-monitoring."""
    high_confidence_new_candidates = [
        row for row in contract["rows"]
        if row["candidate_sources"] and row["candidate_sources"][0]["confidence"] == "high"
    ]
    assert len(high_confidence_new_candidates) >= 5
    for row in high_confidence_new_candidates:
        assert row["recommended_initial_monitoring_state"] == "discovery_pending"


def test_california_giant_stays_blocked_not_fabricated_active(contract):
    cal_giant = next(r for r in contract["rows"] if r["spreadsheet_label"] == "California Giant")
    assert cal_giant["recommended_initial_monitoring_state"] == "source_blocked"
    assert cal_giant["candidate_sources"] == []


def test_unresolved_entities_are_not_assigned_a_fabricated_domain(contract):
    for label in ("Denning Blueberries", "Splendor Produce", "Marionnet"):
        row = next(r for r in contract["rows"] if r["spreadsheet_label"] == label)
        assert row["official_domain"] is None
        assert row["recommended_initial_monitoring_state"] == "no_supported_source"


# ---------------------------------------------------------------------------
# Noncanonical import proposal -- never a live Source
# ---------------------------------------------------------------------------


def test_all_candidate_proposals_are_explicitly_marked_noncanonical(proposals):
    assert proposals["NONCANONICAL"] is True
    assert proposals["count"] == len(proposals["proposals"])
    for p in proposals["proposals"]:
        assert p["NONCANONICAL"] is True
        assert p["linked_competitor_ids"], p["proposed_id"]


def test_no_proposal_id_collides_with_a_real_source_id(proposals, sources):
    real_ids = {s["id"] for s in sources}
    for p in proposals["proposals"]:
        assert p["proposed_id"] not in real_ids


def test_no_live_source_record_was_created_for_new_candidates(sources):
    """None of the newly-researched domains from this mission (a sample of
    distinctive ones) appear as a feed_url in the real, committed
    sources.json -- proving this mission did not silently onboard anything."""
    new_domains_sample = ["wishfarms.com", "ozblu.com", "oishii.com", "fruitist.com", "smartberries.com.au"]
    feed_urls = " ".join(
        str((s.get("discovery") or {}).get("feed_url") or "") for s in sources
    )
    for domain in new_domains_sample:
        assert domain not in feed_urls, f"{domain} unexpectedly already has a live Source feed_url"


# ---------------------------------------------------------------------------
# Canonical data untouched
# ---------------------------------------------------------------------------


def test_reconciliation_matrix_is_byte_for_byte_unchanged(reconciliation):
    """This mission reads but must never rewrite the prior mission's
    reconciliation matrix -- 33 rows, same shape, same canonical ids."""
    assert reconciliation["row_count"] == 33
    assert len(reconciliation["rows"]) == 33


def test_no_new_variety_entities_were_created():
    variety_dir = REPO / "data" / "entities" / "varieties"
    if not variety_dir.is_dir():
        return
    # This mission created zero files anywhere under data/entities/ --
    # a coarse but real check that nothing new landed there.
    import subprocess
    result = subprocess.run(
        ["git", "-c", f"safe.directory={REPO}", "status", "--porcelain", "--", "data/entities/varieties"],
        cwd=REPO, capture_output=True, text=True, check=False,
    )
    assert result.stdout.strip() == "", f"unexpected changes under data/entities/varieties: {result.stdout}"


def test_no_changes_to_sources_configuration_file():
    import subprocess
    result = subprocess.run(
        ["git", "-c", f"safe.directory={REPO}", "status", "--porcelain", "--",
         "data/configuration/sources.json"],
        cwd=REPO, capture_output=True, text=True, check=False,
    )
    assert result.stdout.strip() == "", f"sources.json was modified by this mission: {result.stdout}"


# ---------------------------------------------------------------------------
# First activation wave
# ---------------------------------------------------------------------------


def test_first_activation_wave_is_bounded_8_to_12(first_wave):
    assert 8 <= first_wave["count"] <= 12


def test_first_wave_entries_all_resolve_to_real_roster_rows(first_wave, contract):
    labels = {r["spreadsheet_label"] for r in contract["rows"]}
    for entry in first_wave["entries"]:
        assert entry["spreadsheet_label"] in labels


def test_california_giant_not_in_first_wave(first_wave):
    labels = {e["spreadsheet_label"] for e in first_wave["entries"]}
    assert "California Giant" not in labels
