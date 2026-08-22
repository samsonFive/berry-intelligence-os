"""Coverage for app/services/deterministic_tagging.py's berry-inference
helper. No dedicated test file existed for this module before Evidence
Berry Tagging Backfill V1 (2026-08-22) -- added because this function
became load-bearing for a mass backfill and a real word-boundary bug was
found and fixed here (a plain substring check false-positived "berry-
blackberry" on ordinary Spanish words like "morado"/purple and
"enamorado"/in love, which merely contain "mora").
"""

from __future__ import annotations

from app.services.deterministic_tagging import infer_berry_ids_from_text


def test_infer_berry_ids_matches_named_species_english() -> None:
    assert infer_berry_ids_from_text("Fresh blueberries arrive early") == ["berry-blueberry"]
    assert infer_berry_ids_from_text("A new raspberry variety") == ["berry-raspberry"]
    assert infer_berry_ids_from_text("Blackberry season begins") == ["berry-blackberry"]
    assert infer_berry_ids_from_text("Strawberry exports rise") == ["berry-strawberry"]


def test_infer_berry_ids_matches_named_species_spanish() -> None:
    assert infer_berry_ids_from_text("Exportación de arándanos") == ["berry-blueberry"]
    assert infer_berry_ids_from_text("Cosecha de frambuesas") == ["berry-raspberry"]
    assert infer_berry_ids_from_text("Producción de zarzamora en Michoacán") == ["berry-blackberry"]
    assert infer_berry_ids_from_text("Temporada de fresas") == ["berry-strawberry"]


def test_infer_berry_ids_does_not_false_positive_on_mora_substring() -> None:
    """Real regression: "mora" is a substring of several ordinary Spanish
    words with nothing to do with blackberries."""
    assert infer_berry_ids_from_text("El cielo está morado al atardecer") == []
    assert infer_berry_ids_from_text("Estaba profundamente enamorado") == []
    assert infer_berry_ids_from_text("Una historia memorable") == []
    assert infer_berry_ids_from_text("La moraleja de la fábula") == []


def test_infer_berry_ids_still_matches_real_generic_mora() -> None:
    assert infer_berry_ids_from_text("Compramos moras frescas hoy") == ["berry-blackberry"]


def test_infer_berry_ids_caneberry_tags_both_raspberry_and_blackberry() -> None:
    result = infer_berry_ids_from_text("Nursery adding caneberries to its lineup")
    assert set(result) == {"berry-raspberry", "berry-blackberry"}


def test_infer_berry_ids_multi_berry_article_returns_all_present() -> None:
    text = "Blueberry, strawberry, raspberry and blackberry all saw price gains"
    assert set(infer_berry_ids_from_text(text)) == {
        "berry-blueberry", "berry-strawberry", "berry-raspberry", "berry-blackberry",
    }


def test_infer_berry_ids_returns_empty_for_unrelated_text() -> None:
    assert infer_berry_ids_from_text("Avocado exports grew 12% this quarter") == []


def test_infer_berry_ids_deduplicates_repeated_terms() -> None:
    text = "Blueberry prices rise as blueberry exports grow"
    assert infer_berry_ids_from_text(text) == ["berry-blueberry"]
