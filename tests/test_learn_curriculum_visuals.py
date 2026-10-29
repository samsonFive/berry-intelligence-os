"""Teaching coverage, scientific boundaries and preservation of human content."""
import json
from copy import deepcopy
from html import unescape
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import learner, learner_visuals
from app.services.learner_curriculum_visuals import DIAGRAMS


CONCEPTS = Path(__file__).resolve().parents[1] / "data/learn/concepts"


def test_every_existing_lesson_has_a_visual_without_rewriting_its_record():
    files = sorted(CONCEPTS.glob("concept-*.json"))
    assert len(files) == 27
    before = {p: p.read_bytes() for p in files}
    for path, raw_bytes in before.items():
        raw = json.loads(raw_bytes)
        original = deepcopy(raw)
        shown = learner_visuals.presentation(raw)
        assert raw == original
        assert all(shown[key] == value for key, value in raw.items() if key != "media")
        if raw["slug"] in DIAGRAMS:
            assert shown.get("media") == raw.get("media")
        assert shown["cane_diagram"] or shown["teaching_diagram"]
        assert learner_visuals.presentation(shown) == shown
    assert all(p.read_bytes() == value for p, value in before.items())


@pytest.mark.parametrize("slug", sorted(DIAGRAMS))
def test_expanded_visuals_work_in_shared_static_template_without_javascript(slug):
    concept = learner.concept_by_slug(slug)
    request = SimpleNamespace(url=SimpleNamespace(path="/learn/" + slug))
    html = main.templates.env.get_template("learn_workspace_concept.html").render(
        request=request, concept=concept, authoring_mode=False, static_build=True,
        return_to="/learn", related=[], related_intelligence={"rows": []},
        berry_notes={"has_any": False},
    )
    text = unescape(html)
    assert "data-teaching-explorer" in html
    assert "Sources checked October 28, 2026" in html
    assert "Research &amp; expand" not in html
    for index, step in enumerate(concept["teaching_diagram"]["steps"]):
        assert step["detail"] in text
        assert f'aria-controls="teaching-detail-{index}"' in html
        assert html.count(f'id="teaching-detail-{index}"') == 1
    assert 'type="button"' in html
    assert "<iframe" not in html
    assert "<noscript>" in html
    if concept["teaching_diagram"]["illustration"]:
        assert 'role="img" aria-labelledby="mechanism-title mechanism-desc"' in html
        assert html.count('id="mechanism-title"') == 1
        assert html.count('id="mechanism-desc"') == 1


@pytest.mark.parametrize("slug", ["bloom", "double-cropping", "firmness", "soil-ph", "strawberry-viruses"])
def test_public_read_does_not_start_research_or_write_state(slug, monkeypatch, tmp_path):
    from app.services.ai_gateway.perplexity_deep_research import DeepResearchClient

    def forbidden(*args, **kwargs):
        pytest.fail("Reading a visual must not launch research")

    monkeypatch.setattr(DeepResearchClient, "start", forbidden)
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    response = TestClient(main.app).get("/learn/" + slug)
    assert response.status_code == 200
    assert "data-teaching-explorer" in response.text
    assert not list(tmp_path.iterdir())


def test_double_cropping_clarification_preserves_originals_and_human_edits():
    original = json.loads((CONCEPTS / "concept-double-cropping.json").read_text(encoding="utf-8"))
    shown = learner_visuals.presentation(original)
    assert shown["summary"] == original["summary"]
    assert shown["what_is_it"] == original["what_is_it"]
    assert "follow-up crop" in shown["lesson_clarification"]["summary"]
    assert "primocane-fruiting" in shown["lesson_clarification"]["what_is_it"]
    for field in ("summary", "what_is_it"):
        edited = deepcopy(original)
        edited[field] = "User-written explanation kept verbatim."
        result = learner_visuals.presentation(edited)
        assert result["lesson_clarification"] is None
        assert result[field] == edited[field]
    shown["lesson_clarification"]["summary"] = "Temporary edit"
    assert learner_visuals.presentation(original)["lesson_clarification"]["summary"] != "Temporary edit"


def test_bloom_is_wax_and_aroma_is_not_an_instrument_texture_claim():
    bloom = learner.concept_by_slug("bloom")
    assert "fruit wax" in bloom["teaching_diagram"]["intro"]
    assert bloom["teaching_diagram"]["illustration"] == "wax"
    assert bloom["teaching_figure"]["license"].startswith("Public domain")
    assert "Scott Bauer" in bloom["teaching_figure"]["attribution"]
    assert "raspberry" not in bloom["teaching_figure"]["alt"].lower()
    firmness = learner.concept_by_slug("firmness")["teaching_diagram"]
    assert all("00502-5" not in s["url"] for s in firmness["sources"])
    texture = learner.concept_by_slug("texture")["teaching_diagram"]
    assert all("1360050" not in s["url"] for s in texture["sources"])
    assert "1360050" in learner.concept_by_slug("volatile-aroma")["teaching_diagram"]["sources"][0]["url"]
    assert "not a chill calculator" in learner.concept_by_slug("chill-hours")["teaching_diagram"]["limit"]


def test_all_presentation_aids_are_independent_copies_and_rights_are_local_to_photo():
    shown = learner_visuals.presentation(learner.concept_by_slug("bloom"))
    shown["teaching_diagram"]["steps"][0]["detail"] = "Changed"
    shown["teaching_figure"]["license"] = "Changed"
    # Presentation must copy caller-owned inputs, not change cached curriculum.
    assert DIAGRAMS["bloom"]["steps"][0]["detail"] != "Changed"
    assert learner_visuals.BLUEBERRY_PHOTO["license"] != "Changed"
    fresh = learner.concept_by_slug("bloom")
    assert fresh["teaching_diagram"]["steps"][0]["detail"] != "Changed"
    assert learner.concept_by_slug("visual-learning-aids")["teaching_figure"] is None
    assert learner.concept_by_slug("primocane-floricane")["teaching_figure"]["license"] == "CC BY 2.5"
