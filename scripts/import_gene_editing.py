"""Repeatable native import. Existing records and analyst corrections always win."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.services.gene_editing_import import import_snapshot

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--snapshot',type=Path,default=ROOT/'data/imports/gene-editing-2026-10-20/snapshot.json')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data')
    parser.add_argument('--inbox-dir',type=Path,default=ROOT/'inbox')
    args=parser.parse_args()
    print(json.dumps(import_snapshot(json.loads(args.snapshot.read_text(encoding='utf-8')), args.data_dir,args.inbox_dir),indent=2))
