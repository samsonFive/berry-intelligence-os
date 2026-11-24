"""Generate an HTML/CSS-only corporate site. Standard library; no browser scripts.

Corporate tiers, projects and flavor are local build inputs, never platform data.
"""
import argparse
import base64
from datetime import date, timedelta
from hashlib import sha256
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


def e(value):
    return escape(str(value if value is not None else ''), quote=True)


def filename(kind, key):
    return kind + '-' + sha256(str(key).encode()).hexdigest()[:20] + '.html'


def safe_url(value):
    try:
        p = urlsplit(value)
        if p.scheme in {'http', 'https'} and p.hostname and not p.username and not p.password and not any(ord(c) < 33 for c in value):
            return value
        if re.fullmatch(r'#[A-Za-z0-9_-]+', value):
            return value
    except (ValueError, TypeError):
        pass
    return ''


class CleanHTML(HTMLParser):
    """Keep passive report/project HTML; never copy active or remote content."""
    allowed = set('article section header footer main nav div span p h1 h2 h3 h4 h5 h6 ul ol li dl dt dd table thead tbody tfoot tr th td caption colgroup col a strong b em i small blockquote pre code br hr details summary label input progress time figure figcaption img style'.split())
    void = {'br', 'hr', 'col', 'input', 'img'}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output, self.skip, self.css = [], [], None
    def handle_starttag(self, tag, attrs):
        if self.skip:
            if tag not in self.void:
                self.skip.append(tag)
            return
        if tag in {'script', 'iframe', 'object', 'embed', 'svg', 'math', 'template'}:
            self.skip.append(tag)
            return
        if tag == 'style':
            self.css = []
            return
        if tag not in self.allowed:
            return
        attrs = dict(attrs)
        kept = []
        for key in ('class', 'id', 'title', 'colspan', 'rowspan', 'scope', 'open', 'checked', 'disabled', 'max', 'value', 'datetime'):
            if key in attrs:
                kept.append((key, attrs[key] or ''))
        if tag == 'a' and safe_url(attrs.get('href')):
            kept += [('href', safe_url(attrs['href'])), ('rel', 'noopener noreferrer'), ('referrerpolicy', 'no-referrer')]
        if tag == 'input':
            kept = [(k, v) for k, v in kept if k not in {'value'}]
            kept.append(('type', 'checkbox'))
        if tag == 'img':
            src = attrs.get('src') or ''
            if not re.fullmatch(r'data:image/(?:png|jpeg|gif|webp);base64,[A-Za-z0-9+/=]+', src):
                return
            kept += [('src', src), ('alt', attrs.get('alt') or '')]
        inline = attrs.get('style') or ''
        if inline and not re.search(r'url\s*\(|@import|expression|javascript|\\|[<>]', inline, re.I):
            kept.append(('style', inline))
        self.output.append('<' + tag + ''.join(' ' + k + '="' + e(v) + '"' for k, v in kept) + '>')
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.void:
            self.handle_endtag(tag)
    def handle_endtag(self, tag):
        if self.skip:
            if tag == self.skip[-1]:
                self.skip.pop()
            return
        if tag == 'style' and self.css is not None:
            css = ''.join(self.css)
            # Imported style blocks are omitted to keep report/project CSS from changing site chrome.
            # Safe per-element styles are retained; the site supplies shared table/type styling.
            self.css = None
        elif tag in self.allowed and tag not in self.void:
            self.output.append('</' + tag + '>')
    def handle_data(self, data):
        if self.skip:
            return
        if self.css is not None:
            self.css.append(data)
        else:
            self.output.append(e(data))


def clean_html(value):
    parser = CleanHTML()
    parser.feed(str(value or ''))
    parser.close()
    return ''.join(parser.output)


CSS = '''
*{box-sizing:border-box}body{margin:0;font:14px/1.45 "Segoe UI",Arial,sans-serif;color:#26362b;background:#f5f6f4}a{color:#38652f;text-underline-offset:3px}button,input{font:inherit}aside{position:fixed;inset:0 auto 0 0;width:210px;padding:0 14px 20px;background:#294b30;color:white;display:flex;flex-direction:column}aside img{width:172px;height:auto;margin:0 auto 16px}aside strong{font-size:16px;margin:0 7px 24px}aside a{color:#dce8d5;text-decoration:none;display:block;padding:10px 12px;border-radius:9px;margin-bottom:5px}aside a.active{background:#ffffff16;border-left:3px solid #f5d746;color:white}aside small{margin-top:auto;color:#bfd0b8;padding:12px 7px}.shell{margin-left:210px}header.top{height:45px;padding:12px 22px;border-top:3px solid #f5d746;background:white;color:#69746c;font-size:12px}main{padding:16px 22px 32px;max-width:1800px}h1{font-size:27px;font-weight:600;letter-spacing:-.5px;margin:0 0 4px}h2{font-size:20px;margin:0 0 10px}h3{font-size:16px;margin:0 0 8px}p{margin:6px 0 12px}.muted,small{color:#69746c}.intro{margin-bottom:14px}.summary{display:flex;gap:20px;font-size:13px;margin:10px 0 13px}.panel{background:white;border:1px solid #d6ded3;border-radius:12px;overflow:hidden;margin:12px 0}.section{padding:16px 18px}.tabs{display:flex;gap:7px;align-items:center;padding:9px 12px;background:#edf2e9;flex-wrap:wrap}.tabs a,.button{display:inline-block;border:1px solid #d6ded3;padding:6px 11px;background:white;border-radius:8px;text-decoration:none}.tabs .active{color:white;background:#4a773c}.controls{padding:9px 12px;border-bottom:1px solid #d6ded3}.control-group{display:flex;gap:5px;align-items:center;flex-wrap:wrap;margin:5px 0}.control-group>b{font-size:12px;margin-right:6px;min-width:72px}.choice{display:inline-flex;align-items:center;gap:4px;border:1px solid #dbe2d7;border-radius:7px;padding:4px 8px;font-size:12px;cursor:pointer}.choice input{accent-color:#4a773c;margin:0;width:12px;height:12px}.choice:has(input:checked){background:#edf4e5;border-color:#6e955d;color:#294b30}.alphabet .choice{padding:3px 5px}.alphabet input{position:absolute;opacity:0;width:1px;height:1px}.choice:has(input:focus-visible){outline:3px solid #7f3d66}.scroll{overflow:auto;max-height:calc(100vh - 380px);min-height:240px}.directory-table{border-collapse:separate;border-spacing:0;width:100%;min-width:990px;table-layout:fixed}.directory-table th,.directory-table td{padding:7px 10px;border-right:1px solid #dce3d7;border-bottom:1px solid #dce3d7;text-align:left;vertical-align:middle;overflow-wrap:anywhere}.directory-table th{position:sticky;top:0;background:#edf2e8;z-index:2;font-weight:600;font-size:13px}.directory-table th:first-child,.directory-table td:first-child{position:sticky;left:0;width:260px;background:white;z-index:1;border-right:2px solid #c7d3c0}.directory-table th:first-child{z-index:3;background:#edf2e8}.directory-table tbody tr:nth-child(even) td{background:#fafcf8}.directory-table tbody tr:hover td{background:#f0f5ea}.identity{display:flex;gap:9px;align-items:center}.identity a{font-weight:600;text-decoration:none}.logo{width:30px;height:30px;object-fit:contain;border:1px solid #e1e6dc;background:white;border-radius:7px;padding:2px}.mark{width:28px;height:28px;flex:0 0 28px;text-align:center;padding-top:6px;font-size:10px;border-radius:7px;background:#eef4e8;color:#547548}.badge{display:inline-block;padding:2px 6px;background:#eef4e9;border-radius:5px;font-size:11px;margin:1px 3px 1px 0}.berry-blueberry{background:#edf0f9;color:#526396}.berry-strawberry{background:#fbefec;color:#a35f55}.berry-raspberry{background:#f7eaf2;color:#925e7f}.berry-blackberry{background:#eeeaf5;color:#68527e}.grid-note{padding:8px 12px;font-size:12px;color:#69746c}.profile-head .logo{width:70px;height:56px}.profile-head .identity{margin-bottom:12px}.card-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:11px}.card{padding:14px;border:1px solid #d9e1d5;border-radius:10px;background:white}.card h3{margin-bottom:6px}.card img{max-width:100%;height:120px;object-fit:contain}.activity{padding:12px 0;border-bottom:1px solid #e0e6dc}.activity p{max-width:1100px}.activity small{display:block}.activity details{margin:5px 0}.source{font-size:12px}.task{display:flex;align-items:flex-start;gap:8px;padding:9px 0;border-bottom:1px solid #e1e6dd}.task input{accent-color:#4a773c;margin-top:4px}.task:has(input:checked) span{text-decoration:line-through;color:#69746c}details{border-radius:8px}summary{cursor:pointer;font-weight:600;padding:7px 0}.columns{display:grid;grid-template-columns:2fr 1fr;gap:14px}.banner{border:1px solid #e8dc9e;background:#fffbed;border-radius:8px;padding:9px 12px;margin:10px 0}.report-body{padding:20px;background:white;border-radius:12px;border:1px solid #d6ded3;overflow-wrap:anywhere}.report-body img{max-width:100%}.report-body table{border-collapse:collapse;width:100%}.report-body th,.report-body td{border:1px solid #d6ded3;padding:7px}.report-body pre{white-space:pre-wrap}.descending{display:none}main:has(#sort-desc:checked) .ascending{display:none}main:has(#sort-desc:checked) .descending{display:table}main:has(#activity-recent:checked) .activity[data-recent="0"]{display:none}@media(max-width:800px){aside{position:static;width:auto;display:block;padding:0 12px 8px}aside img{width:145px;margin:0}aside strong{display:inline-block;font-size:14px;margin:0 12px}aside nav{display:flex;flex-wrap:wrap}aside nav a{padding:7px 10px;margin:0}aside small{display:none}.shell{margin-left:0}main{padding:12px}.columns{grid-template-columns:1fr}.control-group>b{min-width:60px}}@media print{aside,.top,.controls,.tabs,.grid-note{display:none}.shell{margin:0}main{padding:0}.scroll{max-height:none;overflow:visible}.directory-table{min-width:0;font-size:10px}.directory-table th,.directory-table td{position:static;padding:5px}.panel{overflow:visible}.descending{display:none!important}main:has(#sort-desc:checked) .ascending{display:table}.card-grid{display:block}.card{break-inside:avoid}.activity{display:block!important}}
'''


def corporate_model(raw, directory):
    raw = raw or {'schema_version': 1, 'kind': 'corporate_site', 'tiers': {}, 'projects': []}
    if raw.get('schema_version') != 1 or raw.get('kind') != 'corporate_site':
        raise ValueError('Corporate settings need schema_version 1 and kind corporate_site.')
    tiers = raw.get('tiers') or {}
    known = {c['id'] for c in directory['companies']}
    if not isinstance(tiers, dict) or set(tiers) - known or any(not isinstance(v, str) or v not in {'tier-1', 'tier-2', 'tier-3', 'unassigned'} for v in tiers.values()):
        raise ValueError('Corporate tiers must use known company IDs and tier-1, tier-2, tier-3 or unassigned. Resolve missing company IDs before publishing.')
    projects = raw.get('projects') or []
    if not isinstance(projects, list) or len(projects) > 1000:
        raise ValueError('Projects must be a list of at most 1000 records.')
    ids = set()
    for p in projects:
        if not isinstance(p, dict) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}', str(p.get('id') or '')) or p['id'] in ids or not p.get('title'):
            raise ValueError('Every project needs a unique stable ID and title.')
        ids.add(p['id'])
        if not isinstance(p.get('tasks', []), list):
            raise ValueError('Project tasks must be a list.')
    return {'schema_version': 1, 'kind': 'corporate_site', 'tiers': tiers, 'projects': projects}


def build_site(workspace, corporate=None, flavor=None):
    d = workspace['directory']
    corp = corporate_model(corporate, d)
    scores = (flavor or {}).get('scores', [])
    if flavor and (flavor.get('kind') != 'flavor' or flavor.get('schema_version') != 1):
        raise ValueError('Use a version 1 corporate flavor supplement.')
    varieties = {v['id']: v for v in d['varieties']}
    companies = {c['id']: c for c in d['companies']}
    for r in scores:
        if r.get('variety_id') not in varieties or r.get('panel') not in {'panel-1', 'panel-2', 'panel-3', 'panel-4'}:
            raise ValueError('Flavor records require a known variety and a distinct panel-1 through panel-4.')
    files = {}
    brand = 'assets/driscolls-logo.png'
    files[brand] = (Path(__file__).parent / 'driscolls-logo.png').read_bytes()
    tiers = corp['tiers']
    tier_label = lambda t: {'tier-1': 'Tier 1', 'tier-2': 'Tier 2', 'tier-3': 'Tier 3', 'unassigned': 'Unassigned'}[t]
    company_tier = lambda key: tiers.get(key, 'unassigned')
    row_tiers = lambda r, company: {company_tier(r['id'])} if company else {company_tier(c) for c in r.get('company_ids', [])} or {'unassigned'}
    asof = workspace.get('as_of') or date.today().isoformat()
    since = (date.fromisoformat(asof) - timedelta(days=89)).isoformat()
    assets = workspace.get('assets', [])
    asset_urls = {}
    for a in assets:
        if not re.fullmatch(r'assets/[a-f0-9]{64}\.(png|jpg|webp|gif|pdf)', a.get('path', '')):
            raise ValueError('Asset path is invalid.')
        body = base64.b64decode(a['data_url'].split(',', 1)[1], validate=True)
        if sha256(body).hexdigest() != a['sha256']:
            raise ValueError('Asset checksum mismatch.')
        files[a['path']] = body
        asset_urls[a['id']] = a['path']
    def badge(value, cls=''):
        return '<span class="badge ' + cls + '">' + e(value) + '</span>'
    def berries(values):
        return ''.join(badge(str(v).replace('berry-', '').title(), 'berry-' + str(v).replace('berry-', '')) for v in values)
    def logo(r):
        a = next((a for a in assets if a['kind'] == 'logo' and r['id'] in a['entity_ids']), None)
        return '<img class="logo" src="' + e(asset_urls[a['id']]) + '" alt="' + e(r['name']) + ' logo">' if a else '<span class="mark">' + e(''.join(w[0] for w in r['name'].split()[:2])) + '</span>'
    def page(title, content, active='directory', extra_css=''):
        nav = [('directory', 'index.html', 'Directory'), ('newsletter', 'newsletter.html', 'Newsletter'), ('projects', 'projects.html', 'Projects'), ('reports', 'reports.html', 'Reports')]
        if scores:
            nav.append(('flavor', 'flavor.html', 'Flavor records'))
        return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'none\'; style-src \'unsafe-inline\'; img-src \'self\' data:; connect-src \'none\'; object-src \'none\'; base-uri \'none\'; form-action \'none\'">'
                '<title>' + e(title) + ' — Driscoll’s Intelligence</title><style>' + CSS + extra_css + '</style></head><body><aside><img src="' + brand + '" alt="Driscoll’s"><strong>Competitive Intelligence</strong><nav>' + ''.join('<a href="' + href + '" class="' + ('active' if k == active else '') + '">' + name + '</a>' for k, href, name in nav) + '</nav><small>Research snapshot · ' + e(asof) + '<br>Internal company workspace.</small></aside><div class="shell"><header class="top">Company workspace / ' + e(title) + '</header><main>' + content + '</main></div></body></html>').encode()
    def choice(group, key, title, checked=False):
        return '<label class="choice"><input type="radio" name="' + group + '" id="' + key + '"' + (' checked' if checked else '') + '><span>' + e(title) + '</span></label>'
    def directory_page(company):
        records = d['companies' if company else 'varieties']
        def geos(r):
            hq = [r['country']] if company and r.get('country') else [companies[c]['country'] for c in r.get('company_ids', []) if companies[c].get('country')]
            return sorted(set(hq)), sorted(set(r.get('activity_geographies', [])))
        places = sorted({v for r in records for values in geos(r) for v in values})
        geo_key = {p: 'g' + sha256(p.encode()).hexdigest()[:12] for p in places}
        css = ''
        controls = '<div class="control-group"><b>Tier</b>' + choice('tier', 'tier-all', 'All tiers', True)
        for t in ['tier-1', 'tier-2', 'tier-3', 'unassigned']:
            controls += choice('tier', 'tier-' + t, tier_label(t))
            css += 'main:has(#tier-' + t + ':checked) .directory-table tbody tr:not([data-tiers~="' + t + '"]){display:none}'
        controls += '</div><div class="control-group"><b>Berry</b>' + choice('berry', 'berry-all', 'All berries', True)
        for b in ['blueberry', 'strawberry', 'raspberry', 'blackberry']:
            controls += choice('berry', 'berry-' + b, b.title())
            css += 'main:has(#berry-' + b + ':checked) .directory-table tbody tr:not([data-berries~="' + b + '"]){display:none}'
        controls += '</div><details><summary>Geography filters</summary><div class="control-group"><b>Match</b>' + choice('basis', 'geo-either', 'Either', True) + choice('basis', 'geo-hq', 'Headquarters' if company else 'Associated company HQ') + choice('basis', 'geo-activity', 'Documented activity') + '</div><div class="control-group">' + choice('place', 'place-all', 'All geographies', True)
        for p in places:
            key = geo_key[p]
            controls += choice('place', 'place-' + key, p)
            for basis, attr in [('either', 'either'), ('hq', 'hq'), ('activity', 'activity')]:
                css += 'main:has(#geo-' + basis + ':checked):has(#place-' + key + ':checked) .directory-table tbody tr:not([data-' + attr + '~="' + key + '"]){display:none}'
        controls += '</div><p class="muted">Headquarters and documented activity are distinct. A company’s headquarters does not establish a variety’s growing location.</p></details>'
        controls += '<div class="control-group alphabet"><b>Names</b>' + choice('letter', 'letter-all', 'All', True)
        import unicodedata
        initial = lambda name: (unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()[:1].upper() or '#')
        for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ#':
            controls += choice('letter', 'letter-' + ('other' if letter == '#' else letter), letter)
            css += 'main:has(#letter-' + ('other' if letter == '#' else letter) + ':checked) .directory-table tbody tr:not([data-letter="' + letter + '"]){display:none}'
        controls += '</div><div class="control-group"><b>Sort</b>' + choice('sort', 'sort-asc', 'Name A–Z', True) + choice('sort', 'sort-desc', 'Name Z–A') + '</div>'
        def table(desc):
            rows = ''
            for r in sorted(records, key=lambda r: r['name'].casefold(), reverse=desc):
                hq, activity = geos(r)
                ts = row_tiers(r, company)
                crop = r.get('berries', []) if company else [r['berry']]
                attrs = {'tiers': ts, 'berries': crop, 'hq': [geo_key[v] for v in hq], 'activity': [geo_key[v] for v in activity], 'either': [geo_key[v] for v in set(hq + activity)]}
                letter = initial(r['name'])
                letter = letter if letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' else '#'
                rows += '<tr data-letter="' + letter + '"' + ''.join(' data-' + k + '="' + e(' '.join(sorted(v))) + '"' for k, v in attrs.items()) + '><td><div class="identity">' + logo(r) + '<div><a href="' + filename('company' if company else 'variety', r['id']) + '">' + e(r['name']) + '</a><br><small>' + e(', '.join(r.get('aliases', [])[:2])) + '</small></div></div></td><td>' + ''.join(badge(tier_label(t)) for t in sorted(ts)) + '</td><td>' + (e(' · '.join(v.replace('_', ' ').title() for v in r.get('roles', []))) if company else '<br>'.join('<a href="' + filename('company', c) + '">' + e(companies[c]['name']) + '</a>' for c in r.get('company_ids', []))) + '</td><td>' + berries(crop) + '</td><td>' + ('<small>HQ </small>' + e(' · '.join(hq)) + '<br>' if hq else '') + ('<small>Activity </small>' + e(' · '.join(activity)) if activity else '') + ('<small>Not recorded</small>' if not hq and not activity else '') + '</td></tr>'
            return '<table class="directory-table ' + ('descending' if desc else 'ascending') + '"><thead><tr><th>' + ('Company' if company else 'Variety') + '</th><th>' + ('Corporate tier' if company else 'Associated company tiers') + '</th><th>' + ('Business roles' if company else 'Associated companies') + '</th><th>Berry</th><th>Geography</th></tr></thead><tbody>' + rows + '</tbody></table>'
        body = '<h1>Company & variety directory</h1><p class="muted intro">' + ('Browse companies and their recorded relationships.' if company else 'Variety tier filters match any associated company’s corporate tier; they do not assign an independent variety tier.') + '</p><div class="summary"><span><b>' + str(len(companies)) + '</b> companies</span><span><b>' + str(len(varieties)) + '</b> varieties</span><a href="changes.html">What changed</a></div><section class="panel"><div class="tabs"><a href="index.html" class="' + ('active' if company else '') + '">Companies</a><a href="varieties.html" class="' + ('' if company else 'active') + '">Varieties</a></div><div class="controls">' + controls + '</div><div class="scroll">' + table(False) + table(True) + '</div><div class="grid-note">Filters combine across tier, berry, geography and initial. Use your browser’s Find command for text search. Tiers reflect corporate assignments.</div></section>'
        return page('Directory', body, extra_css=css)
    files['index.html'] = directory_page(True)
    files['varieties.html'] = directory_page(False)
    def source_card(r):
        when = r.get('published_date') or r.get('captured_date') or ''
        recent = bool(when and since <= when <= asof)
        return '<article class="activity" data-recent="' + ('1' if recent else '0') + '"><small>' + e(r.get('category', '').title()) + ' · ' + e(r.get('status')) + (' · Confidence: ' + e(r.get('confidence')) if r.get('confidence') else '') + (' · Retained archive snapshot' if r.get('availability') == 'retained_archive' else '') + '</small><h3>' + e(r['title']) + '</h3><p>' + e(r.get('summary')) + '</p><p class="source">' + e(r.get('source')) + ' · Published: ' + e(r.get('published_date') or 'Not supplied') + ' · Captured: ' + e(r.get('captured_date') or 'Not supplied') + (' · Job status: ' + e(r['job_status']) if r.get('job_status') else '') + '</p>' + (('<p><a href="' + e(safe_url(r.get('source_url'))) + '" rel="noopener noreferrer" referrerpolicy="no-referrer">Open source</a></p>') if safe_url(r.get('source_url')) else '') + ('<details><summary>Source qualifications</summary><p>' + e(' · '.join(r.get('caveats', []))) + '</p></details>' if r.get('caveats') else '') + '</article>'
    for company, records in [(True, d['companies']), (False, d['varieties'])]:
        for r in records:
            related = [v for v in d['varieties'] if r['id'] in v.get('company_ids', [])] if company else [companies[c] for c in r.get('company_ids', [])]
            body = '<section class="panel section profile-head"><div class="identity">' + logo(r) + '<div><h1>' + e(r['name']) + '</h1>' + ''.join(badge(tier_label(t)) for t in sorted(row_tiers(r, company))) + '</div></div><p>' + e(r.get('description')) + '</p>' + berries(r.get('berries', []) if company else [r['berry']]) + '<p class="muted">' + e('Aliases: ' + ', '.join(r.get('aliases', []))) + '</p></section><section class="panel section"><h2>' + ('Variety portfolio' if company else 'Associated companies') + '</h2><div class="card-grid">' + ''.join('<a class="card" href="' + filename('variety' if company else 'company', v['id']) + '">' + e(v['name']) + '<br>' + ''.join(badge(tier_label(t)) for t in sorted(row_tiers(v, not company))) + '</a>' for v in related) + '</div></section>'
            if company:
                links = ([{'platform': 'Website', 'url': r['website']}] if r.get('website') else []) + r.get('socials', [])
                body += '<section class="panel section"><h2>Website & social channels</h2>' + ' '.join('<a class="button" href="' + e(safe_url(v['url'])) + '" rel="noopener noreferrer" referrerpolicy="no-referrer">' + e(v['platform'].title()) + '</a>' for v in links if safe_url(v['url'])) + '</section>'
            hq = [r['country']] if company and r.get('country') else [companies[c]['country'] for c in r.get('company_ids', []) if companies[c].get('country')]
            body += '<section class="panel section"><h2>Geography</h2><p>' + ('Headquarters: ' if company else 'Associated company headquarters: ') + e(' · '.join(sorted(set(hq))) or 'Not recorded') + '<br>Documented activity: ' + e(' · '.join(r.get('activity_geographies', [])) or 'Not recorded') + '</p>' + ('' if company else '<p class="muted">Company headquarters does not establish a variety’s growing footprint.</p>') + '</section>'
            activity = [a for a in workspace.get('activity', []) if r['id'] in a['company_ids' if company else 'variety_ids']]
            body += '<section class="panel section"><h2>Public-source activity</h2><p class="muted">Independent of newsletter selections. Latest 90 days ends ' + e(asof) + '. The full archive includes older and undated records. Use browser Find for text search.</p><div class="control-group">' + choice('history', 'activity-recent', 'Latest 90 days', True) + choice('history', 'activity-all', 'Full archive') + '</div>'
            for cat, title in [('news', 'News'), ('social', 'Social posts'), ('jobs', 'Job listings'), ('communications', 'Public communications'), ('other', 'Other source records')]:
                values = [a for a in activity if a['category'] == cat]
                body += '<details open><summary>' + title + ' · ' + str(len(values)) + ' retained</summary>' + ''.join(source_card(a) for a in values) + ('<p class="muted">No records exported in this category.</p>' if not values else '') + '</details>'
            body += '<p class="muted">A blank recent view does not mean the company has no activity. Open Full archive to see all retained records. A captured job is not proof of a current vacancy.</p></section>'
            attached = [a for a in assets if r['id'] in a['entity_ids']]
            body += '<section class="panel section"><h2>Images & supporting documents</h2><div class="card-grid">' + ''.join('<article class="card">' + ('<img src="' + e(asset_urls[a['id']]) + '" alt="' + e(a['title']) + '">' if a['mime'].startswith('image/') else '<p>PDF document</p>') + '<h3>' + e(a['title']) + '</h3><small>' + e(a.get('attribution')) + '</small><p><a href="' + e(asset_urls[a['id']]) + '">Open file</a></p></article>' for a in attached) + '</div>' + ('<p class="muted">No file attachments in this snapshot.</p>' if not attached else '') + '</section>'
            files[filename('company' if company else 'variety', r['id'])] = page(r['name'], body)
    editions = workspace.get('issues', [])
    body = '<h1>Newsletter</h1><p class="muted">Curated editions from the Personal Digest.</p>'
    for edition in sorted(editions, key=lambda i: i['date'], reverse=True):
        body += '<section class="panel section"><h2>' + e(edition['title']) + '</h2><p class="muted">' + e(edition['date']) + ' · ' + e(edition.get('editor')) + '</p><p>' + e(edition.get('intro')) + '</p>' + ''.join(source_card({**a, 'captured_date': '', 'category': a.get('category') or 'Newsletter'}) for a in edition['items']) + '</section>'
    files['newsletter.html'] = page('Newsletter', body + ('<section class="panel section">No newsletter edition selected for this release.</section>' if not editions else ''), 'newsletter')
    reports = workspace.get('reports', [])
    body = '<h1>Reports</h1><p class="muted">Reports explicitly selected for internal distribution.</p><div class="card-grid">'
    for r in reports:
        body += '<article class="card"><h2><a href="' + filename('report', r['id']) + '">' + e(r['title']) + '</a></h2><p>' + e(r.get('summary')) + '</p><small>' + e(r.get('date')) + ' · ' + e(r.get('status')) + '</small></article>'
        doc = '<h1>' + e(r['title']) + '</h1><p class="muted">' + e(r.get('date')) + ' · ' + e(r.get('status')) + '</p>'
        for asset in r.get('files', []):
            name = 'report-files/' + sha256((r['id'] + ':' + asset['name']).encode()).hexdigest()[:24] + '.' + asset['extension']
            files[name] = base64.b64decode(asset['base64'], validate=True)
            doc += '<a class="button" href="' + name + '">Download ' + e(asset['extension'].upper()) + '</a> '
        files[filename('report', r['id'])] = page(r['title'], doc + '<section class="report-body">' + clean_html(r.get('html')) + '</section>', 'reports')
    files['reports.html'] = page('Reports', body + '</div>' + ('<section class="panel section">No reports have been included in this release.</section>' if not reports else ''), 'reports')
    projects = corp['projects']
    body = '<h1>Projects</h1><p class="muted">Corporate-managed project pages. Weekly research updates preserve this separate collection.</p><div class="card-grid">'
    for p in projects:
        body += '<article class="card"><h2><a href="' + filename('project', p['id']) + '">' + e(p['title']) + '</a></h2>' + badge(p.get('status', 'Not specified')) + '<p>' + e(p.get('summary')) + '</p></article>'
        doc = '<h1>' + e(p['title']) + '</h1><p>' + e(p.get('summary')) + '</p><div class="summary">' + badge(p.get('status', 'Not specified')) + '<span>Owner: ' + e(p.get('owner', 'Not assigned')) + '</span></div><p class="banner">Checkbox changes are temporary visual marks. Ask the site publisher to save and publish shared status changes.</p><section class="panel section"><h2>Milestones & tasks</h2>'
        for task in p.get('tasks', []):
            doc += '<label class="task"><input type="checkbox"' + (' checked' if task.get('done') is True else '') + '><span><strong>' + e(task.get('title')) + '</strong><br><small>' + e(task.get('owner')) + (' · Due ' + e(task['due']) if task.get('due') else '') + '</small></span></label>'
        files[filename('project', p['id'])] = page(p['title'], doc + '</section><section class="panel section">' + clean_html(p.get('html')) + '</section>', 'projects')
    files['projects.html'] = page('Projects', body + '</div>' + ('<section class="panel section">No corporate projects added yet.</section>' if not projects else '') + '<p><a href="project-template.html">Open the HTML project tracker template</a></p>', 'projects')
    files['project-template.html'] = page('Project tracker template', '<h1>Project tracker template</h1><p class="muted">Template only. Add a project title, owner, milestones and tasks through the site publisher.</p><section class="panel section"><h2>Project overview</h2><p>Purpose, owner, status and next milestone.</p><details open><summary>Milestone and task group</summary><label class="task"><input type="checkbox"><span>Example task — temporary visual checkbox</span></label></details><p class="banner">Checkbox marks are temporary in this view. Shared project updates are saved and published by the site publisher.</p></section>', 'projects')
    changes = workspace.get('changes', {})
    files['changes.html'] = page('What changed', '<h1>What changed</h1><p>Baseline: ' + e(changes.get('baseline_id') or 'First release') + ' · ' + e(changes.get('basis')) + '</p><section class="panel section">' + ''.join('<p><b>' + e(r['change'].replace('_', ' ').title()) + '</b> · ' + e(r['container']) + ' · ' + e(r['title']) + '</p>' for r in changes.get('items', [])) + '</section><details><summary>Unavailable or excluded assets</summary>' + ''.join('<p>' + e(r['title']) + ': ' + e(r['reason']) + '</p>' for r in workspace.get('asset_omissions', [])) + '</details>')
    if scores:
        rows = ''.join('<tr><td>' + e(varieties[r['variety_id']]['name']) + '</td><td>' + e(r['panel']) + '</td><td>' + e(r.get('date')) + '</td>' + ''.join('<td>' + e(r.get(k)) + '</td>' for k in ['overall_liking', 'taste', 'texture', 'appearance', 'brix', 'acidity']) + '<td>' + e(r.get('acidity_unit')) + '</td></tr>' for r in scores)
        files['flavor.html'] = page('Corporate flavor records', '<h1>Corporate flavor records</h1><p>Corporate-only supplement. Each panel record is displayed separately. Update the source file and republish; no values are sent to the research platform.</p><section class="panel"><div class="scroll"><table class="directory-table"><thead><tr>' + ''.join('<th>' + t + '</th>' for t in ['Variety', 'Panel', 'Date', 'Overall liking', 'Taste', 'Texture', 'Appearance', 'Brix', 'Acidity', 'Unit']) + '</tr></thead><tbody>' + rows + '</tbody></table></div></section>', 'flavor')
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--corporate')
    parser.add_argument('--flavor')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    load = lambda name: json.loads(Path(name).read_text(encoding='utf-8-sig')) if name else None
    workspace = load(args.workspace)
    if workspace.get('scores'):
        raise ValueError('Use a research-only workspace. Supply corporate scores through --flavor.')
    corporate = load(args.corporate)
    if corporate:
        corporate_model(corporate, workspace['directory'])
        for project in corporate.get('projects', []):
            if project.get('html_file'):
                base = Path(args.corporate).resolve().parent
                path = (base / project['html_file']).resolve()
                if not path.is_relative_to(base) or path.suffix.lower() != '.html' or not path.is_file() or path.stat().st_size > 5_000_000:
                    raise ValueError('Project HTML files must be bounded .html files inside the corporate settings folder.')
                project['html'] = path.read_text(encoding='utf-8-sig')
    files = build_site(workspace, corporate, load(args.flavor))
    root = Path(args.output).resolve()
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise ValueError('Choose a new empty staging folder. Replacing the complete published tree prevents deselected reports from lingering.')
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    manifest = {'delivery': 'html_inline_css_no_javascript', 'files': {k: sha256(v).hexdigest() for k, v in files.items()}}
    (root / 'site-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'Built {len(files)} files. Open {root / "index.html"}. No JavaScript or APIs required.')


if __name__ == '__main__':
    main()
