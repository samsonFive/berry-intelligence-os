"""Stored alternate URLs survive preview and remain reachable without trust claims."""
from copy import deepcopy
from app import main
from app.services import news_workspace
from app.services.publication_sources import source_preview
from app.services.today_relevance import collapse_story_clusters
from tests.test_news_workspace import article,project

PRIMARY='https://freshplaza.com/article/9891520/20-increase-in-strawberry-acreage'
ALTERNATE='https://hortidaily.com/article/9891520/20-increase-in-strawberry-acreage'


def test_original_alternate_url_survives_metadata_preview_and_read_only_news(monkeypatch):
    def forbidden(*a,**k):raise AssertionError('Preview must not acquire or translate sources')
    monkeypatch.setattr('app.services.feed_first_reader.fetch_public_article',forbidden)
    monkeypatch.setattr('app.services.feed_first_reader.capture_item',forbidden)
    monkeypatch.setattr('app.services.news_local_translation.translate',forbidden)
    source=article('live-source-links',source_url=PRIMARY,discovery_urls=[PRIMARY,ALTERNATE],
                   article={'paragraphs':[{'text':'PRIVATE BODY'}]})
    before=deepcopy(source);preview=source_preview(source)
    assert 'article' not in preview and 'PRIVATE BODY' not in str(preview)
    assert preview['discovery_urls']==[PRIMARY,ALTERNATE]
    card=project([preview])['cards'][0]
    assert card['retained_source_links']==[{'url':ALTERNATE,'label':'hortidaily.com','kind':'Publisher link'}]
    assert source==before
    html=main.templates.env.get_template('_news_cards.html').render(cards=[card],tags=[],authoring_mode=False)
    assert f'href="{ALTERNATE}"' in html and 'data-retained-source-links' in html
    assert 'do not establish independent corroboration' in html


def test_refresh_does_not_discard_inherited_source_urls_or_create_duplicates():
    source=article('live-source-links',source_url=PRIMARY,discovery_urls=[PRIMARY,ALTERNATE])
    again=collapse_story_clusters([source])[0]
    assert again['discovery_urls']==[PRIMARY,ALTERNATE]
    third='https://third.example/original'
    result=collapse_story_clusters([again,{**source,'id':'live-third','source_url':third}])[0]
    assert result['discovery_urls']==[PRIMARY,ALTERNATE,third]
    assert collapse_story_clusters([result])[0]['discovery_urls']==result['discovery_urls']


def test_links_skip_primary_tracking_twins_unsafe_urls_and_malformed_values():
    row={'source_url':PRIMARY,'discovery_urls':[PRIMARY+'?utm_source=index',None,{},
        'javascript:alert(1)','data:text/html,unsafe','http://127.0.0.1/a',
        'https://user:secret@publisher.example/article',ALTERNATE,ALTERNATE+'#section']}
    assert [r['url'] for r in news_workspace.retained_source_links(row)]==[ALTERNATE]
    assert news_workspace.retained_source_links({'discovery_urls':'not a list'})==[]


def test_wrappers_are_labeled_unresolved_and_large_lists_are_bounded():
    row={'source_url':PRIMARY,'discovery_urls':['https://news.google.com/rss/articles/opaque']}
    assert news_workspace.retained_source_links(row)[0]['kind']=='Index link · publisher URL unresolved'
    assert len(news_workspace.retained_source_links({'discovery_urls':[f'https://publisher.example/{i}' for i in range(200)]}))==16
