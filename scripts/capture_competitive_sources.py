"""Capture explicitly selected research-source metadata through retained News packets.

No fetching, extraction, publication or trust promotion. The selection file is
private and must identify each source plus any analyst-resolved destination IDs.
Re-running retains canonical article identity rather than duplicating sources.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
import re
from pathlib import Path

from app.services import competitive_evaluation as ce, personal_digest
from app.services.analyst_state_io import atomic_json
from app.services.pipeline_lock import pipeline_lock
from app.services.article_dedup import normalize_canonical_url
from app.services.living_workspaces import Store, digest


def capture(inbox, selections, *, published=(), entities):
    store = Store(inbox)
    research = store.rows('competitive_record')
    sources = {(r['batch_id'], r['local_id']): r for r in research if r['kind'] == 'source'}
    existing = personal_digest.source_records(list(published), inbox, metadata_only=True)
    by_url = {normalize_canonical_url(r.get('source_url')): r['id'] for r in sorted(existing.values(), key=lambda r:r.get('status')=='published')}
    path = Path(inbox) / 'news_packets/captures/packet-competitive-research.json'
    with pipeline_lock(Path(inbox), 'competitive-source-capture'):
        packet = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'records': []}
        retained = {r['id']: r for r in packet['records']}
        links = []
        for selected in selections:
            source = sources[(selected['batch_id'], selected['source_id'])]
            f = source['fields']
            url = normalize_canonical_url(f['original_url'])
            if not str(f['original_url']).startswith(('https://', 'http://')):
                raise ValueError('Public original HTTP(S) URL required')
            article_id = by_url.get(url) or 'ev-research-' + digest(url)[:28]
            old = retained.get(article_id, {})
            destinations = selected.get('destination_market_ids', old.get('destination_market_ids', []))
            destination_rationale = selected.get('destination_rationale') or old.get('scope_resolution')
            if destinations and (not destination_rationale or any(entities.get(x, {}).get('entity_type') != 'geography' for x in destinations)):
                raise ValueError('Canonical destinations need an explicit source-based rationale')
            related = [r for r in research if r['batch_id'] == source['batch_id'] and source['local_id'] in r['source_refs'] and r['resolution'] == 'accepted_structure']
            ids = sorted({r['entity_id'] for r in related if r.get('entity_id') in entities})
            berries = sorted({berry for r in related for berry in re.findall(r'berry-(?:blueberry|strawberry|raspberry|blackberry)\b', str(r['fields'].get('berry_scope') or ''))})
            if article_id not in existing or article_id in retained:
                raw_date = str(f.get('published_date') or '')[:10]
                try:
                    published_date = date.fromisoformat(raw_date).isoformat()
                except ValueError:
                    published_date = None
                old = retained.get(article_id, {})
                retained[article_id] = {'id': article_id, 'record_type': 'evidence', 'status': 'unreviewed',
                    'title': f.get('title_original') or f.get('title') or source['local_id'],
                    'source_name': f.get('publisher') or f.get('source_family') or 'Unknown',
                    'source_url': f['original_url'], 'published_date': published_date,
                    'captured_date': old.get('captured_date') or date.today().isoformat(),
                    'event_date': f.get('event_date') if f.get('event_date') not in {None, '', 'Unknown'} else None,
                    'summary': 'Research-source metadata; original attribution remains unreviewed. ' + str(f.get('supporting_passage') or '')[:700],
                    'entity_ids': sorted(set(old.get('entity_ids', [])) | set(ids)),
                    'berry_ids': sorted(set(old.get('berry_ids', [])) | set(berries)),
                    'destination_market_ids': destinations, 'tags': old.get('tags', []),
                    'competitive_source_ids': sorted(set(old.get('competitive_source_ids', [])) | {source['id']}),
                    'source_type': 'manual_public_research_capture',
                    'scope_resolution': destination_rationale or 'No destination inferred',
                    'article': {'extraction_status': 'metadata_only'}}
                by_url[url] = article_id
            links.append((source['id'], f['original_url'], article_id))
        packet['records'] = list(retained.values())
        packet['trust_effect'] = 'Private metadata captures only; no publication or extracted Atomic Evidence'
        atomic_json(path, packet)
        # Captures remain recoverable if a concurrent research revision prevents
        # linking; retry can finish the link without duplicating the article.
        with store.transaction() as db:
            for source_id, original_url, article_id in links:
                current = store.get(source_id, db)
                if current['fields']['original_url'] != original_url:
                    raise ValueError('Original source changed during capture; retry with the current source')
                if current.get('article_id') != article_id:
                    current['article_id'] = article_id
                    store.put(db, 'competitive_record', current, 'public-source-capture', expected=current['version'])
    return {'retained_captures': len(retained), 'selected_sources': len(selections)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('selection_file', type=Path)
    parser.add_argument('--inbox', type=Path, default=ce.ROOT / 'inbox')
    args = parser.parse_args()
    from app import main
    print(json.dumps(capture(args.inbox, json.loads(args.selection_file.read_text(encoding='utf-8')),
                           published=main.published_evidence(), entities={r['id']:r for r in main.all_entities()}), indent=2))
