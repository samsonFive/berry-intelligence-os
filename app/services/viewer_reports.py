"""Explicit selection of finished artifacts or saved prose; no report regeneration."""
import base64
from pathlib import Path

from app.services import report_library
from app.services.report_builder import reports_store
from app.viewer_assets.static_site import clean_html

MAX_REPORT_FILE = 10 * 1024 * 1024


def candidates(main):
    result = []
    for r in report_library.list_combined_finished_reports(main._report_library_roots()):
        result.append({'id': 'finished:' + r['id'], 'title': r['title'], 'date': r['published_date'],
                       'summary': r.get('summary') or '', 'status': 'Finished report', 'origin': 'finished', 'record': r})
    for r in reports_store.list_reports(main.INBOX_DIR):
        if r.get('status') == 'archived' or not r.get('sections'):
            continue
        result.append({'id': 'saved:' + r['id'], 'title': r['title'], 'date': str(r.get('updated_at') or r.get('created_at') or '')[:10],
                       'summary': 'Saved report prose as stored; no research is regenerated.',
                       'status': 'Saved ' + str(r.get('status') or 'draft') + ' — AI-assisted content may be unreviewed', 'origin': 'saved', 'record': r})
    return sorted(result, key=lambda r: (r['date'], r['id']), reverse=True)


def selected_reports(main, selected):
    from app.services.viewer_export import strings, text, public_url
    from html import escape
    selected = strings(selected)
    available = {r['id']: r for r in candidates(main)}
    if set(selected) - available.keys():
        raise ValueError('A selected report is unavailable or archived. Review the report selection again.')
    result = []
    for key in selected:
        item = available[key]
        r = item['record']
        files = []
        if item['origin'] == 'finished':
            path = r['files']['html']
            if path.stat().st_size > MAX_REPORT_FILE:
                raise ValueError('Selected report HTML exceeds the 10 MB file limit.')
            html = clean_html(path.read_text(encoding='utf-8-sig'))
            for ext in ('pdf', 'xlsx'):
                path = r['files'].get(ext)
                if path is None:
                    continue
                if path.stat().st_size > MAX_REPORT_FILE:
                    raise ValueError('Selected report download exceeds the 10 MB file limit.')
                body = path.read_bytes()
                if (ext == 'pdf' and not body.startswith(b'%PDF-')) or (ext == 'xlsx' and not body.startswith(b'PK')):
                    raise ValueError('Selected report download format does not match its file type.')
                files.append({'name': ext, 'extension': ext, 'base64': base64.b64encode(body).decode()})
        else:
            sections = []
            source_ids = set()
            for section in r['sections']:
                prose = section.get('edited_prose') if section.get('edited_prose') is not None else section.get('generated_prose')
                if not prose:
                    continue
                source_ids.update(section.get('citation_ids') or [])
                sections.append('<section><h2>' + escape(str(section.get('title') or section.get('section_id') or 'Section')) + '</h2><p style="white-space:pre-wrap">' + escape(str(prose)) + '</p></section>')
            records = {v['id']: v for v in main.unified_information(include_private=True)}
            references = []
            for sid in sorted(source_ids):
                source = records.get(sid) or {}
                if source.get('publication_scope') == 'private' or source.get('status') in {'rejected', 'archived', 'deleted', 'withdrawn'}:
                    continue
                try:
                    url = public_url(source.get('source_url'))
                except ValueError:
                    continue
                if url:
                    references.append('<li><a href="' + escape(url, quote=True) + '">' + escape(str(source.get('title') or sid)) + '</a></li>')
            html = ''.join(sections) + '<h2>Available source references</h2><ul>' + ''.join(references) + '</ul>'
            if not sections:
                raise ValueError('A selected saved report has no stored prose to export. Finish or deselect it.')
        result.append({'id': key, 'title': text(item['title'], 500), 'date': item['date'], 'summary': text(item['summary']),
                       'status': item['status'], 'html': html, 'files': files})
    return normalize_reports(result)


def normalize_reports(raw):
    from app.services import viewer_export as s
    result = []
    for r in s.rows(raw or [], 'Reports'):
        files = []
        for a in s.rows(r.get('files', []), 'Report files'):
            if a.get('extension') not in {'pdf', 'xlsx'}:
                raise ValueError('Report downloads must be PDF or XLSX.')
            try:
                body = base64.b64decode(a.get('base64', ''), validate=True)
            except (ValueError, TypeError):
                raise ValueError('Invalid report file encoding.') from None
            if len(body) > MAX_REPORT_FILE or not body.startswith(b'%PDF-' if a['extension'] == 'pdf' else b'PK'):
                raise ValueError('Invalid or oversized report file.')
            files.append({'name': s.text(a.get('name'), 100), 'extension': a['extension'], 'base64': base64.b64encode(body).decode()})
        result.append({'id': s.identifier(r.get('id')), 'title': s.text(r.get('title'), 500),
                       'date': s.iso_date(r['date']) if r.get('date') else '', 'summary': s.text(r.get('summary')),
                       'status': s.text(r.get('status'), 300), 'html': clean_html(s.text(r.get('html'), MAX_REPORT_FILE)), 'files': files})
    return s.unique(result, 'report')
