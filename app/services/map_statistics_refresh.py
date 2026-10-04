"""Explicit official-reference refresh/review; no canonical or trust writes."""
from copy import deepcopy
from datetime import UTC, date, datetime
import json
from pathlib import Path
import re
from uuid import uuid4

from app.services.analyst_state_io import atomic_json, serialized_write
from app.services.market_statistics_reference import METHODOLOGY, group_id
from app.services.pipeline_lock import pipeline_lock
from scripts.capture_map_statistics import capture

SUBDIR = 'market_statistics_refresh'
ACTIVE = {'queued', 'running'}
COUNTRIES = ('Germany', 'Spain', 'Netherlands', 'Portugal')


def now():
    return datetime.now(UTC)


def empty():
    return {'version': 1, 'revision': 0, 'jobs': {}, 'approved': [], 'history': []}


def path(inbox_dir):
    return Path(inbox_dir) / SUBDIR / 'state.json'


def validate_groups(groups):
    if not isinstance(groups, list) or len(groups) > 4:
        raise ValueError()
    seen = set()
    for group in groups:
        if not isinstance(group, dict) or group.get('source') != 'Eurostat' or group.get('country_id') not in {
            'geography-germany', 'geography-spain', 'geography-netherlands', 'geography-portugal'}:
            raise ValueError()
        if group.get('berry_id') != 'berry-strawberry' or group.get('commodity') != 'Strawberries':
            raise ValueError()
        if any(not isinstance(group.get(key), str) or not group[key] for key in
               ('country', 'period', 'source_url', 'locator', 'accessed_date', 'status', 'basis')):
            raise ValueError()
        from urllib.parse import parse_qs, urlsplit
        source = urlsplit(group['source_url'])
        query = parse_qs(source.query)
        expected = {'geography-germany': 'DE', 'geography-spain': 'ES', 'geography-netherlands': 'NL', 'geography-portugal': 'PT'}
        if source.scheme != 'https' or source.netloc != 'ec.europa.eu' or source.path != '/eurostat/api/dissemination/statistics/1.0/data/apro_cpsh1':
            raise ValueError()
        if query.get('geo') != [expected[group['country_id']]] or query.get('crops') != ['S0000'] or query.get('time') != [group['period'][:4]]:
            raise ValueError()
        if date.fromisoformat(group['accessed_date']).isoformat() != group['accessed_date'] or group.get('methodology_url') != METHODOLOGY:
            raise ValueError()
        if any(not isinstance(group.get(key), str) for key in ('published_date', 'source_updated_at')):
            raise ValueError()
        if not re.fullmatch(r'\d{4} calendar year', group['period']) or group['country_id'] in seen:
            raise ValueError()
        seen.add(group['country_id'])
        from app.services.market_statistics_reference import INDICATORS
        import math
        metrics = group.get('metrics')
        if not isinstance(metrics, list) or not 1 <= len(metrics) <= 3:
            raise ValueError()
        codes = set()
        for metric in metrics:
            code = metric.get('source_code')
            if code not in INDICATORS or code in codes or (metric.get('label'), metric.get('unit')) != INDICATORS[code]:
                raise ValueError()
            value = metric.get('value')
            if type(value) not in {int, float} or not math.isfinite(value) or value < 0 or not isinstance(metric.get('source_flag'), str) or 'c' in metric['source_flag']:
                raise ValueError()
            codes.add(code)


def load(inbox_dir):
    file = path(inbox_dir)
    if not file.exists():
        return empty()
    try:
        state = json.loads(file.read_text(encoding='utf-8'))
        if state.get('version') != 1 or type(state.get('revision')) is not int or state['revision'] < 0:
            raise ValueError()
        if not isinstance(state.get('jobs'), dict) or not isinstance(state.get('history'), list):
            raise ValueError()
        validate_groups(state['approved'])
        for key, job in state['jobs'].items():
            if not isinstance(job, dict) or not re.fullmatch(r'market-check-[a-f0-9]{32}', key) or job.get('id') != key:
                raise ValueError()
            if job.get('status') not in ACTIVE | {'ready', 'failed', 'interrupted'}:
                raise ValueError()
            if not re.fullmatch(r'[A-Za-z0-9_-]{12,80}', job.get('token', '')) or not isinstance(job.get('message'), str):
                raise ValueError()
            for field in ('created_at', 'updated_at'):
                if datetime.fromisoformat(job[field]).utcoffset() is None:
                    raise ValueError()
            validate_groups(job['groups'])
            if job['status'] == 'ready' and not job['groups']:
                raise ValueError()
        for entry in state['history']:
            if not isinstance(entry, dict) or entry.get('job_id') not in state['jobs'] or not isinstance(entry.get('actor'), str):
                raise ValueError()
            validate_groups(entry['before'])
            validate_groups(entry['after'])
        return state
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise ValueError('Market reference history cannot be read. Restore it before making changes.') from exc


def save(inbox_dir, state):
    state['revision'] += 1
    atomic_json(path(inbox_dir), state)


@serialized_write
def reserve(inbox_dir, token):
    if not re.fullmatch(r'[A-Za-z0-9_-]{12,80}', token):
        raise ValueError('Reload the page before checking official figures.')
    state = load(inbox_dir)
    for job in state['jobs'].values():
        if job['token'] == token:
            return deepcopy(job), False
    instant = now()
    for job in state['jobs'].values():
        if job['status'] in ACTIVE:
            if (instant - datetime.fromisoformat(job['updated_at'])).total_seconds() < 300:
                return deepcopy(job), False
            job.update(status='interrupted', message='The earlier check stopped. Existing figures were retained.', updated_at=instant.isoformat())
    key = 'market-check-' + uuid4().hex
    job = {'id': key, 'token': token, 'status': 'queued', 'created_at': instant.isoformat(), 'updated_at': instant.isoformat(),
           'message': 'Official figures check requested.', 'groups': [], 'capture_file': ''}
    state['jobs'][key] = job
    save(inbox_dir, state)
    return deepcopy(job), True


@serialized_write
def update(inbox_dir, job_id, *, status, message, groups=None, capture_file=''):
    state = load(inbox_dir)
    job = state['jobs'][job_id]
    if job['status'] not in ACTIVE:
        return False
    if groups is not None:
        validate_groups(groups)
        job['groups'] = groups
    job.update(status=status, message=message, updated_at=now().isoformat(), capture_file=capture_file)
    save(inbox_dir, state)
    return True


def run(inbox_dir, job_id):
    if not update(inbox_dir, job_id, status='running', message='Checking the latest Eurostat figures…'):
        return
    try:
        with pipeline_lock(Path(inbox_dir), 'map_statistics_refresh'):
            file, groups = capture(output_dir=Path(inbox_dir) / SUBDIR / 'captures')
        update(inbox_dir, job_id, status='ready', message='Official figures are ready to compare. Map references are unchanged.',
               groups=groups, capture_file=file.name)
    except Exception:
        update(inbox_dir, job_id, status='failed', message='Official figures could not be checked. Existing references were retained; you can try again.')


def category(group):
    return tuple(group[key] for key in ('source', 'country_id', 'berry_id', 'commodity'))


def merge(baseline, approved):
    replacements = {category(group): group for group in approved}
    return [deepcopy(replacements.pop(category(group), group)) for group in baseline] + list(deepcopy(replacements).values())


@serialized_write
def apply(inbox_dir, job_id, selected, revision, actor):
    state = load(inbox_dir)
    if revision != state['revision']:
        raise ValueError('The references changed while you were reviewing. Reload to compare the latest values.')
    job = state['jobs'].get(job_id)
    if not job or job['status'] != 'ready':
        raise ValueError('Choose a completed official figures check.')
    options = {group_id(group): group for group in job['groups']}
    if not selected or not set(selected).issubset(options):
        raise ValueError('Select at least one displayed country after reviewing its figures.')
    chosen = [deepcopy(options[key]) for key in options if key in selected]
    current = {category(group): group for group in state['approved']}
    for group in chosen:
        old = current.get(category(group))
        if old and (group['period'] < old['period'] or group['accessed_date'] < old['accessed_date']):
            raise ValueError('A newer reference is already saved. Review the latest check instead.')
    before = deepcopy(state['approved'])
    after = merge(before, chosen)
    if after == before:
        return False
    state['approved'] = after
    state['history'].append({'job_id': job_id, 'actor': actor, 'at': now().isoformat(), 'before': before, 'after': deepcopy(after)})
    save(inbox_dir, state)
    return True


def references(baseline, inbox_dir=None, authoring=False):
    return merge(baseline, load(inbox_dir)['approved']) if authoring and inbox_dir else deepcopy(baseline)
