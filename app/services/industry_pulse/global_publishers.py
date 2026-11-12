"""Global publisher metadata routes; no Source approval or article-body access."""
from urllib.parse import quote_plus

ENGLISH = 'blueberry OR blueberries OR strawberry OR strawberries OR raspberry OR raspberries OR blackberry OR blackberries OR "berry growers"'
SPANISH = 'arándano OR arándanos OR fresa OR fresas OR frutilla OR frutillas OR frambuesa OR frambuesas OR zarzamora OR zarzamoras'
FRENCH = 'myrtille OR myrtilles OR bleuet OR bleuets OR fraise OR fraises OR framboise OR framboises OR mûre OR mûres OR "petits fruits"'
ARABIC = 'الفراولة OR الفريز OR "التوت الأزرق" OR "توت العليق" OR "التوت الأسود"'
GERMAN = 'Heidelbeere OR Heidelbeeren OR Erdbeere OR Erdbeeren OR Himbeere OR Himbeeren OR Brombeere OR Brombeeren'

# Public-feed transport and publication dates checked November 11, 2026.
# General feeds complement seven-day crop searches: no-hit checks are not recall.
DIRECT = (
 ('nyt','The New York Times','nytimes.com','global','en-US','US','en','https://rss.nytimes.com/services/xml/rss/nyt/Business.xml'),
 ('diario-huelva','Diario de Huelva','diariodehuelva.es','europe','es-ES','ES','es','https://www.diariodehuelva.es/rss/'),
 ('huelva-hoy','Huelva Hoy','huelvahoy.com','europe','es-ES','ES','es','https://www.huelvahoy.com/rss/'),
 ('la-discusion','La Discusión','ladiscusion.cl','americas','es-419','CL','es','https://ladiscusion.cl/tag/arandanos/feed/'),
 ('la-republica','La República','larepublica.pe','americas','es-419','PE','es','https://larepublica.pe/rss/economia.xml'),
 ('la-terre','La Terre de chez nous','laterre.ca','americas','fr-CA','CA','fr','https://www.laterre.ca/feed/'),
 ('cbc-bc','CBC British Columbia','cbc.ca','americas','en-CA','CA','en','https://www.cbc.ca/webfeed/rss/rss-canada-britishcolumbia'),
 ('bbc-business','BBC News','bbc.co.uk','global','en-GB','GB','en','https://feeds.bbci.co.uk/news/business/rss.xml'),
 ('bbc-kent','BBC Kent','bbc.co.uk','europe','en-GB','GB','en','https://feeds.bbci.co.uk/news/england/kent/rss.xml'),
 ('agrarheute','agrarheute','agrarheute.com','europe','de-DE','DE','de','https://www.agrarheute.com/news.xml'),
 ('canada-food-en','Canadian Food Inspection Agency','recalls-rappels.canada.ca','americas','en-CA','CA','en','https://recalls-rappels.canada.ca/en/feed/cfia-alerts-recalls'),
 ('canada-food-fr','Agence canadienne d’inspection des aliments','recalls-rappels.canada.ca','americas','fr-CA','CA','fr','https://recalls-rappels.canada.ca/fr/fil-de-nouvelles/acia-rappels-avis-securite'),
 ('serbia-stips','Serbia STIPS agriculture market information','stips.minpolj.gov.rs','europe','sr-RS','RS','sr','https://www.stips.minpolj.gov.rs/srl/taxonomy/term/6/feed'),
 ('france-food','France RappelConso','rappel.conso.gouv.fr','europe','fr-FR','FR','fr','https://rappel.conso.gouv.fr/rss?categorie=01'),
)

INDEXED = (
 ('reuters','Reuters','reuters.com','global','en-US','US','en',ENGLISH),
 ('ap','Associated Press','apnews.com','global','en-US','US','en',ENGLISH),
 ('bbc','BBC News','bbc.com','global','en-GB','GB','en',ENGLISH),
 ('guardian','The Guardian','theguardian.com','global','en-GB','GB','en',ENGLISH),
 ('diario-huelva','Diario de Huelva','diariodehuelva.es','europe','es-ES','ES','es',SPANISH),
 ('huelva-hoy','Huelva Hoy','huelvahoy.com','europe','es-ES','ES','es',SPANISH),
 ('hespress-ar','Hespress','hespress.com','africa','ar','MA','ar',ARABIC),
 ('hespress-fr','Hespress Français','fr.hespress.com','africa','fr-FR','MA','fr',FRENCH),
 ('la-discusion','La Discusión','ladiscusion.cl','americas','es-419','CL','es',SPANISH),
 ('la-republica','La República','larepublica.pe','americas','es-419','PE','es',SPANISH),
 ('la-terre','La Terre de chez nous','laterre.ca','americas','fr-CA','CA','fr',FRENCH),
 ('cbc','CBC','cbc.ca','americas','en-CA','CA','en',ENGLISH),
 ('agrarheute','agrarheute','agrarheute.com','europe','de-DE','DE','de',GERMAN),
 ('agronegocios','Agronegocios','agronegocios.co','americas','es-419','CO','es',SPANISH),
 ('rnz','RNZ','rnz.co.nz','apac','en-NZ','NZ','en',ENGLISH),
 ('times-india','The Times of India','timesofindia.indiatimes.com','apac','en-IN','IN','en',ENGLISH),
)


def expanded_publisher_feeds():
    rows=[]
    for route,definitions in (('direct_rss',DIRECT),('indexed',INDEXED)):
        for key,label,host,geo,hl,gl,language,target in definitions:
            if route=='indexed':
                domains='(site:bbc.com OR site:bbc.co.uk)' if key=='bbc' else f'site:{host}'
                target=f'https://news.google.com/rss/search?q={quote_plus(f"{domains} ({target}) when:7d")}&hl={hl}&gl={gl}&ceid={gl}:{language}'
            rows.append(dict(id=f'feed:priority:{key}:{"rss" if route=="direct_rss" else "indexed"}',
                label=label,host=host,geography=geo,hl=hl,gl=gl,ceid=f'{gl}:{language}',
                adapter='article_rss' if route=='direct_rss' else 'news_search_rss',route=route,
                source_type='government_document' if key.startswith('canada-food-') or key in {'serbia-stips','france-food'} else 'trade_press' if key in {'la-terre','agrarheute','agronegocios'} else 'news_search',feed_url=target))
            if key in {'hespress-ar','hespress-fr','rnz'}:
                rows[-1]['access_note']='Direct feed blocked during verification; indexed metadata only. No access bypass.'
            if key == 'serbia-stips':
                rows[-1]['access_note']='Latest ten Agroinfo entries include attributed reporting; ministry hosting does not establish that every claim is a primary administrative record. Serbian original retained when no local translation model is available.'
            if key == 'france-food':
                rows[-1]['access_note']='Official food-category RSS, latest 20 notices. Shallow window; earlier notices require archive review. French mûre alone is ambiguous and does not assign blackberry.'
    from app.services.industry_pulse.public_record_feeds import FSA_FEED
    rows.append(dict(FSA_FEED))
    return rows
