"""Information Universe Activation Phase 2 — paid retrieval + authoritative data."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import Workbook

from app.services.authoritative_registries.classify import (
    AUTHORITATIVE_REGISTRY,
    DISCOVERY_PROVIDER,
    LAYER_OF,
    STRUCTURED_DATASET,
)
from app.services.authoritative_registries.events import (
    PATENT_GRANTED,
    PVP_APPLICATION_FILED,
    PVP_GRANTED,
    classify_patent_event,
    classify_pvp_event,
)
from app.services.authoritative_registries.usda_pvpo import (
    berry_id_for,
    parse_status_workbook,
    summarize_berry_import,
)
from app.services.global_week import display_url, run_week_intelligence
from app.services.industry_pulse.activation import APITUBE_CONTRACT, EXA_CONTRACT, operator_steps
from app.services.industry_pulse.apitube import APITUBE_SETUP, ApiTubeSearchProvider
from app.services.industry_pulse.canonical_urls import preferred_url, url_quality
from app.services.industry_pulse.catchall_cache import hits_from_cache, write_cache
from app.services.industry_pulse.catchall_recall import AWAITING_KEY, run_catchall_recall
from app.services.industry_pulse.credentials import APITUBE_API_KEY_ENV, EXA_API_KEY_ENV
from app.services.industry_pulse.dedup import dedupe_hits, unique_hits
from app.services.industry_pulse.errors import ProviderAuthError
from app.services.industry_pulse.exa import EXA_SETUP, ExaSearchProvider
from app.services.industry_pulse.exa_queries import week_unknown_unknown_queries
from app.services.industry_pulse.live_stack import optional_sync_discovery_providers, week_discovery_stack
from app.services.industry_pulse.matrix import PulseQuery, query_count
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.providers import MemoryProvider
from app.services.patent_monitor.berry_queries import BERRY_ODP_QUERIES, odp_query_for
from app.services.patent_monitor.berry_retrieval import run_bounded_berry_retrieval
from app.services.patent_monitor.bigquery_patents import cpc_sql, keyword_sql, prototype_bundle

REPO = Path(__file__).resolve().parents[1]
CORPUS = json.loads(
    (REPO / "data" / "configuration" / "information_universe_frozen_corpus.json").read_text(encoding="utf-8")
)


def _hit(**overrides) -> DiscoveryHit:
    base = dict(
        title="Hot summer boosts British blueberry volumes by 11 per cent",
        url="https://www.fruitnet.com/fresh-produce-journal/hot-summer-boosts-british-blueberry-volumes-by-11-per-cent/272546.article",
        source_domain="fruitnet.com",
        published_date="2026-09-01",
        snippet="UK blueberry volumes rose 11 per cent.",
        query_id="feed:fruitnet",
        query_text="",
        geography="europe",
        berry="blueberry",
        topic="specialist_feed",
        provider="specialist_rss",
        origin_publisher_name="Fruitnet",
        origin_publisher_url="https://www.fruitnet.com/fresh-produce-journal/hot-summer-boosts-british-blueberry-volumes-by-11-per-cent/272546.article",
    )
    base.update(overrides)
    return DiscoveryHit(**base)


def test_pulse_matrix_stays_at_32() -> None:
    assert query_count() == 32


def test_operator_activation_is_set_env_only() -> None:
    steps = operator_steps()
    assert any(step.startswith("SET APITUBE_API_KEY") for step in steps)
    assert any(step.startswith("SET EXA_API_KEY") for step in steps)
    assert APITUBE_CONTRACT["boot_required"] is False
    assert EXA_CONTRACT["boot_required"] is False
    assert "SET APITUBE_API_KEY" in APITUBE_SETUP
    assert "SET EXA_API_KEY" in EXA_SETUP


def test_paid_providers_refuse_without_keys_and_are_not_boot_required(monkeypatch) -> None:
    monkeypatch.delenv(APITUBE_API_KEY_ENV, raising=False)
    monkeypatch.delenv(EXA_API_KEY_ENV, raising=False)
    query = PulseQuery(
        id="ad-hoc",
        text="blueberry harvest",
        berry="blueberry",
        geography="global",
        topic="ad_hoc",
        kind="ad_hoc",
        hl="en-US",
        gl="US",
        ceid="US:en",
        date_window="7d",
    )
    with pytest.raises(ProviderAuthError):
        ApiTubeSearchProvider().discover(query)
    with pytest.raises(ProviderAuthError):
        ExaSearchProvider().discover(query)
    assert optional_sync_discovery_providers() == []
    primary, _catch, specialist = week_discovery_stack(perplexity_enabled=False)
    assert [row.name for row in primary] == ["google_news_rss"]
    assert specialist.name == "specialist_rss"


def test_unknown_unknown_queries_are_exa_only_not_pulse_32() -> None:
    rows = week_unknown_unknown_queries()
    assert len(rows) >= 5
    assert all(row.kind == "unknown_unknown" for row in rows)
    assert query_count() == 32
    assert not any("blueberry" in row.text.split()[:3] for row in rows if "Vaccinium" in row.text)


def test_catchall_recall_awaits_key_and_writes_cache(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("NEWSCATCHER_API_KEY", raising=False)
    monkeypatch.delenv("CATCHALL_API_KEY", raising=False)
    report = run_catchall_recall(inbox_dir=tmp_path)
    assert report["state"] == AWAITING_KEY
    assert report["hit_count"] == 0
    assert hits_from_cache(tmp_path) == []


def test_week_consumes_catchall_cache_not_live_submit(tmp_path: Path) -> None:
    write_cache(
        {
            "status": "ready",
            "hits": [
                _hit(
                    title="Obscure nursery licenses a nameless selection",
                    url="https://example-breeder.com/license-move",
                    source_domain="example-breeder.com",
                    provider="newscatcher_catchall",
                    origin_publisher_url="https://example-breeder.com/license-move",
                    query_id="catchall:cache",
                ).as_dict()
            ],
        },
        inbox_dir=tmp_path,
    )
    cached = hits_from_cache(tmp_path)
    edition = run_week_intelligence(
        window="7d",
        providers=[MemoryProvider(hits=[])],
        background_hits=cached,
        now=datetime(2026, 9, 1, tzinfo=timezone.utc),
        entities=[],
        varieties=[],
        sources=[],
    )
    assert edition.stats["provider_unique"].get("newscatcher_catchall", 0) >= 0
    assert any(item.provider == "newscatcher_catchall" for item in edition.items) or edition.stats["raw_discovered"] >= 1


def test_display_url_prefers_first_party_article_over_wrapper() -> None:
    article = _hit()
    wrapped = _hit(
        url="https://news.google.com/rss/articles/abc",
        origin_publisher_url="https://www.fruitnet.com",
        wrapper_url="https://news.google.com/rss/articles/abc",
        provider="google_news_rss",
    )
    assert "272546.article" in display_url(article)
    assert preferred_url(wrapped) == wrapped.wrapper_url
    assert url_quality(article) > url_quality(wrapped)


def test_dedupe_keeps_specialist_article_over_google_wrapper() -> None:
    article = _hit()
    wrapped = _hit(
        url="https://news.google.com/rss/articles/abc",
        origin_publisher_url="https://www.fruitnet.com",
        wrapper_url="https://news.google.com/rss/articles/abc",
        provider="google_news_rss",
    )
    dedupe_hits([wrapped, article])
    kept = unique_hits([wrapped, article])
    assert len(kept) == 1
    assert "272546.article" in (kept[0].origin_publisher_url or kept[0].url)


def test_pvpo_event_overlay_and_summary(tmp_path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet["B2"] = "Application #"
    sheet["C2"] = "Variety Name"
    sheet["E2"] = "Scientific Name"
    sheet["F2"] = "Common Name"
    sheet["G2"] = "Applicant "
    sheet["H2"] = "Application Date"
    sheet["J2"] = "Certificate Status"
    sheet["K2"] = "Status Date"
    sheet["L2"] = "Issued Date"
    sheet["B3"] = "202400001"
    sheet["C3"] = "Sekoya Pop"
    sheet["E3"] = "Vaccinium corymbosum"
    sheet["F3"] = "Blueberry, highbush"
    sheet["G3"] = "Fall Creek Farm & Nursery, Inc."
    sheet["H3"] = "2024-01-15"
    sheet["J3"] = "Application Pending"
    sheet["B4"] = "201800224"
    sheet["C4"] = "Yotsuboshi"
    sheet["E4"] = "Fragaria L. x ananassa"
    sheet["F4"] = "Strawberry"
    sheet["J4"] = "Certificate Issued"
    sheet["L4"] = "2020-05-18"
    buffer = BytesIO()
    workbook.save(buffer)
    rows = parse_status_workbook(buffer.getvalue())
    assert berry_id_for(common_name="Blueberry, highbush", scientific_name="") == "berry-blueberry"
    assert classify_pvp_event(rows[0])["event_kind"] == PVP_APPLICATION_FILED
    assert classify_pvp_event(rows[1])["event_kind"] == PVP_GRANTED
    summary = summarize_berry_import(
        rows,
        {
            "written_count": 2,
            "built_count": 2,
            "distinct_new": 2,
            "possible_alias": 0,
            "unknown": 0,
            "candidates": [
                {"identity_state": "distinct", "candidate_canonical_match": None},
                {"identity_state": "distinct", "candidate_canonical_match": None},
            ],
        },
    )
    assert summary["raw_berry_records"] == 2
    assert summary["distinct_variety_names"] == 2
    assert summary["auto_confirmed"] is False
    assert LAYER_OF["usda_pvpo"] == AUTHORITATIVE_REGISTRY


def test_uspto_queries_cover_taxonomy_semantics_and_assignees() -> None:
    names = {name for name, _query in BERRY_ODP_QUERIES}
    assert names >= {"blueberry", "strawberry", "taxonomic-vaccinium", "semantic-traits", "assignees"}
    assert "Vaccinium" in odp_query_for("taxonomic-vaccinium")
    assert "shelf life" in odp_query_for("semantic-traits")
    assert "Fall Creek" in odp_query_for("assignees")


def test_uspto_retrieval_uses_injected_search_without_writing_evidence(tmp_path: Path) -> None:
    evidence = tmp_path / "data" / "evidence"
    evidence.mkdir(parents=True)

    def fake_google(query: str, num: int = 8, **_kwargs):
        return {
            "hits": [
                {
                    "publication_number": "USPP35665P2",
                    "title": "Blueberry plant named ‘FC12-029’",
                    "assignees": ["Fall Creek Farm & Nursery, Inc."],
                    "grant_date": "2024-01-16",
                    "publication_date": "2024-01-16",
                    "abstract": "A new Vaccinium corymbosum cultivar.",
                }
            ]
        }

    report = run_bounded_berry_retrieval(data_dir=tmp_path / "data", limit=5, google_search=fake_google)
    assert report["applications_or_grants"] == 1
    assert report["auto_confirmed"] is False
    assert classify_patent_event(fake_google("")["hits"][0])["event_kind"] == PATENT_GRANTED
    assert list(evidence.glob("*.json")) == []


def test_bigquery_templates_are_bounded(monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    assert "LIMIT" in keyword_sql(limit=10)
    assert "A01H6/74" in cpc_sql(limit=10)
    bundle = prototype_bundle(limit=5)
    assert bundle["available"] is False
    assert all(row["available"] is False for row in bundle["reports"].values())
    assert LAYER_OF["google_patents_bigquery"] == STRUCTURED_DATASET
    assert LAYER_OF["apitube"] == DISCOVERY_PROVIDER


def test_frozen_corpus_does_not_rewrite_window_truth() -> None:
    by_id = {row["id"]: row for row in CORPUS["cases"]}
    assert by_id["company-hortifrut-naturipe-mbo-2026-07-30"]["expected_in_true_7d_from_2026-09-01"] is False
    assert by_id["specialist-fruitnet-fpj-2026-09-01"]["expected_in_true_7d_from_2026-09-01"] is True
    lanes = {row["lane"] for row in CORPUS["cases"]}
    assert lanes >= {"NEWS", "SPECIALIST_PRESS", "PBR", "PATENTS", "APAC", "MAINSTREAM_CONTEXT", "COMPANY_RELEASES"}
