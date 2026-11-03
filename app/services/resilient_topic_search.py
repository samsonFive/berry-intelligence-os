"""Disclosed, bounded fallback after a primary-provider outage or missing key."""
import hashlib
import threading
import time

from app.services.ai_gateway.errors import (GatewayAuthError, GatewayRateLimitError,
                                           GatewayTimeoutError, GatewayUnavailableError)
from app.services.public_research_search import PublicResearchSearchClient

_CIRCUITS={}
_LOCK=threading.Lock()
COOLDOWN_SECONDS=300


class ResilientTopicSearchClient:
    def __init__(self, primary, *, credential='', entities=None, primary_sources=None, fallback=None, clock=time.monotonic):
        self.primary=primary
        self.fallback=fallback or PublicResearchSearchClient(entities=entities or {},primary_sources=primary_sources or {})
        self.clock=clock
        self.primary_failure=''
        self.used_fallback=False
        self.primary_requests=0
        self._key=hashlib.sha256(credential.encode()).hexdigest()

    def search(self, query, **kwargs):
        with _LOCK:state=_CIRCUITS.get(self._key)
        if state and self.clock()-state[0]<COOLDOWN_SECONDS:
            self.primary_failure=state[1]
        elif self.primary is not None:
            try:
                self.primary_requests+=1
                response=self.primary.search(query,**kwargs)
                with _LOCK:_CIRCUITS.pop(self._key,None)
                return response
            except (GatewayAuthError,GatewayRateLimitError,GatewayTimeoutError,GatewayUnavailableError) as e:
                self.primary_failure=type(e).__name__
                with _LOCK:_CIRCUITS[self._key]=(self.clock(),self.primary_failure)
        else:self.primary_failure='MissingCredentialError'
        self.used_fallback=True
        return self.fallback.search(query,**kwargs)

    def diagnostics(self):
        return dict(fallback_used=self.used_fallback,
                    primary_failure=self.primary_failure,
                    fallback_failures=list(self.fallback.failures),
                    primary_requests_this_request=self.primary_requests,
                    fallback_requests_this_request=self.fallback.requests,
                    coverage_limit='Credit-free scholarly indexes, Google News RSS and registered primary-source leads; not equivalent to full web discovery.' if self.used_fallback else '')
