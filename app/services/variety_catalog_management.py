"""Explicit catalog identity actions; no automatic trait, rights or role approval."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import re

from app.services.map_regions import public_source_url
from app.services.variety_universe.identity import fold_identity, resolve_identity

BERRIES={'berry-blueberry','berry-raspberry','berry-strawberry','berry-blackberry'}
PRIMARY={'tier_1_registry','tier_1_breeder_catalog','tier_1_patent_pvr','tier_1_national_register','tier_2_technical_sheet'}


def promotion_digest(candidate):
    from app.services.variety_catalog_handoff import decision_digest
    return hashlib.sha256(json.dumps([decision_digest(candidate),candidate.get('source_url'),candidate.get('source_tier'),candidate.get('breeder_code'),candidate.get('denomination'),candidate.get('trade_name')],ensure_ascii=False).encode()).hexdigest()


def surfaces(candidate):
    return {fold_identity(str(value)) for value in [candidate.get('candidate_name'),candidate.get('denomination'),candidate.get('breeder_code'),candidate.get('trade_name'),*(candidate.get('aliases') or [])] if value and len(fold_identity(str(value)))>=3}


def promotion_plan(candidate, *, varieties, candidates=()):
    name=str(candidate.get('candidate_name') or '').strip();berry=candidate.get('berry_id')
    reason=''
    resolution=resolve_identity(candidate,varieties)
    if candidate.get('status')=='rejected' or candidate.get('identity_state')!='distinct':reason='Identity is unresolved, rejected or may already be represented.'
    elif not name or berry not in BERRIES:reason='A literal name and established berry are required.'
    elif resolution.get('matches'):reason='A catalog name, code or registration may already represent this identity.'
    elif candidate.get('source_tier') not in PRIMARY:reason='A clear primary or technical source is still needed.'
    elif not public_source_url(candidate.get('source_url')):reason='A public identity source is required.'
    elif any(ch.isdigit() for ch in name):reason='A coded selection needs individual denomination/alias review.'
    elif any(other.get('id')!=candidate.get('id') and other.get('status')!='rejected' and other.get('berry_id')==berry and surfaces(candidate)&surfaces(other) for other in candidates):reason='Another candidate shares a name, commercial label or code; reconcile them first.'
    return dict(ready=not reason,reason=reason,name=name,berry_id=berry,source_url=public_source_url(candidate.get('source_url')) or '',digest=promotion_digest(candidate))


def canonical_record(candidate, *, varieties, candidates=(), actor, authorization):
    plan=promotion_plan(candidate,varieties=varieties,candidates=candidates)
    if not plan['ready']:raise ValueError(plan['reason'])
    if not actor.strip() or not authorization.strip():raise ValueError('An explicit reviewer and authorization are required.')
    slug=re.sub('[^a-z0-9]+','-',fold_identity(plan['name'])).strip('-')[:65] or 'cultivar'
    suffix=hashlib.sha256((plan['berry_id']+'|'+candidate['id']).encode()).hexdigest()[:8]
    return dict(id='variety-'+slug+'-'+suffix,record_type='entity',entity_type='variety',name=plan['name'],aliases=[],status='unverified',
                description='Catalog identity admitted from the cited source. Agronomic, commercial and legal claims remain subject to review.',
                roles=['cultivar'],berry_ids=[plan['berry_id']],evidence_ids=[],fact_ids=[],relationship_ids=[],attributes={
                    'catalog_candidate_id':candidate['id'],
                    'identity_review':dict(reviewer=actor,reviewed_at=datetime.now(timezone.utc).isoformat(),authorization=authorization,source_url=plan['source_url'],source_label=candidate.get('source_label') or '',candidate_name=plan['name'])})


def set_removed(record, *, removed, actor):
    if record.get('entity_type')!='variety':raise ValueError('This action only applies to varieties.')
    updated=deepcopy(record);attrs=updated.setdefault('attributes',{})
    if removed:
        if not attrs.get('catalog_removed'):
            attrs['catalog_removal']={'previous_status':record.get('status','unverified'),'actor':actor,'removed_at':datetime.now(timezone.utc).isoformat()}
        attrs['catalog_removed']=True;updated['status']='inactive'
    else:
        updated['status']=(attrs.get('catalog_removal') or {}).get('previous_status','unverified');attrs.pop('catalog_removed',None)
    return updated
