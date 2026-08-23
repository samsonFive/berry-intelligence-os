"""Learner Mode V1 -- deterministic educational concept pages, connected
to but distinct from trusted Competitive Intelligence."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.learner import (
    all_concepts,
    concept_by_slug,
    concepts_by_pillar,
    learn_href_for_trait_id,
    related_concepts,
    related_intelligence_for_concept,
    search_concepts,
)

ACCEPTANCE_SLUGS = {
    "flavor",
    "firmness",
    "shelf-life",
    "bloom",
    "fruit-size",
    "texture",
    "precocity",
    "double-cropping",
    "winter-production",
    "color",
}


def test_acceptance_concepts_all_present():
    slugs = {c["slug"] for c in all_concepts()}
    assert ACCEPTANCE_SLUGS <= slugs


def test_every_concept_has_required_fields_and_no_placeholder_copy():
    required = [
        "what_is_it",
        "why_it_matters",
        "how_evaluated",
        "what_affects_it",
        "how_to_interpret",
    ]
    for concept in all_concepts():
        for field in required:
            value = concept.get(field) or ""
            assert len(value) > 40, f"{concept['slug']}.{field} looks like placeholder copy"
            assert "lorem ipsum" not in value.lower()
            assert "coming soon" not in value.lower()
        assert concept.get("sources"), f"{concept['slug']} has no sources"
        for source in concept["sources"]:
            assert source.get("publisher")
            assert source.get("title")


def test_concept_by_slug_and_aliases():
    concept = concept_by_slug("firmness")
    assert concept is not None
    assert concept["name"] == "Firmness"
    assert "fruit firmness" in concept["aliases"]
    assert concept_by_slug("does-not-exist") is None


def test_search_matches_name_alias_and_summary():
    assert any(c["slug"] == "firmness" for c in search_concepts("firmness"))
    assert any(c["slug"] == "fruit-size" for c in search_concepts("caliber"))
    assert any(c["slug"] == "double-cropping" for c in search_concepts("double cropping"))
    assert search_concepts("completely-unrelated-xyz") == []


def test_search_empty_query_returns_all():
    assert len(search_concepts("")) == len(all_concepts())


def test_category_grouping_uses_declared_pillars_and_stable_order():
    groups = concepts_by_pillar()
    labels = [g["label"] for g in groups]
    assert "Taste & Consumer Science" in labels
    assert "Plant Biology & Agronomy" in labels
    total = sum(len(g["concepts"]) for g in groups)
    assert total == len(all_concepts())
    # Deterministic ordering: calling twice yields identical structure.
    assert concepts_by_pillar() == groups


def test_related_concepts_resolve_to_real_slugs():
    concept = concept_by_slug("firmness")
    related = related_concepts(concept)
    assert related
    for row in related:
        assert concept_by_slug(row["slug"]) is not None
        assert row["href"] == f"/learn/{row['slug']}"


def test_learn_href_for_trait_id_maps_known_traits_and_returns_none_for_unknown():
    assert learn_href_for_trait_id("trait-fruit-firmness") == "/learn/firmness"
    assert learn_href_for_trait_id("trait-postharvest-shelf-life") == "/learn/shelf-life"
    assert learn_href_for_trait_id("trait-does-not-exist") is None


def test_related_intelligence_only_trusted_facts_and_bounded():
    concept = concept_by_slug("firmness")
    entities = {
        "variety-a": {"id": "variety-a", "entity_type": "variety", "name": "Variety A"},
        "trait-fruit-firmness": {"id": "trait-fruit-firmness", "entity_type": "trait", "name": "Fruit firmness"},
    }
    facts = [
        {
            "id": f"fact-{i}",
            "statement": f"Statement {i}",
            "classification": "fact",
            "entity_ids": ["variety-a", "trait-fruit-firmness"],
            "evidence_ids": [f"ev-{i}"],
        }
        for i in range(12)
    ]
    evidence_by_id = {
        f"ev-{i}": {"id": f"ev-{i}", "source_name": "Source", "published_date": f"2026-01-{i+1:02d}"}
        for i in range(12)
    }
    result = related_intelligence_for_concept(
        concept, facts=facts, entities=entities, evidence_by_id=evidence_by_id, limit=8
    )
    assert result["has_any"] is True
    assert len(result["rows"]) == 8
    # Most recent first.
    assert result["rows"][0]["published_date"] == "2026-01-12"


def test_related_intelligence_ignores_unrelated_facts_and_non_variety_matches():
    concept = concept_by_slug("firmness")
    entities = {
        "company-a": {"id": "company-a", "entity_type": "company", "name": "Company A"},
        "trait-fruit-firmness": {"id": "trait-fruit-firmness", "entity_type": "trait", "name": "Fruit firmness"},
    }
    facts = [
        {"id": "fact-1", "statement": "irrelevant", "entity_ids": ["company-a", "trait-fruit-firmness"], "evidence_ids": []},
        {"id": "fact-2", "statement": "no trait tag", "entity_ids": ["company-a"], "evidence_ids": []},
    ]
    result = related_intelligence_for_concept(concept, facts=facts, entities=entities, evidence_by_id={})
    assert result == {"rows": [], "has_any": False}


def test_related_intelligence_honest_empty_for_concepts_without_trait_ids():
    concept = concept_by_slug("bloom")
    assert concept["trait_ids"] == []
    result = related_intelligence_for_concept(concept, facts=[{"id": "x", "entity_ids": []}], entities={}, evidence_by_id={})
    assert result == {"rows": [], "has_any": False}


# --- Route-level tests against real data --------------------------------


def test_learn_home_loads():
    client = TestClient(app)
    page = client.get("/learn")
    assert page.status_code == 200
    assert "Learner Mode" in page.text
    assert "Taste &amp; Consumer Science" in page.text or "Taste & Consumer Science" in page.text


def test_learn_home_search_firmness():
    client = TestClient(app)
    page = client.get("/learn", params={"q": "firmness"})
    assert page.status_code == 200
    assert "Firmness" in page.text


def test_learn_home_search_no_match_shows_honest_empty_state():
    client = TestClient(app)
    page = client.get("/learn", params={"q": "completely-unrelated-xyz-term"})
    assert page.status_code == 200
    assert "No Learner Mode concepts match" in page.text


def test_learn_concept_detail_firmness_has_all_required_sections():
    client = TestClient(app)
    page = client.get("/learn/firmness")
    assert page.status_code == 200
    for heading in (
        "What is it?",
        "Why does it matter?",
        "How is it evaluated / observed?",
        "What can affect it?",
        "When you see this in intelligence",
        "Related terms",
        "Related berry intelligence",
        "Sources / provenance",
    ):
        assert heading in page.text


def test_learn_concept_invalid_slug_is_404():
    client = TestClient(app)
    page = client.get("/learn/does-not-exist-xyz")
    assert page.status_code == 404


def test_learn_concept_shows_knowledge_class_never_masquerades_as_trust_object():
    client = TestClient(app)
    page = client.get("/learn/firmness")
    assert page.status_code == 200
    assert "EDUCATIONAL KNOWLEDGE" in page.text
    assert "not trusted Competitive Intelligence" in page.text
    # Never rendered as one of the real trust-object badges.
    assert '<span class="badge badge-fact">FACT</span>\n            \n              Firmness' not in page.text


def test_learn_concept_double_cropping_is_regional_production_practice():
    client = TestClient(app)
    page = client.get("/learn/double-cropping")
    assert page.status_code == 200
    assert "Regional production practice" in page.text
    assert "never universal across regions" in page.text


def test_learn_related_intelligence_uses_trusted_data_and_variety_link():
    client = TestClient(app)
    page = client.get("/learn/firmness")
    assert page.status_code == 200
    assert "/entities/variety/" in page.text
    assert "Coverage, not a completeness claim" in page.text


def test_learn_no_pending_leakage():
    client = TestClient(app)
    page = client.get("/learn/firmness")
    assert page.status_code == 200
    assert "in_review" not in page.text
    assert "signal_candidate" not in page.text.casefold()


def test_explain_this_link_present_on_real_variety_intelligence_page():
    client = TestClient(app)
    page = client.get("/entities/variety/variety-sekoya-grande")
    assert page.status_code == 200
    assert 'href="/learn/firmness"' in page.text
    assert "Explain this" in page.text


def test_explain_this_round_trip_lands_on_concept_page():
    client = TestClient(app)
    profile = client.get("/entities/variety/variety-sekoya-grande")
    assert 'href="/learn/firmness"' in profile.text
    concept_page = client.get("/learn/firmness")
    assert concept_page.status_code == 200
    assert "Firmness" in concept_page.text


def test_learn_nav_entry_present():
    client = TestClient(app)
    page = client.get("/learn")
    assert page.status_code == 200
    assert 'href="/learn"' in page.text


def test_learn_deterministic_ordering_across_requests():
    client = TestClient(app)
    first = client.get("/learn").text
    second = client.get("/learn").text
    assert first == second
