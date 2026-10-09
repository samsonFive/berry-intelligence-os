"""Original licensing sources cannot silently approve identities, rights or images."""
from copy import deepcopy
import json
from pathlib import Path

from html.parser import HTMLParser
from fastapi.testclient import TestClient
import pytest

from app import main
from app.services import variety_photos as photos
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA = Path(__file__).resolve().parents[1] / 'data'
PREFIX = 'portfolio-apg-original-'
NAMES = {'Stella-ASBP','Red Rhapsody','Sundrench','Scarlet Rose','Susie','Tahli','Tamara','QSGA 002','QSGA 003','APG 003'}


def sources():
    return [s for s in load_portfolio_observations(DATA) if s['id'].startswith(PREFIX)]


def test_entire_index_programs_and_linked_factsheets_have_explicit_accounting():
    rows, candidates = reconcile_portfolios(sources=sources(), varieties=[], entities=[], candidates=[])
    assert len(rows) == 23 and sum(len(s['names']) for s in rows) == 37
    assert {c['candidate_name'] for c in candidates} == NAMES
    assert all(not s['accounting_view']['issues'] for s in rows)
    assert sum(s['needs_follow_up'] for s in rows) == 5  # Three unnamed overviews, two conflicting Stella sources.
    assert all(s['company_ids'] == ['company-australasian-plant-genetics'] and not s.get('published_date') for s in rows)
    index = next(s for s in rows if s['id'] == PREFIX+'all-varieties')
    assert len(index['names']) == 10
    assert len(next(s for s in rows if s['id'] == PREFIX+'asbp-program')['names']) == 7
    civ = next(s for s in rows if s['id'] == PREFIX+'civ-program')
    assert {n['candidate_name'] for n in civ['names']} == {'QSGA 002','QSGA 003','APG 003'}
    assert civ['accounting_view']['exclusions'][0]['label'] == 'QSGA 002-003'
    assert 'Florida Festival' not in NAMES and 'Albion' not in NAMES
    assert {e['label'] for s in rows for e in s['accounting_view']['exclusions']} >= {'Florida Festival','Albion','Macadamia varieties'}
    for c in candidates:
        assert not c['human_gated'] and not c['auto_confirmed'] and not c['aliases'] and not c['proposed_relationships']
        assert not c['registration']['status'] and not c.get('breeder_code')


def test_conflicting_protection_and_printed_pdf_revision_remain_unresolved():
    rows = sources()
    web = next(s for s in rows if s['id'] == PREFIX+'stella-asbp')
    pdf = next(s for s in rows if s['id'] == PREFIX+'stella-asbp-factsheet')
    assert 'applied for' in web['review_warnings'][0] and 'protected' in pdf['review_warnings'][0]
    assert pdf['url'].endswith('FACTSHEET-STELLA-ASBP-V1.pdf')
    assert pdf['capture_reference']['printed_document_label'] == 'FACTSHEET-STELLA-ASBP-V2'
    factsheets = [s for s in rows if s['source_type'] == 'company_variety_factsheet']
    assert len(factsheets) == 7
    assert all(s['capture_reference']['all_pages_read'] and s['capture_reference']['visually_checked_pages'] == [1]
               and s['capture_reference']['page_count'] == 1 and len(s['capture_reference']['sha256']) == 64 for s in factsheets)
    apg = next(s for s in rows if s['id'] == PREFIX+'apg-003')
    assert 'October 2022' in apg['names'][0]['portfolio_context']
    assert 'today' in apg['names'][0]['portfolio_context'] and not apg.get('published_date')
    _, candidates = reconcile_portfolios(sources=rows, varieties=[], entities=[], candidates=[])
    stella = next(c for c in candidates if c['candidate_name'] == 'Stella-ASBP')
    assert len(stella['portfolio_review_warnings']) == 2
    assert not stella['registration']['status'] and not stella['human_gated']


def test_existing_candidate_ids_and_operator_fields_survive_added_provenance():
    all_sources = load_portfolio_observations(DATA)
    _, before = reconcile_portfolios(sources=[s for s in all_sources if not s['id'].startswith(PREFIX)], varieties=[], entities=[], candidates=[])
    _, after = reconcile_portfolios(sources=all_sources, varieties=[], entities=[], candidates=[])
    identifiers = {(c['candidate_name'],c['berry_id']): c['id'] for c in after}
    assert all(identifiers[(c['candidate_name'],c['berry_id'])] == c['id'] for c in before)
    human = {'id':'operator-red-rhapsody','candidate_name':'Red Rhapsody','berry_id':'berry-strawberry',
             'identity_state':'distinct','status':'reviewed','human_gated':True,'aliases':['Operator label'],
             'registration':{'status':'Keep my note'},'review_notes':'Keep notes','photos':[{'operator':'Keep image choice'}]}
    saved = deepcopy(human)
    _, candidates = reconcile_portfolios(sources=sources(),varieties=[],entities=[],candidates=[human])
    c = next(c for c in candidates if c['id'] == human['id'])
    assert all(c[k] == saved[k] for k in ['identity_state','status','aliases','registration','review_notes','photos'])
    assert human == saved


def test_all_ten_named_hero_photos_are_attributed_held_and_crop_specific():
    _, candidates = reconcile_portfolios(sources=sources(), varieties=[], entities=[], candidates=[])
    for c in candidates:
        gallery = photos.gallery(c, sourced=photos.source_photos(c,candidate=True), authoring=True)
        assert len(gallery) == 1
        p = gallery[0]
        assert p['named_variety'] == c['candidate_name'] and p['source_url'].startswith('https://ausplantgenetics.com.au/varieties/')
        assert p['reuse'] == 'unknown' and not p['display_image'] and not p['license_url']
        assert 'photographer not individually credited' in p['credit']
        assert 'radar' not in p['image_url'].lower() and '300x300' not in p['image_url']
        assert not photos.gallery(c,sourced=gallery,authoring=False)
        assert not photos.compatible(p,dict(candidate_name=c['candidate_name'],berry_id='berry-blueberry'),candidate=True)


def test_warning_validation_rejects_non_text_and_unbounded_source_notes(tmp_path):
    path = tmp_path/'imports/variety-portfolio-observations-fixture/observations.json'
    path.parent.mkdir(parents=True)
    source = sources()[0]
    for warnings in ['not a list',[{}],[''],['x'*1001],['warning']*9]:
        path.write_text(json.dumps({'kind':'unreviewed_portfolio_name_observations','sources':[{**source,'review_warnings':warnings}]}))
        with pytest.raises(ValueError,match='Stored portfolio observations failed validation') as error:
            load_portfolio_observations(tmp_path)
        assert 'Source review warnings' in str(error.value.__cause__)


def test_live_source_conflict_is_outside_collapsed_context_and_public_has_no_private_photos(monkeypatch,tmp_path):
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    client = TestClient(main.app)
    page = client.get('/varieties/coverage',params={'company':'company-australasian-plant-genetics'})
    assert page.status_code == 200
    row = page.text.split('id="portfolio-source-'+PREFIX+'stella-asbp-factsheet"',1)[1].split('</tr>',1)[0]
    assert 'Source details need checking' in row and 'V1.pdf' in row
    class Structure(HTMLParser):
        def __init__(self):
            super().__init__(); self.stack=[]; self.warnings=[]; self.contexts=[]
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if 'portfolio-review-warnings' in attrs.get('class',''):
                self.warnings.append([a.get('class','') for _,a in self.stack])
            if attrs.get('class') == 'portfolio-source-context':
                self.contexts.append(attrs)
            if tag not in {'br','img','input','link','meta','hr'}:
                self.stack.append((tag,attrs))
        def handle_endtag(self, tag):
            for i in range(len(self.stack)-1,-1,-1):
                if self.stack[i][0] == tag:
                    self.stack = self.stack[:i]; break
    structure = Structure(); structure.feed('<tr '+row+'</tr>')
    assert structure.warnings and all('portfolio-source-context' not in ancestry for ancestry in structure.warnings)
    assert structure.contexts and all('open' not in attrs for attrs in structure.contexts)
    original_universe = main.variety_candidate_universe
    _, candidates = reconcile_portfolios(sources=sources(),varieties=[],entities=[],candidates=[])
    monkeypatch.setattr(main,'variety_candidate_universe',lambda:([],candidates,{}))
    conflict_page = client.get('/varieties/candidates',params={'source':PREFIX+'stella-asbp-factsheet','q':'Stella-ASBP'})
    assert conflict_page.status_code == 200
    assert 'aria-label="Source details to check"' in conflict_page.text
    conflict = next(s for s in sources() if s['id'] == PREFIX+'stella-asbp')['review_warnings'][0]
    assert conflict_page.text.count(conflict) == 1
    page = client.get('/varieties/candidates',params={'source':PREFIX+'qsga-002','q':'QSGA 002'})
    assert page.status_code == 200 and 'Ignore permission' in page.text
    photo = next(s for s in sources() if s['id'] == PREFIX+'qsga-002')['names'][0]['photos'][0]
    assert 'data-image-url="'+photo['image_url']+'"' in page.text and 'src="'+photo['image_url']+'"' not in page.text
    assert not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main,'variety_candidate_universe',original_universe)
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    public = client.get('/varieties/coverage',params={'company':'company-australasian-plant-genetics'})
    assert public.status_code == 200 and PREFIX not in public.text and 'V1.pdf' not in public.text
    assert client.get('/varieties/candidates').status_code == 403
    assert not list(tmp_path.rglob('*.json'))
