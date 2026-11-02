"""Conservative presentation groups; never identity, trust or corroboration writes."""
import hashlib
import re
from datetime import date

from app.services.story_threads import items_form_thread
from app.services.topic_retrieval import record_passages, normalize


def _names(entity):
    names = [entity.get('name') or '', *(entity.get('aliases') or [])]
    canonical = names[0]
    match = re.search(r'\s*\(([^)]+)\)$', canonical)
    if match and match[1] in names[1:]:
        names.append(canonical[:match.start()])
    return [n for n in names if len(n) >= 4 or (len(n) == 3 and n.isupper())]


def _mentions(text, name):
    return bool(re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',text,0 if len(name)==3 else re.I))


def _license_signature(row, entities, varieties, matchers):
    from app.services.variety_source_reading import _title_mentions
    subjects = _title_mentions(row, varieties, matchers)
    if len(subjects) != 1:
        return None
    # Body-owned passages only. Metadata/snippets cannot establish event identity.
    text = ' '.join(p for loc,p in record_passages(row) if loc not in {'title','summary','snippet'})[:12000]
    if not text and row.get('passage_locator') not in {None,'title','summary','snippet'}:
        text = str(row.get('passage') or '')[:12000]
    licenses = []
    for entity in entities.values():
        if entity.get('entity_type') != 'company':
            continue
        for name in _names(entity):
            match = re.search(r'\blicensed\s+to\s+(?:the\s+)?'+re.escape(name)+r'(?!\w)',text,0 if len(name)==3 else re.I)
            if not match:
                continue
            tail = text[match.end():match.end()+180]
            territory = re.search(r'\b(outside|in|across)\s+(?:the\s+)?(.+)',tail,re.I)
            if not territory:
                continue
            clause = re.split(r'[,.;]|\b(?:following|marking|after)\b',territory[2],maxsplit=1,flags=re.I)[0]
            places = tuple(sorted(e['id'] for e in entities.values() if e.get('entity_type') == 'geography'
                                  and any(_mentions(clause,n) for n in _names(e))))
            if places:
                licenses.append((entity['id'],territory[1].lower(),places))
    licenses = set(licenses)
    return (next(iter(subjects)),next(iter(licenses))) if len(licenses)==1 else None


def event_groups(rows, entities):
    from app.services.deterministic_tagging import matchers_from_entities
    varieties = [e for e in entities.values() if e.get('entity_type') == 'variety']
    matchers = matchers_from_entities(varieties,'variety')
    signatures = {r['id']:_license_signature(r,entities,varieties,matchers) for r in rows}
    def kind(row):
        if signatures[row['id']]:
            return 'licensing'
        body = ' '.join(p for loc,p in record_passages(row) if loc not in {'title','summary','snippet'})[:12000]
        if re.search(r'\blicensed\s+to\b',body,re.I):
            return 'unresolved_licensing'
        title = normalize(row.get('title') or '')
        return 'introduction' if re.search(r'\b(introduc\w*|releas\w*|launch\w*)\b',title) else 'other'
    def together(left,right):
        try:
            gap = abs((date.fromisoformat((left.get('published_date') or left.get('date') or '')[:10])-date.fromisoformat((right.get('published_date') or right.get('date') or '')[:10])).days)
        except ValueError:
            return False
        if gap>7 or kind(left)!=kind(right):
            return False
        if kind(left)=='unresolved_licensing':
            return False
        a,b = signatures[left['id']],signatures[right['id']]
        if a or b:
            return bool(a and a==b)
        return items_form_thread(left,right)
    groups=[]
    for row in rows:
        group = next((g for g in groups if all(together(row,member) for member in g)),None)
        if group is None:
            groups.append([row])
        else:
            group.append(row)
    return [{'id':'research-event-'+hashlib.sha256('|'.join(sorted(r['id'] for r in group)).encode()).hexdigest()[:16],
             'member_ids':[r['id'] for r in group], 'members':group,
             'reason':'Same named variety, licensee, territory and nearby publication dates' if signatures[group[0]['id']] else 'Existing conservative Story Thread match',
             'label':'Related coverage · independence not established'} for group in groups]
