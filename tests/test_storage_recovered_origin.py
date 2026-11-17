"""Closed recovered-origin adoption of fictional native/manual evidence."""
import copy
import hashlib
import json

import pytest

from app.services import storage_recovery as recovery
from storage_recovered_origin_fixtures import recovered_origin_environment
from storage_recovery_fixtures import encoded
from test_storage_recovery import _memory_state, _reseal_memory_wrapper
from test_storage_retention import environment as accepted_environment


@pytest.fixture
def recovered_environment(accepted_environment):
    return recovered_origin_environment(accepted_environment)


def test_recovered_origin_profile_authenticates_native_and_manual_lineage(recovered_environment):
    env = recovered_environment
    state = _memory_state(env)
    recovery.validate_accepted_recovery_proofs(state['manifest'], read_file=state['read'], stat_file=state['stat'])
    native = recovery.accepted_native_origin(state['manifest'], read_file=state['read'], stat_file=state['stat'])
    assert native['native_origin'] == state['manifest']['accepted_native_origin']
    assert len(state['manifest']['live_binding']) == 8
    assert env['adoption_descriptor']['profile'] == recovery.ADOPTION_RECOVERED_LOGO_PROFILE
    # Admission-machine locators remain observations. They are never files in
    # the host protection closure; native/server refs authenticate their bytes.
    assert not any(pin['path'].startswith('C:\\fictional-admission\\') for pin in state['manifest']['accepted_content_pins'])
    assert 'accepted-private-value' not in json.dumps(state['manifest'])
    for reference in (env['wrapper']['plan'], env['wrapper']['recovery_files']['final_proof']):
        assert 'operation_kind' not in json.loads(state['bodies'][reference['path']])
    for profile in (recovery.ADOPTION_PROFILE, recovery.ADOPTION_LOGO_PROFILE):
        other = _memory_state(env); wrapper = copy.deepcopy(env['wrapper'])
        descriptor = copy.deepcopy(env['adoption_descriptor']); descriptor['profile'] = profile
        other['bodies'][wrapper['adoption']['path']] = encoded(descriptor)
        wrapper['adoption']['sha256'] = hashlib.sha256(encoded(descriptor)).hexdigest()
        _reseal_memory_wrapper(other, wrapper)
        with pytest.raises(recovery.StorageRecoveryError, match='accepted_adoption_profile_unsupported'):
            recovery.validate_accepted_recovery_proofs(other['manifest'], read_file=other['read'], stat_file=other['stat'])


def _profile_graph(env):
    """Re-seal descendants to test semantics beyond ordinary hash rejection.

    This exercises the profile validator directly; the separate positive above
    validates the entire accepted ledger/promotion/archive metadata closure.
    """
    state = _memory_state(env)
    load = lambda ref: json.loads(state['bodies'][ref['path']])
    wrapper = copy.deepcopy(env['wrapper'])
    descriptor = copy.deepcopy(env['adoption_descriptor'])
    plan = load(wrapper['plan']); admission = load(plan['proofs']['rehearsal'])
    bridge = admission['recovered_production_binding']
    capsule = load(descriptor['recovered_origin']); execution = load(capsule['transition_execution'])
    proof = load(execution['proof']); closure = load(capsule['recovery_closure'])
    health = load(closure['config_health_receipt']); manual = load(health['original_plan'])
    native_pre = load(wrapper['snapshots']['pre'])

    def seal(ref, value):
        state['bodies'][ref['path']] = value if isinstance(value, bytes) else encoded(value)
        return {'path': ref['path'], 'sha256': hashlib.sha256(state['bodies'][ref['path']]).hexdigest()}

    def check(*, after_seal=None):
        health['original_plan'] = seal(health['original_plan'], manual)
        closure['config_health_receipt'] = seal(closure['config_health_receipt'], health)
        capsule['recovery_closure'] = seal(capsule['recovery_closure'], closure)
        execution['proof'] = seal(execution['proof'], proof)
        execution['stdout'] = copy.deepcopy(execution['proof'])
        capsule['transition_execution'] = seal(capsule['transition_execution'], execution)
        bridge['execution']['sha256'] = capsule['transition_execution']['sha256']
        for key in ('proof', 'stdout', 'program'): bridge[key] = copy.deepcopy(execution[key])
        for key in ('raw_snapshots', 'original_baseline', 'original_pre_baseline', 'recovered_baseline'):
            bridge[key] = copy.deepcopy(proof[key])
        for key in ('program', 'proof', 'stdout'): bridge['local_transports'][key]['sha256'] = execution[key]['sha256']
        if after_seal: after_seal(bridge, capsule)
        plan['proofs']['rehearsal'] = seal(plan['proofs']['rehearsal'], admission)
        descriptor['recovered_origin'] = seal(descriptor['recovered_origin'], capsule)
        files = recovery._AcceptedFiles(state['read'], state['stat'])
        recovery._adoption_recovered_evidence({'descriptor': descriptor}, wrapper, plan, native_pre, files)
        return files

    return locals()


def test_recovered_profile_rejects_resealed_semantic_drift(recovered_environment):
    cases = [
        ('boolean-exit', 'accepted_recovered_execution_invalid'),
        ('no-manual-closure', 'accepted_recovered_origin_invalid'),
        ('wrong-server-mapping', 'accepted_recovered_execution_mapping_invalid'),
        ('unsafe-client-locator', 'accepted_recovered_observation_invalid'),
        ('transport-substitution', 'accepted_recovered_transport_mismatch'),
        ('historical-ledger', 'accepted_recovered_historical_ledger_mismatch'),
        ('producer-crosswire', 'accepted_recovered_producer_pin_mismatch'),
        ('raw-log-config', 'accepted_recovered_configuration_mismatch'),
        ('raw-oom', 'accepted_recovered_raw_pair_unhealthy'),
        ('raw-boolean-pid', 'accepted_recovered_raw_pair_unhealthy'),
        ('stale-native-pre', 'accepted_recovered_native_pre_mismatch'),
        ('native-mount-rw', 'accepted_recovered_native_pre_mismatch'),
        ('native-mount-source', 'accepted_recovered_native_pre_mismatch'),
        ('same-id-restart', 'accepted_recovered_lifecycle_mismatch'),
        ('boolean-restart-count', 'accepted_recovered_lifecycle_invalid'),
        ('manual-pair', 'accepted_recovered_manual_pair_mismatch'),
        ('manual-argv-env', 'accepted_recovered_manual_plan_invalid'),
        ('nonfinite-manual-times', 'accepted_recovered_manual_preservation_invalid'),
        ('historical-marker-claim', 'accepted_recovered_historical_markers_invalid'),
        ('rollback-not-completed', 'accepted_recovered_rollback_invalid'),
    ]
    for change, reason in cases:
        graph = _profile_graph(recovered_environment)
        proof, execution, capsule = (graph[name] for name in ('proof', 'execution', 'capsule'))
        after_seal = None
        if change == 'boolean-exit': execution['exit_code'] = False
        elif change == 'no-manual-closure':
            after_seal = lambda _bridge, value: value.pop('recovery_closure')
        elif change == 'wrong-server-mapping':
            after_seal = lambda bridge, _capsule: bridge['execution'].update(sha256='f' * 64)
        elif change == 'unsafe-client-locator':
            after_seal = lambda bridge, _capsule: bridge['execution'].update(path='relative/execution.json')
        elif change == 'transport-substitution':
            after_seal = lambda bridge, _capsule: bridge['local_transports']['program'].update(sha256='e' * 64)
        elif change == 'historical-ledger': proof['ledgers']['current']['sha256'] = 'a' * 64
        elif change == 'producer-crosswire':
            body = graph['state']['bodies'][execution['program']['path']]
            old = proof['binding_program']['sha256'].encode()
            execution['program'] = graph['seal'](execution['program'], body.replace(old, b'0' * 64))
        elif change.startswith('raw-'):
            ref = proof['raw_snapshots']['original']
            pair = json.loads(graph['state']['bodies'][ref['path']])
            if change == 'raw-log-config': pair['app']['HostConfig']['LogConfig'] = {'Type': 'json-file', 'Config': {'max-size': '1m'}}
            elif change == 'raw-oom': pair['app']['State']['OOMKilled'] = True
            else: pair['copilot']['State']['Pid'] = True
            proof['raw_snapshots']['original'] = graph['seal'](ref, pair)
        elif change == 'stale-native-pre': graph['native_pre']['app']['HostConfig']['LogConfig']['Config']['unaccepted'] = 'drift'
        elif change == 'native-mount-rw': graph['native_pre']['app']['Mounts'][0]['RW'] = not graph['native_pre']['app']['Mounts'][0]['RW']
        elif change == 'native-mount-source': graph['native_pre']['app']['Mounts'][0]['Source'] += '/unaccepted'
        elif change == 'same-id-restart':
            graph['native_pre']['app']['RestartCount'] += 1
            graph['native_pre']['app']['State']['StartedAt'] = '2026-11-10T03:30:00Z'
        elif change == 'boolean-restart-count': graph['native_pre']['app']['RestartCount'] = False
        elif change == 'manual-pair': graph['health']['pair']['app']['id'] = 'e' * 64
        elif change == 'manual-argv-env': graph['manual']['argv'].remove('--env-file')
        elif change == 'nonfinite-manual-times':
            graph['manual']['native_created_at'] = float('-inf')
            graph['health']['finished_at_unix'] = graph['closure']['closed_at_unix'] = float('inf')
        elif change == 'historical-marker-claim': proof['rollback']['markers']['data']['exists'] = True
        else:
            journal = json.loads(graph['state']['bodies'][proof['rollback']['journal']['path']])
            journal['state'] = 'applying'
            proof['rollback']['journal'] = graph['seal'](proof['rollback']['journal'], journal)
        with pytest.raises(recovery.StorageRecoveryError, match=reason):
            graph['check'](after_seal=after_seal)


def test_recovered_profile_keeps_historical_observations_and_client_paths_inert(recovered_environment):
    graph = _profile_graph(recovered_environment)
    # The actual current store is active; the earlier rollback observation says
    # absent. Both are truthful at different times. No live absence probe occurs.
    assert recovered_environment['active_store_marker'].exists()
    # Docker may reorder the same full effective Mounts rows on a later inspect.
    graph['native_pre']['app']['Mounts'].reverse()
    files = graph['check']()
    assert str(recovery.LEDGER_PATH) not in files.pins
    assert not any(name.startswith('C:\\fictional-admission\\') for name in files.pins)
    assert graph['proof']['ledgers']['immutable']['path'] in files.pins
    assert graph['proof']['raw_snapshots']['original']['path'] in files.pins
    assert graph['proof']['raw_snapshots']['recovered']['path'] in files.pins
