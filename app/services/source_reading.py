"""Read-only access to human-affirmed original articles in the private workspace."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.services.article_dedup import normalize_canonical_url
from app.services.feed_first import SAFE_ID_RE
from app.services.source_body import article_full_text, reader_content
from app.services.source_fidelity_recovery import (
    RECOVERY_SCHEMA_VERSION, effective_record_for_extraction, trusted_identity_sha256,
)

MAX_RECOVERY_BYTES = 4_000_000


def reviewed_original_for_reading(record: dict, inbox_dir: Path) -> dict:
    """Resolve one matching reviewed recovery without changing stored source data.

    Call only from private selected reading or the private article-name audit,
    never from a feed metadata projection or public/static output. Existing
    stored article text, including operator edits, remains authoritative.
    """
    key = str(record.get('id') or '')
    if (record.get('status') != 'published' or record.get('evidence_role') == 'atomic_evidence'
            or not SAFE_ID_RE.fullmatch(key)
            or article_full_text(record)):
        return record
    path = Path(inbox_dir) / 'source_fidelity' / 'artifacts' / (key + '.json')
    try:
        if not path.exists():
            return record
        if path.is_symlink() or path.stat().st_size > MAX_RECOVERY_BYTES:
            raise ValueError('unavailable recovery')
        artifact = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(artifact, dict):
            raise ValueError('invalid recovery')
        review = artifact.get('review') or {}
        if not isinstance(review, dict) or review.get('status') != 'affirmed':
            return record
        if (artifact.get('source_fidelity_artifact_schema_version') != RECOVERY_SCHEMA_VERSION
                or artifact.get('evidence_id') != key
                or artifact.get('trusted_identity_sha256') != trusted_identity_sha256(record)
                or not isinstance(review.get('reviewed_by'), str) or not review['reviewed_by'].strip()
                or not review.get('reviewed_at')
                or not isinstance(artifact.get('source_url'), str) or not artifact['source_url']
                or normalize_canonical_url(artifact['source_url']) != normalize_canonical_url(record.get('source_url'))):
            raise ValueError('recovery no longer matches')
        if artifact.get('artifact_type') != 'article':
            return record
        payload = artifact.get('artifact')
        if not isinstance(payload, dict) or not isinstance(payload.get('article'), dict):
            raise ValueError('invalid article recovery')
        digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                         separators=(',', ':')).encode('utf-8')).hexdigest()
        if digest != artifact.get('source_artifact_sha256'):
            raise ValueError('recovered content changed')
        effective = effective_record_for_extraction(record, artifact)
        content = reader_content(effective)
        if (content['state'] not in {'body_available', 'body_partial'} or not content['body']
                or ' '.join(content['body'].split()) == ' '.join(content['summary'].split())):
            raise ValueError('original article unavailable')
        effective['reader_source_recovery'] = {'state': 'affirmed'}
        return effective
    except (OSError, ValueError, TypeError, AttributeError):
        # Do not surface private paths, payloads or exception strings. The UI
        # can point to the established Source Fidelity review surface.
        return {**record, 'reader_source_recovery': {'state': 'unavailable'}}
