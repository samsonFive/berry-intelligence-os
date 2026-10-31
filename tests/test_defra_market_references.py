"""Offline official-source tests; the original public capture stays unselected."""
from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime
from io import BytesIO
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
import httpx
from fastapi.testclient import TestClient

from app import main
from app.services import defra_market_references as uk
from app.services import map_statistics_refresh as refresh
from app.services.global_explorer import IntelligenceQuery, snapshot_model
from app.services.map_workspace import statistics
from app.services.market_statistics_reference import group_id, identified_groups, reference_groups
from app.services.report_builder import pdf_export
from scripts.capture_map_statistics import capture_defra

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / 'data/imports/map-market-references-2026-10-31-uk/defra-berries.json'
STAMP = '2026-10-31T18:00:00+00:00'
TOKEN = 'explicit-uk-figures-review'
NOTICE = uk.POLICY + '. Strawberry production declined. The total cultivated area remained stable at 4,602 hectares. The raspberry growing area declined marginally by 1.5% to 1,344 hectares.'
BERRIES = {'berry-blueberry': 'Blueberry', 'berry-strawberry': 'Strawberry', 'berry-raspberry': 'Raspberry'}


def document():
    return json.loads(CAPTURE.read_text(encoding='utf-8'))


def workbook(mutation=None):
    """Small ODS fixture using the nine retained official cell texts/values."""
    root = ET.Element('{' + uk.NS['o'] + '}document-content')
    sheet = ET.SubElement(root, '{' + uk.NS['o'] + '}spreadsheet')
    def table(name, rows):
        t = ET.SubElement(sheet, '{' + uk.NS['t'] + '}table', {'{' + uk.NS['t'] + '}name': name})
        for row in rows:
            tr = ET.SubElement(t, '{' + uk.NS['t'] + '}table-row')
            for text, raw in row:
                cell = ET.SubElement(tr, '{' + uk.NS['t'] + '}table-cell')
                if raw is not None:
                    cell.set('{' + uk.NS['o'] + '}value', raw)
                ET.SubElement(cell, '{' + uk.NS['x'] + '}p').text = text
        return t
    table('Notes_and_Contact_Details', [[('Published: 25th June 2026', None)], [('Horticultural Statistics 2025', None)]])
    for name, (code, _, _, unit) in uk.TABLES.items():
        rows = [[(unit, None)], [('', None), ('CALENDAR YEAR', None), ('2025', '2025')]]
        for crop in uk.CROPS:
            c = next(c for c in document()['source_cells'] if c['crop'] == crop and c['metric'] == code)
            rows.append([('', None), (crop, None), (c['text'], c['cached_value'])])
        t = table(name, rows)
        # The actual area sheet also has an older panel with repeated crop
        # names. It must never replace the current-year figures.
        if name == 'Table_4_Fruit_area':
            extra = [[('(Hectares)', None)], [('', None), ('YEAR', None), ('2010', '2010')],
                     [('', None), ('Strawberries', None), ('99', '99')]]
            old = table('temporary', extra)
            for row in list(old): t.append(row)
            sheet.remove(old)
    if mutation:
        mutation(root)
    out = BytesIO()
    with ZipFile(out, 'w') as z:
        z.writestr('mimetype', 'application/vnd.oasis.opendocument.spreadsheet')
        z.writestr('content.xml', ET.tostring(root))
    return out.getvalue()


def parse(content=None, **kwargs):
    d = document()
    return uk.workbook_capture(workbook() if content is None else content, source_url=d['groups'][0]['source_url'],
                              notice_text=NOTICE, notice_url=d['groups'][0]['notice_url'],
                              captured_at=STAMP, **kwargs)


def test_retained_source_cells_replay_as_nine_original_unit_figures():
    actual = parse()
    assert len(actual['groups']) == 3 and sum(len(g['metrics']) for g in actual['groups']) == 9
    groups = {g['berry_id']: g for g in actual['groups']}
    assert [m['value'] for m in groups['berry-strawberry']['metrics']] == [92.9, 4427, 20.99]
    assert [m['value'] for m in groups['berry-raspberry']['metrics']] == [17.4, 1314, 13.26]
    assert [m['value'] for m in groups['berry-blueberry']['metrics']] == [3.5, 410, 8.6]
    assert all([m['unit'] for m in g['metrics']] == ['1000 t', 'ha', 't/ha'] for g in groups.values())
    assert all(m['label'] != 'Harvested production' for g in groups.values() for m in g['metrics'])
    assert all('Planted area differs' in groups[b]['date_note'] for b in ('berry-strawberry', 'berry-raspberry'))
    assert groups['berry-blueberry']['date_note'] == ''
    assert next(c for c in actual['source_cells'] if c['crop'] == 'Strawberries' and c['metric'] == 'planted_area')['cached_value'] == '4426.6623181360264'
    refresh.validate_groups(actual['groups'])
    assert document()['state'] == 'reference_capture_for_review'


@pytest.mark.parametrize('change', ['unit', 'crop', 'year', 'display', 'cached', 'duplicate'])
def test_changed_or_ambiguous_workbook_cannot_become_a_reference(change):
    def mutation(root):
        t = root.find('.//t:table[@t:name="Table_4_Fruit_area"]', uk.NS)
        rows = t.findall('t:table-row', uk.NS)
        if change == 'unit': rows[0].find('.//x:p', uk.NS).text = '(Thousand hectares)'
        if change == 'crop': rows[2].findall('t:table-cell', uk.NS)[1].find('x:p', uk.NS).text = 'Mixed berries'
        if change == 'year': rows[1].findall('t:table-cell', uk.NS)[2].find('x:p', uk.NS).text = '2024'
        if change in {'display', 'cached'}:
            cell = rows[2].findall('t:table-cell', uk.NS)[2]
            if change == 'display': cell.find('x:p', uk.NS).text = '#REF!'
            else: cell.set('{' + uk.NS['o'] + '}value', '7')
        if change == 'duplicate': t.insert(3, deepcopy(rows[2]))
    with pytest.raises(ValueError):
        parse(workbook(mutation))


def test_missing_cell_stays_missing_zero_remains_zero_and_yield_is_not_calculated():
    def mutation(root):
        t = root.find('.//t:table[@t:name="Table_5_Fruit_yield"]', uk.NS)
        cell = t.findall('t:table-row', uk.NS)[2].findall('t:table-cell', uk.NS)[2]
        cell.attrib.clear(); cell.find('x:p', uk.NS).text = '. .'
        t = root.find('.//t:table[@t:name="Table_6_Fruit_production"]', uk.NS)
        cell = t.findall('t:table-row', uk.NS)[2].findall('t:table-cell', uk.NS)[2]
        cell.set('{' + uk.NS['o'] + '}value', '0'); cell.find('x:p', uk.NS).text = '0.0'
    group = parse(workbook(mutation))['groups'][0]
    assert [m['source_code'] for m in group['metrics']] == ['marketed_production', 'planted_area']
    assert group['metrics'][0]['value'] == 0


def test_an_area_discrepancy_is_not_invented_when_the_notice_is_missing_or_agrees():
    d=document(); kwargs={'source_url':d['groups'][0]['source_url'], 'notice_url':d['groups'][0]['notice_url'], 'captured_at':STAMP}
    unknown=uk.workbook_capture(workbook(),notice_text=uk.POLICY,**kwargs)['groups'][0]
    assert 'was not reconciled' in unknown['date_note'] and 'differs' not in unknown['date_note']
    agreeing=NOTICE.replace('4,602','4,427').replace('1,344','1,314')
    groups=uk.workbook_capture(workbook(),notice_text=agreeing,**kwargs)['groups']
    assert all(not g['date_note'] for g in groups)


@pytest.mark.parametrize('content', [b'', b'not-an-ods'])
def test_invalid_source_file_is_not_a_successful_capture(content):
    with pytest.raises(ValueError): parse(content)


@pytest.mark.parametrize('url', ['https://elsewhere.invalid/test.ods', 'http://assets.publishing.service.gov.uk/media/a/hort-dataset-25-20260625.ods',
                                 'https://assets.publishing.service.gov.uk:443/media/a/hort-dataset-25-20260625.ods',
                                 'https://assets.publishing.service.gov.uk/media/a/hort-dataset-25-20260625.ods?key=secret'])
def test_only_expected_public_dataset_locations_are_accepted(url):
    assert not uk.dataset_url(url)


def test_bounded_discovery_retains_originals_and_never_overwrites_captures(tmp_path):
    d = document(); url = d['groups'][0]['source_url']; notice = d['groups'][0]['notice_url']
    bodies = {uk.LANDING: ('<a href="'+url+'">Dataset</a>').encode(), notice: NOTICE.encode(), url: workbook()}
    calls = []
    def fetch(url, *, maximum):
        calls.append((url, maximum)); return bodies[url]
    first, groups = capture_defra(output_dir=tmp_path, fetch=fetch, now=datetime.fromisoformat(STAMP))
    before = first.read_bytes()
    second, _ = capture_defra(output_dir=tmp_path, fetch=fetch, now=datetime.fromisoformat(STAMP))
    assert first != second and first.read_bytes() == before
    assert (first.parent/'original.ods').read_bytes() == bodies[url]
    assert calls[:3] == [(uk.LANDING, 1_000_000), (notice, 1_000_000), (url, 2_000_000)]
    assert len(groups) == 3 and json.loads(first.read_text())['state'] == 'reference_capture_for_review'


@pytest.mark.parametrize('case', ['body_limit', 'redirect'])
def test_transport_stops_at_the_byte_limit_and_does_not_follow_redirects(case, monkeypatch):
    calls=[]
    @contextmanager
    def stream(method,url,**kwargs):
        calls.append((method,url,kwargs))
        if case=='redirect':
            yield httpx.Response(302,headers={'location':'http://127.0.0.1/private'},request=httpx.Request('GET',url))
        else:
            class Response:
                is_redirect=False
                def raise_for_status(self): pass
                def iter_bytes(self):
                    yield b'ab';yield b'cd'
                    pytest.fail('Reader continued after its byte limit.')
            yield Response()
    monkeypatch.setattr(uk.httpx,'stream',stream)
    with pytest.raises((ValueError,httpx.HTTPStatusError)):
        uk.fetch_bytes(uk.LANDING,maximum=3)
    assert len(calls)==1 and calls[0][2]['follow_redirects'] is False


@pytest.mark.parametrize('case', ['expanded_xml', 'member_count', 'mimetype_size'])
def test_oversized_archive_metadata_is_rejected_before_decompression(case, monkeypatch):
    class Info:
        def __init__(self,size):self.file_size=size
    class Archive:
        def __init__(self,*args):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def getinfo(self,name):
            size=20_000_001 if case=='expanded_xml' and name=='content.xml' else 101 if case=='mimetype_size' and name=='mimetype' else 50
            return Info(size)
        def infolist(self):return [None]*(257 if case=='member_count' else 2)
        def read(self,*args):pytest.fail('Oversized archive content was decompressed.')
    monkeypatch.setattr(uk,'ZipFile',Archive)
    with pytest.raises(ValueError,match='Oversized'):
        parse(b'bounded-archive-metadata-fixture')


@pytest.mark.parametrize('case', ['columns', 'rows'])
def test_oversized_grids_are_rejected_without_expanding_repeated_cells(case):
    def mutation(root):
        t=root.find('.//t:table[@t:name="Table_4_Fruit_area"]',uk.NS)
        if case=='columns':
            cell=t.find('t:table-row/t:table-cell',uk.NS)
            cell.set('{' + uk.NS['t'] + '}number-columns-repeated','1000000')
        else:
            for _ in range(301):ET.SubElement(t,'{' + uk.NS['t'] + '}table-row')
    with pytest.raises(ValueError):parse(workbook(mutation))


def test_oversized_source_failure_keeps_selected_references_and_history(tmp_path, monkeypatch):
    groups=document()['groups'];job,_=refresh.reserve(tmp_path,TOKEN,'defra')
    refresh.update(tmp_path,job['id'],status='ready',message='Ready.',groups=groups)
    state=refresh.load(tmp_path)
    refresh.apply(tmp_path,job['id'],[group_id(groups[0])],state['revision'],'Fictional analyst')
    old=refresh.load(tmp_path)
    new,_=refresh.reserve(tmp_path,'explicit-oversized-uk-retry','defra')
    def unavailable(**kwargs):raise ValueError('PRIVATE oversized source detail')
    monkeypatch.setattr(refresh,'capture_defra',unavailable)
    refresh.run(tmp_path,new['id'])
    saved=refresh.load(tmp_path)
    assert saved['jobs'][new['id']]['status']=='failed'
    assert saved['approved']==old['approved'] and saved['history']==old['history']
    assert 'PRIVATE' not in str(saved) and not (tmp_path/refresh.SUBDIR/'captures').exists()


@pytest.mark.parametrize('mutation', ['country', 'crop', 'url', 'year', 'unit', 'classification', 'negative', 'cell'])
def test_saved_source_crop_period_units_and_qualifications_fail_closed(mutation):
    group = deepcopy(document()['groups'][0])
    if mutation == 'country': group['country_id'] = 'geography-china'
    if mutation == 'crop': group['berry_id'] = 'berry-blackberry'
    if mutation == 'url': group['source_url'] = group['source_url'].replace('dataset-25', 'dataset-24')
    if mutation == 'year': group['period'] = '2024 calendar year'
    if mutation == 'unit': group['metrics'][0]['unit'] = '1000 ha'
    if mutation == 'classification': group['metrics'][0]['classification'] = 'Verified fact'
    if mutation == 'negative': group['metrics'][0]['value'] = -1
    if mutation == 'cell': group['metrics'][0]['source_cell'] = 'arbitrary claim'
    with pytest.raises(ValueError): refresh.validate_groups([group])


def test_shared_selection_preserves_other_sources_and_public_seed(tmp_path, monkeypatch):
    baseline = reference_groups(); seed = (ROOT/'data/configuration/market_statistics_reference.json').read_bytes()
    groups = document()['groups']; job, _ = refresh.reserve(tmp_path, TOKEN, 'defra')
    refresh.update(tmp_path, job['id'], status='ready', message='Ready.', groups=groups)
    state = refresh.load(tmp_path); assert not state['approved']
    selected = next(g for g in groups if g['berry_id'] == 'berry-blueberry')
    refresh.apply(tmp_path, job['id'], [group_id(selected)], state['revision'], 'Fictional analyst')
    assert refresh.references(baseline, tmp_path, True) == baseline + [selected]
    assert refresh.references(baseline, tmp_path, False) == baseline
    saved = refresh.path(tmp_path).read_bytes()
    assert not refresh.apply(tmp_path, job['id'], [group_id(selected)], refresh.load(tmp_path)['revision'], 'Fictional analyst')
    assert refresh.path(tmp_path).read_bytes() == saved
    monkeypatch.setattr('app.services.map_workspace.reference_groups', lambda: deepcopy(baseline))
    country = {'id': uk.COUNTRY_ID, 'entity_type': 'geography', 'name': 'United Kingdom', 'attributes': {'iso_3166_1_alpha_2': 'GB'}}
    entities = {country['id']: country}
    query = IntelligenceQuery((uk.COUNTRY_ID,), berry_ids=('berry-blueberry',))
    model = snapshot_model(query, [], entities, [], BERRIES, ['statistics'], inbox_dir=tmp_path, authoring=True)
    assert model['statistics']['groups'] == statistics(query, entities, [], inbox_dir=tmp_path, authoring=True)['groups']
    assert len(model['statistics']['groups']) == 1
    assert next(m for m in model['statistics']['groups'][0]['metrics'] if m['source_code']=='marketed_yield')['value'] == 8.6
    assert not statistics(query, entities, [], inbox_dir=tmp_path, authoring=False)['groups']
    assert (ROOT/'data/configuration/market_statistics_reference.json').read_bytes() == seed
    assert refresh.load(tmp_path)['history'][0]['before'] == []


def test_wrong_source_cannot_corrupt_a_job_and_legacy_jobs_need_no_rewrite(tmp_path):
    groups=document()['groups']; job,_=refresh.reserve(tmp_path,TOKEN)
    before=refresh.path(tmp_path).read_bytes()
    with pytest.raises(ValueError,match='does not match'):
        refresh.update(tmp_path,job['id'],status='ready',message='Wrong source.',groups=groups)
    assert refresh.path(tmp_path).read_bytes()==before
    state=refresh.load(tmp_path);state['jobs'][job['id']].pop('source')
    refresh.path(tmp_path).write_text(json.dumps(state),encoding='utf-8');before=refresh.path(tmp_path).read_bytes()
    assert refresh.load(tmp_path)['jobs'][job['id']].get('source') is None
    assert refresh.reserve(tmp_path,TOKEN)[1] is False
    assert refresh.path(tmp_path).read_bytes()==before


def test_source_choice_is_explicit_idempotent_and_get_does_not_fetch(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path); monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    calls = []
    def capture(**kwargs):
        calls.append('defra'); p=kwargs['output_dir']/'fixture/reference.json';p.parent.mkdir(parents=True);p.write_text('{}')
        return p, document()['groups']
    monkeypatch.setattr(refresh, 'capture_defra', capture)
    monkeypatch.setattr(refresh, 'capture', lambda **kw: pytest.fail('UK choice cannot call Eurostat.'))
    client = TestClient(main.app)
    assert client.get('/explorer/statistics').status_code == 200 and calls == []
    assert not list(tmp_path.rglob('*'))
    assert client.post('/explorer/statistics/check', data={'token': TOKEN, 'source':'unknown'}).status_code == 409
    form = {'token':TOKEN,'source':'defra'}
    page = client.post('/explorer/statistics/check', data=form)
    assert page.status_code == 200 and len(calls) == 1 and 'Defra · original figures' in page.text
    assert 'Provisional estimate' in page.text and 'Published 2026-06-25' in page.text
    assert client.post('/explorer/statistics/check', data=form).status_code == 200 and len(calls) == 1
    assert not refresh.load(tmp_path)['approved']
    assert client.post('/explorer/statistics/check', data={**form,'source':'eurostat'}).status_code == 409


def test_snapshot_pdf_keeps_marketed_definitions_provisional_units_and_source(monkeypatch):
    monkeypatch.setattr('app.services.map_workspace.reference_groups', lambda: deepcopy(document()['groups']))
    texts = []; original = pdf_export.Paragraph
    def paragraph(text, style, **kwargs):
        texts.append(text); return original(text,style,**kwargs)
    monkeypatch.setattr(pdf_export, 'Paragraph', paragraph)
    entity={'id':uk.COUNTRY_ID,'entity_type':'geography','name':'United Kingdom'}
    query=IntelligenceQuery((uk.COUNTRY_ID,),berry_ids=('berry-strawberry',))
    model=snapshot_model(query,[],{uk.COUNTRY_ID:entity},[],BERRIES,['statistics'])
    pdf=pdf_export.render_report_pdf(model['report'],model['packet'],model['coverage'])
    text=' '.join(texts)
    assert pdf.startswith(b'%PDF') and 'Marketed production' in text and 'Marketed yield' in text
    assert 'Provisional estimate' in text and '1000 t' in text and '2025 calendar year' in text
    assert 'Raspberries' not in text and 'Blueberry · Defra' not in text
    assert model['packet']['source_trace'][0]['source_url'].endswith('.ods')
