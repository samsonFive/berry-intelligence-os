"""Tests for app/services/relevance_screen.py."""

from __future__ import annotations

from app.services.relevance_screen import DEFAULT_THRESHOLD, screen_relevance


def test_direct_berry_mention_is_always_relevant_even_with_no_other_signal():
    result = screen_relevance(title="Blueberry harvest begins", description="")
    assert result.relevant is True
    assert "berry_identity" in result.likely_topics


def test_unrelated_agricultural_content_with_no_signal_is_not_relevant():
    result = screen_relevance(title="Onion demand grows in Sri Lanka", description="Local farmers plan expansion.")
    assert result.relevant is False


def test_word_boundary_matching_avoids_false_positive_substring():
    # "berrywood" contains "berry" as a substring but is not a berry mention.
    result = screen_relevance(title="Berrywood Estates opens new offices", description="A real estate announcement.")
    assert "berry_identity" not in result.likely_topics


def test_two_weaker_categories_combined_can_clear_threshold_without_berry_identity():
    result = screen_relevance(
        title="Grower acreage expands amid strong export demand",
        description="Production and shipper volumes rose this season on higher retail pricing.",
    )
    assert result.score >= DEFAULT_THRESHOLD
    assert result.relevant is True
    assert "berry_identity" not in result.likely_topics


def test_body_text_contributes_to_the_score_when_provided():
    without_body = screen_relevance(title="Industry update", description="A general note.")
    with_body = screen_relevance(
        title="Industry update", description="A general note.", body="Blueberry growers reported strong yield this season."
    )
    assert without_body.relevant is False
    assert with_body.relevant is True


def test_custom_threshold_is_respected():
    result = screen_relevance(title="Acreage grows", description="Production up.", threshold=100)
    assert result.relevant is False
    assert result.threshold == 100


def test_as_dict_is_json_serializable_shape():
    result = screen_relevance(title="Blueberry variety dispute", description="")
    payload = result.as_dict()
    assert payload["relevant"] is True
    assert isinstance(payload["matched_terms"], list)
    assert isinstance(payload["likely_topics"], list)
