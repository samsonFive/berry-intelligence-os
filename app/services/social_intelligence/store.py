"""SQLite private acquisition index with transactional page/checkpoint durability.

Canonical Evidence handoff uses existing inbox drafts. SQLite is not a second
trusted corpus. Source/mode/native ID identity prevents fixture contamination.
"""
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit
from .model import validate_intake
from .extraction import analyze

def now():
    return datetime.now(timezone.utc).isoformat()

def identity(item):
    return 'ev-social-' + hashlib.sha256(f"{item['source']}:{item['mode']}:{item['native_id']}".encode()).hexdigest()[:24]

def media_reference_key(source,url):
    """Only inspected Facebook CDN paths identify signed photo variants."""
    if not url:return None
    parts=urlsplit(url)
    if source=='facebook' and (parts.hostname or '').endswith('.fbcdn.net') and parts.path.startswith('/v/') and parts.path.lower().endswith(('.jpg','.jpeg','.png','.webp')):
        return 'facebook-photo:'+parts.path
    return url

class Store:
    def __init__(self, inbox):
        self.inbox = Path(inbox)
        self.path = self.inbox / 'social' / 'observations.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS observations(id TEXT PRIMARY KEY, payload TEXT NOT NULL, analysis TEXT NOT NULL, removed INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS source_deletions(evidence_id TEXT, source TEXT, native_id TEXT, mode TEXT, media_id TEXT, deleted_at TEXT, PRIMARY KEY(evidence_id,media_id));
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, evidence_id TEXT, event TEXT, at TEXT);
            CREATE TABLE IF NOT EXISTS media_tombstones(evidence_id TEXT, media_id TEXT, state TEXT, PRIMARY KEY(evidence_id,media_id));
            CREATE TABLE IF NOT EXISTS collection_receipts(evidence_id TEXT, method TEXT, query_version TEXT, collected_at TEXT, PRIMARY KEY(evidence_id,method,query_version,collected_at));
            CREATE TABLE IF NOT EXISTS media_url_tombstones(evidence_id TEXT, url_hash TEXT, state TEXT, PRIMARY KEY(evidence_id,url_hash));
            PRAGMA user_version=1;
            ''')
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA secure_delete=ON')
        return db
    def ingest(self, payloads, entities, *, mode=None, job=None):
        rows = [validate_intake(p,mode=mode) for p in payloads]
        prepared = [(identity(p),p,analyze(p,entities)) for p in rows]
        with closing(self.connect()) as db, db:
            for key,p,a in prepared:
                existing = db.execute('SELECT payload,analysis,removed FROM observations WHERE id=?',(key,)).fetchone()
                if existing and existing[2]:
                    continue # Tombstones prevent deleted content resurrection on replay.
                tombstones=dict(db.execute('SELECT media_id,state FROM media_tombstones WHERE evidence_id=?',(key,)))
                url_tombstones=dict(db.execute('SELECT url_hash,state FROM media_url_tombstones WHERE evidence_id=?',(key,)))
                if tombstones or url_tombstones:
                    for media in p['media']:
                        reference=media_reference_key(p['source'],media['source_url'])
                        digest=hashlib.sha256(reference.encode()).hexdigest() if reference else None
                        legacy_digest=hashlib.sha256(media['source_url'].encode()).hexdigest() if media['source_url'] else None
                        state=tombstones.get(media['id']) or url_tombstones.get(digest) or url_tombstones.get(legacy_digest)
                        if state:
                            media.update(state=state,source_url=None,literal=[],content_hash=None,object_ref=None)
                    a=analyze(p,entities)
                if existing:
                    old = json.loads(existing[0]); prior = json.loads(existing[1])
                    # Retain established attachment IDs when an inspected CDN
                    # variant changes; review locators and removal use these IDs.
                    old_refs={media_reference_key(p['source'],m['source_url']):m for m in old['media'] if m['source_url']}
                    for media in p['media']:
                        retained=old_refs.get(media_reference_key(p['source'],media['source_url']))
                        if retained:media['id']=retained['id']
                    multiple_methods = db.execute('SELECT 1 FROM collection_receipts WHERE evidence_id=? AND method<>? LIMIT 1',(key,p['discovery_method'])).fetchone()
                    if old['discovery_method'] != p['discovery_method'] or multiple_methods:
                        # A different provider's partial response is not a source
                        # deletion. Preserve observed attachments across providers.
                        incoming_ids={m['id'] for m in p['media']}
                        incoming_urls={media_reference_key(p['source'],m['source_url']) for m in p['media'] if m['source_url']}
                        for media in old['media']:
                            reference=media_reference_key(p['source'],media['source_url'])
                            if media['id'] not in incoming_ids and (not reference or reference not in incoming_urls):
                                if len(p['media']) < 30:
                                    p['media'].append(media)
                                    incoming_ids.add(media['id'])
                                    if reference:incoming_urls.add(reference)
                        a=analyze(p,entities)
                    # A search summary omitting pictures does not invalidate a
                    # separately captured full-post reference. Explicit removal
                    # tombstones still govern these durable supplements.
                    incoming={m['id'] for m in p['media']}
                    supplements=[m for m in old['media'] if m['id'].startswith('detail-') and m['id'] not in incoming]
                    if supplements:
                        p['media']+=supplements
                        p=validate_intake(p)
                        a=analyze(p,entities)
                    for media in p['media']:
                        retained=next((m for m in old['media'] if m['id']==media['id']),None)
                        if retained and retained.get('object_ref') and media['id'] not in tombstones:
                            media.update(object_ref=retained['object_ref'],content_hash=retained['content_hash'])
                    if prior.get('reviewed'):
                        a = prior # Preserve analyst corrections; changed source stays visibly flagged.
                        a['source_changed'] = old['text'] != p['text'] or old['media'] != p['media']
                for media in p['media']:
                    if media['state']=='deleted':
                        db.execute('INSERT OR IGNORE INTO source_deletions VALUES(?,?,?,?,?,?)',(key,p['source'],p['native_id'],p['mode'],media['id'],now()))
                db.execute('INSERT INTO observations VALUES(?,?,?,0) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,analysis=excluded.analysis', (key,json.dumps(p,ensure_ascii=False),json.dumps(a,ensure_ascii=False)))
                if existing:
                    db.execute('INSERT OR IGNORE INTO collection_receipts VALUES(?,?,?,?)',(key,old['discovery_method'],old['query_version'],old['collected_at']))
                db.execute('INSERT OR IGNORE INTO collection_receipts VALUES(?,?,?,?)',(key,p['discovery_method'],p['query_version'],p['collected_at']))
                db.execute('INSERT INTO audit(evidence_id,event,at) VALUES(?,?,?)',(key,'intake:'+p['mode'],now()))
            if job:
                db.execute('INSERT OR REPLACE INTO jobs VALUES(?,?)',(job['id'],json.dumps(job)))
        return [p[0] for p in prepared]
    def collection_receipts(self,key):
        """Content-free acquisition history; provider changes do not erase it."""
        with closing(self.connect()) as db:
            rows=db.execute('SELECT method,query_version,collected_at FROM collection_receipts WHERE evidence_id=? ORDER BY collected_at,method',(key,)).fetchall()
        return [{'method':m,'query_version':q,'collected_at':at} for m,q,at in rows]
    def records(self, *, mode=None):
        with closing(self.connect()) as db:
            rows = db.execute('SELECT id,payload,analysis FROM observations WHERE removed=0 ORDER BY id').fetchall()
        records=[{**json.loads(p),'id':key,'analysis':json.loads(a)} for key,p,a in rows if not mode or json.loads(p)['mode']==mode]
        from .output_eligibility import deleted_sources
        receipts=deleted_sources(self.inbox)
        ids={r['id'] for r in receipts};native={(r['source'],r['native_id']) for r in receipts}
        for record in records:
            if record['mode']!='fixture' and (record['id'] in ids or (record['source'],record['native_id']) in native):
                record['output_excluded']=True
        return records
    def jobs(self):
        with closing(self.connect()) as db:
            return [json.loads(p) for (p,) in db.execute('SELECT payload FROM jobs ORDER BY id')]
    def job(self,key):
        return next((p for p in self.jobs() if p['id']==key),None)
    def save_job(self,job):
        with closing(self.connect()) as db, db:
            db.execute('INSERT OR REPLACE INTO jobs VALUES(?,?)',(job['id'],json.dumps(job)))
    def refresh_proposals(self, keys, entities):
        """Explicit offline reanalysis; source bytes and human decisions stay intact.

        Removed/reviewed observations are skipped. Missing IDs abort the whole
        transaction, preventing a partial refresh from looking complete.
        """
        if (not isinstance(keys,list) or len(keys)>100
                or any(not isinstance(k,str) for k in keys) or len(set(keys))!=len(keys)):
            raise ValueError('At most 100 distinct observation IDs required')
        changed=[]
        with closing(self.connect()) as db, db:
            for key in keys:
                row=db.execute('SELECT payload,analysis,removed FROM observations WHERE id=?',(key,)).fetchone()
                if not row:
                    raise ValueError('Unavailable observation')
                payload, previous, removed=row
                old=json.loads(previous)
                if removed or old.get('reviewed'):
                    continue
                updated=analyze(json.loads(payload),entities)
                if updated==old:
                    continue
                db.execute('INSERT INTO audit(evidence_id,event,at) VALUES(?,?,?)',
                           (key,json.dumps({'proposal_refresh_before':old,'new_version':updated['version']},ensure_ascii=False),now()))
                db.execute('UPDATE observations SET analysis=? WHERE id=?',
                           (json.dumps(updated,ensure_ascii=False),key))
                changed.append(key)
        return changed
    def correct(self,key,analysis,reviewer):
        if not reviewer or len(reviewer)>100:
            raise ValueError('Reviewer required')
        with closing(self.connect()) as db, db:
            old = db.execute('SELECT analysis FROM observations WHERE id=? AND removed=0',(key,)).fetchone()
            if not old:
                raise ValueError('Unavailable observation')
            updated = deepcopy(analysis); updated.update(reviewed=True,reviewer=reviewer,reviewed_at=now())
            db.execute('INSERT INTO audit(evidence_id,event,at) VALUES(?,?,?)',(key,json.dumps({'correction_before':json.loads(old[0]),'reviewer':reviewer}),now()))
            db.execute('UPDATE observations SET analysis=? WHERE id=?',(json.dumps(updated),key))
    def remove(self,key, *, state='deleted', media_id=None):
        if state not in ('deleted','unavailable','restricted'):
            raise ValueError('Invalid removal state')
        with closing(self.connect()) as db, db:
            row = db.execute('SELECT payload FROM observations WHERE id=?',(key,)).fetchone()
            if not row:
                raise ValueError('Unavailable observation')
            p = json.loads(row[0])
            objects=[m.get('object_ref') for m in p['media'] if not media_id or m['id']==media_id]
            mode=p['mode']
            if media_id:
                found = False
                for m in p['media']:
                    if m['id']==media_id:
                        if m['source_url']:
                            reference=media_reference_key(p['source'],m['source_url'])
                            db.execute('INSERT OR REPLACE INTO media_url_tombstones VALUES(?,?,?)',(key,hashlib.sha256(reference.encode()).hexdigest(),state))
                        m.update(state=state,source_url=None,literal=[],content_hash=None,object_ref=None); found=True
                if not found:
                    raise ValueError('Unknown attachment')
            else:
                p.update(text='',translation=None,media=[],engagement={})
            # Derived proposals are cleared immediately. Caller may explicitly
            # reprocess remaining text; no cached summaries retain media output.
            db.execute('UPDATE observations SET payload=?,analysis=?,removed=? WHERE id=?',(json.dumps(p),json.dumps({'relevance':'needs-review','berry_ids':[], 'aspects':[], 'entity_links':[], 'retailers':[], 'concepts':[], 'candidates':[], 'removed_media':media_id}),0 if media_id else 1,key))
            if media_id:
                db.execute('INSERT OR REPLACE INTO media_tombstones VALUES(?,?,?)',(key,media_id,state))
            if state=='deleted':
                db.execute('INSERT OR IGNORE INTO source_deletions VALUES(?,?,?,?,?,?)',(key,p['source'],p['native_id'],mode,media_id or '',now()))
            db.execute('UPDATE audit SET event=? WHERE evidence_id=?',('source content removed; prior correction detail redacted',key))
            db.execute('INSERT INTO audit(evidence_id,event,at) VALUES(?,?,?)',(key,'removal:'+state,now()))
        draft = self.inbox/'evidence'/f'{key}.json'
        if draft.exists():
            draft.unlink() # Untrusted handoff is invalidated, never published data.
        retained={m.get('object_ref') for r in self.records(mode=mode) for m in r['media']}
        for obj in objects:
            if obj and obj not in retained:
                (self.inbox/'social'/'media'/mode/obj).unlink(missing_ok=True)
        # Secure-delete clears SQLite pages; checkpoint truncates old WAL bodies.
        with closing(self.connect()) as db:
            db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    def attach_media(self,key,media_id,content,mime):
        if len(content)>5_000_000:
            raise ValueError('Media exceeds 5 MB')
        signatures={'image/png':b'\x89PNG\r\n\x1a\n','image/jpeg':b'\xff\xd8\xff','image/webp':b'RIFF'}
        if mime not in signatures or not content.startswith(signatures[mime]):
            raise ValueError('Only validated PNG/JPEG/WebP image bytes; no SVG or executable content')
        with closing(self.connect()) as db, db:
            row=db.execute('SELECT payload FROM observations WHERE id=? AND removed=0',(key,)).fetchone()
            if not row: raise ValueError('Unavailable observation')
            p=json.loads(row[0]); m=next((m for m in p['media'] if m['id']==media_id),None)
            if not m or m['storage_permission']!='permitted_bytes' or m['state']!='available':
                raise ValueError('Explicit permitted_bytes and available attachment required')
            obj=hashlib.sha256(content).hexdigest(); path=self.inbox/'social'/'media'/p['mode']/obj
            path.parent.mkdir(parents=True,exist_ok=True)
            if not path.exists(): path.write_bytes(content)
            m.update(object_ref=obj,content_hash=obj,mime=mime)
            db.execute('UPDATE observations SET payload=? WHERE id=?',(json.dumps(p),key))
        return obj
    def media(self,key,media_id):
        r=next((r for r in self.records() if r['id']==key),None)
        if not r or r.get('output_excluded'): raise ValueError('Unavailable observation')
        m=next((m for m in r['media'] if m['id']==media_id and m['state']=='available'),None)
        if not m or not m.get('object_ref'): raise ValueError('No permitted stored bytes; reference/availability limits apply')
        return self.inbox/'social'/'media'/r['mode']/m['object_ref'],m['mime']
    def expire(self):
        expired=[]
        for r in self.records():
            if datetime.fromisoformat(r['collected_at']) + timedelta(days=r['retention_days']) < datetime.now(timezone.utc):
                self.remove(r['id']); expired.append(r['id'])
        return expired
    def handoff(self,key):
        r = next((r for r in self.records() if r['id']==key),None)
        if not r or r['mode']=='fixture' or r.get('output_excluded'):
            raise ValueError('Unavailable/fixture observations cannot enter publication review')
        folder = self.inbox/'evidence'; folder.mkdir(parents=True,exist_ok=True)
        draft = {'id':key,'record_type':'evidence','status':'draft','review_state':'draft',
          'source_type':'social_observation','evidence_role':'publication_artifact','title':r['text'][:150] or 'Manual social URL capture',
          'source_name':r['source'],'source_url':r['canonical_url'],'captured_date':r['collected_at'][:10],
          'published_date':r['published_at'][:10] if r['published_at'] else None,'summary':r['text'],
          'submitted_by':'social-intake','berry_ids':r['analysis']['berry_ids'],'entity_ids':[],
          'social_observation':{'schema_version':1,'id':r['id'],'source':r['source'],'native_id':r['native_id'],
            'mode':r['mode'],'parent_native_id':r['parent_native_id'],'collected_at':r['collected_at'],
            'discovery_method':r['discovery_method'],'query_version':r['query_version'],
            'private_reader_href':'/social?mode='+r['mode']+'&story='+r['id'],
            'retention_days':r['retention_days'],'permission_basis':r['permission_basis']},'verification_state':'unverified',
          'does_not_prove':['Social observation, not verified registry relationship, cultivar identity or national distribution.'],
          'priority':{k:{'level':'none','rationale':'Awaiting social observation review'} for k in ('reading','testing','commercial_position','monitoring')}}
        from jsonschema import Draft202012Validator
        schema = Path(__file__).resolve().parents[3]/'schemas'/'evidence.schema.json'
        Draft202012Validator(json.loads(schema.read_text())).validate(draft)
        path=folder/f'{key}.json'
        if not path.exists():
            with path.open('x',encoding='utf-8') as f:
                json.dump(draft,f,ensure_ascii=False,indent=2)
        return '/review/'+key
