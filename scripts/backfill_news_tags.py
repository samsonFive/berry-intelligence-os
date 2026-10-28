"""Classify stored sources only; safe to rerun after interruption or ingestion."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inbox', type=Path, help='Existing private runtime inbox (defaults to app configuration)')
    parser.add_argument('--data', type=Path, help='Existing canonical data directory')
    args = parser.parse_args()
    if args.inbox:
        os.environ['BIOS_INBOX_DIR'] = str(args.inbox.resolve())
    if args.data:
        os.environ['BIOS_DATA_DIR'] = str(args.data.resolve())
    from app.news_workspace_routes import classify_stored_tags
    from app import main as app
    from app.services import news_tags
    text_coverage = classify_stored_tags()
    with news_tags.database(app.INBOX_DIR) as db:
        coverage = [dict(row) for row in db.execute('''SELECT t.name, COUNT(a.article) AS evaluated,
            SUM(a.present) AS automatic_matches FROM tags t LEFT JOIN automatic a ON a.tag=t.id GROUP BY t.id ORDER BY t.name''')]
    print(json.dumps({'job': news_tags.job_state(app.INBOX_DIR), 'text_coverage': text_coverage, 'coverage': coverage}, indent=2))


if __name__ == '__main__':
    main()
