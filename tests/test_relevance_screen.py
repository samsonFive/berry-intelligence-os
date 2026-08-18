"""Tests for app/services/relevance_screen.py's two-stage design.

Regression cases below are the real headlines/descriptions from this
project's own article pilot (Fresh Plaza feed) that were the actual false
positives motivating this redesign -- not synthetic examples.
"""

from __future__ import annotations

from app.services.relevance_screen import DEFAULT_THRESHOLD, screen_relevance


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
