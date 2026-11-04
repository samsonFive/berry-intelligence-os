"""Idempotently index an operator's actual topic-cache bodies for local reuse.

Only the specified inbox's immediate topic_research_cache is read. Evaluation
pools, Google baselines and arbitrary nested captures are never auto-imported.
No network, Evidence promotion or source subscription is performed.
"""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.services.research_source_cache import remember_sources


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inbox',type=Path,default=ROOT/'inbox')
    args=parser.parse_args();records=[];files=0;unreadable=0
    for path in sorted((args.inbox/'topic_research_cache').glob('*.json')):
        if path.is_symlink()or path.stat().st_size>12000000:unreadable+=1;continue
        try:
            payload=json.loads(path.read_text(encoding='utf8'))
            records.extend(payload.get('items',[]));files+=1
        except (OSError,ValueError,AttributeError):unreadable+=1
    receipt=remember_sources(args.inbox,records)
    print(json.dumps({'files':files,'unreadable':unreadable,'candidate_records':len(records),**receipt}))


if __name__=='__main__':main()
