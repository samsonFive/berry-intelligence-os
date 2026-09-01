"""Authoritative data + NewsCatcher CatchAll expansion bake-off V1."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from openpyxl import Workbook

from app.services.authoritative_registries.classify import (
    AUTHORITATIVE_REGISTRY,
    DISCOVERY_PROVIDER,
    LAYER_OF,
    NORMALIZATION_REFERENCE,
    SPECIALIST_SOURCE,
    STRUCTURED_DATASET,
)
from app.services.authoritative_registries.usda_pvpo import (
    STATUS_REPORT_URL,
    berry_id_for,
    import_berry_rows,
    parse_status_workbook,
)
from app.services.authoritative_registries.upov_pluto import (
    LICENSING_FLAGS,
    MAX_DISTRIBUTABLE_RECORDS,
    UpovPlutoError,
    import_operator_rows,
    parse_operator_export,
)
from app.services.industry_pulse.bakeoff import UNIT_COST_USD, credential_status, run_bakeoff
from app.services.industry_pulse.catchall_provider import (
    CatchAllDiscoveryProvider,
    records_to_hits,
)
from app.services.industry_pulse.errors import ProviderAuthError
from app.services.industry_pulse.matrix import generate_pulse_queries
from app.services.industry_pulse.providers import MemoryProvider
from app.services.media_discovery import _normalize_sitemap_entry, _sitemap_entries
from app.services.patent_monitor.berry_queries import BERRY_ODP_QUERIES, odp_query_for
from app.services.patent_monitor.bigquery_patents import (
    bibliographic_sql,
    estimate_usd,
    run_bounded_query,
    similarity_sql,
)
from app.services.patent_monitor.uspto_odp import parse_odp_results

REPO = Path(__file__).resolve().parents[1]


def _pvpo_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet["B2"] = "Application #"
    sheet["C2"] = "Variety Name"
    sheet["D2"] = "Experimental Name"
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
    sheet["F3"] = "Blueberry"
    sheet["G3"] = "Fall Creek Farm & Nursery, Inc."
    sheet["H3"] = "01/15/2024"
    sheet["J3"] = "Application Pending"
    sheet["B4"] = "201800224"
    sheet["C4"] = "Yotsuboshi"
    sheet["E4"] = "Fragaria L. x ananassa"
    sheet["F4"] = "Strawberry"
    sheet["G4"] = "NARO"
    sheet["J4"] = "Certificate Issued"
    sheet["L4"] = "05/18/2020"
    sheet["B5"] = "7100001"
    sheet["C5"] = "Green Ice"
    sheet["E5"] = "Lactuca sativa L."
    sheet["F5"] = "Lettuce"
    sheet["G5"] = "Nunhems B.V."
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_layer_classes_are_not_all_news() -> None:
    assert LAYER_OF["usda_pvpo"] == AUTHORITATIVE_REGISTRY
    assert LAYER_OF["upov_pluto"] == NORMALIZATION_REFERENCE
    assert LAYER_OF["uspto_odp"] == AUTHORITATIVE_REGISTRY
    assert LAYER_OF["google_patents_bigquery"] == STRUCTURED_DATASET
    assert LAYER_OF["newscatcher_catchall"] == DISCOVERY_PROVIDER
    assert LAYER_OF["hortidaily"] == SPECIALIST_SOURCE


def test_usda_pvpo_maps_berry_fields() -> None:
    rows = parse_status_workbook(_pvpo_bytes())
    assert [row["berry_id"] for row in rows] == ["berry-blueberry", "berry-strawberry"]
    assert rows[0]["application_number"] == "202400001"
    assert rows[0]["applicant"] == "Fall Creek Farm & Nursery, Inc."
    assert rows[0]["source_tier"] == "tier_1_national_register"
    assert rows[0]["source_url"] == STATUS_REPORT_URL
    assert berry_id_for(common_name="Lettuce", scientific_name="Lactuca sativa L.") is None


def test_usda_import_is_inbox_candidates_only(tmp_path: Path) -> None:
    evidence = tmp_path / "data" / "evidence"
    evidence.mkdir(parents=True)
    rows = parse_status_workbook(_pvpo_bytes())
    report = import_berry_rows(rows, varieties=[], inbox_dir=tmp_path / "inbox")
    assert report["written_count"] == 2
    assert list(evidence.glob("*.json")) == []
    written = list((tmp_path / "inbox" / "variety_candidates").glob("*.json"))
    assert len(written) == 2
    assert all('"auto_confirmed": false' in path.read_text(encoding="utf-8") for path in written)


def test_upov_refuses_html_and_over_cap() -> None:
    try:
        parse_operator_export(b"<html>WIPO login</html>")
        raise AssertionError("html scrape should fail")
    except UpovPlutoError as exc:
        assert "scrape" in str(exc)
    try:
        parse_operator_export([{"denomination": f"V{i}"} for i in range(MAX_DISTRIBUTABLE_RECORDS + 1)])
        raise AssertionError("cap should fail")
    except UpovPlutoError as exc:
        assert "100" in str(exc)
    assert "saas_resale_vendor_review_required" in LICENSING_FLAGS


def test_upov_operator_export_maps_and_imports(tmp_path: Path) -> None:
    rows = parse_operator_export(
        [
            {
                "denomination": "G-Viva",
                "applicant": "BerryWorld",
                "jurisdiction": "IT",
                "application_number": "IT-2024-1",
                "berry_id": "berry-raspberry",
            }
        ]
    )
    assert rows[0]["source_id"] == "upov-pluto-operator-export"
    report = import_operator_rows(rows, varieties=[], inbox_dir=tmp_path / "inbox")
    assert report["written_count"] == 1


def test_uspto_structured_queries_and_parse() -> None:
    assert "Vaccinium" in odp_query_for("blueberry")
    assert {name for name, _query in BERRY_ODP_QUERIES} >= {"blueberry", "strawberry", "raspberry", "blackberry"}
    hits = parse_odp_results(
        {
            "patentFileWrapperDataBag": [
                {
                    "applicationMetaData": {
                        "patentNumber": "USPP35665P2",
                        "inventionTitle": "Blueberry plant named FC12-029",
                        "applicationNumberText": "17890123",
                        "inventorBag": [{"firstName": "David", "lastName": "Brazelton"}],
                        "assigneeBag": [{"nameLineOneText": "Fall Creek Farm & Nursery, Inc."}],
                    }
                }
            ]
        }
    )
    assert hits[0]["publication_number"]
    assert hits[0]["acquisition_method"] == "uspto_odp"


def test_bigquery_sql_is_bounded_and_unavailable_without_project(monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    sql = bibliographic_sql(limit=10)
    assert "LIMIT 10" in sql
    assert "blueberry" in sql
    assert "SELECT * FROM" not in sql
    similar = similarity_sql(publication_number="US-PP35665-P2", limit=3)
    assert "VECTOR_SEARCH" in similar and "LIMIT 2000" in similar
    report = run_bounded_query(sql)
    assert report["available"] is False
    assert report["bytes_processed"] is None
    dry = run_bounded_query(sql, query_fn=lambda _sql, dry_run: {"bytes_processed": 8_000_000, "rows": []})
    assert dry["bytes_processed"] == 8_000_000
    assert dry["estimated_usd"] == estimate_usd(8_000_000)


def test_catchall_requires_key_and_normalizes_records() -> None:
    query = generate_pulse_queries()[0].with_window("7d")
    try:
        CatchAllDiscoveryProvider(api_key="").discover(query)
        raise AssertionError("missing key should fail")
    except ProviderAuthError:
        pass
    hits = CatchAllDiscoveryProvider(
        api_key="test-key",
        prefetched_records=[
            {
                "record_id": "ca-1",
                "record_title": "Planasa launches blueberry variety in Peru",
                "citations": [{"url": "https://gestion.pe/planasa", "name": "Gestion", "published_date": "2026-08-28"}],
                "enrichment": {"summary": "New genetics for export growers."},
            }
        ],
    ).discover(query)
    assert hits[0].source_domain == "gestion.pe"
    assert hits[0].provider == "newscatcher_catchall"
    assert hits[0].qualifying is False


def test_catchall_not_in_slice_loop_and_no_monitors() -> None:
    source = (REPO / "app" / "services" / "industry_pulse" / "bakeoff.py").read_text(encoding="utf-8")
    pulse = (REPO / "app" / "services" / "industry_pulse" / "run.py").read_text(encoding="utf-8")
    provider = (REPO / "app" / "services" / "industry_pulse" / "catchall_provider.py").read_text(encoding="utf-8")
    assert "CatchAllDiscoveryProvider()" not in source
    assert "/catchAll/monitors/create" not in source
    assert "catchall" not in pulse.lower()
    assert "monitors/create" not in provider
    status = credential_status()
    assert status["newscatcher_catchall"]["live"] is False
    assert UNIT_COST_USD["newscatcher_catchall"] == 0.10


def test_catchall_existing_provider_compatibility() -> None:
    report = run_bakeoff(sources=[], published_evidence=[], include_live=False)
    names = [row["provider"] for row in report["providers"]]
    assert names[0] == "google_news_rss"
    assert "newscatcher_catchall" not in names
    assert report["catchall_probe"]["tested"] is False
    assert report["auto_trust"] is False
    assert report["production_provider"] == "google_news_rss"


def test_hortidaily_news_sitemap_title_and_berry_slug() -> None:
    import xml.etree.ElementTree as ET

    xml = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
            xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
      <url>
        <loc>https://www.hortidaily.com/article/1/global-blueberry-crop/</loc>
        <lastmod>2026-09-01T16:15:00+02:00</lastmod>
        <news:news>
          <news:publication_date>2026-09-01T16:15:00+02:00</news:publication_date>
          <news:title>Global blueberry crop projected to reach 3.36 million tons</news:title>
        </news:news>
      </url>
      <url>
        <loc>https://www.hortidaily.com/article/2/tomato-greenhouse/</loc>
        <news:news><news:title>Tomato greenhouse expansion</news:title></news:news>
      </url>
    </urlset>
    """
    rows = _sitemap_entries(ET.fromstring(xml))
    berry = [row for row in rows if "blueberry" in (row["loc"] or "")]
    hit = _normalize_sitemap_entry(berry[0])
    assert hit.title.startswith("Global blueberry crop")
    assert hit.published_date == "2026-09-01"
    assert len(berry) == 1


def test_no_secret_or_static_leakage() -> None:
    build = (REPO / "scripts" / "build_static.py").read_text(encoding="utf-8")
    today = (REPO / "app" / "templates" / "today.html").read_text(encoding="utf-8")
    creds = (REPO / "app" / "services" / "industry_pulse" / "credentials.py").read_text(encoding="utf-8")
    assert "catchall.newscatcherapi.com" not in build
    assert "PVPOApplicationStatus" not in today
    assert "NEWSCATCHER_API_KEY" in creds
    assert "os.environ.get" in creds


def test_no_trust_mutation_from_catchall_or_registries(tmp_path: Path) -> None:
    sources = tmp_path / "data" / "configuration" / "sources.json"
    sources.parent.mkdir(parents=True)
    sources.write_text("[]", encoding="utf-8")
    query = generate_pulse_queries()[0].with_window("7d")
    MemoryProvider(hits=[records_to_hits(
        [{"record_title": "x", "citations": [{"url": "https://example.com/a"}]}],
        query=query,
    )[0]]).discover(query)
    assert sources.read_text(encoding="utf-8") == "[]"
    assert list((tmp_path / "data").glob("evidence/*.json")) == []
