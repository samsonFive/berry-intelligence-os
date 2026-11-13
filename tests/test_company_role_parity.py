"""Recorded selling and trial roles survive every existing portfolio projection."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import investigation_api as api, variety_navigation
from app.services.company_workspace import present_company_compare, present_company_portfolio
from app.services.variety_footprint import variety_footprint
from app.services.variety_workspace import build_variety_indexes, present_variety_compare


ROOT = Path(__file__).resolve().parents[1]
UNITED = "company-united-exports"
UNITED_VARIETIES = {"variety-" + name for name in (
    "bella", "bonita", "dina", "elaina", "julieta", "magica", "magnifica", "olivia",
)}


def record(folder, key):
    return json.loads((ROOT / "data" / folder / (key + ".json")).read_text(encoding="utf8"))


def entity(key, kind):
    return {"id": key, "name": key, "entity_type": kind, "status": "active", "aliases": [],
            "berry_ids": ["berry-blueberry"], "attributes": {}}


def source(key):
    return {"id": key, "title": key, "status": "published", "source_type": "trade_press",
            "entity_ids": [], "source_url": "https://example.com/" + key}


def world(entities, relationships, evidence=()):
    main = SimpleNamespace(all_facts=lambda: [], all_signals=lambda: [], all_assessments=lambda: [])
    return api.World(main, entities, relationships, list(evidence))


def inputs(data):
    return dict(entities=data.entities, relationships=data.relationships, published_evidence=data.published,
                facts=data.facts, evidence_by_id=data.evidence_index, signals=data.signals,
                assessments=data.assessments, berry_labels={"berry-blueberry": "Blueberry"})


def portfolio_items(data, company_id):
    # A company-wide profile must keep its role basis even outside standing scope.
    result = api.detail_data(data, api.DEFAULT_CONTEXT.copy(), {"edges": [], "sources": [], "nodes": {}},
                             "company", company_id)
    return next(section["items"] for section in result["sections"] if section["title"] == "Recorded portfolio roles")


@pytest.fixture
def united_world():
    entities = {UNITED: record("entities/companies", UNITED),
                "brand-ozblu": record("entities/brands", "brand-ozblu")}
    entities.update({key: record("entities/varieties", key) for key in UNITED_VARIETIES})
    relationships = [record("relationships", "rel-united-exports-sells-" + key.removeprefix("variety-"))
                     for key in sorted(UNITED_VARIETIES)]
    relationships += [record("relationships", "rel-united-exports-owns-brand-ozblu"),
                      record("relationships", "rel-united-exports-licenses-ozblu")]
    evidence_ids = {key for row in relationships for key in row["evidence_ids"]}
    return world(entities, relationships, [record("evidence", key) for key in sorted(evidence_ids)])


def test_united_exports_eight_existing_selling_links_are_not_ownership_or_licensing(united_world):
    data = united_world
    before = deepcopy((data.entities, data.relationships, data.evidence))
    portfolio = present_company_portfolio(UNITED, **inputs(data))
    assert {row["id"] for row in portfolio["variety_rows"]} == UNITED_VARIETIES
    assert all(row["roles"] == ["Seller"] for row in portfolio["variety_rows"])
    compared = present_company_compare([UNITED], **inputs(data))
    assert compared["role_matrix"] == [{"bucket": "seller", "label": "Seller", "counts": [8]}]
    assert {row["id"] for row in compared["companies"][0]["roles"]["seller"]} == UNITED_VARIETIES
    for bucket in ("breeder", "owner_rights_holder", "licensee", "marketer", "grower", "trial_participant"):
        assert compared["companies"][0]["roles"][bucket] == []
    assert (data.entities, data.relationships, data.evidence) == before


def test_seller_is_the_same_in_incoming_variety_footprint_compare_index_and_directory(united_world):
    data = united_world
    varieties = [data.entities[key] for key in sorted(UNITED_VARIETIES)]
    indexes = build_variety_indexes(varieties=varieties, entities=list(data.entities.values()),
                                    relationships=data.relationships, published_evidence=data.published)
    for variety in varieties:
        footprint = variety_footprint(variety["id"], entities=list(data.entities.values()),
                                      relationships=data.relationships, published_evidence=data.published)
        assert footprint["roles"]["seller"] == [UNITED]
        assert indexes["roles"][variety["id"]]["seller"] == [UNITED]
    compared = present_variety_compare(["variety-bella"], **inputs(data))
    assert compared["varieties"][0]["roles"]["seller"][0]["id"] == UNITED
    directory = variety_navigation.directory(varieties, params={"favorites": "1"},
        state={"entity_favorites": {UNITED: True}}, entities=data.entities, relationships=data.relationships, regions=[])
    assert {row["id"] for row in directory["variety_rows"]} == UNITED_VARIETIES
    assert all(row["additional_roles"][0]["label"] == "Seller" for row in directory["variety_rows"])


def test_native_company_info_keeps_exact_legacy_role_notes_caveats_and_citations(united_world):
    data = united_world
    items = portfolio_items(data, UNITED)
    assert {item["id"] for item in items} == UNITED_VARIETIES
    for item in items:
        relationship = next(row for row in data.relationships if row["predicate"] == "sells" and row["object_id"] == item["id"])
        assert item["value"] == "Seller"
        assert relationship["notes"] in item["notes"]
        assert relationship["id"] in item["notes"]
        assert item["caveat"] == ""
        assert "Legacy role mapping · verify the source" in item["notes"]
        assert item["evidence_ids"] == relationship["evidence_ids"]
        assert [row["id"] for row in item["sources"]] == relationship["evidence_ids"]
        assert all("article" not in row and "supporting_excerpt" not in row for row in item["sources"])


def test_distinct_roles_and_multiple_bases_survive_without_reverse_or_unrelated_sources():
    entities = {key: entity(key, kind) for key, kind in (("company-a", "company"), ("variety-a", "variety"), ("brand-a", "brand"))}
    def edge(key, predicate, status="active", **extra):
        return {"id": key, "subject_id": "company-a", "object_id": "variety-a", "predicate": predicate,
                "status": status, "notes": key + " exact scope", "evidence_ids": ["ev-" + key], **extra}
    relationships = [edge("sold", "sells", "historical", territory="Southern Chile", confidence="low"),
                     edge("sold-review", "sells", "disputed"), edge("marketed", "markets"), edge("owned", "owns"),
                     edge("reverse", "sells", subject_id="variety-a", object_id="company-a"),
                     edge("unrelated", "partners_with"), edge("brand-owned", "owns", object_id="brand-a")]
    before = deepcopy(relationships)
    data = world(entities, relationships, [source("ev-" + row["id"]) for row in relationships])
    portfolio = present_company_portfolio("company-a", **inputs(data))
    row = portfolio["variety_rows"][0]
    assert row["roles"] == ["Marketer", "Owner / rights holder", "Seller"]
    assert {ref["id"] for ref in row["role_relationships"]} == {"sold", "sold-review", "marketed", "owned"}
    compared = present_company_compare(["company-a"], **inputs(data))
    assert next(role for role in compared["role_matrix"] if role["bucket"] == "seller")["counts"] == [1]
    item = portfolio_items(data, "company-a")[0]
    assert set(item["evidence_ids"]) == {"ev-sold", "ev-sold-review", "ev-marketed", "ev-owned"}
    assert "Historical relationship" in item["caveat"] and "Disputed / review required" in item["caveat"]
    assert "Recorded territory: Southern Chile" in item["notes"]
    assert "Confidence: low" in item["notes"]
    assert "sold exact scope" in item["notes"] and "sold-review exact scope" in item["notes"]
    row["role_relationships"][0]["evidence_ids"].append("mutation-of-returned-copy")
    assert relationships == before


def test_trial_participation_is_not_growing_or_a_brand_or_berry_portfolio():
    trial = record("relationships", "rel-fall-creek-trials-fc11-164-chile")
    general_trial = record("relationships", "rel-university-of-arkansas-trials-blueberry")
    entities = {key: entity(key, kind) for key, kind in ((trial["subject_id"], "company"),
        (trial["object_id"], "variety"), (general_trial["subject_id"], "company"), ("berry-blueberry", "berry"))}
    data = world(entities, [trial, general_trial], [source(key) for key in trial["evidence_ids"] + general_trial["evidence_ids"]])
    portfolio = present_company_portfolio(trial["subject_id"], **inputs(data))
    assert [(row["id"], row["roles"]) for row in portfolio["variety_rows"]] == [(trial["object_id"], ["Trial participant"])]
    assert present_company_portfolio(general_trial["subject_id"], **inputs(data))["variety_rows"] == []
    footprint = variety_footprint(trial["object_id"], entities=list(entities.values()), relationships=data.relationships, published_evidence=data.published)
    assert footprint["roles"]["trial_participant"] == [trial["subject_id"]]
    assert footprint["roles"]["grower"] == [] and footprint["countries_observed"] == []
    item = portfolio_items(data, trial["subject_id"])[0]
    assert trial["notes"] in item["notes"] and "southern Chile" in item["notes"]
    directory = variety_navigation.directory([entities[trial["object_id"]]], params={}, state={},
        entities=entities, relationships=data.relationships, regions=[])
    assert directory["variety_rows"][0]["additional_roles"][0]["label"] == "Trial participant"


def test_directory_keeps_its_active_only_membership_policy():
    entities = {key: entity(key, kind) for key, kind in (("company-a", "company"), ("variety-a", "variety"))}
    for status in ("historical", "disputed"):
        relationships = [{"subject_id": "company-a", "object_id": "variety-a", "predicate": "sells", "status": status}]
        assert variety_navigation.company_actors("variety-a", relationships, entities) == set()
        assert present_company_portfolio("company-a", **inputs(world(entities, relationships)))["variety_rows"][0]["roles"] == ["Seller"]
