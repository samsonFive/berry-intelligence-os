"""Run an isolated loopback rehearsal with real research and no paid providers.

Clone the shared workspace SQLite snapshot only when the target does not exist.
Shared workspace objects and their history are copied. Credential, user-account
and source-provider configuration files are excluded. Rehearsal decisions stay
in the explicitly named preview inbox.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import os
from pathlib import Path
import shutil
import sqlite3


def clone(source, target):
    source, target = Path(source).resolve(), Path(target).resolve()
    if source == target or source in target.parents:
        raise ValueError('Use a sibling preview inbox, outside the source inbox')
    original = source / 'living_workspaces/workspace.sqlite3'
    destination = target / 'living_workspaces/workspace.sqlite3'
    if destination.exists():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(original.as_uri()+'?mode=ro', uri=True)) as src:
        with closing(sqlite3.connect(destination)) as dst:
            src.backup(dst)
    captures = source / 'news_packets/captures/packet-competitive-research.json'
    if captures.exists():
        folder = target / 'news_packets/captures'
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(captures, folder / captures.name)
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inbox', required=True, type=Path)
    parser.add_argument('--clone-from', type=Path)
    parser.add_argument('--port', type=int, default=8770)
    args = parser.parse_args()
    if args.clone_from:
        clone(args.clone_from, args.inbox)
    os.environ['BIOS_INBOX_DIR'] = str(args.inbox.resolve())
    os.environ['ENABLE_SOURCE_POLLING'] = '0'
    os.environ['ENABLE_PERPLEXITY_PULSE'] = '0'
    for key in ('PERPLEXITY_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'EXA_API_KEY', 'APITUBE_API_KEY', 'NEWSCATCHER_API_KEY', 'GEMINI_API_KEY', 'GOOGLE_API_KEY'):
        os.environ[key] = ''
    from app.main import app
    app.state.competitive_preview = True
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=args.port)
