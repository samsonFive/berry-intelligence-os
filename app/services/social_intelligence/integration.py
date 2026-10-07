"""Compatible private context hooks; no source observation becomes a fact."""
from urllib.parse import urlencode
from .presentation import readable_in_english, display_text, newest_first_key

def context_links(records,entity_id=None,berry_id='all',market=None, *, entity_ids=None):
    rows=[r for r in records if r['mode']!='fixture' and readable_in_english(r) and r['analysis'].get('berry_ids') and (berry_id=='all' or berry_id in r['analysis']['berry_ids'])]
    if entity_id:rows=[r for r in rows if any(l['entity_id']==entity_id for l in r['analysis'].get('entity_links',[]))]
    if entity_ids:rows=[r for r in rows if any(l['entity_id'] in entity_ids for l in r['analysis'].get('entity_links',[]))]
    if market:rows=[r for r in rows if (r.get('purchase_market') or {}).get('value')==market]
    rows.sort(key=newest_first_key,reverse=True)
    return [{'id':r['id'],'title':display_text(r)[:160],'trust_class':'UNREVIEWED SOCIAL OBSERVATION',
             'source_ids':[r['id']],'mode':r['mode'],'date':(r['published_at'] or r['collected_at'])[:10],
             'date_basis':'publication' if r['published_at'] else 'collection',
             'href':'/social?'+urlencode({'mode':r['mode'],'berry':berry_id,'story':r['id']}),
             'does_not_prove':['Verified relationship','National availability','Representative consumer sentiment']} for r in rows[:20]]

def market_context_provider(store):
    """Explicit opt-in provider seam for ResearchScope, excludes fixture/private
    text from automatic model packets. Returns navigation references only.
    """
    def provide(scope):
        allowed=set(scope.company_ids)|set(scope.variety_ids)
        rows=context_links(store.records(),berry_id=scope.berry_id or 'all',entity_ids=allowed)
        return [{**r,'title':'Unreviewed social context; inspect in analyst workspace'} for r in rows]
    return provide
