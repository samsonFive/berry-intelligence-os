from pathlib import Path
from urllib.parse import urlsplit

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader, select_autoescape

from app.services.global_search import search_documents
from app.services.variety_season import blackberry_season


DATA = Path(__file__).resolve().parents[1] / "data"


def test_fruiting_habit_and_harvested_cane_are_independent():
    strict = blackberry_season(DATA, "", {"habit": "Floricane"})
    assert len(strict["rows"]) == 9
    second_year = blackberry_season(DATA, "", {"crops": "Floricane"})
    names = {row["name"] for row in second_year["rows"]}
    assert "Prime-Ark Horizon" in names
    assert "Fontana" not in names


def test_alias_and_explicit_facets_intersect():
    filters = {"region": "Southeast US", "markets": "Fresh"}
    result = blackberry_season(DATA, "NC 740", filters)
    assert [row["name"] for row in result["rows"]] == ["Ervin"]
    assert not blackberry_season(DATA, "NC 740", {**filters, "markets": "Processing"})["rows"]


def test_every_observation_and_milestone_resolves_to_original_source():
    result = blackberry_season(DATA, "", {})
    for row in result["rows"]:
        assert row["citations"]
        for source_id in row["citations"] + [event[-1] for event in row["events"]]:
            _, url, locator = result["sources"][source_id]
            assert urlsplit(url).scheme == "https" and locator
        if row["variety_id"]:
            assert (DATA / "entities/varieties" / (row["variety_id"] + ".json")).is_file()


def test_global_search_links_to_pilot_for_original_and_corrected_queries():
    assert search_documents([], "Blackberry Floricans")["blackberry_season"]
    assert search_documents([], "floricane", berry="berry-blackberry")["blackberry_season"]
    assert not search_documents([], "raspberry floricane")["blackberry_season"]


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
        comparison=comparison, filters={key: filters.get(key, "") for key in comparison["facets"]}, query="",
    )
    assert "Mills River, NC" in page and 'value="High tunnel" selected' in page
    assert "Plant stock for 2027 is unverified" in page
    assert "International license" in page and "Sweet-Ark Immaculate" not in page
