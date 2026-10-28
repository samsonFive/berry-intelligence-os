"""The shell must update section clearance as its real header wraps."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_shared_header_measurement_tracks_wrap_and_restored_pages():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is needed for the browser-script contract')
    script = Path(__file__).with_name('workspace_anchor_checks.js')
    subprocess.run([node, str(script)], check=True, capture_output=True, text=True)
