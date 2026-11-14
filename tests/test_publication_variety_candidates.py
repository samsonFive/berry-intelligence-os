"""Publication name suggestions stay review aids until deliberately selected."""
from __future__ import annotations

from copy import deepcopy
import re

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services.publication_review_workspace import (
    _named_variety_candidates,
    apply_dossier_prefill,
    build_publication_review_dossier,
)


def draft(**changes):
    return {
        "id": "ev-synthetic-name-review", "record_type": "evidence", "status": "draft",
        "review_state": "draft", "intake_type": "article_or_url", "evidence_role": "publication_artifact",
        "source_type": "company_press_release", "source_name": "Orchard Labs newsroom",
        "source_url": "https://example.org/cultivar", "published_date": "2026-03-26", "captured_date": "2026-11-09",
        "title": "Orchard Labs introduces GZ-42", "summary": "GZ-42 is the first commercial strawberry from this programme.",
        "submitted_by": "synthetic fixture", "berry_ids": ["berry-strawberry"],
        "suggested_varieties": [], "suggested_competitors": [], "attachments": [], **changes,
    }


def dossier(record, entities=()):
    return build_publication_review_dossier(record, entities=list(entities), berry_labels=main.BERRIES)


def variety_value(html):
    return re.search(r'id="varieties"[^>]*value="([^"]*)"', html).group(1)


@pytest.fixture
def web(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "false")
    monkeypatch.delenv("BIOS_BASIC_AUTH", raising=False)
    main._JSON_FOLDER_CACHE.clear()
    repositories = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    main.save_draft(draft())
    return TestClient(main.app), repositories


@pytest.mark.parametrize("text", [
    "It is the first commercial strawberry available.",
    "The First Commercial Strawberry is described in the announcement.",
    "The new strawberry programme begins this season.",
])
def test_descriptive_words_are_not_variety_names(text):
    assert _named_variety_candidates(text, set()) == []


@pytest.mark.parametrize("text,expected", [
    ("GZ-42 strawberry is the first commercial strawberry release.", ["GZ-42"]),
    ("The strawberry selection GZ-17.5417-060 enters a trial.", ["GZ-17.5417-060"]),
    ("The strawberry selection ORC029 enters a trial.", ["ORC029"]),
    ("A strawberry variety called Scarlet Joy was announced.", ["Scarlet Joy"]),
    ("La variedad 'Fresa Roja' comienza las pruebas.", ["Fresa Roja"]),
    ("品種「紅ほっぺ」の試験。", ["紅ほっぺ"]),
    ("The strawberry cultivar named '雪の香' enters trials.", ["雪の香"]),
])
def test_codes_and_explicit_unicode_names_remain_qualified_candidates(text, expected):
    assert _named_variety_candidates(text, set()) == expected
    assert _named_variety_candidates(text, {value.casefold() for value in expected}) == []


def test_unrelated_code_and_generic_number_are_not_naming_evidence():
    assert _named_variety_candidates("GZ-42 is a warehouse identifier. " + "Other operations. " * 15 + "Strawberry sales continue.", set()) == []
    assert _named_variety_candidates("The strawberry item weighs 42 grams.", set()) == []
    assert _named_variety_candidates("An F1 hybrid strawberry is described.", set()) == []


def test_thin_summary_name_has_span_and_basis_but_no_entity_prefill():
    value = draft()
    before = deepcopy(value)
    review = dossier(value)
    assert value == before
    assert review["source_completeness"]["class"] == "THIN_DESCRIPTION"
    assert review["proposed_variety_candidates"] == ["GZ-42"]
    assert review["prefill"]["varieties"] == ""
    assert review["prefill"]["field_classes"]["varieties"] == "B"
    candidate = review["variety_candidate_details"][0]
    assert candidate["name"] == "GZ-42"
    assert candidate["source_span"] == value["summary"]
    assert "Summary only" in candidate["basis"]
    assert "the first commercial" not in review["proposed_variety_candidates"]
    assert apply_dossier_prefill({"varieties": ""}, review)["varieties"] == ""


def test_captured_text_basis_is_distinct_from_title_and_summary():
    text = "The strawberry cultivar named '雪の香' enters replicated trials. " + "The source describes the trial location and methods. " * 15
    value = draft(title="Nursery trial update", summary="An analyst's brief summary.",
        article={"paragraphs": [{"index": 0, "text": text}], "word_count": 160})
    review = dossier(value)
    candidate = next(row for row in review["variety_candidate_details"] if row["name"] == "雪の香")
    assert candidate["basis"] == "Captured source body"
    assert "雪の香" in candidate["source_span"]
    assert review["prefill"]["varieties"] == ""


def test_directory_identity_status_and_existing_links_remain_distinct():
    entity = {"id": "variety-orchard-ruby", "entity_type": "variety", "name": "Orchard Ruby", "status": "active"}
    value = draft(title="Orchard Ruby strawberry update", summary="A source update.")
    assert dossier(value, [entity])["prefill"]["varieties"] == "Orchard Ruby"
    unverified = {**entity, "status": "unverified"}
    review = dossier(value, [unverified])
    assert review["prefill"]["varieties"] == ""
    assert "Unverified directory" in review["variety_candidate_details"][0]["basis"]
    assert dossier({**value, "entity_ids": [entity["id"]]}, [unverified])["prefill"]["varieties"] == "Orchard Ruby"


def test_get_shows_candidates_without_prefilling_or_writing(web):
    client, repositories = web
    path = main.INBOX_DIR / "evidence" / "ev-synthetic-name-review.json"
    before = path.read_bytes()
    entities = repositories.entities.list()
    page = client.get("/review/ev-synthetic-name-review")
    assert page.status_code == 200
    assert variety_value(page.text) == ""
    assert "Unverified name candidates" in page.text
    assert "Summary only" in page.text and 'data-variety-candidate="GZ-42"' in page.text
    assert path.read_bytes() == before and repositories.entities.list() == entities
    # Native form submission includes current edits even without JavaScript.
    assert 'formaction="/review/ev-synthetic-name-review/save" formnovalidate' in page.text
    assert 'id="save_summary"' not in page.text


@pytest.mark.parametrize("saved", ["", "Corrected Selection", "GZ-42"])
def test_save_reopen_preserves_explicit_variety_values_including_clear(web, saved):
    client, repositories = web
    value = main.get_draft("ev-synthetic-name-review")
    value["suggested_varieties"] = ["Original Intake Suggestion"]
    main.save_draft(value)
    page = client.get("/review/ev-synthetic-name-review")
    assert variety_value(page.text) == "Original Intake Suggestion"
    result = client.post("/review/ev-synthetic-name-review/save", data={"title": value["title"], "summary": value["summary"], "varieties": saved}, follow_redirects=False)
    assert result.status_code == 303
    stored = main.get_draft(value["id"])
    assert stored["publication_review_values"]["varieties"] == saved
    assert stored["suggested_varieties"] == ["Original Intake Suggestion"]
    assert variety_value(client.get(f"/review/{value['id']}").text) == saved
    assert repositories.entities.list() == [] and repositories.evidence.list() == []


def test_cleared_existing_directory_match_does_not_repopulate(web):
    client, repositories = web
    entity = {"id": "variety-orchard-ruby", "record_type": "entity", "entity_type": "variety", "name": "Orchard Ruby", "status": "active", "aliases": []}
    repositories.entities.create(entity)
    value = draft(title="Orchard Ruby strawberry update", entity_ids=[entity["id"]])
    main.save_draft(value)
    assert variety_value(client.get(f"/review/{value['id']}").text) == "Orchard Ruby"
    client.post(f"/review/{value['id']}/save", data={"title": value["title"], "summary": value["summary"], "varieties": ""})
    assert variety_value(client.get(f"/review/{value['id']}").text) == ""


def test_legacy_publication_save_also_preserves_a_cleared_suggestion(web):
    client, _ = web
    value = draft(suggested_varieties=["Original Intake Suggestion"])
    value.pop("evidence_role")
    main.save_draft(value)
    response = client.post(f"/review/{value['id']}/save", data={"title": value["title"], "summary": value["summary"], "varieties": ""})
    assert response.status_code == 200
    assert variety_value(client.get(f"/review/{value['id']}").text) == ""


def test_publish_validation_error_preserves_explicit_empty_variety_field(web):
    client, repositories = web
    repositories.entities.create({"id": "variety-orchard-ruby", "record_type": "entity", "entity_type": "variety", "name": "Orchard Ruby", "status": "active"})
    main.save_draft(draft(title="Orchard Ruby strawberry update"))
    response = client.post("/review/ev-synthetic-name-review/publish", data={"title": "Orchard Ruby strawberry update", "summary": "Reviewed draft", "varieties": ""})
    assert response.status_code == 400 and "Reviewer is required" in response.text
    assert variety_value(response.text) == ""


@pytest.mark.parametrize("manual_names", ["", "GZ-42"])
def test_publish_only_links_explicitly_submitted_names(web, manual_names):
    client, repositories = web
    value = main.get_draft("ev-synthetic-name-review")
    response = client.post(f"/review/{value['id']}/publish", data={
        "title": value["title"], "summary": value["summary"], "source_type": value["source_type"],
        "source_name": value["source_name"], "source_url": value["source_url"],
        "published_date": value["published_date"], "captured_date": value["captured_date"],
        "reviewer": "fixture analyst", "varieties": manual_names, "berries": "berry-strawberry",
    }, follow_redirects=False)
    assert response.status_code == 303
    assert repositories.evidence.get(value["id"]) is not None
    varieties = [row for row in repositories.entities.list() if row["entity_type"] == "variety"]
    assert [row["name"] for row in varieties] == (["GZ-42"] if manual_names else [])
    assert all(row["status"] == "unverified" for row in varieties)
    assert repositories.facts.list() == []
