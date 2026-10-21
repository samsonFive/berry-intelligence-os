"""Selected-profile recall parity without global attribution of unrelated drafts."""
from copy import deepcopy

import pytest

from app.services import draft_attribution as attribution


ENTITIES = {
    'company-green': {'id': 'company-green', 'entity_type': 'company',
                      'name': 'Green Farms S.A.', 'aliases': ['Green Farms']},
    'company-orchard': {'id': 'company-orchard', 'entity_type': 'company',
                       'name': 'Orchard Group', 'aliases': ['Orchard']},
    'variety-emerald': {'id': 'variety-emerald', 'entity_type': 'variety',
                       'name': 'Emerald', 'aliases': ['FL 00-01']},
    'geography-peru': {'id': 'geography-peru', 'entity_type': 'geography', 'name': 'Peru'},
    'person-alex': {'id': 'person-alex', 'entity_type': 'person', 'name': 'Alex Farmer'},
    'program-green': {'id': 'program-green', 'entity_type': 'breeding_program', 'name': 'Green program'},
}
SOURCES = {'source-green': {'label': 'Green Farms Newsroom',
                            'linked_competitor_ids': ['company-green']}}


def historical_membership(record, entity, entities, sources):
    if not entity.get('id'):
        return False
    if entity['id'] in (record.get('entity_ids') or []):
        return True
    result = attribution.attribute_draft(record, entities, sources=sources)
    return (result.get('primary') or {}).get('id') == entity['id'] or any(
        hit.get('id') == entity['id'] and hit.get('location') in {'title', 'source'}
        for hit in result.get('suggested') or [])


@pytest.mark.parametrize('record', [
    {'title': 'Harvest update', 'summary': 'Emerald from Green Farms is grown in Peru.'},
    {'title': 'Emerald launch with Green Farms in Peru'},
    {'headline': 'FL 00-01 production', 'title': 'Orchard agrees new license'},
    {'title': 'Harvest update', 'source_id': 'source-green'},
    {'title': 'Orchard launch', 'publisher': 'Green Farms S.A.'},
    {'title': 'Market outlook', 'source_name': 'Orchard Group newsroom', 'tags': ['market']},
    {'title': 'Alex Farmer joins Green Farms', 'summary': 'Orchard is mentioned.'},
    {'title': 'Trade report', 'entity_ids': ['variety-emerald', 'company-orchard']},
    {'title': 'Emerald launch', '_pending_attribution': {}},
    {'title': 'Trade report', '_pending_attribution': {
        'primary': {'id': 'variety-emerald'}, 'suggested': []}},
    {'title': 'Trade report', '_pending_attribution': {
        'primary': None, 'suggested': [{'id': 'company-green', 'location': 'source'}]}},
    {'title': 'Trade report', 'source_id': 'source-unusual'},
])
def test_selected_matching_preserves_full_attribution_membership(record):
    # Include a non-company linked source: the historical helper permits it.
    sources = {**SOURCES, 'source-unusual': {
        'linked_competitor_ids': ['variety-emerald', 'program-green']}}
    before = deepcopy((record, ENTITIES, sources))
    for entity in ENTITIES.values():
        assert attribution.draft_matches_entity(record, entity, ENTITIES, sources=sources) == \
            historical_membership(record, entity, ENTITIES, sources)
    assert (record, ENTITIES, sources) == before


def test_body_only_and_unrelated_stories_skip_global_attribution(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Unrelated story triggered full catalog attribution')
    monkeypatch.setattr(attribution, 'attribute_draft', forbidden)
    for i in range(100):
        record = {'title': f'Seasonal update {i}', 'summary': 'Emerald and Green Farms are mentioned.'}
        assert not attribution.draft_matches_entity(record, ENTITIES['variety-emerald'], ENTITIES)
        assert not attribution.draft_matches_entity(record, ENTITIES['company-green'], ENTITIES)


def test_possible_matches_keep_authoritative_attribution_and_precomputed_suggestions(monkeypatch):
    calls = []
    original = attribution.attribute_draft
    def counted(*args, **kwargs):
        calls.append(args[0])
        return original(*args, **kwargs)
    monkeypatch.setattr(attribution, 'attribute_draft', counted)
    target = ENTITIES['variety-emerald']
    assert attribution.draft_matches_entity({'title': 'Emerald launch'}, target, ENTITIES)
    assert attribution.draft_matches_entity({'_pending_attribution': {
        'primary': {'id': target['id']}}}, target, ENTITIES)
    assert len(calls) == 2


def test_catalog_and_source_edits_are_visible_without_display_entity_refresh():
    entities, sources = deepcopy(ENTITIES), deepcopy(SOURCES)
    display = deepcopy(entities['variety-emerald'])
    record = {'title': 'Emerald launch'}
    assert attribution.draft_matches_entity(record, display, entities)
    entities[display['id']]['name'] = 'Renamed selection'
    assert not attribution.draft_matches_entity(record, display, entities)
    entities[display['id']]['aliases'].append('Emerald')
    assert attribution.draft_matches_entity(record, display, entities)
    company = entities['company-orchard']
    record = {'title': 'Harvest outlook', 'source_id': 'source-green'}
    assert not attribution.draft_matches_entity(record, company, entities, sources=sources)
    sources['source-green']['linked_competitor_ids'].append(company['id'])
    assert attribution.draft_matches_entity(record, company, entities, sources=sources)
    sources['source-green']['linked_competitor_ids'].remove(company['id'])
    assert not attribution.draft_matches_entity(record, company, entities, sources=sources)


def test_stored_link_remains_recall_even_when_only_body_mentions_entity():
    record = {'title': 'Harvest outlook', 'entity_ids': ['variety-emerald'],
              'article': {'paragraphs': [{'text': 'Emerald trials.'}]}}
    assert attribution.draft_matches_entity(record, ENTITIES['variety-emerald'], ENTITIES)
