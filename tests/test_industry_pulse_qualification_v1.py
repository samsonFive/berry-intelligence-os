"""Industry Pulse qualification + editorial relevance V1."""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.qualification_benchmark import BENCHMARK_PATH, score_benchmark
from app.services.industry_pulse.qualify import (
    EDITORIAL_MARKET,
    EDITORIAL_VARIETY,
    QualificationIndex,
    qualify_hit,
)
from app.services.industry_pulse.run import run_pulse
from app.services.industry_pulse.providers import MemoryProvider

REPO = Path(__file__).resolve().parents[1]
RECALL_BENCHMARK = REPO / "data" / "imports" / "missed-intelligence-recall-audit-v1" / "benchmark.json"
# Frozen SHA-256 of the 22-row genetics recall benchmark (LF bytes as stored in git).
RECALL_BENCHMARK_SHA256 = "88b219f0822384c2a220bf55cfc0e38899f51fa370f8dee61e7a53db55091e27"


def _hit(**kwargs) -> DiscoveryHit:
    row = dict(
        title="Planasa launches new strawberry variety in Spain",
        url="https://www.freshplaza.com/article/planasa-strawberry",
        source_domain="freshplaza.com",
        published_date="2026-09-01",
        snippet="Planasa commercial launch of a new strawberry cultivar for Spanish growers.",
        query_id="pulse:strawberry:europe:7d",
        query_text="strawberry Europe",
        geography="europe",
        berry="strawberry",
        topic="industry_pulse",
        provider="memory",
        origin_publisher_url="https://www.freshplaza.com/article/planasa-strawberry",
    )
    row.update(kwargs)
    return DiscoveryHit(**row)


def test_raspberry_pi_rejected() -> None:
    hit = qualify_hit(
        _hit(
            title="Raspberry Pi 5 used for farm genetics models",
            snippet="GPIO cluster",
            berry="raspberry",
        )
    )
    assert hit.qualifying is False
    assert "Raspberry Pi" in hit.qualify_reason


def test_blackberry_device_rejected() -> None:
    hit = qualify_hit(
        _hit(
            title="IP Litigation Insider: All about Key Patent Innovation's BlackBerry bet",
            snippet="patent litigation smartphone",
            berry="blackberry",
        )
    )
    assert hit.qualifying is False
    assert "BlackBerry device" in hit.qualify_reason


def test_blackberry_stock_rejected() -> None:
    hit = qualify_hit(
        _hit(
            title="Is BlackBerry Stock Pricing In A Turnaround That Hasn't Arrived?",
            snippet="BlackBerry shares and equity pricing.",
            berry="blackberry",
        )
    )
    assert hit.qualifying is False
    assert "BlackBerry device" in hit.qualify_reason


def test_cannabis_rejected() -> None:
    hit = qualify_hit(
        _hit(
            title="Royal Queen Seeds: History, Founder & Genetics",
            snippet="Cannabis seed bank breeding",
            berry="raspberry",
        )
    )
    assert hit.qualifying is False
    assert "cannabis" in hit.qualify_reason


def test_recipe_rejected() -> None:
    hit = qualify_hit(_hit(title="10 blueberry smoothie recipes for summer", snippet="Calories and yogurt bowls"))
    assert hit.qualifying is False
    assert "recipe" in hit.qualify_reason


def test_job_posting_rejected() -> None:
    hit = qualify_hit(
        _hit(
            title="Director of Breeding - Fall Creek",
            snippet="Job posting for a blueberry breeding director",
            berry="blueberry",
        )
    )
    assert hit.qualifying is False
    assert "jobs" in hit.qualify_reason


def test_livestock_rejected() -> None:
    hit = qualify_hit(
        _hit(
            title="Spain leads livestock genetic conservation",
            snippet="protection of livestock genetic diversity",
            berry="strawberry",
        )
    )
    assert hit.qualifying is False
    assert "livestock" in hit.qualify_reason


def test_gardening_guide_rejected_even_with_industry_terms() -> None:
    hit = qualify_hit(
        _hit(
            title="raspberry (Rubus idaeus): Care & Growing Guide",
            snippet="Home garden growing guide and planting raspberry plants in pots.",
            berry="raspberry",
        )
    )
    assert hit.qualifying is False
    assert "gardening" in hit.qualify_reason


def test_generic_food_noise_rejected() -> None:
    hit = qualify_hit(
        _hit(
            title="Hyte releases new strawberry-colored PC case",
            snippet="launch of a computer case",
            berry="strawberry",
        )
    )
    assert hit.qualifying is False


def test_school_cafeteria_harvest_rejected() -> None:
    hit = qualify_hit(
        _hit(
            title="Volunteers harvest 350 pounds of blueberries for school cafeterias",
            snippet="Community harvest for school cafeterias.",
            berry="blueberry",
        )
    )
    assert hit.qualifying is False
    assert "event noise" in hit.qualify_reason


def test_blueberry_cultivar_qualifies() -> None:
    hit = qualify_hit(_hit())
    assert hit.qualifying is True
    assert hit.qualify_reason.startswith("QUALIFY:")
    assert hit.editorial_topic == EDITORIAL_VARIETY


def test_raspberry_breeder_qualifies() -> None:
    hit = qualify_hit(
        _hit(
            title="James Hutton raspberry breeder releases Loch Katrine",
            snippet="New raspberry cultivar from the breeding program.",
            berry="raspberry",
        )
    )
    assert hit.qualifying is True


def test_strawberry_production_qualifies() -> None:
    hit = qualify_hit(
        _hit(
            title="Spanish strawberry production and harvest update",
            snippet="Huelva strawberry acreage and harvest conditions.",
            berry="strawberry",
        )
    )
    assert hit.qualifying is True
    assert hit.editorial_topic == EDITORIAL_MARKET


def test_blackberry_trade_qualifies() -> None:
    hit = qualify_hit(
        _hit(
            title="Mexico blackberry export and trade report",
            snippet="Blackberry exports and grower supply.",
            berry="blackberry",
        )
    )
    assert hit.qualifying is True


def test_pbr_qualifies() -> None:
    hit = qualify_hit(
        _hit(
            title="USDA issues PBR certificate for a new blueberry cultivar",
            snippet="Plant variety protection for a commercial blueberry variety.",
            berry="blueberry",
            source_domain="ams.usda.gov",
            url="https://www.ams.usda.gov/pbr/blueberry",
        )
    )
    assert hit.qualifying is True
    assert hit.source_context == "government_agriculture"


def test_patent_genetics_qualifies() -> None:
    hit = qualify_hit(
        _hit(
            title="Plant patent granted for seedless blackberry genetics",
            snippet="CPVO plant patent and gene edited blackberry cultivar.",
            berry="blackberry",
        )
    )
    assert hit.qualifying is True


def test_university_berry_research_qualifies() -> None:
    hit = qualify_hit(
        _hit(
            title="Oregon State University extension reports raspberry field trial results",
            snippet="University extension caneberry trial.",
            berry="raspberry",
            source_domain="extension.oregonstate.edu",
        )
    )
    assert hit.qualifying is True


def test_market_trade_qualifies() -> None:
    hit = qualify_hit(
        _hit(
            title="Blueberry harvest and export update in Peru",
            snippet="blueberry export acreage harvest americas",
            berry="blueberry",
        )
    )
    assert hit.qualifying is True
    assert hit.editorial_topic == EDITORIAL_MARKET


def test_unknown_but_relevant_source_qualifies() -> None:
    hit = qualify_hit(
        _hit(
            title="Rijk Zwaan opens new breeding greenhouse for berries",
            snippet="New berry breeding greenhouse for commercial cultivars.",
            source_domain="agrospectrumindia.com",
            url="https://agrospectrumindia.com/rijk-zwaan",
        )
    )
    assert hit.qualifying is True
    assert hit.source_context == "unknown"


def test_unrelated_gov_rejected() -> None:
    hit = qualify_hit(
        _hit(
            title="FDA PMA device database entry",
            snippet="Medical device PMA supplement.",
            source_domain="accessdata.fda.gov",
            url="https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpma/pma.cfm",
            berry="blueberry",
        )
    )
    assert hit.qualifying is False
    assert any(
        token in hit.qualify_reason
        for token in (".gov", "non-agricultural", "unrelated scientific")
    )


def test_query_provenance_not_enough_alone() -> None:
    hit = qualify_hit(
        _hit(
            title="Local council approves industrial zoning",
            snippet="No crop mentioned.",
            berry="blueberry",
            geography="africa",
        )
    )
    assert hit.qualifying is False
    assert "no berry-crop identity" in hit.qualify_reason


def test_provider_neutral_same_decision() -> None:
    kwargs = dict(
        title="Plant Sciences Genetics unveils primocane blackberry cultivar",
        snippet="New blackberry variety for commercial growers.",
        berry="blackberry",
    )
    google = qualify_hit(_hit(provider="google_news_rss", **kwargs))
    perplexity = qualify_hit(_hit(provider="perplexity", **kwargs))
    assert google.qualifying is True
    assert perplexity.qualifying is True
    assert google.qualify_reasons == perplexity.qualify_reasons


def test_qualification_reasons_deterministic() -> None:
    first = qualify_hit(_hit())
    second = qualify_hit(_hit())
    assert first.qualify_reason == second.qualify_reason
    assert first.qualify_reasons == second.qualify_reasons
    assert first.qualify_reason.startswith("QUALIFY:")


def test_existing_frozen_recall_benchmark_unchanged() -> None:
    payload = RECALL_BENCHMARK.read_bytes().replace(b"\r\n", b"\n")
    digest = hashlib.sha256(payload).hexdigest()
    assert RECALL_BENCHMARK.is_file()
    assert digest == RECALL_BENCHMARK_SHA256
    assert "RA-EU-BK-01" in payload.decode("utf-8")


def test_no_trust_mutation(tmp_path: Path) -> None:
    evidence = tmp_path / "data" / "evidence"
    evidence.mkdir(parents=True)
    sources = tmp_path / "data" / "configuration" / "sources.json"
    sources.parent.mkdir(parents=True)
    sources.write_text("[]", encoding="utf-8")
    report = run_pulse(
        provider=MemoryProvider(hits_by_query_id={"pulse:strawberry:europe:7d": [_hit()]}),
        sources=[],
        published_evidence=[],
        persist_dir=tmp_path / "inbox",
    )
    assert report["auto_trust"] is False
    assert list(evidence.glob("*.json")) == []
    assert sources.read_text(encoding="utf-8") == "[]"


def test_no_static_leakage() -> None:
    source = (REPO / "scripts" / "build_static.py").read_text(encoding="utf-8")
    assert "industry_pulse_qualification" not in source
    feed = (REPO / "app" / "templates" / "feed.html").read_text(encoding="utf-8")
    today = (REPO / "app" / "templates" / "today.html").read_text(encoding="utf-8")
    assert "qualify_reasons" not in feed
    assert "qualification_benchmark" not in today


def test_frozen_benchmark_improves_precision_without_recall_loss() -> None:
    report = score_benchmark()
    assert report["entry_count"] >= 30
    assert BENCHMARK_PATH.is_file()
    assert report["after"]["false_negatives"] == 0
    assert report["after"]["false_positives"] == 0
    assert report["recall_losses"] == []
    assert report["before"]["false_positives"] > report["after"]["false_positives"]
    assert (report["after"]["precision"] or 0) > (report["before"]["precision"] or 0)


def test_index_compiled_once_matches_kwargs() -> None:
    index = QualificationIndex.compile(company_names=["Planasa"], variety_names=["Loch Katrine"])
    named = qualify_hit(
        _hit(title="Planasa strawberry growers in Spain", snippet="commercial strawberry hectares"),
        index=index,
    )
    assert named.qualifying is True
    assert any("Planasa" in reason for reason in named.qualify_reasons)


def test_editorial_topic_not_forced() -> None:
    hit = qualify_hit(
        _hit(
            title="Blueberry growers meet in Chile",
            snippet="Grower meeting about the blueberry crop.",
        )
    )
    assert hit.qualifying is True
    assert hit.editorial_topic is None


def test_qualification_is_cheap_over_hundreds() -> None:
    import time

    index = QualificationIndex.compile(company_names=["Planasa"], variety_names=["Apex"])
    rows = [_hit() for _ in range(250)]
    rows.extend(
        [
            _hit(title="Raspberry Pi cluster", snippet="GPIO"),
            _hit(title="Blueberry muffin recipe", snippet="calories dessert"),
        ]
        * 50
    )
    started = time.perf_counter()
    for row in rows:
        qualify_hit(row, index=index)
    elapsed = time.perf_counter() - started
    assert elapsed < 1.0


def test_qualification_benchmark_is_not_recall_benchmark_autoload() -> None:
    folder = REPO / "data" / "imports" / "industry-pulse-qualification-v1"
    assert (folder / "qualification_benchmark.json").is_file()
    assert not (folder / "benchmark.json").exists()
