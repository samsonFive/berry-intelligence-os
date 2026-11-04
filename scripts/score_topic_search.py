"""Score an existing benchmark snapshot without any network/provider request."""
from pathlib import Path
import argparse
import json
import hashlib
from datetime import datetime, timezone
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.services.search_quality_evaluation import score_snapshot


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--google-baseline',type=Path,required=True)
    parser.add_argument('--judgments',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    run=json.loads(args.run.read_text(encoding='utf8'));baseline=json.loads(args.google_baseline.read_text(encoding='utf8'))
    judgments=json.loads(args.judgments.read_text(encoding='utf8')) if args.judgments else {}
    report=score_snapshot(run,baseline,judgments)
    report["computed_at"]=datetime.now(timezone.utc).isoformat(timespec="seconds")
    report["input_sha256"]={"run":hashlib.sha256(args.run.read_bytes()).hexdigest(),"google_baseline":hashlib.sha256(args.google_baseline.read_bytes()).hexdigest(),"judgments":hashlib.sha256(args.judgments.read_bytes()).hexdigest() if args.judgments else None}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({key:value for key,value in report.items() if key!='queries'},ensure_ascii=True,indent=2))


if __name__=='__main__':main()
