"""Reading structure retains source lineage and never exposes private decisions."""
from copy import deepcopy
from html import unescape

import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.mark.parametrize("path", ["/signals", "/assessments", "/recommendations", "/strategic-questions"])
def test_catalogs_share_live_navigation_and_current_location(path):
    page = TestClient(main.app).get(path)
    assert page.status_code == 200
    assert 'class="intelligence-workspace"' in page.text
    assert 'aria-label="Intelligence views"' in page.text
    assert f'href="{path}" aria-current="page"' in page.text
    assert '/static/intelligence_workspace.css' in page.text


def test_readonly_judgment_details_do_not_load_private_analyst_decisions(monkeypatch):
    def private_read(*args, **kwargs):
        raise AssertionError("Published view must not load private analyst decisions")

    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    monkeypatch.setattr(main, "load_analyst_queue_state", private_read)
    recommendation = main.all_recommendations()[0]
    client = TestClient(main.app)
    for path in ("/signals/sig-financial-owners-taking-positions-in-berry-genetics", f"/recommendations/{recommendation['id']}"):
        page = client.get(path)
        assert page.status_code == 200
        assert 'class="judgment-takeaway"' in page.text
        assert "alert-decision" not in page.text
        assert "proposal-decision" not in page.text
        assert "Proposal decision:" not in page.text
        assert "Alert decision:" not in page.text
        nav = page.text.split('aria-label="Intelligence views"', 1)[1].split('</nav>', 1)[0]
        assert '/statements' not in nav and '/radar' not in nav


def test_assessment_keeps_both_source_and_fact_counterevidence_without_writes(monkeypatch):
    assessment = deepcopy(main.all_assessments()[0])
    evidence = main.published_evidence()[0]
    fact = main.all_facts()[0]
    assessment["counterevidence_ids"] = [evidence["id"], fact["id"]]
    before = deepcopy(assessment)
    monkeypatch.setattr(main, "assessment_by_id", lambda object_id: assessment)
    page = TestClient(main.app).get(f"/assessments/{assessment['id']}")
    assert page.status_code == 200
    section = page.text.split('<h2>Counterevidence</h2>', 1)[1].split('<details class="judgment-related">', 1)[0]
    assert f'href="/evidence/{evidence["id"]}"' in section
    assert fact["statement"] in unescape(section)
    assert "No counterevidence recorded." not in section
    assert assessment == before


def test_takeaway_precedes_closed_metadata_and_retains_interpretation():
    page = TestClient(main.app).get('/assessments/assessment-financial-capital-entering-berry-genetics-ownership')
    assert page.status_code == 200
    assert page.text.index('class="judgment-takeaway"') < page.text.index('<details class="judgment-meta">')
    assert '<details class="judgment-meta"><summary>Review details</summary>' in page.text
    assert 'Would change our view' in page.text
    assert 'Why it matters' in page.text
    assert 'Counterevidence' in page.text
    assert page.text.index('Supporting evidence') < page.text.index('<details class="judgment-related">')


def test_static_assessment_keeps_published_source_and_fact_counterevidence(monkeypatch, tmp_path):
    from scripts import build_static

    original = deepcopy(build_static.all_assessments())
    rows = deepcopy(original)
    evidence = main.published_evidence()[0]
    fact = main.all_facts()[0]
    rows[0]["counterevidence_ids"] = [evidence["id"], fact["id"]]
    monkeypatch.setattr(build_static, "all_assessments", lambda: rows)
    output = tmp_path / 'static-counterevidence'
    monkeypatch.setattr(build_static, "OUTPUT_DIR", output)
    assert build_static.main() == 0
    page = (output / 'assessments' / rows[0]["id"] / 'index.html').read_text(encoding='utf-8')
    section = page.split('<h2>Counterevidence</h2>', 1)[1].split('<details class="judgment-related">', 1)[0]
    assert evidence["id"] in section
    assert fact["statement"] in unescape(section)
    assert "No counterevidence recorded." not in section
    assert "proposal-decision" not in page and "alert-decision" not in page
    assert main.all_assessments() == original


@pytest.mark.parametrize("kind,loader,field", [
    ("signals", main.all_signals, "description"),
    ("assessments", main.all_assessments, "rationale"),
    ("recommendations", main.all_recommendations, "rationale"),
])
def test_primary_and_supporting_reading_keep_every_authored_unit(kind, loader, field):
    records = deepcopy(loader())
    client = TestClient(main.app)
    for row in records:
        page = client.get(f'/{kind}/{row["id"]}')
        assert page.status_code == 200
        rendered = unescape(page.text)
        original_text = row.get(field) or row.get("observation") or ""
        for unit in main.as_bullets(original_text):
            assert unit in rendered
    assert loader() == records


def test_question_analysis_precedes_collapsed_scope_without_losing_sources():
    page = TestClient(main.app).get('/strategic-questions/sq-public-record-gaps')
    assert page.status_code == 200
    assert page.text.index('id="sq-think"') < page.text.index('id="sq-know"')
    assert page.text.index('id="sq-know"') < page.text.index('id="sq-scope"')
    assert '<details class="v2-company-section judgment-meta" id="sq-scope">' in page.text
    assert 'Supporting source index' in page.text
    assert 'id="sq-source-trace"' in page.text
    assert 'data-open-reader' in page.text
    assert 'What would change our view' in page.text
