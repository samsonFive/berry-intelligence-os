"""Source/rights preservation and shared public teaching presentation."""
from copy import deepcopy
from html import unescape

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import learner, learner_visuals


@pytest.mark.parametrize("slug", ["ipm", "harvest-robotics", "sugar-acid-balance", "visual-learning-aids"])
def test_teaching_diagrams_preserve_records_and_are_idempotent(slug):
    concept = learner.concept_by_slug(slug)
    original = deepcopy(concept)
    shown = learner_visuals.presentation(concept)
    assert concept == original
    assert learner_visuals.presentation(shown) == shown
    assert shown["sources"] == original["sources"]
    assert shown["how_to_interpret"] == original["how_to_interpret"]
    assert shown["teaching_diagram"]["limit"]
    assert all(source["url"].startswith("https://") for source in shown["teaching_diagram"]["sources"])
    shown["teaching_diagram"]["steps"][0]["title"] = "Edited locally"
    assert learner_visuals.DIAGRAMS[slug]["steps"][0]["title"] != "Edited locally"


@pytest.mark.parametrize("slug", ["ipm", "harvest-robotics", "sugar-acid-balance", "visual-learning-aids"])
def test_reading_a_visual_lesson_keeps_content_and_does_not_start_research(slug, monkeypatch, tmp_path):
    from app.services.ai_gateway import perplexity_deep_research

    def forbidden(*args, **kwargs):
        pytest.fail("Reading a lesson must not start paid research")

    monkeypatch.setattr(perplexity_deep_research.DeepResearchClient, "start", forbidden)
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    response = TestClient(main.app).get("/learn/" + slug)
    assert response.status_code == 200
    assert 'data-teaching-explorer' in response.text
    assert "Original schematic by Berry Intelligence" in response.text
    assert "EDUCATIONAL KNOWLEDGE" in response.text
    assert "Research &amp; expand" not in response.text
    for key in ("what_is_it", "why_it_matters", "how_evaluated", "what_affects_it", "how_to_interpret"):
        assert learner.concept_by_slug(slug)[key] in unescape(response.text)
    assert not list(tmp_path.iterdir())


def test_unverified_picture_stays_a_source_link_and_verified_photo_has_attribution():
    unverified = learner.concept_by_slug("visual-learning-aids")
    assert unverified["teaching_figure"] is None
    assert any(item["url"].endswith("File:Blueberries.jpg") for item in unverified["media"])
    verified = learner.concept_by_slug("primocane-floricane")
    assert verified["teaching_figure"]["license"] == "CC BY 2.5"
    assert verified["teaching_figure"]["attribution"]
    shown = learner_visuals.presentation(verified)
    shown["teaching_figure"]["caption"] = "Changed"
    assert learner_visuals.PHOTO["caption"] != "Changed"


def test_static_learn_uses_public_shared_templates_and_real_search_route():
    concept = learner.concept_by_slug("visual-learning-aids")
    from types import SimpleNamespace
    request = SimpleNamespace(url=SimpleNamespace(path="/learn/visual-learning-aids"))
    html = main.templates.env.get_template("learn_workspace_concept.html").render(
        request=request, concept=concept, authoring_mode=False, static_build=True, return_to="/learn",
        related=[], related_intelligence={"rows": []}, berry_notes={"has_any": False},
    )
    assert "data-teaching-explorer" in html
    # Before script enhancement, every explanation remains readable.
    assert all(step["detail"] in unescape(html) for step in concept["teaching_diagram"]["steps"])
    assert "Special:FilePath/Blueberries.jpg" not in html
    assert "Research &amp; expand" not in html
    home = main.templates.env.get_template("learn_workspace_home.html").render(
        request=request, authoring_mode=False, static_build=True, search_results=None, stale_view=False,
        pillars=[], concept_count=23,
    )
    assert 'href="/search"' in home and 'href="/learn/stale"' in home
    assert 'name="q"' not in home
