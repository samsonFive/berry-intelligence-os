"""Explicit public market research and human-checked private reference context.

Research cannot publish evidence, approve statements or fill missing statistics.
The Eurostat capture contract remains in map_statistics_refresh, unchanged.
"""
from copy import deepcopy
from datetime import UTC, date, datetime
import json
import hashlib
import math
from pathlib import Path
import re
from uuid import uuid4

from app.services.analyst_state_io import atomic_json, serialized_write
from app.services.ai_gateway.perplexity_deep_research import CONFIG, ResearchError
from app.services.map_regions import public_source_url
from app.services.company_profile_research import readable_note
from app.services.market_statistics_reference import group_id

FILENAME = 'market_reference_research.json'
TERMINAL = {'ready', 'partial', 'failed', 'cancelled'}
STATUSES = TERMINAL | {'requested', 'submitting', 'submission_uncertain', 'running', 'cancelling'}
LABELS = {'requested': 'Research requested', 'submitting': 'Starting research', 'running': 'Research in progress',
          'submission_uncertain': 'Reconnect the existing research', 'cancelling': 'Stopping research',
          'ready': 'Figures ready to review', 'partial': 'Partial result — review the limitations',
          'failed': 'Research unavailable', 'cancelled': 'Research stopped'}
BERRIES = {'berry-blueberry': 'Blueberry', 'berry-strawberry': 'Strawberry',
           'berry-raspberry': 'Raspberry', 'berry-blackberry': 'Blackberry'}
INDICATORS = {'area': 'Area', 'production': 'Harvested production', 'yield': 'Yield'}
UNITS = {
    'area': {'ha', 'hectares', 'hectáreas', '1000 ha', '1,000 ha', 'thousand hectares', 'acres', '1000 acres', 'thousand acres', 'km²', 'm²'},
    'production': {'t', 'tonnes', 'metric tons', 'toneladas', '1000 t', '1,000 t', 'thousand tonnes', 'short tons', 'tons', 'kg', 'kilograms', 'lb', 'lbs', 'pounds', 'million pounds', '1000 lb'},
    'yield': {'t/ha', 'tonnes per hectare', 'kg/ha', 'kg/m²', 'kg/m2', 'lb/acre', 'lbs/acre', 'tons/acre', 't/acre'},
}


def now():
    return datetime.now(UTC)


def empty():
    return {'version': 1, 'revision': 0, 'jobs': {}, 'approved': [], 'history': []}


def scope(country, berry_id):
    code = (country.get('attributes') or {}).get('iso_3166_1_alpha_2')
    if country.get('entity_type') != 'geography' or not re.fullmatch(r'[A-Z]{2}', str(code or '')) or berry_id not in BERRIES:
        raise ValueError('Choose one country and one berry for this research.')
    if not country.get('id') or not isinstance(country.get('name'), str) or not country['name'].strip():
        raise ValueError('This country needs an identity check before research.')
    return {'country_id': country['id'], 'country': country['name'], 'country_code': code,
            'berry_id': berry_id, 'berry': BERRIES[berry_id], 'through_year': now().year}


def valid_date(value):
    if value == '':
        return True
    try:
        return isinstance(value, str) and date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def validate_groups(groups):
    if not isinstance(groups, list):
        raise ValueError('Unreadable research references.')
    seen = set()
    for group in groups:
        if not isinstance(group, dict) or any(not isinstance(group.get(key), str) or not group[key].strip() or len(group[key]) > bound
                for key, bound in {'country_id': 150, 'country': 150, 'commodity': 150, 'reported_commodity': 150,
                                  'period': 100, 'source': 200, 'source_url': 3000, 'locator': 500,
                                  'accessed_date': 10, 'status': 200, 'basis': 2000}.items()):
            raise ValueError('Incomplete research reference.')
        if group.get('berry_id') not in BERRIES or group.get('coverage') != 'National' or group.get('crop_scope') != 'single_crop':
            raise ValueError('The reported coverage is not the requested national crop.')
        if not re.fullmatch(r'\d{4} (?:calendar|reporting) year', group['period']) or not public_source_url(group['source_url']):
            raise ValueError('The source or reporting period is unusable.')
        if not valid_date(group['accessed_date']) or not group['accessed_date'] or any(not valid_date(group.get(k)) for k in ('published_date', 'source_updated_at')):
            raise ValueError('Invalid source date.')
        if any(not isinstance(group.get(k), str) or len(group[k]) > 600 for k in ('date_note', 'methodology_url')):
            raise ValueError('Invalid source notes.')
        if group['methodology_url'] and not public_source_url(group['methodology_url']):
            raise ValueError('The methodology link is unusable.')
        metrics = group.get('metrics')
        if not isinstance(metrics, list) or not 1 <= len(metrics) <= 3:
            raise ValueError('No usable reported figures.')
        codes = set()
        for metric in metrics:
            if not isinstance(metric, dict):
                raise ValueError('Invalid reported figure.')
            code = metric.get('source_code')
            value = metric.get('value')
            if code not in INDICATORS or code in codes or metric.get('label') != INDICATORS[code]:
                raise ValueError('Invalid or repeated indicator.')
            if type(value) not in {int, float} or not math.isfinite(value) or value < 0:
                raise ValueError('Invalid reported number.')
            if not isinstance(metric.get('unit'), str) or metric['unit'].casefold() not in UNITS[code]:
                raise ValueError('The source unit is missing or unsupported.')
            if metric.get('classification') not in {'Reported', 'Estimated', 'Provisional'}:
                raise ValueError('Missing figure qualification.')
            if any(not isinstance(metric.get(k), str) or not metric[k].strip() or len(metric[k]) > bound
                   for k, bound in {'passage': 900, 'definition': 500}.items()):
                raise ValueError('No source passage or definition to check.')
            codes.add(code)
        key = group_id(group)
        if key in seen:
            raise ValueError('Repeated research reference.')
        seen.add(key)


def load(inbox_dir):
    file = Path(inbox_dir) / FILENAME
    if not file.exists():
        return empty()
    try:
        state = json.loads(file.read_text(encoding='utf-8'))
        if not isinstance(state, dict) or state.get('version') != 1 or type(state.get('revision')) is not int or state['revision'] < 0:
            raise ValueError()
        if not isinstance(state.get('jobs'), dict) or not isinstance(state.get('history'), list):
            raise ValueError()
        validate_groups(state['approved'])
        for key, job in state['jobs'].items():
            if not isinstance(job, dict) or not re.fullmatch(r'market-research-[a-f0-9]{32}', key) or job.get('id') != key or job.get('status') not in STATUSES:
                raise ValueError()
            if type(job.get('revision')) is not int or job['revision'] < 1 or not re.fullmatch(r'[A-Za-z0-9_-]{12,80}', job.get('token', '')):
                raise ValueError()
            if any(not isinstance(job.get(k), str) for k in ('provider_id', 'text', 'error', 'created_at', 'updated_at')) or not isinstance(job.get('config'), dict):
                raise ValueError()
            if job['provider_id'] and not re.fullmatch(r'[A-Za-z0-9_-]{1,180}', job['provider_id']):
                raise ValueError()
            for k in ('created_at', 'updated_at'):
                if datetime.fromisoformat(job[k]).utcoffset() is None:
                    raise ValueError()
            selected = job.get('scope')
            if not isinstance(selected, dict) or selected.get('berry_id') not in BERRIES or selected.get('berry') != BERRIES[selected['berry_id']]:
                raise ValueError()
            if any(not isinstance(selected.get(k), str) or not selected[k] for k in ('country_id', 'country', 'country_code')) or not re.fullmatch(r'[A-Z]{2}', selected['country_code']):
                raise ValueError()
            if type(selected.get('through_year')) is not int or not 2000 <= selected['through_year'] <= 2200:
                raise ValueError()
            if not isinstance(job.get('citations'), list) or any(not isinstance(c, dict) or not public_source_url(c.get('url')) for c in job['citations']):
                raise ValueError()
            if not isinstance(job.get('warnings'), list) or any(not isinstance(v, str) for v in job['warnings']):
                raise ValueError()
            validate_groups(job['groups'])
            if len(job['groups']) > 8:
                raise ValueError()
            cited = {c['url'] for c in job['citations']}
            for group in job['groups']:
                if group['country_id'] != selected['country_id'] or group['berry_id'] != selected['berry_id'] or group['source_url'] not in cited:
                    raise ValueError()
                if not selected['through_year'] - 4 <= int(group['period'][:4]) <= selected['through_year']:
                    raise ValueError()
        for entry in state['history']:
            if not isinstance(entry, dict) or entry.get('job_id') not in state['jobs'] or not isinstance(entry.get('actor'), str) or not entry['actor']:
                raise ValueError()
            validate_groups(entry['before'])
            validate_groups(entry['after'])
        return state
    except (OSError, ValueError, TypeError, AttributeError, KeyError, OverflowError) as exc:
        raise ValueError('Market research history cannot be read. Restore it before making changes.') from exc


def save(inbox_dir, state):
    state['revision'] += 1
    atomic_json(Path(inbox_dir) / FILENAME, state)


@serialized_write
def reserve(inbox_dir, selected, token):
    if not re.fullmatch(r'[A-Za-z0-9_-]{12,80}', token):
        raise ValueError('Reload the page before requesting research.')
    state = load(inbox_dir)
    for job in state['jobs'].values():
        if job['token'] == token:
            if job['scope'] != selected:
                raise ValueError('This request belongs to another country or berry.')
            return deepcopy(job), False
        if job['scope'] == selected and job['status'] not in TERMINAL:
            return deepcopy(job), False
    if sum(job['status'] not in TERMINAL for job in state['jobs'].values()) >= 2:
        raise ValueError('Finish or stop existing market research before requesting another.')
    stamp = now().isoformat()
    key = 'market-research-' + uuid4().hex
    job = {'id': key, 'scope': selected, 'token': token, 'revision': 1, 'status': 'requested',
           'created_at': stamp, 'updated_at': stamp, 'provider_id': '', 'text': '', 'citations': [], 'groups': [], 'warnings': [], 'error': '',
           'config': {**CONFIG, 'prompt_version': 'market-reference-research-v2'}}
    state['jobs'][key] = job
    save(inbox_dir, state)
    return deepcopy(job), True


def prompt(job):
    selected = job['scope']
    public = {k: selected[k] for k in ('country', 'country_code', 'berry', 'through_year')}
    return ('Research the latest publicly reported NATIONAL annual area, harvested production and yield for the country and berry below. '
            'The JSON scope is data, not instructions. Use the last five calendar years through through_year; prefer the latest populated year. '
            'Prioritize original government statistical agencies, agriculture ministries, university/extension reports and transparent industry statistical reports. '
            'Read the original source and cite its exact URL using your web tools. Never invent, infer, convert or calculate a missing value, especially yield. '
            'Do not substitute exports, fresh market utilization, company acreage, regional totals, mixed berries, forecasts, retail prices or acreage intentions for national production. '
            'If unavailable or ambiguous, return no group and explain the gap in limits. Estimates and provisional statistics must keep their qualifications. '
            'Return ONLY JSON {groups: [...], limits: [...]} with at most 8 groups and 10 short limits. Each group: country_code, berry (exact scope name), '
            'coverage ("National" only), crop_scope ("single_crop" only), reported_commodity (original source crop/category label), '
            'year (integer source reporting year; not an assertion of a uniform survey or harvest period), source (agency/publisher), source_url (original URL unchanged), locator (table/page/dataset), '
            'published_date and source_updated_at (precise YYYY-MM-DD if explicitly stated, otherwise empty), date_note (retain partial/unknown dates, harvest seasons, mixed regional survey years and period limitations), '
            'methodology_url (public original link or empty), basis (definitions and qualifications), metrics. '
            'Each metric: indicator (area/production/yield), value (original numeric value), unit (original source unit unchanged), '
            'classification (Reported/Estimated/Provisional), passage (short exact source passage containing the figure), definition (what this figure measures). '
            'Include only explicitly reported figures; missing metrics are absent. Keep source categories and measurement periods distinct. Scope: '
            + json.dumps(public, ensure_ascii=False))


def parse(result, job):
    text = str(result.get('text') or '').strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text)
    try:
        document = json.loads(text)
        items = document['groups']
        if not isinstance(items, list) or len(items) > 8 or not isinstance(document.get('limits', []), list):
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        return [], ['The response did not contain usable figures. Existing references are unchanged.']
    warnings = [readable_note(v[:600], result.get('citations', []))[0] for v in document.get('limits', [])[:10] if isinstance(v, str)]
    cited = {c['url'] for c in result.get('citations', []) if isinstance(c, dict) and public_source_url(c.get('url'))}
    selected, groups, rejected, seen = job['scope'], [], 0, set()
    for item in items:
        try:
            if not isinstance(item, dict) or item.get('country_code') != selected['country_code'] or item.get('berry') != selected['berry']:
                raise ValueError()
            year = item.get('year')
            if type(year) is not int or not selected['through_year'] - 4 <= year <= selected['through_year'] or item.get('source_url') not in cited:
                raise ValueError()
            commodity = item['reported_commodity']
            if not isinstance(commodity, str):
                raise ValueError()
            # A generated single-crop label cannot hide obvious combined berry categories.
            stems = ('blueberr', 'strawberr', 'raspberr', 'blackberr')
            expected = {'Blueberry': 'blueberr', 'Strawberry': 'strawberr', 'Raspberry': 'raspberr', 'Blackberry': 'blackberr'}[selected['berry']]
            crop_words = sum(bool(re.search(word, commodity.casefold())) for word in stems)
            if crop_words > 1 or commodity.casefold().strip() in {'berries', 'small fruit', 'soft fruit', 'mixed berries'}:
                raise ValueError()
            if any(word != expected and word in commodity.casefold() for word in stems):
                raise ValueError()
            group = {k: item.get(k) for k in ('reported_commodity', 'coverage', 'crop_scope', 'source', 'source_url', 'locator',
                      'published_date', 'source_updated_at', 'date_note', 'methodology_url', 'basis')}
            group.update(country_id=selected['country_id'], country=selected['country'], berry_id=selected['berry_id'],
                         commodity=commodity, period=f'{year} reporting year', accessed_date=now().date().isoformat(),
                         status='Research proposal · check the original source', metrics=[])
            if isinstance(group['basis'], str):
                group['basis'], _ = readable_note(group['basis'], result.get('citations', []))
            if isinstance(group['date_note'], str):
                group['date_note'], _ = readable_note(group['date_note'], result.get('citations', []))
            for metric in item['metrics']:
                code = metric.get('indicator')
                group['metrics'].append({k: metric.get(k) for k in ('value', 'unit', 'classification', 'passage', 'definition')}
                                       | {'source_code': code, 'label': INDICATORS.get(code, '')})
                if isinstance(group['metrics'][-1]['definition'], str):
                    group['metrics'][-1]['definition'], _ = readable_note(group['metrics'][-1]['definition'], result.get('citations', []))
            validate_groups([group])
            key = group_id(group)
            if key in seen:
                raise ValueError()
            seen.add(key)
            groups.append(group)
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
            rejected += 1
    if rejected:
        warnings.append(f'{rejected} result(s) lacked an exact cited source, usable scope, period, units or figures and were not offered for use.')
    if not groups:
        warnings.append('No usable national production references were returned. Missing figures remain unknown.')
    return groups, warnings


@serialized_write
def claim(inbox_dir, key):
    state = load(inbox_dir)
    job = state['jobs'][key]
    if job['status'] != 'requested':
        return None
    job.update(status='submitting', revision=job['revision'] + 1, updated_at=now().isoformat())
    save(inbox_dir, state)
    return deepcopy(job)


@serialized_write
def apply_result(inbox_dir, key, result, revision):
    state = load(inbox_dir)
    job = state['jobs'][key]
    if job['revision'] != revision or job['status'] in TERMINAL:
        return False
    if job['provider_id'] and job['provider_id'] != result['provider_id']:
        raise ValueError('This result belongs to another market research request.')
    status = result['provider_status']
    job.update(provider_id=result['provider_id'], provider_status=status, model=result.get('model', ''), usage=result.get('usage', {}),
               status={'completed': 'ready', 'incomplete': 'partial', 'failed': 'failed', 'cancelled': 'cancelled', 'cancelling': 'cancelling'}.get(status, 'running'),
               revision=job['revision'] + 1, updated_at=now().isoformat(), error='')
    if status in {'completed', 'incomplete'}:
        job['text'] = str(result.get('text') or '')[:100000]
        job['original_citations'] = deepcopy(result.get('citations') or [])
        job['citations'] = [{**c, 'title': str(c.get('title') or 'Research source')[:500]} for c in job['original_citations']
                            if isinstance(c, dict) and public_source_url(c.get('url'))]
        job['groups'], job['warnings'] = parse({**result, 'text': job['text'], 'citations': job['citations']}, job)
    if status == 'failed':
        job['error'] = 'Research could not finish. Existing figures are unchanged.'
    save(inbox_dir, state)
    return True


@serialized_write
def failure(inbox_dir, key, exc, revision, *, submitting=False):
    state = load(inbox_dir)
    job = state['jobs'][key]
    if job['revision'] != revision or job['status'] in TERMINAL:
        return
    job['error'] = str(exc) if isinstance(exc, ResearchError) else 'Research could not complete. Existing figures are unchanged.'
    if submitting:
        job['status'] = 'submission_uncertain' if getattr(exc, 'uncertain', True) else 'failed'
    job.update(revision=job['revision'] + 1, updated_at=now().isoformat())
    save(inbox_dir, state)


def submit(inbox_dir, key, client_factory):
    job = claim(inbox_dir, key)
    if job:
        try:
            apply_result(inbox_dir, key, client_factory().start(prompt(job)), job['revision'])
        except Exception as exc:
            failure(inbox_dir, key, exc, job['revision'], submitting=True)


@serialized_write
def stop_unsubmitted(inbox_dir, key, revision):
    state = load(inbox_dir)
    job = state['jobs'][key]
    if job['status'] != 'requested' or job['revision'] != revision:
        raise ValueError('This research changed. Reload before stopping it.')
    job.update(status='cancelled', revision=job['revision'] + 1, updated_at=now().isoformat())
    save(inbox_dir, state)


def category(group):
    return tuple(group[k] for k in ('source', 'country_id', 'berry_id', 'commodity'))


def reference_revision(current, proposed):
    """Detect changed baseline/agency values outside the research-store revision."""
    keys = {category(group) for group in proposed}
    compared = sorted((group for group in current if category(group) in keys), key=category)
    return hashlib.sha256(json.dumps(compared, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def merge(baseline, approved):
    replacements = {category(group): group for group in approved}
    return [deepcopy(replacements.pop(category(group), group)) for group in baseline] + list(deepcopy(replacements).values())


@serialized_write
def apply(inbox_dir, key, selected, revision, actor, current, compared_revision=None):
    state = load(inbox_dir)
    if state['revision'] != revision:
        raise ValueError('Market research changed. Reload to compare the latest figures.')
    job = state['jobs'].get(key)
    if not job or job['status'] not in {'ready', 'partial'}:
        raise ValueError('Choose completed research before using figures.')
    current = current() if callable(current) else current
    if compared_revision is not None and compared_revision != reference_revision(current, job['groups']):
        raise ValueError('Current market figures changed. Reload and compare them before saving.')
    options = {group_id(g): g for g in job['groups']}
    if not selected or not set(selected).issubset(options) or not actor:
        raise ValueError('Select a displayed reference after checking its original source and figures.')
    chosen = [deepcopy(options[k]) for k in options if k in selected]
    old = {category(g): g for g in current}
    for group in chosen:
        previous = old.get(category(group))
        if previous and group['period'][:4] < previous['period'][:4]:
            raise ValueError('A newer period is already recorded for this source and crop. Keep the latest reference.')
        group['status'] = 'Source checked by analyst · statistical reference'
    before = deepcopy(state['approved'])
    after = merge(before, chosen)
    if after == before:
        return False
    state['approved'] = after
    state['history'].append({'job_id': key, 'actor': actor, 'at': now().isoformat(), 'before': before, 'after': deepcopy(after),
                             'compared': [deepcopy(old.get(category(g))) for g in chosen]})
    save(inbox_dir, state)
    return True


def references(baseline, inbox_dir):
    return merge(baseline, load(inbox_dir)['approved'])
