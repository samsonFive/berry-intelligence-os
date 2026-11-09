from pathlib import Path
from shutil import copyfile
from urllib.parse import urlsplit

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader, select_autoescape

from app.services.global_search import search_documents
from app.services.topic_retrieval import match_record, plan_query, record_passages
from app.services.variety_season import COMPARISON, SEASON_CROPS, berry_season, blackberry_season, season_candidate_sources, season_preview, season_source_leads


DATA = Path(__file__).resolve().parents[1] / "data"


def test_season_preview_is_cited_and_respects_explicit_search_constraints():
    rows = season_preview(DATA, plan_query("Blackberry Floricans"))
    assert [row["name"] for row in rows] == ["Ervin", "Sweet-Ark Immaculate", "Loch Katrine"]
    assert any("seregionalconference.org" in url for _, url, _ in rows[0]["sources"])
    assert not season_preview(DATA, plan_query("blackberry floricane pruning"))
    assert not season_preview(DATA, plan_query("blackberry floricane varieties Spain"))
    assert not season_preview(DATA, plan_query("blackberry floricane varieties 2026-01-01"))


def test_fruiting_habit_and_harvested_cane_are_independent():
    strict = blackberry_season(DATA, "", {"habit": "Floricane"})
    assert len(strict["rows"]) == 9
    second_year = blackberry_season(DATA, "", {"crops": "Floricane"})
    names = {row["name"] for row in second_year["rows"]}
    assert "Prime-Ark Horizon" in names
    assert "Fontana" not in names


def test_primocane_variety_passage_is_adjacent_to_strict_floricane_query():
    record = {
        "title": "Blackberry cultivars suited for the Mid-Atlantic",
        "body_text": "Prime-Ark Horizon was released in 2020. This primocane-fruiting blackberry variety can also produce a floricane crop.",
    }
    strict = match_record(record, plan_query("floricane blackberry varieties"))
    production = match_record(record, plan_query("floricane blackberry crop"))
    assert strict and strict["relevance"] == "adjacent"
    assert production and production["relevance"] == "direct"


def test_alias_and_explicit_facets_intersect():
    filters = {"region": "Southeast US", "markets": "Fresh"}
    result = blackberry_season(DATA, "NC 740", filters)
    assert [row["name"] for row in result["rows"]] == ["Ervin"]
    assert not blackberry_season(DATA, "NC 740", {**filters, "markets": "Processing"})["rows"]


def test_evidence_filter_tracks_active_reviewed_claims_and_withdrawal():
    from types import SimpleNamespace

    evidence_id = "ev-frontier-ervin-mills-river-trial"
    fact_id = "fact-frontier-ervin-mills-river-trial-1"
    baseline = blackberry_season(DATA, "", {})
    source_url = baseline["sources"]["nc_trial"][1]
    evidence = {"status": "published", "source_url": source_url, "fact_ids": [fact_id]}
    fact = {"status": "active", "evidence_ids": [evidence_id]}
    repositories = SimpleNamespace(evidence={evidence_id: evidence}, facts={fact_id: fact})
    breeder_id = "ev-frontier-immaculate-breeder-update"
    breeder_fact = "fact-frontier-immaculate-breeder-update-1"
    repositories.evidence[breeder_id] = {
        "status": "published", "source_url": baseline["sources"]["ar"][1], "fact_ids": [breeder_fact],
    }
    repositories.facts[breeder_fact] = {"status": "active", "evidence_ids": [breeder_id]}

    filters = {"evidence_status": "Has reviewed evidence"}
    reviewed = blackberry_season(DATA, "", filters, repositories=repositories)
    assert [row["name"] for row in reviewed["rows"]] == ["Ervin", "Sweet-Ark Immaculate"]
    assert reviewed["rows"][0]["reviewed"] == {"nc_trial": evidence_id}
    von = next(row for row in blackberry_season(DATA, "", {}, repositories=repositories)["rows"] if row["name"] == "Von")
    assert "ar" in von["citations"] and not von["reviewed"]

    fact["status"] = "withdrawn"
    assert not blackberry_season(DATA, "NC 740", filters, repositories=repositories)["rows"]
    remaining = blackberry_season(DATA, "NC 740", {"evidence_status": "Source-reported only"}, repositories=repositories)
    assert remaining["rows"][0]["reviewed"] == {}
    assert remaining["sources"]["nc_trial"][1] == source_url
    assert [row["name"] for row in remaining["rows"]] == ["Ervin"]


def test_every_observation_and_milestone_resolves_to_original_source():
    for crop in SEASON_CROPS:
        result = berry_season(DATA, crop, "", {})
        assert result["rows"]
        _assert_cited_rows(result, crop)


def _assert_cited_rows(result, crop):
    import json

    for row in result["rows"]:
        assert row["citations"]
        for source_id in row["citations"] + [event[-1] for event in row["events"]]:
            _, url, locator = result["sources"][source_id]
            assert urlsplit(url).scheme == "https" and locator
        if row["variety_id"]:
            variety = json.loads((DATA / "entities/varieties" / (row["variety_id"] + ".json")).read_text(encoding="utf-8"))
            assert crop in variety["berry_ids"]


def test_global_search_links_to_pilot_for_original_and_corrected_queries():
    assert search_documents([], "Blackberry Floricans")["blackberry_season"]
    assert search_documents([], "floricane", berry="berry-blackberry")["blackberry_season"]
    assert not search_documents([], "raspberry floricane")["blackberry_season"]


def test_season_discovery_leads_keep_release_and_licensing_urls_separate():
    leads = [(url, words) for key, _, url, words in season_source_leads(DATA) if key == "variety-ervin"]
    assert any("rubus.ces.ncsu.edu" in url and "Floricane" in words for url, words in leads)
    assert any("globalplantgenetics.com" in url and "International license" in words for url, words in leads)
    assert not any("globalplantgenetics.com" in url and "Introduction" in words for url, words in leads)


def test_public_discovery_can_find_season_source_without_named_cultivar():
    from app.services.public_research_search import PublicResearchSearchClient

    entity = {"id": "variety-ervin", "entity_type": "variety", "name": "Ervin", "berry_ids": ["berry-blackberry"]}
    lead = next(
        (title, url) for key, title, url, words in season_source_leads(DATA)
        if key == entity["id"] and "International license" in words
    )
    title, url = lead
    client = PublicResearchSearchClient(
        entities={entity["id"]: entity},
        primary_sources={entity["id"]: [{"title": title, "url": url}]},
        primary_terms={url: ["floricane", "license"]},
    )
    hits = client._registry("blackberry floricane licensing")
    assert [hit.url for hit in hits] == [url]
    assert "not verified" in hits[0].snippet


def test_original_source_seeds_cover_uncataloged_names_and_spanish_market():
    loch = season_candidate_sources(DATA, plan_query("Varietà di mora Loch Katrine prove produttive Scozia"))
    spain = season_candidate_sources(DATA, plan_query("Variedades de zarzamora floricane en España"))
    ervin = season_candidate_sources(DATA, plan_query("NC 740 blackberry high tunnel trial"))
    oregon = season_candidate_sources(DATA, plan_query("Pacific Northwest blackberry mechanical harvesting trial"))
    assert any("hutton.ac.uk" in url and subject == "Loch Katrine" for _, url, subject in loch)
    assert any("berryneo.com" in url for _, url, _ in spain)
    assert any("seregionalconference.org" in url for _, url, _ in ervin)
    assert any("ars.usda.gov" in url for _, url, _ in oregon)
    assert not season_candidate_sources(DATA, plan_query("blackberry floricane -\"Loch Katrine\""))
    assert not season_candidate_sources(DATA, plan_query("fresa floricane España"))


def test_spanish_commercial_catalog_terms_are_distinct_from_function_words():
    plan = plan_query("Variedades de zarzamora floricane para producción comercial en España")
    assert {"blackberry", "floricane", "production", "commercial", "españa"} <= set(plan.terms)
    assert not set(plan.terms).intersection({"de", "para", "en"})


def test_uncataloged_breeder_source_is_captured_during_provider_failure(tmp_path):
    from app.services.topic_discovery import discover_topic

    fixture = tmp_path / "data" / COMPARISON
    fixture.parent.mkdir(parents=True)
    copyfile(DATA / COMPARISON, fixture)

    class OfflineProvider:
        def search(self, query, *, max_results):
            raise TimeoutError()

    def fetch(url):
        assert "hutton.ac.uk" in url or "berryplant.com" in url
        return {
            "headline": "Loch Katrine blackberry trial",
            "passages": ["Loch Katrine is a thornless blackberry. Loch Katrine trial yields were comparable to Loch Ness."],
            "canonical_url": url,
            "availability": "full_text",
        }

    result = discover_topic(
        plan_query("Loch Katrine blackberry trial yield"), inbox_dir=tmp_path / "inbox",
        data_dir=tmp_path / "data", client=OfflineProvider(), fetcher=fetch, entities={},
    )
    assert result["status"] == "partial"
    assert any("hutton.ac.uk" in row["source_url"] for row in result["items"])
    assert all(row["trust_class"] == "LIVE / UNREVIEWED" for row in result["items"])


def test_trial_comparator_is_owned_by_an_explicit_yield_comparison():
    from app.services.topic_support import identity_in_passage

    entity = {"name": "Ouachita", "berry_ids": ["berry-blackberry"]}
    assert identity_in_passage("Total yield was similar to Von and Ouachita in year one.", entity)
    assert not identity_in_passage("Yield was measured at harvest. Conditions were similar to Ouachita.", entity)
    assert not identity_in_passage("Total yield was similar to Ouachita County.", entity)


def test_named_source_reference_requires_the_cultivar_and_place_in_owned_body():
    plan = plan_query("Varietà di mora senza spine Loch Katrine prove produttive Scozia")
    record = {
        "title": "Blackberry breeding",
        "provider": "local_primary_citation",
        "reference_subject": "Loch Katrine",
        "body_text": "Loch Katrine is a thornless variety with yields comparable to Loch Ness in Scottish trials.",
    }
    matched = match_record(record, plan)
    assert matched and matched["support_status"] == "body_supported"
    unrelated = match_record({**record, "body_text": record["body_text"].replace("Scottish", "French")}, plan)
    assert unrelated and unrelated["support_status"] == "scope_unverified"


def test_numbered_poster_excerpts_do_not_mix_two_crops_on_one_page():
    from app.services.source_passage_scope import owned_pdf_abstracts

    rows = [
        ("pdf:page:9", "[PDF page 9]\n10. Grape trial\nResearchers\nAbstract: Grapes were evaluated."),
        ("pdf:page:10", "[PDF page 10]\n11. Blackberry trial\nResearchers\nAbstract: NC 740 yielded"),
        ("pdf:page:11", "[PDF page 11]\nwell.\n12. Strawberry trial\nResearchers\nAbstract: Strawberries were evaluated."),
    ]
    results = dict(owned_pdf_abstracts(rows))
    blackberry = results["pdf:section:11:pages:10-11"]
    assert "NC 740 yielded\nwell." in blackberry
    assert "Grapes" not in blackberry and "Strawberry" not in blackberry


def test_explicit_pdf_page_citation_cannot_use_an_unrelated_page():
    record = {
        "source_url": "https://example.org/posters.pdf#page=10",
        "article": {"paragraphs": [
            {"locator": "pdf:page:10", "text": "Blackberry trial in Mills River"},
            {"locator": "pdf:page:11", "text": "Strawberry trial in Huelva"},
        ]},
    }
    assert record_passages(record) == [("pdf:page:10", "Blackberry trial in Mills River")]
    assert match_record(record, plan_query("strawberry trial Huelva")) is None


def test_processing_trial_needs_harvest_operation_and_regional_trial_context():
    from app.services.topic_support import passage_intent_supported, support_context, trial_location_in_passage

    plan = plan_query("Pacific Northwest blackberry mechanical harvest trial for processing")
    places = support_context(plan, {}, [])["trial_places"]
    correct = "The blackberry trial in Oregon used a machine harvester for processing fruit."
    wrong_operation = "The blackberry trial in Oregon used mechanical cooling for fruit processing."
    wrong_location = "The blackberry trial in North Carolina used a machine harvester for processing fruit."
    assert passage_intent_supported(correct, plan) and trial_location_in_passage(correct, places)
    assert not passage_intent_supported(wrong_operation, plan)
    assert not trial_location_in_passage(wrong_location, places)


def test_multilingual_crop_words_block_off_crop_benchmark_results():
    french = plan_query("Comparaison des variétés de framboise remontante en tunnel en France")
    spanish = plan_query("Fresa variedades tolerantes al calor ensayo Huelva")
    assert "raspberry" in french.terms and "strawberry" in spanish.terms
    assert french.cane_type == "primocane" and not plan_query("fraise remontante").cane_type
    assert {"blackberry", "thornless", "scotland", "trial"} <= set(
        plan_query("Varietà di mora senza spine Loch Katrine prove produttive Scozia").terms
    )
    assert not match_record({
        "title": "Comparaison des pratiques en France",
        "body_text": "Comparaison des variétés de pratiques en tunnel en France.",
    }, french)
    assert not match_record({
        "title": "Variedades de patata tolerantes al calor",
        "body_text": "Un ensayo sobre variedades tolerantes al calor en Huelva.",
    }, spanish)
    assert "blueberry" in plan_query("Arándano cosecha mecánica cultivares ensayo Perú").terms
    assert "blueberry" not in plan_query("Arándanos rojos frescos").terms


def test_comparison_renders_scoped_trial_and_distinct_citations():
    filters = {"habit": "Floricane", "system": "High tunnel"}
    comparison = blackberry_season(DATA, "", filters)
    environment = Environment(
        loader=ChoiceLoader([
            DictLoader({"glasshouse_base.html": "{% block content %}{% endblock %}"}),
            FileSystemLoader(DATA.parent / "app/templates"),
        ]),
        autoescape=select_autoescape(),
    )
    page = environment.get_template("variety_season.html").render(
        crop="Blackberry", berry="berry-blackberry", season_crops={"berry-blackberry": "Blackberry"}, comparison=comparison, filters={key: filters.get(key, "") for key in comparison["facets"]}, query="",
    )
    assert "Mills River, NC" in page and 'value="High tunnel" selected' in page
    assert "Plant stock for 2027 is unverified" in page
    assert "International license" in page and "Sweet-Ark Immaculate" not in page



def test_paired_strawberry_trial_is_seeded_once_without_a_single_cultivar_scope():
    plan = plan_query("Strawberry cultivar Florida Brilliance versus Florida Beauty university trial yield early harvest")
    sources = season_candidate_sources(DATA, plan)
    assert len(sources) == 1
    assert sources[0][1].startswith("https://fieldreport.caes.uga.edu/")
    assert sources[0][2] == ""



def test_comparison_retrieves_two_cultivar_rows_only_from_the_same_trial_table():
    names = ("Florida Brilliance", "Florida Beauty")
    entities = {
        name: {"id": name, "name": name, "entity_type": "variety", "berry_ids": ["berry-strawberry"]}
        for name in names
    }
    plan = plan_query("Strawberry cultivar Florida Brilliance versus Florida Beauty university trial yield early harvest")
    rows = [
        "University strawberry cultivar trial yield and early harvest",
        "Table 2. Strawberry Variety Yield and First Harvest in the Field Demonstration.",
        "Variety | First harvest date | Yield (g/plant)",
        "Florida Beauty | 02/04/2020 | 41.9",
        "Florida Brilliance | 01/28/2020 | 66.9",
    ]
    def result(passages):
        record = {"title": rows[0], "article": {"paragraphs": [{"text": p} for p in passages]}}
        return match_record(record, plan, entities=entities)

    direct = result(rows)
    assert direct["relevance"] == "direct"
    assert all(value in direct["passage"] for value in ("41.9", "66.9", "Yield (g/plant)"))
    assert result(rows[:4] + rows[1:3] + rows[4:])["relevance"] != "direct"
