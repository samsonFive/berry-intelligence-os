"""Read-only geographic/commodity queries over published evidence.

No title matching, HQ inference, enrichment, or trust promotion. Geography
uses canonical containment. Layer contracts name supporting evidence ids.
"""
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode
from xml.sax.saxutils import escape

from app.services.geography_hierarchy import record_geography_ids, resolve_geography_scope
from app.services.intelligence_feed import present_feed_item

@dataclass(frozen=True)
class IntelligenceQuery:
    geography_ids: tuple[str, ...] = ()
    berry_id: str = ''

    @classmethod
    def parse(cls, countries, berry, entities, berries):
        ids = tuple(dict.fromkeys(x.strip() for x in countries.split(',') if x.strip()))
        for eid in ids:
            if eid not in entities or entities[eid].get('entity_type') != 'geography':
                raise ValueError('Unknown geography selection')
        if berry and berry not in berries:
            raise ValueError('Unknown berry selection')
        return cls(ids, berry)

    def params(self):
        return {'countries': ','.join(self.geography_ids), 'berry': self.berry_id}

    def url(self, path='/explorer'):
        return path + '?' + urlencode(self.params())

    def retrieve(self, records, relationships):
        scope = set()
        for eid in self.geography_ids:
            scope.update(resolve_geography_scope(eid, relationships=relationships).all_ids)
        return sorted((r for r in records if r.get('status') == 'published'
            and 'structural' not in (r.get('tags') or [])
            and (not scope or bool(record_geography_ids(r) & scope))
            and (not self.berry_id or self.berry_id in (r.get('berry_ids') or []))),
            key=lambda r: (r.get('published_date') or '', r.get('id') or ''), reverse=True)

@dataclass(frozen=True)
class GeographicLayerFeature:
    geography_id: str
    evidence_ids: tuple[str, ...]
    properties: dict

class GeographicLayer(Protocol):
    """Future overlays must expose provenance and honor the same query."""
    def features(self, query: IntelligenceQuery) -> list[GeographicLayerFeature]: ...

SECTIONS = {'overview': 'Market overview', 'developments': 'Recent developments',
            'companies': 'Company activity', 'varieties': 'Variety activity'}
GAPS = ['Production volumes and growing-region metrics are not populated by this explorer. '
        'Evidence counts reflect stored coverage, not market size or source independence.']

def explorer_model(query, records, entities, relationships, berries):
    selected = query.retrieve(records, relationships)
    entries = [present_feed_item(r, entities=entities, berry_labels=berries) for r in selected]
    countries = []
    for e in entities.values():
        iso = (e.get('attributes') or {}).get('iso_3166_1_alpha_2')
        if e.get('entity_type') != 'geography' or not iso: continue
        rows = IntelligenceQuery((e['id'],), query.berry_id).retrieve(records, relationships)
        countries.append({'id': e['id'], 'name': e['name'], 'iso': iso,
                          'count': len(rows), 'recent': [{'title': r.get('title') or r['id'],
                          'href': '/intelligence/'+r['id'], 'date': r.get('published_date') or 'Date unknown'} for r in rows[:3]],
                          'berries': sorted({berries[b] for r in rows for b in r.get('berry_ids', []) if b in berries}),
                          'companies': sorted({entities[eid]['name'] for r in rows for eid in r.get('entity_ids', []) if eid in entities and entities[eid].get('entity_type') == 'company'})})
    return {'query': query, 'entries': entries, 'countries': sorted(countries,key=lambda c:c['name']),
            'selected': [entities[eid] for eid in query.geography_ids], 'berries': berries,
            'total': len(entries), 'gaps': GAPS}

def snapshot_model(query, records, entities, relationships, berries, included):
    model = explorer_model(query, records, entities, relationships, berries)
    entries = model['entries']
    sections = []
    for key, title in SECTIONS.items():
        if key not in included: continue
        rows = entries if key in {'overview', 'developments'} else [r for r in entries if any(
            e['entity_type'] == ('company' if key == 'companies' else 'variety') for e in r['entities'])]
        if key == 'overview':
            text = f"{len(entries)} published evidence records match this scope. This is a source inventory, not a verified market conclusion."
        else:
            text = '\n\n'.join(escape(f"[{r['id']}] {r['title']} — {r['source_name']} ({r['date'] or 'date unknown'}). Source: {r['source_url'] or 'URL unavailable'}") for r in rows) or 'No published evidence is available for this section.'
        sections.append({'section_id':key,'title':title,'generated_prose':text,
                         'citation_ids':[r['id'] for r in rows], 'status':'supported' if rows else 'unavailable'})
    scope = {'geography_ids':list(query.geography_ids), 'berry_id':query.berry_id}
    report = {'title':'Market Snapshot — '+(', '.join(e['name'] for e in model['selected']) or 'Global')+' / '+berries.get(query.berry_id,'All Berries'),
              'report_type':'market_snapshot', 'scope':scope, 'sections':sections}
    cited = {eid for s in sections for eid in s['citation_ids']}
    trace = [{'id':r['id'], 'title':escape(r['title']), 'source_name':escape(r['source_name']),
              'date':r['date'], 'source_url':r['source_url'], 'href':r['href']} for r in entries if r['id'] in cited]
    packet = {'recent_developments':entries, 'source_trace':trace}
    coverage = {'counts':{'evidence_count':len(entries)},'gaps':GAPS}
    return model | {'report':report, 'packet':packet, 'coverage':coverage, 'section_options':SECTIONS, 'included':included}
