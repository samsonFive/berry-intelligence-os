"""Fictional, fully sealed v2 evidence; never a native image/resource PASS."""
import copy
import hashlib
import json
from pathlib import Path

from storage_adoption_fixtures import adoption_environment
from storage_recovery_fixtures import encoded


def replay_v2_environment(environment):
    from app.services import storage_recovery as recovery
    env = adoption_environment(environment, logos=True, prepared=True)
    wrapper = copy.deepcopy(env['wrapper']); recovery_files = wrapper['recovery_files']
    stage = Path(wrapper['current']['stage']) / 'operator-private' / 'replay-v2'
    stage.mkdir(mode=0o700)
    digest = lambda body: hashlib.sha256(body).hexdigest()

    def write(name, value):
        path = stage / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value if isinstance(value, bytes) else encoded(value)); path.chmod(0o600)
        return {'path': str(path), 'sha256': digest(path.read_bytes())}

    def load(ref): return json.loads(Path(ref['path']).read_bytes())

    native_plan = load(wrapper['plan']); source = load(recovery_files['final_proof'])
    archive = wrapper['archives']['current']; recipe = load(archive['recovery_recipe'])
    original_ref = {'path': str(Path(recovery_files['raw_plan']['path']).with_name('PLAN-preparation.private.json'))}
    original_ref['sha256'] = digest(Path(original_ref['path']).read_bytes())
    original = load(original_ref)
    program = write('replay-program.py', b'# fictional v2 replay executable\n')
    metadata_program = write('metadata.py', b'# fictional bounded two-phase metadata program\n')
    protocol = {'schema': 'berry.migration-replay-protocol.v2', 'image': recipe['candidate_image'], 'source_sha': recipe['source_sha'],
        'restore': {'module': 'app.services.runtime_backup', 'function': 'restore_backup', 'require_empty': True},
        'source_metadata': {'from': 'source-receipt.source_manifest+timestamp-sidecar.source_mtime_ns',
            'source_receipt': recovery_files['source_receipt'], 'timestamp_sidecar': recovery_files['timestamp_dependencies']['sidecar'],
            'program': metadata_program, 'verify_archive_member_coverage': True, 'verify_size_sha256_mode_before_metadata': True,
            'restore_mtime_ns': True, 'reject_unknown_roots_and_unsafe_paths': True, 'release_buffers_before_plan': True},
        'plan': {'module': 'accepted-preservation-helper', 'function': 'prepare_migration_plan',
            'program': native_plan['modules']['preservation'], 'original_preparation_receipt': original_ref,
            'fresh_runtime_paths': True, 'new_empty_backup_base': True, 'encoding': 'ascii-json', 'exclusive_prepared_plan': True},
        'apply': {'module': 'app.services.information_migration', 'function': 'apply_migration', 'quiesced': True,
            'resume_id': 'this-prepared-plan.migration_id', 'no_replan': True, 'no_aggregate_plan_rewrite': True},
        'verification': ['current-store', 'winner-and-variants', 'analyst-decisions', 'all-protected-runtime-state'],
        'original_migration_id_is_provenance_only': True, 'program': program}
    protocol_ref = write('protocol.json', protocol)
    input_ref = write('input.json', {'schema': 'berry.migration-replay-input.v2', 'candidate_image': recipe['candidate_image'],
        'source_sha': recipe['source_sha'], 'replay_protocol': protocol_ref, 'operator_modules': recipe['operator_modules'], 'raw_plan': recipe['raw_plan']})
    def execution_config():
        return {'schema': 'berry.migration-replay-functional-config.v2', 'source_mode': 'app', 'image': protocol['image'],
            'source_sha': protocol['source_sha'], 'program': program, 'protocol': protocol_ref, 'recipe_input': input_ref,
            'preparer': protocol['plan']['program'], 'metadata': metadata_program, 'output_dir': '/proofs', 'work_dir': '/work'}
    def invocation(mode, output_host, work_host, *, owned=False):
        config = execution_config()
        arguments = ['-I', '-B', program['path'], mode, '--protocol', protocol_ref['path'], '--protocol-sha256', protocol_ref['sha256'],
            '--recipe', input_ref['path'], '--recipe-sha256', input_ref['sha256'], '--output-dir', '/proofs', '--work-dir', '/work']
        if owned:
            arguments += ['--runtime-dir', '/app/runtime', '--backup-base', '/work/qualification/migration-backups',
                '--scratch-dir', '/work/qualification/scratch']
        refs = [program, protocol_ref, input_ref, protocol['plan']['program'], metadata_program, original_ref,
                recovery_files['source_receipt'], recovery_files['timestamp_dependencies']['sidecar']]
        mounts = [{'Type': 'bind', 'Source': ref['path'], 'Destination': ref['path'], 'RW': False} for ref in refs]
        mounts += [{'Type': 'bind', 'Source': str(output_host), 'Destination': '/proofs', 'RW': True},
                   {'Type': 'bind', 'Source': str(work_host), 'Destination': '/work', 'RW': True}]
        if owned: mounts.append({'Type': 'bind', 'Source': workspace, 'Destination': '/app/runtime', 'RW': True})
        return config, {'Config': {'Entrypoint': None, 'Cmd': ['python3', *arguments]}, 'Path': 'python3', 'Args': arguments, 'Mounts': mounts}
    files = recovery._AcceptedFiles(env['accepted_read_file'], env['accepted_stat_file'])
    stats = recovery._v2_metadata(protocol, source, archive, files)
    workspace = '/tmp/fictional-owned-qualification'
    metadata_result = {'state': 'passed', 'counts': {'files': stats['files'], 'bytes': stats['bytes']},
        'hashes': {'inventory': stats['source_inventory_sha256'], 'timestamp': stats['timestamp_digest']},
        'artifacts': {'metadata_allocation': {'schema': 'berry.migration-replay-metadata-allocation.v2', 'state': 'passed',
            'source_receipt': protocol['source_metadata']['source_receipt'], 'timestamp_sidecar': protocol['source_metadata']['timestamp_sidecar'],
            **stats, 'validated_entries': stats['files'], 'maps_released_before_plan': True, 'stream_buffer_bytes': 2 * 1024**2}}}
    # Same native workload/ID is legitimate at a NEW, initially empty base.
    observed = copy.deepcopy(original)
    observed['path'] = '/work/qualification/migration-backups/' + observed['migration_id'] + '/PLAN.private.json'
    apply = {'resume_id': observed['migration_id'], 'migration_id': observed['migration_id'], 'plan_calls': 1,
        'aggregate_plan_writes': 0, 'before_plan_sha256': observed['sha256'], 'after_plan_sha256': observed['sha256'],
        'before_plan_bytes': observed['bytes'], 'after_plan_bytes': observed['bytes']}
    result = {'schema': 'berry.migration-replay-prepare-apply.v2', 'state': 'passed', 'image': protocol['image'],
        'source_sha': protocol['source_sha'], 'program_sha256': program['sha256'],
        'preparer_sha256': protocol['plan']['program']['sha256'], 'counts': observed['counts'],
        'hashes': {'source_inventory_sha256': stats['source_inventory_sha256'], 'timestamp_digest': stats['timestamp_digest'],
            'before_plan_sha256': observed['sha256'], 'after_plan_sha256': observed['sha256']},
        'artifacts': {'prepared_migration_plan': observed}, 'apply': apply}

    def execution(label, identifier, program_sha, result):
        output = stage / (label + '-output')
        command_config, observed_command = invocation('--metadata-allocation' if label == 'metadata' else '--prepare-apply-only',
            output, '/tmp/fictional-' + label + '-work', owned=label != 'metadata')
        config = write(label + '-config.json', {'data_dir': '/app/runtime/data', 'inbox_dir': '/app/runtime/inbox',
            'backup_dir': '/work/qualification', 'policy': {'source_sha': protocol['source_sha'],
                'program_sha256': program_sha, 'preparer_sha256': protocol['plan']['program']['sha256'],
                'metadata_program_sha256': metadata_program['sha256'], 'replay_execution': command_config}})
        phase = write(label + '-phase.json', {'ephemeral': {'name': 'fictional-' + label, 'id': identifier,
            'image': protocol['image'], 'stop_on_halt': True}})
        result_ref = write(label + '-output/result.json', result)
        initial = {'Id': identifier, 'Image': protocol['image'], 'HostConfig': {'Memory': 448 * 1024**2, 'MemorySwap': 448 * 1024**2},
            'State': {'Running': True, 'Pid': 1234, 'StartedAt': '2026-11-17T01:00:00Z'}, **observed_command}
        initial_ref = write(label + '-initial-inspection.json', initial)
        final = copy.deepcopy(initial); final['State'].update(Running=False, Pid=0, Status='exited', ExitCode=0,
            OOMKilled=False, FinishedAt='2026-11-17T01:01:00Z')
        inspection = write(label + '-inspection.json', final)
        kernel = write(label + '-kernel.json', {'schema': 'berry.migration-replay-kernel.v2', 'state': 'verified',
            'container_id': identifier, 'initial_inspection': initial_ref, 'observer': write(label + '-observer.py', b'# fictional observer\n'),
            'init_pid': 1234, 'proc_cgroup_path': '/system.slice/docker-' + identifier + '.scope',
            'cgroup_path': '/sys/fs/cgroup/system.slice/docker-' + identifier + '.scope',
            'memory_max_bytes': 448 * 1024**2, 'swap_max_bytes': 0, 'memory_peak_bytes': 200 * 1024**2,
            'events_before': {'oom': 0, 'oom_kill': 0}, 'events_after': {'oom': 0, 'oom_kill': 0}, 'populated_after': False,
            'result_sha256': result_ref['sha256']})
        completion = write(label + '-native-completion.json', {'state': 'passed', 'container_id': identifier,
            'image': protocol['image'], 'program_sha256': program_sha, 'config_sha256': config['sha256'], 'phase_sha256': phase['sha256'],
            'memory_cap_mib': 448, 'helper_exit': 0, 'watcher_exit': 0, 'oom_killed': False, 'counts': result['counts'],
            'hashes': result['hashes'], 'result_sha256': result_ref['sha256']})
        return {'completion': completion, 'inspection': inspection, 'kernel': kernel, 'config': config, 'phase': phase, 'result': result_ref}

    metadata_execution = execution('metadata', '6' * 64, program['sha256'], metadata_result)
    preparation_execution = execution('preparation', '7' * 64, program['sha256'], result)
    qualification = {'schema': 'berry.migration-replay-qualification-complete.v2', 'state': 'passed', 'nonce': '9' * 32,
        'image': protocol['image'], 'source_sha': protocol['source_sha'], 'protocol_sha256': protocol_ref['sha256'],
        'program_sha256': program['sha256'], 'original_preparation_receipt': original_ref,
        'source_receipt': protocol['source_metadata']['source_receipt'], 'timestamp_sidecar': protocol['source_metadata']['timestamp_sidecar'],
        'native_completion': preparation_execution['completion'],
        **{key: value for key, value in preparation_execution.items() if key != 'completion'}, 'workspace_root': workspace,
        'backup_base_before': {'path': '/tmp/fictional-preparation-work/qualification/migration-backups',
            'device': 1, 'inode': 2, 'entries': [], 'observed_before_prepare': True}}
    preparation_execution['completion'] = write('qualification-completion.json', qualification)
    resource = {'schema': 'berry.migration-replay-resource.v2', 'mode': 'owned-qualification',
        'metadata_execution': metadata_execution, 'prepare_apply_execution': preparation_execution}
    resource_ref = write('resource.json', resource)
    roots = {'runtime': '/tmp/fictional-functional/runtime', 'data': '/tmp/fictional-functional/runtime/data',
        'inbox': '/tmp/fictional-functional/runtime/inbox', 'backup_base': '/tmp/fictional-functional/backups',
        'proof_dir': '/proofs', 'fresh_runtime': True, 'new_empty_backup_base': True}
    fresh_plan = load(recovery_files['raw_plan'])
    fresh_plan.update(data_dir=roots['data'], inbox_dir=roots['inbox'])
    fresh_fp = digest(json.dumps({'data': roots['data'], 'inbox': roots['inbox'], 'sources': fresh_plan['sources']}, sort_keys=True,
        separators=(',', ':')).encode())
    fresh = copy.deepcopy(original)
    fresh.update(source_fingerprint=fresh_fp, migration_id='information-' + fresh_fp[:20])
    fresh_plan.update(migration_id=fresh['migration_id'], source_fingerprint=fresh_fp)
    raw = (json.dumps(fresh_plan, ensure_ascii=True, sort_keys=True, indent=2) + '\n').encode('ascii')
    fresh.update(path=roots['backup_base'] + '/' + fresh['migration_id'] + '/PLAN.private.json', sha256=digest(raw),
        canonical_sha256=digest(recovery._canonical(fresh_plan)), bytes=len(raw))
    fresh_ref = write('functional-output/fresh-preparation.json', fresh)
    native = {'schema': 'berry.migration-replay-native.v2', 'state': 'passed', 'fixture_only': True,
        'execution_context': 'app-modules-fixture', 'image': protocol['image'], 'source_sha': protocol['source_sha'],
        'protocol_sha256': protocol_ref['sha256'], 'program_sha256': program['sha256'],
        'preparer_sha256': protocol['plan']['program']['sha256'],
        'module_sha256': {'runtime_backup': 'a' * 64, 'information_migration': 'b' * 64,
            'information_storage': 'c' * 64, 'metadata': metadata_program['sha256']}, 'roots': roots,
        'source_metadata': {'archive_sha256': 'a' * 64, 'source_receipt_sha256': 'b' * 64,
            'timestamp_sidecar_sha256': 'c' * 64, 'inventory_sha256': 'd' * 64, 'timestamp_sha256': 'e' * 64,
            'files': 2, 'verified_before_mtime': True, 'released_before_plan': True},
        'prepared_plan': {key: fresh[key] for key in ('path', 'sha256', 'canonical_sha256', 'source_fingerprint',
            'migration_id', 'bytes', 'counts', 'largest_source_codepoint')},
        'apply': {**apply, 'resume_id': fresh['migration_id'], 'migration_id': fresh['migration_id'],
            'before_plan_sha256': fresh['sha256'], 'after_plan_sha256': fresh['sha256'],
            'before_plan_bytes': fresh['bytes'], 'after_plan_bytes': fresh['bytes']},
        'checks': {key: True for key in recovery.REPLAY_V2_CHECKS}}
    native['prepared_plan'].update(receipt_path=roots['proof_dir'] + '/fresh-preparation.json', receipt_sha256=fresh_ref['sha256'])
    native_ref = write('functional-output/native-functional.json', native)
    functional_config, observed_command = invocation('--fixture-only', stage / 'functional-output', '/tmp/fictional-functional-work')
    functional_config_ref = write('functional-config.json', functional_config)
    inspection_ref = write('functional-inspection.json', {'Id': '5' * 64, 'Image': protocol['image'],
        'HostConfig': {}, 'State': {'Running': False, 'Status': 'exited', 'ExitCode': 0, 'OOMKilled': False}, **observed_command})
    completion_ref = write('functional-completion.json', {'schema': 'berry.migration-replay-functional-complete.v2',
        'state': 'passed', 'container_id': '5' * 64, 'image': protocol['image'], 'source_sha': protocol['source_sha'],
        'program_sha256': program['sha256'], 'config_sha256': functional_config_ref['sha256'], 'result_sha256': native_ref['sha256'],
        'inspection_sha256': inspection_ref['sha256'], 'helper_exit': 0, 'oom_killed': False})
    functional_ref = write('functional-execution.json', {'schema': 'berry.migration-replay-functional-execution.v2',
        'state': 'passed', 'completion': completion_ref, 'inspection': inspection_ref, 'config': functional_config_ref, 'result': native_ref})
    verified = {'schema': 'berry.migration-replay-verification.v2', 'state': 'passed', 'image': protocol['image'],
        'source_sha': protocol['source_sha'], 'protocol_sha256': protocol_ref['sha256'], 'program_sha256': program['sha256'],
        'checks': native['checks'], 'test_program': program, 'native_receipt': native_ref,
        'native_execution': functional_ref, 'preparation_receipt': fresh_ref, 'resource_evidence': resource_ref}
    verified_ref = write('verification.json', verified)
    recipe.update(replay_protocol=protocol_ref, protocol_verification=verified_ref)
    archive['recovery_recipe'] = write('recipe.json', recipe)
    pointer = env['proof_pointer']; Path(pointer['path']).write_bytes(encoded(wrapper))
    pointer['sha256'] = digest(encoded(wrapper))
    ledger = load({'path': str(env['ledger'])}); ledger['recovery_proof'] = pointer
    env['ledger'].write_bytes(encoded(ledger))
    receipt_path = Path(ledger['receipt']); receipt = load({'path': str(receipt_path)})
    receipt['new_ledger_sha256'] = digest(env['ledger'].read_bytes()); receipt_path.write_bytes(encoded(receipt))
    context = recovery._load_accepted_closure(env['ledger'], env['backups'],
        older_path=Path(env['value']['previous_before_ledger_path']), read_file=env['accepted_read_file'], stat_file=env['accepted_stat_file'])
    value = copy.deepcopy(env['value'])
    value.update(ledger_sha256=digest(env['ledger'].read_bytes()), accepted_recovery_proofs=context['accepted_recovery_proofs'],
        accepted_promotion_receipts=context['accepted'], accepted_native_origin=context['native_origin'])
    value['accepted_content_pins'] = sorted(context['files'].pins.values(), key=lambda pin: pin['path'])
    value['protected_paths'].extend({'path': pin['path'], 'kind': 'file'} for pin in value['accepted_content_pins'])
    for row in value['recovery_sets']: row['backup'].update(wrapper['archives'][row['role']])
    env.update(value=value, wrapper=wrapper, replay_protocol=protocol, replay_verification=verified, replay_resource=resource,
        original_preparation=original, fresh_preparation=fresh, native_replay=native)
    env['protection'].write_bytes(encoded(value))
    return env
