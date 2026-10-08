"""Explicit guarded trial jobs; private environment token, no scheduler."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.social_intelligence.apify_jobs import ApifyJobs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--manifest', type=Path, help='Private JSON: case, actor, build_id, build_number, actor_input')
    choice.add_argument('--observe', help='Poll saved case once; never submit a new job')
    choice.add_argument('--status', action='store_true', help='Content-free cached job/budget status; no network')
    choice.add_argument('--normalize', help='Offline cached export for reviewed schema-validated import; no network or ingestion')
    parser.add_argument('--live', action='store_true', help='Explicit API opt-in; requires APIFY_TOKEN privately')
    parser.add_argument('--private-dir', type=Path, default=ROOT / 'inbox/social-bakeoff/apify-jobs')
    args = parser.parse_args()
    if not args.live and not (args.normalize or args.status):
        parser.error('API operations require --live; ordinary tests are offline')
    folder = args.private_dir.resolve()
    inbox = (ROOT / 'inbox').resolve()
    if not folder.is_relative_to(inbox):
        parser.error('Job state and raw datasets must remain below the private inbox')
    jobs = ApifyJobs(folder, enabled=args.live and not (args.normalize or args.status))
    if args.status:
        result = jobs.cached_status()
    elif args.normalize:
        result = jobs.normalize_cached(args.normalize)
    elif args.manifest:
        if args.manifest.stat().st_size > 16000:
            parser.error('Manifest byte ceiling exceeded')
        config = json.loads(args.manifest.read_text(encoding='utf-8'))
        result = jobs.launch(config['case'], config['actor'], build_id=config['build_id'],
                             build_number=config['build_number'], actor_input=config['actor_input'])
    else:
        result = jobs.observe(args.observe)
    # Raw post content/input and credential never enter console/report output.
    print(json.dumps(result if args.status else {k: result[k] for k in ('case', 'run_id', 'state', 'reused', 'terminal', 'normalized', 'rejected', 'duplicate_copies', 'mode', 'ingested', 'file') if k in result}))


if __name__ == '__main__':
    main()
