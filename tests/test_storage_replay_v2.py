"""Closed v2 evidence regressions using fictional native/resource fixtures."""
import copy
import hashlib
import json
import os
from pathlib import Path

import pytest

from test_storage_retention import environment as accepted_environment
from test_storage_recovery import _memory_state
from storage_replay_v2_fixtures import replay_v2_environment
from storage_recovery_fixtures import encoded
from app.services import storage_recovery as recovery


@pytest.fixture
def replay(accepted_environment):
    return replay_v2_environment(accepted_environment)


def test_v2_new_owned_qualification_accepts_same_id_at_fresh_empty_base_without_old_plan_parse(replay, monkeypatch):
    state = _memory_state(replay)
    old_plan = state['bodies'][replay['wrapper']['recovery_files']['raw_plan']['path']]
    parsed = recovery._parsed
    def bounded_metadata(body):
        assert body != old_plan, 'original PLAN must be streamed, never parsed to recover timestamps'
        return parsed(body)
    monkeypatch.setattr(recovery, '_parsed', bounded_metadata)
    recovery.validate_accepted_recovery_proofs(state['manifest'], read_file=state['read'], stat_file=state['stat'])
    original = replay['original_preparation']
    observed = replay['replay_resource']['prepare_apply_execution']
    result = json.loads(state['bodies'][observed['result']['path']])
    assert result['apply']['resume_id'] == original['migration_id']
    assert original['sha256'] != original['canonical_sha256']
    assert replay['fresh_preparation']['sha256'] != original['sha256']
    assert not any(pin['path'] == result['artifacts']['prepared_migration_plan']['path']
                   for pin in state['manifest']['accepted_content_pins'])


def test_v2_requires_resource_kernel_and_actual_functional_image_evidence(replay):
    state = _memory_state(replay); baseline = copy.deepcopy(state['bodies'])
    for which in ('kernel', 'native'):
        state['bodies'].clear(); state['bodies'].update(baseline)
        ref = (replay['replay_resource']['prepare_apply_execution']['kernel'] if which == 'kernel'
               else replay['replay_verification']['native_receipt'])
        state['bodies'].pop(ref['path'])
        with pytest.raises(recovery.StorageRecoveryError, match='accepted_recovery_proof_invalid'):
            recovery.validate_accepted_recovery_proofs(state['manifest'], read_file=state['read'], stat_file=state['stat'])


def _protocol_call(state, protocol=None, verified=None):
    env = state['env']; wrapper = env['wrapper']; archive = wrapper['archives']['current']
    load = lambda ref: json.loads(state['bodies'][ref['path']])
    recipe = load(archive['recovery_recipe'])
    recovery._replay_protocol_v2(protocol or load(recipe['replay_protocol']), verified or load(recipe['protocol_verification']),
        recipe, archive, wrapper['recovery_files'], load(wrapper['recovery_files']['final_proof']),
        load(wrapper['recovery_files']['final_proof']), load(wrapper['plan']),
        recovery._AcceptedFiles(state['read'], state['stat']))


def _replace(state, reference, value):
    state['bodies'][reference['path']] = encoded(value)
    reference['sha256'] = hashlib.sha256(encoded(value)).hexdigest()


def test_v2_resealed_functional_receipts_cannot_hide_source_only_resume_replan_or_rewrite(replay):
    state = _memory_state(replay); baseline = copy.deepcopy(state['bodies'])
    cases = [('source-only', 'replay_v2_native_invalid'), ('wrong-id', 'replay_v2_apply_invalid'),
             ('replan', 'replay_v2_apply_invalid'), ('rewrite', 'replay_v2_apply_invalid'),
             ('raw-as-canonical', 'replay_v2_native_invalid'), ('boolean-check', 'replay_v2_native_invalid')]
    for change, reason in cases:
        state['bodies'].clear(); state['bodies'].update(baseline)
        verified = copy.deepcopy(replay['replay_verification'])
        native = copy.deepcopy(replay['native_replay'])
        if change == 'source-only': native['execution_context'] = 'source-api-only'
        elif change == 'wrong-id': native['apply']['resume_id'] = 'information-' + '0' * 20
        elif change == 'replan': native['apply']['plan_calls'] = 2
        elif change == 'rewrite': native['apply']['aggregate_plan_writes'] = 1
        elif change == 'raw-as-canonical': native['prepared_plan']['canonical_sha256'] = native['prepared_plan']['sha256']
        else: native['checks']['no-old-plan-reuse'] = 1
        _replace(state, verified['native_receipt'], native)
        with pytest.raises(recovery.StorageRecoveryError, match=reason):
            _protocol_call(state, verified=verified)


def test_v2_resealed_kernel_numbers_and_empty_base_are_required(replay):
    state = _memory_state(replay); baseline = copy.deepcopy(state['bodies'])
    for change, reason in [('float-cap', 'replay_v2_kernel_invalid'), ('boolean-exit', 'replay_v2_kernel_invalid'),
                           ('oom', 'replay_v2_kernel_invalid'), ('not-empty', 'replay_v2_qualification_invalid'),
                           ('old-path', 'replay_v2_qualification_invalid'), ('early-oom', 'replay_v2_kernel_invalid')]:
        state['bodies'].clear(); state['bodies'].update(baseline)
        verified = copy.deepcopy(replay['replay_verification']); evidence = copy.deepcopy(replay['replay_resource'])
        role = evidence['metadata_execution']
        if change in {'not-empty', 'old-path'}:
            role = evidence['prepare_apply_execution']
            completion = json.loads(state['bodies'][role['completion']['path']])
            if change == 'not-empty':
                completion['backup_base_before']['entries'] = ['old-failed-plan']
            else:
                result = json.loads(state['bodies'][role['result']['path']])
                result['artifacts']['prepared_migration_plan']['path'] = replay['original_preparation']['path']
                _replace(state, role['result'], result)
                kernel = json.loads(state['bodies'][role['kernel']['path']])
                kernel['result_sha256'] = role['result']['sha256']; _replace(state, role['kernel'], kernel)
                worker = json.loads(state['bodies'][completion['native_completion']['path']])
                worker['result_sha256'] = role['result']['sha256']; _replace(state, completion['native_completion'], worker)
                completion.update(result=role['result'], kernel=role['kernel'])
            _replace(state, role['completion'], completion)
        elif change == 'boolean-exit':
            inspection = json.loads(state['bodies'][role['inspection']['path']])
            inspection['State']['ExitCode'] = False
            _replace(state, role['inspection'], inspection)
        else:
            kernel = json.loads(state['bodies'][role['kernel']['path']])
            if change == 'float-cap': kernel['memory_max_bytes'] = float(kernel['memory_max_bytes'])
            elif change == 'early-oom': kernel['events_before']['oom_kill'] = kernel['events_after']['oom_kill'] = 1
            else: kernel['events_after']['oom_kill'] = 1
            _replace(state, role['kernel'], kernel)
        _replace(state, verified['resource_evidence'], evidence)
        with pytest.raises(recovery.StorageRecoveryError, match=reason):
            _protocol_call(state, verified=verified)


def test_v2_provenance_receipt_is_not_a_resume_argument_or_substitutable_raw_plan(replay):
    state = _memory_state(replay)
    for apply in ({'resume_id': None}, {'resume_id': replay['original_preparation']['migration_id']}, {'no_replan': 1}):
        protocol = copy.deepcopy(replay['replay_protocol']); protocol['apply'].update(apply)
        with pytest.raises(recovery.StorageRecoveryError, match='replay_v2_protocol_invalid'):
            _protocol_call(state, protocol=protocol)
    protocol = copy.deepcopy(replay['replay_protocol'])
    protocol['plan']['original_preparation_receipt']['path'] += '.valid-copy'
    with pytest.raises(recovery.StorageRecoveryError, match='replay_v2_original_preparation_invalid'):
        _protocol_call(state, protocol=protocol)


def test_v2_resealed_native_labels_cannot_override_actual_image_argv_or_mounts(replay):
    state = _memory_state(replay); baseline = copy.deepcopy(state['bodies'])
    for change in ('local-source', 'no-isolation', 'app-mount', 'writable-code', 'wrong-image'):
        state['bodies'].clear(); state['bodies'].update(baseline)
        verified = copy.deepcopy(replay['replay_verification'])
        execution = json.loads(state['bodies'][verified['native_execution']['path']])
        inspection = json.loads(state['bodies'][execution['inspection']['path']])
        if change == 'local-source': inspection['Config']['Cmd'] += ['--local-source', '/fictional/source']
        elif change == 'no-isolation': inspection['Config']['Cmd'].remove('-I')
        elif change == 'app-mount': inspection['Mounts'].append({'Type': 'bind', 'Source': '/fictional/source', 'Destination': '/app', 'RW': False})
        elif change == 'writable-code': inspection['Mounts'][0]['RW'] = True
        else: inspection['Image'] = 'sha256:' + '9' * 64
        inspection['Args'] = inspection['Config']['Cmd'][1:]
        _replace(state, execution['inspection'], inspection)
        completion = json.loads(state['bodies'][execution['completion']['path']])
        completion['inspection_sha256'] = execution['inspection']['sha256']
        _replace(state, execution['completion'], completion)
        _replace(state, verified['native_execution'], execution)
        with pytest.raises(recovery.StorageRecoveryError, match='replay_v2_execution_invalid'):
            _protocol_call(state, verified=verified)


def test_v2_complete_native_reuse_joins_the_actual_http_evidence_map(replay):
    state = _memory_state(replay); protocol = replay['replay_protocol']; wrapper = replay['wrapper']
    load = lambda ref: json.loads(state['bodies'][ref['path']])
    recipe = load(wrapper['archives']['current']['recovery_recipe'])
    evidence = copy.deepcopy(replay['replay_resource']); evidence['mode'] = 'composed-native'
    role = evidence['prepare_apply_execution']; qualification = load(role['completion'])
    role['completion'] = qualification['native_completion']
    result = load(role['result']); observed = result['artifacts']['prepared_migration_plan']
    result = {'state': 'passed', 'counts': {**observed['counts'], 'original_files': 3, 'reports': 24, 'workspaces': 52},
        'hashes': {'original_manifest': '4' * 64}, 'artifacts': {'prepared_migration_plan': observed,
            'full_file_manifests': {'path': '/retired/observed-only.json'}, 'snapshot_spills': {}}}
    config = load(role['config']); config['policy'].update(program_sha256=protocol['plan']['program']['sha256'],
        expected_report_count=24, expected_workspace_count=52)
    _replace(state, role['config'], config); _replace(state, role['result'], result)
    completion = load(role['completion']); completion.update(program_sha256=protocol['plan']['program']['sha256'],
        config_sha256=role['config']['sha256'], counts=result['counts'], hashes=result['hashes'])
    _replace(state, role['completion'], completion)
    kernel = load(role['kernel']); kernel['result_sha256'] = role['result']['sha256']; _replace(state, role['kernel'], kernel)
    admission_ref = {'path': role['config']['path'] + '.admission', 'sha256': '0' * 64}
    admission = {'native_evidence': {'rehearsal': role['completion'], 'rehearsal_helper_stdout': role['result'],
        'rehearsal_config': role['config'], 'rehearsal_phase': role['phase']},
        'http_coverage': {'evidence': {'rehearsal_helper_stdout': role['result'], 'http-before': {'sha256': 'a' * 64}}}}
    _replace(state, admission_ref, admission)
    native_plan = load(wrapper['plan']); native_plan['proofs']['rehearsal'] = admission_ref
    verified = copy.deepcopy(replay['replay_verification']); _replace(state, verified['resource_evidence'], evidence)
    def check():
        files = recovery._AcceptedFiles(state['read'], state['stat'])
        source = load(wrapper['recovery_files']['final_proof'])
        stats = recovery._v2_metadata(protocol, source, wrapper['archives']['current'], files)
        recovery._v2_resources(verified['resource_evidence'], protocol, verified, native_plan, replay['original_preparation'],
            stats, source, recipe, files)
    check()
    admission['http_coverage']['evidence']['rehearsal_helper_stdout'] = {'path': '/unrelated/result.json', 'sha256': 'f' * 64}
    _replace(state, admission_ref, admission)
    with pytest.raises(recovery.StorageRecoveryError, match='replay_v2_native_reuse_unanchored'):
        check()


@pytest.mark.skipif(os.name != 'posix' or not hasattr(os, 'geteuid') or os.geteuid() != 0,
    reason='Default root reader verifies application-owned preparation metadata')
def test_v2_default_collector_accepts_authenticated_uid1000_original_preparation(replay, monkeypatch):
    original = Path(replay['replay_protocol']['plan']['original_preparation_receipt']['path'])
    os.chown(original, 1000, 1000)
    app = copy.deepcopy(replay['post_pair']['app'])
    app['_storage_recovery_sidecar'] = recovery._sidecar_snapshot(replay['post_pair']['copilot'])
    monkeypatch.setattr(recovery, '_verify_image_set', lambda rows: [
        {'image': image, 'source_sha': source, 'exists': True, 'provenance_verified': True}
        for image, source in sorted(rows.items())])
    manifest = recovery.collect_recovery_manifest(replay['ledger'], replay['backups'], app_inspection=app)
    recovery.validate_accepted_recovery_proofs(manifest)
    assert manifest['operation_kind'] == 'recovery-adoption'
