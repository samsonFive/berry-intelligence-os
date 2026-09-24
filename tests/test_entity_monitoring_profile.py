from copy import deepcopy

from fastapi.testclient import TestClient

from app.main import app
from app.services.entity_monitoring import (
    build_monitoring_profile,
    monitored_public_signals,
)


def _entity():
    return {
        "id": "company-example",
        "entity_type": "company",
        "name": "Example Berry Genetics",
        "aliases": ["EBG", "Blue"],
        "berry_ids": ["berry-blueberry"],
    }


def test_monitoring_expression_is_transparent_and_contextualizes_weak_aliases():
    profile = build_monitoring_profile(
        _entity(),
        related_terms=["Example Nova"],
    )
    assert '"Example Berry Genetics"' in profile["expression"]
    assert '("EBG" AND ("blueberry"))' in profile["expression"]
    assert '("Blue" AND ("blueberry"))' in profile["expression"]
    assert '"Example Nova"' in profile["expression"]
    assert profile["exclusions"] == ["Raspberry Pi", "BlackBerry device"]
    assert len(profile["terms"]) <= 12


def test_monitored_signals_preserve_source_family_and_match_provenance():
    entity = _entity()
    records = [
        {
            "id": "ev-podcast",
            "status": "published",
            "title": "Industry interview",
            "summary": "A public interview with the breeding team.",
            "source_name": "Berry Podcast",
            "source_type": "industry_podcast",
            "source_url": "https://example.test/podcast",
            "published_date": "2026-09-20",
            "entity_ids": [entity["id"]],
            "geography_ids": ["geography-peru"],
        },
        {
            "id": "ev-report",
            "status": "published",
            "title": "Example Berry Genetics annual research report",
            "summary": "Public research summary.",
            "source_name": "Public University",
            "source_type": "research_program_publication",
            "source_url": "https://example.test/report.pdf",
            "published_date": "2026-09-19",
            "entity_ids": [],
            "geography_ids": [],
        },
    ]
    original = deepcopy(records)
    rows = monitored_public_signals(
        entity,
        records,
        entities={entity["id"]: entity},
    )
    assert [row["signal_label"] for row in rows] == ["Podcast", "Research"]
    assert rows[0]["match_reason"] == "Canonical entity link on published Evidence"
    assert "Alias “Example Berry Genetics” matched title" == rows[1]["match_reason"]
    assert rows[0]["geography_ids"] == ["geography-peru"]
    assert records == original


def test_monitored_signals_keep_real_source_diversity_within_bound():
    entity = _entity()
    records = [
        {
            "id": f"ev-news-{index}",
            "status": "published",
            "title": f"Example Berry Genetics news {index}",
            "source_name": "Trade publisher",
            "source_type": "trade_press",
            "source_url": f"https://example.test/news/{index}",
            "published_date": f"2026-09-{20 + index:02d}",
            "entity_ids": [entity["id"]],
        }
        for index in range(5)
    ] + [
        {
            "id": "ev-older-podcast",
            "status": "published",
            "title": "Public industry interview",
            "source_name": "Podcast publisher",
            "source_type": "industry_podcast",
            "source_url": "https://example.test/podcast",
            "published_date": "2025-10-28",
            "entity_ids": [entity["id"]],
        }
    ]
    rows = monitored_public_signals(
        entity,
        records,
        entities={entity["id"]: entity},
        limit=3,
    )
    assert len(rows) == 3
    assert {row["signal_label"] for row in rows} == {"News", "Podcast"}


def test_company_dossier_exposes_monitoring_profile_and_public_signals():
    page = TestClient(app).get(
        "/entities/company/company-fall-creek-farm-and-nursery"
    )
    assert page.status_code == 200
    assert "data-monitoring-profile" in page.text
    assert "Inspect monitoring expression" in page.text
    assert "Open original evidence" in page.text
    assert "Canonical entity link" in page.text or "matched title" in page.text
