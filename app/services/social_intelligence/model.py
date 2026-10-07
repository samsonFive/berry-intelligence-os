"""Versioned provider-neutral intake; import and adapters use exactly this contract."""
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit
import ipaddress
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator

PLATFORMS = ('instagram', 'tiktok', 'facebook', 'threads', 'x', 'reddit', 'youtube',
             'bluesky', 'linkedin', 'pinterest', 'weibo', 'douyin', 'red', 'bilibili', 'forums-retail')
MODES = ('live', 'imported', 'manual', 'fixture')

def safe_url(value: str) -> str:
    """References only. No arbitrary URL fetcher is exposed by intake."""
    p = urlsplit(value)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None, 443):
        raise ValueError('Only public HTTPS references without credentials are accepted')
    host = p.hostname.lower()
    if host == 'localhost' or '.' not in host or host.endswith(('.local', '.internal', '.localhost')):
        raise ValueError('Private/local references are forbidden')
    try:
        if not ipaddress.ip_address(host).is_global:
            raise ValueError('Private IP references are forbidden')
    except ValueError as exc:
        if 'forbidden' in str(exc):
            raise
    if len(value) > 2048:
        raise ValueError('URL too long')
    return value

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Translation(Strict):
    text: str = Field(max_length=20000)
    language: str = 'en'
    method: Literal['human', 'provider', 'machine', 'synthetic']
    version: str
    uncertainty: str

class Geography(Strict):
    value: str = Field(max_length=120)
    basis: Literal['explicit_text', 'package_label', 'analyst', 'profile', 'query_target']
    evidence_ref: str
    confidence: float = Field(ge=0, le=1)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

class LiteralExtraction(Strict):
    text: str = Field(max_length=4000)
    method: Literal['human_label', 'ocr', 'transcript']
    version: str
    locator: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)

class Media(Strict):
    id: str = Field(min_length=1, max_length=200)
    parent_native_id: str
    kind: Literal['image', 'video', 'thumbnail', 'transcript']
    source_url: str | None = None
    mime: str = Field(max_length=100)
    content_hash: str | None = None
    object_ref: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    attribution: str = Field(max_length=500)
    state: Literal['available', 'unavailable', 'deleted', 'restricted', 'unsupported']
    storage_permission: Literal['reference_only', 'permitted_bytes', 'restricted']
    retention: str = Field(min_length=1, max_length=500)
    literal: list[LiteralExtraction] = Field(default_factory=list, max_length=30)
    _url = field_validator('source_url')(lambda v: safe_url(v) if v else v)

class Intake(Strict):
    schema_version: Literal[1] = 1
    source: str
    native_id: str = Field(min_length=1, max_length=500)
    canonical_url: str
    parent_native_id: str | None = None
    published_at: datetime | None = None
    collected_at: datetime
    mode: Literal['live', 'imported', 'manual', 'fixture']
    discovery_method: str = Field(min_length=1, max_length=120)
    query_version: str = Field(min_length=1, max_length=120)
    text: str = Field(max_length=20000)
    language: str = Field(min_length=2, max_length=35)
    language_basis: str = Field(min_length=1, max_length=120)
    translation: Translation | None = None
    content_role: Literal['consumer', 'recipe', 'company_owned', 'creator', 'disclosed_sponsorship', 'trade', 'news_repost', 'unknown'] = 'unknown'
    record_role: Literal['original', 'reply', 'repost'] = 'original'
    source_embed_urn: str | None = None
    author_handle: str | None = Field(default=None, max_length=500)
    author_name: str | None = Field(default=None, max_length=500)
    attribution: str = Field(max_length=500)
    permission_basis: str = Field(min_length=1, max_length=500)
    retention_days: int = Field(default=30, ge=1, le=365)
    purchase_market: Geography | None = None
    fruit_origin: Geography | None = None
    author_geography: Geography | None = None
    conversation_market: Geography | None = None
    search_market: Geography | None = None
    media: list[Media] = Field(default_factory=list, max_length=30)
    engagement: dict[str, int] = Field(default_factory=dict, max_length=20)
    engagement_at: datetime | None = None

    @field_validator('source')
    @classmethod
    def source_known(cls, v):
        if v not in PLATFORMS:
            raise ValueError('Unknown platform')
        return v

    _url = field_validator('canonical_url')(safe_url)

    @field_validator('source_embed_urn')
    @classmethod
    def embed_urn(cls, value):
        if value and not re.fullmatch(r'urn:li:(?:activity|share|ugcPost):\d{1,30}', value):
            raise ValueError('Unsupported source embed identity')
        return value

    @field_validator('collected_at','published_at','engagement_at')
    @classmethod
    def timestamp_timezone(cls,v):
        if v and v.tzinfo is None:
            raise ValueError('Timestamps require a timezone')
        return v

    @field_validator('purchase_market', 'fruit_origin')
    @classmethod
    def direct_geography(cls, v):
        if v and v.basis not in ('explicit_text', 'package_label', 'analyst'):
            raise ValueError('Purchase/origin requires explicit evidence, never profile or query targeting')
        return v

def validate_intake(payload, *, mode=None):
    item = Intake.model_validate(payload)
    if item.source_embed_urn and item.source != 'linkedin':
        raise ValueError('LinkedIn embed identity belongs only to LinkedIn evidence')
    if mode and item.mode != mode:
        raise ValueError('Intake provenance does not match this entry point')
    if any(m.parent_native_id != item.native_id for m in item.media):
        raise ValueError('Media parent must be the attached post/comment native ID')
    if any(m.object_ref for m in item.media):
        raise ValueError('Stored objects are created only by the permitted byte attachment path')
    if item.translation and item.translation.method == 'synthetic' and item.mode != 'fixture':
        raise ValueError('Synthetic translations belong only to fixtures')
    return item.model_dump(mode='json')
