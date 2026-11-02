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


def test_real_import_resolves_exact_31_real_profiles_without_canonical_mutation():
    payload, varieties = corpus()
    before = deepcopy(varieties)
    notes = validate_notes(payload, varieties)
    assert len(notes) == 31
    assert sum(len(n['details']) for n in notes.values()) == 138
    assert sum(n['status'] == 'demo_excluded' for n in notes.values()) == 0
    assert sum(n['status'] == 'identity_hold' for n in notes.values()) == 4
    for variety in varieties:
        assert profile_source_details('data', variety, varieties=varieties) == notes.get(variety['id'])
    assert varieties == before
    assert all(not v.get('attributes', {}).get('traits') for v in varieties if v['id'] in notes)


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
