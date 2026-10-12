"""Real read-only API paths. No paid providers, scraping or arbitrary hosts.

Every page and its next checkpoint commit together; bounded calls include
retries. HTTP errors log only status, never token-bearing URLs/responses.
"""
from datetime import datetime, timezone
import hashlib
import os
import time
import httpx
from .store import now
from app.services.collection_runner import CollectionRunLock

class AccessBlocked(RuntimeError):
    pass

class Transport:
    def __init__(self, *, client=None, max_requests=12, sleep=time.sleep):
        self.client = client or httpx.Client(timeout=20, follow_redirects=False)
        self.max_requests = max_requests
        self.requests = 0
        self.sleep = sleep
    def get(self,url,params):
        for attempt in range(3):
            if self.requests >= self.max_requests:
                raise AccessBlocked('Request budget exhausted; resume checkpoint on next authorized run')
            self.requests += 1
            try:
                with self.client.stream('GET',url,params=params) as response:
                    if response.status_code in (429,500,502,503,504) and attempt<2:
                        self.sleep(min(2**attempt,4)); continue
                    if response.status_code != 200:
                        raise AccessBlocked(f'API HTTP {response.status_code}; no success claimed')
                    body=bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body)>2_000_000:
                            raise AccessBlocked('API response exceeded 2 MB limit')
                    import json
                    return json.loads(body)
            except (httpx.HTTPError,ValueError) as exc:
                if attempt==2:
                    raise AccessBlocked('API transport/malformed-response failure') from exc
                self.sleep(min(2**attempt,4))
        raise AccessBlocked('Retry budget exhausted')

def common(source,native,url,text,language='und',published=None,parent=None):
    return {'source':source,'native_id':native,'canonical_url':url,'text':text,
      'language':language,'language_basis':'provider tag' if language!='und' else 'unknown; analyst review required',
      'published_at':published,'collected_at':now(),'parent_native_id':parent,
      'mode':'live','discovery_method':'official-api','query_version':'social-query-1',
      'attribution':source+' public source; minimal attribution', 'permission_basis':'official API reference; operator must maintain terms compliance',
      'content_role':'unknown','record_role':'reply' if parent else 'original','media':[],'engagement':{}}

def bsky_post(post):
    uri=post['uri']; record=post.get('record',{})
    did, key=uri.removeprefix('at://').split('/')[0],uri.rsplit('/',1)[-1]
    url=f'https://bsky.app/profile/{did}/post/{key}'
    parent=record.get('reply',{}).get('parent',{}).get('uri')
    row=common('bluesky',uri,url,record.get('text',''),(record.get('langs') or ['und'])[0],record.get('createdAt'),parent)
    images=(post.get('embed') or {}).get('images',[])
    images+=((post.get('embed') or {}).get('media') or {}).get('images',[])
    for i,img in enumerate(images):
        row['media'].append({'id':f'{key}-image-{i}', 'parent_native_id':uri,'kind':'image',
         'source_url':img.get('fullsize') or img.get('thumb'),'mime':'image/jpeg','attribution':'Original Bluesky source',
         'state':'available','storage_permission':'reference_only','retention':'Refresh within 30 days; remove on source deletion; no rehosting'})
    if 'video' in (post.get('embed') or {}).get('$type',''):
        row['media'].append({'id':f'{key}-video','parent_native_id':uri,'kind':'video','source_url':url,
         'mime':'video/reference','attribution':'Original Bluesky source','state':'unsupported','storage_permission':'reference_only',
         'retention':'Reference only; no transcript analysis'})
    row['engagement']={k:post[k] for k in ('likeCount','replyCount','repostCount','quoteCount') if isinstance(post.get(k),int)}
    row['engagement_at']=now()
    return row

class Bluesky:
    source='bluesky'
    def __init__(self,transport): self.transport=transport
    def page(self,query,cursor=None,language=None):
        params={'q':query,'sort':'latest','limit':20}
        if cursor: params['cursor']=cursor
        if language: params['lang']=language
        data=self.transport.get('https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts',params)
        if 'posts' not in data or not isinstance(data['posts'],list):
            raise AccessBlocked('Bluesky response lacks posts')
        return [bsky_post(p) for p in data['posts']],data.get('cursor')
    def thread(self,uri):
        data=self.transport.get('https://public.api.bsky.app/xrpc/app.bsky.feed.getPostThread',{'uri':uri,'depth':2,'parentHeight':1})
        rows=[]
        def walk(node,depth=0):
            if depth>3 or len(rows)>=50: return
            if node.get('post'): rows.append(bsky_post(node['post']))
            for reply in node.get('replies',[]): walk(reply,depth+1)
        walk(data.get('thread',{}))
        return rows

class YouTube:
    source='youtube'
    def __init__(self,transport,key=None):
        self.transport=transport; self.key=key if key is not None else os.environ.get('BIOS_SOCIAL_YOUTUBE_KEY','')
    def call(self,endpoint,params):
        if not self.key:
            raise AccessBlocked('BIOS_SOCIAL_YOUTUBE_KEY missing; enable YouTube Data API v3 in an existing authorized Google project')
        data=self.transport.get('https://www.googleapis.com/youtube/v3/'+endpoint,{**params,'key':self.key})
        if 'items' not in data: raise AccessBlocked('YouTube response lacks items')
        return data
    def page(self,query,cursor=None,language=None):
        params={'part':'snippet','q':query,'type':'video','order':'date','maxResults':10}
        if cursor: params['pageToken']=cursor
        if language: params['relevanceLanguage']=language
        data=self.call('search',params); rows=[]
        for p in data['items']:
            native=p['id']['videoId']; s=p['snippet']
            row=common('youtube',native,'https://www.youtube.com/watch?v='+native,s['title']+'\n'+s.get('description',''),'und',s.get('publishedAt'))
            thumb=s.get('thumbnails',{}).get('medium',{}).get('url')
            if thumb:
                row['media']=[{'id':native+'-thumbnail','parent_native_id':native,'kind':'thumbnail','source_url':thumb,
                 'mime':'image/jpeg','state':'available','attribution':'YouTube source thumbnail','storage_permission':'reference_only','retention':'Refresh or delete API data within 30 days'}]
            rows.append(row)
        return rows,data.get('nextPageToken')
    def comments(self,video,cursor=None):
        data=self.call('commentThreads',{'part':'snippet,replies','videoId':video,'maxResults':20,'textFormat':'plainText',**({'pageToken':cursor} if cursor else {})})
        rows=[]
        for thread in data['items']:
            parent=thread['snippet']['topLevelComment']
            for comment in [parent]+thread.get('replies',{}).get('comments',[]):
                s=comment['snippet']; native=comment['id']
                rows.append(common('youtube',native,f'https://www.youtube.com/watch?v={video}&lc={native}',s.get('textOriginal',s.get('textDisplay','')),'und',s.get('publishedAt'),video if native==parent['id'] else parent['id']))
        # The response may omit replies: this is a bounded sample, not complete comments.
        return rows,data.get('nextPageToken')

def collect(store,adapter,entities, *, query,language,market,max_pages=2,max_items=40,enabled=False,include_comments=False):
    if not enabled:
        raise AccessBlocked('Collection disabled; explicit bounded operator enablement required')
    if max_pages not in range(1,4) or max_items not in range(1,61) or len(query)>300:
        raise ValueError('Pilot budgets: 1–3 pages, 1–60 items, query ≤300 characters')
    key=adapter.source+'-'+hashlib.sha256(f'{query}:{language}:{market}:social-query-1'.encode()).hexdigest()[:16]
    prior=store.job(key) or {}
    job={**prior,'id':key,'source':adapter.source,'query':query,'language':language,'market':market,'query_version':'social-query-1',
         'status':'running','started_at':now(),'last_success':prior.get('last_success'),'cursor':prior.get('cursor'),
         'query_changed':not bool(prior),'observed_volume':prior.get('observed_volume'), 'calls':0,'cost_usd':0,
         'budget':{'max_pages':max_pages,'max_items':max_items,'max_requests':adapter.transport.max_requests}}
    ids=[]
    with CollectionRunLock(store.inbox/'operations'/'collection.lock',run_id=key):
        store.save_job(job)
        try:
            # Resume incomplete page cycles; a completed search starts fresh.
            cursor=job['cursor'] if prior.get('has_more') else None
            for _ in range(max_pages):
                rows,next_cursor=adapter.page(query,cursor,language)
                if include_comments and rows:
                    # One bounded thread/video sample per page. Incomplete replies
                    # remain labeled; this never claims exhaustive thread capture.
                    if adapter.source=='bluesky': rows+=adapter.thread(rows[0]['native_id'])
                    else:
                        comments,_=adapter.comments(rows[0]['native_id']);rows+=comments
                    rows=list({r['native_id']:r for r in rows}.values())
                if len(ids)+len(rows)>max_items:
                    # Do not advance past records that were not persisted.
                    raise AccessBlocked('Item budget cannot fit complete page; increase within pilot bound and resume')
                for row in rows:
                    row['search_market']={'value':market,'basis':'query_target','evidence_ref':key,'confidence':1}
                committed_job={**job,'cursor':next_cursor,'has_more':bool(next_cursor),'last_success':now(),
                               'status':'partial' if next_cursor else 'live','observed_volume':len(ids)+len(rows),
                               'calls':adapter.transport.requests}
                # Advance in-memory state only after records and checkpoint commit
                # together. Failure reporting must retain the last durable cursor.
                committed_ids=store.ingest(rows,entities,mode='live',job=committed_job)
                job=committed_job
                ids+=committed_ids
                cursor=next_cursor
                if not cursor: break
            return {'state':'success','created':ids,'job':job}
        except Exception as exc:
            job.update(status='access-pending' if isinstance(exc,AccessBlocked) else 'failed',failure=str(exc) if isinstance(exc,AccessBlocked) else 'Normalization/processing failure',failed_at=now(),calls=adapter.transport.requests)
            store.save_job(job)
            return {'state':'error','failed':[{'source':adapter.source,'reason':job['failure']}],'job':job}
