"""Deterministic pending-draft attribution: names, aliases, newsroom identity."""

from __future__ import annotations

from app.services.draft_attribution import attribute_draft, draft_matches_entity, watch_match_quality


def _entities() -> dict[str, dict]:
    return {
        "company-hortifrut": {
            "id": "company-hortifrut",
            "entity_type": "company",
            "name": "Hortifrut S.A.",
            "aliases": ["Hortifrut"],
        },
        "company-planasa": {
            "id": "company-planasa",
            "entity_type": "company",
            "name": "Plantas de Navarra, S.A.",
            "aliases": ["Planasa"],
        },
        "company-sanlucar": {
            "id": "company-sanlucar",
            "entity_type": "company",
            "name": "SanLucar Group",
            "aliases": ["SanLucar"],
        },
        "geography-mexico": {
            "id": "geography-mexico",
            "entity_type": "geography",
            "name": "Mexico",
            "aliases": [],
        },
    }


def _sources() -> dict[str, dict]:
    return {
        "source-20260819-hortifrut-newsroom": {
            "id": "source-20260819-hortifrut-newsroom",
            "label": "Hortifrut Newsroom",
            "linked_competitor_ids": ["company-hortifrut"],
        }
    }


def test_hortifrut_newsroom_without_entity_ids_is_primary() -> None:
    record = {
        "id": "draft-hf",
        "title": "First-half results and Naturipe platform update",
        "summary": "The group reported berry sales and genetics-platform expansion.",
        "source_id": "source-20260819-hortifrut-newsroom",
        "entity_ids": [],
    }
    attribution = attribute_draft(record, _entities(), sources=_sources())
    assert attribution["primary"]["id"] == "company-hortifrut"
    assert attribution["primary"]["method"] == "newsroom_identity"
    assert draft_matches_entity(record, _entities()["company-hortifrut"], _entities(), sources=_sources())
    assert not draft_matches_entity(record, _entities()["company-planasa"], _entities(), sources=_sources())


def test_planasa_title_attaches_without_stored_ids() -> None:
    record = {
        "id": "draft-pl",
        "title": "Planasa launches Blue Maldiva blueberry in Peru",
        "summary": "The Spanish breeder expanded licensed plantings.",
        "entity_ids": [],
    }
    attribution = attribute_draft(record, _entities())
    assert attribution["primary"]["id"] == "company-planasa"
    assert attribution["primary"]["method"] == "alias"
    assert attribution["primary"]["location"] == "title"


def test_body_comention_is_not_primary_subject() -> None:
    record = {
        "id": "draft-cfia",
        "title": "Plant Breeders' Rights - blueberry variety index",
        "summary": "The index lists Planasa and Hortifrut among many applicants.",
        "entity_ids": [],
    }
    attribution = attribute_draft(record, _entities())
    assert attribution["primary"] is None or attribution["primary"].get("entity_type") != "company"
    mention_ids = {hit["id"] for hit in attribution["mentions"]}
    assert "company-planasa" in mention_ids
    assert "company-hortifrut" in mention_ids
    assert not draft_matches_entity(record, _entities()["company-planasa"], _entities())


def test_title_company_beats_newsroom_of_another_company() -> None:
    record = {
        "id": "draft-mixed",
        "title": "Planasa signs a license with a Chilean exporter",
        "summary": "Coverage of the Spanish nursery group.",
        "source_id": "source-20260819-hortifrut-newsroom",
        "entity_ids": [],
    }
    attribution = attribute_draft(record, _entities(), sources=_sources())
    assert attribution["primary"]["id"] == "company-planasa"
    hortifrut = next(hit for hit in attribution["hits"] if hit["id"] == "company-hortifrut")
    assert hortifrut["strength"] == "mention"


def test_source_label_identity_attaches_ushbc() -> None:
    record = {
        "id": "draft-ushbc-pod",
        "title": "Click to Cart: Capturing the Modern Blueberry Shopper",
        "summary": "A conversation about blueberry retail conversion.",
        "source_id": "source-business-of-blueberries-podcast",
        "source_name": "The Business of Blueberries (USHBC / NABC)",
        "entity_ids": [],
    }
    sources = {
        "source-business-of-blueberries-podcast": {
            "id": "source-business-of-blueberries-podcast",
            "label": "The Business of Blueberries (USHBC / NABC)",
            "linked_competitor_ids": [],
        }
    }
    entities = {
        "company-ushbc": {
            "id": "company-ushbc",
            "entity_type": "company",
            "name": "U.S. Highbush Blueberry Council",
            "aliases": ["USHBC", "NABC"],
        }
    }
    attribution = attribute_draft(record, entities, sources=sources)
    assert attribution["primary"]["id"] == "company-ushbc"
    assert attribution["primary"]["method"] == "newsroom_identity"


def test_watch_match_primary_vs_mention() -> None:
    entities = _entities()
    about = attribute_draft(
        {"title": "Planasa files a new blueberry variety", "entity_ids": []},
        entities,
    )
    mention = attribute_draft(
        {
            "title": "Mexico blueberry harvest outlook",
            "summary": "Planasa licensees are among the shippers.",
            "entity_ids": [],
        },
        entities,
    )
    watches = {"company-planasa", "geography-mexico"}
    assert watch_match_quality(about, watches) == ("primary", "company-planasa")
    match, entity_id = watch_match_quality(mention, watches)
    assert match == "primary"
    assert entity_id == "geography-mexico"
    planasa_mention, _ = watch_match_quality(mention, {"company-planasa"})
    assert planasa_mention == "mention"
