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
    if 'breeder'in words and not re.search(r'\b(?:breeder|breeding|bred|origin\w*|parentage|cross\w*|select\w*)\b',plain):return False
    asks_bumble=bool(words&{'bumblebee','bumblebees'}or ('bumble'in words and words&{'bee','bees'}))
    if asks_bumble and not re.search(r'\b(?:bumble\s*bee\w*|bombus)\b',plain):return False
    if 'license' in words:
        # Article copyright and open-access licences are not cultivar deals.
        licensing=re.search(r'\b(?:licen[sc](?:e|es|ed|ing)\s+(?:to|for|in|across|outside|agreement|arrangement|rights|territory|territories)|licen[sc](?:e|es|ed|ing)\s+(?:the\s+)?(?:blackberry|blueberry|raspberry|strawberry|variety)|(?:licen[sc]e|licen[sc]ing)\s+(?:agreement|deal|partner|program|programme)|(?:propagation|growing|commercialisation|commercialization)\s+rights)\b',plain)
        # A cultivar's separate introduction can remain attributed background;
        # it never establishes its licensing milestone (classified downstream).
        crop=r'(?:variety|floricane|primocane|blackberry|raspberry|blueberry|strawberry)'
        introduction=re.search(r'\b(?:introduc\w*|releas\w*|launch\w*)\b[^.!?]{0,65}\b'+crop+r'\b|\b'+crop+r'\b[^.!?]{0,65}\b(?:introduc\w*|releas\w*|launch\w*)\b',plain)
        if not licensing and not introduction:return False
    requirements=[
        ({'breeding'},r'\b(?:breed\w*|bred|genetic\w*|genomic\w*|cross\w*|select\w*)\b'),
        ({'variety'},r'\b(?:variet\w*|cultivar\w*|breed\w*|selection\w*|genotyp\w*)\b'),
        ({'calcium'},r'\b(?:calcium|ca)\b'),
        ({'foliar'},r'\b(?:foliar|leaf spray\w*|preharvest spray\w*)\b'),
        ({'firmness'},r'\b(?:firm\w*|texture|soften\w*)\b'),
        ({'leakage'},r'\b(?:leak\w*|leaky|juice loss)\b'),
        ({'postharvest'},r'\b(?:postharvest|post harvest|after harvest|fruit stor\w*)\b'),
        ({'chilling'},r'\b(?:chill\w*|vernali[sz]\w*|cold treatment\w*)\b'),
        ({'flowering'},r'\b(?:flower\w*|bloom\w*|floral|bud break)\b'),
        ({'controlled','environment'},r'\b(?:controlled environment\w*|greenhouse\w*|glasshouse\w*|growth chamber\w*|climate chamber\w*)\b'),
        ({'phytophthora'},r'\bphytophthora\b'),
        ({'root','rot'},r'\b(?:root rot|phytophthora)\b'),
        ({'night'},r'\b(?:night\w*|after sunset|after dark|evening)\b'),
        ({'salt','stress'},r'\b(?:salin\w*|salt stress|nacl)\b'),
        ({'silicon'},r'\b(?:silicon|silica|sio\s*2|sinps)\b'),
        ({'cold','storage'},r'\b(?:cold stor\w*|chill\w* stor\w*|stor\w*[^.!?]{0,35}\b(?:cold|[0-9]+\s*(?:c|degrees)))\b'),
        ({'tray'},r'\btray\w*\b'),
        ({'bruising'},r'\b(?:bruis\w*|damag\w*|injur\w*)\b'),
        ({'mechanical'},r'\b(?:mechanical\w*|machine|mechaniz\w*|mechanis\w*)\b'),
        ({'netting'},r'\b(?:netting|netted|exclusion nets?)\b'),
        ({'pollination'},r'\b(?:pollinat\w*|bumblebee\w*)\b'),
    ]
    for required,pattern in requirements:
        if required<=words and not re.search(pattern,plain):return False
    if 'ultraviolet' in words or words&{'uv','uvc','uvb'}:
        if not re.search(r'\b(?:ultraviolet|uv(?:[ -]?[abc])?)\b',plain):return False
    if words&{'greenhouse','glasshouse'}:
        if not re.search(r'\b(?:greenhouse|glasshouse|protected cultivation|high tunnel)\b',plain):return False
    if 'nursery' in words and not re.search(r'\b(?:nursery|nurseries|transplant\w*)\b',plain):return False
    if 'anthracnose' in words and not re.search(r'\b(?:anthracnose|colletotrichum)\b',plain):return False
    if {'powdery','mildew'} <= words:
        if not re.search(r'\b(?:powdery mildew|podosphaera aphanis|sphaerotheca macularis)\b',plain):return False
    if 'resistance' in words and not re.search(r'\b(?:resistan\w*|toleran\w*|susceptib\w*)\b',plain):return False
    if 'disease' in words and not re.search(r'\b(?:disease\w*|pathogen\w*|fung\w*|mildew|botrytis|anthracnose)\b',plain):return False
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
    if any(t.startswith(('trial','experiment','evaluat')) for t in words):
        if not re.search(r'\b(?:trial\w*|evaluat\w*|experiment\w*|test\w*|compar\w*)\b',plain):return False
        if 'field' in words:
            # Field capacity is a substrate-water measure, not a field site.
            if not re.search(r'\b(?:field(?! capacity)|outdoor)\b',plain):return False
            # Proposed field work cannot establish a completed field result.
            if re.search(r'\b(?:should|must|will|future|needs? to)\b[^.!?]{0,240}\b(?:field(?! capacity)|outdoor)\b',plain):return False
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
        if entity.get('entity_type')not in {'company','breeding_program'}:continue
        names=tuple(filter(None,(normalize(n) for n in [entity.get('name') or '',*(entity.get('aliases') or [])])))
        if any(len(name)>=4 and re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',positive) for name in names):
            organizations.append(names)
    places=[]
    place_terms=set()
    if 'license' in plan.terms or any(t.startswith(('trial','experiment','evaluat','research')) for t in plan.terms):
        for entity in (entities or {}).values():
            if entity.get('entity_type')!='geography':continue
            names=[entity.get('name') or '',*(entity.get('aliases') or [])]
            if entity.get('name')=='United Kingdom':names.append('U.K.')
            matched_names=[normalize(name) for name in names if name and re.search(r'(?<!\w)'+re.escape(normalize(name))+r'(?!\w)',positive)]
            if matched_names:
                place_terms.update(word for name in matched_names for word in name.split())
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
                place_terms.update(term.split())
    return {'identities':list(identities.values()),'trial_places':places,
            'place_terms':tuple(sorted(place_terms)),'organizations':organizations}


def organizations_in_passage(text, groups):
    from app.services.topic_retrieval import normalize
    plain=normalize(text)
    return all(any(re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',plain) for name in names) for names in groups)


def identity_in_passage(text, entity):
    from app.services.topic_retrieval import normalize
    original = text
    # Retain sentence boundaries: an author's name at the end of one sentence
    # must not own a cultivar description in the next sentence.
    text=' . '.join(normalize(part)for part in re.split(r'(?<=[.!?])\s+',text))
    text=re.sub(r"(?<!\w)'|'(?!\w)",'',text)
    for name in [entity.get('name') or '',*(entity.get('aliases') or [])]:
        name=normalize(name)
        if not name:continue
        if re.search(r'\d',name):
            pattern=r'\s*'.join(re.escape(t) for t in re.findall(r'[a-z]+|\d+',name))
            if pattern and re.search(r'(?<!\w)'+pattern+r'(?!\w)',text):return True
        name=re.escape(name)
        # Explicit cultivar grammar prevents a person's namesake becoming a trait.
        if re.search(r'\b(?:variety|cultivar|blackberry|raspberry|blueberry|strawberry|named|called|introduce\w*)\s+(?:the\s+)?'+name+r'(?!\w)',text):return True
        if re.search(r'\b(?:includes?|including|such as)\s+(?:the\s+)?(?:variety|cultivar)\s+[^.!?]{0,350}(?<!\w)'+name+r'(?!\w)',text):return True
        descriptors=r'(?:(?:ever bearer|everbearer|primocane fruiting|floricane fruiting|thornless|early|late|midseason|main season|mid late|june bearing|day neutral|short day|low chilling|low chill|southern highbush|northern highbush|highbush)\s+){0,3}'
        if re.search(r'(?<!\w)'+name+r'\s+(?:(?:is|was)\s+)?(?:(?:a|the)\s+)?(?:new\s+)?'+descriptors+r'(?:blackberry|raspberry|blueberry|strawberry|variety|cultivar)\b',text):return True
        # A parenthesized experimental cultivar list owns its crop context,
        # including when a PDF page break falls inside the list. Names outside
        # that explicit list (authors, other crops) do not inherit the context.
        for group in re.finditer(r'\b(?:evaluated|tested|compared)\s+(?:(?:primocane|floricane)\s+)?(raspberries|blackberries|blueberries|strawberries)\b[^.!?]{0,250}\(([^)]+)\)', original, re.I):
            crop = normalize(group[1])
            quoted=re.findall(r"[\"'‘“]([^\"'’”]+)[\"'’”]",group[2])
            if 'berry-' + crop in entity.get('berry_ids', []) and any(re.fullmatch(name,normalize(value))for value in quoted):
                return True
    return False


def cane_in_passage(text, cane):
    if not cane:return True
    from app.services.topic_retrieval import normalize
    text=normalize(text)
    if re.search(r'\b'+cane+r'[- ]?(?:fruit\w*|bear\w*|crop|yield\w*|flower\w*|production|blackberr\w*|raspberr\w*|variet\w*|cultivar\w*|trial\w*)\b',text,re.I):return True
    return bool(re.search(r'\b(?:fruit\w*|crop|yield\w*|flower\w*|produc\w*)\b[^.!?]{0,65}\b'+cane+r'\b',text,re.I))


def trial_location_in_passage(text, places, *, require_trial=True):
    from app.services.topic_retrieval import normalize
    if not places:return True
    text=normalize(text)
    if require_trial and not re.search(r'\b(?:trial\w*|evaluat\w*|experiment\w*|research|study|studies)\b',text):return False
    prepositions='in|at|across|within|near'if require_trial else'in|at|across|within|near|for|throughout|outside'
    subjects='trial|evaluation|experiment'if require_trial else'licen[sc]\\w*|territor\\w*|agreement'
    return all(any(re.search(r'\b(?:'+prepositions+r') (?:the )?'+re.escape(place)+r'(?!\w)|(?<!\w)'+re.escape(place)+r' (?:field )?(?:'+subjects+r')',text) for place in group) for group in places)
