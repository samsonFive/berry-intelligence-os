"""Compatible private context hooks; no source observation becomes a fact."""
from urllib.parse import urlencode

def context_links(records,entity_id=None,berry_id='berry-blueberry',market=None):
    rows=[r for r in records if r['mode']!='fixture' and berry_id in r['analysis'].get('berry_ids',[])]
    if entity_id:rows=[r for r in rows if any(l['entity_id']==entity_id for l in r['analysis'].get('entity_links',[]))]
    if market:rows=[r for r in rows if (r.get('purchase_market') or {}).get('value')==market]
    return [{'id':r['id'],'title':r['text'][:160],'trust_class':'UNREVIEWED SOCIAL OBSERVATION',
             'source_ids':[r['id']],'mode':r['mode'],'date':(r['published_at'] or r['collected_at'])[:10],
             'date_basis':'publication' if r['published_at'] else 'collection',
             'href':'/social?'+urlencode({'mode':r['mode'],'berry':berry_id,'story':r['id']}),
             'does_not_prove':['Verified relationship','National availability','Representative consumer sentiment']} for r in rows[:20]]

def market_context_provider(store):
    """Explicit opt-in provider seam for ResearchScope, excludes fixture/private
    text from automatic model packets. Returns navigation references only.
    """
    def provide(scope):
        rows=context_links(store.records(),berry_id=scope.berry_id or 'berry-blueberry')
        allowed=set(scope.company_ids)|set(scope.variety_ids)
        if allowed:
            ids={r['id'] for r in store.records() if any(l['entity_id'] in allowed for l in r['analysis'].get('entity_links',[]))}
            rows=[r for r in rows if r['id'] in ids]
        return [{**r,'title':'Unreviewed social context; inspect in analyst workspace'} for r in rows]
    return provide
