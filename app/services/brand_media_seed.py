"""Add approved official image references without replacing runtime decisions.

This is an offline release operation. Run apply while application writers are
quiescent: the shared collector lease does not serialize analyst HTTP writes.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from app.services.analyst_state_io import atomic_json, serialized_write
from app.services.brand_media import Asset, PACK_KINDS, VERSION, index_path, official_image_reference
from app.services.pipeline_lock import pipeline_lock

MAX_SEED_ASSETS = 100
MAX_SEED_ENTITIES = 20


def _pairs(values):
    result = {}
    for key, value in values:
        if key in result:
            raise ValueError('Duplicate JSON keys are not permitted')
        result[key] = value
    return result


def _constant(_value):
    raise ValueError('Non-finite JSON values are not permitted')


def read_json(path):
    """Reject silent duplicate-key replacement without logging source values."""
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=_pairs, parse_constant=_constant)


def _existing(inbox):
    path = index_path(inbox)
    if not path.exists():
        return {}
    try:
        payload = read_json(path)
        if (not isinstance(payload, dict) or set(payload) != {'version', 'assets'}
                or type(payload['version']) is not int or payload['version'] != VERSION
                or not isinstance(payload['assets'], dict)):
            raise ValueError('Invalid index envelope')
        for key, row in payload['assets'].items():
            if not isinstance(row, dict) or key != row.get('id'):
                raise ValueError('Index identity mismatch')
            Asset.model_validate(row)
        # Keep the original dictionaries, including omitted optional fields.
        # Validating must not normalize or rewrite existing analyst choices.
        return payload['assets']
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ValueError('Existing media index requires repair; no records changed') from None


def validate_seed(payload, entities):
    if (not isinstance(payload, dict) or set(payload) - {'version', 'assets', 'note'}
            or type(payload.get('version')) is not int or payload['version'] != VERSION):
        raise ValueError('Seed requires a version 1 assets envelope')
    rows = payload.get('assets')
    if isinstance(rows, dict):
        if any(not isinstance(row, dict) or key != row.get('id') for key, row in rows.items()):
            raise ValueError('Seed asset keys must match their identities')
        rows = list(rows.values())
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_SEED_ASSETS:
        raise ValueError('Seed must contain 1–100 official image references')
    prepared = {}
    for number, raw in enumerate(rows, 1):
        try:
            asset = Asset.model_validate(raw)
            entity = entities.get(asset.entity_id)
            if (not isinstance(entity, dict) or entity.get('id') != asset.entity_id
                    or entity.get('entity_type') not in {'company', 'brand', 'retailer'}):
                raise ValueError('Entity does not match the canonical catalog')
            if (asset.origin != 'official_reference' or asset.source_kind != 'official'
                    or asset.observation_id is not None or asset.media_id is not None
                    or asset.object_ref is not None or asset.evidence_ids or asset.retail_observation_ids):
                raise ValueError('Only standalone official reference metadata is allowed')
            if not official_image_reference(asset.original_image_url, asset.source_page_url):
                raise ValueError('Official image destination is not approved')
            expected = 'asset-' + hashlib.sha256(
                f'official:{asset.entity_id}:{asset.source_page_url}:{asset.original_image_url}'.encode()).hexdigest()[:24]
            if asset.id != expected or asset.id in prepared:
                raise ValueError('Duplicate or mismatched asset identity')
            if (not asset.policy.reference_display_requested or asset.policy.display
                    or asset.policy.cache or asset.policy.export):
                raise ValueError('Reference request must not grant licensing, caching or export')
            if not isinstance(raw, dict) or (raw.get('policy') or {}).get('reference_display_requested') is not True:
                raise ValueError('An explicit reference display request is required')
            if asset.match_status != 'matched' or asset.rejected:
                raise ValueError('Seed identity must be matched and unrejected')
            if asset.kind in PACK_KINDS | {'logo'} and not (asset.classification_basis or '').strip():
                raise ValueError('Logo and packaging classification requires an inspection basis')
            prepared[asset.id] = asset.model_dump(mode='json')
        except (ValueError, TypeError, AttributeError, KeyError):
            raise ValueError(f'Seed asset {number} failed official-reference validation') from None
    if len({asset['entity_id'] for asset in prepared.values()}) > MAX_SEED_ENTITIES:
        raise ValueError('Seed must target at most 20 distinct entities')
    return prepared


def _plan(prepared, current, apply):
    missing = sorted(set(prepared) - set(current))
    preserved = sorted(set(prepared) & set(current))
    return {'requested': len(prepared), 'missing': len(missing), 'preserved': len(preserved),
            'created': len(missing) if apply else 0, 'missing_ids': missing,
            'added_ids': missing if apply else [], 'preserved_ids': preserved,
            'applied': bool(apply), 'changed': bool(apply and missing)}


@serialized_write
def install_seed(inbox, payload, *, entities, apply=False):
    """Plan by default; apply creates missing IDs and never replaces a record.

    All seed rows and the existing index are validated before any runtime write.
    An unchanged apply performs no writes, including no transient lease write.
    """
    inbox = Path(inbox)
    prepared = validate_seed(payload, entities)
    current = _existing(inbox)
    result = _plan(prepared, current, apply)
    if not apply or not result['missing']:
        return result
    target = index_path(inbox)
    if target.is_symlink() or not target.resolve().is_relative_to(inbox.resolve()):
        raise ValueError('Media index destination must remain inside the selected inbox')
    with pipeline_lock(inbox, 'brand_media_seed'):
        current = _existing(inbox)
        result = _plan(prepared, current, True)
        if not result['missing']:
            return result
        additions = {key: deepcopy(prepared[key]) for key in result['missing_ids']}
        # Seed defaults are not analyst selections. Any existing manual choice
        # must keep precedence, including a non-primary choice at another ID.
        for row in additions.values():
            row.update(primary=False, analyst_selected=False)
        atomic_json(target, {'version': VERSION, 'assets': {**current, **additions}})
    return result
