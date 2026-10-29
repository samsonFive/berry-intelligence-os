"""Related publications are context, never proof of a focal grant or current right."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app import main


def row(key, title):
    return dict(id=key, title=title, kind='USPTO', published_date='2018-07-01',
                href='/intelligence/'+key, trusted_href='/evidence/'+key)


def test_related_source_dates_review_and_default_scope_are_distinct_from_focal_filings():
    published=[row('fixture-reviewed','Reprint discussing two cultivars')]
    pending=[row('fixture-pending','Pending document')]
    before=deepcopy((published,pending))
    html=main.templates.env.get_template('_variety_related_rights_sources.html').render(
        rights_published=published,rights_drafts=pending,authoring_mode=True,static_build=False)
    first=html[html.index('<details'):].split('>',1)[0]
    assert ' open' not in first and 'Related reports &amp; records · 2' in html
    assert 'Reviewed source' in html and 'Source date 7/1/2018' in html
    assert 'Source review is separate from confirming' in html
    assert 'Pending review' in html and 'data-item-id="fixture-pending"' in html
    assert 'Granted' not in html and '>Trusted<' not in html and '>USPTO<' not in html
    assert (published,pending)==before


@pytest.mark.parametrize('authoring,static',[(False,False),(False,True),(True,True)])
def test_pending_titles_links_and_counts_are_defensively_excluded_outside_private_authoring(authoring,static):
    template=main.templates.env.get_template('_variety_related_rights_sources.html')
    html=template.render(rights_published=[row('reviewed','Reviewed document')],
        rights_drafts=[row('private-draft','PRIVATE_UNREVIEWED_SOURCE')],authoring_mode=authoring,static_build=static)
    assert 'PRIVATE_UNREVIEWED_SOURCE' not in html and 'private-draft' not in html
    assert 'Related reports &amp; records · 1' in html
    if static:
        assert '/evidence/reviewed' in html and 'data-open-reader' not in html
    assert not template.render(rights_published=[],rights_drafts=[row('private','PRIVATE')],
        authoring_mode=authoring,static_build=static).strip()


def test_actual_profile_and_legacy_view_keep_reviewed_records_dates_and_originals_without_writes(monkeypatch,tmp_path):
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    root=Path(__file__).resolve().parents[1]/'data/evidence'
    files=[root/'ev-uspp023572-ridley-1111.json',root/'ev-uspp025432-ridley-1403.json']
    before={p:sha256(p.read_bytes()).hexdigest()for p in files}
    client=TestClient(main.app)
    for suffix in ['','?view=legacy']:
        response=client.get('/entities/variety/variety-eureka'+suffix)
        assert response.status_code==200
        html=response.text
        related=html.split('rights-source-context"',1)[1].split('</details>',1)[0]
        assert 'Reviewed source' in related and 'Source date 7/1/2018' in related
        assert 'ev-uspp023572-ridley-1111' in related and 'Ridley 1111' in related
        assert 'Original filing references' in html and 'Claims' in html
        assert 'PDF page 9' in html and 'C99-42 comparison' in html
    assert {p:sha256(p.read_bytes()).hexdigest()for p in files}==before
    assert not list(tmp_path.rglob('*.json'))
