"""Read-only article inputs for private variety identity discovery.

Uses the existing Digest source inventory, affirmed recoveries and Reader captures. No fetches,
candidate persistence, canonical writes or publication/claim approvals.
"""
from __future__ import annotations

from pathlib import Path
from functools import wraps
from io import BytesIO
from threading import RLock
import hashlib
import os
import pickle
import stat

from app.services.feed_first import SAFE_ID_RE
from app.services.feed_first_reader import CAPTURE_SUBDIR, capture_path, load_capture, merge_capture
from app.services.feed_first_live import CACHE_SUBDIR
from app.services.personal_digest import source_records
from app.services.presentation_memo import ByteMemo, _BuiltinPickler
from app.services.publication_sources import active_publication_record, inactive_publication_record
from app.services.source_body import article_full_text, reader_content
from app.services.source_reading import reviewed_original_for_reading

MAX_CAPTURE_BYTES = 2_000_000
MAX_ARTICLE_CHARS = 200_000


def _file_token(path):
    own = path.lstat()
    # Ordinary files need one syscall. Links/reparse points additionally need
    # their target state: editing or replacing either must invalidate reuse.
    actual = path.stat() if (stat.S_ISLNK(own.st_mode)
                             or getattr(own, 'st_reparse_tag', 0)) else own
    return tuple((row.st_ino, row.st_size, row.st_mtime_ns, row.st_ctime_ns,
                  row.st_mode, row.st_uid, row.st_gid) for row in (own, actual))


def _article_file_inputs(root):
    locations = ((root / CACHE_SUBDIR, '????-??-??.json'),
                 (root / 'news_packets' / 'captures', 'packet-*.json'),
                 (root / CAPTURE_SUBDIR, '*.json'),
                 (root / CAPTURE_SUBDIR / 'previews', '*.json'),
                 (root / 'source_fidelity' / 'artifacts', '*.json'))
    rows = []
    for folder, pattern in locations:
        try:
            folder_token = _file_token(folder)
        except FileNotFoundError:
            folder_token = None
        # Keep enumeration order: the original readers use it to break ties.
        rows.append((str(folder), folder_token,
                     [(path.name, _file_token(path)) for path in folder.glob(pattern)]))
    return rows


def _article_dependencies():
    # Replacing a selector (for example in a fixture) must also replace its
    # memo. Retain the references so object IDs cannot be recycled underneath it.
    from app.services import personal_digest, feed_first_reader
    return (article_source_records, source_records, reviewed_original_for_reading,
            capture_path, load_capture, merge_capture, article_full_text,
            reader_content, active_publication_record, inactive_publication_record,
            personal_digest.retained_news, feed_first_reader.attach_capture_previews)


def _memo_article_sources(function):
    memo = ByteMemo(max_bytes=32_000_000, max_entries=2, max_item=16_000_000)
    dependencies = ()
    lock = RLock()

    @wraps(function)
    def wrapped(published, inbox_dir, *, pending=None):
        nonlocal memo, dependencies
        # Windows ctime can mean creation time rather than metadata-change
        # time. Keep its original path rather than weakening edit freshness.
        if os.name != 'posix':
            return function(published, inbox_dir, pending=pending)
        current = _article_dependencies()
        with lock:
            if (len(current) != len(dependencies)
                    or any(left is not right for left, right in zip(current, dependencies))):
                dependencies = current
                memo = ByteMemo(max_bytes=32_000_000, max_entries=2, max_item=16_000_000)
            active_memo = memo
        try:
            root = Path(inbox_dir).resolve()
            before = _article_file_inputs(root)
            stream = BytesIO()
            # Exact builtin graph, including tuple/list distinctions and alias
            # structure. Classes/reducers are rejected before any execution.
            _BuiltinPickler(stream, protocol=5).dump((str(root), published, pending, before))
            payload = stream.getvalue()
            if len(payload) > 32_000_000:
                return function(published, inbox_dir, pending=pending)
            key = hashlib.sha256(payload).hexdigest()
        except (OSError, ValueError, TypeError, AttributeError, RecursionError, pickle.PicklingError):
            return function(published, inbox_dir, pending=pending)
        cached = active_memo.get(key)
        if cached is not None:
            try:
                if before == _article_file_inputs(root):
                    return cached
            except OSError:
                pass
        result = function(published, inbox_dir, pending=pending)
        try:
            if before == _article_file_inputs(root):
                active_memo.put(key, result)
        except OSError:
            pass
        return result
    return wrapped


def article_source_records(published: list[dict], inbox_dir: Path, *, pending=None) -> dict[str, dict]:
    """Known source identities; canonical prose wins over any inbox version.

    A same-ID pending draft may supply its stored article only for an exact
    source URL match. Conflicting identities stay in publication review.
    """
    records = source_records(published, inbox_dir)
    canonical_ids = {str(row["id"]) for row in published
                     if row.get("id") and row.get("status") == "published"}
    for original in pending or []:
        if inactive_publication_record(original) and str(original.get("id") or "") not in canonical_ids:
            records.pop(str(original.get("id") or ""), None)
            continue
        record = active_publication_record(original)
        if record is None or record["id"] in canonical_ids:
            continue
        cached = records.get(record["id"])
        if cached and cached.get("source_url") != record.get("source_url"):
            continue
        records[record["id"]] = record
    return records


@_memo_article_sources
def available_article_sources(published: list[dict], inbox_dir: Path, *, pending=None) -> tuple[list[dict], dict]:
    """Known published/retained news and optional active publication drafts.

    Text is selected only in the private identity workspace, never the feed's
    metadata projection or a public/static build. Existing stored text wins
    over a Reader capture, including operator edits.
    """
    records = article_source_records(published, inbox_dir, pending=pending)
    selected = []
    counts = {"known_sources": len(records), "readable_sources": 0,
              "reviewed_sources": 0, "unreviewed_sources": 0,
              "reader_captures": 0, "oversized_sources": 0,
              "affirmed_recoveries": 0, "recovery_issues": 0}
    for item_id, original in records.items():
        record = reviewed_original_for_reading(original, inbox_dir)
        recovered = (record.get('reader_source_recovery') or {}).get('state') == 'affirmed'
        counts['recovery_issues'] += int((record.get('reader_source_recovery') or {}).get('state') == 'unavailable')
        captured = False
        if SAFE_ID_RE.fullmatch(item_id) and original.get("source_url"):
            path = capture_path(inbox_dir, item_id)
            try:
                bounded = path.stat().st_size <= MAX_CAPTURE_BYTES
            except OSError:
                bounded = False
            if bounded:
                capture = load_capture(inbox_dir, item_id)
                if (capture and capture.get("ok") is True
                        and capture.get("item_id") == item_id
                        and capture.get("requested_url") == original["source_url"]
                        and isinstance(capture.get("passages"), list)
                        and all(isinstance(text, str) for text in capture["passages"])):
                    record = merge_capture(record, capture)
                    captured = not recovered and not article_full_text(original) and bool(article_full_text(record))
        # Recoveries and exact-source captures have already been considered.
        # A record with no article text cannot become an eligible article by
        # classifying its summary, description or transcript. Do not perform
        # Reader display work for that metadata-only case.
        text = article_full_text(record, preserve_line_breaks=True)
        if not text:
            continue
        content = reader_content(record)
        if content["state"] not in {"body_available", "body_partial"}:
            continue
        if len(text) > MAX_ARTICLE_CHARS:
            counts["oversized_sources"] += 1
            continue
        # A copied synopsis is still a synopsis, not an original article.
        if " ".join(text.split()) == " ".join(content["summary"].split()):
            continue
        selected.append(record)
        counts["readable_sources"] += 1
        counts["reviewed_sources" if record.get("status") == "published" else "unreviewed_sources"] += 1
        counts["reader_captures"] += int(captured)
        counts['affirmed_recoveries'] += int(recovered)
    return selected, counts
