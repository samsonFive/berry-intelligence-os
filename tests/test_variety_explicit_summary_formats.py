"""Scope, ambiguity and human decisions matter more than a recall headline."""
from copy import deepcopy

import pytest

from app.services.variety_universe.corpus_discovery import (
    build_discovered_candidates, discover_corpus_variety_mentions, merge_visible_candidates,
)


def record(summary, **extra):
    return {"id": "ev-format-test", "status": "published", "summary": summary,
            "source_type": "company_press_release", "source_url": "https://example.test/list?crop=all&v=2",
            "berry_ids": ["berry-blueberry"], **extra}


def discover(summary, **extra):
    return discover_corpus_variety_mentions(varieties=[], entities=[], facts=[],
                                           published_evidence=[record(summary, **extra)])


def test_reordered_markdown_table_keeps_whole_names_codes_and_each_rows_crop():
    source = record("| Code | Cultivar | Crop |\n| --- | :--- | ---: |\n"
        "| NR 1711902 | Megan | Black raspberry |\n| NT 141114 | Beskid | Strawberry |\n"
        "| BB05-251MI-14 | Keepsake | Blueberry |\n| | Summer Breeze Cherry Blossom F1 | Strawberry |")
    before = deepcopy(source)
    result = discover_corpus_variety_mentions(varieties=[], entities=[], facts=[], published_evidence=[source])
    assert source == before
    names = {m['candidate_name']: m for m in result['mentions']}
    assert names['Megan']['berry_id'] == 'berry-raspberry'
    assert names['Megan']['breeder_code'] == 'NR 1711902'
    assert names['Beskid']['berry_id'] == 'berry-strawberry'
    assert names['Keepsake']['breeder_code'] == 'BB05-251MI-14'
    assert names['Summer Breeze Cherry Blossom F1']['berry_id'] == 'berry-strawberry'
    assert all(m['source_url'] == source['source_url'] and m['evidence_ids'] == [source['id']]
               and m['source_tier'] != 'tier_1_registry' for m in names.values())


def test_bad_table_rows_are_visible_exclusions_and_cannot_borrow_publication_crop():
    result = discover('Crop | Name | Code\nBlack raspberry | Valid | NR 123\n'
        'Berry | Wrong Crop | NR 124\nBlackberry | Wrong Code | active rights\n'
        'Strawberry | One Two Three Four Five Six Seven Eight Nine | NT 125\n'
        'Raspberry | Incomplete\n\nStrawberry | After Table | NT 126')
    assert [m['candidate_name'] for m in result['mentions']] == ['Valid']
    assert result['mentions'][0]['berry_id'] == 'berry-raspberry'
    assert {r['reason'] for r in result['exclusions']} == {
        'berry_not_established', 'table_code_format_unresolved', 'table_name_format_unresolved',
        'table_row_shape_unresolved'}
    assert all(r['record_id'] == 'ev-format-test' for r in result['exclusions'])


@pytest.mark.parametrize('summary', [
    'Country | Name | Code\nSpain | Strawberry Company | NR 123',
    'Name | Code\nBaron | NR 1849002',
    'Crop | Name | Name\nRaspberry | Baron | Baron',
    'Blueberry | Prelude | BB001',
    'Variedades de mora: Nombre Ambiguo.',  # mora may describe another crop
    'Odmiany: Bez Uprawy.',
    'No variedades de arándano: Nombre Falso.',
    'Nie odmiany maliny: Fałszywa Nazwa.',
    'Odmiany maliny: nowa odmiana łączy te cechy.',
    'Odmiany maliny: "Unclosed Name.',
    'Variedades de fresa: Unclosed Name".',
])
def test_unsupported_or_negated_formats_do_not_invent_names(summary):
    assert discover(summary)['mentions'] == []


def test_translated_lists_preserve_accents_and_explicit_crop_overrides_tags():
    result = discover('Variedades de frutilla: "Fresa Nueva", Élite y Ámbar.\n'
                      'Odmiany jeżyny: Łąkowa, Świt oraz Żar.')
    pairs = {(m['candidate_name'], m['berry_id']) for m in result['mentions']}
    assert pairs == {(n, 'berry-strawberry') for n in ['Fresa Nueva', 'Élite', 'Ámbar']} | {
        (n, 'berry-blackberry') for n in ['Łąkowa', 'Świt', 'Żar']}
    assert all(m['mention_kind'] == 'explicit_summary_translated_list' for m in result['mentions'])


def test_table_same_label_on_two_crops_stays_two_unreviewed_identity_leads():
    result = discover('Crop | Name\nBlueberry | Keepsake\nStrawberry | Keepsake')
    assert {(m['candidate_name'], m['berry_id']) for m in result['mentions']} == {
        ('Keepsake', 'berry-blueberry'), ('Keepsake', 'berry-strawberry')}
    assert all(m.get('canonical_variety_id') is None for m in result['mentions'])


def test_formats_never_scan_article_body_or_unpublished_drafts():
    body = 'Crop | Name\nBlueberry | Body Only\nOdmiany maliny: Secret Name.'
    assert discover('No names in summary.', body=body)['mentions'] == []
    assert discover(body, status='in_review')['mentions'] == []


def test_replayed_translated_discovery_preserves_human_rejection():
    existing = {'id': 'vcand-keep-human', 'candidate_name': 'Świt', 'berry_id': 'berry-blackberry',
        'status': 'rejected', 'identity_state': 'rejected', 'human_gated': True,
        'reviewer': 'Human', 'review_notes': 'Keep this decision', 'knowledge': {'notes': 'My notes'}}
    before = deepcopy(existing)
    report = build_discovered_candidates(varieties=[], entities=[], facts=[],
        published_evidence=[record('Odmiany jeżyny: Świt.')], existing_candidates=[existing])
    rows = merge_visible_candidates([existing], report['candidates'], report=report)
    kept = next(r for r in rows if r['id'] == existing['id'])
    assert existing == before
    assert kept['status'] == 'rejected' and kept['review_notes'] == before['review_notes']
    assert kept['knowledge'] == before['knowledge'] and kept['human_gated']
    assert kept['corpus_evidence_ids'] == ['ev-format-test']


def test_all_caps_declaration_does_not_relax_case_sensitive_name_boundaries():
    result = discover('VARIEDADES DE ARÁNDANO: Uno, Dos y Tres.\n'
                      'ODMIANY MALINY: Łuna i Żar.\nOdmiany maliny: ącki małe litery.')
    assert {m['candidate_name'] for m in result['mentions']} == {'Uno', 'Dos', 'Tres', 'Łuna', 'Żar'}


def test_mismatched_table_quotes_stay_unresolved_instead_of_shortened_names():
    result = discover('Crop | Name\nStrawberry | "Wrong Quote\nRaspberry | \'Mismatched"')
    assert result['mentions'] == []
    assert all(r['reason'] == 'table_name_format_unresolved' for r in result['exclusions'])


def test_next_unsupported_table_cannot_inherit_previous_crop_columns():
    result = discover('Crop | Name | Code\nBlueberry | Valid | BB001\n'
                      'Crop | Name | Region\nStrawberry | Wrong Table | NT123')
    assert [m['candidate_name'] for m in result['mentions']] == ['Valid']
    assert result['exclusions'][0]['reason'] == 'table_heading_format_unresolved'


def test_live_candidate_handoff_keeps_crop_code_source_and_authoring_boundary(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app import main

    source = record('Crop | Name | Code\nBlack raspberry | Test Megan | NR 1711902\n'
                    'Strawberry | Test Beskid | NT 141114',
                    title='Fictional formatted-source acceptance check', source_name='Fixture publisher')
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    monkeypatch.setattr(main, 'published_evidence', lambda: [source])
    client = TestClient(main.app)
    page = client.get('/varieties/candidates?q=Test+Megan&berry=berry-raspberry')
    assert page.status_code == 200 and 'Test Megan' in page.text and 'NR 1711902' in page.text
    assert 'Test Beskid' not in page.text
    assert 'ev-format-test' in page.text and 'Fixture publisher' in page.text
    assert not list(tmp_path.rglob('*'))
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    assert client.get('/varieties/candidates?q=Test+Megan').status_code == 403
