"""Historical product labels preserve crop, chronology and identity conflicts."""
from copy import deepcopy
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services.variety_portfolio_coverage import load_portfolio_observations, portfolio_coverage, reconcile_portfolios

DATA = Path(__file__).resolve().parents[1] / 'data'
IDS = {'portfolio-singrow-nus-report-2023', 'portfolio-singrow-company-interview-2021',
       'portfolio-surexport-company-interview-2013'}


def inputs():
    sources = load_portfolio_observations(DATA)
    return sources, {s['id']: s for s in sources if s['id'] in IDS}


def test_original_names_clocks_and_accounting_do_not_create_legal_or_current_claims():
    _, cohort = inputs()
    assert set(cohort) == IDS and sum(len(s['names']) for s in cohort.values()) == 15
    nus = cohort['portfolio-singrow-nus-report-2023']
    assert [n['candidate_name'] for n in nus['names']] == ['Crystal', 'Rouge', 'Winterbelle', 'Blush']
    assert not nus.get('published_date')
    assert nus['capture_reference']['pdf_pages_read'] == [1, 4, 25, 26]
    assert nus['capture_reference']['prior_direct_status'] == 404
    assert nus['capture_reference']['capture_sha256'] == '8bed3ef7651a760821e08f454ee435b7549217efc8a098bf363dcb48d3476768'
    assert nus['url'].endswith('/2026/09/NUS-Sustainability-Report-2023.pdf#page=25')
    assert [n['product_url'].split('#')[-1] for n in nus['names']] == ['page=25','page=26','page=26','page=26']
    old = cohort['portfolio-singrow-company-interview-2021']
    assert old['published_date'] == '2021-08-24'
    assert [n['candidate_name'] for n in old['names']] == ['Ruby','Crystal']
    sure = cohort['portfolio-surexport-company-interview-2013']
    assert sure['published_date'] == '2013-04-16'
    assert [n['candidate_name'] for n in sure['names'] if n['berry_id']=='berry-strawberry'] == ['Candonga','Sabrina','Splendour','Virtue','Victoria']
    assert [n['candidate_name'] for n in sure['names'] if n['berry_id']=='berry-raspberry'] == ['Glen Lyon','Tulameen','Radiance','Grandeur']
    assert all(s['review_state']=='unreviewed' for s in cohort.values())
    assert all(not n.get(key) for s in cohort.values() for n in s['names']
               for key in ('photos','denomination','breeder_code','grant_date','patent_number','aliases'))
    for source in cohort.values():
        assert source['accounting']['observed_items'] == len(source['names'])+len(source['accounting']['exclusions'])
    excluded = {r['label'] for s in cohort.values() for r in s['accounting']['exclusions']}
    assert excluded == {'Blooom','Fast Cultivation Method','Cherrito','Komatsuna','Doñarosa'}


def test_conflicting_crystal_and_ruby_rouge_labels_stay_visible_and_unapproved():
    _, cohort = inputs()
    rows, candidates = reconcile_portfolios(sources=list(cohort.values()),varieties=[],entities=[],candidates=[])
    by_name = {c['candidate_name']:c for c in candidates}
    assert {'Crystal','Ruby','Rouge','Winterbelle','Blush'} <= set(by_name)
    crystal = by_name['Crystal']
    assert len(crystal['portfolio_sources']) == 2
    assert any('pictured red' in w and 'white' in w for w in crystal['portfolio_review_warnings'])
    assert all('pictured red' not in w for w in by_name['Winterbelle']['portfolio_review_warnings'])
    assert by_name['Ruby']['id'] != by_name['Rouge']['id']
    assert all(not c['aliases'] and not c['human_gated'] and not c['auto_confirmed'] for c in candidates)
    assert all(not c['proposed_relationships'] and not c['breeder_owner'] for c in candidates)
    assert all(not c['registration']['grant_date'] and not c['deployment'] for c in candidates)
    assert all(row['needs_follow_up'] and not row['accounting_view']['issues'] for row in rows)


def test_strawberry_victoria_does_not_match_existing_blackberry_or_invent_roles():
    _, cohort = inputs()
    victoria = dict(id='variety-victoria',entity_type='variety',name='Victoria',
                    berry_ids=['berry-blackberry'],aliases=["Driscoll's Victoria"])
    rows, candidates = reconcile_portfolios(sources=[cohort['portfolio-surexport-company-interview-2013']],
        varieties=[victoria],entities=[victoria],candidates=[])
    row = next(n for n in rows[0]['names'] if n['candidate_name']=='Victoria')
    candidate = next(c for c in candidates if c['candidate_name']=='Victoria')
    assert row['berry_id']=='berry-strawberry' and row['status']=='needs_review' and not row['catalog_id']
    assert not candidate['candidate_canonical_match'] and not candidate['proposed_relationships']
    assert any('not the catalog blackberry' in w for w in candidate['portfolio_review_warnings'])
    assert victoria['aliases']==["Driscoll's Victoria"]


def test_append_and_replay_preserve_saved_ids_rejections_fields_and_photo_choices():
    sources, _ = inputs()
    baseline = [s for s in sources if s['id'] not in IDS]
    _, saved = reconcile_portfolios(sources=baseline,varieties=[],entities=[],candidates=[])
    saved.append(dict(id='fixture-saved-ruby',candidate_name='Ruby',berry_id='berry-strawberry',
        status='rejected',identity_state='rejected',human_gated=True,reviewer='Fixture analyst',
        review_notes='Keep my decision',aliases=['My private spelling'],photos=[{'operator':'Keep chosen image'}],
        registration={'status':'Keep user status'},knowledge={'notes':'My research'}))
    original = deepcopy((sources,saved))
    rows, after = reconcile_portfolios(sources=sources,varieties=[],entities=[],candidates=saved)
    indexed = {c['id']:c for c in after}
    for previous in saved:
        assert previous['id'] in indexed
        for key,value in previous.items():
            if key not in {'portfolio_sources','portfolio_review_warnings','portfolio_identity_notes'}:
                assert indexed[previous['id']][key] == value
    ruby = next(n for s in rows if s['id']=='portfolio-singrow-company-interview-2021'
                for n in s['names'] if n['candidate_name']=='Ruby')
    assert ruby['candidate_id']=='fixture-saved-ruby' and ruby['status']=='previously_rejected' and not ruby['catalog_id']
    repeated_rows,repeated = reconcile_portfolios(sources=sources,varieties=[],entities=[],candidates=after)
    assert repeated_rows==rows and repeated==after
    assert len({c['id'] for c in after})==len(after) and (sources,saved)==original


def test_company_named_source_progress_retains_incomplete_portfolio_states():
    sources, _ = inputs()
    entities = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((DATA/'entities').rglob('*.json'))]
    varieties = [e for e in entities if e.get('entity_type')=='variety']
    report = portfolio_coverage(data_dir=DATA,sources=sources,varieties=varieties,entities=entities,candidates=[])
    assert report['summary']['registry_entries']==77
    assert report['summary']['registry_entries_checked']==66
    for company,count in [('company-singrow',6),('company-surexport',9)]:
        subject = next(s for s in report['subjects'] if company in s['entity_ids'])
        assert subject['source_status']=='names_found' and subject['checked']
        assert subject['has_source_gaps'] and subject['named_occurrences']==count
    assert not any(n['catalog_id'] for s in report['sources'] if s['id'] in IDS for n in s['names'])


def test_routes_keep_scope_periods_conflicts_and_original_links_without_get_writes(monkeypatch,tmp_path):
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    client = TestClient(main.app)
    sing = client.get('/varieties/candidates',params={'company':'company-singrow','source':'portfolio-singrow-nus-report-2023'})
    assert sing.status_code==200
    assert all(name in sing.text for name in ['Crystal','Rouge','Winterbelle','Blush'])
    assert 'pictured red' in sing.text and 'white' in sing.text and 'NUS Sustainability Report 2023' in sing.text
    assert 'NUS-Sustainability-Report-2023.pdf#page=25' in sing.text
    sure = client.get('/varieties/candidates',params={'company':'company-surexport','source':'portfolio-surexport-company-interview-2013','berry':'berry-raspberry'})
    assert sure.status_code==200
    assert all(name in sure.text for name in ['Glen Lyon','Tulameen','Radiance','Grandeur'])
    assert {row['candidate_name'] for row in sure.context['candidates']} == {'Glen Lyon','Tulameen','Radiance','Grandeur'}
    assert all(row['berry_id']=='berry-raspberry' for row in sure.context['candidates'])
    assert '<b>Victoria</b>' not in sure.text and '<b>Candonga</b>' not in sure.text
    source = client.get('/varieties/coverage/source/portfolio-singrow-nus-report-2023')
    assert source.status_code==200 and '2023' in source.text and 'publication date' in source.text
    for company,count,names in [
        ('company-singrow',5,['Crystal','Ruby','Rouge','Winterbelle','Blush']),
        ('company-surexport',9,['Candonga','Sabrina','Splendour','Virtue','Victoria','Glen Lyon','Tulameen','Radiance','Grandeur'])]:
        profile = client.get('/entities/company/'+company,params={'tab':'varieties'})
        assert profile.status_code==200 and str(count)+' additional names to check' in profile.text
        assert all(name in profile.text for name in names)
        assert 'Name needs review' in profile.text and 'source sections still need follow-up' in profile.text
    assert not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    assert client.get('/varieties/candidates').status_code==403
    assert client.get('/varieties/coverage/source/portfolio-singrow-nus-report-2023').status_code==403
