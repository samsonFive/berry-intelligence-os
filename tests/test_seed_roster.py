"""Seed roster repair, reconcile, and competitor-count rules."""

from __future__ import annotations

from app.services.seed_roster import (
    build_roster,
    filter_roster,
    following_model,
    is_http_url,
    merge_entities_for_matching,
    normalize_name,
    official_social_channels,
    related_from_seed_note,
    repair_row,
    roster_counts,
    seed_profile,
    seed_track_id,
)


def _raw(**overrides):
    base = {
        "entity_id": "ORG-0004",
        "competitor_name": "Fall Creek Farm & Nursery",
        "aliases_legacy_names": "Fall Creek",
        "country_hq": "United States",
        "entity_type": "private company",
        "monitoring_status": "Active",
        "website": "https://www.fallcreeknursery.com/",
        "resolved_website": "https://www.fallcreeknursery.com/",
        "strawberry": False,
        "blueberry": True,
        "raspberry": False,
        "blackberry": False,
        "commercial_sales": True,
        "marketing": True,
        "technology": False,
        "genetics": True,
        "breeding": True,
        "monitoring_tier": "Tier 2",
        "verification_status": "Verified-secondary",
        "evidence_url": "https://example.test/evidence",
        "evidence_summary": "Nursery history page.",
        "logo_image_url": "https://www.fallcreeknursery.com/favicon.ico",
    }
    base.update(overrides)
    return base


def test_monitoring_status_urls_are_not_imported_as_status():
    row = repair_row(
        _raw(
            monitoring_status="https://www.openagrar.de/example.pdf",
            evidence_url="",
            verification_status="Candidate-review",
        )
    )
    assert row["monitoring_status"] == "watch"
    assert row["evidence_url"] == "https://www.openagrar.de/example.pdf"
    assert "monitoring_status_url" in row["repaired_fields"]
    assert row["candidate"] is True
    assert row["status"] == "unverified"
    assert row["verification_status"] == "candidate-review"


def test_resolved_website_is_not_official_domain():
    row = repair_row(
        _raw(
            website="",
            resolved_website="https://ars.usda.gov/program-page",
            verification_status="Candidate-review",
        )
    )
    assert row["official_website"] == ""
    assert row["resolved_website"] == "https://ars.usda.gov/program-page"
    assert "resolved_website_not_official" in row["repaired_fields"]
    assert all(watch["kind"] != "official_site" for watch in row["watches"])


def test_registries_are_excluded_from_competitor_counts():
    roster = [
        repair_row(_raw()),
        repair_row(
            _raw(
                entity_id="ORG-0147",
                competitor_name="Community Plant Variety Office (CPVO)",
                entity_type="registry/source system",
                verification_status="Verified-primary",
                website="https://cpvo.europa.eu/",
                monitoring_status="Active",
            )
        ),
    ]
    counts = roster_counts(roster)
    assert counts["seed_records"] == 2
    assert counts["tracked_companies"] == 1
    assert counts["registries"] == 1
    assert roster[1]["competitor"] is False
    assert roster[1]["is_registry"] is True
    visible = filter_roster(roster, include_registries=False)
    assert [row["canonical_name"] for row in visible] == ["Fall Creek Farm & Nursery"]


def test_reconcile_matches_trusted_company_and_does_not_overwrite():
    existing = [
        {
            "id": "company-fall-creek-farm-and-nursery",
            "entity_type": "company",
            "name": "Fall Creek Farm & Nursery, Inc.",
            "aliases": ["Fall Creek"],
            "status": "active",
        }
    ]
    roster = build_roster(existing, seed_path=None)
    # Use in-memory repair against the real seed file via build_roster, then find Fall Creek.
    matched = next(row for row in roster if "fall creek" in row["canonical_name"].casefold())
    assert matched["id"] == "company-fall-creek-farm-and-nursery"
    assert matched["trusted_entity_id"] == "company-fall-creek-farm-and-nursery"
    assert matched["verification_status"] in {"verified-secondary", "candidate-review"}
    # Trusted catalog identity stays on the existing id; seed does not invent a new company file.


def test_real_seed_tracks_one_hundred_plus_companies():
    roster = build_roster([])
    counts = roster_counts(roster)
    assert counts["seed_records"] == 151
    assert counts["tracked_companies"] >= 100
    assert counts["tracked_companies"] == 145
    assert counts["registries"] == 6
    assert counts["candidates"] == 61
    assert counts["monitoring_status_repaired"] == 61
    assert counts["mention_watches"] == 145
    assert all(not is_http_url(row["monitoring_status"]) for row in roster)
    candidates = [row for row in roster if row["candidate"]]
    assert candidates
    assert all(row["status"] == "unverified" for row in candidates)
    assert all(row["competitor"] is False for row in roster if row["is_registry"])


def test_following_model_and_seed_profile_use_repaired_rows():
    existing = [
        {
            "id": "company-driscolls",
            "entity_type": "company",
            "name": "Driscoll’s",
            "aliases": ["Driscolls"],
            "status": "active",
        }
    ]
    model = following_model(existing, crop="blueberry")
    assert model["counts"]["tracked_companies"] == 145
    assert all("blueberry" in row["crops"] for row in model["rows"])
    assert all(row["competitor"] for row in model["rows"])
    profile = seed_profile("company-driscolls", existing)
    assert profile is not None
    assert profile["id"] == "company-driscolls"
    seed_only = next(row for row in build_roster(existing) if not row.get("trusted_entity_id"))
    found = seed_profile(seed_only["id"], existing)
    assert found is not None
    assert found["id"] == seed_only["id"]
    assert found["id"].startswith("seed-")


def test_merge_entities_does_not_replace_trusted_records():
    existing = [
        {
            "id": "company-fall-creek-farm-and-nursery",
            "entity_type": "company",
            "name": "Fall Creek Farm & Nursery, Inc.",
            "aliases": ["Fall Creek"],
            "status": "active",
            "description": "trusted",
        }
    ]
    roster = build_roster(existing)
    merged = merge_entities_for_matching(existing, roster)
    trusted = next(row for row in merged if row["id"] == "company-fall-creek-farm-and-nursery")
    assert trusted["description"] == "trusted"
    assert trusted["status"] == "active"
    assert any(row["id"].startswith("seed-") for row in merged)


def test_nan_resolved_website_is_not_promoted():
    row = repair_row(_raw(website="", resolved_website=float("nan"), crawl_status=float("nan")))
    assert row["official_website"] == ""
    assert row["resolved_website"] == ""


def test_official_social_stays_unverified_discovery():
    row = repair_row(_raw(facebook_url="https://www.facebook.com/FallCreekNursery", instagram_url=""))
    channels = official_social_channels(row)
    assert channels == [
        {
            "platform": "facebook",
            "url": "https://www.facebook.com/FallCreekNursery",
            "official_status": "unverified",
            "coverage": "provider-unavailable",
            "source": "seed-discovery",
        }
    ]


def test_parent_successor_links_only_when_another_roster_name_appears():
    fall = repair_row(_raw())
    other = repair_row(
        _raw(
            entity_id="ORG-0006",
            competitor_name="Hortifrut",
            parent_or_successor="Expanded after a Fall Creek Farm & Nursery partnership note.",
        )
    )
    linked = related_from_seed_note(other, [fall, other])
    assert [row["name"] for row in linked] == ["Fall Creek Farm & Nursery"]
    assert related_from_seed_note(fall, [fall, other]) == []


def test_normalize_name_aligns_apostrophes_and_legal_suffixes():
    assert normalize_name("Driscoll’s") == normalize_name("Driscolls")
    assert normalize_name("Fall Creek Farm & Nursery, Inc.") == normalize_name("Fall Creek Farm and Nursery")
    assert seed_track_id("ORG-0004") == "seed-org-0004"
