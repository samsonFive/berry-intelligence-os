"""Explain existing photo identity holds without linking or loading the image."""
from hashlib import sha256
from urllib.parse import urlencode

from app.services.variety_photos import compatible, source_photos, validate_photo
from app.services.variety_portfolio_coverage import _identity_pair_notes, _key
from app.services.variety_universe.identity import resolve_identity


def photo_identity_reviews(target, *, sources=(), varieties=(), sourced=None):
    """Return source/review links only; every gallery/identity gate stays intact."""
    if sourced is None:
        sourced = source_photos(target, sources=sources, varieties=varieties)
    eligible = {photo['id'] for photo in sourced}
    pair_notes = None
    rows = {}
    for source in sources:
        for ref in source.get('names', []):
            for raw in ref.get('photos', []):
                photo = validate_photo(raw)
                if not compatible(photo, target):
                    continue
                key = 'source-photo-' + sha256((photo['source_url'] + '\n' + photo['image_url']).encode()).hexdigest()[:20]
                if key in eligible:
                    continue
                if pair_notes is None:
                    pair_notes = _identity_pair_notes(sources)
                notes = list(ref.get('identity_notes') or [])
                notes += pair_notes.get((source['id'], _key(ref), ref.get('trade_name') or ref['candidate_name']), [])
                if varieties:
                    resolved = resolve_identity({'candidate_name': photo['named_variety'], 'berry_id': photo['berry_id']}, list(varieties))
                    ids = {row['variety_id'] for row in resolved['matches'] if row['reason'] == 'exact_identity_string'}
                    if len(ids) > 1:
                        notes.append('This photo name matches more than one catalog entry. Review the identity before linking it.')
                if not notes:
                    continue
                rows[(source['id'], photo['named_variety'])] = {
                    'source_id': source['id'], 'title': source.get('title') or photo['named_variety'],
                    'named_variety': photo['named_variety'], 'source_url': photo['source_url'],
                    'review_notes': list(dict.fromkeys(notes)),
                    # Show coded and uncoded leads together; a photo-source
                    # filter alone hides the very pairing that needs review.
                    'review_href': '/varieties/candidates?' + urlencode({'q': photo['named_variety'], 'berry': photo['berry_id']}) + '#candidate-results',
                }
    return list(rows.values())
