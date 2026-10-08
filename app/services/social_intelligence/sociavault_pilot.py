"""Explicit, private, prepaid-free multi-platform evaluation; never a scheduler.

Endpoint prices checked against official task docs on 2026-10-07. Account reads
must show free status/no past purchase before every uncached request. Successful
responses are cached; failures are not retried. No media downloads or AI calls.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import httpx
from .adapters import AccessBlocked
from .bakeoff import require_free_budget
from app.services.analyst_state_io import atomic_json

TASKS={
 'reddit-search':('reddit/search',{'query','sort','timeframe','trim'}),
 'tiktok-search':('tiktok/search/keyword',{'query','date_posted','sort_by','trim'}),
 'instagram-search':('instagram/search/hashtag',{'hashtag','date_posted','media_type'}),
 'youtube-search':('youtube/search',{'query','uploadDate','sortBy'}),
 'x-search':('twitter/search',{'query','type'}),
 'linkedin-search':('linkedin/search/posts',{'query','date_posted'}),
 'linkedin-company':('linkedin/company',{'url'}),
 'linkedin-post':('linkedin/post',{'url'}),
 'pinterest-search':('pinterest/search',{'query','trim'}),
 'reddit-comments':('reddit/post/comments',{'url','trim'}),
 'tiktok-comments':('tiktok/comments',{'url','trim'}),
 'instagram-comments':('instagram/comments',{'url','trim'}),
 'instagram-post':('instagram/post-info',{'url','trim'}),
 'youtube-comments':('youtube/video/comments',{'url','order','trim'}),
 'facebook-posts':('facebook/profile/posts',{'url'}),
 'threads-post':('threads/post',{'url','trim'}),
}

def private_key(path=None):
    if path:
        raw=Path(path).read_text(encoding='utf-8-sig')
        if len(raw)>65536:raise AccessBlocked('Credential file exceeds bounded size')
        found=[]
        for label in re.finditer(r'social?\s*vault',raw,re.I):
            match=re.search(r'sk_live_[A-Za-z0-9_-]+',raw[label.end():label.end()+300])
            if match:found.append(match.group())
        found=list(dict.fromkeys(found))
        if len(found)!=1:raise AccessBlocked('One uniquely labeled SociaVault key required')
        return found[0]
    token=os.environ.get('SOCIAVAULT_API_KEY')
    if not token:raise AccessBlocked('Configure SOCIAVAULT_API_KEY privately')
    return token

class MultiPlatformPilot:
    def __init__(self,private,*,enabled=False,key=None,client=None,ceiling=30):
        self.private=Path(private);self.enabled=enabled;self.key=key
        self.client=client or httpx.Client(timeout=45,follow_redirects=False)
        self.ceiling=ceiling
        self.ledger_path=self.private/'ledger.json'
        self.ledger=json.loads(self.ledger_path.read_text()) if self.ledger_path.exists() else {'initial_balance':None,'attempts':[]}

    def _read(self,path,params=None):
        try:
            with self.client.stream('GET','https://api.sociavault.com'+path,
                params=params,headers={'X-API-Key':self.key}) as response:
                body=bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body)>2_000_000:raise AccessBlocked('Response exceeds byte cap')
                status=response.status_code
            data=json.loads(bytes(body).decode().replace(self.key,'[redacted]'))
            return status,data
        except (httpx.HTTPError,ValueError):
            raise AccessBlocked('Transport or JSON failure; no retry') from None

    def balance(self):
        if not self.enabled:raise AccessBlocked('Explicit live opt-in required')
        if not self.key:raise AccessBlocked('Private key required')
        status,data=self._read('/v1/credits')
        if status!=200:raise AccessBlocked(f'Account verification HTTP {status}')
        if data.get('subscriptionStatus')!='free' or data.get('subscriptionId'):
            raise AccessBlocked('Only actual free-only accounts without purchases are eligible')
        balance=data.get('credits')
        if not isinstance(balance,int) or isinstance(balance,bool) or balance<0:
            raise AccessBlocked('Unrecognized account balance schema')
        if self.ledger['initial_balance'] is None:self.ledger['initial_balance']=balance
        return {'checked_at':datetime.now(timezone.utc).isoformat(),'balance':balance,
          'initial_verified_balance':self.ledger['initial_balance'],'evidence_state':'actual-account',
          'evidence_reference':'Authenticated /v1/credits: free, no purchased pack; official prepaid-only pricing',
          'free_only':True,'payment_method':False,'auto_recharge':False,
          'enforceable_no_charge_cap':True,'ancillary_costs_included':True}

    def _save(self):
        self.private.mkdir(parents=True,exist_ok=True)
        atomic_json(self.ledger_path,self.ledger)

    def fetch(self,task,params,*,case_id):
        if any(a['state']=='price-mismatch' for a in self.ledger['attempts']):
            raise AccessBlocked('Previous price mismatch requires review before further calls')
        if task not in TASKS or not set(params)<=TASKS[task][1]:
            raise AccessBlocked('Task or parameters outside pinned endpoint allowlist')
        if len(json.dumps(params))>4096:raise ValueError('Parameters exceed cap')
        digest=hashlib.sha256(json.dumps([task,params,case_id],sort_keys=True).encode()).hexdigest()
        cache=self.private/(digest+'.json')
        if cache.exists():return json.loads(cache.read_text(encoding='utf-8')),True
        if any(a['id']==digest for a in self.ledger['attempts']):
            raise AccessBlocked('Previously attempted request is not retried')
        verification=self.balance()
        if len(self.ledger['attempts'])>=self.ceiling:
            raise AccessBlocked('Cumulative request attempt ceiling reached')
        # Keep the attempt limit separate from actual account consumption.
        # Fresh authenticated balance includes failed/zero-credit requests and
        # any other account usage; the 20% reserve and 80% credit cap still apply.
        spent=verification['initial_verified_balance']-verification['balance']
        require_free_budget(verification,all_in_upper_bound=1,spent=spent,ceiling=self.ceiling)
        entry={'id':digest,'case_id':case_id,'task':task,'params':params,
               'at':verification['checked_at'],'balance_before':verification['balance'],
               'reserved_credits':1,'state':'started'}
        self.ledger['attempts'].append(entry);self._save() # durable before request
        try:
            status,data=self._read('/v1/scrape/'+TASKS[task][0],params)
            root=data.get('data',{})
            nested_error=isinstance(root,dict) and (root.get('success') is False or bool(root.get('error')) or root.get('status_code',0)!=0)
            entry.update(http=status,state='success' if status==200 and data.get('success') and not nested_error else 'provider-error',
                         reported_credits=data.get('credits_used'))
            after=self.balance();entry['balance_after']=after['balance']
            entry['observed_credit_delta']=entry['balance_before']-after['balance']
            if entry['observed_credit_delta']>1 or (data.get('credits_used') or 0)>1:
                entry['state']='price-mismatch';raise AccessBlocked('Unexpected credit cost; stop evaluation')
            if entry['state']!='success':raise AccessBlocked(f'Provider HTTP {status} or unsuccessful response; not zero volume')
            atomic_json(cache,data)
            return data,False
        except AccessBlocked:
            if entry['state']=='started':entry['state']='transport-blocked'
            raise
        finally:self._save()
