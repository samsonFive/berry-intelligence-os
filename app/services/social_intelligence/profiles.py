"""Registry-linked suggestions only. No automatic new-source/query activation."""
from .extraction import VOCAB
from pydantic import Field
from .model import Strict

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
