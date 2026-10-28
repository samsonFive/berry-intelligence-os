"""Request-scoped Digest views over the existing analyst stores.

Shared research, lists, marks and review decisions keep their existing scope.
Legacy personal state remains retained for the configured original analyst;
other accounts start with an empty personal view, never a copy of that history.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import hashlib
import json

_account = ContextVar('digest_account', default=None)
PERSONAL_DECISION_KEYS = {'saved', 'read'}


@contextmanager
def bind(username, legacy_owner):
    identity = str(username or '').strip().casefold()
    owner = str(legacy_owner or '').strip().casefold()
    token = _account.set((identity, bool(owner and identity == owner)) if identity else None)
    try:
        yield
    finally:
        _account.reset(token)


def account_key():
    value = _account.get()
    return 'account-' + hashlib.sha256(value[0].encode()).hexdigest() if value else ''


def legacy_access():
    value = _account.get()
    return value is None or value[1]


def _accounts(payload):
    value = payload.get('personal_accounts')
    return deepcopy(value) if isinstance(value, dict) else {}


def _entry(payload, key):
    accounts = payload.get('personal_accounts')
    return accounts.get(key) if isinstance(accounts, dict) else None


def read_for_write(path):
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise ValueError('Existing analyst state could not be read; changes were not saved') from exc
    if not isinstance(payload, dict) or ('personal_accounts' in payload and not isinstance(payload['personal_accounts'], dict)):
        raise ValueError('Existing analyst state is invalid; changes were not saved')
    return payload


def project_feed(payload, view):
    key = account_key()
    if not key:
        return view
    personal = _entry(payload, key)
    if not isinstance(personal, dict):
        personal = {'decisions': {
            item: {name: value for name, value in row.items() if name in PERSONAL_DECISION_KEYS}
            for item, row in (view.get('decisions') or {}).items() if isinstance(row, dict)
        }, 'digest_subscriptions': view.get('digest_subscriptions', [])} if legacy_access() else {}
    decisions = {
        item: {name: value for name, value in row.items() if name not in PERSONAL_DECISION_KEYS}
        for item, row in (view.get('decisions') or {}).items() if isinstance(row, dict)
    }
    for item, row in (personal.get('decisions') or {}).items():
        if isinstance(row, dict):
            decisions.setdefault(item, {}).update({name: value for name, value in row.items() if name in PERSONAL_DECISION_KEYS})
    return {**view, 'decisions': decisions,
            'digest_subscriptions': deepcopy(personal.get('digest_subscriptions') or [])}


def merge_feed(payload, view):
    key = account_key()
    result = {**payload, **view}
    accounts = _accounts(payload)
    if not key:
        if accounts:
            result['personal_accounts'] = accounts
        return result
    current = view.get('decisions') or {}
    accounts[key] = {
        'decisions': {item: {name: value for name, value in row.items() if name in PERSONAL_DECISION_KEYS}
                      for item, row in current.items() if isinstance(row, dict)},
        'digest_subscriptions': deepcopy(view.get('digest_subscriptions') or []),
    }
    # Keep the original shared personal fields as a retained legacy archive.
    legacy = payload.get('decisions') or {}
    result['decisions'] = {
        item: {**{name: value for name, value in row.items() if name not in PERSONAL_DECISION_KEYS},
               **{name: value for name, value in (legacy.get(item) or {}).items() if name in PERSONAL_DECISION_KEYS}}
        for item, row in current.items() if isinstance(row, dict)
    }
    result['digest_subscriptions'] = deepcopy(payload.get('digest_subscriptions') or [])
    result['personal_accounts'] = accounts
    return result


def project_queue(payload, view):
    key = account_key()
    if not key:
        return view
    personal = _entry(payload, key)
    reading = personal.get('reading', {}) if isinstance(personal, dict) else view.get('reading', {}) if legacy_access() else {}
    return {**view, 'reading': deepcopy(reading) if isinstance(reading, dict) else {}}


def merge_queue(payload, view):
    key = account_key()
    result = {**payload, **view}
    accounts = _accounts(payload)
    if not key:
        if accounts:
            result['personal_accounts'] = accounts
        return result
    accounts[key] = {'reading': deepcopy(view.get('reading') or {})}
    result['reading'] = deepcopy(payload.get('reading') or {})
    result['personal_accounts'] = accounts
    return result
