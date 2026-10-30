"""Offline citation fidelity checks, not a substitute for source/claim review."""
import hashlib
import re
from app.services.topic_retrieval import record_passages

_METADATA={'title','summary','snippet'}


def audit_semantic_reviews(query, packet, sections, reviews):
    """Account for independently inspected annotations; never infer entailment.

    Each disposition is bound to its query, section prose, source version and
    exact excerpt. Missing or stale reviews remain open, including when a
    mechanical quotation check passes. This does not verify source truth.
    """
    sources={r['id']:r for r in packet.get('topic_sources',[])}
    rows=[]
    for section in sections:
        if section.section_id not in {'topic_findings','topic_background'}:
            continue
        for source_id in section.citation_ids:
            source=sources.get(source_id,{})
            candidates=[r for r in reviews if r.get('query')==query and r.get('section_id')==section.section_id and r.get('source_id')==source_id]
            review=candidates[0] if len(candidates)==1 else {}
            bound=bool(review.get('reason') and review.get('reviewer') and review.get('checked_at')
                       and review.get('disposition') in {'supported','context_only','needs_review'}
                       and bool(source.get('source_version'))
                       and review.get('source_version')==source.get('source_version')
                       and review.get('passage_sha256')==hashlib.sha256(str(source.get('passage') or '').encode()).hexdigest()
                       and review.get('section_sha256')==hashlib.sha256(section.prose.encode()).hexdigest())
            rows.append({'section_id':section.section_id,'source_id':source_id,
                         'disposition':review['disposition'] if bound else 'unreviewed',
                         'reason':review['reason'] if bound else 'Missing, duplicate or stale semantic review'})
    return {'review_scope':'Inspected quotation meaning and section/topic context; not independent source-truth verification',
            'reviewed':sum(r['disposition']!='unreviewed' for r in rows),
            'unreviewed':sum(r['disposition']=='unreviewed' for r in rows),
            'issues':sum(r['disposition']=='needs_review' for r in rows),'items':rows}


def audit_topic_citations(packet, sections, captured_records):
    sources={r['id']:r for r in packet.get('topic_sources',[])}
    failures=[];checked=set();quotes=0
    if len(sources)!=len(packet.get('topic_sources',[])):
        failures.append({'section_id':None,'source_id':None,'reason':'duplicate source snapshot IDs'})
    for section in sections:
        for source_id in section.citation_ids:
            row=sources.get(source_id);original=captured_records.get(source_id)
            def fail(reason):failures.append({'section_id':section.section_id,'source_id':source_id,'reason':reason})
            if not row or not original:
                fail('missing source snapshot');continue
            if section.section_id not in {'topic_findings','topic_background'}:
                continue  # Identity references and undated leads are not source quotations.
            passages=[(loc,text) for loc,text in record_passages(original) if loc not in _METADATA]
            locators=str(row.get('passage_locator') or '').split(';')
            located=[text for loc,text in passages if loc in locators]
            if not located or not all(loc in {p[0] for p in passages} for loc in locators):
                fail('missing or metadata-only locator');continue
            normalize=lambda value:' '.join(str(value).split())
            if not row.get('passage') or normalize(row['passage']) not in normalize(' '.join(located)):
                fail('excerpt does not match located captured text');continue
            if row.get('origin')=='web':
                body='\n'.join(str(p.get('text') or '') for p in (original.get('article') or {}).get('paragraphs',[]))
            else:
                body='\n\n'.join(text for _,text in passages)
            actual=hashlib.sha256(body.encode()).hexdigest() if body else None
            if not row.get('source_version') or actual!=row['source_version']:
                fail('captured source version mismatch');continue
            expected=f"[{source_id}] {row.get('source_name') or 'Source'} ({row.get('published_date') or 'publication date unknown'}) — source excerpt: “{row['passage']}”\n{row.get('source_url') or ''}"
            if expected not in section.prose:
                fail('report quotation or attribution changed');continue
            if row.get('source_url')!=original.get('source_url') or row.get('published_date')!=original.get('published_date'):
                fail('source identity or publication date changed');continue
            plan=packet.get('topic_research',{}).get('plan',{})
            stamp=row.get('published_date') or ''
            if (plan.get('start') and stamp<plan['start']) or (plan.get('end') and stamp>plan['end']):
                fail('quoted source outside explicit publication scope');continue
            if row.get('origin')=='web' and row.get('trust_class')!='LIVE / UNREVIEWED':
                fail('web source review status elevated');continue
            quotes+=1;checked.add(source_id)
        if section.section_id in {'topic_findings','topic_background'}:
            inline=re.findall(r'^\[([^\]\n]+)\]',section.prose,re.M)
            for source_id in inline:
                if source_id not in section.citation_ids:
                    failures.append({'section_id':section.section_id,'source_id':source_id,'reason':'undeclared inline citation'})
    return {'version':1,'audit_scope':'Quotation fidelity, source version, locator, attribution, date scope and web review label; not source truth or complete citation semantics',
            'quoted_sources_checked':len(checked),'quotations_checked':quotes,'failures':failures,'passed':not failures}
