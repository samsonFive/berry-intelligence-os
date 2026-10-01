"""Read-only geographic/commodity queries over published evidence.

No title matching, HQ inference, enrichment, or trust promotion. Geography
uses canonical containment. Layer contracts name supporting evidence ids.
"""
import json
from functools import lru_cache
from pathlib import Path

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode
from xml.sax.saxutils import escape

from app.services.geography_hierarchy import record_geography_ids, resolve_geography_scope
from app.services.intelligence_feed import present_feed_item

@lru_cache(maxsize=1)
def boundary_countries():
    """Boundary metadata is a selector catalog, never an intelligence Entity."""
    path = Path(__file__).resolve().parents[1] / 'static' / 'countries.geojson'
    features = json.loads(path.read_text(encoding='utf-8'))['features']
    return {f['properties']['ISO3166-1-Alpha-2']: f['properties']['name']
            for f in features if len(f['properties']['ISO3166-1-Alpha-2']) == 2
            and f['properties']['ISO3166-1-Alpha-2'].isalpha()}


@dataclass(frozen=True)
class IntelligenceQuery:
    geography_ids: tuple[str, ...] = ()
    berry_id: str = ''
    country_codes: tuple[str, ...] = ()
    berry_ids: tuple[str, ...] = ()
    view: str = "trusted"

    @classmethod
    def parse(cls, countries, berry, entities, berries):
        ids = tuple(dict.fromkeys(x.strip() for x in countries.split(',') if x.strip()))
        canonical = []
        codes = []
        by_iso = {(e.get('attributes') or {}).get('iso_3166_1_alpha_2'): e['id']
                  for e in entities.values() if e.get('entity_type') == 'geography'}
        for eid in ids:
            if eid.startswith('iso:') and eid[4:] in boundary_countries():
                code = eid[4:]
                if code in by_iso:
                    canonical.append(by_iso[code])
                else:
                    codes.append(code)
            elif eid in entities and entities[eid].get('entity_type') == 'geography':
                canonical.append(eid)
            else:
                raise ValueError('Unknown geography selection')
        commodities = tuple(dict.fromkeys(x.strip() for x in berry.split(',') if x.strip()))
        if any(bid not in berries for bid in commodities):
            raise ValueError('Unknown berry selection')
        return cls(tuple(dict.fromkeys(canonical)), commodities[0] if len(commodities) == 1 else '',
                   tuple(dict.fromkeys(codes)), commodities)

    def commodities(self):
        # Preserve callers that constructed the former single-berry query.
        return self.berry_ids or ((self.berry_id,) if self.berry_id else ())

    def params(self):
        return {'countries': ','.join((*self.geography_ids, *(f'iso:{code}' for code in self.country_codes))), 'berry': ','.join(self.commodities()), 'view': self.view}

    def url(self, path='/explorer'):
        return path + '?' + urlencode(self.params())

    def retrieve(self, records, relationships):
        scope = set()
        for eid in self.geography_ids:
            scope.update(resolve_geography_scope(eid, relationships=relationships).all_ids)
        if self.country_codes and not scope:
            return []
        return sorted((r for r in records if (r.get('status') == 'published' or (self.view == 'unreviewed' and r.get('status') == 'unreviewed'))
            and 'structural' not in (r.get('tags') or [])
            and (not scope or bool(record_geography_ids(r) & scope))
            and (not self.commodities() or bool(set(self.commodities()) & set(r.get('berry_ids') or [])))),
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

def explorer_model(query, records, entities, relationships, berries, facts=None, state=None, present_entries=True):
    from app.services.feed_first import safe_image_url, decision_for
    escalations = {}
    for fact in facts or []:
        if fact.get("status") != "active":
            continue
        for eid in fact.get("evidence_ids") or []:
            escalations.setdefault(eid, []).append(fact)
    if facts is not None and query.view == "trusted":
        from app.services.news_workspace import source_reviewed
        records = [r for r in records if r.get("id") in escalations and source_reviewed(r)]
    selected = query.retrieve(records, relationships)
    entries = [present_feed_item(r, entities=entities, berry_labels=berries) for r in selected] if present_entries else []
    by_id = {r['id']: r for r in selected}
    for item in entries:
        record = by_id[item['id']]
        item['image_url'] = safe_image_url(record)
        item['explorer_feedback'] = query.view == 'unreviewed'
        item['decision'] = decision_for(item['id'], state or {})
        item['escalations'] = escalations.get(item['id'], [])
        item['trust'] = 'trusted' if item['escalations'] else 'pending'
    countries = []
    for e in entities.values():
        iso = (e.get('attributes') or {}).get('iso_3166_1_alpha_2')
        if e.get('entity_type') != 'geography' or not iso: continue
        rows = IntelligenceQuery((e['id'],), berry_ids=query.commodities(), view=query.view).retrieve(records, relationships)
        countries.append({'id': e['id'], 'name': e['name'], 'iso': iso,
                          'count': len(rows), 'recent': [{'title': r.get('title') or r['id'],
                          'href': '/intelligence/'+r['id'], 'date': r.get('published_date') or 'Date unknown'} for r in rows[:3]],
                          'berries': sorted({berries[b] for r in rows for b in r.get('berry_ids', []) if b in berries}),
                          'companies': sorted({entities[eid]['name'] for r in rows for eid in r.get('entity_ids', []) if eid in entities and entities[eid].get('entity_type') == 'company'})})
    known_codes = {country['iso'] for country in countries}
    for code, name in boundary_countries().items():
        if code not in known_codes:
            countries.append({'id': 'iso:'+code, 'name': name, 'iso': code,
                              'count': 0, 'recent': [], 'berries': [], 'companies': [],
                              'unavailable': True})
    selected_countries = [entities[eid] for eid in query.geography_ids]
    selected_countries.extend({'id': 'iso:'+code, 'name': boundary_countries()[code]}
                              for code in query.country_codes)
    return {'query': query, 'entries': entries, 'countries': sorted(countries,key=lambda c:c['name']),
            'selected': selected_countries, 'berries': berries,
            'total': len(entries), 'gaps': GAPS}

def snapshot_model(query, records, entities, relationships, berries, included, facts=None, state=None):
    from dataclasses import replace
    query = replace(query, view="trusted")
    model = explorer_model(query, records, entities, relationships, berries, facts=facts, state=state)
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
    scope = {'geography_ids':list(query.geography_ids), 'berry_id':query.berry_id,
             'country_codes': list(query.country_codes), 'berry_ids': list(query.commodities())}
    report = {'title':'Market Snapshot — '+(', '.join(e['name'] for e in model['selected']) or 'Global')+' / '+(', '.join(berries[bid] for bid in query.commodities()) or 'All Berries'),
              'report_type':'market_snapshot', 'scope':scope, 'sections':sections}
    cited = {eid for s in sections for eid in s['citation_ids']}
    trace = [{'id':r['id'], 'title':escape(r['title']), 'source_name':escape(r['source_name']),
              'date':r['date'], 'source_url':r['source_url'], 'href':r['href']} for r in entries if r['id'] in cited]
    packet = {'recent_developments':entries, 'source_trace':trace}
    coverage = {'counts':{'evidence_count':len(entries)},'gaps':GAPS}
    return model | {'report':report, 'packet':packet, 'coverage':coverage, 'section_options':SECTIONS, 'included':included}
