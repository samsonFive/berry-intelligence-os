"""Idempotent topic backfill; never changes publication dates or trust state.

Stored analyst classification (reviewed_by or origin=analyst) always wins.
Only classification and topic tags are changed; monitoring tags are independent.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.services.gene_editing import classify, TOPICS
from app.services.analyst_state_io import atomic_json


def backfill(folder, *, apply=False):
    counts={'changed':0,'unchanged':0,'analyst_preserved':0}
    for path in sorted(Path(folder).glob('*.json')):
        record=json.loads(path.read_text(encoding='utf-8'))
        old=record.get('classification') or {}
        if old.get('reviewed_by') or old.get('origin')=='analyst':
            counts['analyst_preserved']+=1
            continue
        classification=classify(record)
        if all(old.get(key)==value for key,value in classification.items()):
            counts['unchanged']+=1
            continue
        # No irrelevant-record churn when this classifier has never tagged it.
        if not classification['topics'] and not old.get('version','').startswith('gene-editing-'):
            counts['unchanged']+=1
            continue
        record['classification']={**classification,'classified_at':datetime.now(timezone.utc).isoformat()}
        record['tags']=[t for t in record.get('tags',[]) if t not in TOPICS]+classification['topics']
        counts['changed']+=1
        if apply:
            atomic_json(path,record)
    return counts

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('folder',type=Path)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    print(json.dumps(backfill(args.folder,apply=args.apply)))
