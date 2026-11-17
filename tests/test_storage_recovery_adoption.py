"""Explicit metadata adoption of the sanitized frozen native590 contract."""
import copy
import hashlib
import json
import os
from pathlib import Path

import pytest

from test_storage_retention import environment as accepted_environment
from test_storage_recovery import _memory_state, _reseal_memory_wrapper
from storage_adoption_fixtures import adoption_environment
from storage_recovery_fixtures import encoded
from app.services import storage_recovery as recovery


@pytest.fixture
def adopted(accepted_environment):
    return adoption_environment(accepted_environment)


def test_native590_adoption_preserves_bytes_runtime_and_logical_previous(adopted):
    state = _memory_state(adopted)
    manifest = state['manifest']
    recovery.validate_accepted_recovery_proofs(manifest, read_file=state['read'], stat_file=state['stat'])
    context = recovery.accepted_native_origin(manifest, read_file=state['read'], stat_file=state['stat'])
    assert context['native_origin'] == manifest['accepted_native_origin']
    assert context['origin_proof'] == adopted['wrapper']['recovery_files']['final_proof']
    origin_raw = state['bodies'][adopted['origin_ledger']['path']]
    assert origin_raw == adopted['origin_original_bytes']
    original, current = json.loads(origin_raw), json.loads(state['bodies'][manifest['ledger_path']])
    changed = {key for key in current if current.get(key) != original.get(key)}
    assert changed == {'backup', 'receipt', 'recovery_proof'}
    assert manifest['accepted_promotion_receipts'][0]['old_ledger_sha256'] == hashlib.sha256(origin_raw).hexdigest()
    assert manifest['previous_ledger_sha256'] != hashlib.sha256(origin_raw).hexdigest()
    assert manifest['operation_kind'] == 'recovery-adoption' and manifest['accepted_caddy_id'] is None
    assert len(manifest['live_binding']) == 8 and manifest['live_binding'] == adopted['value']['live_binding']
    assert 'accepted-private-value' not in json.dumps(manifest)
    for reference in (adopted['wrapper']['plan'], adopted['wrapper']['recovery_files']['final_proof']):
        assert 'operation_kind' not in json.loads(state['bodies'][reference['path']])


@pytest.mark.skipif(os.name != 'posix' or not hasattr(os, 'geteuid') or os.geteuid() != 0,
    reason='Actual default recovery reader requires root-private Linux evidence')
def test_adoption_default_collector_verifies_two_local_archives_and_preserves_ids(adopted, monkeypatch):
    _assert_default_collector(adopted, monkeypatch)


@pytest.mark.skipif(os.name != 'posix' or not hasattr(os, 'geteuid') or os.geteuid() != 0,
    reason='Actual default recovery reader requires root-private Linux evidence')
def test_logo_adoption_default_collector_verifies_the_complete_native_extension(accepted_environment, monkeypatch):
    _assert_default_collector(adoption_environment(accepted_environment, logos=True), monkeypatch)


def _assert_default_collector(adopted, monkeypatch):
    app = copy.deepcopy(adopted['post_pair']['app'])
    app['_storage_recovery_sidecar'] = recovery._sidecar_snapshot(adopted['post_pair']['copilot'])
    monkeypatch.setattr(recovery, '_verify_image_set', lambda rows: [
        {'image': image, 'source_sha': source, 'exists': True, 'provenance_verified': True}
        for image, source in sorted(rows.items())])
    manifest = recovery.collect_recovery_manifest(adopted['ledger'], adopted['backups'], app_inspection=app)
    recovery.validate_accepted_recovery_proofs(manifest)
    assert manifest['operation_kind'] == 'recovery-adoption'
    assert manifest['live_binding']['app_id'] == adopted['post_pair']['app']['Id']
    assert manifest['live_binding']['copilot']['container_id'] == adopted['post_pair']['copilot']['Id']
    assert {row['role'] for row in manifest['recovery_sets']} == {'current', 'previous'}
    assert all(row['backup']['verified'] for row in manifest['recovery_sets'])


def test_historical_hold_and_native_missing_kind_are_never_implicitly_ready(adopted):
    state = _memory_state(adopted)
    original = json.loads(state['bodies'][adopted['origin_ledger']['path']])
    state['bodies'][state['manifest']['ledger_path']] = encoded(original)
    with pytest.raises(recovery.StorageRecoveryError, match='accepted_recovery_proof_missing'):
        recovery.validate_accepted_recovery_proofs(state['manifest'], read_file=state['read'], stat_file=state['stat'])


def test_adoption_profile_refuses_manufactured_native_operation_kind(accepted_environment):
    with pytest.raises(recovery.StorageRecoveryError, match='accepted_adoption_native_kind_manufactured'):
        adoption_environment(accepted_environment, native_kind='unified-migration')


def test_adoption_cannot_change_runtime_or_lie_about_receipt_lineage(adopted):
    state = _memory_state(adopted)
    baseline = copy.deepcopy(state['bodies'])
    path = state['manifest']['ledger_path']
    for field, value, reason in [
        ('compose_override', '/fictional/unaccepted.json', 'accepted_adoption_runtime_changed'),
        ('source_sha', '0' * 40, 'accepted_adoption_runtime_changed'),
        ('future_extension', {'enabled': 1, 'revision': 1}, 'accepted_adoption_runtime_changed'),
        ('future_extension', {'enabled': True, 'revision': 1.0}, 'accepted_adoption_runtime_changed'),
    ]:
        state['bodies'].clear(); state['bodies'].update(baseline)
        document = json.loads(state['bodies'][path]); document[field] = value
        state['bodies'][path] = encoded(document)
        with pytest.raises(recovery.StorageRecoveryError, match=reason):
            recovery.validate_accepted_recovery_proofs(state['manifest'], read_file=state['read'], stat_file=state['stat'])
    state['bodies'].clear(); state['bodies'].update(baseline)
    document = json.loads(state['bodies'][path]); receipt_path = document['receipt']
    receipt = json.loads(state['bodies'][receipt_path]); receipt['old_ledger_sha256'] = state['manifest']['previous_ledger_sha256']
    state['bodies'][receipt_path] = encoded(receipt)
    with pytest.raises(recovery.StorageRecoveryError, match='accepted_previous_ledger_mismatch'):
        recovery.validate_accepted_recovery_proofs(state['manifest'], read_file=state['read'], stat_file=state['stat'])


def test_resealed_adoption_descriptor_still_requires_explicit_profile_and_exact_local_copy(adopted):
    state = _memory_state(adopted)
    baseline = copy.deepcopy(state['bodies'])
    for change, reason in [('profile', 'accepted_adoption_profile_unsupported'),
                          ('sha', 'accepted_adoption_archive_mapping_invalid'),
                          ('source_size_type', 'accepted_adoption_archive_mapping_invalid')]:
        state['bodies'].clear(); state['bodies'].update(baseline)
        wrapper = copy.deepcopy(adopted['wrapper'])
        descriptor = copy.deepcopy(adopted['adoption_descriptor'])
        if change == 'profile': descriptor['profile'] = 'unknown-producer.v99'
        elif change == 'sha': descriptor['local_archive']['destination']['sha256'] = '0' * 64
        else:
            # Reaccept all outer bytes, while retaining the original source
            # object and integer destination/wrapper size. Python considers
            # these numerically equal; the accepted source format is exact.
            descriptor['local_archive']['source']['size'] = float(descriptor['local_archive']['source']['size'])
        state['bodies'][wrapper['adoption']['path']] = encoded(descriptor)
        wrapper['adoption']['sha256'] = hashlib.sha256(encoded(descriptor)).hexdigest()
        _reseal_memory_wrapper(state, wrapper)
        with pytest.raises(recovery.StorageRecoveryError, match=reason):
            recovery.validate_accepted_recovery_proofs(state['manifest'], read_file=state['read'], stat_file=state['stat'])


@pytest.fixture
def adopted_logos(accepted_environment):
    return adoption_environment(accepted_environment, logos=True)


def test_actual_logo_variant_preserves_all_extra_evidence_and_normalizes_only_known_files(adopted_logos):
    state = _memory_state(adopted_logos)
    recovery.validate_accepted_recovery_proofs(state['manifest'], read_file=state['read'], stat_file=state['stat'])
    inherited = recovery.accepted_native_origin(state['manifest'], read_file=state['read'], stat_file=state['stat'])
    wrapper = adopted_logos['wrapper']; historical = adopted_logos['origin_wrapper']
    assert len(wrapper['recovery_files']) == 14
    assert historical['protected_dirs'] != wrapper['protected_dirs']
    previous_archive = historical['previous_accepted']['backup']
    assert previous_archive in historical['protected_dirs'] and previous_archive not in wrapper['protected_dirs']
    assert all(Path(path).is_relative_to(adopted_logos['backups']) for path in inherited['protected_dirs'])
    assert str(Path(wrapper['recovery_files']['raw_plan']['path']).parent) in inherited['protected_dirs']
    for role, pin in wrapper['archives'].items():
        assert recovery._archive_proof(Path(pin['path']), pin, Path(adopted_logos['proof_pointer']['path']))['verified']
    # A later configuration needs the native metadata/raw store, never the
    # historical #584 archive body. Its removal cannot break a flat lookup.
    Path(previous_archive).unlink()
    assert recovery.accepted_native_origin(state['manifest'], read_file=state['read'], stat_file=state['stat']) == inherited


def test_logo_variant_refuses_wrong_types_choices_missing_extra_and_unknown_file_classification(adopted_logos):
    state = _memory_state(adopted_logos)
    wrapper = adopted_logos['wrapper']; evidence = wrapper['recovery_files']; baseline = copy.deepcopy(state['bodies'])
    files = recovery._AcceptedFiles(state['read'], state['stat'])
    constants = recovery._logo_constants(evidence['logo_supplement']['helper'], files)
    audit_ref = copy.deepcopy(evidence['logo_supplement']['audit'])
    original_audit = json.loads(state['bodies'][audit_ref['path']])
    for field, value in [('forced_selections', True), ('new_grants_false', False), ('old_choices_after_sha256', '0' * 64)]:
        audit = copy.deepcopy(original_audit); audit[field] = value
        state['bodies'][audit_ref['path']] = encoded(audit)
        audit_ref['sha256'] = hashlib.sha256(encoded(audit)).hexdigest()
        with pytest.raises(recovery.StorageRecoveryError, match='accepted_logo_preservation_invalid'):
            recovery._logo_audit(audit_ref, evidence['logo_supplement']['preseed_index'], constants, None,
                recovery._AcceptedFiles(state['read'], state['stat']))
    state['bodies'].clear(); state['bodies'].update(baseline)
    changed = copy.deepcopy(wrapper); changed['recovery_files'].pop('logo_supplement')
    _reseal_memory_wrapper(state, changed)
    with pytest.raises(recovery.StorageRecoveryError, match='accepted_adoption_native_context_changed'):
        recovery.validate_accepted_recovery_proofs(state['manifest'], read_file=state['read'], stat_file=state['stat'])
    state['bodies'].clear(); state['bodies'].update(baseline)
    changed = copy.deepcopy(wrapper)
    changed['protected_dirs'].append(evidence['logo_supplement']['audit']['path'])
    _reseal_memory_wrapper(state, changed)
    with pytest.raises(recovery.StorageRecoveryError, match='accepted_adoption_protected_path_classification_invalid'):
        recovery.validate_accepted_recovery_proofs(state['manifest'], read_file=state['read'], stat_file=state['stat'])
    state['bodies'].clear(); state['bodies'].update(baseline)
    # A correctly hashed replacement sidecar still cannot pass a float as
    # nanosecond metadata. Exercise the semantic gate after its copy-SHA join.
    files = recovery._AcceptedFiles(state['read'], state['stat'])
    adoption = recovery._adoption_context(wrapper, files)
    dependencies = copy.deepcopy(evidence)
    sidecar_ref = dependencies['timestamp_dependencies']['sidecar']
    sidecar = json.loads(state['bodies'][sidecar_ref['path']])
    first = next(iter(sidecar['source_mtime_ns']))
    sidecar['source_mtime_ns'][first] = float(sidecar['source_mtime_ns'][first])
    state['bodies'][sidecar_ref['path']] = encoded(sidecar)
    sidecar_ref['sha256'] = hashlib.sha256(encoded(sidecar)).hexdigest()
    adoption['receiver']['sidecar']['sha256'] = sidecar_ref['sha256']
    with pytest.raises(recovery.StorageRecoveryError, match='accepted_timestamp_inventory_invalid'):
        recovery._adoption_logo_evidence(adoption, dependencies,
            json.loads(state['bodies'][wrapper['plan']['path']]),
            json.loads(state['bodies'][evidence['final_proof']['path']]),
            json.loads(state['bodies'][evidence['phase_receipt']['path']]),
            recovery._AcceptedFiles(state['read'], state['stat']))


def test_optional_candidate_image_inventory_is_durable_and_bound_to_image_admission(accepted_environment):
    env = adoption_environment(accepted_environment, logos=True, inventory=True)
    state = _memory_state(env)
    recovery.validate_accepted_recovery_proofs(state['manifest'], read_file=state['read'], stat_file=state['stat'])
    plan = json.loads(state['bodies'][env['wrapper']['plan']['path']])
    reference = plan['candidate_image_manifest']
    assert reference['path'] in {pin['path'] for pin in state['manifest']['accepted_content_pins']}
    original = state['bodies'][reference['path']]
    state['bodies'].pop(reference['path'])
    with pytest.raises(recovery.StorageRecoveryError, match='accepted_recovery_proof_invalid'):
        recovery.validate_accepted_recovery_proofs(state['manifest'], read_file=state['read'], stat_file=state['stat'])
    state['bodies'][reference['path']] = original + b'changed'
    with pytest.raises(recovery.StorageRecoveryError, match='accepted_file_digest_mismatch'):
        recovery.validate_accepted_recovery_proofs(state['manifest'], read_file=state['read'], stat_file=state['stat'])
    state['bodies'][reference['path']] = original
    for source, path in [('0' * 40, '/app/reports/one.json'), (plan['source_sha'], '/app/../outside.json')]:
        manifest = json.loads(original); manifest['source_sha'] = source
        manifest['exact_image_files'] = {path: '1' * 64}
        state['bodies'][reference['path']] = encoded(manifest)
        changed = copy.deepcopy(plan)
        changed['candidate_image_manifest']['sha256'] = hashlib.sha256(encoded(manifest)).hexdigest()
        admission_ref = changed['proofs']['image']
        admission = json.loads(state['bodies'][admission_ref['path']])
        admission['image_verification_sha256'] = changed['candidate_image_manifest']['sha256']
        state['bodies'][admission_ref['path']] = encoded(admission)
        admission_ref['sha256'] = hashlib.sha256(encoded(admission)).hexdigest()
        with pytest.raises(recovery.StorageRecoveryError):
            recovery._candidate_image_inventory(changed, recovery._AcceptedFiles(state['read'], state['stat']))
