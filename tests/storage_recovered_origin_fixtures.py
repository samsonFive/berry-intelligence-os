"""Fictional recovered-origin evidence, never a native execution claim.

This is an optional hook in the shared adoption builder. It seals the real
producer's field shapes using disposable files and synthetic identities only.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def recovered_origin_environment(environment):
    from storage_adoption_fixtures import adoption_environment
    return adoption_environment(environment, logos=True, recovered=True)


def recovered_origin_evidence(env, wrapper, plan, proof, phase, write, replace, private):
    from app.services import storage_recovery as recovery

    def load(reference):
        return json.loads(Path(reference['path']).read_bytes())

    def digest(value):
        return hashlib.sha256(recovery._canonical(value)).hexdigest()

    def code(name):
        return write(private / name, ('# fictional ' + name + '\n').encode())

    def file_row(pin):
        return {**copy.deepcopy(pin), 'bytes': Path(pin['path']).stat().st_size}

    epoch = datetime(2026, 11, 10, tzinfo=timezone.utc).timestamp()
    recovered = load(wrapper['snapshots']['pre'])
    canonical_source = 'b' * 40
    for index, (role, row) in enumerate(recovered.items()):
        config, host = row['Config'], row['HostConfig']
        config['Image'] = row['Image']
        config['Hostname'] = (recovered['app']['Id'] if role == 'copilot' else row['Id'])[:12]
        config['Env'].append('BIOS_CANONICAL_SHA=' + canonical_source)
        host['Binds'] = [mount['Source'] + ':' + mount['Destination'] + ':' + ('rw' if mount['RW'] else 'ro')
                         for mount in row['Mounts']]
        host.setdefault('MemorySwap', host['Memory'])
        host.setdefault('ReadonlyRootfs', False)
        row['RestartCount'] = 0
        row['State'].update(Pid=4000 + index, StartedAt='2026-11-10T03:00:00Z', OOMKilled=False,
                            Paused=False, Dead=False, Restarting=False)
    original = copy.deepcopy(recovered)
    for index, (role, identifier) in enumerate([('app', '8' * 64), ('copilot', '7' * 64)]):
        row = original[role]
        row['Id'] = identifier
        row['Config']['Hostname'] = ('8' * 64 if role == 'copilot' else identifier)[:12]
        row['Config']['Env'].reverse()
        row['HostConfig']['Binds'].reverse()
        row['Mounts'].reverse()
        if role == 'copilot':
            row['HostConfig']['NetworkMode'] = 'container:' + '8' * 64
        row['State'].update(Pid=3000 + index, StartedAt='2026-11-10T02:00:00Z')
    raw_original = write(private / 'transition-original-full-pair.json', original)
    raw_recovered = write(private / 'transition-recovered-full-pair.json', recovered)
    # The later producer PRE is a separate capture, retaining the same full
    # configuration and lifecycle rather than reusing raw snapshot bytes.
    native_pre = copy.deepcopy(recovered)
    for row in native_pre.values():
        row['State']['Health']['Log'] = [{'fixture': 'later native PRE observation'}]
    replace(wrapper['snapshots']['pre'], native_pre)

    declared = wrapper['configuration']['pre']['app']
    compose = {'project': declared['project'], 'working_dir': declared['working_dir'],
               'files': [file_row(pin) for pin in declared['compose_files']]}
    environment_files = [file_row(pin) for pin in declared['environment_files']]
    workspace = {'page_count': 3, **{name: {'count': count, 'sha256': digest([name, count])}
        for name, count in [('objects', 3), ('history', 5), ('requests', 1), ('outbox', 0)]}}
    private_ids = ['fictional-report-one', 'fictional-report-two']
    private_files = {name: {'sha256': digest(name), 'bytes': len(name)} for name in
                     ['fictional-report-one/report.html', 'fictional-report-two/report.html']}
    packaged_files = {'fictional-packaged/report.json': {'sha256': digest('packaged fixture'), 'bytes': 17}}
    stable = {'version': 1, 'app_image': recovered['app']['Image'], 'app_user': recovered['app']['Config']['User'],
        'app_mounts': recovery._native_pair_binding(recovered)['app']['mounts'],
        'compose': {role: copy.deepcopy(compose) for role in ('app', 'copilot')},
        'protected_environment_files': environment_files,
        'entrypoint_sha256': digest('fictional entrypoint'), 'requirements_web_sha256': digest('fictional requirements'),
        'runtime_bindings': {name: str(env['runtime'] / name) for name in ('data', 'inbox')},
        'private_report_ids': private_ids, 'private_report_files': private_files,
        'private_report_library_sha256': digest('fictional private library'),
        'packaged_report_files': packaged_files, 'packaged_report_catalog': {'reports': ['fictional-packaged']},
        'packaged_report_library_sha256': digest('fictional packaged library'), 'workspaces': workspace,
        'provisional_live_read': True}

    def baseline(pair, collected):
        return {**copy.deepcopy(stable), 'collected_at_unix': collected,
                'production_binding': recovery._recovered_pair_binding(pair),
                'running_containers': [pair[role]['Id'] for role in ('app', 'copilot')]}

    prior_baseline = baseline(original, epoch + 7202)
    rehearsal_baseline = copy.deepcopy(prior_baseline)
    rehearsal_baseline['collected_at_unix'] = epoch + 3602
    for row in rehearsal_baseline['production_binding'].values():
        row['state']['started_at'] = '2026-11-10T01:00:00Z'
    recovered_baseline = baseline(recovered, epoch + 10803)
    original_ref = write(private / 'transition-original-baseline.json', rehearsal_baseline)
    original_pre_ref = write(private / 'transition-original-pre-baseline.json', prior_baseline)
    recovery_files = wrapper['recovery_files']
    replace(recovery_files['baseline'], recovered_baseline)
    recovered_ref = copy.deepcopy(recovery_files['baseline'])
    validator, binding_program = (code(name) for name in ('transition-validator.py', 'transition-binding.py'))
    historical_ledger = write(private / 'transition-immutable-previous-ledger.bytes',
                              Path(wrapper['previous_ledger']['path']).read_bytes())
    constants = {'VALIDATOR_SHA': validator['sha256'], 'BINDING_SHA': binding_program['sha256'],
        'ORIGINAL_SHA': original_ref['sha256'], 'PRE_BASELINE_SHA': original_pre_ref['sha256'],
        'PRE_SHA': raw_original['sha256'], 'POST_SHA': raw_recovered['sha256'],
        'RECOVERED_SHA': recovered_ref['sha256'], 'LEDGER_SHA': historical_ledger['sha256']}
    producer = write(private / 'transition-producer.py', ('# fictional sealed producer; never executed\n' +
        ''.join(name + ' = ' + repr(value) + '\n' for name, value in constants.items())).encode())
    journal = write(private / 'historical-rollback-journal.json', {
        'migration_id': 'information-fictional-original-attempt', 'state': 'rolled_back'})
    mount_roots = {row['Destination']: row['Source'] for row in recovered['app']['Mounts']}
    data, inbox = Path(mount_roots['/app/runtime/data']), Path(mount_roots['/app/runtime/inbox'])
    markers = {'data': {'path': str(data / 'information/store.json'), 'exists': False},
               'inbox': {'path': str(inbox / '.information-store.json'), 'exists': False},
               'transition': {'path': str(data / '.information-store-transition.json'), 'exists': False}}
    semantics, translations = recovery._recovered_configuration(original, recovered, rehearsal_baseline)
    protected = {'compose': rehearsal_baseline['compose'], 'environment': environment_files}
    preservation = {key: rehearsal_baseline[key] for key in ('private_report_ids', 'private_report_files',
        'private_report_library_sha256', 'packaged_report_files', 'packaged_report_catalog', 'packaged_report_library_sha256')}
    preservation['workspaces'] = workspace
    transition_proof = {'schema': 'berry.recovered-production-binding-transition.v1', 'version': 1, 'state': 'verified',
        'validator_program': validator, 'binding_program': binding_program,
        'original_baseline': original_ref, 'original_pre_baseline': original_pre_ref, 'recovered_baseline': recovered_ref,
        'observed_at_utc': '2026-11-10T04:00:01Z',
        'production_binding': {'original': rehearsal_baseline['production_binding'], 'recovered': recovered_baseline['production_binding']},
        'original_pre_binding': prior_baseline['production_binding'],
        'state_observations': {label: {role: value['production_binding'][role]['state'] for role in ('app', 'copilot')}
            for label, value in [('rehearsal', rehearsal_baseline), ('original_pre', prior_baseline), ('recovered', recovered_baseline)]},
        'raw_snapshots': {'original': raw_original, 'recovered': raw_recovered},
        'semantic_configuration': semantics, 'mechanical_translations': translations,
        'protected_files': {'original': protected, 'recovered': protected}, 'preservation': preservation,
        'ledgers': {'current': {'path': str(recovery.LEDGER_PATH), 'sha256': historical_ledger['sha256']}, 'immutable': historical_ledger},
        'rollback': {'journal': journal, 'migration_id': 'information-fictional-original-attempt', 'state': 'rolled_back',
            'markers': markers, 'information_directory': {'path': str(data / 'information'), 'state': 'absent'}},
        'native_checks': {'resource_counts': {name: {'disk_free_bytes': 20 * 1024**3, 'mem_available_bytes': 3 * 1024**3}
            for name in ('before', 'after')}, 'workspace_read_mode': 'mode=ro transaction; SQLite may update WAL SHM',
            'actual_current_pair_inspections': 3, 'actual_private_report_inventories': 2, 'actual_workspace_table_reads': 2,
            'actual_packaged_report_inventory': True, 'protected_compose_files': len(compose['files'])}}
    transition_proof_ref = write(private / 'transition-safe-proof.json', transition_proof)
    execution = {'schema': 'berry.recovery-transition-execution.v1', 'version': 1, 'state': 'completed', 'exit_code': 0,
        'program': producer, 'started_at_utc': '2026-11-10T04:00:00Z', 'finished_at_utc': '2026-11-10T04:00:02Z',
        'stdout': transition_proof_ref, 'proof': transition_proof_ref}
    execution_ref = write(private / 'transition-server-execution.json', execution)
    rendered = write(private / 'manual-rendered-compose.json', {'services': {role: {'image': row['Image']}
                                                                  for role, row in original.items()}})
    argv = ['docker', '--host', 'unix:///var/run/docker.sock', 'compose', '--project-name', compose['project'],
            '--project-directory', compose['working_dir']]
    for row in environment_files: argv += ['--env-file', row['path']]
    for row in compose['files']: argv += ['-f', row['path']]
    argv += ['up', '-d', '--no-build', '--pull', 'never', '--force-recreate', 'app', 'copilot']
    manual_plan = {'schema': 'berry.original-pair-recovery-plan.v1', 'state': 'prepared', 'argv': argv,
        'rendered': rendered, 'expected_images': {role: row['Image'] for role, row in original.items()},
        'original_snapshot': raw_original, 'baseline': original_pre_ref, 'journal': journal,
        'ordered_env_files': [row['path'] for row in environment_files], 'source_markers_absent': True,
        'environment_values_preserved': True, 'native_created_at': epoch + 10740}
    manual_plan_ref = write(private / 'manual-recovery-plan.json', manual_plan)
    pair = {role: {'id': row['Id'], 'image': row['Image'], 'healthy': True} for role, row in recovered.items()}
    health = {'schema': 'berry.original-pair-recovery.v1', 'state': 'old-pair-config-and-health-verified', 'pair': pair,
        'snapshot': raw_recovered, 'validator': validator, 'original_plan': manual_plan_ref,
        'write_barrier_remains_held': True, 'collector_remains_held': True, 'finished_at_unix': epoch + 10802}
    health_ref = write(private / 'manual-config-health-receipt.json', health)
    timer_hold = write(private / 'manual-original-timer-hold.json', {'original': {'ActiveState': 'active', 'UnitFileState': 'enabled'}})
    closure = {'schema': 'berry.original-release-recovery-closure.v1', 'state': 'recovered',
        'original_release_restored': True, 'unified_deployment_accepted': False, 'pair': pair,
        'full_pair_snapshot': raw_recovered, 'config_health_receipt': health_ref, 'recovered_baseline': recovered_ref,
        'protected_workspace_tables': 4, 'workspaces': workspace['page_count'], 'private_report_files': len(private_files),
        'reports': len(private_ids) + len(stable['packaged_report_catalog']['reports']),
        'legacy_promotion_manifest_runtime_and_semantic_hashes_preserved': True,
        'legacy_promotion_manifest_canonical_source': canonical_source, 'active_store_markers_absent': True,
        'barrier_restored': True, 'ingress': {'path': '/login', 'status': 200, 'tls_verified': True},
        'timer': {'ActiveState': 'active', 'UnitFileState': 'enabled', 'MainPID': '0', 'ControlPID': '0'},
        'collector_service': {'ActiveState': 'inactive', 'UnitFileState': 'static', 'MainPID': '0', 'ControlPID': '0'},
        'original_timer_hold': timer_hold, 'accepted_ledger_unchanged': True, 'closed_at_unix': epoch + 10804}
    closure_ref = write(private / 'manual-semantic-recovery-closure.json', closure)
    capsule = {'schema': 'berry.recovered-origin-adoption.v1', 'transition_execution': execution_ref, 'recovery_closure': closure_ref}
    capsule_ref = write(private / 'recovered-origin-capsule.json', capsule)

    def local(reference, name):
        return {**reference, 'path': 'C:\\fictional-admission\\' + name}

    bridge = {'execution': local(execution_ref, 'execution.json'), 'proof': transition_proof_ref,
        'stdout': transition_proof_ref, 'program': producer, 'validator': validator,
        'counts': {'workspaces': workspace['page_count'], 'workspace_tables': 4,
                   'private_report_files': len(private_files), 'private_reports': len(private_ids)},
        'raw_snapshots': transition_proof['raw_snapshots'], 'original_baseline': original_ref,
        'original_pre_baseline': original_pre_ref, 'recovered_baseline': recovered_ref,
        'admission_baselines': {'original': local(original_ref, 'original-baseline.json'),
                                'recovered': local(recovered_ref, 'recovered-baseline.json')},
        'local_transports': {name: local(reference, name + '.json') for name, reference in
            [('program', producer), ('proof', transition_proof_ref), ('stdout', transition_proof_ref), ('original_pre_baseline', original_pre_ref)]}}
    admission = load(plan['proofs']['rehearsal'])
    admission['recovered_production_binding'] = bridge
    replace(plan['proofs']['rehearsal'], admission)
    plan['proofs']['baseline'] = recovered_ref
    replace(wrapper['plan'], plan)
    proof.update(baseline_path=recovered_ref['path'], baseline_sha256=recovered_ref['sha256'],
                 old_binding=recovery._native_pair_binding(native_pre), protected_files=copy.deepcopy(environment_files),
                 compose_files=copy.deepcopy(compose['files']))
    proof['rollback_recipe']['plan_sha256'] = wrapper['plan']['sha256']
    replace(recovery_files['final_proof'], proof)
    phase['bindings']['proof_seals'] = {key: reference['sha256'] for key, reference in plan['proofs'].items()}
    phase['final_verification']['recovery_proof_sha256'] = recovery_files['final_proof']['sha256']
    replace(recovery_files['phase_receipt'], phase)
    native_ref = recovery_files['timestamp_dependencies']['native_verified_receipt']
    native = load(native_ref)
    native.update(final_receipt_sha256=recovery_files['phase_receipt']['sha256'], proof_seals=phase['bindings']['proof_seals'])
    replace(native_ref, native)
    archive = wrapper['archives']['current']
    transform = load(archive['transformation_proof']); transform['final_proof'] = recovery_files['final_proof']
    replace(archive['transformation_proof'], transform)
    recipe = load(archive['recovery_recipe']); recipe['transformation_proof'] = archive['transformation_proof']
    replace(archive['recovery_recipe'], recipe)
    env['recovered_origin'] = {'capsule': capsule_ref, 'capsule_value': capsule, 'bridge': bridge,
        'execution': execution_ref, 'execution_value': execution, 'proof': transition_proof_ref, 'proof_value': transition_proof,
        'original_baseline': original_ref, 'original_pre_baseline': original_pre_ref, 'recovered_baseline': recovered_ref,
        'raw_original': raw_original, 'raw_recovered': raw_recovered, 'original_pair': original, 'recovered_pair': recovered,
        'closure': closure_ref, 'closure_value': closure, 'config_health': health_ref, 'manual_plan': manual_plan_ref,
        'journal': journal, 'immutable_ledger': historical_ledger, 'producer': producer, 'validator': validator,
        'binding_program': binding_program, 'timer_hold': timer_hold}
    return capsule_ref
