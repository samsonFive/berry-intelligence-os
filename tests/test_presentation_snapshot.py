"""Typed output/copy isolation and internal-only snapshot boundaries."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date, datetime, UTC
from enum import IntEnum
import math
import pickle
import random
import json

import pytest
from markupsafe import Markup

from app.services import presentation_memo as service


def assert_types(left, right):
    assert type(left) is type(right)
    if type(left) is dict:
        assert left.keys() == right.keys()
        for key in left:
            assert_types(left[key], right[key])
    elif type(left) in {list, tuple}:
        assert len(left) == len(right)
        for a, b in zip(left, right):
            assert_types(a, b)


def test_large_model_retains_types_aliases_and_owned_results():
    shared = [{'decision': 'unresolved', 'sources': ['source-a']}]
    value = {'rows': [{'name': 'Berry ' + str(n), 'notes': 'Source wording ' * 10} for n in range(1000)],
             'shared': shared, 'again': shared, 'tuple': ('raw', shared),
             'set': {'source-a', 'source-b'}, 'numbers': (True, 1, 1.0, -0.0, 2 ** 100)}
    expected = deepcopy(value)
    memo = service.ByteMemo(max_item=2_000_000)
    memo.put('model', value)
    value['rows'][0]['notes'] = 'Later source edit'
    shared[0]['decision'] = 'confirmed'
    result = memo.get('model')
    assert result == expected
    assert_types(result, expected)
    assert result['shared'] is result['again'] is result['tuple'][1]
    assert math.copysign(1, result['numbers'][3]) == -1
    result['shared'][0]['sources'].append('different')
    result['rows'][0]['notes'] = 'A local display edit'
    assert memo.get('model') == expected
    assert memo.bytes <= memo.max_bytes


@pytest.mark.parametrize('seed', range(40))
def test_supported_graphs_match_deepcopy_values_and_types(monkeypatch, seed):
    monkeypatch.setattr(service, '_SNAPSHOT_MIN_BYTES', 0)
    rng = random.Random(seed)
    def graph(depth):
        if depth == 0:
            return rng.choice([None, True, False, 1, -7, 3.5, -0.0, 2 ** 100, 'Bær / 甜 / 🌱'])
        children = [graph(depth - 1) for _ in range(rng.randrange(1, 5))]
        return rng.choice([children, tuple(children), {str(i): row for i, row in enumerate(children)}])
    value = graph(4)
    memo = service.ByteMemo()
    memo.put('graph', value)
    copied = memo.get('graph')
    assert copied == deepcopy(value)
    assert_types(copied, value)


@pytest.mark.parametrize('special', [date(2026, 11, 2), datetime(2026, 11, 2, tzinfo=UTC), float('nan'), float('inf'), Markup('<strong>existing trusted markup</strong>')])
def test_other_types_and_nonfinite_numbers_keep_legacy_copy_semantics(monkeypatch, special):
    monkeypatch.setattr(service, '_SNAPSHOT_MIN_BYTES', 0)
    memo = service.ByteMemo()
    value = {'special': special, 'rows': [1, 2]}
    memo.put('legacy', value)
    copied = memo.get('legacy')
    assert type(copied['special']) is type(special)
    if type(special) is float:
        assert copied['special'] is special
    else:
        assert copied['special'] == special
    copied['rows'].append(3)
    assert memo.get('legacy')['rows'] == [1, 2]


def test_dict_subclasses_use_original_deepcopy_behavior(monkeypatch):
    monkeypatch.setattr(service, '_SNAPSHOT_MIN_BYTES', 0)
    class Annotated(dict):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.annotation = ['keep me']
    original = Annotated(rows=['source wording'])
    memo = service.ByteMemo()
    memo.put('custom', original)
    original.annotation.append('later')
    copied = memo.get('custom')
    assert type(copied) is Annotated and copied.annotation == ['keep me']
    copied.annotation.append('display edit')
    assert memo.get('custom').annotation == ['keep me']


def test_snapshot_creation_denies_custom_reducers_before_legacy_copy(monkeypatch):
    monkeypatch.setattr(service, '_SNAPSHOT_MIN_BYTES', 0)
    calls = []
    class Custom(dict):
        def __reduce_ex__(self, protocol):
            calls.append('reduce')
            raise AssertionError('The snapshot path must reject classes first')
        def __deepcopy__(self, memo):
            calls.append('deepcopy')
            return Custom(deepcopy(dict(self), memo))
    memo = service.ByteMemo()
    memo.put('custom', {'nested': Custom(rows=['original'])})
    copied = memo.get('custom')
    assert type(copied['nested']) is Custom and copied == {'nested': {'rows': ['original']}}
    assert calls == ['deepcopy', 'deepcopy']


def test_nan_dictionary_key_keeps_legacy_identity(monkeypatch):
    monkeypatch.setattr(service, '_SNAPSHOT_MIN_BYTES', 0)
    nan = float('nan')
    memo = service.ByteMemo()
    memo.put('numbers', {nan: 'original'})
    copied = memo.get('numbers')
    assert next(iter(copied)) is nan and copied[nan] == 'original'


def test_large_immutable_text_keeps_constant_time_legacy_copy():
    value = 'Publisher source wording. ' * 10000
    memo = service.ByteMemo(max_item=1_000_000)
    memo.put('text', value)
    assert memo.get('text') is value


def test_binary_overhead_does_not_change_legacy_cache_admission():
    value = ['x' * 100000]
    limit = len('one'.encode()) + len(json.dumps(value, ensure_ascii=False).encode())
    memo = service.ByteMemo(max_bytes=limit, max_item=limit)
    memo.put('one', value)
    assert memo.get('one') == value and memo.bytes == limit
    assert memo.get('one')[0] is value[0]


def test_integer_enum_type_is_not_flattened(monkeypatch):
    monkeypatch.setattr(service, '_SNAPSHOT_MIN_BYTES', 0)
    class Level(IntEnum):
        REVIEWED = 1
    memo = service.ByteMemo()
    memo.put('enum', {'status': Level.REVIEWED})
    assert memo.get('enum')['status'] is Level.REVIEWED


@pytest.mark.parametrize('payload', [b'not a pickle', pickle.dumps(date(2026, 11, 2), protocol=5)])
def test_corrupt_or_class_loading_internal_entry_is_a_cache_miss(monkeypatch, payload):
    monkeypatch.setattr(service, '_SNAPSHOT_MIN_BYTES', 0)
    memo = service.ByteMemo()
    memo.put('model', {'status': 'unreviewed'})
    size = memo.rows['model'][1]
    memo.rows['model'] = (service._BuiltinSnapshot(payload), size)
    # The second payload needs a global datetime class lookup, forbidden even
    # though datetime values are harmless when handled by legacy deepcopy.
    assert memo.get('model') is None and 'model' not in memo.rows and memo.bytes == 0


def test_parallel_cached_readers_never_share_mutable_output(monkeypatch):
    monkeypatch.setattr(service, '_SNAPSHOT_MIN_BYTES', 0)
    memo = service.ByteMemo()
    memo.put('shared', {'rows': [{'status': 'unreviewed'}]})
    def read(n):
        value = memo.get('shared')
        value['rows'][0]['status'] = str(n)
        return value
    with ThreadPoolExecutor(max_workers=8) as pool:
        values = list(pool.map(read, range(64)))
    assert [v['rows'][0]['status'] for v in values] == [str(n) for n in range(64)]
    assert memo.get('shared') == {'rows': [{'status': 'unreviewed'}]}
