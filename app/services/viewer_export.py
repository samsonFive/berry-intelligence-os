"""Private, account-scoped exports to the disconnected static company viewer.

No article acquisition, model calls, evidence writes, or corporate publication occurs. Recorded public asset retrieval is handled by viewer_content during preview.
Only allowlisted output fields are persisted or embedded in a release.
"""
from __future__ import annotations

import base64
from copy import deepcopy
import csv
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from io import BytesIO, StringIO
import json
import math
from pathlib import Path
import re
import secrets
from urllib.parse import urlsplit
from zipfile import ZIP_DEFLATED, ZipFile

from app.services import personal_scope
from app.services.analyst_state_io import atomic_json, serialized_write

ASSETS = Path(__file__).resolve().parents[1] / 'viewer_assets'
MAX_FILE = 10 * 1024 * 1024
MAX_ROWS = 20000
PANELS = ('panel-1', 'panel-2', 'panel-3', 'panel-4')
METRICS = ('overall_liking', 'taste', 'texture', 'appearance')
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}\Z')


class ExportConflict(ValueError):
    """A newer export or a changed baseline must be reviewed again."""


def now():
    return datetime.now(UTC).isoformat(timespec='seconds')


def text(value, limit=8000):
    if value is None:
        return ''
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f'Text must be a string of at most {limit} characters.')
    return value.strip()


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError('Record IDs must be stable strings using letters, numbers, periods, hyphens, underscores or colons.')
    return value


def strings(value):
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_ROWS:
        raise ValueError('Expected a bounded list of strings.')
    return list(dict.fromkeys(text(v, 160) for v in value if v))


def rows(value, label):
    if not isinstance(value, list) or len(value) > MAX_ROWS or any(not isinstance(r, dict) for r in value):
        raise ValueError(f'{label} must be a list of at most {MAX_ROWS} records.')
    return value


def unique(value, label):
    result, seen = [], set()
    for row in value:
        if row['id'] in seen:
            raise ValueError(f'Duplicate {label} ID: {row["id"]}.')
        seen.add(row['id'])
        result.append(row)
    return result


def iso_date(value):
    value = text(value, 50)
    try:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ValueError('Choose a real date in YYYY-MM-DD format.') from None


def public_url(value):
    value = text(value, 2000)
    if not value:
        return ''
    try:
        parts = urlsplit(value)
        if (parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username or parts.password
                or any(ord(c) < 33 for c in value)):
            raise ValueError
    except ValueError:
        raise ValueError('Source URLs must be valid HTTP(S) links without embedded credentials.') from None
    return value


def crop(value):
    return text(value, 100).removeprefix('berry-').lower()


def normalize_directory(raw):
    if not isinstance(raw, dict):
        raise ValueError('The directory is missing.')
    companies = unique([{
        'id': identifier(r.get('id')), 'name': text(r.get('name'), 300),
        'aliases': strings(r.get('aliases')), 'country': text(r.get('country'), 100),
        'activity_geographies': strings(r.get('activity_geographies')),
        'roles': strings(r.get('roles')), 'berries': [crop(b) for b in strings(r.get('berries'))],
        'description': text(r.get('description')), 'tags': strings(r.get('tags')),
        'website': public_url(r.get('website')),
        'socials': [{'platform': text(a.get('platform'), 100), 'url': public_url(a.get('url'))} for a in rows(r.get('socials', []), 'Social channels')],
    } for r in rows(raw.get('companies'), 'Companies')], 'company')
    company_ids = {r['id'] for r in companies}
    varieties = unique([{
        'id': identifier(r.get('id')), 'name': text(r.get('name'), 300),
        'aliases': strings(r.get('aliases')), 'berry': crop(r.get('berry')),
        'company_ids': strings(r.get('company_ids')), 'activity_geographies': strings(r.get('activity_geographies')),
        'description': text(r.get('description')),
        'traits': strings(r.get('traits')), 'tags': strings(r.get('tags')),
    } for r in rows(raw.get('varieties'), 'Varieties')], 'variety')
    for r in companies + varieties:
        if not r['name']:
            raise ValueError(f'{r["id"]} needs a name.')
    for r in varieties:
        if not r['berry']:
            raise ValueError(f'Variety {r["id"]} has no recorded berry scope. Resolve its directory scope before export.')
        if set(r['company_ids']) - company_ids:
            raise ValueError(f'Variety {r["id"]} references a missing company.')
    return {'companies': companies, 'varieties': varieties, 'exported_at': text(raw.get('exported_at'), 100),
            'title': text(raw.get('title'), 200) or 'Company and variety directory'}


def normalize_issue(raw):
    if not isinstance(raw, dict):
        raise ValueError('A newsletter issue must be an object.')
    items = unique([{
        'id': identifier(r.get('id')), 'title': text(r.get('title'), 300),
        'summary': text(r.get('summary')), 'source': text(r.get('source'), 200),
        'source_url': public_url(r.get('source_url')),
        'published_date': iso_date(r['published_date']) if r.get('published_date') else '',
        'category': text(r.get('category'), 100) or 'Industry',
        'berries': [crop(b) for b in strings(r.get('berries'))], 'company_ids': strings(r.get('company_ids')),
        'tags': strings(r.get('tags')), 'editor_note': text(r.get('editor_note')),
        'status': text(r.get('status'), 100) or 'Curated selection',
    } for r in rows(raw.get('items'), 'Newsletter stories')], 'story')
    if any(not r['title'] for r in items):
        raise ValueError('Every selected story needs a title.')
    title = text(raw.get('title'), 300)
    if not title:
        raise ValueError('Give the newsletter edition a title.')
    return {'id': identifier(raw.get('id')), 'title': title, 'date': iso_date(raw.get('date')),
            'intro': text(raw.get('intro')), 'editor': text(raw.get('editor'), 200), 'items': items}


def normalize_scores(raw, varieties):
    known = {r['id'] for r in varieties}
    result = []
    for row in rows(raw, 'Flavor records'):
        vid = identifier(row.get('variety_id'))
        if vid not in known:
            raise ValueError(f'Flavor variety {vid} is absent from this directory. Include it before exporting; existing flavor records were not changed.')
        match = re.fullmatch(r'(?:panel[ _-]?)?([1-4])', text(row.get('panel') or row.get('panel_id'), 100), re.I)
        if not match:
            raise ValueError('Every flavor record needs panel-1, panel-2, panel-3 or panel-4.')
        panel = 'panel-' + match[1]

        def number(value, label, optional=False):
            if value is None or value == '' or (isinstance(value, str) and not value.strip()):
                if optional:
                    return None
                raise ValueError(f'{label} is required.')
            if isinstance(value, bool) or not isinstance(value, (str, int, float)):
                raise ValueError(f'{label} must be a finite number.')
            try:
                n = float(value)
                if not math.isfinite(n):
                    raise ValueError
            except (TypeError, ValueError, OverflowError):
                raise ValueError(f'{label} must be a finite number.') from None
            # JSON integers and decimals remain numeric with no rounding.
            return int(n) if n.is_integer() else n

        low, high = number(row.get('scale_min', 1), 'Scale minimum'), number(row.get('scale_max', 9), 'Scale maximum')
        if not 0 <= low < high <= 100:
            raise ValueError('A sensory scale must have 0 <= minimum < maximum <= 100.')
        size = number(row.get('panel_size'), 'Panel size', optional=True)
        if size is not None and (int(size) != size or not 1 <= size <= 100000):
            raise ValueError('Panel size must be a positive whole number when supplied.')
        values = {}
        for key in METRICS:
            value = row.get(key, row.get('overall') if key == 'overall_liking' else None)
            values[key] = number(value, key, optional=key != 'overall_liking')
            if values[key] is not None and not low <= values[key] <= high:
                raise ValueError(f'{key} is outside its recorded sensory scale.')
        for key in ('brix', 'acidity'):
            values[key] = number(row.get(key, row.get('bricks') if key == 'brix' else None), key, optional=True)
            if values[key] is not None and (values[key] < 0 or (key == 'brix' and values[key] > 100)):
                raise ValueError(f'{key} has an invalid physical measurement.')
        stamp, sample = iso_date(row.get('date')), text(row.get('sample'), 250)
        generated = sha256(json.dumps([vid, panel, stamp, sample]).encode()).hexdigest()[:20]
        result.append({'id': identifier(row.get('id') or 'tasting-' + generated), 'variety_id': vid, 'panel': panel,
                       'date': stamp, 'sample': sample, 'panel_size': size, 'scale_min': low, 'scale_max': high,
                       **values, 'acidity_unit': text(row.get('acidity_unit'), 60), 'notes': text(row.get('notes'))})
    return unique(result, 'flavor record')


def empty_workspace():
    return {'schema_version': 1, 'kind': 'workspace',
            'directory': {'companies': [], 'varieties': [], 'exported_at': '', 'title': 'Company and variety directory'},
            'scores': [], 'issues': [], 'demo': {'directory': False, 'flavor': False, 'digest': False}, 'import_log': []}


def normalize_workspace(raw):
    from app.services import viewer_content, viewer_reports
    if not isinstance(raw, dict) or type(raw.get('schema_version')) is not int or raw.get('schema_version') != 1 or raw.get('kind') != 'workspace':
        raise ValueError('Upload an Export workspace JSON backup using schema version 1.')
    if not isinstance(raw.get('demo', {}), dict):
        raise ValueError('Workspace demo markers must be an object.')
    if any((raw.get('demo') or {}).values()):
        raise ValueError('This baseline contains fictional demonstration data. Use a real viewer backup, or explicitly start a new site.')
    directory = normalize_directory(raw.get('directory'))
    return {**empty_workspace(), 'directory': directory,
            'scores': normalize_scores(raw.get('scores'), directory['varieties']),
            'issues': unique([normalize_issue(r) for r in rows(raw.get('issues'), 'Newsletter editions')], 'edition'),
            'activity': viewer_content.normalize_activity(raw.get('activity', [])),
            'assets': viewer_content.normalize_assets(raw.get('assets', [])),
            'asset_omissions': viewer_content.normalize_omissions(raw.get('asset_omissions', [])),
            'changes': viewer_content.normalize_changes(raw.get('changes')),
            'as_of': iso_date(raw['as_of']) if raw.get('as_of') else '',
            'reports': viewer_reports.normalize_reports(raw.get('reports', []))}


def parse_json(data):
    if len(data) > MAX_FILE:
        raise ValueError('Each uploaded file must be no larger than 10 MB.')
    try:
        return json.loads(data.decode('utf-8-sig'), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (UnicodeError, ValueError, RecursionError):
        raise ValueError('The uploaded file is not valid UTF-8 JSON.') from None


def parse_flavor(data, filename, varieties):
    if len(data) > MAX_FILE:
        raise ValueError('Each uploaded file must be no larger than 10 MB.')
    if filename.lower().endswith('.csv'):
        try:
            reader = csv.DictReader(StringIO(data.decode('utf-8-sig')), strict=True)
            if not reader.fieldnames:
                raise ValueError('Flavor CSV needs a header row.')
            headers = [re.sub(r'\s+', '_', h.strip().lower()) for h in reader.fieldnames]
            if len(headers) != len(set(headers)) or any(not h for h in headers):
                raise ValueError('CSV column names must be unique and nonempty.')
            reader.fieldnames = headers
            data_rows = []
            for row in reader:
                if None in row or any(v is None for v in row.values()):
                    raise ValueError('CSV rows must have the same number of columns as the header.')
                data_rows.append(row)
                if len(data_rows) > MAX_ROWS:
                    raise ValueError('Too many flavor records.')
        except (UnicodeError, csv.Error):
            raise ValueError('The flavor CSV could not be read. Check UTF-8 encoding and quoted fields.') from None
    else:
        raw = parse_json(data)
        if not isinstance(raw, dict) or raw.get('kind') != 'flavor' or raw.get('schema_version') != 1:
            raise ValueError('Use a flavor CSV or a version 1 flavor JSON package.')
        data_rows = raw.get('scores')
    return normalize_scores(data_rows, varieties)


def directory_from_catalog(companies, entities, relationships, berry='', evidence=()):
    """Reuse resolved company rows and the existing one-pass Variety role index."""
    from app.services.variety_workspace import build_variety_indexes
    from app.services.variety_catalog import visible

    entity_map = {r['id']: r for r in entities}
    varieties = [r for r in entities if r.get('entity_type') == 'variety' and visible(r)
                 and (not berry or berry in r.get('berry_ids', []))]
    # Absent berry scope stays explicit instead of inventing it from a name.
    unresolved = [r['name'] for r in varieties if len(r.get('berry_ids') or []) != 1]
    if unresolved:
        raise ValueError('Resolve missing or ambiguous berry scope before exporting varieties: ' + ', '.join(unresolved[:8]))
    valid_relationships = [r for r in relationships if r.get('status') == 'active']
    indexes = build_variety_indexes(varieties=varieties, entities=entities, relationships=valid_relationships,
                                    published_evidence=[r for r in evidence if r.get('status') == 'published'],
                                    inbox_drafts=[r for r in evidence if r.get('status') != 'published'])

    def geography_names(values):
        return sorted({entity_map.get(v, {}).get('name', v) for v in values if isinstance(v, str) and v}) if isinstance(values, (list, set, tuple)) else []

    company_activity = {}
    for rel in valid_relationships:
        target = entity_map.get(rel.get('object_id')) or {}
        if rel.get('predicate') == 'operates_in' and target.get('entity_type') == 'geography':
            company_activity.setdefault(rel.get('subject_id'), []).append(target['id'])
    all_company_ids = {r['id'] for r in companies}
    cids = {r['id'] for r in companies if not berry or berry in r.get('berry_ids', [])}
    linked = {}
    for v in varieties:
        attrs = v.get('attributes') or {}
        connections = [r.get('entity_id') for r in attrs.get('catalog_connections', []) if isinstance(r, dict)]
        connections += [c for values in indexes['roles'].get(v['id'], {}).values() for c in values]
        linked[v['id']] = sorted({c for c in connections if c in all_company_ids})
        cids.update(linked[v['id']])
    output_companies = []
    for r in companies:
        if r['id'] not in cids:
            continue
        attrs = r.get('attributes') or {}
        country = attrs.get('headquarters_country') or attrs.get('headquarters_geography_id') or attrs.get('country') or r.get('country') or ''
        country = entity_map.get(country, {}).get('name', country) if isinstance(country, str) else ''
        output_companies.append({'id': r['id'], 'name': r['name'], 'aliases': r.get('aliases', []),
                                 'country': country, 'roles': r.get('roles', []), 'berries': r.get('berry_ids', []),
                                 'activity_geographies': geography_names(company_activity.get(r['id'], []) + strings(attrs.get('operating_geography_ids')) + strings(attrs.get('activity_geographies'))),
                                 'description': r.get('description', ''), 'tags': ['Identity ' + r.get('status', 'unverified')],
                                 'website': r.get('website', ''),
                                 'socials': (r.get('socials') or []) + ([{'platform': 'linkedin', 'url': r['linkedin']}] if r.get('linkedin') else [])})
    output_varieties = []
    for v in varieties:
        attrs = v.get('attributes') or {}
        # No trait conclusions are derived from prose, candidate claims or scores.
        traits = [entity_map[t]['name'] for t in attrs.get('trait_ids', []) if t in entity_map and entity_map[t].get('entity_type') == 'trait']
        output_varieties.append({'id': v['id'], 'name': v['name'], 'aliases': v.get('aliases', []),
                                 'berry': v['berry_ids'][0], 'company_ids': linked[v['id']],
                                 'activity_geographies': geography_names(set(indexes['observations'][v['id']]['countries']) | set(strings(attrs.get('activity_geographies')))),
                                 'description': v.get('description', ''), 'traits': traits,
                                 'tags': ['Identity ' + v.get('status', 'unverified')]})
    return normalize_directory({'companies': sorted(output_companies, key=lambda r: r['name'].casefold()),
                                'varieties': sorted(output_varieties, key=lambda r: r['name'].casefold()),
                                'exported_at': now(), 'title': 'Company and variety directory'})


def exportable(card, record):
    return (not card.get('missing_source') and record.get('record_type', 'evidence') == 'evidence'
            and record.get('status') not in {'rejected', 'archived'}
            and record.get('review_state') not in {'rejected', 'archived'}
            and record.get('evidence_role') not in {'atomic_evidence', 'atomic_proposal'}
            and bool(card.get('source_url')))


def issue_from_selection(cards, records, selected, settings):
    selected = strings(selected)
    by_id = {c['id']: c for c in cards if exportable(c, records.get(c['id'], {}))}
    if set(selected) - set(by_id):
        raise ValueError('A selected story is outside your current Digest selection or is no longer exportable. Review the list again.')
    if not selected:
        raise ValueError('Select at least one story, or turn off Add newsletter edition.')
    output = []
    for key in selected:
        c = by_id[key]
        # Cards provide a bounded preview, never article/transcript bodies.
        company_ids = [r['id'] for r in c.get('entities', []) if r.get('entity_type') in {'company', 'brand', 'breeding_program'}]
        output.append({'id': key, 'title': c['headline'], 'summary': c.get('deck', ''),
                       'source': c.get('source_name', ''), 'source_url': c.get('source_url', ''),
                       'published_date': str(c.get('published_at') or '')[:10], 'category': 'Industry',
                       'berries': c.get('crops', []), 'company_ids': company_ids, 'tags': [], 'editor_note': '',
                       'status': ('Source reviewed' if c.get('trusted') or c.get('source_reviewed') else 'Source not reviewed')
                                 + (' · AI-assisted summary' if c.get('ai_untrusted') else '')})
    return normalize_issue({'id': settings['issue_id'], 'title': settings['title'], 'date': settings['date'],
                            'intro': settings.get('intro', ''), 'editor': settings.get('editor', ''), 'items': output})


def assemble_workspace(directory, baseline=None, issue=None, scores=None):
    baseline = normalize_workspace(baseline) if baseline is not None else empty_workspace()
    directory = normalize_directory(directory)
    retained = normalize_scores(baseline['scores'], directory['varieties'])
    merged = {r['id']: r for r in retained}
    for row in normalize_scores(scores or [], directory['varieties']):
        old = merged.get(row['id'])
        if old and (old['panel'], old['variety_id']) != (row['panel'], row['variety_id']):
            raise ValueError(f'Flavor ID {row["id"]} belongs to another panel or variety. Use a distinct ID.')
        merged[row['id']] = row
    editions = {r['id']: r for r in baseline['issues']}
    if issue:
        issue = normalize_issue(issue)
        editions[issue['id']] = issue
    return {**empty_workspace(), 'directory': directory, 'scores': list(merged.values()), 'issues': list(editions.values())}


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def release_id(workspace):
    return sha256(json_bytes(workspace)).hexdigest()[:16]


def counts(workspace):
    return {'companies': len(workspace['directory']['companies']), 'varieties': len(workspace['directory']['varieties']),
            'editions': len(workspace['issues']), 'flavor_records': len(workspace['scores']),
            'panels': {p: sum(r['panel'] == p for r in workspace['scores']) for p in PANELS},
            'activity': len(workspace.get('activity', [])), 'assets': len(workspace.get('assets', [])),
            'asset_omissions': len(workspace.get('asset_omissions', [])), 'reports': len(workspace.get('reports', []))}


def standalone_html(workspace):
    """Compatibility entry point: index HTML for the generated multi-page site."""
    from app.viewer_assets.static_site import build_site
    return build_site(normalize_workspace(workspace))['index.html']


def build_release(workspace, *, created_at=None, issue=None, json_only=False):
    workspace = normalize_workspace(workspace)
    if workspace['scores']:
        raise ValueError('Research exports cannot contain corporate flavor records. Keep the supplement corporate.')
    created_at = created_at or now()
    files = {'content/workspace.json': json_bytes(workspace),
             'content/directory.json': json_bytes({'schema_version': 1, 'kind': 'directory', **workspace['directory']}),
             'content/flavor.json': json_bytes({'schema_version': 1, 'kind': 'flavor', 'scores': workspace['scores']})}
    if issue:
        issue = normalize_issue(issue)
        files['content/digest.json'] = json_bytes({'schema_version': 1, 'kind': 'digest', 'issue': issue})
    if not json_only:
        from app.viewer_assets.static_site import build_site
        files.update({'site/' + name: body for name, body in build_site(workspace).items()})
    files['DATA-FORMATS.md'] = (ASSETS / 'DATA-FORMATS.md').read_bytes()
    files['content/activity.json'] = json_bytes({'schema_version': 1, 'kind': 'activity', 'items': workspace.get('activity', [])})
    files['content/research.json'] = json_bytes({**workspace, 'kind': 'research'})
    files['content/assets.json'] = json_bytes({'schema_version': 1, 'kind': 'assets', 'items': workspace.get('assets', []), 'omissions': workspace.get('asset_omissions', [])})
    files['changes.json'] = json_bytes(workspace.get('changes', {}))
    files['asset-omissions.json'] = json_bytes(workspace.get('asset_omissions', []))
    for asset in workspace.get('assets', []):
        files['site/' + asset['path']] = base64.b64decode(asset['data_url'].split(',', 1)[1])
    changes = workspace.get('changes', {})
    files['CHANGELOG.md'] = ('# Changes in this research snapshot\n\nComparison: ' + str(changes.get('basis', 'first_release')) +
        ' / ' + str(changes.get('baseline_id') or 'none') + '\n\n' + '\n'.join('- ' + r['change'] + ' | ' + r['container'] + ' | ' + r['title'].replace('\n', ' ') + (' | fields: ' + ', '.join(r['fields']) if r['fields'] else '') for r in changes.get('items', [])) +
        '\n\nNo longer exported does not assert a job closed or a company stopped activity. See asset-omissions.json for unavailable files.\n').encode()
    files['START-HERE.md'] = b'''# HTML-only weekly site

Publish the entire site/ folder, preserving filenames and assets. Open site/index.html. Every page uses inline CSS, no JavaScript and no API calls. Directory tier/berry/geography/alphabet/sort controls use native HTML and CSS. Text search uses the browser Find command.

Corporate tiers, projects and flavor stay in separate corporate-side inputs. Do not upload them to the research platform or replace them in a weekly update. Keep a rollback copy. To rebuild with corporate settings:

python publisher/static_site.py --workspace content/workspace.json --corporate corporate-site.json --flavor corporate-flavor.json --output staged-site

Omit --flavor when absent. corporate-site.example.json documents company tiers and HTML project pages. Preserve the authoritative corporate files outside staged-site. HTML task checkboxes are temporary marks; save shared status in corporate-site.json and regenerate/re-publish. No browser editing or file upload is offered.

Reports are opt-in selections from the platform export dialog. Review the prose and draft/review labels before sharing. Deselecting a report removes it from the next release. Report HTML is passive and downloads are packaged locally.

Review changes.json, CHANGELOG.md and asset-omissions.json. Confirm the actual SharePoint folder/page publishing route and test CSS filter support, relative page links, assets and downloads. If CSS relational selectors are unsupported, all records remain visible and page links still work. Confirm publication in the platform only after the corporate site is verified.

Research snapshots contain no corporate tiers, project information or flavor scores. Source links are deliberate outbound navigation; employee interactions never call the research platform.
'''
    files['COPILOT-HANDOFF.md'] = b'''# Corporate publishing instructions

Use only HTML with inline CSS and local assets. No script tags, external stylesheets, API calls, analytics, or browser storage. Keep the complete site folder structure. Read START-HERE.md and verify manifest.json. Do not reconstruct the site weekly.

Keep corporate-site.json and corporate-flavor.json outside the research update boundary. Company tier values are tier-1, tier-2, tier-3 or unassigned. Variety filters match any associated company's tier; they do not assign an independent variety rating. Projects are maintained in corporate settings and rendered as HTML pages. Use native details/checkboxes for temporary interaction; shared saved changes require updating source settings and publishing.

Use the bundled Python publisher to merge the incoming research snapshot with the corporate inputs. It refuses unknown company or flavor-variety IDs instead of silently discarding records. Resolve those mappings before publication. Never send corporate settings or scores to the research platform.

Selected reports are included in this full snapshot; deselected reports disappear from the next release. Preserve the prior release for rollback. Test the real SharePoint route with JavaScript disabled, tier/berry/geography filters on company and variety lists, profile links, newsletter, Projects and Reports. Publish with the existing company process.
'''
    files['content/reports.json'] = json_bytes({'schema_version': 1, 'kind': 'reports', 'reports': workspace.get('reports', [])})
    files['publisher/static_site.py'] = (ASSETS / 'static_site.py').read_bytes()
    files['publisher/driscolls-logo.png'] = (ASSETS / 'driscolls-logo.png').read_bytes()
    files['corporate-site.example.json'] = json_bytes({'schema_version': 1, 'kind': 'corporate_site', 'tiers': {}, 'projects': []})
    catalog_csv = StringIO()
    writer = csv.writer(catalog_csv)
    writer.writerow(['company_id', 'company_name'])
    writer.writerows((r['id'], r['name']) for r in workspace['directory']['companies'])
    files['corporate-company-ids.csv'] = catalog_csv.getvalue().encode('utf-8-sig')
    files['PROJECTS-AND-TIERS.md'] = b'''# Corporate-only settings

Keep corporate-site.json on corporate systems. Start with corporate-site.example.json only for the first publication; never overwrite existing settings during a research update. corporate-company-ids.csv maps names to stable company IDs. Tier values are tier-1, tier-2, tier-3 and unassigned. Varieties match the tiers of their associated companies.

Example structure (replace COMPANY_ID with a real ID):

```json
{"schema_version":1,"kind":"corporate_site","tiers":{"COMPANY_ID":"tier-1"},"projects":[{"id":"project-example","title":"Project title","status":"Planning","owner":"Corporate owner","summary":"Project purpose","tasks":[{"title":"First milestone","owner":"Task owner","due":"2026-12-15","done":false}],"html":"<details><summary>Working notes</summary><p>Project content.</p></details>"}]}
```

A project may use html_file instead of an inline html value. It must identify a .html file within the corporate settings folder. The publisher strips active scripts/embeds, remote images and global style blocks; safe inline element styles and native details/checkboxes remain. Shared project updates require editing source settings/HTML and publishing; browser checkbox changes are temporary.

Build into a new empty staging folder. Publish the complete new tree and retire files absent from the new manifest so deselected reports do not linger. Preserve the previous release separately for rollback under normal corporate access controls.
'''
    manifest = {'package_version': 3, 'viewer_version': '2.0.0', 'schema_version': 1,
                'release_id': release_id(workspace), 'created_at': created_at, 'counts': counts(workspace),
                'edition_ids': [r['id'] for r in workspace['issues']], 'format': 'json' if json_only else 'site',
                'delivery': 'html_inline_css_no_javascript', 'corporate_inputs': ['tiers', 'projects', 'flavor'], 'flavor_boundary': 'corporate_only', 'default_activity_days': 90,
                'comparison': workspace.get('changes', {}),
                'files': {name: sha256(body).hexdigest() for name, body in files.items()}}
    files['manifest.json'] = json_bytes(manifest)
    output = BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for name, body in files.items():
            archive.writestr(name, body)
    return output.getvalue(), manifest


def _folder(inbox_dir):
    key = personal_scope.account_key() or 'local-operator'
    if not re.fullmatch(r'account-[0-9a-f]{64}|local-operator', key):
        raise ValueError('Export account scope is unavailable.')
    return Path(inbox_dir) / 'viewer_exports' / key


def _read(path):
    if not path.exists():
        return None
    try:
        if path.stat().st_size > MAX_FILE * 3 + 100000:
            raise ValueError('Stored export is too large.')
        value = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (OSError, ValueError, RecursionError):
        raise ValueError('Your saved export could not be read. Upload a known workspace backup; the existing file has not been overwritten.') from None


def load_latest(inbox_dir):
    value = _read(_folder(inbox_dir) / 'latest.json')
    if value:
        value['workspace'] = normalize_workspace(value.get('workspace'))
    return value


def load_published(inbox_dir):
    value = _read(_folder(inbox_dir) / 'published.json')
    if value:
        value['workspace'] = normalize_workspace(value['workspace'])
    return value


@serialized_write
def preview_file(inbox_dir, name):
    """Cache the account's generated research preview; serve only known outputs."""
    from pathlib import PurePosixPath
    from app.viewer_assets.static_site import build_site
    relative = PurePosixPath(name)
    if not name or relative.is_absolute() or '..' in relative.parts or '\\' in name or ':' in name:
        raise ValueError('Unknown viewer preview page.')
    latest = _read(_folder(inbox_dir) / 'latest.json')
    if not latest or not re.fullmatch(r'[a-f0-9]{16}', latest.get('release_id', '')):
        raise ValueError('Generate a research release before opening its preview.')
    root = _folder(inbox_dir) / 'preview-site' / latest['release_id']
    marker = root / 'files.json'
    source_sha = sha256((ASSETS / 'static_site.py').read_bytes() + (ASSETS / 'driscolls-logo.png').read_bytes()).hexdigest()
    cached = json.loads(marker.read_text(encoding='utf-8')) if marker.is_file() else {}
    if cached.get('source_sha') != source_sha:
        files = build_site(normalize_workspace(latest['workspace']))
        for filename, body in files.items():
            target = root / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
        atomic_json(marker, {'files': list(files), 'source_sha': source_sha})
    names = json.loads(marker.read_text(encoding='utf-8'))['files']
    if name not in names:
        raise ValueError('Unknown viewer preview page.')
    return root / name


@serialized_write
def confirm_published(inbox_dir, rid):
    latest = load_latest(inbox_dir)
    if not latest or latest['release_id'] != rid:
        raise ExportConflict('Only your latest generated release can be confirmed. Generate it again if needed.')
    latest['confirmed_at'] = now()
    atomic_json(_folder(inbox_dir) / 'published.json', latest)
    return latest


def revision(latest):
    return sha256(json_bytes(latest)).hexdigest() if latest else ''


@serialized_write
def prepare(inbox_dir, workspace, settings, *, expected_revision, issue=None):
    latest = load_latest(inbox_dir)
    if revision(latest) != expected_revision:
        raise ExportConflict('A newer export was generated in another window. Reopen Export to viewer and review its baseline.')
    workspace = normalize_workspace(workspace)
    if workspace['scores']:
        raise ValueError('Flavor data must stay in the corporate supplement, outside platform exports.')
    if len(json_bytes(workspace)) > MAX_FILE:
        raise ValueError('This workspace is larger than the viewer limit of 10 MB. Reduce the content scope before exporting.')
    preview = {'token': secrets.token_urlsafe(32), 'created_at': now(), 'expected_revision': expected_revision,
               'workspace': workspace, 'settings': settings, 'issue': normalize_issue(issue) if issue else None}
    atomic_json(_folder(inbox_dir) / 'preview.json', preview)
    return preview


def load_preview(inbox_dir, token):
    preview = _read(_folder(inbox_dir) / 'preview.json')
    if not preview or not isinstance(token, str) or not secrets.compare_digest(str(preview.get('token', '')).encode(), token.encode()):
        raise ExportConflict('This preview is unavailable for your account. Open Export to viewer and prepare it again.')
    if datetime.fromisoformat(preview['created_at']) < datetime.now(UTC) - timedelta(hours=2):
        raise ExportConflict('This export preview expired. Review the current content before downloading.')
    preview['workspace'] = normalize_workspace(preview['workspace'])
    return preview


@serialized_write
def download_prepared(inbox_dir, token):
    preview = load_preview(inbox_dir, token)
    latest = load_latest(inbox_dir)
    rid = release_id(preview['workspace'])
    if revision(latest) != preview['expected_revision'] and (not latest or latest.get('preview_token') != token):
        raise ExportConflict('The previous export changed after this preview. Reopen the dialog to preserve the newer baseline.')
    bundle, manifest = build_release(preview['workspace'], created_at=preview['created_at'], issue=preview['issue'],
                                     json_only=preview['settings'].get('format') == 'json')
    saved = {'workspace': preview['workspace'], 'settings': preview['settings'], 'created_at': preview['created_at'], 'issue': preview['issue'],
             'release_id': rid, 'preview_token': token}
    atomic_json(_folder(inbox_dir) / 'latest.json', saved)
    return bundle, manifest
