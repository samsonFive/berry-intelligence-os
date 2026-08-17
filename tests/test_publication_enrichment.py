"""Deterministic tagging plus non-trusted AI publication enrichment."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.publication_enrichment import enrich_publication_draft


def test_deterministic_tags_run_before_ai_and_preserve_publisher_text() -> None:
    draft = {
        "id": "ev-media-enrich-1",
        "title": "Peru blueberry harvest update",
        "summary": "Raw RSS with a <a href='https://example.invalid'>link</a> &nbsp; promo.",
        "why_it_matters": "",
        "berry_ids": [],
        "geography_ids": [],
        "entity_ids": [],
    }
    item = {
        "title": draft["title"],
        "description": draft["summary"],
        "source_name": "Blueberries TV",
    }
    geographies = [{"id": "geo-peru", "entity_type": "geography", "name": "Peru", "aliases": []}]
    entities = [{"id": "company-export", "entity_type": "company", "name": "Export Partners", "aliases": []}]
    berries = [{"id": "berry-blueberry", "entity_type": "berry", "name": "Blueberry"}]

    def complete(prompt, **kwargs):
        assert "Peru blueberry harvest update" in prompt
        assert "Deterministic berry_ids" in prompt
        return SimpleNamespace(
            parsed={
                "concise_summary": "Peru blueberry harvest conditions are discussed.",
                "why_it_matters": "Supply timing in Peru affects export windows.",
                "suggested_berry_ids": ["berry-blueberry"],
                "suggested_geography_ids": ["geo-peru"],
                "suggested_entity_ids": [],
                "suggested_tags": ["harvest"],
                "topical_relevance": "high",
                "confidence": 0.7,
                "caveats": "Show notes only.",
            },
            model="anthropic/claude-haiku-4-5",
        )

    updated = enrich_publication_draft(
        draft,
        item,
        berries=berries,
        geographies=geographies,
        entities=entities,
        complete_json=complete,
    )
    assert "&nbsp;" not in updated["publisher_description"]
    assert "promo" in updated["publisher_description"].casefold()
    assert updated["publisher_description"] != updated["summary"]
    assert updated["berry_ids"] == ["berry-blueberry"]
    assert "geo-peru" in updated["geography_ids"]
    assert updated["summary"] == "Peru blueberry harvest conditions are discussed."
    assert updated["why_it_matters"] == "Supply timing in Peru affects export windows."
    assert updated["ai_enrichment"]["model_provenance"]["status"] == "ok"
    assert updated["ai_enrichment"]["model_provenance"]["trust_state"] == "untrusted_suggestion"


def test_ai_failure_does_not_block_deterministic_enrichment() -> None:
    draft = {
        "id": "ev-media-enrich-2",
        "title": "Strawberry acreage in California",
        "summary": "Grower interview.",
        "why_it_matters": "",
        "berry_ids": [],
        "geography_ids": [],
        "entity_ids": [],
    }
    geographies = [{"id": "geo-california", "entity_type": "geography", "name": "California", "aliases": []}]

    def boom(*_args, **_kwargs):
        raise RuntimeError("provider down")

    updated = enrich_publication_draft(
        draft,
        {"description": "Grower interview.", "title": draft["title"]},
        berries=[],
        geographies=geographies,
        entities=[],
        complete_json=boom,
    )
    assert updated["berry_ids"] == ["berry-strawberry"]
    assert "geo-california" in updated["geography_ids"]
    assert updated["ai_enrichment"]["model_provenance"]["status"] == "failed"
    assert updated["publisher_description"] == "Grower interview."
