"""Explicit, bounded private Apify jobs. No scheduler or automatic ingestion.

An uncertain submission consumes its reservation and is never relaunched. Poll
the persisted run ID; observation timeouts do not mean the actor stopped.
"""
import hashlib
import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx
from jsonschema import Draft7Validator

from app.services.analyst_state_io import atomic_json
from app.services.collection_runner import CollectionRunLock
from .adapters import AccessBlocked

ACTORS = {'apify/facebook-posts-scraper', 'apify/instagram-scraper',
          'harvestapi/linkedin-post-search'}
TERMINAL = {'SUCCEEDED', 'FAILED', 'TIMED-OUT', 'ABORTED'}


class ApifyJobs:
    def __init__(self, private_dir, *, enabled=False, client=None, token=None):
        self.folder = Path(private_dir)
        self.enabled = enabled
        self.token = token or os.environ.get('APIFY_TOKEN')
        self.client = client or httpx.Client(timeout=30, follow_redirects=False)
        self.ledger_path = self.folder / 'ledger.json'

    def _read(self):
        if not self.ledger_path.exists():
            return {'ceiling_free_credit_usd': 1, 'cash_spend': 0, 'attempts': []}
        try:
            ledger = json.loads(self.ledger_path.read_text(encoding='utf-8'))
            ceiling = ledger['ceiling_free_credit_usd']
            if (not isinstance(ledger['attempts'], list) or ledger.get('cash_spend') != 0
                    or not isinstance(ceiling, (int, float)) or not math.isfinite(ceiling) or not 0 < ceiling <= 2
                    or len({a.get('case') for a in ledger['attempts'] if isinstance(a, dict)}) != len(ledger['attempts'])
                    or any(not isinstance(a, dict) or not isinstance(a.get('case'), str)
                           or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', a['case'])
                           or not isinstance(a.get('cap_usd'), (int, float)) or not math.isfinite(a['cap_usd'])
                           or not 0 < a['cap_usd'] <= .1 for a in ledger['attempts'])):
                raise ValueError()
            return ledger
        except (ValueError, KeyError, TypeError):
            raise AccessBlocked('Private job ledger unreadable; do not launch') from None

    def _request(self, method, path, *, params=None, body=None):
        if not self.enabled or not self.token:
            raise AccessBlocked('Explicit live opt-in and private APIFY_TOKEN required')
        try:
            with self.client.stream(method, 'https://api.apify.com/v2' + path,
                                    params=params, json=body, follow_redirects=False,
                                    headers={'Authorization': 'Bearer ' + self.token}) as response:
                expected = 201 if method == 'POST' else 200
                if response.status_code != expected:
                    raise AccessBlocked(f'Apify HTTP {response.status_code}; no retry')
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 2_000_000:
                        raise AccessBlocked('Apify response byte ceiling exceeded')
            return json.loads(raw)
        except (httpx.HTTPError, ValueError):
            raise AccessBlocked('Apify transport/schema failure; no retry') from None

    def launch(self, case, actor, *, build_id, build_number, actor_input, cap_usd=.1):
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', case):
            raise ValueError('Bounded case identifier required')
        if actor not in ACTORS or not re.fullmatch(r'[A-Za-z0-9]{5,50}', build_id):
            raise AccessBlocked('Inspected actor and exact build identity required')
        if not re.fullmatch(r'\d+\.\d+\.\d+', build_number):
            raise AccessBlocked('Exact build number required; latest is not a pin')
        if not isinstance(actor_input, dict) or len(json.dumps(actor_input)) > 8000:
            raise ValueError('Bounded actor input required')
        if not isinstance(cap_usd, (float, int)) or not math.isfinite(cap_usd) or not 0 < cap_usd <= .1:
            raise ValueError('Trial cap must be positive and at most $0.10 included credit')
        self.folder.mkdir(parents=True, exist_ok=True)
        with CollectionRunLock(self.folder / 'collection.lock', run_id=case):
            ledger = self._read()
            fingerprint = hashlib.sha256(json.dumps([actor, build_id, build_number, actor_input], sort_keys=True).encode()).hexdigest()
            previous = next((a for a in ledger['attempts'] if a['case'] == case), None)
            if previous:
                if previous.get('fingerprint') != fingerprint:
                    raise AccessBlocked('Existing case input differs or predates this runner; no relaunch')
                return {**previous, 'reused': True}
            account = self._request('GET', '/users/me')['data']
            limits = self._request('GET', '/users/me/limits')['data']
            current = limits['current']
            usage = current['monthlyUsageUsd']
            reserved = math.fsum(a['cap_usd'] for a in ledger['attempts'])
            ceiling = ledger['ceiling_free_credit_usd']
            if (account.get('plan', {}).get('id') != 'FREE' or account.get('isPaying') is not False
                    or limits['limits']['maxMonthlyUsageUsd'] > 5
                    or not isinstance(usage, (int, float)) or not math.isfinite(usage) or usage < 0
                    or usage + cap_usd > ceiling or reserved + cap_usd > ceiling
                    or current.get('activeActorJobCount') != 0):
                raise AccessBlocked('Fresh free-account, non-overlap or conservative reservation budget guard blocked')
            metadata = self._request('GET', '/acts/' + actor.replace('/', '~'))['data']
            build = self._request('GET', '/actor-builds/' + build_id)['data']
            if (build.get('status') != 'SUCCEEDED' or build.get('id') != build_id
                    or build.get('buildNumber') != build_number or not metadata.get('id')
                    or build.get('actId') != metadata['id']):
                raise AccessBlocked('Inspected build differs from requested pin')
            pricing = metadata.get('currentPricingInfo')
            if not pricing:
                # Actual API may return null currentPricingInfo with dated history.
                # Select only an already effective version, never a future change.
                now = datetime.now(timezone.utc)
                effective = []
                for candidate in metadata.get('pricingInfos', []):
                    try:
                        started = datetime.fromisoformat(candidate['startedAt'].replace('Z', '+00:00'))
                        ended = datetime.fromisoformat(candidate['endedAt'].replace('Z', '+00:00')) if candidate.get('endedAt') else None
                        if started.tzinfo and started <= now and (ended is None or now < ended):
                            effective.append((started, candidate))
                    except (ValueError, KeyError, TypeError):
                        raise AccessBlocked('Pricing version dates unrecognized') from None
                if effective:
                    effective.sort(key=lambda value: value[0], reverse=True)
                    if len(effective) > 1 and effective[0][0] == effective[1][0]:
                        raise AccessBlocked('Pricing version ambiguity')
                    pricing = effective[0][1]
            if not pricing or pricing.get('pricingModel') != 'PAY_PER_EVENT':
                raise AccessBlocked('Only inspected event-priced actors eligible; rental/unknown pricing blocked')
            Draft7Validator(json.loads(build['inputSchema'])).validate(actor_input)
            memory = metadata['defaultRunOptions']['memoryMbytes']
            if not isinstance(memory, int) or not 128 <= memory <= 8192:
                raise AccessBlocked('Unbounded actor memory configuration')
            entry = {'case': case, 'actor': actor, 'build_id': build_id, 'build_number': build_number,
                     'actor_id': metadata['id'], 'pricing_model': pricing['pricingModel'],
                     'pricing_started_at': pricing.get('startedAt'), 'input': actor_input, 'fingerprint': fingerprint, 'cap_usd': cap_usd,
                     'reserved_at': datetime.now(timezone.utc).isoformat(),
                     'state': 'reserved-before-launch', 'usage_before': usage}
            ledger['attempts'].append(entry)
            atomic_json(self.ledger_path, ledger)
            # Any exception after reservation leaves the case consumed. Even a
            # lost HTTP response may have started an actor: never retry POST.
            run = self._request('POST', '/acts/' + actor.replace('/', '~') + '/runs',
                                params={'build': build_number, 'timeout': 90, 'memory': memory,
                                        'maxTotalChargeUsd': cap_usd, 'restartOnError': 'false',
                                        'forcePermissionLevel': 'LIMITED_PERMISSIONS', 'waitForFinish': 0},
                                body=actor_input)['data']
            if not re.fullmatch(r'[A-Za-z0-9]{5,50}', run.get('id', '')):
                raise AccessBlocked('No usable run identity; reconcile reserved submission manually')
            entry.update(run_id=run['id'], state=run['status'])
            atomic_json(self.ledger_path, ledger)
            if run.get('buildId') != build_id or run.get('actId') != metadata['id']:
                raise AccessBlocked('Submitted run/build/actor mismatch; retain saved run for reconciliation')
            return {**entry, 'reused': False}

    def observe(self, case):
        """One bounded poll. Terminal success fetches at most twenty items.

        Failed/aborted runs do not count as successful zero results. Cost may
        settle later; usageTotalUsd is an observation, not a final invoice.
        """
        if not isinstance(case, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', case):
            raise ValueError('Bounded case identifier required')
        self.folder.mkdir(parents=True, exist_ok=True)
        with CollectionRunLock(self.folder / 'collection.lock', run_id='observe'):
            ledger = self._read()
            entry = next((a for a in ledger['attempts'] if a['case'] == case), None)
            if not entry or not re.fullmatch(r'[A-Za-z0-9]{5,50}', entry.get('run_id', '')):
                raise AccessBlocked('No saved run ID; do not relaunch an uncertain submission')
            run = self._request('GET', '/actor-runs/' + entry['run_id'])['data']
            if run.get('id') != entry['run_id'] or run.get('buildId') != entry['build_id']:
                raise AccessBlocked('Run/build identity mismatch')
            entry.update(state=run['status'], usage_total_usd=run.get('usageTotalUsd'))
            atomic_json(self.ledger_path, ledger)
            if run['status'] != 'SUCCEEDED':
                return {'case': case, 'run_id': entry['run_id'], 'state': run['status'],
                        'terminal': run['status'] in TERMINAL, 'items': None}
            dataset = run.get('defaultDatasetId', '')
            if not re.fullmatch(r'[A-Za-z0-9]{5,50}', dataset):
                raise AccessBlocked('Missing terminal dataset identity')
            items = self._request('GET', '/datasets/' + dataset + '/items', params={'limit': 20, 'clean': 'true'})
            if not isinstance(items, list) or len(items) > 20:
                raise AccessBlocked('Dataset schema/item ceiling exceeded')
            atomic_json(self.folder / (case + '-items.json'), items)
            entry['returned'] = len(items)
            entry['data_observed_at'] = datetime.now(timezone.utc).isoformat()
            atomic_json(self.ledger_path, ledger)
            return {'case': case, 'run_id': entry['run_id'], 'state': 'SUCCEEDED',
                    'terminal': True, 'items': items}


    def normalize_cached(self, case):
        """Offline export for existing schema-validated import; no Store write.

        Imported provenance is intentional. Re-reading a cached response is not
        a new live observation or independent language/relevance review.
        """
        if not isinstance(case, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', case):
            raise ValueError('Bounded case identifier required')
        from .apify_intake import apify_dataset
        ledger = self._read()
        entry = next((a for a in ledger['attempts'] if a['case'] == case), None)
        if not entry or entry.get('state') != 'SUCCEEDED':
            raise AccessBlocked('Successful saved job required; unfinished/failing jobs are not importable zeroes')
        source = {'apify/facebook-posts-scraper': 'facebook',
                  'apify/instagram-scraper': 'instagram',
                  'harvestapi/linkedin-post-search': 'linkedin'}.get(entry.get('actor'))
        if not source or not entry.get('build_number'):
            raise AccessBlocked('Saved source/build contract unrecognized')
        cache = self.folder / (case + '-items.json')
        if not cache.exists() or cache.stat().st_size > 2_000_000:
            raise AccessBlocked('Successful bounded raw dataset cache required')
        raw = cache.read_bytes()
        items = json.loads(raw)
        captured = entry.get('data_observed_at')
        basis = 'Saved dataset observation timestamp'
        if not captured:
            captured = datetime.fromtimestamp(cache.stat().st_mtime, timezone.utc).isoformat()
            basis = 'Legacy cached receipt file-save timestamp, not publication time'
        result = apify_dataset(items, source=source, build=entry['build_number'],
                               collected_at=captured, mode='imported')
        for row in result['rows']:
            row['permission_basis'] += '; ' + basis
        # Conflicts fail before write; rejection counts remain explicit in a
        # separate receipt. Operator reviews rows before existing import.
        output = self.folder / (case + '-normalized-import.json')
        atomic_json(output, result['rows'])
        receipt = {'case': case, 'state': 'normalized-cached', 'mode': 'imported',
                   'input_items': result['input_items'], 'normalized': len(result['rows']),
                   'rejected': len(result['rejected']), 'duplicate_copies': result['duplicate_copies'],
                   'collection_time_basis': basis, 'data_observed_at': captured,
                   'run_id': entry.get('run_id'), 'dataset_sha256': hashlib.sha256(raw).hexdigest(),
                   'new_source_calls': 0, 'ingested': False,
                   'file': str(output)}
        atomic_json(self.folder / (case + '-normalization.json'), receipt)
        return receipt


    def cached_status(self):
        """Content-free cached status, never fresh account/coverage verification."""
        ledger = self._read()
        jobs = []
        sources = {'apify/facebook-posts-scraper': 'facebook',
                   'apify/instagram-scraper': 'instagram',
                   'harvestapi/linkedin-post-search': 'linkedin'}
        for entry in ledger['attempts']:
            source = sources.get(entry.get('actor'))
            if not source:
                raise AccessBlocked('Saved actor unrecognized')
            case = entry['case']
            state = entry.get('state')
            status = 'failed' if state in ('FAILED', 'ABORTED', 'TIMED-OUT', 'launch-rejected') else 'unknown'
            volume, last_success = None, None
            note = 'Saved run is unfinished or unverified; this is not zero conversation'
            receipt_path = self.folder / (case + '-normalization.json')
            cache = self.folder / (case + '-items.json')
            if state == 'SUCCEEDED':
                note = 'Provider run completed; cached rows have not been verified by normalization'
                if receipt_path.exists() and cache.exists() and receipt_path.stat().st_size <= 16000 and cache.stat().st_size <= 2_000_000:
                    try:
                        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
                        bound = (receipt.get('case') == case and receipt.get('run_id') == entry.get('run_id')
                                 and receipt.get('dataset_sha256') == hashlib.sha256(cache.read_bytes()).hexdigest())
                        counts = [receipt.get(k) for k in ('normalized', 'rejected', 'input_items')]
                        valid_counts = all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in counts)
                        if bound and valid_counts:
                            normalized, rejected, input_items = counts
                            if normalized or not rejected and input_items == 0:
                                status, volume = 'partial', normalized
                                captured = datetime.fromisoformat(receipt['data_observed_at'].replace('Z', '+00:00'))
                                if captured.tzinfo is None or captured > datetime.now(timezone.utc):
                                    raise ValueError('Invalid cached capture timestamp')
                                last_success = captured.isoformat()
                                note = 'One-off normalized snapshot; not ongoing monitoring, relevance, language or country coverage'
                                if rejected:
                                    note += '; some returned items failed normalization'
                            else:
                                status = 'failed'
                                note = 'Returned items failed post/comment normalization; not a successful zero-result search'
                        else:
                            note = 'Cached normalization receipt no longer matches this run/dataset; results unverified'
                    except (ValueError, KeyError, TypeError):
                        status, volume, last_success = 'unknown', None, None
                        note = 'Cached normalization receipt invalid; results unverified'
            jobs.append({'id': 'apify-trial-' + case, 'source': source,
                         'market': 'No market target', 'language': 'und', 'status': status,
                         'started_at': entry.get('reserved_at'), 'last_success': last_success,
                         'observed_volume': volume, 'failure': note, 'query_changed': True,
                         'query_label': case, 'mode': 'live', 'provider_run_state': state,
                         'cost_usd': entry.get('usage_total_usd'), 'cost_final': False})
        return {'state': 'cached-status', 'jobs': jobs,
                'reserved_free_credit_usd': round(sum(a['cap_usd'] for a in ledger['attempts']), 6),
                'trial_ceiling_usd': ledger['ceiling_free_credit_usd'], 'attempts': len(jobs),
                'fresh_account_verified': False, 'scheduled_collection': False, 'new_source_calls': 0}
