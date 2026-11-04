"""Read-only, attributed research notes; never canonical traits or Facts."""
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

IMPORT_PATH = Path('imports/variety-profile-source-details-2026-10-27/observations.json')
STATUSES = {'source_reported', 'limited', 'identity_hold', 'demo_excluded'}


def validate_notes(payload, varieties):
    """Reject malformed/foreign references before displaying research notes."""
    known = {v['id']: v for v in varieties}
    if payload.get('version') != 1 or payload.get('review_status') != 'unreviewed':
        raise ValueError('Research notes must be version 1 and unreviewed')
    result = {}
    for note in payload['profiles']:
        key = note['variety_id']
        if key in result or key not in known or note['status'] not in STATUSES:
            raise ValueError('Invalid or duplicate variety reference')
        if note['berry_ids'] != known[key].get('berry_ids', []):
            raise ValueError('Wrong crop scope')
        date.fromisoformat(note['checked_on'])
        sources = note['sources']
        if len(sources) > 8 or len(note['details']) > 20:
            raise ValueError('Research note budget exceeded')
        for source_id, source in sources.items():
            parsed = urlsplit(source['url'])
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('Unsafe source URL')
            for field in ('title', 'kind', 'locator'):
                if not isinstance(source[field], str) or not 1 <= len(source[field]) <= 400:
                    raise ValueError('Invalid source metadata')
        for row in note['details']:
            if row['source_id'] not in sources:
                raise ValueError('Missing citation')
            for field in ('field', 'value', 'context'):
                if not isinstance(row[field], str) or not 1 <= len(row[field]) <= 1200:
                    raise ValueError('Invalid field value or conditions')
        if not isinstance(note['limitations'], str) or not 1 <= len(note['limitations']) <= 1800:
            raise ValueError('Missing limitations')
        if note['status'] == 'demo_excluded' and (sources or note['details']):
            raise ValueError('Demo varieties cannot carry researched traits')
        if note['status'] != 'demo_excluded' and not note['details']:
            raise ValueError('Non-demo notes need cited details')
        result[key] = note
    return result


def all_profile_source_details(data_dir, *, varieties):
    path = Path(data_dir) / IMPORT_PATH
    if not path.exists():
        return {}
    if path.stat().st_size > 300_000:
        raise ValueError('Research import too large')
    payload = json.loads(path.read_text(encoding='utf-8'))
    return validate_notes(payload, varieties)


def profile_source_details(data_dir, variety, *, varieties):
    return all_profile_source_details(data_dir, varieties=varieties).get(variety['id'])
