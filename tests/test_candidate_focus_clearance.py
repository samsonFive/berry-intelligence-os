"""Keyboard focus clears the sticky shell without changing navigation or data."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_candidate_controls_clear_sticky_navigation_only_on_focus():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is needed for the browser-script contract')
    script = Path(__file__).with_name('candidate_focus_checks.js')
    subprocess.run([node, str(script)], check=True, capture_output=True, text=True)
