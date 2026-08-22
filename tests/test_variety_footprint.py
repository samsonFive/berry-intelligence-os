"""Variety Commercial Footprint -- Variety Intelligence Backbone V1.

Fixtures are synthetic but shaped exactly like real records (mirroring the
real variety-drisblueseventeen / Zara / Victoria cases discovered during
the mission) -- no live data or network access.
"""

from __future__ import annotations

from app.services.variety_footprint import (
    competing_varieties_in_berry_market,
    variety_footprint,
    varieties_observed_in_market,
    varieties_with_ip_activity_and_commercial_observation,
)


def _entities():
    return [
        {"id": "company-driscolls", "record_type": "entity", "entity_type": "company", "name": "Driscoll's, Inc.", "status": "active"},
        {"id": "company-other", "record_type": "entity", "entity_type": "company", "name": "Other Co", "status": "active"},
        {
            "id": "variety-x17",
            "record_type": "entity",
            "entity_type": "variety",
            "name": "X17",
            "berry_ids": ["berry-blueberry"],
            "status": "active",
        },
        {
            "id": "variety-y1",
            "record_type": "entity",
            "entity_type": "variety",
            "name": "Y1",
            "berry_ids": ["berry-raspberry"],
            "status": "active",
        },
        {"id": "geography-united-kingdom", "record_type": "entity", "entity_type": "geography", "name": "United Kingdom", "status": "active"},
        {"id": "retailer-tesco", "record_type": "entity", "entity_type": "retailer", "name": "Tesco", "status": "active"},
    ]


def _relationships():
    return [
        {
            "id": "rel-driscolls-develops-x17",
            "record_type": "relationship",
            "subject_id": "company-driscolls",
            "predicate": "develops",
            "object_id": "variety-x17",
            "status": "active",
            "evidence_ids": ["ev-pvr-x17"],
        },
        {
            "id": "rel-driscolls-owns-x17",
            "record_type": "relationship",
            "subject_id": "company-driscolls",
            "predicate": "owns",
            "object_id": "variety-x17",
            "status": "active",
            "evidence_ids": ["ev-pvr-x17"],
        },
        {
            "id": "rel-other-markets-y1",
            "record_type": "relationship",
            "subject_id": "company-other",
            "predicate": "markets",
            "object_id": "variety-y1",
            "status": "active",
            "evidence_ids": ["ev-obs-y1"],
        },
    ]


def _published():
    return [
        {
            "id": "ev-pvr-x17",
            "record_type": "evidence",
            "status": "published",
            "source_type": "plant_breeders_rights_record",
            "title": "PVR grant for X17",
            "published_date": "2024-01-01",
            "entity_ids": ["company-driscolls", "variety-x17"],
        }
    ]


def _drafts():
    return [
        {
            "id": "ev-obs-x17-uk",
            "record_type": "evidence",
            "status": "draft",
            "source_type": "field_observation",
            "intake_type": "commercial_observation",
            "captured_date": "2026-05-01",
            "geography_ids": ["geography-united-kingdom"],
            "entity_ids": ["variety-x17", "retailer-tesco"],
            "commercial_observation": {
                "retailer_entity_id": "retailer-tesco",
                "variety_entity_id": "variety-x17",
                "market_country": "United Kingdom",
                "observed_at": "2026-05-01",
            },
        },
        {
            "id": "ev-obs-x17-uk-later",
            "record_type": "evidence",
            "status": "draft",
            "source_type": "field_observation",
            "intake_type": "commercial_observation",
            "captured_date": "2026-07-01",
            "geography_ids": ["geography-united-kingdom"],
            "entity_ids": ["variety-x17", "retailer-tesco"],
            "commercial_observation": {
                "retailer_entity_id": "retailer-tesco",
                "variety_entity_id": "variety-x17",
                "market_country": "United Kingdom",
                "observed_at": "2026-07-01",
            },
        },
        {
            "id": "ev-obs-y1-uk",
            "record_type": "evidence",
            "status": "draft",
            "source_type": "field_observation",
            "intake_type": "commercial_observation",
            "captured_date": "2026-06-01",
            "geography_ids": ["geography-united-kingdom"],
            "entity_ids": ["variety-y1", "retailer-tesco"],
            "commercial_observation": {
                "retailer_entity_id": "retailer-tesco",
                "variety_entity_id": "variety-y1",
                "market_country": "United Kingdom",
                "observed_at": "2026-06-01",
            },
        },
    ]


def test_footprint_keeps_breeder_and_owner_as_separate_buckets_for_same_company() -> None:
    fp = variety_footprint(
        "variety-x17",
        entities=_entities(),
        relationships=_relationships(),
        published_evidence=_published(),
        inbox_drafts=_drafts(),
    )
    assert fp["roles"]["breeder"] == ["company-driscolls"]
    assert fp["roles"]["owner_rights_holder"] == ["company-driscolls"]
    assert fp["roles"]["marketer"] == []
    assert fp["rights_filings"]["published"][0]["id"] == "ev-pvr-x17"


def test_footprint_derives_first_and_latest_observed_and_marks_trust() -> None:
    fp = variety_footprint(
        "variety-x17",
        entities=_entities(),
        relationships=_relationships(),
        published_evidence=_published(),
        inbox_drafts=_drafts(),
    )
    assert fp["first_observed"] == "2026-05-01"
    assert fp["latest_observed"] == "2026-07-01"
    assert fp["countries_observed"] == ["geography-united-kingdom"]
    assert fp["retailers_observed"] == ["retailer-tesco"]
    assert all(o["trust"] == "draft (pending review)" for o in fp["commercial_observations"])


def test_footprint_unknown_variety_returns_empty_shape_not_an_error() -> None:
    fp = variety_footprint(
        "variety-does-not-exist",
        entities=_entities(),
        relationships=_relationships(),
        published_evidence=_published(),
        inbox_drafts=_drafts(),
    )
    assert fp["known"] is False
    assert fp["roles"]["breeder"] == []
    assert fp["commercial_observations"] == []


def test_varieties_observed_in_market_filters_by_berry() -> None:
    all_uk = varieties_observed_in_market(
        country_geo_id="geography-united-kingdom", entities=_entities(), published_evidence=_published(), inbox_drafts=_drafts()
    )
    assert {row["variety_id"] for row in all_uk} == {"variety-x17", "variety-y1"}

    blueberry_only = varieties_observed_in_market(
        country_geo_id="geography-united-kingdom",
        berry_id="berry-blueberry",
        entities=_entities(),
        published_evidence=_published(),
        inbox_drafts=_drafts(),
    )
    assert {row["variety_id"] for row in blueberry_only} == {"variety-x17"}


def test_ip_and_commercial_overlap_requires_both_sides() -> None:
    both = varieties_with_ip_activity_and_commercial_observation(
        entities=_entities(), published_evidence=_published(), inbox_drafts=_drafts()
    )
    # variety-x17 has both a PVR record (published) and a commercial
    # observation (draft) -- variety-y1 has an observation only, no IP
    # evidence, and is correctly excluded.
    assert [row["variety_id"] for row in both] == ["variety-x17"]


def test_competing_varieties_groups_by_real_relationship_not_guessed() -> None:
    rows = competing_varieties_in_berry_market(
        berry_id="berry-blueberry",
        country_geo_id=None,
        entities=_entities(),
        relationships=_relationships(),
        published_evidence=_published(),
        inbox_drafts=_drafts(),
    )
    assert len(rows) == 1
    assert rows[0]["company_id"] == "company-driscolls"
    assert rows[0]["varieties"] == ["X17"]

    # A marketer-only relationship still counts for "who has a competing
    # variety" (a broader question than variety_footprint()'s own strict
    # role buckets) -- variety-y1/company-other via "markets".
    raspberry_rows = competing_varieties_in_berry_market(
        berry_id="berry-raspberry",
        country_geo_id=None,
        entities=_entities(),
        relationships=_relationships(),
        published_evidence=_published(),
        inbox_drafts=_drafts(),
    )
    assert raspberry_rows[0]["company_id"] == "company-other"
    assert raspberry_rows[0]["varieties"] == ["Y1"]
