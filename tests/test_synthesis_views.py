"""V2 Phase 1.5B (docs/v2/10-BACKLOG.md BL-026/BL-027/BL-028): the Landscape,
Company, and Variety synthesis prototypes. Covers both the pure aggregation
functions (fast, no HTTP) and the rendered routes (proves the templates
actually wire the data through), per this task's explicit testing list:
Landscape route, Company/Variety synthesis rendering, correct
intelligence-object linkage, Fact vs Claim distinction, relationship
labels, missing/partial-data handling, vendor-neutral rendering."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import main
from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Pure aggregation functions
# ---------------------------------------------------------------------------

def test_landscape_context_excludes_seed_fixture_records() -> None:
    context = main.landscape_context("berry-blueberry")
    variety_ids = {row["entity"]["id"] for row in context["variety_rollup"]}
    company_ids = {row["entity"]["id"] for row in context["competitive_field"]}
    assert "variety-example-blue" not in variety_ids
    assert "company-example-genetics" not in company_ids
    assert "company-example-nursery" not in company_ids


def test_landscape_context_synthesizes_real_intelligence_objects() -> None:
    context = main.landscape_context("berry-blueberry")
    signal_ids = {s["id"] for s in context["signals"]}
    assert signal_ids == {
        "sig-breeder-and-patent-attribution-drift-in-public-sources",
        "sig-breeding-programmes-becoming-consumer-platforms",
        "sig-financial-owners-taking-positions-in-berry-genetics",
        "sig-owner-published-quality-figures-exceed-independent-measurement",
        "sig-registry-participation-is-highly-uneven-between-breeders",
        "sig-southern-africa-as-licensing-and-enforcement-arena",
    }
    assessment_ids = {a["id"] for a in context["assessments"]}
    assert "assessment-financial-capital-entering-berry-genetics-ownership" in assessment_ids
    recommendation_ids = {r["id"] for r in context["recommendations"]}
    assert "recommendation-treat-costa-driscolls-as-structurally-linked" in recommendation_ids


def test_landscape_competitive_field_has_no_composite_ranking_field() -> None:
    # Explicit instruction: coverage counts only, never a blended
    # "competitive strength" or ranking score.
    context = main.landscape_context("berry-blueberry")
    for row in context["competitive_field"]:
        assert "strength" not in row
        assert "score" not in row
        assert "rank" not in row
    # Rows are sorted alphabetically, not by any count.
    names = [row["entity"]["name"] for row in context["competitive_field"]]
    assert names == sorted(names)


def test_landscape_evidence_coverage_reports_real_gaps() -> None:
    context = main.landscape_context("berry-blueberry")
    coverage = context["evidence_coverage"]
    assert coverage["disputed_fact_count"] > 0
    assert coverage["unresolved_strategic_question_count"] == 9
    assert coverage["evidence_count"] > 0


def test_landscape_asia_filter_uses_real_china_geography() -> None:
    context = main.landscape_context("berry-blueberry")
    asia = context["regional_summaries"]["asia"]
    assert asia["geography_names"] == ["China"]
    assert asia["evidence_count"] > 0
    assert context["region_metrics"]["asia"]["geographies"] == 1


def test_competitive_theme_matrix_is_relationship_and_trait_derived() -> None:
    matrix = main.landscape_context("berry-blueberry")["competitive_theme_matrix"]
    assert matrix["themes"] == [
        "Flavor / Sweetness",
        "Firmness / Shelf Life",
        "Yield / Production",
        "Climate adaptability",
        "Fruit size",
    ]
    assert len(matrix["rows"]) == 7
    fall_creek = next(
        row for row in matrix["rows"] if row["company"]["name"] == "Fall Creek Farm & Nursery, Inc."
    )
    firmness = next(cell for cell in fall_creek["cells"] if cell["theme"] == "Firmness / Shelf Life")
    assert {association["variety"]["name"] for association in firmness["associations"]} >= {
        "Blue Ribbon",
        "SEKOYA Beauty",
    }
    assert all(association["evidence_count"] > 0 for association in firmness["associations"])


def test_variety_trait_profile_distinguishes_claim_from_measurement() -> None:
    entities = main.entity_index()
    blue_manila = entities["variety-blue-manila"]
    rows = main.variety_trait_profile(blue_manila, entities)
    assert rows, "expected structured trait data for variety-blue-manila"
    # Every Blue Manila trait entry is either an owner/marketer claim or
    # explicitly unresolved (the owner publishes two conflicting soluble-solids
    # figures on its own pages) -- none is an independently-sourced measurement.
    assert all(r["is_claim"] or r["is_unresolved"] for r in rows)
    assert any(r["is_claim"] for r in rows)
    assert any(r["is_unresolved"] for r in rows)

    blue_ribbon = entities["variety-blue-ribbon"]
    ribbon_rows = main.variety_trait_profile(blue_ribbon, entities)
    provenances = {r["provenance"] for r in ribbon_rows}
    assert "named_trial_measurement" in provenances
    assert "owner_or_marketer_claim" in provenances
    measured = [r for r in ribbon_rows if r["provenance"] == "named_trial_measurement"]
    assert all(not r["is_claim"] for r in measured)


def test_variety_with_no_trait_data_returns_empty_list() -> None:
    entities = main.entity_index()
    arana = entities["variety-arana"]
    assert main.variety_trait_profile(arana, entities) == []


def test_variety_patent_link_matches_normalized_patent_number() -> None:
    entities = main.entity_index()
    patents = [e for e in entities.values() if e.get("entity_type") == "patent"]
    blue_manila = entities["variety-blue-manila"]
    match = main.variety_patent_link(blue_manila, patents)
    assert match is not None
    assert match["id"] == "patent-uspp031345p2"


def test_variety_patent_link_returns_none_without_fabricating() -> None:
    entities = main.entity_index()
    patents = [e for e in entities.values() if e.get("entity_type") == "patent"]
    arana = entities["variety-arana"]
    assert main.variety_patent_link(arana, patents) is None


def test_grouped_relationships_renders_honest_direction_and_predicate() -> None:
    entities = main.entity_index()
    relationships = main.all_relationships()
    rows = main.grouped_relationships_for_entity("company-costa-group-holdings", relationships, entities)
    assert rows, "expected Costa to have recorded relationships"
    # A licensing edge must stay 'licenses', never be upgraded to 'owns'.
    predicates = {r["predicate"] for r in rows}
    assert predicates <= {
        "owns", "develops", "licenses", "distributes", "grows",
        "trials", "sells", "carries", "partners_with", "operates_in",
    }
    for row in rows:
        assert row["direction"] in {"incoming", "outgoing"}
        assert row["other"]["id"] != "company-costa-group-holdings"


def test_signals_assessments_recommendations_for_entity_are_correctly_linked() -> None:
    costa_signals = main.signals_for_entity("company-costa-group-holdings")
    assert any(s["id"] == "sig-financial-owners-taking-positions-in-berry-genetics" for s in costa_signals)

    costa_assessments = main.assessments_for_entity("company-costa-group-holdings")
    assert any(
        a["id"] == "assessment-financial-capital-entering-berry-genetics-ownership" for a in costa_assessments
    )

    costa_recommendations = main.recommendations_for_entity("company-costa-group-holdings")
    assert any(
        r["id"] == "recommendation-treat-costa-driscolls-as-structurally-linked" for r in costa_recommendations
    )

    # An unrelated entity must not pick these up.
    unrelated_signals = main.signals_for_entity("berry-blueberry")
    assert "sig-financial-owners-taking-positions-in-berry-genetics" not in {s["id"] for s in unrelated_signals}


# ---------------------------------------------------------------------------
# Rendered routes
# ---------------------------------------------------------------------------

def test_landscape_route_renders_all_required_sections() -> None:
    response = client.get("/landscapes/berries/blueberry")
    assert response.status_code == 200
    for heading in [
        "What deserves attention",
        "Recent meaningful movement",
        "Competitive field",
        "Variety landscape",
        "Geographic footprint",
        "Evidence coverage",
    ]:
        assert heading in response.text
    assert "Berries / Blueberry / Global" in response.text


def test_landscape_route_renders_region_and_intelligence_state_filters() -> None:
    response = client.get("/landscapes/berries/blueberry?region=emea&intelligence_state=all")
    assert response.status_code == 200
    assert "Berries / Blueberry / EMEA" in response.text
    for label in ["Global", "Americas", "EMEA", "Australia / New Zealand", "Asia"]:
        assert label in response.text
    for label in ["All Intelligence", "Observed in Store", "Tested Internally"]:
        assert label in response.text
    assert "Regional intelligence" in response.text
    assert "Public Intelligence" in response.text
    assert 'class="filter-chip region-filter' in response.text
    assert "history.replaceState" in response.text
    assert "data-regions=" in response.text


def test_landscape_internal_filters_are_honest_empty_states() -> None:
    observed = client.get(
        "/landscapes/berries/blueberry?region=americas&intelligence_state=observed"
    )
    assert "No internal observation records are connected in this public prototype." in observed.text
    assert "Berries / Blueberry / Americas" in observed.text
    assert 'id="public-landscape"' in observed.text
    assert "publicView.hidden = false" in observed.text
    assert "What competitive products are we actually encountering in-market?" in observed.text

    tested = client.get(
        "/landscapes/berries/blueberry?region=asia&intelligence_state=tested"
    )
    assert "No internal test records are connected in this environment." in tested.text
    assert "Berries / Blueberry / Asia" in tested.text
    assert 'data-empty-lens="tested"' in tested.text
    assert "What has actually been evaluated against our own standards?" in tested.text


def test_landscape_public_preview_has_enrichment_placeholders() -> None:
    text = client.get("/landscapes/berries/blueberry").text
    assert "Internal Intelligence Enrichment" in text
    for label in [
        "Trial performance",
        "Deployment / commercial status",
        "Consumer / sensory",
        "Grower / field",
        "Commercial performance",
        "Competitive observations",
    ]:
        assert label in text
    assert "portable JSON" in text


def test_landscape_renders_static_region_aware_competitive_theme_matrix() -> None:
    text = client.get("/landscapes/berries/blueberry").text
    assert "Competitor × Competitive Theme Matrix" in text
    assert "Blank cells indicate no association in current coverage" in text
    assert 'class="matrix-association" data-regions=' in text
    assert "visibleAssociations" in text
    assert "No defensible competitor-to-theme associations" in text


def test_landscape_intelligence_brief_is_prioritized_and_traceable() -> None:
    context = main.landscape_context("berry-blueberry")
    assert len(context["executive_assessments"]) == 5
    assert len(context["actors_to_watch"]) <= 8
    assert all("competitor" in row["entity"]["roles"] for row in context["actors_to_watch"])
    actor_names = {row["entity"]["name"] for row in context["actors_to_watch"]}
    assert "University of Florida" not in actor_names
    assert "Florida Foundation Seed Producers, Inc." not in actor_names
    assert len(context["priority_signals"]) == 5
    assert set(context["intelligence_agenda"]) == {"now", "watch", "deeper"}


def test_regional_attention_uses_region_attributed_cited_evidence() -> None:
    context = main.landscape_context("berry-blueberry")
    attention_ids = {}
    for key, brief in context["regional_briefings"].items():
        attention_ids[key] = [item["id"] for item in brief["attention"]]
        assert all(item["regional_supporting_evidence_count"] > 0 for item in brief["attention"])
        assert brief["attention_coverage_developing"] == (len(brief["attention"]) < 3)
    assert attention_ids["americas"] != attention_ids["emea"]
    assert attention_ids["emea"] != attention_ids["asia"]


def test_recent_developments_use_publication_dates_and_region_support() -> None:
    context = main.landscape_context("berry-blueberry")
    assert len(context["recent_developments"]["global"]) == 5
    for key, items in context["recent_developments"].items():
        assert 0 <= len(items) <= 5
        assert all(item.get("published_date") for item in items)
        assert all(item.get("source_url") for item in items)
        if key != "global":
            expected_regions = {
                "americas": "Americas", "emea": "Europe",
                "australia-nz": "Oceania", "asia": "Asia",
            }
            if key != "emea":
                assert all(expected_regions[key] in item["regions"] for item in items)
            else:
                assert all(set(item["regions"]) & {"Europe", "Middle East & Africa"} for item in items)


def test_what_changed_dates_disclose_date_semantics() -> None:
    context = main.landscape_context("berry-blueberry")
    assert context["curated_movement"]
    for item in context["curated_movement"]:
        assert item["date_label"] in {"Event date", "Published", "Captured"}
        assert item["display_date"]
        if item["date_label"] == "Captured":
            assert not item.get("event_date") and not item.get("published_date")


def test_landscape_manager_disclosures_and_region_news_render() -> None:
    text = client.get("/landscapes/berries/blueberry").text
    assert "not market share or a competitor ranking" in text
    assert "regional evidence record" in text
    assert 'data-region-news="global"' in text
    assert 'data-region-news="asia"' in text
    assert "Captured” means ingestion, not event date" in text
    assert "el.dataset.regionNews !== region" in text
    global_panel = text.split('data-region-news="global"', 1)[1].split('</div>', 1)[0]
    assert global_panel.count("<tr>") == 6  # one header plus five articles
    assert "tbody tr:nth-child(n+6)" in text


def test_landscape_manager_brief_uses_compact_comparison_tables() -> None:
    text = client.get("/landscapes/berries/blueberry").text
    assert 'class="brief-list executive-brief-list"' in text
    assert text.count('class="brief-table') >= 6
    for heading in ["Manager readout", "Confirm / weaken", "Intelligence link"]:
        assert heading in text
    assert 'class="actor-watch-grid balanced-card-grid"' in text
    assert 'class="metric-bullets"' in text


def test_landscape_renders_sticky_quick_navigation_and_explore_layer() -> None:
    text = client.get("/landscapes/berries/blueberry").text
    for heading in [
        "Executive Readout",
        "What We Think",
        "Competitive Actors to Watch",
        "Where Competition Is Concentrating",
        "Regional Briefing",
        "What Changed",
        "What We're Watching",
        "Intelligence Agenda",
        "Explore the Landscape",
    ]:
        assert heading in text
    assert 'class="landscape-quick-nav"' in text
    assert 'data-scroll-target="executive-readout"' in text
    assert 'id="explore-details"' in text
    assert "scrollIntoView" in text
    assert "IntersectionObserver" in text


def test_landscape_route_synthesizes_not_just_lists_one_record_type() -> None:
    # The concrete test of "synthesis, not just listing" (07-IMPLEMENTATION-ROADMAP.md
    # Phase 1.5 acceptance criteria): one page must surface Signal, Assessment,
    # Recommendation, Strategic Question, and Entity content together.
    response = client.get("/landscapes/berries/blueberry")
    text = response.text
    assert "Institutional and private-equity capital is taking or rotating ownership" in text
    assert "Institutional and financial capital has taken large" in text
    assert "Treat Costa Group Holdings and Driscoll" in text
    assert "Costa Group Holdings Pty Ltd" in text
    assert "Blue Manila" in text


def test_landscape_route_excludes_fictional_seed_data() -> None:
    response = client.get("/landscapes/berries/blueberry")
    assert "Example Blue" not in response.text
    assert "Example Genetics" not in response.text
    assert "Example Nursery" not in response.text


def test_company_page_shows_intelligence_summary_and_portfolio() -> None:
    response = client.get("/entities/company/company-costa-group-holdings")
    assert response.status_code == 200
    assert "Bottom line" in response.text
    assert "Portfolio &amp; network" in response.text or "Portfolio & network" in response.text
    assert "Treat Costa Group Holdings and Driscoll" in response.text


def test_company_page_relationship_direction_reads_naturally() -> None:
    response = client.get("/entities/company/company-costa-group-holdings")
    # British Columbia Investment Management Corporation owns Costa (incoming edge) --
    # must render as "X owns Costa", not silently flipped or upgraded to a stronger claim.
    assert "British Columbia Investment Management Corporation" in response.text
    assert "owns" in response.text
    assert "<strong>Costa Group Holdings Pty Ltd</strong>" in response.text


def test_variety_page_shows_trait_profile_and_claim_badges() -> None:
    response = client.get("/entities/variety/variety-blue-manila")
    assert response.status_code == 200
    assert "Trait profile" in response.text
    assert "OWNER/MARKETER CLAIM" in response.text
    assert "Owner-published fruit-quality figures sit consistently above" in response.text  # the linked Signal


def test_variety_page_handles_missing_trait_and_patent_data_honestly() -> None:
    response = client.get("/entities/variety/variety-arana")
    assert response.status_code == 200
    assert "No structured trait data recorded" in response.text
    assert "no patent number recorded" in response.text


def test_variety_page_breeding_program_and_patent_links_resolve() -> None:
    response = client.get("/entities/variety/variety-blue-manila")
    assert '/entities/breeding_program/breeding_program-planasa-blueberry' in response.text
    assert '/entities/patent/patent-uspp031345p2' in response.text


def test_fact_and_claim_badges_are_visually_distinct_on_entity_page() -> None:
    response = client.get("/entities/company/company-costa-group-holdings")
    assert 'badge-fact' in response.text
    assert 'badge-claim' in response.text
    assert 'badge-counterevidence">DISPUTED' in response.text  # the disputed founding-date claim


def test_synthesis_pages_are_vendor_neutral() -> None:
    # ADR-0004 / this task's explicit instruction: no organization is
    # privileged in the UI. No synthesis page may refer to any market
    # participant as "our"/"home"/"us" in a possessive sense.
    for url in [
        "/landscapes/berries/blueberry",
        "/entities/company/company-costa-group-holdings",
        "/entities/variety/variety-blue-manila",
    ]:
        text = client.get(url).text.lower()
        assert "our company" not in text
        assert "home company" not in text
        assert "our competitor" not in text
