"""A source jump reveals references without changing native navigation."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_source_jump_reveals_only_the_requested_disclosure():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is needed for the browser-script contract')
    subprocess.run([node, str(Path(__file__).with_name('learn_source_jump_checks.js'))],
                   check=True, capture_output=True, text=True)
