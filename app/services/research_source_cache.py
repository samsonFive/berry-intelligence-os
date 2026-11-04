"""Private, unreviewed public-source history shared across research queries.

This is a retrieval cache, not an Evidence import or publication approval.
Only public captures are stored. Original body/version/edition/date provenance
is retained; query scores, analyst notes and snippets are never indexed.
"""
import json
import sqlite3
from pathlib import Path

FIELDS=('id','title','source_url','source_name','published_date','publication_date_basis',
        'retrieved_at','capture_status','capture_reason','capture_provenance','source_version','article','provider')
MAX_RECORD_BYTES=1000000
MAX_DOCUMENTS=2000


def _path(inbox_dir):
    path=Path(inbox_dir)/'research_public_sources.sqlite3'
    if path.is_symlink():raise ValueError('Source cache cannot be a symlink')
    return path.absolute()


def remember_sources(inbox_dir,records):
    from app.services.feed_first_reader import is_public_http_url
    from app.services.article_dedup import normalize_canonical_url
    from app.services.topic_retrieval import normalize
    try:
        path=_path(inbox_dir);path.parent.mkdir(parents=True,exist_ok=True)
    except (ValueError,OSError):return {'status':'unavailable','stored':0}
    accepted=[]
    for record in records:
        url=record.get('source_url')
        if not is_public_http_url(url)or not record.get('source_version'):continue
        if record.get('capture_status')not in {'full','partial','excerpt_only'}:continue
        paragraphs=(record.get('article')or{}).get('paragraphs',[])
        body='\n'.join(str(p.get('text')or'')for p in paragraphs if isinstance(p,dict))
        if not body:continue
        import hashlib
        if hashlib.sha256(body.encode()).hexdigest()!=record['source_version']:continue
        public={key:record.get(key)for key in FIELDS}
        public['article']={'paragraphs':[{key:p[key]for key in ('index','locator','text')if key in p}for p in paragraphs if isinstance(p,dict)]}
        encoded=json.dumps(public,ensure_ascii=False)
        if len(encoded.encode())>MAX_RECORD_BYTES:continue
        accepted.append((normalize_canonical_url(url),record['source_version'],encoded,normalize(str(record.get('title')or'')),normalize(body)))
    if not accepted:return {'status':'unchanged','stored':0}
    try:
        with sqlite3.connect(path,timeout=3)as db:
            db.execute('CREATE TABLE IF NOT EXISTS sources (url TEXT PRIMARY KEY, version TEXT NOT NULL, record TEXT NOT NULL)')
            db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS source_search USING fts5(url UNINDEXED,title,body)')
            changed=0
            for url,version,record,title,body in accepted:
                previous=db.execute('SELECT version,record FROM sources WHERE url=?',(url,)).fetchone()
                if previous and previous==(version,record):continue
                db.execute('DELETE FROM source_search WHERE url=?',(url,))
                db.execute('INSERT OR REPLACE INTO sources VALUES(?,?,?)',(url,version,record))
                db.execute('INSERT INTO source_search(url,title,body)VALUES(?,?,?)',(url,title,body));changed+=1
            # Keep the bounded most recently inserted row set. No canonical
            # publication, saved workspace material or analyst data is deleted.
            excess=db.execute('SELECT url FROM sources ORDER BY rowid DESC LIMIT -1 OFFSET ?',(MAX_DOCUMENTS,)).fetchall()
            for(url,)in excess:
                db.execute('DELETE FROM source_search WHERE url=?',(url,))
                db.execute('DELETE FROM sources WHERE url=?',(url,))
        return {'status':'ready','stored':changed}
    except (sqlite3.Error,OSError):return {'status':'unavailable','stored':0}


def cached_sources(inbox_dir,plan,*,limit=150):
    try:path=_path(inbox_dir)
    except ValueError:return [],'unavailable'
    if not path.is_file():return [],'empty'
    # Vocabulary/constraints remain in the shared matcher. OR candidates retain
    # paraphrases and phrase hits; FTS syntax supplied by a user is never SQL.
    terms=list(dict.fromkeys(plan.terms))[:32]
    import re
    terms.extend(part for term in list(terms)if re.search(r'\d',term)for part in re.findall(r'[a-z]+|\d+',term))
    if not terms:return [],'empty'
    expression=' OR '.join('"'+term.replace('"','""')+'"'for term in terms)
    try:
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=3)as db:
            rows=db.execute('SELECT s.record FROM source_search f JOIN sources s ON f.url=s.url '
                'WHERE source_search MATCH ? ORDER BY bm25(source_search,0,5,1) LIMIT ?',(expression,min(max(limit,1),300))).fetchall()
        result=[]
        for(raw,)in rows:
            record=json.loads(raw)
            from app.services.feed_first_reader import is_public_http_url
            import hashlib
            paragraphs=(record.get('article')or{}).get('paragraphs',[])
            body='\n'.join(str(p.get('text')or'')for p in paragraphs if isinstance(p,dict))
            if not is_public_http_url(record.get('source_url'))or not body:continue
            if hashlib.sha256(body.encode()).hexdigest()!=record.get('source_version'):continue
            record.update(trust_class='LIVE / UNREVIEWED',research_cache_reused=True)
            result.append(record)
        return result,'ready'
    except (sqlite3.Error,OSError,ValueError):return [],'unavailable'


def merge_source_records(*groups):
    from app.services.article_dedup import normalize_canonical_url
    rows={}
    for group in groups:
        for row in group:
            key=normalize_canonical_url(row.get('source_url'))or row.get('id')
            if key:rows[key]=row
    return list(rows.values())
