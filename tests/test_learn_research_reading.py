from fastapi.testclient import TestClient
import pytest

from app import main, learn_routes
from app.services import learn_research as service, learner


def test_emphasis_is_readable_without_weakening_source_or_html_safety():
    citations = [{"url": "https://university.example/guide", "title": "Guide", "reference_ids": ["web:9"]}]
    rendered = str(service.reading_inline(
        "**Answer** *laterals* [*Visual guide*](https://university.example/guide) "
        "[*Unknown video*](https://video.example/unverified) [web:9] *<script>unsafe</script>*", citations))
    assert "<strong>Answer</strong>" in rendered and "<em>laterals</em>" in rendered
    assert '<em>Visual guide</em></a>' in rendered
    assert '<em>Unknown video</em> (link not verified)' in rendered
    assert 'href="https://video.example/unverified"' not in rendered
    assert 'aria-label="Source: Guide"' in rendered
    assert '<script>' not in rendered and '&lt;script&gt;unsafe&lt;/script&gt;' in rendered


def test_numbered_steps_keep_their_values_and_do_not_swallow_unordered_lists():
    text = "3. First retained step\n5. *Later* step\n- Separate note\n- Another note\n1. Start again"
    blocks = service.reading_blocks(text)
    assert [row["kind"] for row in blocks] == ["ordered_list", "list", "ordered_list"]
    assert blocks[0]["numbers"] == [3, 5] and blocks[2]["numbers"] == [1]
    assert blocks[1]["items"] == ["Separate note", "Another note"]
    assert blocks[0]["items"][1] == "<em>Later</em> step"


def test_only_an_identical_opening_title_is_omitted_from_the_reading_view():
    text = "# **Cane biology**\n\nThe answer.\n\n## Cane biology\n\nMore detail."
    raw = service.reading_blocks(text)
    view = service.lesson_reading_blocks(text, title=" Cane  biology ")
    assert raw[0]["kind"] == "heading" and view[0]["kind"] == "paragraph"
    assert [row["text"] for row in view if row["kind"] == "heading"] == ["Cane biology"]
    assert service.lesson_reading_blocks(text, title="A different title") == raw


def _saved_lesson(tmp_path, monkeypatch, *, title, concept_id=""):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    def forbidden(*args, **kwargs):
        raise AssertionError("Opening a saved lesson must never start or check provider research")
    monkeypatch.setattr(learn_routes, "client_factory", forbidden)
    request = service.clean_request({"topic": title, "concept_id": concept_id, "return_to": "/learn"},
        berries=main.BERRIES, entities={}, concepts=learner.all_concepts())
    job, _ = service.reserve(tmp_path, request, "reading-view-token-0001")
    text = "# " + title + "\n\n**The answer.** Primocane is mentioned in this body.\n\n3. First step\n5. *Laterals* remain distinct."
    result = {"provider_id": "resp_reading_fixture", "provider_status": "completed", "text": text,
              "citations": [], "model": "fixture-only", "usage": {}}
    row = service.apply_result(tmp_path, job["id"], result)
    before = service.path(tmp_path).read_bytes()
    response = TestClient(main.app).get("/learn/lessons/" + row["lesson_id"])
    assert response.status_code == 200
    assert service.path(tmp_path).read_bytes() == before
    saved = service.load(tmp_path)["lessons"][row["lesson_id"]]
    assert saved["text"] == saved["original_text"] == text
    assert saved["education_status"] == "ai_draft" and saved["history"] == [] and not saved["reviewed_at"]
    assert saved["request"] == request
    return response


def test_public_topic_without_selected_concept_gets_existing_interactive_cane_visual(tmp_path, monkeypatch):
    title = "How primocane and floricane fruiting differ in raspberries"
    response = _saved_lesson(tmp_path, monkeypatch, title=title)
    assert 'data-cane-calendar' in response.text and 'data-cane-habit="primocane"' in response.text
    assert 'This teaching aid is separate from the research draft.' in response.text
    assert '/learn/primocane-floricane#sources' in response.text
    assert f'<h2>{title}</h2>' not in response.text
    assert '<li value="3">First step</li>' in response.text
    assert '<li value="5"><em>Laterals</em> remain distinct.</li>' in response.text


@pytest.mark.parametrize("title", ["An unrelated research topic", "Primocane and chill hours"])
def test_unknown_or_ambiguous_titles_do_not_guess_a_visual_from_the_body(tmp_path, monkeypatch, title):
    response = _saved_lesson(tmp_path, monkeypatch, title=title)
    assert 'data-cane-calendar' not in response.text and 'data-teaching-explorer' not in response.text


def test_an_explicit_selection_takes_priority_over_ambiguous_title_matches(tmp_path, monkeypatch):
    response = _saved_lesson(tmp_path, monkeypatch, title="Primocane and chill hours", concept_id="concept-primocane-floricane")
    assert 'data-cane-calendar' in response.text


def test_another_unique_known_topic_reuses_its_existing_teaching_diagram(tmp_path, monkeypatch):
    title = next(row["name"] for row in learner.all_concepts() if row["slug"] == "soil-ph")
    response = _saved_lesson(tmp_path, monkeypatch, title=title)
    assert 'data-teaching-explorer' in response.text and 'data-cane-calendar' not in response.text
