from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from app.services.patent_monitor.corroboration import propose_corroboration_links
from app.services.patent_monitor.entity_link import matched_entity_ids, suggest_entity_links
from app.services.patent_monitor.google_patents import parse_search_results
from app.services.patent_monitor.normalize import (
    extract_botanical_name,
    extract_cultivar_name,
    names_as_list,
    normalize_discovery_hit,
    patent_numbers_equivalent,
)
from app.services.patent_monitor.relevance import berry_ids_for_filing, relevance_decision
from app.services.patent_monitor.service import (
    build_review_draft,
    choose_provider,
    run_patent_monitor,
)
from app.services.patent_monitor.uspto_odp import parse_odp_results
from app.services.review_workbench import attach_publication_card

ROOT = Path(__file__).resolve().parents[1]


def _filing(**overrides):
    base = normalize_discovery_hit(
        {
            "publication_number": "USPP35665P2",
            "title": "Blueberry plant named ‘FC12-029’",
            "snippet": "A new Vaccinium corymbosum cultivar named ‘FC12-029’.",
            "filing_date": "2023-02-01",
            "grant_date": "2024-01-16",
            "inventor": "David Brazelton",
            "assignee": "Fall Creek Farm & Nursery, Inc.",
            "acquisition_method": "google_patents_json",
        }
    )
    base.update(overrides)
    return base


def test_normalize_extracts_cultivar_and_keeps_assignee_inventor_distinct() -> None:
    filing = _filing()
    assert extract_cultivar_name(filing["title"]) == "FC12-029"
    assert extract_botanical_name(filing["title"], filing["abstract"] or "") == "Vaccinium corymbosum"
    assert filing["botanical_name"] == "Vaccinium corymbosum"
    assert filing["assignees"] == ["Fall Creek Farm & Nursery, Inc."]
    assert filing["inventors"] == ["David Brazelton"]
    assert filing["applicants"] == []
    assert filing["inventors"] != filing["assignees"]
    assert patent_numbers_equivalent("US PP35,665 P2", "USPP35665P2")


def test_names_as_list_does_not_copy_inventor_into_assignee() -> None:
    assert names_as_list("Omar Carrillo Mendoza") == ["Omar Carrillo Mendoza"]
    filing = normalize_discovery_hit(
        {
            "publication_number": "USPP33090P2",
            "title": "Strawberry plant variety named ‘DrisStrawEightyThree’",
            "inventor": "Omar Carrillo Mendoza",
            "assignee": "Driscoll's, Inc.",
        }
    )
    assert filing["assignees"] == ["Driscoll's, Inc."]
    assert "Omar" not in " ".join(filing["assignees"])


def test_berry_matching_accepts_vaccinium_corymbosum_and_rejects_cranberry() -> None:
    blueberry = _filing()
    assert berry_ids_for_filing(blueberry) == ["berry-blueberry"]
    cranberry = _filing(title="Cranberry plant named ‘HyRed’", abstract="Vaccinium macrocarpon")
    assert berry_ids_for_filing(cranberry) == []
    generic = _filing(
        title="Ornamental berry shrub named ‘Sparkle’",
        abstract="decorative landscape plant",
        botanical_name=None,
        cultivar_name="Sparkle",
    )
    assert relevance_decision(generic)["relevant"] is False


def test_entity_suggestions_match_assignee_not_inventor_creation() -> None:
    entities = [
        {
            "id": "company-fall-creek-farm-and-nursery",
            "entity_type": "company",
            "name": "Fall Creek Farm & Nursery, Inc.",
            "aliases": ["Fall Creek"],
        },
        {
            "id": "variety-fc12-029",
            "entity_type": "variety",
            "name": "FC12-029",
            "aliases": [],
        },
    ]
    suggestions = suggest_entity_links(_filing(), entities)
    roles = {row["role"]: row for row in suggestions}
    assert roles["assignee"]["match_status"] == "matched"
    assert roles["assignee"]["match_entity_id"] == "company-fall-creek-farm-and-nursery"
    driscoll = suggest_entity_links(
        _filing(assignees=["Driscoll's, Inc."], inventors=["Brian K. Hamilton"], cultivar_name="DrisRaspTwentyThree"),
        [
            {
                "id": "breeding_program-driscolls-blueberry",
                "entity_type": "breeding_program",
                "name": "Driscoll's blueberry breeding programme",
                "aliases": [],
            },
            {
                "id": "company-driscolls",
                "entity_type": "company",
                "name": "Driscoll's, Inc.",
                "aliases": ["Driscoll's", "Driscolls"],
            },
        ],
    )
    assignee = next(row for row in driscoll if row["role"] == "assignee")
    assert assignee["match_entity_id"] == "company-driscolls"
    strawberry_emerald = suggest_entity_links(
        _filing(
            title="Strawberry plant named ‘Emerald’",
            abstract="A new Fragaria cultivar named ‘Emerald’.",
            botanical_name="Fragaria × ananassa",
            cultivar_name="Emerald",
            assignees=["Fragaria Plant Sciences, B.V."],
            inventors=["Jonathan R. Nelson"],
        ),
        [
            {
                "id": "variety-emerald",
                "entity_type": "variety",
                "name": "Emerald",
                "aliases": ["FL95-209a"],
                "berry_ids": ["berry-blueberry"],
            }
        ],
    )
    variety = next(row for row in strawberry_emerald if row["role"] == "variety")
    assert variety["match_status"] == "unresolved"
    assert variety["match_entity_id"] is None
    assert roles["inventor"]["match_status"] == "unresolved"
    assert roles["inventor"]["match_entity_id"] is None
    assert "person-" not in json.dumps(suggestions)
    assert matched_entity_ids(suggestions) == [
        "company-fall-creek-farm-and-nursery",
        "variety-fc12-029",
    ]


def test_corroboration_link_is_proposed_only() -> None:
    trusted = [
            {
                "id": "ev-planasa-blue-manila-datasheet",
                "status": "published",
                "title": "Planasa Blue Manila / Plablue 1545 datasheet",
                "summary": "Commercial description of Plablue 1545.",
                "berry_ids": ["berry-blueberry"],
                "entity_ids": ["company-planasa"],
            }
    ]
    filing = _filing(
        publication_number="USPP31345P2",
        title="Blueberry plant named ‘Plablue 1545’",
        cultivar_name="Plablue 1545",
        assignees=["Plantas de Navarra, S.A."],
    )
    links = propose_corroboration_links(
        filing,
        trusted_evidence=trusted,
        matched_entity_ids=["company-planasa"],
        berry_ids=["berry-blueberry"],
    )
    assert links
    assert all(link["status"] == "proposed" for link in links)
    assert all(link["predicate"] in {"corroborates", "same_signal"} for link in links)


def test_draft_is_untrusted_and_schema_valid() -> None:
    filing = _filing()
    draft = build_review_draft(
        filing,
        berry_ids=["berry-blueberry"],
        suggestions=[],
        evidence_links=[],
        source_id="source-uspto-plant-patents",
        captured_date=date.today().isoformat(),
    )
    assert draft["status"] == "draft"
    assert draft["review_state"] == "in_review"
    assert draft["verification_state"] == "unverified"
    assert draft["source_authority"] == "high"
    assert draft["information_confidence"] == "unknown"
    assert draft["evidence_role"] == "publication_artifact"
    schema = json.loads((ROOT / "schemas" / "evidence.schema.json").read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(draft))
    assert errors == [], [error.message for error in errors]


def test_google_patents_parser_and_odp_parser() -> None:
    google_payload = {
        "results": {
            "cluster": [
                {
                    "result": [
                        {
                            "id": "patent/USPP33090P2/en",
                            "patent": {
                                "title": "<b>Strawberry plant variety named</b> ‘DrisStrawEightyThree’",
                                "snippet": "A new strawberry plant.",
                                "filing_date": "2020-06-25",
                                "grant_date": "2021-05-25",
                                "inventor": "Omar Carrillo Mendoza",
                                "assignee": "Driscoll's, Inc.",
                                "publication_number": "USPP33090P2",
                            },
                        }
                    ]
                }
            ]
        }
    }
    hits = parse_search_results(google_payload)
    assert hits[0]["publication_number"] == "USPP33090P2"
    assert hits[0]["cultivar_name"] == "DrisStrawEightyThree"
    odp_payload = {
        "patentFileWrapperDataBag": [
            {
                "applicationMetaData": {
                    "patentNumber": "USPP35665P2",
                    "inventionTitle": "Blueberry plant named ‘FC12-029’",
                    "filingDate": "2023-02-01",
                    "grantDate": "2024-01-16",
                    "inventorBag": [{"firstName": "David", "lastName": "Brazelton"}],
                    "assigneeBag": [{"nameLineOneText": "Fall Creek Farm & Nursery, Inc."}],
                    "applicationNumberText": "17987654",
                }
            }
        ]
    }
    odp_hits = parse_odp_results(odp_payload)
    assert odp_hits[0]["assignees"] == ["Fall Creek Farm & Nursery, Inc."]
    assert odp_hits[0]["inventors"] == ["David Brazelton"]


def test_monitor_dedupes_and_isolates_query_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BIOS_USPTO_ODP_API_KEY", raising=False)
    data_dir = tmp_path / "data"
    inbox = tmp_path / "inbox"
    (data_dir / "entities" / "companies").mkdir(parents=True)
    (data_dir / "evidence").mkdir()
    (data_dir / "entities" / "companies" / "company-fall-creek-farm-and-nursery.json").write_text(
        json.dumps(
            {
                "id": "company-fall-creek-farm-and-nursery",
                "record_type": "entity",
                "entity_type": "company",
                "name": "Fall Creek Farm & Nursery, Inc.",
                "aliases": ["Fall Creek"],
                "status": "active",
            }
        )
        + "\n"
    )
    (data_dir / "evidence" / "ev-existing.json").write_text(
        json.dumps(
            {
                "id": "ev-existing",
                "status": "published",
                "title": "Fall Creek FC12-029 grower note",
                "summary": "Mentions FC12-029 in a catalogue.",
                "entity_ids": ["company-fall-creek-farm-and-nursery"],
            }
        )
        + "\n"
    )
    watchlist = {
        "kind": "berry-intelligence-os-patent-watchlist",
        "provider_preference": ["google_patents_json"],
        "publication_after": "2023-01-01",
        "max_candidates_per_run": 10,
        "exclude_terms": ["cranberry"],
        "queries": [
            {"id": "ok-query", "q": '("blueberry plant named")', "berry_hint": "berry-blueberry"},
            {"id": "bad-query", "q": '("fail")', "berry_hint": "berry-blueberry"},
        ],
    }
    watch_path = tmp_path / "watchlist.json"
    watch_path.write_text(json.dumps(watchlist) + "\n")

    def fake_google(query, **kwargs):
        if "fail" in query:
            raise RuntimeError("network down")
        return {
            "query": query,
            "total": 2,
            "hits": [_filing(), _filing()],  # duplicate number
        }

    def wrapping(query, **kwargs):
        if "fail" in query:
            from app.services.patent_monitor.google_patents import GooglePatentsError

            raise GooglePatentsError("isolated failure")
        return fake_google(query, **kwargs)

    first = run_patent_monitor(
        data_dir=data_dir,
        inbox_dir=inbox,
        watchlist_path=watch_path,
        max_candidates=10,
        google_search=wrapping,
    )
    assert first["berry_relevant"] == 1
    assert first["review_ready"] == 1
    assert first["failed"]
    draft_path = inbox / "evidence" / "ev-patent-uspp35665p2.json"
    assert draft_path.is_file()
    draft = json.loads(draft_path.read_text())
    assert draft["status"] == "draft"
    assert draft["verification_state"] == "unverified"
    assert any(link["status"] == "proposed" for link in draft["evidence_links"])
    second = run_patent_monitor(
        data_dir=data_dir,
        inbox_dir=inbox,
        watchlist_path=watch_path,
        max_candidates=10,
        google_search=wrapping,
    )
    assert second["duplicates"] == 1
    assert second["created"] == []


def test_discover_keeps_fair_quota_across_queries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BIOS_USPTO_ODP_API_KEY", raising=False)
    data_dir = tmp_path / "data"
    inbox = tmp_path / "inbox"
    (data_dir / "entities").mkdir(parents=True)
    (data_dir / "evidence").mkdir()
    watchlist = {
        "kind": "berry-intelligence-os-patent-watchlist",
        "provider_preference": ["google_patents_json"],
        "publication_after": "2023-01-01",
        "max_candidates_per_run": 10,
        "exclude_terms": [],
        "queries": [
            {"id": "blue", "q": '("blueberry plant named")', "berry_hint": "berry-blueberry"},
            {"id": "rasp", "q": '("raspberry plant named")', "berry_hint": "berry-raspberry"},
        ],
    }
    watch_path = tmp_path / "watchlist.json"
    watch_path.write_text(json.dumps(watchlist) + "\n")

    def fake_google(query, **kwargs):
        if "raspberry" in query:
            hit = _filing(
                publication_number="USPP37404P2",
                title="Raspberry plant named ‘DrisRaspTwentySix’",
                snippet="A new Rubus idaeus cultivar.",
            )
        else:
            hit = _filing()
        return {"query": query, "total": 20, "hits": [hit] * 12}

    result = run_patent_monitor(
        data_dir=data_dir,
        inbox_dir=inbox,
        watchlist_path=watch_path,
        max_candidates=10,
        google_search=fake_google,
        dry_run=True,
    )
    titles = [row["title"] for row in result["filings"]]
    assert any("Blueberry" in title for title in titles)
    assert any("Raspberry" in title for title in titles)
    assert result["berry_relevant"] == 2


def test_choose_provider_prefers_odp_only_when_key_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BIOS_USPTO_ODP_API_KEY", raising=False)
    assert choose_provider() == "google_patents_json"
    monkeypatch.setenv("BIOS_USPTO_ODP_API_KEY", "not-a-real-key")
    assert choose_provider() == "uspto_odp"


def test_publication_card_treats_patent_as_ready_filing() -> None:
    draft = build_review_draft(
        _filing(),
        berry_ids=["berry-blueberry"],
        suggestions=[],
        evidence_links=[],
        source_id="source-uspto-plant-patents",
        captured_date="2026-08-18",
    )
    attach_publication_card(draft, entities={}, berry_labels={"berry-blueberry": "Blueberry"})
    assert draft["card"]["transcript_label"] == "Patent filing"
    assert draft["card"]["transcript_state"] == "ready"
    assert draft["card"]["relevance_band"] == "High"
