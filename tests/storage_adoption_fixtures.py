"""Sanitized frozen-590 native shapes: missing kinds and offhost HOLD are real.

All identities and bytes here are fictional. This fixture does not claim that
an actual migration, native image replay or production acceptance occurred.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from storage_recovery_fixtures import encoded


def adoption_environment(environment, *, native_kind=None, logos=False):
    import app.services.storage_recovery as recovery

    env = dict(environment)
    wrapper = copy.deepcopy(env['wrapper'])
    ledger_path = env['ledger']
    original = json.loads(ledger_path.read_bytes())
    private = Path(original['stage']) / 'operator-private' / 'adoption-fixture'
    private.mkdir(mode=0o700)
    digest = lambda body: hashlib.sha256(body).hexdigest()

    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value if isinstance(value, bytes) else encoded(value))
        path.chmod(0o600)
        return {'path': str(path), 'sha256': digest(path.read_bytes())}

    def replace(ref, value):
        ref.update(write(Path(ref['path']), value))

    # Actual frozen producer has NO kind in any of these native objects.
    plan = json.loads(Path(wrapper['plan']['path']).read_bytes())
    plan.pop('operation_kind')
    if native_kind is not None:
        plan['operation_kind'] = native_kind
    replace(wrapper['plan'], plan)
    recovery_files = wrapper['recovery_files']
    proof = json.loads(Path(recovery_files['final_proof']['path']).read_bytes())
    proof.pop('operation_kind')
    if native_kind is not None:
        proof['operation_kind'] = native_kind
    proof['rollback_recipe']['plan_sha256'] = wrapper['plan']['sha256']
    source = wrapper['archives']['current']
    offhost = 'C:\\fictional-receiver\\final-590.tar.gz'
    proof['offhost_archive'].update(path=offhost, state='verified', files=2, bytes=10, manifest_sha256='e' * 64)
    replace(recovery_files['final_proof'], proof)
    phase = json.loads(Path(recovery_files['phase_receipt']['path']).read_bytes())
    phase['bindings'].pop('operation_kind')
    if native_kind is not None:
        phase['bindings']['operation_kind'] = native_kind
    phase['final_verification']['recovery_proof_sha256'] = recovery_files['final_proof']['sha256']
    replace(recovery_files['phase_receipt'], phase)
    transform = json.loads(Path(source['transformation_proof']['path']).read_bytes())
    transform['final_proof'] = recovery_files['final_proof']
    replace(source['transformation_proof'], transform)
    recipe = json.loads(Path(source['recovery_recipe']['path']).read_bytes())
    recipe['transformation_proof'] = source['transformation_proof']
    replace(source['recovery_recipe'], recipe)

    extension = _logo_extension(env, wrapper, plan, proof, phase, write, replace, private) if logos else {}
    verification = write(private / 'timestamp-receiver-complete.private.json', {
        'state': 'completed', 'writers_resumed': True, 'nonce': wrapper['operation_nonce'],
        'source_sha': original['source_sha'], 'canonical_sha': plan['canonical_sha'], 'candidate_image': original['image'],
        'archive_sha256': source['sha256'], 'source_receipt_sha256': recovery_files['source_receipt']['sha256'],
        'candidate_binding_sha256': phase['final_verification']['candidate_binding_sha256'],
        'final_receipt_sha256': recovery_files['phase_receipt']['sha256'],
        'native_verified_receipt': {'path': 'C:\\fictional-receiver\\native.private.json', 'sha256': '1' * 64},
        'timestamp_proof': {'path': 'C:\\fictional-receiver\\timestamps.private.json', 'sha256': '2' * 64},
        'sidecar': {'path': 'C:\\fictional-receiver\\timestamps.json', 'sha256': '3' * 64},
        'files': 2, 'timestamp_digest': '4' * 64, **extension})
    if logos:
        recovery_files['timestamp_completion'] = verification
    previous_raw = Path(wrapper['previous_ledger']['path']).read_bytes()
    previous = json.loads(previous_raw)
    previous_receipt = write(Path(previous['receipt']), Path(previous['receipt']).read_bytes())
    historical = copy.deepcopy(wrapper)
    historical.update(schema='berry.unified-release-recovery.v1', retention_readiness='HOLD',
        previous_accepted={'ledger': wrapper['previous_ledger'], 'backup': previous['backup'],
            'original_backup_size': wrapper['archives']['previous']['size'], 'stage': previous['stage'],
            'original_archive_sha256': wrapper['archives']['previous']['sha256'],
            'historical_acceptance': {'decision': previous_receipt, 'activation': previous_receipt},
            'historical_proof_dependencies': [previous_receipt]},
        archives={'current': {'location': 'offhost-verified', 'path': offhost, 'sha256': source['sha256'],
            'size': source['size'], 'verification': verification}})
    if logos:
        wrapper['protected_dirs'] = sorted(wrapper['protected_dirs'])
        historical['protected_dirs'] = sorted(set(wrapper['protected_dirs']) | {previous['backup'], previous_receipt['path']})
    historical_ref = write(private / 'historical-HOLD.private.json', historical)
    origin_receipt_path = private / 'original-590-promotion.private.json'
    original.update(pr=590, backup=offhost, receipt=str(origin_receipt_path), future_extension={'enabled': True, 'revision': 1},
        recovery_proof={'schema': historical['schema'], **historical_ref},
        unified_information_release={'source_sha': original['source_sha'], 'canonical_sha': plan['canonical_sha'],
            'retention_readiness': 'HOLD', 'native_final_proof': recovery_files['final_proof'], 'proofs': {
                'plan': wrapper['plan'], 'snapshot_pre': wrapper['snapshots']['pre'], 'snapshot_post': wrapper['snapshots']['post'],
                'phase_receipt': recovery_files['phase_receipt'], 'final_proof': recovery_files['final_proof'],
                'archive_verification': verification}})
    origin_ledger = write(private / 'original-590-ledger.bytes', original)
    origin_receipt = write(origin_receipt_path, {'state': 'accepted', 'status': 'PASS',
        'source_sha': original['source_sha'], 'canonical_sha': plan['canonical_sha'], 'candidate_image': original['image'],
        'old_ledger_sha256': wrapper['previous_ledger']['sha256'], 'new_ledger_sha256': origin_ledger['sha256'],
        'recovery_proof': original['recovery_proof'], 'native_final_proof': recovery_files['final_proof'], 'retention_readiness': 'HOLD'})
    descriptor = {'schema': recovery.ADOPTION_SCHEMA, 'profile': recovery.ADOPTION_LOGO_PROFILE if logos else recovery.ADOPTION_PROFILE,
        'origin_ledger': origin_ledger, 'origin_receipt': origin_receipt, 'origin_wrapper': historical_ref,
        'local_archive': {'source': historical['archives']['current'],
            'destination': {key: source[key] for key in ('path', 'sha256', 'size')}}}
    descriptor_ref = write(private / 'adoption-descriptor.private.json', descriptor)
    wrapper.update(operation_kind='recovery-adoption', adoption=descriptor_ref)
    wrapper_ref = write(private / 'accepted-adoption.private.json', wrapper)
    receipt_path = private / 'adoption-promotion.private.json'
    adopted = {**original, 'backup': source['path'], 'receipt': str(receipt_path),
        'recovery_proof': {'schema': recovery.RECOVERY_PROOF_SCHEMA, **wrapper_ref}}
    write(ledger_path, adopted)
    write(receipt_path, {'status': 'PASS', 'candidate_image': original['image'],
        'old_ledger_sha256': origin_ledger['sha256'], 'new_ledger_sha256': digest(ledger_path.read_bytes())})
    value = copy.deepcopy(env['value'])
    context = recovery._load_accepted_closure(ledger_path, env['backups'],
        older_path=Path(value['previous_before_ledger_path']), read_file=env['accepted_read_file'], stat_file=env['accepted_stat_file'])
    value.update(ledger_sha256=digest(ledger_path.read_bytes()), operation_kind='recovery-adoption',
        accepted_native_origin=context['native_origin'], adoption_origin_ledger_sha256=context['adoption_origin_sha256'],
        previous_adoption_origin_ledger_sha256=context['previous_adoption_origin_sha256'],
        accepted_recovery_proofs=context['accepted_recovery_proofs'], accepted_promotion_receipts=context['accepted'])
    value['accepted_content_pins'] = sorted(context['files'].pins.values(), key=lambda pin: pin['path'])
    value['protected_paths'].extend({'path': pin['path'], 'kind': 'file'} for pin in value['accepted_content_pins'])
    for row in value['recovery_sets']:
        row['backup'].update(wrapper['archives'][row['role']])
    env['protection'].write_bytes(encoded(value))
    env.update(value=value, wrapper=wrapper, proof_pointer=adopted['recovery_proof'], adoption_descriptor=descriptor,
        origin_ledger=origin_ledger, origin_wrapper=historical, origin_receipt=origin_receipt,
        origin_original_bytes=encoded(original))
    return env


def _logo_extension(env, wrapper, plan, proof, phase, write, replace, private):
    """Actual extended-logo producer field shapes, with fictional artifact bytes."""
    from datetime import datetime, timezone
    from app.services import storage_recovery as recovery
    from app.services.runtime_backup import create_backup, restore_backup, verify_backup

    digest = lambda value: hashlib.sha256(recovery._canonical(value)).hexdigest()
    recovery_files = wrapper['recovery_files']; archive = wrapper['archives']['current']
    previous_rows = {'retained-analyst-row': {'primary': True, 'analyst_selected': True, 'policy': {'display_allowed': True}}}
    added = {'fictional-logo-' + str(i): {'primary': False, 'analyst_selected': False, 'policy': {
        'display_allowed': False, 'cache_allowed': False, 'export_allowed': False}, 'object_ref': None} for i in range(5)}
    expected = {key: digest(value) for key, value in added.items()}
    before_payload = {'version': 1, 'assets': previous_rows}
    after_payload = {'version': 1, 'assets': {**previous_rows, **added}}
    before_ref = write(private / 'brand-media-index-before.bin', before_payload)
    active_index = write(env['runtime'] / 'inbox' / 'brand_media' / 'index.json', after_payload)
    # The genuine final archive is post-seed, pre-migration LEGACY, rather than
    # the fixture's older pre-seed archive or today's active unified runtime.
    restored = env['tmp'] / 'logo-postseed-legacy'
    restore_backup(env['current'], restored)
    write(restored / 'inbox' / 'brand_media' / 'index.json', after_payload)
    current = create_backup(restored, env['backups'] / 'logo-final-recovery', now=datetime(2026, 11, 16, 11, tzinfo=timezone.utc))
    env['current'] = current
    archive.update(path=str(current), sha256=hashlib.sha256(current.read_bytes()).hexdigest(), size=current.stat().st_size)
    manifest = verify_backup(current)
    inventory = {row['path']: {key: row[key] for key in ('sha256', 'size', 'mode')} for row in manifest['files']}
    inventory_sha = digest(inventory); missing = sorted(expected)
    choices = ('primary', 'analyst_selected', 'rejected', 'match_status', 'policy', 'object_ref')
    module = write(private / 'logo_supplement.py', ('SOURCE = ' + repr(plan['source_sha']) + '\nSEED_SHA = ' + repr('d' * 64)
        + '\nINDEX = "inbox/brand_media/index.json"\nEXPECTED = ' + repr(expected) + '\nCHOICES = ' + repr(choices) + '\n').encode())
    preservation_module = write(private / 'preservation.py', b'# fictional unchanged preservation code\n')
    plan['modules'].update(logo_seed=module, preservation=preservation_module)
    preservation = write(private / 'original-preservation-completion.json', {'state': 'passed',
        'image': plan['candidate_image'], 'program_sha256': preservation_module['sha256']})
    plan['proofs']['rehearsal'] = write(private / 'rehearsal-admission.json', {
        'native_evidence': {'rehearsal': {'path': 'C:\\fictional-original\\completion.json', 'sha256': preservation['sha256']}}})
    # All six original core admissions remain distinct from this auxiliary copy.
    for name in ('image', 'ci', 'prior_archive', 'barrier'):
        plan['proofs'][name] = write(private / (name + '-admission.json'), {'fixture': name})
    audit = {'schema': 'berry.logo-supplement-47ad.v1', 'state': 'verified', 'source_sha': plan['source_sha'],
        'seed_sha256': 'd' * 64, 'index_path': 'inbox/brand_media/index.json', 'preseed_index': before_ref,
        'before_index': {'sha256': before_ref['sha256'], 'size': Path(before_ref['path']).stat().st_size, 'mode': 0o600},
        'after_index': copy.deepcopy(inventory['inbox/brand_media/index.json']),
        'missing_ids': missing, 'expected_normalized_hashes': expected,
        'before_raw_row_hashes': {key: digest(value) for key, value in previous_rows.items()},
        'after_raw_row_hashes': {key: digest(value) for key, value in after_payload['assets'].items()},
        'old_choices_before_sha256': digest({key: {field: row[field] for field in choices if field in row} for key, row in previous_rows.items()}),
        'old_choices_after_sha256': digest({key: {field: row[field] for field in choices if field in row} for key, row in previous_rows.items()}),
        'mutations': ['inbox/brand_media/index.json'], 'raw_rows_preserved': True, 'no_binary_downloads': True,
        'new_grants_false': True, 'forced_selections': False, 'replay_exact_noop': True,
        'before_inventory_sha256': 'b' * 64, 'after_inventory_sha256': inventory_sha}
    for name, apply, ids in [('dry', False, missing), ('apply', True, missing), ('replay', True, [])]:
        audit[name] = {'requested': 5, 'missing': len(ids), 'preserved': 5 - len(ids), 'created': len(ids) if apply else 0,
            'missing_ids': ids, 'added_ids': ids if apply else [], 'preserved_ids': sorted(set(expected) - set(ids)),
            'applied': apply, 'changed': bool(apply and ids)}
    audit_ref = write(private / 'logo-seed-audit.json', audit)
    copy_audit = copy.deepcopy(audit)
    copy_audit['preseed_index'] = {**before_ref, 'path': '/app/runtime/.release-proof/logo-copy/artifacts/index-before.private.json'}
    copy_audit_ref = write(private / 'copy-logo-audit.json', copy_audit)
    copy_before = write(private / 'copy-before.json', before_payload)
    before_map = {**inventory, 'inbox/brand_media/index.json': audit['before_index']}
    copy_proof = write(private / 'copy-logo-completion.json', {'schema': 'berry.copy-logo-supplement-complete.v1',
        'state': 'verified', 'source_sha': plan['source_sha'], 'candidate_image': plan['candidate_image'],
        'logo_helper_sha256': module['sha256'], 'seed_sha256': 'd' * 64, 'preservation_completion': preservation,
        'logo_audit': copy_audit_ref, 'preseed_index': copy_before,
        'current_before_seed_files': write(private / 'copy-before-map.json', before_map),
        'current_after_seed_files': write(private / 'copy-after-map.json', inventory),
        'native_worker': write(private / 'copy-worker.json', {'schema': 'berry.copy-logo-supplement-worker.v1', 'state': 'verified'}),
        'helper_exit': 0, 'watcher_exit': 0, 'oom_killed': False, 'isolated_copy_preserved': True,
        'phase_sha256': 'c' * 64, 'wrapper_sha256': 'f' * 64, 'memory_cap_mib': 256})
    refs = {'audit': audit_ref, 'preseed_index': before_ref, 'helper': module, 'copy_proof': copy_proof}
    plan['logo_supplement'] = {'copy_proof': copy_proof}
    replace(wrapper['plan'], plan)
    base_producer = write(private / 'live-base.py', b'# fictional accepted timestamp base producer\n')
    metadata = {'archive_sha256': archive['sha256'], 'archive_bytes': archive['size'], 'files': len(inventory), 'bytes': 10,
        'manifest_sha256': 'e' * 64, 'state': 'verified'}
    times = {name: 123456789 for name in inventory}; timestamp_sha = digest(times)
    sidecar_ref = write(private / 'timestamps-server-copy.json', {'version': 1, 'state': 'captured', 'source_timestamp_version': 1,
        'source_stable': True, 'source_mtime_stable': True, 'base_producer_sha256': base_producer['sha256'], 'archive': metadata,
        'source_inventory_sha256': inventory_sha, 'source_inventory_after_sha256': inventory_sha,
        'source_mtime_ns': times, 'source_mtime_ns_sha256': timestamp_sha, 'source_mtime_ns_after_sha256': timestamp_sha})
    remote = {**sidecar_ref, 'path': str(private / 'remote-timestamps.json'), 'digest': timestamp_sha, 'count': len(times)}
    source = {'source_manifest': inventory, 'source_inventory_sha256': inventory_sha, 'source_inventory_after_sha256': inventory_sha,
        'source_stable': True, 'archive': {**metadata, 'timestamps': remote}, 'nonce': plan['nonce'],
        'candidate_image': plan['candidate_image'], 'logo_supplement': refs}
    replace(recovery_files['source_receipt'], source)
    proof.update(logo_supplement=refs, source_receipt=recovery_files['source_receipt'],
        offhost_archive={'path': proof['offhost_archive']['path'], **source['archive']})
    proof['rollback_recipe'].update(plan_sha256=wrapper['plan']['sha256'], operator_modules=plan['modules'])
    replace(recovery_files['final_proof'], proof)
    phase['seed'] = {'logo_supplement': audit}
    phase['bindings'].update(archive_sha256=archive['sha256'], source_inventory_sha256=inventory_sha,
        source_receipt_sha256=recovery_files['source_receipt']['sha256'], proof_seals={key: ref['sha256'] for key, ref in plan['proofs'].items()})
    phase['final_verification']['recovery_proof_sha256'] = recovery_files['final_proof']['sha256']
    replace(recovery_files['phase_receipt'], phase)
    recovery_files['rollback_modules'] = list(plan['modules'].values())
    transform = json.loads(Path(archive['transformation_proof']['path']).read_bytes())
    transform.update(archive_sha256=archive['sha256'], source_inventory_sha256=inventory_sha,
        source_receipt=recovery_files['source_receipt'], final_proof=recovery_files['final_proof'])
    replace(archive['transformation_proof'], transform)
    recipe = json.loads(Path(archive['recovery_recipe']['path']).read_bytes())
    recipe.update(archive_sha256=archive['sha256'], operator_modules=plan['modules'], transformation_proof=archive['transformation_proof'])
    replace(archive['recovery_recipe'], recipe)
    local_sidecar = {**sidecar_ref, 'path': 'C:\\fictional-receiver\\sidecar.json'}
    timestamp_proof = write(private / 'timestamp-proof-server-copy.json', {'state': 'verified', 'source_timestamp_version': 1,
        'files': len(times), 'source_inventory_sha256': inventory_sha, 'timestamp_digest': timestamp_sha,
        'source_receipt_sha256': recovery_files['source_receipt']['sha256'], 'archive_sha256': archive['sha256'],
        'nonce': plan['nonce'], 'candidate_image': plan['candidate_image'], 'remote_sidecar': remote, 'local_sidecar': local_sidecar})
    native = write(private / 'native-receiver-server-copy.json', {'state': 'completed', 'writers_resumed': True,
        **{key: plan[key] for key in ('nonce', 'source_sha', 'canonical_sha', 'candidate_image')},
        'final_receipt_sha256': recovery_files['phase_receipt']['sha256'],
        'candidate_binding_sha256': phase['final_verification']['candidate_binding_sha256'],
        'source_inventory_sha256': inventory_sha, 'source_receipt_sha256': recovery_files['source_receipt']['sha256'],
        'proof_seals': phase['bindings']['proof_seals']})
    recovery_files.update(timestamp_dependencies={'native_verified_receipt': native, 'timestamp_proof': timestamp_proof, 'sidecar': sidecar_ref},
        live_base_dependency=base_producer, logo_supplement=refs)
    return {'native_verified_receipt': {**native, 'path': 'C:\\fictional-receiver\\native.json'},
        'timestamp_proof': {**timestamp_proof, 'path': 'C:\\fictional-receiver\\timestamps-verified.json'},
        'sidecar': local_sidecar, 'files': len(times), 'timestamp_digest': timestamp_sha,
        'logo_supplement': {'remote': refs, 'audit': {**audit_ref, 'path': 'C:\\fictional-receiver\\audit.json'},
            'preseed_index': {**before_ref, 'path': 'C:\\fictional-receiver\\before.json'}}}
