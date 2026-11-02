"""Cited, local variety search. Source context is never a growing footprint."""
import json
import shlex
import re
import unicodedata

from app.services.deterministic_tagging import matchers_from_entities
from app.services.feed_first import SAFE_ID_RE
from app.services.map_regions import public_source_url
from app.services.topic_retrieval import record_passages
from app.services.variety_source_reading import _eligible, _title_mentions


def source_activity(*, notes=None, reading=None, filings=()):
    """Index already-attributed coverage; an award mention is not a verified win."""
    awards=[]
    for row in (notes or {}).get('details') or []:
        if re.search(r'\b(award|awards|medal|recognition)\b',row['field']+' '+row['value'],re.I):
            source=notes['sources'][row['source_id']]
            awards.append(dict(title=row['field'],text=row['value'],context=row['context'],url=source['url'],label='Source-reported · Pending review'))
    mentions=(reading or {}).get('rows') or []
    for row in mentions:
        text=' '.join([row['title'],row.get('excerpt') or '',*(row.get('passages') or [])])
        match=re.search(r'\b(award|awards|medal|recognition)\b',text,re.I)
        if match:
            awards.append(dict(title=row['title'],text=text[max(0,match.start()-100):match.start()+360],context='Award-related source coverage; verify the named winner, category and event date in the source.',url=row['source_url'],label='Unreviewed award-related mention'))
    return dict(awards=awards[:8],mentions=mentions[:12],filing_count=len(filings or []))


def fold(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(text)).casefold() if not unicodedata.combining(c))


def query_terms(query):
    if len(query) > 240:
        raise ValueError('Use a search of 240 characters or fewer.')
    try:
        terms = [fold(t) for t in shlex.split(query) if t.strip()]
    except ValueError as exc:
        raise ValueError('Close the quotation marks around a phrase.') from exc
    if len(terms) > 12:
        raise ValueError('Use up to twelve terms or quoted phrases.')
    return terms


def search_varieties(query, *, varieties, records=(), notes=None, facts=(), names_only=False, record_loader=None):
    terms = query_terms(query)
    if not terms:
        return {}
    docs = {v['id']: [] for v in varieties}
    known = {v['id']: v for v in varieties}

    def add(key, label, text, href, source_url='', pending=False):
        if key in docs and text:
            docs[key].append(dict(label=label, text=str(text)[:24_000], href=href, source_url=public_source_url(source_url) or '', pending=pending))

    evidence_links = {}
    for v in varieties:
        key = v['id'];href = '/entities/variety/' + key
        add(key, 'Name / identity', ' '.join([v['name'], *(v.get('aliases') or [])]), href)
        if names_only:
            continue
        attrs={k:value for k,value in (v.get('attributes') or {}).items() if k not in {'catalog_removal','catalog_removed','catalog_candidate_id','identity_review'}}
        identity_source=(v.get('attributes') or {}).get('identity_review') or {}
        add(key, 'Stored profile', (v.get('description') or '') + ' ' + json.dumps(attrs, ensure_ascii=False), href)
        add(key, 'Catalog identity citation', ' '.join(str(identity_source.get(k) or '') for k in ['source_url','source_label']), href, identity_source.get('source_url') or '')
        for source_id in v.get('evidence_ids') or []:
            evidence_links.setdefault(source_id, set()).add(key)
        note = (notes or {}).get(key) or {}
        for row in note.get('details') or []:
            source = note['sources'][row['source_id']]
            add(key, 'Source-reported · Pending review', '\n'.join([row['field'], row['value'], row['context'], source['title'], source['kind'], source['locator'], source['url']]),
                href + '#variety-researched-details', source['url'], True)
    if not names_only:
        matchers = matchers_from_entities(varieties, 'variety')
        for record in records:
            if not _eligible(record) or not SAFE_ID_RE.fullmatch(str(record.get('id') or '')):
                continue
            associated = set(record.get('entity_ids') or []) & docs.keys()
            associated |= evidence_links.get(record.get('id'), set())
            crop = set(record.get('berry_ids') or [])
            mentioned = _title_mentions(record, varieties, matchers) if crop else set()
            if (associated or mentioned) and record_loader:
                record = record_loader(record) or record
            for key in associated | mentioned:
                if crop and not crop.intersection(known[key].get('berry_ids') or []):
                    continue
                label = 'Published source' if record.get('status') == 'published' else 'Publication review pending'
                if key not in associated:
                    label += ' · Unreviewed name mention'
                if record.get('_private_capture_unreviewed'):
                    label += ' · Captured text pending review'
                href='/intelligence/' + str(record['id']);url=record.get('source_url') or '';pending=record.get('status') != 'published' or key not in associated or bool(record.get('_private_capture_unreviewed'))
                add(key, label, '\n'.join(str(record.get(field) or '') for field in ['title','source_name','source_url']), href, url, pending)
                seen=set()
                for locator,text in record_passages(record):
                    if text in seen:continue
                    seen.add(text)
                    add(key, label+' · '+locator, text, href, url, pending)
        for fact in facts:
            if fact.get('status') not in {'approved', 'active', 'published', 'validated', 'confirmed'}:
                continue
            for key in set(fact.get('entity_ids') or []) & docs.keys():
                add(key, 'Reviewed statement', str(fact.get('statement') or fact.get('text') or ''), '/entities/variety/' + key + '#variety-intelligence')
    results = {}
    for key, passages in docs.items():
        all_text = '\n'.join(fold(p['text']) for p in passages)
        if not all(term in all_text for term in terms):
            continue
        matched = []
        for p in passages:
            text = fold(p['text'])
            positions = [text.find(term) for term in terms if term in text]
            if not positions:
                continue
            start = max(0, min(positions) - 80)
            matched.append({**p, 'excerpt': ('…' if start else '') + p['text'][start:start+360] + ('…' if len(p['text']) > start+360 else '')})
        matched.sort(key=lambda p: (p['label'] == 'Name / identity', sum(t in fold(p['text']) for t in terms)), reverse=True)
        results[key] = {'matches': matched[:4], 'match_count': len(matched)}
    return results
