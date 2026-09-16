"""TD-108 FreshPlaza duplicate Source retirement; TD-109 Hortifrut RUT alias."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.competitor_pulse import company_query_terms
from app.services.source_lifecycle import RETIRED, is_collection_eligible, lifecycle_state

ROOT = Path(__file__).resolve().parents[1]
FRESHPLAZA_FEED = "https://www.freshplaza.com/rss.xml"
DUPLICATE_ID = "source-20260806173428-a004-fresh-plaza-74"
KEPT_ID = "source-freshplaza-global"


def _sources() -> list[dict]:
    return json.loads((ROOT / "data" / "configuration" / "sources.json").read_text(encoding="utf-8"))


def test_freshplaza_duplicate_is_retired_with_replacement():
    by_id = {row["id"]: row for row in _sources()}
    duplicate = by_id[DUPLICATE_ID]
    kept = by_id[KEPT_ID]
    assert lifecycle_state(duplicate) == RETIRED
    assert duplicate["lifecycle"]["replacement_source_id"] == KEPT_ID
    assert not is_collection_eligible(duplicate)
    assert is_collection_eligible(kept)
    assert (duplicate.get("discovery") or {}).get("feed_url") == FRESHPLAZA_FEED
    assert (kept.get("discovery") or {}).get("feed_url") == FRESHPLAZA_FEED


def test_only_one_collection_eligible_source_for_freshplaza_rss():
    eligible = [
        row["id"]
        for row in _sources()
        if (row.get("discovery") or {}).get("feed_url") == FRESHPLAZA_FEED
        and is_collection_eligible(row)
    ]
    assert eligible == [KEPT_ID]


def test_hortifrut_rut_is_registration_id_not_alias():
    company = json.loads(
        (ROOT / "data" / "entities" / "companies" / "company-hortifrut.json").read_text(encoding="utf-8")
    )
    aliases = company.get("aliases") or []
    assert "RUT 96.896.990-0" not in aliases
    assert all(not str(alias).upper().startswith("RUT ") for alias in aliases)
    regs = (company.get("attributes") or {}).get("registration_ids") or []
    assert any(row.get("kind") == "RUT" and row.get("value") == "96.896.990-0" for row in regs)
    terms = company_query_terms(company)
    assert "Hortifrut" in terms
    assert "RUT 96.896.990-0" not in terms
    assert "96.896.990-0" not in terms
