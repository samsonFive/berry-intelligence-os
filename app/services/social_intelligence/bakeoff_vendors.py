"""Guarded candidate paths, not production connectors or entitlement claims.

Only SociaVault TikTok search/comments schema is presently pinned. Apify launch
plans remain non-executing until Actor build, input and all-in billing are
verified. No tokens accepted as CLI arguments or persisted in reports.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import httpx
from .adapters import common, AccessBlocked
from .bakeoff import require_free_budget
from .model import safe_url, validate_intake

def _values(value):
    if isinstance(value,list):return value
    if isinstance(value,dict):return list(value.values())
    return []

def sociavault_tiktok_rows(payload, *, task, manifest, supplied_url=None):
    data=payload.get('data',{})
    if not payload.get('success') or data.get('status_code',0)!=0:
        raise AccessBlocked('Provider error is not zero volume')
    field='search_item_list' if task=='search' else 'comments'
    if field not in data:
        raise AccessBlocked('Unrecognized vendor schema; retain privately for inspection')
    rows=[]
    for item in _values(data[field])[:10 if task=='search' else 20]:
        post=item.get('aweme_info',{}) if task=='search' else item
        native=str(post.get('aweme_id' if task=='search' else 'cid',''))
        parent=None if task=='search' else str(post.get('reply_id') or '0')
        if parent=='0':parent=str(post.get('aweme_id',''))
        if not native or (task=='comments' and not parent):
            raise AccessBlocked('Required native/parent identity absent')
        if task=='comments':
            if not supplied_url:raise AccessBlocked('Comment needs the actual supplied source post URL')
            url=safe_url(supplied_url)+('?comment_id=' if '?' not in supplied_url else '&comment_id=')+native
        else:
            url=post.get('share_url') or post.get('share_info',{}).get('share_url')
            handle=post.get('author',{}).get('unique_id')
            if not url and isinstance(handle,str) and re.fullmatch(r'[A-Za-z0-9_.]{1,100}',handle):
                url=f'https://www.tiktok.com/@{handle}/video/{native}'
            if not url:raise AccessBlocked('No attributable working post URL; no placeholder handle invented')
        published=datetime.fromtimestamp(post['create_time'],timezone.utc).isoformat() if post.get('create_time') else None
        row=common('tiktok',native,url,post.get('desc' if task=='search' else 'text',''),
          post.get('comment_language','und'),published,parent)
        row.update(discovery_method='sociavault-tiktok-'+task,query_version=manifest['version'],
          permission_basis='Third-party API response; public reference only; no redistribution or media storage rights inferred',
          attribution='Original public TikTok source via SociaVault')
        if task=='search' and published and not manifest['start_utc']<=published<=manifest['end_utc']:
            continue
        row['engagement']={k:v for k,v in (post.get('statistics',{}) if task=='search' else {'likes':post.get('digg_count')}).items() if isinstance(v,int) and v>=0}
        # image_list presence and null sample do not demonstrate a working image.
        # Only a supplied explicit HTTPS url_list is a reference; never avatar.
        for i,image in enumerate(_values(post.get('image_list'))[:30]):
            refs=image.get('url_list',[]) if isinstance(image,dict) else []
            media_url=next((u for u in refs if isinstance(u,str) and u.startswith('https://')),None)
            row['media'].append({'id':native+f'-image-{i}','parent_native_id':native,'kind':'image',
              'source_url':media_url,'mime':'image/reference','state':'available' if media_url else 'unsupported',
              'storage_permission':'reference_only','attribution':'TikTok source image reference',
              'retention':'Availability and retention/redisplay rights not established; do not download'})
        rows.append(validate_intake(row))
    return rows

class SociaVaultPilot:
    def __init__(self, private_dir, *, enabled=False, client=None):
        self.private=Path(private_dir);self.enabled=enabled
        self.client=client or httpx.Client(timeout=20,follow_redirects=False)
        self.calls=0;self.reserved=0;self.last_verification=None
    def fetch(self, *, task, value, verification, ceiling=20):
        if task not in ('search','comments'):
            raise ValueError('Only pinned TikTok search/comments pilot endpoints allowed')
        if not self.enabled:raise AccessBlocked('Explicit metered live opt-in required')
        token=os.environ.get('SOCIAVAULT_API_KEY')
        if not token:raise AccessBlocked('SOCIAVAULT_API_KEY absent; configure privately, never in reports')
        params={'query':value,'date_posted':'this-month','sort_by':'date-posted','trim':'false'} if task=='search' else {'url':safe_url(value),'trim':'false'}
        if len(value)>2048:raise ValueError('Input too long')
        # This-month is a documented approximation; exact dates filtered locally.
        endpoint='/v1/scrape/tiktok/'+('search/keyword' if task=='search' else 'comments')
        digest=hashlib.sha256(json.dumps([endpoint,params],sort_keys=True).encode()).hexdigest()
        cache=self.private/(digest+'.json')
        if cache.exists():return json.loads(cache.read_text(encoding='utf-8')),True
        if self.calls>=5:raise AccessBlocked('Pilot call ceiling reached')
        if not verification.get('task_pricing_verified') or verification.get('endpoint_maximum_credits')!=1:
            raise AccessBlocked('Confirm endpoint-specific maximum cost; public pricing guide conflicts with endpoint docs')
        if self.last_verification and verification['checked_at']<=self.last_verification:
            raise AccessBlocked('Verify current balance and billing again before each new metered run')
        require_free_budget(verification,all_in_upper_bound=1,spent=self.reserved,ceiling=ceiling)
        self.last_verification=verification['checked_at']
        self.calls+=1;self.reserved+=1 # reserve even on transport failure; never retry
        try:
            with self.client.stream('GET','https://api.sociavault.com'+endpoint,
                params=params,headers={'X-API-Key':token}) as response:
                if response.status_code!=200:raise AccessBlocked(f'Provider HTTP {response.status_code}; no retry')
                body=bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body)>2_000_000:raise AccessBlocked('Vendor response byte cap exceeded')
            data=json.loads(body)
        except (httpx.HTTPError,ValueError) as exc:
            raise AccessBlocked('Vendor transport/schema failure; no retry') from exc
        if not data.get('success'):raise AccessBlocked('Vendor returned unsuccessful response')
        self.private.mkdir(parents=True,exist_ok=True)
        cache.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
        return data,False

def apify_launch_plan(actor, *, build, actor_input, verification, all_in_upper_bound=.5):
    """Concrete reviewable request only; does NOT start an Actor or reserve credit.

    maxTotalChargeUsd only caps eligible Actor charges, not an all-in account
    budget. A launch is deliberately unavailable until ancillary bounds and
    selected build input-schema validation have been confirmed.
    """
    allowed={'apify/instagram-scraper','apify/instagram-comment-scraper',
      'clockworks/tiktok-scraper','atomus/weibo-scraper','atomus/douyin-scraper',
      'atomus/xiaohongshu-scraper','atomus/bilibili-scraper'}
    if actor not in allowed or not build or build in ('latest','default'):
        raise AccessBlocked('Exact shortlisted Actor and immutable build required')
    require_free_budget(verification,all_in_upper_bound=all_in_upper_bound,spent=0,ceiling=1)
    if not verification.get('actor_input_schema_verified') or not verification.get('task_pricing_verified'):
        raise AccessBlocked('Pin and validate Actor input/schema and task event rates first')
    if not isinstance(actor_input,dict) or len(json.dumps(actor_input))>8000:
        raise ValueError('Bounded input object required')
    return {'method':'POST','url':'https://api.apify.com/v2/acts/'+actor.replace('/','~')+'/runs',
      'headers':{'Authorization':'Bearer <private APIFY_TOKEN>'},
      'params':{'build':build,'timeout':60,'memory':256,'maxItems':10,'maxTotalChargeUsd':.25},
      'input':actor_input,'state':'setup-required','launch_enabled':False,
      'reason':'Plan only; actual credit/billing, schema and ancillary ceiling revalidation required before execution'}
