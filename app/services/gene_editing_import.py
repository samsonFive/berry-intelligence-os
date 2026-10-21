"""Add-only native Entity/publication import; publication review is never bypassed."""
from copy import deepcopy
import json
import os
import tempfile
from pathlib import Path

from app.services.analyst_state_io import atomic_json
from app.services.pipeline_lock import pipeline_lock
from app.services.article_dedup import normalize_canonical_url


def canonical_url(value):
    return normalize_canonical_url(value)


def import_snapshot(snapshot, data_dir, inbox_dir):
    data_dir, inbox_dir = Path(data_dir), Path(inbox_dir)
    counts = {'companies_created': 0, 'programs_created': 0, 'news_created': 0, 'sources_created': 0,
              'preserved': 0, 'duplicate_urls': 0, 'relationships_for_review': len(snapshot['relationships'])}
    # The existing pipeline lease prevents a concurrent seed/collector race.
    with pipeline_lock(inbox_dir, 'gene_editing_import'):
        entities = {r['id']: r for p in (data_dir/'entities').rglob('*.json') for r in [json.loads(p.read_text(encoding='utf-8'))]}
        urls = {}
        ids = set()
        for folder in (data_dir/'evidence', inbox_dir/'evidence'):
            for path in folder.glob('*.json'):
                row = json.loads(path.read_text(encoding='utf-8'))
                ids.add(row.get('id'))
                if row.get('source_url'):
                    urls[canonical_url(row['source_url'])] = row['id']
        aliases = {}
        for original in snapshot['evidence']:
            row = deepcopy(original)
            if row['id'] in ids:
                counts['preserved'] += 1
                continue
            existing = urls.get(canonical_url(row['source_url']))
            if existing:
                aliases[row['id']] = existing
                counts['duplicate_urls'] += 1
                continue
            row.update(status='in_review', review_state='in_review', evidence_role='publication_artifact')
            atomic_json(inbox_dir/'evidence'/f"{row['id']}.json", row)
            urls[canonical_url(row['source_url'])] = row['id']
            ids.add(row['id'])
            counts['news_created'] += 1
        for kind, records in [('companies', snapshot['entities']), ('breeding_programs', snapshot['program_entities'])]:
            for original in records:
                if original['id'] in entities:
                    counts['preserved'] += 1
                    continue
                row = deepcopy(original)
                row['evidence_ids'] = [aliases.get(key, key) for key in row.get('evidence_ids', [])]
                atomic_json(data_dir/'entities'/kind/f"{row['id']}.json", row)
                entities[row['id']] = row
                counts['companies_created' if kind == 'companies' else 'programs_created'] += 1
        source_path = data_dir/'configuration/sources.json'
        sources = json.loads(source_path.read_text(encoding='utf-8')) if source_path.exists() else []
        source_ids = {r['id'] for r in sources}
        source_urls = {canonical_url(r.get('url') or r.get('value')) for r in sources}
        for source in snapshot['sources']:
            if source['id'] in source_ids or canonical_url(source['url']) in source_urls:
                counts['preserved'] += 1
                continue
            sources.append(source)
            source_ids.add(source['id'])
            source_urls.add(canonical_url(source['url']))
            counts['sources_created'] += 1
        if counts['sources_created']:
            # Preserve the hand-formatted existing registry verbatim. Only append
            # newly onboarded rows, rather than reformatting thousands of lines.
            raw = source_path.read_text(encoding='utf-8') if source_path.exists() else '[]\n'
            additions = [r for r in sources if r['id'] not in {s['id'] for s in json.loads(raw)}]
            body = raw.rstrip().removesuffix(']').rstrip()
            if json.loads(raw):
                body += ','
            body += '\n' + ',\n'.join('  '+json.dumps(r,ensure_ascii=False,indent=2).replace('\n','\n  ') for r in additions) + '\n]\n'
            source_path.parent.mkdir(parents=True,exist_ok=True)
            fd,temporary=tempfile.mkstemp(dir=source_path.parent,suffix='.tmp')
            try:
                with os.fdopen(fd,'w',encoding='utf-8') as stream:
                    stream.write(body)
                os.replace(temporary,source_path)
            finally:
                if Path(temporary).exists():
                    Path(temporary).unlink()
        # Persist identity remaps privately, so citations resolve to already-captured
        # originals without rewriting the immutable import or analyst records.
        mapping_path = inbox_dir/'gene_editing/evidence_aliases.json'
        previous = json.loads(mapping_path.read_text(encoding='utf-8')) if mapping_path.exists() else {}
        atomic_json(mapping_path, {**aliases, **previous})
    return counts
