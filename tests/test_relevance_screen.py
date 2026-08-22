"""Tests for app/services/relevance_screen.py's two-stage design.

Regression cases below are the real headlines/descriptions from this
project's own article pilot (Fresh Plaza feed) that were the actual false
positives motivating this redesign -- not synthetic examples.
"""

from __future__ import annotations

import re

from app.services.relevance_screen import (
    DEFAULT_THRESHOLD,
    geography_corroboration_matchers,
    screen_relevance,
)


def test_direct_berry_mention_in_title_is_confidently_relevant_at_stage_a():
    result = screen_relevance(title="Blueberry harvest begins", description="")
    assert result.relevant is True
    assert result.confidence == "confident"
    assert result.needs_body_check is False
    assert "berry_identity" in result.likely_topics


def test_zero_signal_is_confidently_irrelevant_at_stage_a_no_body_needed():
    result = screen_relevance(title="City council approves new bridge budget", description="Local infrastructure news.")
    assert result.relevant is False
    assert result.confidence == "confident"
    assert result.needs_body_check is False


def test_word_boundary_matching_avoids_false_positive_substring():
    result = screen_relevance(title="Berrywood Estates opens new offices", description="A real estate announcement.")
    assert "berry_identity" not in result.likely_topics


# --- Real pilot regression cases -------------------------------------------
# These three headlines/descriptions, from Fresh Plaza's general feed,
# originally cleared the old single-stage threshold (two weak generic-ag
# categories combining to >= 4) with zero berry mention anywhere -- the
# exact bug this redesign fixes.

def test_onion_headline_is_borderline_at_stage_a_not_relevant():
    result = screen_relevance(
        title="Sri Lanka targets 50% of big onion demand from local production",
        description="Sri Lanka's Department of Agriculture is preparing to produce onions through the Yala season harvest.",
    )
    assert result.relevant is False
    assert result.needs_body_check is True  # generic ag signal present, must check body, not just assumed irrelevant


def test_onion_article_stays_irrelevant_at_stage_b_after_reading_real_body():
    body = (
        "Sri Lanka's Department of Agriculture is preparing to produce 50% of the country's annual big onion "
        "requirement through the upcoming Yala season harvest, officials said, citing strong grower demand and "
        "favorable pricing for local production this export season."
    )
    result = screen_relevance(
        title="Sri Lanka targets 50% of big onion demand from local production",
        description="Onion production update.",
        body=body,
    )
    assert result.relevant is False
    assert result.berry_identity_hit is False
    assert result.confidence == "confident"


def test_apple_crop_headline_does_not_pass_from_generic_signals_alone():
    stage_a = screen_relevance(
        title="First indicators point to smaller U.S. apple crop",
        description="The first apple varieties from the new crop are available; harvest is underway.",
    )
    assert stage_a.relevant is False
    body = (
        "The first apple varieties from the 2026/2027 crop are available. In Washington state, harvest of Gala "
        "and Honeycrisp has started. Given that Gala supply from the prior season is winding down, growers expect "
        "smaller volumes and firmer pricing this export season."
    )
    stage_b = screen_relevance(
        title="First indicators point to smaller U.S. apple crop", description="Apple crop update.", body=body,
    )
    assert stage_b.relevant is False
    assert stage_b.berry_identity_hit is False


def test_fig_season_headline_does_not_pass_from_generic_signals_alone():
    stage_a = screen_relevance(
        title="Earlier end anticipated for California fig season",
        description="Fresh figs continue to be in good supply from California; production and harvest updates.",
    )
    assert stage_a.relevant is False
    body = (
        "Fresh figs continue to be in good supply from California and have been so for the past month. "
        "Production was initially slower but jumped up significantly three weeks ago. Sizing is normal for "
        "this point in the harvest season."
    )
    stage_b = screen_relevance(
        title="Earlier end anticipated for California fig season", description="Fig season update.", body=body,
    )
    assert stage_b.relevant is False


def test_bare_berries_as_one_item_in_a_long_fruit_list_is_borderline_not_confident():
    """Real pilot regression: a multi-commodity trade-mission article whose
    description lists "...spanning table grapes, apples and pears, citrus,
    mangos, avocados, cherries, berries, summer fruit..." must not become
    confidently relevant merely because "berries" is one of eight items in
    that list, with zero berry-specific content anywhere in the article."""
    result = screen_relevance(
        title="Australian Horticulture Opens New Channels Into China's Tier-2 Cities",
        description=(
            "The delegation brought together senior leaders of eight peak industry bodies spanning table "
            "grapes, apples and pears, citrus, mangos, avocados, cherries, berries, summer fruit and dried fruits."
        ),
    )
    assert result.relevant is False
    assert result.needs_body_check is True
    assert result.berry_identity_hit is False


def test_berry_company_name_in_title_is_confidently_relevant_even_with_no_species_named():
    """Real pilot regression: 'SanLucar acquires stake in Twin River
    Berries' -- a genuine berry-industry M&A story whose real article body
    never once names a specific berry species, only the company name
    'Twin River Berries' and generic 'premium fruit' language. A pure
    species-name gate would (and initially did) incorrectly exclude this."""
    result = screen_relevance(
        title="SanLucar acquires stake in Twin River Berries, expanding North American and Asian footprint",
        description="The companies said they shared the passion for quality and year-round premium fruit availability.",
    )
    assert result.relevant is True
    assert result.confidence == "confident"
    assert "Twin River Berries" in result.reason


def test_lowercase_berries_word_is_not_mistaken_for_a_company_name():
    """The company-name heuristic requires a capitalized proper-noun
    pattern -- ordinary lowercase "berries" in a sentence must not
    trigger it (that's the separate, non-auto-triggering generic_berry_
    mention category, covered elsewhere in this file)."""
    result = screen_relevance(
        title="Local market sees strong demand for fresh berries this week",
        description="Shoppers reported good prices on berries at the farmers market.",
    )
    assert result.needs_body_check is True
    assert result.relevant is False


def test_bare_berries_in_fruit_list_stays_irrelevant_if_body_has_no_berry_specifics():
    body = (
        "The 23-member delegation spent eight days visiting Kunming, Chongqing, Changsha and Qingdao, meeting "
        "wholesale market operators and retailers. Australian horticulture exports are forecast to reach "
        "AU$4.7 billion this year, led by table grapes and citrus, with China the largest export market."
    )
    result = screen_relevance(
        title="Australian Horticulture Opens New Channels Into China's Tier-2 Cities",
        description="Trade mission covering table grapes, apples, citrus, mangos, avocados, cherries, berries.",
        body=body,
    )
    assert result.relevant is False
    assert result.berry_identity_hit is False


# --- The other side: a generic headline that genuinely IS berry content ---

def test_generic_headline_that_genuinely_discusses_berries_in_body_becomes_relevant():
    """Per the task's own requirement: an onion/apple/fig-style generic
    headline must still be able to pass Stage B if the real article
    genuinely contains berry-related intelligence."""
    stage_a = screen_relevance(
        title="Fruit exports grow amid strong seasonal demand",
        description="Export volumes rose across several categories this quarter, driven by grower production gains.",
    )
    assert stage_a.needs_body_check is True
    body = (
        "Export volumes rose across several fruit categories this quarter. Blueberry shipments led the gains, "
        "with growers reporting a 15 percent increase in acreage dedicated to new highbush varieties."
    )
    stage_b = screen_relevance(
        title="Fruit exports grow amid strong seasonal demand", description="Export update.", body=body,
    )
    assert stage_b.relevant is True
    assert stage_b.berry_identity_hit is True


def test_blueberry_variety_dispute_real_headline_is_confidently_relevant():
    """The strongest real example from the pilot -- must remain trivially
    relevant under the new gate, not regress."""
    result = screen_relevance(
        title="Blueberry Variety Dispute Between Noposion and Meiming Escalates",
        description="Litigation over blueberry proprietary variety rights and seedling quality.",
    )
    assert result.relevant is True
    assert result.confidence == "confident"


def test_custom_threshold_is_still_accepted_and_recorded():
    result = screen_relevance(title="Acreage grows", description="Production up.", threshold=100)
    assert result.threshold == 100


def test_as_dict_is_json_serializable_shape():
    result = screen_relevance(title="Blueberry variety dispute", description="")
    payload = result.as_dict()
    assert payload["relevant"] is True
    assert payload["confidence"] == "confident"
    assert "berry_identity_hit" in payload
    assert "query_corroboration" in payload


# --- French species vocabulary (Relevance Screen Boundary V1) --------------
# Real regression: a dedicated French-language Morocco source
# (source-news-search-morocco-berry-fr) had zero French berry vocabulary in
# this screen -- 45 of its 50 real discovered items scored 0 and were
# confidently rejected despite genuinely covering Moroccan blueberry/
# strawberry/raspberry trade news (AgriMaroc, Le360, Bladi.net).

def test_french_blueberry_term_is_confidently_relevant():
    result = screen_relevance(
        title="Le Maroc, nouveau leader des myrtilles sur le marché britannique",
        description="",
    )
    assert result.relevant is True
    assert result.confidence == "confident"


def test_french_strawberry_and_raspberry_terms_are_confidently_relevant():
    assert screen_relevance(title="Fraises contaminées : les résultats de l'enquête", description="").relevant is True
    assert screen_relevance(title="Framboises surgelées : record d'exportation", description="").relevant is True


def test_french_mure_deliberately_excluded_stays_generic():
    """French 'mûre'/'mûres' (blackberry) is deliberately NOT a
    berry_identity term -- it collides with the ordinary adjective 'ripe'
    ('une fraise mûre'), the same collision-risk precedent as excluding
    Italian 'more'. A bare, unrelated use must not auto-trigger relevance."""
    result = screen_relevance(title="Une récolte mûre pour l'exportation", description="")
    assert "berry_identity" not in result.likely_topics


def test_fruits_rouges_is_generic_not_auto_triggering():
    """French collective 'fruits rouges' (red berries, no named species)
    mirrors English 'berry'/'berries': contributes score but is not
    confident identity on its own."""
    result = screen_relevance(
        title="Exportations des fruits rouges : chiffres en demi-teinte", description="",
    )
    assert result.berry_identity_hit is False
    assert result.needs_body_check is True


# --- Query-provenance corroboration (Relevance Screen Boundary V1) ---------
# Real regression: 'UNIFRUTTI GROUP ACQUIRES BOMAREA AND AVOAMERICA PERU...'
# (PR Newswire, TD-040/TD-045's own cited case) scores 0 -- no berry/CI
# keyword anywhere -- and was confidently, permanently rejected before this
# fix even though the discovering source's own query was "Peru blueberry
# acquisition OR investment OR expands". Query provenance alone must never
# prove relevance (this module's own docstring, mission Section 6) -- these
# tests check the corroboration mechanism only ever *reopens* Stage B, never
# grants confident relevance by itself.

def _matcher(entity_id: str, name: str) -> tuple[str, "re.Pattern[str]"]:
    return (entity_id, re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE))


PERU = [_matcher("geography-peru", "Peru")]
COSTA = [_matcher("company-costa-group-holdings", "Costa Group")]


def test_zero_signal_title_without_matchers_is_unchanged_confident_irrelevant():
    """Omitting geo_matchers/company_matchers preserves the exact prior
    behavior -- no regression for any caller that doesn't opt in."""
    result = screen_relevance(
        title="UNIFRUTTI GROUP ACQUIRES BOMAREA AND AVOAMERICA PERU TO FURTHER STRENGTHEN ITS GLOBAL MULTI-FRUIT PLATFORM",
        description="",
    )
    assert result.confidence == "confident"
    assert result.relevant is False
    assert result.query_corroboration is None


def test_real_unifrutti_headline_is_kept_open_by_geography_plus_action_verb():
    result = screen_relevance(
        title="UNIFRUTTI GROUP ACQUIRES BOMAREA AND AVOAMERICA PERU TO FURTHER STRENGTHEN ITS GLOBAL MULTI-FRUIT PLATFORM",
        description="",
        geo_matchers=PERU, company_matchers=[],
    )
    assert result.confidence == "borderline"
    assert result.needs_body_check is True
    assert result.relevant is False  # never granted relevance directly -- Stage B still decides
    assert result.query_corroboration == "geography-peru"


def test_real_costa_group_headline_is_kept_open_by_company_plus_action_verb():
    result = screen_relevance(
        title="Driscoll's strikes deal to acquire Australia's Costa Group",
        description="",
        geo_matchers=[], company_matchers=COSTA,
    )
    assert result.needs_body_check is True
    assert result.query_corroboration == "company-costa-group-holdings"


def test_geography_alone_without_action_verb_does_not_corroborate():
    """A registered geography name alone, with no corporate-action term, is
    not enough -- must stay the ordinary zero-signal confident-irrelevant
    result rather than flooding review with every Peru-mentioning headline."""
    result = screen_relevance(
        title="Peru celebrates national holiday with parade", description="",
        geo_matchers=PERU, company_matchers=[],
    )
    assert result.confidence == "confident"
    assert result.query_corroboration is None


def test_action_verb_alone_without_geography_or_company_does_not_corroborate():
    result = screen_relevance(
        title="Local business announces major expansion plans", description="",
        geo_matchers=PERU, company_matchers=COSTA,
    )
    assert result.confidence == "confident"
    assert result.query_corroboration is None


def test_continent_level_geography_excluded_from_corroboration_matchers():
    """geography_corroboration_matchers deliberately excludes continent-
    level entities (Europe, North America) -- too broad, would corroborate
    almost any global corporate-action headline regardless of berry
    relevance. Real regression: 'Plastic Ingenuity makes first acquisition
    in Europe' (a packaging company, zero berry connection)."""
    entities = [
        {"id": "geography-europe", "entity_type": "geography", "name": "Europe"},
        {"id": "geography-peru", "entity_type": "geography", "name": "Peru"},
    ]
    matchers = geography_corroboration_matchers(entities)
    ids = {entity_id for entity_id, _ in matchers}
    assert ids == {"geography-peru"}


def test_score_greater_than_zero_borderline_is_unaffected_by_corroboration_matchers():
    """The existing generic-agriculture-signal borderline path (score > 0)
    is untouched by this change -- corroboration only ever applies to the
    true zero-signal case."""
    result = screen_relevance(
        title="Peru grower announces major expansion", description="Production update.",
        geo_matchers=PERU, company_matchers=[],
    )
    assert result.score > 0
    assert result.needs_body_check is True
    assert result.query_corroboration is None  # this path was already borderline on its own signal
