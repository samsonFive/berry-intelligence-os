"""Source notes stay attributed, scoped and outside trusted/static profiles."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

from app.services.variety_profile_sources import IMPORT_PATH, profile_source_details, validate_notes


def corpus():
    payload = json.loads((Path('data') / IMPORT_PATH).read_text(encoding='utf-8'))
    varieties = [json.loads(p.read_text(encoding='utf-8')) for p in Path('data/entities/varieties').glob('*.json')]
    return payload, varieties


def test_real_import_resolves_real_profiles_without_canonical_mutation():
    payload, varieties = corpus()
    before = deepcopy(varieties)
    notes = validate_notes(payload, varieties)
    assert len(notes) == 54
    assert sum(len(n['details']) for n in notes.values()) == 198
    assert sum(n['status'] == 'demo_excluded' for n in notes.values()) == 0
    assert sum(n['status'] == 'identity_hold' for n in notes.values()) == 4
    for variety in varieties:
        assert profile_source_details('data', variety, varieties=varieties) == notes.get(variety['id'])
    assert varieties == before


@pytest.mark.parametrize('damage', ['duplicate', 'foreign', 'crop', 'trusted', 'citation', 'javascript', 'credentials', 'demo', 'empty_context'])
def test_invalid_scope_citations_and_trust_are_rejected(damage):
    payload, varieties = corpus()
    n = payload['profiles'][0]
    if damage == 'duplicate': payload['profiles'].append(deepcopy(n))
    if damage == 'foreign': n['variety_id'] = 'variety-not-real'
    if damage == 'crop': n['berry_ids'] = ['berry-blackberry']
    if damage == 'trusted': payload['review_status'] = 'approved'
    if damage == 'citation': n['details'][0]['source_id'] = 'missing'
    if damage == 'javascript': n['sources']['1']['url'] = 'javascript:alert(1)'
    if damage == 'credentials': n['sources']['1']['url'] = 'https://secret@example.org/'
    if damage == 'demo': n['status'] = 'demo_excluded'
    if damage == 'empty_context': n['details'][0]['context'] = ''
    with pytest.raises(ValueError): validate_notes(payload, varieties)


def test_specific_numbers_and_cultivar_boundaries():
    payload, varieties = corpus()
    notes = validate_notes(payload, varieties)
    values = lambda slug: ' '.join(r['value'] for r in notes['variety-'+slug]['details'])
    assert '6–7 g' in values('zawadi')
    assert '28 g' in values('melissa') and '27 g' in values('marimbella')
    assert 'Medium' in values('melissa')
    assert '60' not in values('sekoya-crunch')
    assert 'firm' not in values('arana').lower()  # Eterna's adjacent card
    assert 'Beatrice' not in values('zara')
    assert all('25358' not in s['url'] for s in notes['variety-bonita']['sources'].values())
    assert 'platform' in values('bk-6-13')


def test_recovered_primary_details_keep_identity_and_measurement_limits():
    payload, varieties = corpus()
    notes = validate_notes(payload, varieties)
    for slug in ['twilight', 'victoria', 'zara', 'bk-6-13']:
        note = notes['variety-'+slug]
        assert note['status'] == 'identity_hold'
        assert note['checked_on'] == '2026-11-03'
    twilight = notes['variety-twilight']
    assert 'units' in twilight['limitations'].lower()
    assert 'blackberry' in twilight['limitations'].lower()  # explicitly excluded crop homonym
    zara = notes['variety-zara']
    assert any('mid-season' in row['value'] and 'very late' in row['context'] for row in zara['details'])
    assert 'not approved' in zara['limitations'] or 'unreviewed' in zara['limitations']
    patent = notes['variety-bk-6-13']
    assert any('bridge' in row['context'] and 'not established' in row['context'] for row in patent['details'])
    assert all(not v.get('attributes', {}).get('traits') for v in varieties
               if v['id'] in {'variety-twilight', 'variety-victoria', 'variety-zara', 'variety-bk-6-13'})


def test_primary_expansion_keeps_records_conditions_and_disagreements_scoped():
    payload, varieties = corpus()
    notes = validate_notes(payload, varieties)
    eterna = notes['variety-eterna']
    record = next(row for row in eterna['details'] if row['field'] == 'Award / record mention')
    assert '20.40 g' in record['value']
    assert 'not a cultivar mean' in record['context']
    assert '13 November 2023' in record['context']
    assert 'Germany' in str(notes['variety-glen-carron-7446efde']['details'])
    assert 'powdery mildew' in str(notes['variety-malling-ace-2a2662f7']['details'])
    manifest = json.loads(Path('data/imports/variety-catalog-admission-2026-11-03/manifest.json').read_text(encoding='utf8'))
    assert len(manifest['created']) == 7
    for row in manifest['created']:
        variety = next(v for v in varieties if v['id'] == row['variety_id'])
        assert variety['status'] == 'unverified' and variety['aliases'] == []
        assert not variety['evidence_ids'] and not variety['relationship_ids']
        assert not variety.get('attributes', {}).get('traits')
        if 'Caddo' in row['name'] or 'Freedom' in row['name']:
            note = notes[variety['id']]
            assert len(note['sources']) == 2
            assert any(r['field'] == 'Release-date discrepancy' for r in note['details'])


def test_private_template_escapes_values_and_preserves_conditions_and_citations():
    payload, varieties = corpus()
    notes = validate_notes(payload, varieties)['variety-melissa']
    env = Environment(loader=FileSystemLoader('app/templates'), autoescape=True)
    env.filters['us_date'] = str
    template = env.get_template('_variety_profile_sources.html')
    for authoring, static in [(False, False), (False, True), (True, True)]:
        assert not template.render(authoring_mode=authoring, static_build=static, variety_profile_sources=notes).strip()
    notes['details'][0]['value'] = '<script>unsafe</script>'
    rendered = template.render(authoring_mode=True, static_build=False, variety_profile_sources=notes)
    assert '&lt;script&gt;unsafe&lt;/script&gt;' in rendered and '<script>unsafe' not in rendered
    assert 'Pending review' in rendered and '28 g' in rendered
    assert 'PDF page 1' in rendered and '2026 English breeder sheet' in rendered
    assert 'href="https://www.novasirigenetics.com/' in rendered


def test_absent_import_does_not_fetch_or_write(tmp_path):
    assert profile_source_details(tmp_path, {'id': 'variety-unknown'}, varieties=[]) is None
    assert list(tmp_path.iterdir()) == []
