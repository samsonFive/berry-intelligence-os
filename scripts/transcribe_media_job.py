"""Run one explicit, time-limited publisher/caption job. Never starts STT."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.runtime_config import resolve_inbox_dir
from app.services.media_transcription_jobs import run_job, status_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--item', required=True)
    parser.add_argument('--inbox-dir', type=Path)
    parser.add_argument('--timeout', type=int, default=60)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    inbox = args.inbox_dir or resolve_inbox_dir(ROOT)
    status_path(inbox, args.item)  # Validate before composing a filesystem path.
    if args.worker:
        from app.services.media_transcription import transcribe_discovered_item, load_transcript_artifact
        item = json.loads((inbox / 'discovered_media' / (args.item + '.json')).read_text(encoding='utf-8'))
        existing = load_transcript_artifact(inbox, args.item)
        if existing:
            if (existing.get('item_id') or existing.get('discovered_item_id')) != args.item:
                raise ValueError('Stored transcript identity mismatch')
            from app.services.transcript_evidence import TranscriptArtifact
            from app.services.media_orchestration import publication_draft_id
            artifact = TranscriptArtifact.from_dict({**existing, 'parent_evidence_id': existing.get('parent_evidence_id') or publication_draft_id(item)})
            result = {'status': 'ok', 'segment_count': len(artifact.segments), 'language': artifact.language, 'tier': 'existing_stored_transcript'}
        else:
            outcome = transcribe_discovered_item(inbox, item, max_tier=2)
            result = {'status': outcome.status, 'segment_count': outcome.segment_count,
                      'language': outcome.detected_language, 'tier': outcome.tier,
                      'partial': bool(outcome.diagnostics.get('low_coverage_suspected')),
                      'caption_reason': outcome.diagnostics.get('caption_reason')}
        print(json.dumps(result))
        return 0
    row = run_job(inbox, args.item, timeout=args.timeout)
    print(json.dumps(row, indent=2))
    return 1 if row['state'] == 'failed' else 0


if __name__ == '__main__':
    raise SystemExit(main())
