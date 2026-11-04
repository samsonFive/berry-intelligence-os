"""Packaged negative quote holds; independent of mutable runtime data.

These do not approve a source or claim. Docker copies this module and its
adjacent JSON together, including when an existing runtime volume is reused.
"""
from functools import lru_cache
import json
from pathlib import Path


@lru_cache(maxsize=1)
def _holds():
    return json.loads(Path(__file__).with_suffix('.json').read_text(encoding='utf-8'))['holds']


def source_quote_hold(row):
    from app.services.article_dedup import normalize_canonical_url
    key=normalize_canonical_url(row.get('source_url') or row.get('url'))
    return next((h for h in _holds() if key and normalize_canonical_url(h['source_url'])==key),None)
