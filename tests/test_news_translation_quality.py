from copy import deepcopy
import pytest
from app.services.news_translation_quality import checked_translation,plain_source,quantities
from app.services import feed_first_translate as translations


def result(title,summary='',language='es'):
    return {'title':title,'summary':summary,'source_language':language,'translation_method':'local-argos-ctranslate2'}


@pytest.mark.parametrize('source,english,language',[
    ('صادرات التوت الأزرق تتجاوز 3800 طن','Blueberry exports exceed 300 tons','ar'),
    ('La producción aumenta 25%','Production increases 25','es'),
    ('Exportaciones por $300 millones','Exports worth €300 million','es'),
    ('La producción cae -12%','Production falls 12%','es'),
    ('Inversión de $373.000 millones','Investment of US$373 billion','es'),
])
def test_changed_quantities_currency_or_percent_are_not_presented_as_translation(source,english,language):
    assert checked_translation(source,'',result(english,language=language)) is None


@pytest.mark.parametrize('source,english,language',[
    ('صادرات التوت الأزرق تتجاوز 3800 طن','Blueberry exports exceed 3,800 tons','ar'),
    ('صادرات التوت الأزرق تتجاوز ٣٨٠٠ طن','Blueberry exports exceed 3,800 tons','ar'),
    ('Inversión de $373.000 millones','Investment of $373 billion','es'),
    ('La producción aumenta 2,4%','Production increases 2.4%','es'),
    ('Exportation de 3 800 tonnes','Exports of 3,800 tons','fr'),
    ('蓝莓出口达到3.8万吨','Blueberry exports reach 38,000 tons','zh'),
    ('蓝莓出口增长百分之2.4','Blueberry exports increase 2.4%','zh'),
    ('11月15日にイチゴ10kgを贈呈','10 kg of strawberries will be presented on November 15','ja'),
    ('蓝莓降价50%','Blueberry prices fall 50 per cent','zh'),
    ('Cosecha el 15 de noviembre','Harvest on November 15','es'),
])
def test_equivalent_source_numbers_and_scales_survive(source,english,language):
    assert checked_translation(source,'',result(english,language=language))['title']==english


def test_source_crop_terms_place_names_and_cache_input_are_preserved():
    cached=result('Melilla starts the cranberry harvest in Ñuble')
    before=deepcopy(cached)
    checked=checked_translation('Melipilla inicia la cosecha de arándanos en Ñuble','',cached)
    assert checked['title']=='Melipilla starts the blueberry harvest in Ñuble'
    assert cached==before
    assert checked_translation('Cosecha de arándanos rojos','',result('Cranberry harvest'))['title']=='Cranberry harvest'
    assert checked_translation('Exportations de myrtilles','',result('Cranberry exports',language='fr'))['title']=='blueberry exports'
    assert checked_translation('صادرات التوت الأزرق','',result('Exports of blue tuts',language='ar'))['title']=='Exports of blueberries'
    assert checked_translation('Exportación de arándanos desde La Libertad','',result('Blueberry exports from Freedom')) is None
    assert checked_translation('La libertad para cultivar arándanos','',result('Freedom to grow blueberries'))


def test_declared_publisher_credit_and_html_entities_do_not_corrupt_article_quantities():
    source='Colombia amplía el cultivo de arándanos con $373.000 millones - Hora 13 Noticias'
    summary='Inversión de $373.000 millones&nbsp;&nbsp;Hora 13 Noticias'
    checked=checked_translation(source,summary,result('Colombia expands blueberry cultivation with $373 billion','Investment of $373 billion'),source_name='Hora 13 Noticias')
    assert checked
    assert plain_source(summary,'Hora 13 Noticias')=='Inversión de $373.000 millones'
    assert plain_source('Precios de fresas - producción local','Unrelated')=='Precios de fresas - producción local'
    assert plain_source('Excerpt [& # 8230;]')=='Excerpt […]'
    assert plain_source('Price &lt; $4; yield &gt; 10 tons')=='Price < $4; yield > 10 tons'


def test_bad_cached_translation_reverts_to_original_without_inference_or_cache_rewrite(tmp_path,monkeypatch):
    title='صادرات التوت الأزرق تتجاوز 3800 طن'
    cached=result('Blueberry exports exceed 300 tons',language='ar')
    translations._save_cache(tmp_path,{translations._cache_key(title,''):cached})
    before=translations._load_cache(tmp_path)
    monkeypatch.setattr('app.services.news_local_translation.translate',lambda *a:pytest.fail('GET must not infer'))
    row={'id':'test','title':cached['title'],'summary':'','original_title':title,'original_summary':'','translated':True}
    actual=translations.cached_translations({'test':row},tmp_path)['test']
    assert actual['title']==title and actual['translation_pending'] and not actual['translated']
    assert translations._load_cache(tmp_path)==before


def test_new_local_result_is_checked_before_cache_write(tmp_path):
    source={'id':'test','title':'صادرات التوت الأزرق تتجاوز 3800 طن','summary':''}
    bad=lambda *a:result('Blueberry exports exceed 300 tons',language='ar')
    actual=translations.apply_english_translation(source,translator=bad,inbox_dir=tmp_path,local_only=True)
    assert actual['translation_pending'] and actual['title']==source['title']
    assert not translations._load_cache(tmp_path)


def test_uncertain_arabic_script_is_not_labeled_as_english(monkeypatch):
    from app.services.feed_first import is_analyst_english
    monkeypatch.setattr('app.services.news_local_translation.language',lambda _: 'und')
    assert not is_analyst_english('صادرات التوت الأزرق 3800 طن')
    assert is_analyst_english('Blueberry exports reach 3,800 tons')
