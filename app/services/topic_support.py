"""Conservative quotation scope checks; no semantic or factual trust approval."""
import re

CROPS={'blackberry','blueberry','raspberry','strawberry'}


def support_context(plan, entities, identifiers):
    from app.services.topic_retrieval import normalize
    positive=normalize(re.sub(r'(?<!\w)-("[^"]+"|[\w-]+)','',plan.raw_query))
    crops=set(plan.terms)&CROPS
    identities={}
    for identifier in identifiers:
        if len(identifier['entities'])==1:
            identities.update(identifier['entities'])
    for entity in (entities or {}).values():
        if entity.get('entity_type')!='variety':continue
        if crops and not any('berry-'+crop in entity.get('berry_ids',[]) for crop in crops):continue
        for name in [entity.get('name') or '',*(entity.get('aliases') or [])]:
            term=normalize(name)
            if len(term)<4 or not set(term.split())-CROPS:continue
            if re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)',positive):
                identities[entity['id']]=entity
    places=[]
    if 'trial' in plan.terms:
        for entity in (entities or {}).values():
            if entity.get('entity_type')!='geography':continue
            names=[entity.get('name') or '',*(entity.get('aliases') or [])]
            if entity.get('name')=='United Kingdom':names.append('U.K.')
            if any(name and re.search(r'(?<!\w)'+re.escape(normalize(name))+r'(?!\w)',positive) for name in names):
                if entity.get('name')=='United Kingdom':names.extend(['England','Scotland','Wales','Northern Ireland','Britain'])
                places.append(tuple(filter(None,(normalize(name) for name in names))))
    return {'identities':list(identities.values()),'trial_places':places}


def identity_in_passage(text, entity):
    from app.services.topic_retrieval import normalize
    text=re.sub(r"(?<!\w)'|'(?!\w)",'',normalize(text))
    for name in [entity.get('name') or '',*(entity.get('aliases') or [])]:
        name=normalize(name)
        if not name:continue
        if re.search(r'\d',name):
            pattern=r'\s*'.join(re.escape(t) for t in re.findall(r'[a-z]+|\d+',name))
            if pattern and re.search(r'(?<!\w)'+pattern+r'(?!\w)',text):return True
        name=re.escape(name)
        # Explicit cultivar grammar prevents a person's namesake becoming a trait.
        if re.search(r'\b(?:variety|cultivar|blackberry|raspberry|blueberry|strawberry|named|called|introduce\w*)\s+(?:the\s+)?'+name+r'(?!\w)',text):return True
        if re.search(r'(?<!\w)'+name+r'\s+(?:(?:is|was)\s+(?:a\s+)?(?:new\s+)?|(?:a|the)\s+)?(?:blackberry|raspberry|blueberry|strawberry|variety|cultivar)\b',text):return True
    return False


def cane_in_passage(text, cane):
    if not cane:return True
    from app.services.topic_retrieval import normalize
    text=normalize(text)
    if re.search(r'\b'+cane+r'[- ]?(?:fruit\w*|bear\w*|crop|yield\w*|flower\w*|production|blackberr\w*|raspberr\w*|variet\w*|cultivar\w*|trial\w*)\b',text,re.I):return True
    return bool(re.search(r'\b(?:fruit\w*|crop|yield\w*|flower\w*|produc\w*)\b[^.!?]{0,65}\b'+cane+r'\b',text,re.I))


def trial_location_in_passage(text, places):
    from app.services.topic_retrieval import normalize
    if not places:return True
    text=normalize(text)
    if not re.search(r'\b(?:trial\w*|evaluat\w*|experiment\w*)\b',text):return False
    return all(any(re.search(r'\b(?:in|at|across|within|near) (?:the )?'+re.escape(place)+r'(?!\w)|(?<!\w)'+re.escape(place)+r' (?:field )?(?:trial|evaluation|experiment)',text) for place in group) for group in places)
