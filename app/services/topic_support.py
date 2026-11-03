"""Conservative quotation scope checks; no semantic or factual trust approval."""
import re

CROPS={'blackberry','blueberry','raspberry','strawberry'}


def passage_intent_supported(text, plan):
    """Require the requested operation, rather than borrowing its title.

    These are quotation eligibility checks, not an entailment/truth score.
    Related sources can remain visible as verification leads.
    """
    from app.services.topic_retrieval import normalize
    words=set(plan.terms)
    plain=normalize(text)
    if any(t.startswith('ventilat') for t in words):
        if not re.search(r'\b(?:vent\w*|air exchange|airflow|air flow)\b',plain):return False
    if 'heat' in words and 'stress' in words:
        if not re.search(r'\b(?:heat\w*|thermal|high\w* temperatur\w*|increas\w* temperatur\w*)\b',plain):return False
        # A heatmap is a plotting method, not a temperature treatment.
        if not re.search(r'\b(?:heat(?!map)\w*|thermal|temperatur\w*)\b',plain):return False
    if any(t.startswith('prun') for t in words):
        if not re.search(r'\b(?:prun\w*|tipp\w*|thin\w*|cut\w*|remov\w*|train\w*)\b',plain):return False
        if 'trial' not in words and not re.search(r'\b(?:should|must|recommend\w*|cut|remove|winter|spring|summer|after harvest)\b',plain):return False
    if {'root','zone'} <= words and any(t.startswith('cool') for t in words):
        if not re.search(r'\broot zone\b',plain):return False
        if not re.search(r'\b(?:cool\w*|temperatur\w*|reduc\w*)\b',plain):return False
    if any(t.startswith(('trial','experiment')) for t in words):
        if not re.search(r'\b(?:trial\w*|evaluat\w*|experiment\w*|test\w*|compar\w*)\b',plain):return False
        if 'field' in words and not re.search(r'\b(?:field|outdoor)\b',plain):return False
    if any(t.startswith('robot') for t in words) and any(t.startswith('harvest') for t in words):
        crops=words & CROPS
        for crop in crops:
            stem=crop.removesuffix('y')
            fruit=stem+r'(?:y|ies)'
            operation=r'(?:harvest\w*|pick\w*)'
            qualifiers=r'(?:(?:the|ripe|delicate|fresh)\s+){0,2}'
            if not re.search(r'\b'+fruit+r'\s+(?:(?:robotic|robot assisted|mechanical)\s+)?'+operation+r'\b|\b'+operation+r'\s+(?:of\s+)?'+qualifiers+fruit+r'\b',plain):return False
    return True


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
    organizations=[]
    for entity in (entities or {}).values():
        if entity.get('entity_type')!='company':continue
        names=tuple(filter(None,(normalize(n) for n in [entity.get('name') or '',*(entity.get('aliases') or [])])))
        if any(len(name)>=4 and re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',positive) for name in names):
            organizations.append(names)
    places=[]
    if any(t.startswith(('trial','experiment')) for t in plan.terms):
        for entity in (entities or {}).values():
            if entity.get('entity_type')!='geography':continue
            names=[entity.get('name') or '',*(entity.get('aliases') or [])]
            if entity.get('name')=='United Kingdom':names.append('U.K.')
            if any(name and re.search(r'(?<!\w)'+re.escape(normalize(name))+r'(?!\w)',positive) for name in names):
                if entity.get('name')=='United Kingdom':names.extend(['England','Scotland','Wales','Northern Ireland','Britain'])
                places.append(tuple(filter(None,(normalize(name) for name in names))))
        # Geographic scope vocabulary does not create registry entities or
        # equate a climate with a country. Unresolved regional requests stay
        # literal, including subdivisions absent from the country registry.
        for name in ('Mediterranean','Scotland','England','Wales','Northern Ireland',
                     'Central America','South America','North America','Southeast Asia'):
            term=normalize(name)
            if re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)',positive):
                places.append((term,))
    return {'identities':list(identities.values()),'trial_places':places,'organizations':organizations}


def organizations_in_passage(text, groups):
    from app.services.topic_retrieval import normalize
    plain=normalize(text)
    return all(any(re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',plain) for name in names) for names in groups)


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
