"""Registry-linked suggestions only. No automatic new-source/query activation."""
from .extraction import VOCAB
from pydantic import Field
from .model import Strict
import hashlib
import json
from datetime import datetime, timezone
from app.services.analyst_state_io import atomic_json, serialized_write
from app.services.watchlist import state_path
from .aggregate import selection, href, bundle

class WatchProfile(Strict):
    schema_version:int=1
    entity_id:str
    aliases:list[str]=Field(default_factory=list,max_length=15)
    handles:list[str]=Field(default_factory=list,max_length=10)
    transliterations:list[str]=Field(default_factory=list,max_length=15)
    hashtags:list[str]=Field(default_factory=list,max_length=15)
    exclusions:list[str]=Field(default_factory=list,max_length=15)
    qualifiers:list[str]=Field(default_factory=list,max_length=10)
    languages:list[str]=Field(default_factory=list,max_length=10)
    markets:list[str]=Field(default_factory=list,max_length=10)
    priority:int=Field(default=3,ge=1,le=5)
    query_version:str='social-watch-1'
    cadence_seconds:int=Field(default=86400,ge=3600)
    review:str='suggestion; analyst review required'
    enabled:bool=False

def suggest(entity):
    aliases=[a if isinstance(a,str) else a.get('name','') for a in entity.get('aliases',[])]
    profile=WatchProfile(entity_id=entity['id'],aliases=[entity['name'],*aliases][:15],
                         qualifiers=['fruit','berry'] if entity.get('entity_type')=='variety' else [],
                         exclusions=['phone','smartphone','Android'] if entity['id']=='berry-blackberry' else [],
                         languages=['en','es','pt','zh','ja'])
    return profile.model_dump()

def bounded_queries(profile,entities):
    p=WatchProfile.model_validate(profile)
    if p.entity_id not in {e['id'] for e in entities}:
        raise ValueError('Watch profile must reference an existing canonical entity')
    if p.enabled and p.review!='analyst-approved':
        raise ValueError('Suggestions cannot activate collection')
    return [' '.join([name,*p.qualifiers]) for name in p.aliases[:5]]

class SavedProfile(Strict):
    id:str=Field(pattern=r'^social-view-[a-f0-9]{24}$')
    name:str=Field(min_length=1,max_length=80)
    filters:dict[str,str]
    revision:int=Field(ge=1)
    updated_at:str
    reviewed_by:str=Field(default='',max_length=80)
    reviewed_at:str|None=None
    targets:list[WatchProfile]=Field(default_factory=list,max_length=1)
    monitoring:bool=False

def _state(inbox_dir):
    path=state_path(inbox_dir)
    try:
        state=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'watches':[]}
        if not isinstance(state,dict) or not isinstance(state.get('social_profiles',[]),list):raise ValueError()
        for row in state.get('social_profiles',[]):
            profile=SavedProfile.model_validate(row)
            if selection(profile.filters)!=profile.filters or profile.monitoring or any(p.enabled for p in profile.targets):raise ValueError()
        return state
    except (OSError,ValueError) as exc:
        raise ValueError('Saved social views cannot be read; existing settings were left unchanged') from exc

def saved_profiles(inbox_dir):
    return [{**row,'url':href(row['filters'],saved=row['id'])} for row in _state(inbox_dir).get('social_profiles',[])]

def matching_profiles(inbox_dir,row):
    return [p for p in saved_profiles(inbox_dir) if bundle([row],[],p['filters'])['count']==1]

@serialized_write
def save_profile(inbox_dir,name,filters,entities,*,reviewed_by='',revision=None):
    if not isinstance(name,str) or not name.strip() or len(name.strip())>80:raise ValueError('Name must contain 1–80 characters')
    if not isinstance(reviewed_by,str) or len(reviewed_by.strip())>80:raise ValueError('Reviewer name is too long')
    if not isinstance(filters,dict):raise ValueError('Expected social filters')
    if revision is not None and (not isinstance(revision,int) or isinstance(revision,bool)):raise ValueError('Invalid saved view revision')
    if set(filters)-set(selection({})):raise ValueError('Unknown social filter')
    f=selection(filters);name=name.strip();reviewed_by=reviewed_by.strip()
    entity=next((e for e in entities if e['id']==f['entity']),None) if f['entity'] else None
    if f['entity'] and (not entity or entity.get('entity_type') not in ('company','variety')):raise ValueError('Company / variety must exist in the registry')
    stamp=datetime.now(timezone.utc).isoformat()
    key='social-view-'+hashlib.sha256(name.casefold().encode()).hexdigest()[:24]
    state=_state(inbox_dir);rows=state.get('social_profiles',[])
    old=next((r for r in rows if r['id']==key),None)
    if old and revision!=old['revision']:raise ValueError('This name is already saved; reopen it before updating')
    if not old and revision is not None:raise ValueError('Saved view no longer exists')
    if not old and len(rows)>=50:raise ValueError('Saved view limit is 50')
    targets=[suggest(entity)] if entity else []
    for target in targets:
        bounded_queries(target,entities)
        if reviewed_by:target['review']='analyst-approved'
    row=SavedProfile(id=key,name=name,filters=f,revision=old['revision']+1 if old else 1,updated_at=stamp,
        reviewed_by=reviewed_by,reviewed_at=stamp if reviewed_by else None,targets=targets).model_dump()
    atomic_json(state_path(inbox_dir),{**state,'social_profiles':[r for r in rows if r['id']!=key]+[row]})
    return {**row,'url':href(f,saved=key)}

@serialized_write
def remove_profile(inbox_dir,key,revision):
    if not isinstance(revision,int) or isinstance(revision,bool):raise ValueError('Invalid saved view revision')
    state=_state(inbox_dir);rows=state.get('social_profiles',[])
    old=next((r for r in rows if r['id']==key),None)
    if not old or revision!=old['revision']:raise ValueError('Saved view changed or no longer exists')
    atomic_json(state_path(inbox_dir),{**state,'social_profiles':[r for r in rows if r['id']!=key]})
