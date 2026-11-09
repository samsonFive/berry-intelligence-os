"""Shared, deterministic topic understanding and passage retrieval.

No network, trust mutations, or persisted index. Callers supply only records
the current user may access; rebuilding from those records avoids index lag.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import date
from functools import lru_cache
from typing import Any, Iterable, Mapping

VERSION = "topic-retrieval-v32"
_PLURALS = {"blackberries": "blackberry", "blueberries": "blueberry", "strawberries": "strawberry", "raspberries": "raspberry", "varieties": "variety", "cultivar": "variety", "cultivars": "variety", "canes": "cane", "floricanes": "floricane", "primocanes": "primocane", "trials": "trial", "releases": "release", "licensed": "license", "licensing": "license", "licence": "license", "licences": "license", "licencing": "license"}
_PLURALS["harvesting"] = "harvest"
_STOP = set("a an the and or of for in on that which what me give write report new latest recent developments development fruit fruits fruiting about is are with to competitive landscape overview intelligence create prepare understand tell show please doing done".split())
_EVENT = re.compile(r"\b(releas\w*|introduc\w*|licen[sc]\w*|trial\w*|launch\w*|patent\w*|commercial\w*|research|study|results)\b", re.I)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", re.sub('[™®℠]','',text)).casefold().translate(str.maketrans({"’": "'", "‘": "'", "–": "-", "—": "-", "‑": "-"}))
    text = re.sub(r"(?<!\w)'|'(?!\w)",'',text)
    from app.services.berry_vocabulary import canonicalize_crop_words, canonicalize_industry_words
    text = canonicalize_industry_words(canonicalize_crop_words(text))
    return " ".join(_PLURALS.get(t, t) for t in re.findall(r"[\w']+", text))


@dataclass(frozen=True)
class QueryPlan:
    raw_query: str
    interpreted_query: str
    terms: tuple[str, ...]
    phrases: tuple[str, ...]
    exclusions: tuple[str, ...]
    cane_type: str | None
    start: str | None
    end: str | None
    corrected: bool

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "version": VERSION}


@lru_cache(maxsize=256)
def plan_query(raw: str, *, use_original: bool = False) -> QueryPlan:
    interpreted = unicodedata.normalize("NFKC", re.sub('[™®℠]','',raw)).strip()
    # Corrections are narrow domain vocabulary; unknown names stay literal.
    if not use_original and re.search(r"\bblackberr(?:y|ies)\b", interpreted, re.I):
        pieces = re.split(r'("[^"]*")', interpreted)
        for i in range(0, len(pieces), 2):
            pieces[i] = re.sub(r"\bfloricans\b", "floricane", pieces[i], flags=re.I)
            pieces[i] = re.sub(r"\b(?:fruit(?:ing)?\s+on\s+)?second[- ‑–]year\s+canes\b", "floricane", pieces[i], flags=re.I)
        interpreted = "".join(pieces)
    exclusions = tuple(normalize(p) for p in re.findall(r'(?<!\w)-("[^"]+"|[\w-]+)', raw))
    positive = re.sub(r'(?<!\w)-("[^"]+"|[\w-]+)', "", interpreted)
    phrases = tuple(normalize(p) for p in re.findall(r'"([^"]+)"', positive))
    dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", positive)
    for stamp in dates:
        date.fromisoformat(stamp)
    start = dates[0] if dates else None
    end = dates[1] if len(dates) > 1 else None
    if start and end and start > end:
        raise ValueError("Start date must precede end date")
    positive = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", positive)
    positive = re.sub(r"\b(?:from|through|between|until)\b", "", positive, flags=re.I)
    positive = re.sub(r"\b(?:arándanos?|arandanos?)(?!\w|\s+(?:roj[oa]s?|azul(?:es)?)\b)", "blueberry", positive, flags=re.I)
    positive = re.sub(r"\b(?:ensayos?|essais?|prove produttive)\b", "trial", positive, flags=re.I)
    positive = re.sub(r"\bcosecha mec[aá]nica\b", "mechanical harvest", positive, flags=re.I)
    positive = re.sub(r"\bvarietà di mora\b(?!\s+di gelso\b)", "blackberry variety", positive, flags=re.I)
    positive = re.sub(r"\bsenza spine\b", "thornless", positive, flags=re.I)
    positive = re.sub(r"\bScozia\b", "Scotland", positive, flags=re.I)
    if "raspberry" in normalize(positive).split():
        positive = re.sub(r"\bremontantes?\b", "primocane", positive, flags=re.I)
    stop = _STOP
    if re.search(r"\b(?:zarzamoras?|fresas?|arándanos?|arandanos?|ensayos?|españa)\b", interpreted, re.I):
        stop = _STOP | {"a", "de", "del", "el", "en", "la", "las", "los", "para", "por", "y"}
    terms = tuple(dict.fromkeys(t for t in normalize(positive).split() if t not in stop))
    cane = "floricane" if "floricane" in terms else "primocane" if "primocane" in terms else None
    return QueryPlan(raw, interpreted, terms, phrases, exclusions, cane, start, end, interpreted != raw.strip())


def record_passages(record: Mapping[str, Any]) -> list[tuple[str, str]]:
    from app.services.source_passage_scope import owned_article_passages, owned_pdf_abstracts
    passages: list[tuple[str, str]] = []
    cited_page = re.search(r'#page=(\d+)$', str(record.get("source_url") or ""))
    for key in ("article", "article_body", "transcript", "pdf"):
        value = record.get(key)
        if isinstance(value, Mapping):
            body = []
            for row in value.get("paragraphs") or value.get("segments") or []:
                if isinstance(row, Mapping) and row.get("text"):
                    body.append((str(row.get('locator') or f"{key}:{row.get('index', len(passages)+len(body))}"), str(row["text"])))
            for field in ("full_text", "text", "body"):
                if isinstance(value.get(field), str):
                    body.extend((key, p) for p in re.split(r"\n\s*\n", value[field]) if p.strip())
            body = owned_pdf_abstracts(body)
            if cited_page and any(locator.startswith("pdf:") for locator, _ in body):
                page = int(cited_page[1])
                scoped = []
                for locator, text in body:
                    location = re.search(r':(?:page|pages):(\d+)(?:-(\d+))?$', locator)
                    if location and int(location[1]) <= page <= int(location[2] or location[1]):
                        scoped.append((locator, text))
                body = scoped
            passages.extend(owned_article_passages(body) if key in {'article','article_body'} else body)
    for key in ("full_text", "body_text", "extracted_text", "supporting_excerpt", "summary", "snippet", "title"):
        if isinstance(record.get(key), str) and record[key].strip():
            passages.extend((key, p) for p in re.split(r"\n\s*\n", record[key]) if p.strip())
    # Bounded overlapping chunks keep long sources searchable beyond the lead.
    chunks=[]
    for locator,text in passages:
        # A complete scientific abstract often defines a disease abbreviation
        # near its start and reports field validation near its end. Keep that
        # owned context together without joining unrelated paragraphs.
        for offset in range(0,len(text),2000):
            excerpt=text[offset:offset+2400]
            if offset+2400<len(text):
                endings=list(re.finditer(r'[.!?](?:["\u201d\u2019])?(?=\s|$)',excerpt))
                if endings and endings[-1].end()>=300:
                    excerpt=excerpt[:endings[-1].end()]
            chunks.append((locator,excerpt))
    return chunks


def _query_identifiers(plan, entities):
    """Whole verified cultivar codes; formatting variants do not change identity."""
    if not entities or not re.search(r'\d',plan.raw_query):
        return []
    positive=re.sub(r'(?<!\w)-("[^"]+"|[\w-]+)', '', plan.raw_query)
    positive=unicodedata.normalize('NFKC',positive).translate(str.maketrans({'–':'-','—':'-','‑':'-','‐':'-'}))
    owners={}
    for entity in entities.values():
        if entity.get('entity_type')!='variety':
            continue
        for alias in [entity.get('name') or '', *(entity.get('aliases') or [])]:
            alias=alias.strip("'\u2018\u2019\"")
            if not re.fullmatch(r'[A-Za-z]{1,16}[ -]?\d{1,6}(?:[ -]\d{1,6}){0,2}[A-Za-z]{0,2}',alias):
                continue
            pattern=re.compile(r'(?<!\w)'+r'[ -]*'.join(re.findall(r'[A-Za-z]+|\d+',alias))+r'(?!\w)',re.I)
            match=pattern.search(positive)
            if match:
                key=re.sub('[ -]','',alias).lower()
                group=owners.setdefault(key,{'pattern':pattern,'tokens':set(),'entities':{}})
                group['tokens'].update(normalize(match.group()).split())
                group['entities'][entity['id']]=entity
    return list(owners.values())


def match_record(record: Mapping[str, Any], plan: QueryPlan, *, entities: Mapping[str, dict[str, Any]] | None = None, _identifiers=None, _support_context=None) -> dict[str, Any] | None:
    passages = record_passages(record)
    linked = [((entities or {}).get(eid) or {}) for eid in record.get("entity_ids") or []]
    aliases = " ".join(str(v) for entity in linked for v in [entity.get("name"), *(entity.get("aliases") or [])] if v)
    text = normalize(" ".join(p for _, p in passages) + " " + aliases)
    words = set(text.split())
    if not plan.terms or any(p in text for p in plan.exclusions) or any(p not in text for p in plan.phrases):
        return None
    if re.search(r"\b(cybersecurity|smartphone|qnx)\b", text) and "blackberry" in plan.terms:
        return None
    if 'raspberry' in plan.terms and re.search(r'\braspberry pi\b',text):
        owned=' '.join(p for loc,p in passages if loc not in {'title','summary','snippet'})
        if not re.search(r'\b(fruit|cultivar|rubus|horticultur\w*|harvest\w*|growers?|berry crops?)\b',owned,re.I):
            return None
    stamp = str(record.get("published_date") or "")[:10]
    if plan.start or plan.end:
        if not stamp or (plan.start and stamp < plan.start) or (plan.end and stamp > plan.end):
            return None
    identifiers=_query_identifiers(plan,entities) if _identifiers is None else _identifiers
    # Unknown identifiers remain literal too: generic releases cannot stand in
    # for a requested cultivar code merely by meeting token-coverage thresholds.
    codes=re.findall(r'(?<!\w)(?:[A-Z]{2,8}[ -]?\d{2,6}[A-Za-z]?|[A-Za-z]{2,8}-\d{2,6}[A-Za-z]?)(?!\w)',plan.raw_query)
    for code in codes:
        if any(i['pattern'].fullmatch(code) for i in identifiers):continue
        pattern=r'\s*'.join(re.escape(t) for t in re.findall(r'[a-z]+|\d+',normalize(code)))
        if not re.search(r'(?<!\w)'+pattern+r'(?!\w)',text):return None
    from app.services.topic_support import support_context, identity_in_passage, cane_in_passage, trial_location_in_passage, passage_intent_supported, organizations_in_passage
    support=support_context(plan,entities,identifiers) if _support_context is None else _support_context
    for identifier in identifiers:
        literal=bool(identifier['pattern'].search(text))
        owners=identifier['entities']
        named=False
        if len(owners)==1:
            entity=next(iter(owners.values()))
            names=[entity.get('name') or '', *(entity.get('aliases') or [])]
            title=normalize(str(record.get('title') or ''))
            named=bool(entity['id'] in (record.get('entity_ids') or []))
            for name in filter(None,names):
                literal_name=re.escape(normalize(name))
                in_title=bool(re.search(r'(?<!\w)'+literal_name+r'(?!\w)',title))
                context=bool(re.search(r"\b(?:variety|cultivar|blackberry|raspberry|blueberry|strawberry) ['\"]?"+literal_name+r"(?!\w)|(?<!\w)"+literal_name+r" ['\"]?(?:blackberry|raspberry|blueberry|strawberry|variety|cultivar)\b",text))
                named=named or in_title or context
        if not literal and not named:
            return None
    evidence_traits: list[str] = []
    if plan.cane_type and plan.cane_type not in words:
        for entity in linked:
            for trait in (entity.get("attributes") or {}).get("traits") or []:
                if isinstance(trait, Mapping) and trait.get("trait") == "trait-fruiting-habit" and trait.get("evidence_ids") and plan.cane_type in normalize(str(trait.get("value") or "")).split():
                    evidence_traits.extend(trait["evidence_ids"])
        if not evidence_traits:
            return None
    crop_terms = set(plan.terms) & {"blackberry", "blueberry", "raspberry", "strawberry"}
    if crop_terms and not crop_terms.intersection(words) and not any("berry-" + crop in (record.get("berry_ids") or []) for crop in crop_terms):
        return None
    title_crops = set(normalize(str(record.get('title') or '')).split()) & {"blackberry", "blueberry", "raspberry", "strawberry"}
    if crop_terms and title_crops and not title_crops.intersection(crop_terms):
        # A different crop's story cannot borrow the requested crop from a
        # company overview and its cane type from an unrelated paragraph.
        owned_match = any(loc not in {'title','summary','snippet'} and crop_terms.intersection(normalize(p).split())
                          and (not plan.cane_type or plan.cane_type in normalize(p).split()) for loc,p in passages)
        if not owned_match:
            return None
    # Crop and cane are mandatory concepts; remaining literal terms use coverage.
    concepts = set(plan.terms) - crop_terms - {"floricane", "primocane"}
    # A requested document format is not mandatory wording in its contents.
    # Literal quoted phrases and exclusions have already been enforced above.
    if 'technical' in concepts and concepts & {'sheet','sheets'}:
        concepts -= {'technical','sheet','sheets'}
    # Geography is checked as an equivalent-place group below. Counting each
    # word of a country's long name here would reject its valid alias before
    # that check (for example a trial explicitly located in England).
    concepts -= set(support['place_terms'])
    concepts -= set().union(*(i['tokens'] for i in identifiers)) if identifiers else set()
    matched = concepts & words
    # Role intent is a lexical concept, not an entity alias or role approval.
    if concepts & {'breeder','breeding'} and words & {'breeder','breeding','bred','originator'}:
        matched.update(concepts & {'breeder','breeding'})
    if concepts and len(matched) / len(concepts) < 0.5:
        return None
    metadata_fields = {"title", "summary", "snippet"}
    requires_trial_location='license'not in plan.terms and any(t.startswith(('trial','experiment','evaluat','research'))for t in plan.terms)
    reference_subject = normalize(str(record["reference_subject"])) if record.get("reference_subject") else ""
    subject_pattern = r"(?<!\w)" + re.escape(reference_subject) + r"(?!\w)"
    named_reference = (
        record.get("provider") == "local_primary_citation" and reference_subject
        and re.search(subject_pattern, " ".join(plan.terms))
        and bool(title_crops.intersection(crop_terms))
    )
    body_matches = [(loc, p) for loc, p in passages if loc not in metadata_fields
                    and (cane_in_passage(p,plan.cane_type) or evidence_traits)
                    and (not support['identities'] or all(identity_in_passage(p,e) for e in support['identities']))
                    and (not crop_terms or crop_terms.intersection(normalize(p).split()) or bool(support['identities'])
                         or (named_reference and re.search(subject_pattern, normalize(p))))
                    and trial_location_in_passage(p,support['trial_places'],require_trial=requires_trial_location)
                    and organizations_in_passage(p,support['organizations'])
                    and passage_intent_supported(p,plan)]
    # A parent code in an offspring patent is useful lineage context, not a
    # description of the requested cultivar. Use only explicit denominations;
    # never guess a patent subject from a nearby number or company name.
    denomination=re.search(r'\b(?:plant|cultivar|plant variety)\s+named\s+[\'"\u2018\u201c]([^\'"\u2019\u201d]+)[\'"\u2019\u201d]',str(record.get('title')or''),re.I)
    if denomination and identifiers:
        compact=lambda value:re.sub(r'[^a-z0-9]','',normalize(value))
        subject=compact(denomination[1])
        owners=[next(iter(i['entities'].values())) for i in identifiers if len(i['entities'])==1]
        if owners and not all(any(compact(name)==subject for name in [owner.get('name')or'',*(owner.get('aliases')or[])]) for owner in owners):
            body_matches=[]
    matching = body_matches or [(loc,p) for loc,p in passages if loc in metadata_fields]
    milestone=re.compile(r'\b(introduc\w*|releas\w*|licen[sc]\w*|launch\w*|establish\w*|debut\w*|trial\w*|evaluat\w*|experiment\w*|results)\b',re.I)
    pruning=any(t.startswith('prun') for t in plan.terms)
    locator, passage = max(matching, key=lambda p: (sum(t in normalize(p[1]).split() for t in plan.terms) if pruning else bool(milestone.search(p[1])),sum(t in normalize(p[1]).split() for t in plan.terms)), default=("", ""))
    support_status='body_supported' if body_matches else 'scope_unverified'
    from app.services.research_source_holds import source_quote_hold
    quote_hold=source_quote_hold(record)
    if quote_hold:support_status='source_review_hold'
    # Retain adjacent source context when it states a licensing/release/trial
    # milestone (e.g. a cultivar introduction followed by its licence terms).
    position = next((i for i, p in enumerate(passages) if p == (locator, passage)), -1)
    if position >= 0 and locator not in metadata_fields and position + 1 < len(passages):
        next_locator, next_passage = passages[position + 1]
        if not locator.startswith('pdf:section:') and not next_locator.startswith('pdf:section:') and next_locator != locator and next_locator not in metadata_fields and next_passage.strip() not in passage and passage_intent_supported(next_passage,plan) and trial_location_in_passage(next_passage,support['trial_places'],require_trial=requires_trial_location) and re.search(r"\b(licen[sc]\w*|introduc\w*|releas\w*|trial\w*)\b", next_passage, re.I):
            passage += "\n\n" + next_passage
            locator += ";" + next_locator
    # Preserve a short framing statement (e.g. the year of a reproduced study)
    # through intervening Abstract headings. The publisher date alone does not
    # date the underlying research.
    reproduced_study_year=None
    if position > 0 and locator not in metadata_fields:
        context=[]
        for previous_locator,previous in reversed(passages[max(0,position-2):position]):
            if previous_locator in metadata_fields or previous_locator==locator:break
            if len(previous)<250 and (re.search(r'\b(?:19|20)\d{2}\b',previous) or previous.strip().casefold()=='abstract'):
                context.insert(0,(previous_locator,previous))
            else:break
        if any(re.search(r'\b(?:19|20)\d{2}\b',p) for _,p in context):
            passage='\n\n'.join([*(p for _,p in context),passage])
            locator=';'.join([*(loc for loc,_ in context),locator])
            framing=' '.join(p for _,p in context)
            year=re.search(r'\b((?:19|20)\d{2})\s+(?:study|research|paper)\b',framing,re.I)
            if year:reproduced_study_year=int(year[1])
    title = str(record.get("title") or "")
    event = bool(_EVENT.search(title) or re.search(r"\b(introduc\w*|releas\w*|licen[sc]\w*|launch\w*)\b", passage, re.I))
    if 'license' in plan.terms:
        event = event and any(loc not in metadata_fields and re.search(r'\blicen[sc]\w*\b',p,re.I) for loc,p in passages)
    if re.search(r"\b(guide|prun\w*|growing|cultivars for)\b", title, re.I) and not re.search(r"\b(releas\w*|licen[sc]\w*|trial\w*)\b", title, re.I):
        event = False
    if pruning and body_matches:event=True
    if re.search(r'\b(?:review|current status|future directions)\b',title,re.I):
        event=False  # Publication of a review does not re-date its cited trials.
    score = 10 * len(set(plan.terms) & words) + 5 * event + 20 * bool(_EVENT.search(title)) + (2 if locator not in {"title", "snippet", "summary"} else 0)
    relevance = "direct" if event else "background"
    if reproduced_study_year and str(record.get('published_date') or '')[:4].isdigit() and reproduced_study_year<int(record['published_date'][:4]):
        relevance='background'
    if support_status != "body_supported":relevance="adjacent"
    if plan.cane_type == "floricane" and "primocane" in normalize(str(record.get("title") or "")).split():
        # A primocane release may mention floricanes only as a comparison.
        # Keep actual floricane-crop trial evidence eligible.
        floricane_trial = any(re.search(r"floricane[- ](?:crop|fruit|yield)", p, re.I) and re.search(r"trial|study|result|evaluat", p, re.I) for _, p in passages)
        if not floricane_trial:
            relevance = "adjacent"
    if (
        plan.cane_type == "floricane" and "variety" in plan.terms
        and "crop" not in plan.terms and "primocane" not in plan.terms
        and re.search(r"\bprimocane[- ]fruiting\b", passage, re.I)
        and not re.search(r"\bfloricane[- ]fruiting\b", passage, re.I)
    ):
        # A guide may discuss the second-year crop of a primocane cultivar.
        # Keep that passage available as context for a strict variety query.
        relevance = "adjacent"
    return {"score": score, "passage": passage, "passage_locator": locator, "relevance": relevance, "support_status":support_status, "source_review_hold":quote_hold['reason'] if quote_hold else None, "match_reason": "Verified fruiting-habit evidence" if evidence_traits else "Matched verified cultivar-code alias" if identifiers else "Matched source passage", "classification_evidence_ids": sorted(set(evidence_traits))}


def retrieve(records: Iterable[dict[str, Any]], plan: QueryPlan, *, entities: Mapping[str, dict[str, Any]] | None = None, limit: int = 40) -> list[dict[str, Any]]:
    from app.services.article_dedup import normalize_canonical_url
    from urllib.parse import urlsplit
    official_hosts=set()
    for entity in (entities or {}).values():
        value=(entity.get('attributes')or{}).get('official_domain')
        if not isinstance(value,str):continue
        try:
            parsed=urlsplit(value)
            if parsed.scheme in {'https','http'} and parsed.hostname and not parsed.username:
                official_hosts.add(parsed.hostname.casefold().removeprefix('www.'))
        except ValueError:pass
    def official_publisher(row):
        try:return (urlsplit(str(row.get('source_url')or row.get('url')or'')).hostname or '').casefold().removeprefix('www.')in official_hosts
        except ValueError:return False
    rows = []
    identifiers = _query_identifiers(plan,entities)
    from app.services.topic_support import support_context
    context=support_context(plan,entities,identifiers)
    for record in records:
        match = match_record(record, plan, entities=entities, _identifiers=identifiers, _support_context=context)
        if match:
            rows.append({**record, **match})
    # Prefer an existing registered publisher over a repost/index when scope
    # and publication date tie. This is source provenance, not claim approval
    # or a newly inferred company/variety relationship.
    rows.sort(key=lambda r: ({"direct": 2, "background": 1, "adjacent": 0}[r["relevance"]], str(r.get("published_date") or ""), official_publisher(r), r["score"]), reverse=True)
    seen: set[str] = set()
    seen_bodies: set[str] = set()
    unique = []
    for row in rows:
        identity = normalize_canonical_url(row.get("source_url") or row.get("url")) or str(row.get("id"))
        body_identity = str(row.get("source_version") or "")
        if identity not in seen and (not body_identity or body_identity not in seen_bodies):
            seen.add(identity)
            if body_identity:
                seen_bodies.add(body_identity)
            unique.append(row)
    return unique[:limit]
