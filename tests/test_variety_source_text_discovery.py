"""Selected article text yields private identity leads, never trusted records."""
from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from app import main, personal_digest_routes as routes
from app.services import feed_first_reader
from app.services.variety_universe.candidates import load_variety_candidates, persist_variety_candidates
from app.services.variety_universe.corpus_discovery import build_discovered_candidates, discover_corpus_variety_mentions


def source(text, **extra):
    return {'id':'ev-body-check','status':'in_review','source_type':'company_press_release',
        'source_name':'Fictional acceptance publisher','title':'Fictional article-text variety check',
        'source_url':'https://example.test/article?original=1','summary':'The article describes a breeding portfolio.',
        'berry_ids':['berry-blackberry'], 'article':{'paragraphs':[{'text':text,'locator':'p1'}]}, **extra}


def scan(record, **extra):
    return build_discovered_candidates(varieties=[], entities=[], facts=[], published_evidence=[],
        source_text_records=[record], **extra)


def test_default_discovery_does_not_read_article_text_or_unpublished_sources():
    record=source('Blackberry varieties include Glorniwa, Juhas, Maryna and Jagna.',status='published')
    original=deepcopy(record)
    result=discover_corpus_variety_mentions(varieties=[],entities=[],facts=[],published_evidence=[record])
    assert not result['mentions'] and record == original
    # An explicit selected-text check can use an unreviewed publication, with
    # its review state retained rather than masquerading as published.
    record['status']='in_review'
    result=scan(record)
    assert {c['candidate_name'] for c in result['candidates']} == {'Glorniwa','Juhas','Maryna','Jagna'}
    assert all(not c['human_gated'] and not c['auto_confirmed'] for c in result['candidates'])
    assert all(c['knowledge']['source_publication_reviewed'] is False for c in result['candidates'])
    assert all(c['source_url'] == record['source_url'] and c['knowledge']['evidence_ids'] == [record['id']]
        for c in result['candidates'])


@pytest.mark.parametrize('field,name,code',[
    ('Cultivar name: Field Lead (selection code FL11-35)', 'Field Lead', 'FL11-35'),
    ('Cultivar name: Field Lead (selection code FL 95-209a)', 'Field Lead', 'FL 95-209a'),
    ('Cultivar name: Field Lead (“UF52-20”)', 'Field Lead', 'UF52-20'),
    ('Blueberry variety name: “Field Lead”', 'Field Lead', ''),
])
def test_explicit_profile_fields_preserve_whole_names_codes_and_unreviewed_provenance(field,name,code):
    record=source('', article={'title':'Field Lead | blueberry-breeding',
        'paragraphs':[{'text':'General Description'},{'text':field}]}, berry_ids=['berry-raspberry'])
    before=deepcopy(record)
    report=scan(record)
    assert len(report['candidates']) == 1
    candidate=report['candidates'][0]
    assert (candidate['candidate_name'],candidate['berry_id'],candidate['breeder_code']) == (name,'berry-blueberry',code)
    assert candidate['source_url'] == record['source_url']
    assert not candidate['human_gated'] and not candidate['auto_confirmed']
    assert not candidate['aliases'] and not candidate['breeder_owner'] and not candidate['proposed_relationships']
    assert candidate['knowledge']['source_publication_reviewed'] is False
    assert candidate['knowledge']['source_text_basis'] == 'available_article_text'
    assert record == before


def test_profile_fields_use_nearby_crop_headings_without_bleeding_across_sections():
    record=source('Southern Highbush Blueberry Variety\n\nGeneral Description\n\n'
        'Fruit is firm.\n\nCultivar name: Local Blue (selection code FL 123)\n\n'
        'Red Raspberry Variety\n\nCultivar name: Local Red (selection code NR 456)',
        berry_ids=['berry-blackberry'])
    assert {(c['candidate_name'],c['berry_id'],c['breeder_code']) for c in scan(record)['candidates']} == {
        ('Local Blue','berry-blueberry','FL 123'),('Local Red','berry-raspberry','NR 456')}


@pytest.mark.parametrize('text,title',[
    ('Cultivar name: Unscoped Lead (selection code FL 123)','Fictional profile'),
    ('Cultivar name: Unscoped Lead','Blueberry and raspberry profiles'),
    ('Raspberry cultivars are discussed.\n\nCultivar name: Unscoped Lead','Blueberry profile'),
    ('Not cultivar name: Negated Lead','Blueberry profile'),
    ('Cultivar name: Incomplete Lead (selection code FL 123','Blueberry profile'),
    ('Cultivar name: Partial Lead and further text','Blueberry profile'),
    ('Cultivar name: Year Lead (2024)','Blueberry profile'),
    ('Cultivar name: Word Lead (selection code Parent)','Blueberry profile'),
    ('Southern Highbush Blueberry Variety'+('\n\nUnrelated prose.'*5)+'\n\nCultivar name: Distant Lead','Fictional profile'),
])
def test_profile_fields_refuse_ambiguous_stale_incomplete_and_publication_tag_only_scope(text,title):
    record=source('',article={'title':title,'paragraphs':[{'text':text}]},berry_ids=['berry-blueberry'])
    assert not scan(record)['candidates']


def test_generic_blueberry_plant_types_are_not_cultivar_identities():
    record=source('Blueberry cultivars are Rabbiteye. Blueberry varieties include Lowbush and Highbush.')
    assert not scan(record)['candidates']


def test_profile_field_refresh_preserves_an_existing_human_candidate():
    record=source('Blueberry cultivar name: Human Lead (selection code FL 123)')
    candidate=scan(record)['candidates'][0]
    candidate.update(human_gated=True,identity_state='rejected',status='rejected',review_notes='Preserve my decision')
    candidate['knowledge']['notes']='My profile notes'
    original=deepcopy(candidate)
    refreshed=scan(record,existing_candidates=[candidate])
    assert refreshed['candidates'] == []
    assert candidate == original


def test_selected_table_keeps_each_crop_code_and_only_declaration_context():
    text=('The surrounding prose includes Company North and Country South.\n'
          'Crop | Name | Code\nBlack raspberry | Test Megan | NR 1711902\n'
          'Strawberry | Test Beskid | NT 141114\n\nA separate paragraph remains outside the declaration.')
    record=source(text)
    original=deepcopy(record)
    candidates=scan(record)['candidates']
    assert {(c['candidate_name'],c['berry_id'],c['breeder_code']) for c in candidates} == {
        ('Test Megan','berry-raspberry','NR 1711902'),('Test Beskid','berry-strawberry','NT 141114')}
    assert all('surrounding prose' not in c['knowledge']['mention_context'] for c in candidates)
    assert record == original


def test_full_text_is_supported_without_changing_the_default_reader_projection():
    from app.services.source_body import article_full_text
    text = 'Crop | Name | Code\nBlackberry | Table Lead | BB 101\n'
    record = source('', article={'full_text': text})
    assert '\n' not in article_full_text(record)
    assert article_full_text(record, preserve_line_breaks=True) == text.strip()
    assert scan(record)['candidates'][0]['candidate_name'] == 'Table Lead'


def test_ambiguous_crop_and_non_declarations_do_not_create_identities():
    record = source('Varieties include Possible Name. Company North has farms in Country South.',
                    berry_ids=['berry-blackberry', 'berry-blueberry'])
    assert not scan(record)['candidates']


@pytest.mark.parametrize('record,reason',[
    (source('',body='Blackberry varieties include Hidden Name.'),'source_text_unavailable'),
    (source('Verify you are a human. Blackberry varieties include Bot Name.'),'source_text_unavailable'),
    (source('x'*200_001+' Blackberry varieties include Truncated Name.'),'source_text_too_large'),
])
def test_unreadable_access_screen_and_oversized_source_do_not_invent_names(record,reason):
    result=scan(record)
    assert not result['candidates']
    assert reason in {r['reason'] for r in result['exclusions']}


def setup_routes(monkeypatch,tmp_path,record):
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    monkeypatch.setattr(main,'published_evidence',lambda:[])
    monkeypatch.setattr(main,'all_facts',lambda:[])
    monkeypatch.setattr(main,'all_entities',lambda:[])
    monkeypatch.setattr(routes,'world',lambda:(main,{'state':{'decisions':{}}},{record['id']:record},{}))
    def no_capture(*args,**kwargs):
        raise AssertionError('name discovery must never acquire or refresh a source')
    monkeypatch.setattr(feed_first_reader,'capture_item',no_capture)
    return TestClient(main.app)


def test_action_adds_only_new_private_candidates_and_replay_preserves_human_notes(monkeypatch,tmp_path):
    record=source('Blackberry varieties include New Lead and Human Lead.')
    client=setup_routes(monkeypatch,tmp_path,record)
    existing=scan(source('Blackberry varieties include Human Lead.'))['candidates'][0]
    existing.update(status='rejected',identity_state='rejected',human_gated=True,
        reviewer='Human',review_notes='Keep this rejection')
    existing['knowledge'].update(notes='My saved notes',evidence_ids=['ev-old-source'])
    path=persist_variety_candidates([existing],inbox_dir=tmp_path)[0]
    original=path.read_bytes()
    response=client.post('/varieties/discover-source/ev-body-check',follow_redirects=False)
    assert response.status_code == 303
    result=client.get(response.headers['location'])
    assert result.status_code == 200 and '2 explicitly named varieties' in result.text and 'New Lead' in result.text
    assert 'Unreviewed source; the variety identity still needs review.' in result.text
    assert '/intelligence/ev-body-check?personal=1' in result.text
    from html import unescape
    import re
    assert 'name="discovery" value="source-text"' in result.text
    alphabet_link = unescape(re.search(
        r'aria-label="Candidate alphabetical navigation"><a href="([^"]+)"', result.text).group(1))
    assert 'discovery=source-text' in alphabet_link
    assert 'Keep this rejection' in client.get(alphabet_link.split('#')[0] + '&status=rejected').text
    rejected=client.get(response.headers['location']+'&status=rejected')
    assert rejected.status_code == 200 and 'Keep this rejection' in rejected.text
    assert path.read_bytes() == original
    candidates=load_variety_candidates(tmp_path)
    assert len(candidates) == 2 and all(c['id'] != record['id'] for c in candidates)
    snapshot={p:p.read_bytes() for p in tmp_path.rglob('*.json')}
    replay=client.post('/varieties/discover-source/ev-body-check',follow_redirects=False)
    assert replay.status_code == 303
    assert {p:p.read_bytes() for p in tmp_path.rglob('*.json')} == snapshot
    assert record['status'] == 'in_review'


def test_catalog_match_and_selected_get_are_read_only(monkeypatch,tmp_path):
    record=source('Blackberry varieties include Known Variety and New Lead.')
    client=setup_routes(monkeypatch,tmp_path,record)
    monkeypatch.setattr(main,'all_entities',lambda:[{'id':'variety-known','entity_type':'variety',
        'name':'Known Variety','berry_ids':['berry-blackberry']}])
    url='/varieties/candidates?source=ev-body-check&discovery=source-text'
    response=client.get(url)
    assert response.status_code == 200 and '/entities/variety/variety-known' in response.text
    assert 'New Lead' in response.text and not list(tmp_path.rglob('*.json'))
    assert client.post('/varieties/discover-source/ev-body-check',follow_redirects=False).status_code == 303
    assert [c['candidate_name'] for c in load_variety_candidates(tmp_path)] == ['New Lead']


def test_cached_article_is_selected_by_id_and_original_url(monkeypatch,tmp_path):
    record=source('')
    client=setup_routes(monkeypatch,tmp_path,record)
    capture={'ok':True,'requested_url':record['source_url'],
        'passages':['Blackberry varieties include Captured Lead.'],'availability':'excerpt_only'}
    feed_first_reader.save_capture(tmp_path,record['id'],capture)
    selected=[]
    original_loader=feed_first_reader.load_capture
    def load(inbox,item_id):
        selected.append(item_id)
        return original_loader(inbox,item_id)
    monkeypatch.setattr(feed_first_reader,'load_capture',load)
    assert client.post('/varieties/discover-source/ev-body-check',follow_redirects=False).status_code == 303
    assert selected == ['ev-body-check']
    assert load_variety_candidates(tmp_path)[0]['candidate_name'] == 'Captured Lead'
    capture['requested_url']='https://example.test/other-source'
    feed_first_reader.save_capture(tmp_path,record['id'],capture)
    assert client.post('/varieties/discover-source/ev-body-check',follow_redirects=False).status_code == 422


def test_write_action_rejects_public_cross_site_unknown_and_missing_body(monkeypatch,tmp_path):
    client=setup_routes(monkeypatch,tmp_path,source(''))
    endpoint='/varieties/discover-source/ev-body-check'
    assert client.get(endpoint).status_code == 405
    assert client.post(endpoint,headers={'origin':'https://other.test'}).status_code == 403
    assert client.post(endpoint,headers={'sec-fetch-site':'cross-site'}).status_code == 403
    assert client.post('/varieties/discover-source/unknown').status_code == 404
    assert client.post(endpoint).status_code == 422
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    assert client.post(endpoint).status_code == 403
    assert not list(tmp_path.rglob('*.json'))


def test_selected_quoted_lists_find_all_crops_without_borrowing_publication_tags():
    # Synthetic prose uses the grammatical forms read on the original Hortifrut
    # page, with expectations fixed before the parser change. It is not a Gold
    # qualification case or copied full publication body.
    blueberries = ['Prelude', 'Daybreak', 'Stellar', 'Candycrunch', 'Apolo', 'Bliss',
                   'Temptation', 'Robust', 'Envy', 'Keepsake', 'Sensation']
    raspberries = ['Pacific Deluxe', 'Pacific Royale', 'Pacific Majesty',
                  'Pacific Scarlet', 'Pacific Gema']
    quoted = lambda names: ', '.join('‘' + name + '’' for name in names[:-1]) + ', and ‘' + names[-1] + '’'
    text = (
        "In blueberries, we have the exclusive license for the best varieties: "
        "‘Rocio’ and ‘Corona’ from Program One for America, and ‘Draper’, ‘Aurora’, "
        "‘Liberty’, and ‘Osorno’ from University Two.\n\n"
        "Our blackberry program tests fruit quality. ‘Camila’ and ‘Amara’ are the first two varieties in this group.\n\n"
        + quoted(blueberries) + " are the first varieties by Program Three. These are blueberries.\n\n"
        + quoted(raspberries) + " are some of the Program Four raspberry varieties."
    )
    record = source(text, berry_ids=['berry-blueberry'])
    before = deepcopy(record)
    result = scan(record)
    expected = {(n, 'berry-blueberry') for n in blueberries + ['Rocio', 'Corona', 'Draper', 'Aurora', 'Liberty', 'Osorno']}
    expected |= {(n, 'berry-raspberry') for n in raspberries}
    expected |= {('Camila', 'berry-blackberry'), ('Amara', 'berry-blackberry')}
    assert {(c['candidate_name'], c['berry_id']) for c in result['candidates']} == expected
    assert len(result['candidates']) == 24
    assert all(not c['aliases'] and not c['proposed_relationships']
               and not c['human_gated'] and not c['auto_confirmed'] for c in result['candidates'])
    assert all(c['knowledge']['source_publication_reviewed'] is False
               and c['knowledge']['source_text_basis'] == 'available_article_text'
               and c['source_url'] == record['source_url'] for c in result['candidates'])
    assert record == before


def test_explicit_reverse_crop_wins_and_one_paragraph_cannot_label_another():
    record = source(
        "‘Red Lead’ are some of the Example Company raspberry varieties. Blueberries are also discussed.\n\n"
        "‘Unknown Lead’ are the first varieties by Example Company.",
        berry_ids=['berry-blueberry'])
    result = scan(record)
    assert {(c['candidate_name'], c['berry_id']) for c in result['candidates']} == {('Red Lead', 'berry-raspberry')}
    assert any(e['reason'] == 'berry_not_established' for e in result['exclusions'])


@pytest.mark.parametrize('text', [
    "Blueberries and blackberries: ‘Ambiguous Lead’ are the first varieties.",
    "The blueberry brand is ‘Brand North’. The quality claim is ‘Sweet Fruit’.",
    "‘Company North’ and ‘Company South’ are partners in a blueberry program.",
    "‘Parent North’ and ‘Parent South’ are not blueberry varieties.",
    "We have no license for the best varieties: ‘Negative Lead’ from Program One. These are blueberries.",
    "‘Incomplete Name’ and Another Name are the first blueberry varieties.",
])
def test_selected_quote_prose_and_negative_or_incomplete_lists_are_not_identities(text):
    result = scan(source(text, berry_ids=[]))
    assert not result['candidates']


def test_long_reverse_lists_are_refused_whole_instead_of_returning_a_suffix():
    from app.services.variety_universe.explicit_article_formats import explicit_article_formats
    from app.services.variety_universe.corpus_discovery import _NAMED_TOKEN
    text = ', '.join('‘Lead' + str(i) + '’' for i in range(65)) + ' are the first blueberry varieties.'
    leads, _ = explicit_article_formats(text, name_token=_NAMED_TOKEN)
    assert leads == []


def test_paragraph_crop_scope_also_protects_existing_forward_and_license_lists():
    record = source(
        'Our raspberries have varieties including Local Red and Local Gold.\n\n'
        'Our blackberry program licenses ‘Local Black’ from Example Program. Blackberry varieties are discussed.',
        berry_ids=['berry-blueberry'])
    assert {(c['candidate_name'], c['berry_id']) for c in scan(record)['candidates']} == {
        ('Local Red', 'berry-raspberry'), ('Local Gold', 'berry-raspberry'), ('Local Black', 'berry-blackberry')}
