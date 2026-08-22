"""Story threads: conservative developing-story grouping. Not a trust layer."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.analyst_queue import load_state, pending_workflow_state
from app.services.morning_brief import build_morning_brief
from app.services.story_threads import (
    compression_report,
    group_story_threads,
    items_form_thread,
    present_thread,
)


PRIORITY = {
    dimension: {"level": "none", "rationale": ""}
    for dimension in ("reading", "testing", "commercial_position", "monitoring")
}


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _isolate(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    (tmp_path / "inbox" / "evidence").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "configuration").mkdir(parents=True, exist_ok=True)
    _write(tmp_path / "data" / "configuration" / "sources.json", [])


def _today() -> str:
    return date.today().isoformat()


def _published(record_id: str, **overrides) -> dict:
    record = {
        "id": record_id,
        "record_type": "evidence",
        "status": "published",
        "review_state": "published",
        "source_type": "news_search",
        "source_name": "FreshPlaza",
        "source_url": "https://example.invalid/" + record_id,
        "title": f"Trusted {record_id}",
        "published_date": "2026-08-10",
        "captured_date": "2026-08-10",
        "summary": "Trusted published article fixture.",
        "why_it_matters": "Analyst-facing rationale.",
        "submitted_by": "reviewer",
        "reviewed_by": "reviewer",
        "reviewed_at": "2026-08-10",
        "priority": deepcopy(PRIORITY),
        "berry_ids": ["berry-blueberry"],
        "entity_ids": [],
        "tags": ["tier-1"],
    }
    record.update(overrides)
    return record


def _draft(record_id: str, **overrides) -> dict:
    record = {
        "id": record_id,
        "record_type": "evidence",
        "evidence_role": "publication_artifact",
        "status": "pending",
        "review_state": "pending_review",
        "source_type": "rss",
        "source_name": "Trade desk",
        "source_url": "https://example.invalid/" + record_id,
        "title": f"Pending {record_id}",
        "published_date": _today(),
        "captured_date": _today(),
        "summary": "Untrusted pending article.",
        "berry_ids": ["berry-blueberry"],
        "entity_ids": [],
        "relevance_tier": "direct",
        "media_format": "web_article",
        "priority": deepcopy(PRIORITY),
    }
    record.update(overrides)
    return record


def _seed_entities(repos) -> None:
    for entity in (
        {
            "id": "company-planasa",
            "record_type": "entity",
            "entity_type": "company",
            "name": "Plantas de Navarra, S.A.",
            "aliases": ["Planasa"],
            "status": "active",
        },
        {
            "id": "company-hortifrut",
            "record_type": "entity",
            "entity_type": "company",
            "name": "Hortifrut S.A.",
            "aliases": ["Hortifrut", "Naturipe"],
            "status": "active",
        },
        {
            "id": "company-ushbc",
            "record_type": "entity",
            "entity_type": "company",
            "name": "U.S. Highbush Blueberry Council",
            "aliases": ["USHBC"],
            "status": "active",
        },
        {
            "id": "geography-mexico",
            "record_type": "entity",
            "entity_type": "geography",
            "name": "Mexico",
            "status": "active",
        },
        {
            "id": "company-driscolls",
            "record_type": "entity",
            "entity_type": "company",
            "name": "Driscoll's, Inc.",
            "aliases": ["Driscoll's"],
            "status": "active",
        },
    ):
        repos.entities.create(entity)


HORTIFRUT_EN = "Naturipe Farms and Hortifrut Expand One of the World's Most Comprehensive Berry Genetics Platforms"
HORTIFRUT_ES = "Naturipe Farms y Hortifrut amplían una de las plataformas de genética de berries más completas"
USHBC_TITLE = "USHBC President on Mexico’s role in the North American blueberry industry: we can’t do it by ourselves"


def test_hortifrut_newsroom_and_spanish_reprint_form_one_thread():
    newsroom = {
        "id": "draft-hf-en",
        "title": HORTIFRUT_EN,
        "source_name": "Hortifrut Newsroom",
        "source_type": "rss",
        "published_date": "2026-07-30",
        "summary": "Hortifrut and Naturipe expand a genetics platform.",
        "primary_subject": {"id": "company-hortifrut", "name": "Hortifrut S.A.", "entity_type": "company"},
    }
    reprint = {
        "id": "draft-hf-es",
        "title": HORTIFRUT_ES,
        "source_name": "International Blueberry Organization",
        "published_date": "2026-07-30",
        "primary_subject": {"id": "company-hortifrut", "name": "Hortifrut S.A.", "entity_type": "company"},
    }
    assert items_form_thread(newsroom, reprint)
    thread = present_thread([newsroom, reprint])
    assert thread["source_count"] == 2
    assert thread["primary"]["id"] == "draft-hf-en"
    assert thread["primary_source_name"] == "Hortifrut Newsroom"
    assert any(row["role"] in {"trade_reprint", "related_coverage"} for row in thread["additional_coverage"])
    assert "trusted conclusion" in thread["why"].casefold() or "not a trusted" in thread["why"].casefold()


def test_exact_title_reprints_thread_across_sources():
    ibo = {
        "id": "draft-ushbc-ibo",
        "title": USHBC_TITLE,
        "source_name": "International Blueberry Organization",
        "published_date": "2026-08-04",
        "primary_subject": {"id": "company-ushbc", "name": "U.S. Highbush Blueberry Council", "entity_type": "company"},
    }
    portal = {
        "id": "draft-ushbc-ffp",
        "title": USHBC_TITLE,
        "source_name": "Fresh Fruit Portal",
        "published_date": "2026-08-04",
        "primary_subject": {"id": "company-ushbc", "name": "U.S. Highbush Blueberry Council", "entity_type": "company"},
    }
    assert items_form_thread(ibo, portal)
    thread = present_thread([ibo, portal])
    assert "International Blueberry Organization" in thread["primary_source_name"]


def test_mexico_conference_does_not_merge_with_ushbc_mexico():
    conference = {
        "id": "draft-mx-conf",
        "title": "Mexico will host a new international conference on blueberry cultivation",
        "source_name": "HortiDaily",
        "published_date": "2026-08-19",
        "primary_subject": {"id": "geography-mexico", "name": "Mexico", "entity_type": "geography"},
    }
    ushbc = {
        "id": "draft-ushbc-mx",
        "title": USHBC_TITLE,
        "source_name": "International Blueberry Organization",
        "published_date": "2026-08-04",
        "primary_subject": {"id": "company-ushbc", "name": "U.S. Highbush Blueberry Council", "entity_type": "company"},
    }
    assert not items_form_thread(conference, ushbc)


def test_same_company_unrelated_stories_do_not_collapse():
    genetics = {
        "id": "draft-hf-genetics",
        "title": HORTIFRUT_EN,
        "source_name": "Hortifrut Newsroom",
        "published_date": "2026-07-30",
        "primary_subject": {"id": "company-hortifrut", "name": "Hortifrut S.A.", "entity_type": "company"},
    }
    archive = {
        "id": "draft-hf-bfruit",
        "title": "Hortifrut takes stake in BFruit",
        "source_name": "Hortifrut Newsroom",
        "published_date": "2020-02-06",
        "primary_subject": {"id": "company-hortifrut", "name": "Hortifrut S.A.", "entity_type": "company"},
    }
    assert not items_form_thread(genetics, archive)


def test_cfia_index_does_not_merge_with_planasa_title():
    cfia = {
        "id": "draft-cfia",
        "title": "CFIA plant breeders' rights index update",
        "source_name": "CFIA",
        "published_date": _today(),
        "primary_subject": {"id": "company-planasa", "name": "Plantas de Navarra, S.A.", "entity_type": "company"},
    }
    planasa = {
        "id": "draft-planasa-maldiva",
        "title": "Blue Maldiva, a Jumbo Blueberry, confirms its adaptability",
        "source_name": "Planasa Newsroom",
        "published_date": _today(),
        "primary_subject": {"id": "company-planasa", "name": "Plantas de Navarra, S.A.", "entity_type": "company"},
    }
    assert not items_form_thread(cfia, planasa)


def test_generic_patent_corroboration_does_not_merge_unrelated_article():
    patent = {
        "id": "ev-patent-uspp35665p2",
        "title": "Blueberry plant named ‘DrisBlueTwentyNine’",
        "source_name": "USPTO plant patent",
        "source_type": "patent_record",
        "published_date": "2024-02-27",
        "kind": "patent",
        "primary_subject": {"id": "company-driscolls", "name": "Driscoll's, Inc.", "entity_type": "company"},
        "evidence_links": [
            {
                "predicate": "corroborates",
                "target_evidence_id": "ev-driscoll-dutch-harvest",
                "status": "proposed",
                "notes": "Assignee/variety entity already linked on existing Evidence; patent filing proposed as additional IP documentation of genetics activity.",
                "proposed_by": "patent-monitor",
            }
        ],
    }
    article = {
        "id": "ev-driscoll-dutch-harvest",
        "title": "Driscoll's announces Dutch harvest fruit program",
        "source_name": "FreshPlaza",
        "published_date": "2026-08-06",
        "primary_subject": {"id": "company-driscolls", "name": "Driscoll's, Inc.", "entity_type": "company"},
    }
    assert not items_form_thread(patent, article)


def test_patent_and_article_thread_when_follows_up_and_variety_overlap():
    patent = {
        "id": "ev-patent-jewel",
        "title": "Blueberry plant named ‘Jewel’",
        "source_name": "USPTO plant patent",
        "source_type": "patent_record",
        "published_date": "2024-07-02",
        "kind": "patent",
        "entity_link_suggestions": [{"name": "Jewel", "role": "variety", "match_status": "unresolved"}],
        "evidence_links": [
            {
                "predicate": "follows_up",
                "target_evidence_id": "draft-jewel-newsroom",
                "status": "proposed",
            }
        ],
    }
    article = {
        "id": "draft-jewel-newsroom",
        "title": "Florida Foundation Seed Producers releases Jewel blueberry",
        "source_name": "Company Newsroom",
        "published_date": "2024-07-03",
        "primary_subject": {"id": "company-florida", "name": "Florida Foundation Seed Producers", "entity_type": "company"},
    }
    assert items_form_thread(patent, article)
    thread = present_thread([patent, article])
    assert thread["source_count"] == 2
    assert {member["id"] for member in thread["members"]} == {"ev-patent-jewel", "draft-jewel-newsroom"}
    assert thread["primary"]["id"] in {"ev-patent-jewel", "draft-jewel-newsroom"}


def test_company_primary_and_variety_primary_thread_on_real_malaika_case():
    """Real case (Raspberry Vertical V1, 2026-08-20): Fruitnet's headline
    led with the company, so attribute_draft() resolved its primary_subject
    to The Summer Berry Company; AICEP's headline led with the variety, so
    its primary_subject resolved to Malaika. Same real harvest announcement,
    4 days apart -- previously false-separated because plain primary_entity_id
    equality never fires across a company/variety type mismatch."""

    fruitnet = {
        "id": "ev-tsbc-harvests-malaika",
        "title": "The Summer Berry Company harvests premium Malaika raspberry variety in Portugal",
        "source_name": "Fruitnet",
        "published_date": "2025-09-29",
        "primary_subject": {
            "id": "company-the-summer-berry-company", "name": "The Summer Berry Company", "entity_type": "company",
        },
        "entities": [
            {"id": "company-the-summer-berry-company", "name": "The Summer Berry Company", "entity_type": "company"},
            {"id": "variety-malaika", "name": "Malaika", "entity_type": "variety"},
        ],
    }
    aicep = {
        "id": "ev-malaika-raises-premium-harvest",
        "title": "Malaika Raspberries Raise the Premium Harvest in Portugal",
        "source_name": "AICEP",
        "published_date": "2025-10-03",
        "primary_subject": {"id": "variety-malaika", "name": "Malaika", "entity_type": "variety"},
        "entities": [
            {"id": "variety-malaika", "name": "Malaika", "entity_type": "variety"},
            {"id": "company-the-summer-berry-company", "name": "The Summer Berry Company", "entity_type": "company"},
        ],
    }
    assert items_form_thread(fruitnet, aicep)
    thread = present_thread([fruitnet, aicep])
    assert thread["source_count"] == 2


def test_company_primary_and_variety_primary_do_not_thread_on_same_company_alone():
    """Same real company (The Summer Berry Company) named as primary_subject
    on both sides is not sufficient by itself -- the variety-primary side
    must also independently reference this specific company, not just any
    company, and the company-primary side must independently reference this
    specific variety. Here the variety-primary article names a different
    real ABB variety (Zawadi) that the company-primary article never
    mentions, so the pair must stay separate even though both are close in
    date and both involve TSBC."""

    company_primary = {
        "id": "ev-tsbc-harvests-malaika-2",
        "title": "The Summer Berry Company harvests premium Malaika raspberry variety in Portugal",
        "source_name": "Fruitnet",
        "published_date": "2025-09-29",
        "primary_subject": {
            "id": "company-the-summer-berry-company", "name": "The Summer Berry Company", "entity_type": "company",
        },
        "entities": [
            {"id": "company-the-summer-berry-company", "name": "The Summer Berry Company", "entity_type": "company"},
            {"id": "variety-malaika", "name": "Malaika", "entity_type": "variety"},
        ],
    }
    variety_primary_different_variety = {
        "id": "ev-zawadi-separate-story",
        "title": "Zawadi raspberry variety trial results published",
        "source_name": "Hort News",
        "published_date": "2025-10-01",
        "primary_subject": {"id": "variety-zawadi", "name": "Zawadi", "entity_type": "variety"},
        "entities": [
            {"id": "variety-zawadi", "name": "Zawadi", "entity_type": "variety"},
            {"id": "company-the-summer-berry-company", "name": "The Summer Berry Company", "entity_type": "company"},
        ],
    }
    assert not items_form_thread(company_primary, variety_primary_different_variety)


def test_shared_variety_alone_does_not_thread_unrelated_company_events():
    """Same real variety (Malaika) named on both sides is not sufficient by
    itself -- a company-primary article about an unrelated company event
    (e.g. a routine portfolio update) that happens to mention Malaika only
    in passing must not thread with a genuinely Malaika-specific story just
    because the variety name co-occurs. The company-primary side here does
    not independently confirm this specific company on the variety-primary
    side (no shared company chip), so the pair stays separate."""

    unrelated_company_news = {
        "id": "ev-abb-unrelated-portfolio-update",
        "title": "Advanced Berry Breeding expands raspberry portfolio",
        "source_name": "Fruitnet",
        "published_date": "2025-09-30",
        "primary_subject": {
            "id": "company-advanced-berry-breeding", "name": "Advanced Berry Breeding", "entity_type": "company",
        },
        "entities": [
            {"id": "company-advanced-berry-breeding", "name": "Advanced Berry Breeding", "entity_type": "company"},
        ],
    }
    malaika_taste_award = {
        "id": "ev-malaika-taste-award",
        "title": "Malaika wins taste award",
        "source_name": "FreshFruitPortal",
        "published_date": "2025-09-30",
        "primary_subject": {"id": "variety-malaika", "name": "Malaika", "entity_type": "variety"},
        "entities": [{"id": "variety-malaika", "name": "Malaika", "entity_type": "variety"}],
    }
    assert not items_form_thread(unrelated_company_news, malaika_taste_award)


def test_generic_species_overlap_does_not_satisfy_cross_subject_edge():
    """Two unrelated company/variety events that only share generic crop
    words (raspberry, berry) -- never a real company or variety match --
    must stay separate. Distinctive named entities only, never trait-*
    or species words, per the calibration lesson this mission carries
    forward."""

    company_event = {
        "id": "ev-chambers-raspberry-trial",
        "title": "Chambers launches major raspberry trial",
        "source_name": "Fruitnet",
        "published_date": "2020-09-08",
        "primary_subject": {"id": "company-chambers", "name": "Chambers", "entity_type": "company"},
        "entities": [{"id": "company-chambers", "name": "Chambers", "entity_type": "company"}],
    }
    variety_event = {
        "id": "ev-double-gold-release",
        "title": "Cornell releases two new raspberry varieties",
        "source_name": "Cornell Chronicle",
        "published_date": "2020-09-10",
        "primary_subject": {"id": "variety-double-gold", "name": "Double Gold", "entity_type": "variety"},
        "entities": [{"id": "variety-double-gold", "name": "Double Gold", "entity_type": "variety"}],
    }
    assert not items_form_thread(company_event, variety_event)


def test_company_newsroom_and_trade_reprint_thread_on_real_redsayra_case():
    """Real case (Strawberry Vertical V1, 2026-08-20): Planasa's own
    newsroom article resolves company-primary via newsroom_identity
    attribution (the source itself, not the title, names the company);
    Fruitnet's third-party trade coverage of the identical claim resolves
    variety-primary. Same real event (RedSayra's market-share claim), same
    day -- the company-newsroom-to-trade-reprint pattern Section 6
    describes, now recognized as one developing story."""

    planasa_newsroom = {
        "id": "ev-planasa-redsayra-newsroom",
        "title": "RedSayra positions itself as the most widely grown strawberry variety in Spain",
        "source_name": "Planasa Newsroom",
        "published_date": "2026-03-16",
        "primary_subject": {"id": "company-planasa", "name": "Plantas de Navarra, S.A.", "entity_type": "company"},
        "entities": [
            {"id": "company-planasa", "name": "Plantas de Navarra, S.A.", "entity_type": "company"},
            {"id": "variety-redsayra", "name": "RedSayra", "entity_type": "variety"},
        ],
    }
    fruitnet_reprint = {
        "id": "ev-redsayra-most-planted-fruitnet",
        "title": "RedSayra becomes Spain's most planted strawberry",
        "source_name": "Fruitnet",
        "published_date": "2026-03-16",
        "primary_subject": {"id": "variety-redsayra", "name": "RedSayra", "entity_type": "variety"},
        "entities": [
            {"id": "variety-redsayra", "name": "RedSayra", "entity_type": "variety"},
            {"id": "company-planasa", "name": "Plantas de Navarra, S.A.", "entity_type": "company"},
        ],
    }
    assert items_form_thread(planasa_newsroom, fruitnet_reprint)


def test_different_patent_filings_for_same_breeder_stay_separate():
    """Two different plant-patent filings from the same real breeder
    (Planasa) for two different real varieties, years apart, must stay
    separate -- same-company mention (even patent-assignee mention) is
    never enough on its own, and there is no deterministic follows_up/
    same_signal evidence_links entry connecting them."""

    blue_manila_patent = {
        "id": "ev-patent-blue-manila",
        "title": "Blueberry plant named 'Blue Manila'",
        "source_name": "USPTO plant patent",
        "source_type": "patent_record",
        "published_date": "2020-01-14",
        "kind": "patent",
        "primary_subject": {"id": "company-planasa", "name": "Plantas de Navarra, S.A.", "entity_type": "company"},
        "entities": [
            {"id": "company-planasa", "name": "Plantas de Navarra, S.A.", "entity_type": "company"},
            {"id": "variety-blue-manila", "name": "Blue Manila", "entity_type": "variety"},
        ],
    }
    blue_maldiva_patent = {
        "id": "ev-patent-blue-maldiva",
        "title": "Blueberry plant named 'Blue Maldiva'",
        "source_name": "USPTO plant patent",
        "source_type": "patent_record",
        "published_date": "2022-06-01",
        "kind": "patent",
        "primary_subject": {"id": "company-planasa", "name": "Plantas de Navarra, S.A.", "entity_type": "company"},
        "entities": [
            {"id": "company-planasa", "name": "Plantas de Navarra, S.A.", "entity_type": "company"},
            {"id": "variety-blue-maldiva", "name": "Blue Maldiva", "entity_type": "variety"},
        ],
    }
    assert not items_form_thread(blue_manila_patent, blue_maldiva_patent)


def test_brief_review_soon_collapses_reprint_into_review_now_thread(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    _seed_entities(repos)
    drafts = [
        _draft(
            "draft-hf-en",
            title=HORTIFRUT_EN,
            source_id="source-hortifrut-newsroom",
            source_name="Hortifrut Newsroom",
            published_date="2026-07-30",
            captured_date="2026-07-30",
            summary="Hortifrut and Naturipe expand a genetics platform.",
        ),
        _draft(
            "draft-hf-es",
            title=HORTIFRUT_ES,
            source_name="International Blueberry Organization",
            published_date="2026-07-30",
            captured_date="2026-07-30",
        ),
        _draft(
            "draft-mx-conf",
            title="Mexico will host a new international conference on blueberry cultivation",
            source_name="HortiDaily",
            published_date=_today(),
        ),
    ]
    brief = build_morning_brief(
        inbox_dir=main.INBOX_DIR,
        published=[],
        drafts=drafts,
        entities={entity["id"]: entity for entity in repos.entities.list()},
        berry_labels={"berry-blueberry": "Blueberry"},
        sources=[
            {
                "id": "source-hortifrut-newsroom",
                "label": "Hortifrut Newsroom",
                "monitoring_priority": "high",
                "linked_competitor_ids": ["company-hortifrut"],
            }
        ],
        mark_seen=False,
    )
    buckets = {group["key"]: group for group in brief["pending_triage"]["buckets"]}
    review_now = buckets["review_now"]
    review_soon = buckets["review_soon"]
    assert review_now["count"] >= 1
    now_ids = [item["id"] for item in review_now["entries"]]
    soon_ids = [item["id"] for item in review_soon["entries"]]
    assert "draft-hf-es" not in soon_ids
    hortifrut_card = next(item for item in review_now["entries"] if item.get("is_thread") or item.get("id") == "draft-hf-en")
    if hortifrut_card.get("is_thread"):
        assert hortifrut_card["source_count"] == 2
        assert "draft-hf-es" in hortifrut_card["member_ids"]
        assert hortifrut_card["primary_source_name"] == "Hortifrut Newsroom"
    assert "draft-mx-conf" in soon_ids or any(
        "conference" in str(item.get("title") or "").casefold() for item in review_soon["entries"]
    )
    hortifrut_delta = next(row for row in brief["company_deltas"] if row["id"] == "company-hortifrut")
    assert any(bullet.get("is_thread") or "Developing" in str(bullet.get("label") or "") for bullet in hortifrut_delta["bullets"])


def test_dismiss_redundant_coverage_keeps_file(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    _seed_entities(repos)
    reprint = _draft(
        "draft-hf-es",
        title=HORTIFRUT_ES,
        source_name="International Blueberry Organization",
        published_date="2026-07-30",
    )
    _write(tmp_path / "inbox" / "evidence" / "draft-hf-es.json", reprint)
    client = TestClient(app)
    response = client.post(
        "/queues/pending/draft-hf-es",
        data={"action": "dismiss", "reviewer": "analyst", "return_to": "/threads/draft-hf-en"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    stored = json.loads((tmp_path / "inbox" / "evidence" / "draft-hf-es.json").read_text(encoding="utf-8"))
    assert stored["status"] == "pending"
    assert pending_workflow_state("draft-hf-es", load_state(main.INBOX_DIR)) == "dismissed"


def test_thread_reader_renders_grouped_sources(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    _seed_entities(repos)
    newsroom = _draft(
        "draft-hf-en",
        title=HORTIFRUT_EN,
        source_id="source-hortifrut-newsroom",
        source_name="Hortifrut Newsroom",
        published_date="2026-07-30",
        captured_date="2026-07-30",
        summary="Hortifrut and Naturipe expand a genetics platform.",
    )
    reprint = _draft(
        "draft-hf-es",
        title=HORTIFRUT_ES,
        source_name="International Blueberry Organization",
        published_date="2026-07-30",
        captured_date="2026-07-30",
    )
    _write(tmp_path / "inbox" / "evidence" / "draft-hf-en.json", newsroom)
    _write(tmp_path / "inbox" / "evidence" / "draft-hf-es.json", reprint)
    _write(
        tmp_path / "data" / "configuration" / "sources.json",
        [
            {
                "id": "source-hortifrut-newsroom",
                "label": "Hortifrut Newsroom",
                "monitoring_priority": "high",
                "linked_competitor_ids": ["company-hortifrut"],
            }
        ],
    )
    client = TestClient(app)
    page = client.get("/threads/draft-hf-en")
    assert page.status_code == 200
    assert "Developing story" in page.text
    assert "Not a Fact" in page.text or "not a Fact" in page.text
    assert "Hortifrut Newsroom" in page.text
    assert "Dismiss redundant coverage" in page.text
    assert "Trust thread" not in page.text


def test_watch_activity_collapses_two_stories(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    _seed_entities(repos)
    watch = deepcopy(PRIORITY)
    watch["reading"] = {"level": "medium", "rationale": "Watch Hortifrut."}
    watch["monitoring"] = {"level": "high", "rationale": "Watch Hortifrut."}
    repos.evidence.create(
        _published(
            "ev-hf-watch",
            title="Hortifrut breeding program",
            entity_ids=["company-hortifrut"],
            priority=watch,
        )
    )
    drafts = [
        _draft(
            "draft-hf-en",
            title=HORTIFRUT_EN,
            source_id="source-hortifrut-newsroom",
            source_name="Hortifrut Newsroom",
            published_date=_today(),
        ),
        _draft(
            "draft-hf-es",
            title=HORTIFRUT_ES,
            source_name="International Blueberry Organization",
            published_date=_today(),
        ),
        _draft(
            "draft-hf-colombia",
            title="Hortifrut moves into Colombian blueberries this season",
            source_id="source-hortifrut-newsroom",
            source_name="Hortifrut Newsroom",
            published_date=_today(),
        ),
        _draft(
            "draft-hf-colombia-reprint",
            title="Hortifrut moves into Colombian blueberries this season",
            source_name="Fresh Fruit Portal",
            published_date=_today(),
        ),
    ]
    brief = build_morning_brief(
        inbox_dir=main.INBOX_DIR,
        published=repos.evidence.list(),
        drafts=drafts,
        entities={entity["id"]: entity for entity in repos.entities.list()},
        berry_labels={"berry-blueberry": "Blueberry"},
        sources=[
            {
                "id": "source-hortifrut-newsroom",
                "label": "Hortifrut Newsroom",
                "monitoring_priority": "high",
                "linked_competitor_ids": ["company-hortifrut"],
            }
        ],
        mark_seen=False,
    )
    hortifrut = next(row for row in brief["watch_activity"] if row["id"] == "company-hortifrut")
    assert hortifrut["item_count"] >= 4
    assert hortifrut["story_count"] < hortifrut["item_count"]
    thread_entries = [entry for entry in hortifrut["entries"] if entry.get("is_thread")]
    assert len(thread_entries) >= 2
    assert all(int(entry.get("source_count") or 0) >= 2 for entry in thread_entries)
    assert "developing" in hortifrut["happened"].casefold()
    assert "source" in hortifrut["kind_summary"]


def test_compression_report_counts_distinct_stories():
    items = [
        {
            "id": "a",
            "title": HORTIFRUT_EN,
            "source_name": "Hortifrut Newsroom",
            "published_date": "2026-07-30",
            "primary_subject": {"id": "company-hortifrut", "name": "Hortifrut S.A.", "entity_type": "company"},
        },
        {
            "id": "b",
            "title": HORTIFRUT_ES,
            "source_name": "IBO",
            "published_date": "2026-07-30",
            "primary_subject": {"id": "company-hortifrut", "name": "Hortifrut S.A.", "entity_type": "company"},
        },
        {
            "id": "c",
            "title": "South African blueberry season faces extreme weather",
            "source_name": "IBO",
            "published_date": "2026-08-13",
        },
    ]
    report = compression_report(items)
    assert report["raw_items"] == 3
    assert report["distinct_stories"] == 2
    assert report["multi_source_threads"] == 1
    assert report["singletons"] == 1
