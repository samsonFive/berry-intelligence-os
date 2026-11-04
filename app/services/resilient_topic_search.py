"""Disclosed, bounded fallback after a primary-provider outage or missing key."""
import hashlib
import threading
import time

from app.services.ai_gateway.errors import (GatewayAuthError, GatewayRateLimitError,
                                           GatewayTimeoutError, GatewayUnavailableError)
from app.services.public_research_search import PublicResearchSearchClient
from app.services.ai_gateway.credentials import credit_free_research_enabled

_CIRCUITS={}
_LOCK=threading.Lock()
COOLDOWN_SECONDS=300


def credit_free_mode():
    return credit_free_research_enabled()


class ResilientTopicSearchClient:
    def __init__(self, primary, *, credential='', entities=None, primary_sources=None, primary_terms=None, fallback=None, clock=time.monotonic):
        self.credit_free_only=credit_free_mode()
        self.primary=None if self.credit_free_only else primary
        self.fallback=fallback or PublicResearchSearchClient(entities=entities or {},primary_sources=primary_sources or {},primary_terms=primary_terms or {})
        self.clock=clock
        self.primary_failure=''
        self.used_fallback=False
        self.primary_requests=0
        self._key=hashlib.sha256(credential.encode()).hexdigest()

    def search(self, query, **kwargs):
        with _LOCK:state=_CIRCUITS.get(self._key)
        if self.credit_free_only:
            self.primary_failure='CreditFreeMode'
        elif state and self.clock()-state[0]<COOLDOWN_SECONDS:
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
                    credit_free_only=self.credit_free_only,
                    primary_failure=self.primary_failure,
                    fallback_failures=list(self.fallback.failures),
                    primary_requests_this_request=self.primary_requests,
                    fallback_requests_this_request=self.fallback.requests,
                    primary_page_requests_this_request=getattr(self.fallback,'primary_page_requests',0),
                    primary_page_failures=list(getattr(self.fallback,'primary_page_failures',[])),
                    coverage_limit='Anonymous Mwmbl web search, scholarly indexes (OpenAIRE Graph, Europe PMC, Crossref), Google News RSS and locally cited primary-source leads. Coverage is bounded and is not guaranteed equivalent to Google.' if self.used_fallback else '')
