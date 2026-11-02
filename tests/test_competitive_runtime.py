"""Production-style mounts must work without checkout-local runtime paths."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from app.services import competitive_evaluation as ce
from app.services.living_workspaces import Store
from tests.test_competitive_evaluation import research


@pytest.mark.parametrize('explicit_paths', [False, True])
def test_competitive_import_uses_mounted_runtime(research, tmp_path, explicit_paths):
    _, entities, _, payload, _, _, _ = research
    runtime = tmp_path / 'mounted-runtime'
    data = runtime / 'data'
    inbox = runtime / 'inbox'
    catalogue = data / 'imports/competitive-landscape-2026-10-30-v1'
    catalogue.mkdir(parents=True)
    (catalogue / 'capability-rubrics.json').write_text(json.dumps(ce.catalogue()), encoding='utf-8')
    (data / 'entities').mkdir()
    for key, entity in entities.items():
        (data / 'entities' / (key+'.json')).write_text(json.dumps(entity), encoding='utf-8')
    batch = inbox / 'competitive_landscape/web-research-2026-10-30/assembled/B16'
    batch.mkdir(parents=True)
    (batch / 'candidate-records.json').write_text(json.dumps(payload), encoding='utf-8')
    env = {k: v for k, v in os.environ.items() if k not in {'BIOS_DATA_DIR', 'BIOS_INBOX_DIR', 'BIOS_RUNTIME_DIR'}}
    env['BIOS_RUNTIME_DIR'] = str(tmp_path / 'unused' if explicit_paths else runtime)
    if explicit_paths:
        env.update(BIOS_DATA_DIR=str(data), BIOS_INBOX_DIR=str(inbox))
    root = Path(__file__).resolve().parents[1]
    probe = 'from app.services.competitive_evaluation import CATALOGUE,catalogue; print(CATALOGUE); assert catalogue()["rubric_version"]'
    checked = subprocess.run([sys.executable, '-c', probe], cwd=root, env=env, text=True, capture_output=True, check=True)
    assert str(catalogue) in checked.stdout
    imported = subprocess.run([sys.executable, '-m', 'scripts.import_competitive_research', '--apply'], cwd=root, env=env, text=True, capture_output=True, check=True)
    summary = json.loads(imported.stdout)
    assert summary['batches'] == 1 and summary['candidate_rows'] == 2
    assert summary['totals']['accepted_structure'] == 2
    assert len(Store(inbox).rows('competitive_record')) == 2
