"""Production first-page false positives and global berry recall controls."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.services import feed_first_translate, news_local_translation
from tests.test_news_workspace import article, project


@pytest.mark.parametrize(('title', 'summary'), [
    ('Lower carrot yields create a very different market', 'Caroline Louwerse assesses the carrot harvest and disappointing yields.'),
    ('Larger pineapple sizes dominate supply', 'Pineapple supplies from Costa Rica and Ecuador are adequate.'),
    ('Purple Bliss hits the shelves', 'Victoria is the first state to receive these bio-engineered tomatoes.'),
    ('China auto industry offers big export opportunities: BlackBerry CEO', 'The CEO discusses domestic automotive use cases.'),
    ('Trump Administration Moves to Cut SNAP Benefits', 'The Packer reports changes to benefits for 6.3 million people.'),
    ('Amazon launches sustainability tech accelerator', 'Climate technology entrepreneurs will become Amazon business partners.'),
    ('Costa Rica refrigerated cargo through Jacksonville grows', 'Costa Rica containerized imports rose in the fiscal year.'),
    ('Florida researchers test insecticide mesh for citrus greening', 'University of Florida researcher Fernando studies citrus production.'),
    ('Empowering young people in high-tech horticulture', "Rijk Zwaan's entrepreneurship program has launched for horticulture students."),
])
def test_default_news_requires_source_grounded_berry_subject_despite_inferred_links(title, summary):
    row = article(title=title, summary=summary, berry_ids=['berry-blueberry'],
                  entity_ids=['company-grower', 'variety-caroline', 'variety-cargo'])
    before = deepcopy(row)
    result = project([row])
    assert result['matching_ids'] == []
    assert 'berry-industry subject' in result['exclusions'][row['id']]
    assert row == before


@pytest.mark.parametrize(('title', 'summary'), [
    ('Blueberry growers expand nursery production', 'New cultivars will enter commercial production.'),
    ('Strawberry growers report harvest disruption', 'Water restrictions affect planted acreage.'),
    ('Raspberry breeder announces new cultivar', 'Growers will trial the new variety.'),
    ('Blackberry growers expand exports', 'Fruit production and harvest volumes increased.'),
    ('Pesquisa avalia potencial do cultivo de mirtilo no Cerrado', 'Embrapa pesquisa produção e cultivo de mirtilo.'),
    ('Huelva inicia la plantación de fresas', 'La producción de frutos rojos amplía la superficie de cultivo.'),
    ('Carrots and blueberries share irrigation trials', 'Blueberry growers test water management in commercial production.'),
])
def test_direct_global_berry_reporting_survives_without_inferred_crop_tags(title, summary):
    assert project([article(title=title, summary=summary, berry_ids=[], entity_ids=[])])['matching_ids'] == ['ev-news']


def test_latin_script_language_detection_and_cached_english_presentation(tmp_path):
    title = 'Pesquisa avalia potencial do cultivo de mirtilo na região do Cerrado'
    summary = 'A pesquisa brasileira avalia novas áreas de produção e cultivo de mirtilo.'
    assert news_local_translation.language(title + ' ' + summary) == 'pt'
    row = article(title=title, summary=summary)
    before = deepcopy(row)
    translated = feed_first_translate.apply_english_translation(row, inbox_dir=tmp_path,
        translator=lambda *_: {'title': 'Research examines blueberry cultivation in the Cerrado',
                              'summary': 'Brazilian research examines new blueberry growing regions.', 'source_language': 'pt'})
    assert translated['translated'] and translated['original_title'] == title
    assert row == before
    saved = feed_first_translate.cached_translations({row['id']: row}, tmp_path)[row['id']]
    assert saved['title'] == translated['title'] and saved['status'] == row['status']
    assert saved['entity_ids'] == row['entity_ids']
    # Translation is presentation, never a new relevance decision. Even a
    # weak English rendering must not hide a qualifying source-language item.
    saved['title'] = 'Research examines a new growing region'
    saved['summary'] = 'The research examines cultivation in the region.'
    assert project([saved])['matching_ids'] == [row['id']]


def test_regional_metadata_can_use_local_translation_without_remote_calls(tmp_path, monkeypatch):
    row = article(title='蓝莓种植面积增加，育种企业扩大生产', summary='蓝莓企业扩大种植和育种项目。',
        acquisition_lane='regional_google_news')
    def local(*_):
        return {'title': 'Blueberry acreage increases', 'summary': 'Breeders expand blueberry production.', 'source_language': 'zh'}
    monkeypatch.setattr(feed_first_translate, 'perplexity_translator', lambda *_: pytest.fail('Paid translation must not run'))
    translated = feed_first_translate.translate_records([row], inbox_dir=tmp_path, translator=local, local_only=True)
    assert translated[0]['translated'] and translated[0]['source_language'] == 'zh'


def test_credit_free_translation_cannot_call_paid_provider(monkeypatch):
    monkeypatch.setenv('BIOS_RESEARCH_CREDIT_FREE_ONLY', '1')
    assert feed_first_translate.perplexity_translator('Título en español', 'Resumen del cultivo') is None


def test_bpe_word_segments_are_flattened_into_model_vocabulary_tokens():
    tokenizer = object.__new__(news_local_translation._BpeTokenizer)
    tokenizer.normalizer = SimpleNamespace(normalize=lambda value: value)
    tokenizer.tokenizer = SimpleNamespace(tokenize=lambda _: ['cultivo', 'fresas'])
    tokenizer.bpe = SimpleNamespace(segment_tokens=lambda _: ['cul@@ tivo', 'fresas'])
    assert tokenizer.encode('cultivo fresas') == ['cul@@', 'tivo', 'fresas']


def test_translation_cannot_invent_a_berry_subject_for_an_unrelated_source():
    row = article(title='Blueberry nursery expands production', summary='Blueberry growers expand acreage.',
        original_title='Carrot harvest report', original_summary='Caroline discusses carrot yields in commercial production.',
        translated=True)
    assert project([row])['matching_ids'] == []
