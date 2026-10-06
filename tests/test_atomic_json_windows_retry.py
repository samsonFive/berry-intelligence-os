"""Readers briefly holding a Windows file cannot corrupt analyst metadata."""
import json
from pathlib import Path

import pytest

from app.services import analyst_state_io as io


def test_temporary_windows_lock_retries_without_removing_old_record(tmp_path, monkeypatch):
    target = tmp_path / 'state.json'
    target.write_text('{"saved":true}')
    original = Path.replace
    calls = []
    def replace(path, destination):
        calls.append(path)
        if len(calls) < 3:
            assert json.loads(target.read_text()) == {'saved': True}
            error = PermissionError('held by another reader')
            error.winerror = 5
            raise error
        return original(path, destination)
    monkeypatch.setattr(Path, 'replace', replace)
    monkeypatch.setattr(io, 'sleep', lambda duration: None)
    io.atomic_json(target, {'saved': True, 'status': 'ready'})
    assert len(calls) == 3 and json.loads(target.read_text())['status'] == 'ready'
    assert list(tmp_path.iterdir()) == [target]


def test_persistent_denial_preserves_original_and_cleans_temporary(tmp_path, monkeypatch):
    target = tmp_path / 'state.json'
    original = '{"saved":true}'
    target.write_text(original)
    def replace(*args):
        error = PermissionError('persistent denial')
        error.winerror = 32
        raise error
    monkeypatch.setattr(Path, 'replace', replace)
    monkeypatch.setattr(io, 'sleep', lambda duration: None)
    with pytest.raises(PermissionError):
        io.atomic_json(target, {'saved': False})
    assert target.read_text() == original and list(tmp_path.iterdir()) == [target]
