"""Deleted-source exclusion for new outputs; canonical history stays intact.

Only explicit deleted receipts seed exclusions. Unavailable/restricted sources
are separate states. Fixture deletion cannot invalidate real evidence.
"""
from contextlib import closing
from pathlib import Path
import sqlite3
import json

DEPENDENCY_FIELDS = frozenset({
    'evidence_ids', 'evidence_id', 'supporting_evidence_ids', 'parent_evidence_id',
    'source_evidence_id', 'fact_ids', 'fact_id', 'signal_ids', 'signal_id',
    'assessment_ids', 'assessment_id', 'recommendation_ids', 'supporting_ids',
    'source_ids', 'citation_ids',
})

def deleted_sources(inbox):
    """Read existing private receipts without creating a database or migration."""
    path=Path(inbox)/'social'/'observations.sqlite3'
    if not path.is_file(): return []
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=10)) as db:
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        receipts=[]
        if 'source_deletions' in tables:
            receipts=[dict(zip(('id','source','native_id','mode','media_id'),r)) for r in db.execute(
                'SELECT evidence_id,source,native_id,mode,media_id FROM source_deletions WHERE mode != ?',('fixture',))]
        # Existing databases may predate durable deletion receipts. Only explicit
        # deletion events/tombstones qualify; removed=1 alone also means outage.
        legacy=[]
        if {'observations','audit'} <= tables:
            legacy.extend((key,payload,'') for key,payload in db.execute(
                "SELECT DISTINCT o.id,o.payload FROM observations o JOIN audit a ON a.evidence_id=o.id WHERE o.removed=1 AND a.event='removal:deleted'"))
        if {'observations','media_tombstones'} <= tables:
            legacy.extend(db.execute("SELECT o.id,o.payload,m.media_id FROM observations o JOIN media_tombstones m ON m.evidence_id=o.id WHERE m.state='deleted'"))
        for key,payload,media_id in legacy:
            item=json.loads(payload)
            if item['mode']!='fixture':receipts.append({'id':key,'source':item['source'],'native_id':item['native_id'],'mode':item['mode'],'media_id':media_id})
        return list({(r['id'],r['media_id']):r for r in receipts}.values())

def dependencies(value):
    result=set()
    if isinstance(value,dict):
        for key,item in value.items():
            if key in DEPENDENCY_FIELDS:
                if isinstance(item,str):result.add(item)
                elif isinstance(item,list):result.update(v for v in item if isinstance(v,str))
            if isinstance(item,(dict,list)):result.update(dependencies(item))
    elif isinstance(value,list):
        for item in value:
            if isinstance(item,(dict,list)):result.update(dependencies(item))
    return result

def exclusion_ids(records, receipts):
    """Conservative transitive closure, including nested briefing dependencies.

Mixed-support outputs are held too: removal must not leave an unreassessed
claim appearing supported merely because another citation remains.
"""
    receipts=[r for r in receipts if r.get('mode')!='fixture']
    blocked={r['id'] for r in receipts}
    native={(r['source'],r['native_id']) for r in receipts}
    for record in records:
        origin=record.get('social_observation') or {}
        if origin.get('mode')!='fixture' and ((origin.get('source'),origin.get('native_id')) in native or origin.get('id') in blocked):
            blocked.add(record['id'])
    edges={r['id']:dependencies(r) for r in records if r.get('id')}
    changed=True
    while changed:
        changed=False
        for key,refs in edges.items():
            if key not in blocked and refs & blocked:
                blocked.add(key);changed=True
    return frozenset(blocked)

def eligible_records(records, blocked):
    return [r for r in records if r.get('id') not in blocked and not (dependencies(r) & blocked)]


def output_exclusions(data_dir, inbox, *, repositories=None):
    """Resolve against canonical IDs, without writing canonical trust state."""
    if inbox is None:return frozenset()
    receipts=deleted_sources(inbox)
    if not receipts:return frozenset()
    if repositories is None:
        from app.composition import get_repositories
        repositories=get_repositories(Path(data_dir))
    records=[]
    for name in ('evidence','facts','signals','assessments','recommendations','relationships'):
        records.extend(getattr(repositories,name).list())
    return exclusion_ids(records,receipts)

def for_new_outputs(records, data_dir, inbox):
    return eligible_records(records,output_exclusions(data_dir,inbox))


class OutputRepositoryView:
    """Read-only list projection; get() retains canonical history for review."""
    def __init__(self, repository, blocked):
        self.repository=repository;self.blocked=blocked
    def list(self, **filters):
        return eligible_records(self.repository.list(**filters),self.blocked)
    def get(self, key):
        return self.repository.get(key)

class OutputRepositories:
    def __init__(self, repositories, blocked):
        self.repositories=repositories;self.blocked=blocked
    def __getattr__(self, name):
        repository=getattr(self.repositories,name)
        if name in ('evidence','facts','signals','assessments','recommendations','relationships'):
            return OutputRepositoryView(repository,self.blocked)
        return repository
