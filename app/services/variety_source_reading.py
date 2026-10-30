"""Private source reading beside a variety; never a trait or identity writer."""
from urllib.parse import quote, urlsplit

from app.services.deterministic_tagging import matchers_from_entities
from app.services.feed_first import SAFE_ID_RE
from app.services.feed_first_reader import is_public_http_url
from app.services.publication_sources import active_publication_record
from app.services.source_body import article_full_text, classify_source_body
from app.services.variety_universe.identity import resolve_identity


def stored_source_reading(item_id, *, load_record, inbox_dir):
    """Reuse exact-source Reader captures and affirmed recoveries, without fetching."""
    if not SAFE_ID_RE.fullmatch(str(item_id)):
        return None
    record = load_record(item_id)
    if not record:
        return None
    from app.services.source_reading import reviewed_original_for_reading
    from app.services.feed_first_reader import capture_path, load_capture, merge_capture
    record = reviewed_original_for_reading(record, inbox_dir)
    if classify_source_body(record)['state'] in {'body_available', 'body_partial'}:
        return record
    path = capture_path(inbox_dir, item_id)
    try:
        if path.is_symlink() or path.stat().st_size > 2_000_000:
            return record
        capture = load_capture(inbox_dir, item_id)
    except (OSError, ValueError):
        return record
    if (not capture or capture.get('ok') is not True or capture.get('item_id') != item_id
            or capture.get('requested_url') != record.get('source_url')
            or not isinstance(capture.get('passages'), list)
            or not all(isinstance(text, str) for text in capture['passages'])):
        return record
    merged = merge_capture(record, capture)
    if article_full_text(merged):
        merged['_private_capture_unreviewed'] = True
    return merged


def _eligible(record):
    if record.get('status') == 'published':
        return record.get('evidence_role') != 'atomic_evidence' and record.get('review_state') not in {'rejected', 'archived'}
    return active_publication_record(record) is not None


def _title_mentions(record, varieties, matchers):
    """Reuse exact catalog matching; suppress contained names and ambiguous aliases."""
    title = record.get('title') or ''
    matches = [(match.start(), match.end(), match.group()) for _, pattern in matchers
               for match in pattern.finditer(title)]
    ids = set()
    for start, end, text in matches:
        if any(a <= start and end <= b and b - a > end - start for a, b, _ in matches):
            continue
        resolution = resolve_identity({'candidate_name': text, 'berry_ids': record.get('berry_ids', [])}, varieties)
        exact = set()
        if resolution['identity_state'] == 'possible_alias':
            exact = {row['variety_id'] for row in resolution['matches']}
        if len(exact) == 1:
            ids.update(exact)
    return ids


def profile_source_reading(variety, *, varieties, records, load_record, limit=12):
    """Select from metadata, then hydrate at most twelve exact-source records.

    A title mention is explicitly unreviewed, not an approved entity link.
    Missing source text stays a coverage gap, not a fabricated profile value.
    """
    matchers = matchers_from_entities(varieties, 'variety')
    target_patterns = [pattern for entity_id, pattern in matchers if entity_id == variety['id']]
    selected = {}
    crop = set(variety.get('berry_ids') or [])
    for record in records:
        rid = str(record.get('id') or '')
        if not SAFE_ID_RE.fullmatch(rid) or not _eligible(record):
            continue
        if not is_public_http_url(record.get('source_url') or ''):
            continue
        declared = set(record.get('berry_ids') or [])
        if crop and declared and not crop.intersection(declared):
            continue
        linked = (variety['id'] in (record.get('entity_ids') or [])
                  or rid in (variety.get('evidence_ids') or []))
        if not linked:
            if not declared or not any(pattern.search(record.get('title') or '') for pattern in target_patterns):
                continue
            if variety['id'] not in _title_mentions(record, varieties, matchers):
                continue
        old = selected.get(rid)
        if old and old['record'].get('status') == 'published':
            continue
        selected[rid] = {'record': record, 'linked': linked}
    ordered = sorted(selected.values(), key=lambda row: (
        row['record'].get('source_type') in {'company_website', 'breeder_catalog', 'university_extension'},
        str(row['record'].get('published_date') or '')), reverse=True)
    rows = []
    for item in ordered[:limit]:
        meta = item['record']
        try:
            full = load_record(meta['id'])
        except (OSError, ValueError):
            full = None
        if full and full.get('id') == meta['id'] and not _eligible(full):
            continue  # A current human rejection wins over stale list metadata.
        if (not full or full.get('id') != meta['id'] or full.get('source_url') != meta['source_url']
                or not _eligible(full)):
            full = meta
        state = classify_source_body(full)['state']
        text = article_full_text(full, preserve_line_breaks=True) if state in {'body_available', 'body_partial'} else ''
        # Local excerpts remain bounded; the existing Reader owns the whole source.
        passages = [part.strip() for part in text.split('\n') if part.strip()]
        rows.append(dict(id=meta['id'], title=meta.get('title') or meta['id'],
            source_url=meta['source_url'], host=urlsplit(meta['source_url']).hostname,
            source_name=meta.get('source_name') or '', published_date=full.get('published_date') or meta.get('published_date'),
            fetched_at=(full.get('article') or {}).get('fetched_at') or (full.get('reader_capture') or {}).get('retrieved_at'),
            pending=full.get('status') != 'published', linked=item['linked'], readable=bool(text),
            capture_unreviewed=bool(full.get('_private_capture_unreviewed')),
            state=state, excerpt=text[:700], passages=[p[:1500] for p in passages[:6]],
            reader_href='/intelligence/' + quote(meta['id'], safe=''),
            review_href='/review/' + quote(meta['id'], safe='')))
    rows.sort(key=lambda row: row['readable'], reverse=True)
    return dict(rows=rows, matched_sources=len(ordered), shown=len(rows),
                readable=sum(row['readable'] for row in rows), missing=sum(not row['readable'] for row in rows),
                truncated=len(ordered) > limit)
