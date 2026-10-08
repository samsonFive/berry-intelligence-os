"""Compatible private context hooks; no source observation becomes a fact."""
from urllib.parse import urlencode
from datetime import datetime, timezone, timedelta
from app.services.geography_hierarchy import resolve_geography_scope
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

def market_context_provider(store, *, entities=(), relationships=(), today=None):
    """Explicit opt-in provider seam for ResearchScope, excludes fixture/private
    text from automatic model packets. Returns navigation references only.
    """
    def provide(scope):
        allowed=set(scope.company_ids)|set(scope.variety_ids)
        records=store.records()
        window=getattr(scope,'window_days',None)
        if window is not None:
            end=today or datetime.now(timezone.utc).date()
            start=end-timedelta(days=max(1,min(int(window),3650)))
            # A recent import of an undated/old post is not recent chatter.
            records=[r for r in records if r.get('published_at') and start<=datetime.fromisoformat(r['published_at'].replace('Z','+00:00')).astimezone(timezone.utc).date()<=end]
        selected=getattr(scope,'geography_ids',())
        if selected:
            geography_entities=entities.values() if isinstance(entities,dict) else entities
            tokens={}
            for entity in geography_entities:
                if entity.get('entity_type')!='geography':continue
                for token in (entity['id'],entity.get('name'),entity.get('attributes',{}).get('iso_3166_1_alpha_2'),*entity.get('aliases',())):
                    if token:tokens.setdefault(token.casefold(),set()).add(entity['id'])
            permitted=set().union(*(resolve_geography_scope(g,relationships=list(relationships)).all_ids for g in selected))
            def in_purchase_market(row):
                market=row.get('purchase_market') or {}
                ids=tokens.get(market.get('value','').casefold(),set())
                return market.get('basis') in ('explicit_text','package_label','analyst') and len(ids)==1 and bool(ids&permitted)
            records=[r for r in records if in_purchase_market(r)]
        rows=context_links(records,berry_id=scope.berry_id or 'all',entity_ids=allowed)
        if window is not None:
            for row in rows:row['href']+='&'+urlencode({'start':start.isoformat(),'end':end.isoformat()})
        return [{**r,'title':'Unreviewed social context; inspect in analyst workspace'} for r in rows]
    return provide
