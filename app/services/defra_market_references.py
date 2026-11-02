"""Bounded public UK workbook references; no inference or automatic selection."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from io import BytesIO
import math
import re
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

import httpx

LANDING = 'https://www.gov.uk/government/statistics/latest-horticulture-statistics'
SOURCE = 'Defra'
COUNTRY_ID = 'geography-united-kingdom'
CROPS = {'Strawberries': 'berry-strawberry', 'Raspberries': 'berry-raspberry', 'Blueberry': 'berry-blueberry'}
TABLES = {
    'Table_4_Fruit_area': ('planted_area', 'Planted area', 'ha', '(Hectares)'),
    'Table_5_Fruit_yield': ('marketed_yield', 'Marketed yield', 't/ha', '(Tonnes/hectare)'),
    'Table_6_Fruit_production': ('marketed_production', 'Marketed production', '1000 t', '(Thousand tonnes)'),
}
NS = {'t': 'urn:oasis:names:tc:opendocument:xmlns:table:1.0',
      'x': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
      'o': 'urn:oasis:names:tc:opendocument:xmlns:office:1.0'}
POLICY = 'figures in the statistical notice and datasets for the latest year reported are provisional and subject to revision'


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(); self.links = []; self.parts = []; self._skip = 0
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}:
            self._skip += 1
        if tag == 'a' and not self._skip:
            self.links.append(dict(attrs).get('href', ''))

    def handle_endtag(self, tag):
        if tag in {'script', 'style'} and self._skip:
            self._skip -= 1

    def handle_data(self, text):
        if not self._skip:
            self.parts.append(text)

    @property
    def text(self):
        return ' '.join(' '.join(self.parts).split())


def dataset_url(value):
    parts = urlsplit(value)
    return (parts.scheme == 'https' and parts.netloc == 'assets.publishing.service.gov.uk'
            and not parts.query and not parts.fragment
            and re.fullmatch(r'/media/[a-zA-Z0-9]+/hort-dataset-\d{2}-\d{8}\.ods', parts.path))


def fetch_bytes(url, *, maximum):
    """No credentials/redirects; cap the body while it is streaming."""
    with httpx.stream('GET', url, timeout=20, follow_redirects=False) as response:
        response.raise_for_status()
        if response.is_redirect:
            raise ValueError('The official source moved; check its new location.')
        result = bytearray()
        for chunk in response.iter_bytes():
            result.extend(chunk)
            if len(result) > maximum:
                raise ValueError('The official source exceeds the bounded capture size.')
    return bytes(result)


def _sheet_rows(table):
    """Inspect a bounded grid, retaining original displayed and cached values."""
    rows = []; position = 1
    elements = table.findall('t:table-row', NS)
    if len(elements) > 300:
        raise ValueError('The official table layout changed.')
    for row in elements:
        cells = {}; column = 1
        for cell in list(row):
            if cell.tag not in {'{' + NS['t'] + '}table-cell', '{' + NS['t'] + '}covered-table-cell'}:
                continue
            text = ' '.join(' '.join(''.join(p.itertext()).split()) for p in cell.findall('x:p', NS))
            raw = cell.get('{' + NS['o'] + '}value')
            repeat = int(cell.get('{' + NS['t'] + '}number-columns-repeated', '1'))
            if repeat < 1 or len(text) > 3000:
                raise ValueError('Unreadable source cell.')
            if text or raw is not None:
                if column + repeat > 66:
                    raise ValueError('The official table is wider than the supported source grid.')
                for offset in range(repeat):
                    cells[column + offset] = {'text': text, 'cached_value': raw}
            column += repeat
        repeat = int(row.get('{' + NS['t'] + '}number-rows-repeated', '1'))
        if repeat < 1 or (cells and (repeat != 1 or position > 5000)):
            raise ValueError('Ambiguous or oversized source rows.')
        if cells:
            rows.append((position, cells))
        position += repeat
    return rows


def _number(cell):
    if cell['text'] in {'', '. .', '..'} and cell['cached_value'] is None:
        return None
    if not re.fullmatch(r'(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?', cell['text']):
        raise ValueError('A source number or missing-value marker needs review.')
    try:
        raw = Decimal(cell['cached_value'])
        displayed = Decimal(cell['text'].replace(',', ''))
    except (InvalidOperation, TypeError):
        raise ValueError('The source numeric cell cannot be read.') from None
    if not raw.is_finite() or raw < 0 or not math.isfinite(float(displayed)):
        raise ValueError('Invalid source value.')
    # We report the publisher's displayed precision, keeping the untouched
    # cached value alongside it in the original capture. Never calculate yield.
    precision = Decimal(1).scaleb(displayed.as_tuple().exponent)
    if abs(raw - displayed) > precision / 2:
        raise ValueError('Displayed and cached source values disagree.')
    return float(displayed)


def workbook_capture(content, *, source_url, notice_text, notice_url, captured_at):
    stamp = datetime.fromisoformat(captured_at)
    if stamp.utcoffset() is None or not dataset_url(source_url):
        raise ValueError('Invalid official source or capture date.')
    if POLICY not in notice_text.casefold():
        raise ValueError('Check the source qualifications before using this release.')
    if not 0 < len(content) <= 2_000_000:
        raise ValueError('Oversized or empty official workbook.')
    try:
        with ZipFile(BytesIO(content)) as archive:
            info = archive.getinfo('content.xml')
            if len(archive.infolist()) > 256 or info.file_size > 20_000_000 or archive.getinfo('mimetype').file_size > 100:
                raise ValueError('Oversized official workbook.')
            if archive.read('mimetype') != b'application/vnd.oasis.opendocument.spreadsheet':
                raise ValueError('Unexpected official workbook format.')
            xml = archive.read('content.xml')
        if b'<!DOCTYPE' in xml or b'<!ENTITY' in xml:
            raise ValueError('Unsupported source XML declarations.')
        document = ET.fromstring(xml)
    except (BadZipFile, KeyError, ET.ParseError) as exc:
        raise ValueError('The official workbook cannot be read.') from exc
    tables = {}
    for table in document.findall('.//t:table', NS):
        name = table.get('{' + NS['t'] + '}name')
        if name in {*TABLES, 'Notes_and_Contact_Details'}:
            if name in tables:
                raise ValueError('Repeated official table.')
            tables[name] = _sheet_rows(table)
    if set(tables) != {*TABLES, 'Notes_and_Contact_Details'}:
        raise ValueError('Required official tables are missing.')
    notes = ' '.join(c['text'] for _, row in tables['Notes_and_Contact_Details'] for c in row.values())
    years = re.findall(r'Horticultural Statistics (\d{4})', notes)
    dates = re.findall(r'Published:\s*(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})', notes)
    if len(set(years)) != 1 or len(dates) != 1:
        raise ValueError('The source release date or crop year needs review.')
    year = years[0]
    published = datetime.strptime(' '.join(dates[0]), '%d %B %Y').date()
    if not stamp.year - 4 <= int(year) <= stamp.year or published > stamp.date():
        raise ValueError('The source period is outside this recent capture.')
    if not source_url.endswith(f'hort-dataset-{year[-2:]}-{published:%Y%m%d}.ods'):
        raise ValueError('Workbook identity and source URL disagree.')
    expected_notice = LANDING + '/horticulture-statistics-' + year
    if notice_url != expected_notice:
        raise ValueError('The source notice does not match this workbook.')
    cells = []; metrics = {crop: [] for crop in CROPS}
    for name, (code, label, unit, source_unit) in TABLES.items():
        rows = tables[name]
        if not any(c['text'] == source_unit for _, row in rows for c in row.values()):
            raise ValueError('Original source units have changed.')
        selected_column = None; found = set(); current_unit = ''
        for row_number, row in rows:
            first = row.get(1, {}).get('text', '')
            if first.startswith('('):
                current_unit = first
            header = [column for column, c in row.items() if c['text'] == year and c['cached_value'] == year]
            if header:
                if len(header) != 1:
                    raise ValueError('Repeated reporting year.')
                if current_unit != source_unit:
                    raise ValueError('The current table uses different source units.')
                selected_column = header[0]
            # Older panels do not contain this release year. Their repeated
            # crop labels must not be mistaken for current data.
            elif any(re.fullmatch(r'\d{4}', c['text']) and c['cached_value'] == c['text'] for c in row.values()):
                selected_column = None
            crop = row.get(2, {}).get('text')
            if crop not in CROPS or selected_column is None:
                continue
            if crop in found:
                raise ValueError('Ambiguous crop rows in the current-year table.')
            found.add(crop)
            cell = row.get(selected_column, {'text': '', 'cached_value': None})
            value = _number(cell)
            locator = f'{name} · row {row_number} · column {selected_column} · {year}'
            cells.append({'crop': crop, 'metric': code, 'locator': locator, **cell})
            if value is not None:
                metrics[crop].append({'source_code': code, 'label': label, 'value': value, 'unit': unit,
                                      'classification': 'Provisional estimate', 'source_label': label,
                                      'definition': label + ' in the Defra fruit tables; original source units and displayed rounding.',
                                      'source_cell': locator})
        if found != set(CROPS):
            raise ValueError('A named crop row is missing from the current table.')
    groups = []
    for crop, values in metrics.items():
        if not values:
            continue
        order = {'marketed_production': 0, 'planted_area': 1, 'marketed_yield': 2}
        values = sorted(values, key=lambda metric: order[metric['source_code']])
        area_note = ''
        area = next((m['value'] for m in values if m['source_code'] == 'planted_area'), None)
        patterns = {
            'Strawberries': r'strawberry production.{0,1800}?total cultivated area.{0,100}?\bat\s+([\d,]+)\s+hectares',
            'Raspberries': r'raspberry growing area.{0,120}?\bto\s+([\d,]+)\s+hectares',
        }
        if crop in patterns and area is not None:
            reported = sorted(set(re.findall(patterns[crop], notice_text.casefold())))
            if len(reported) == 1:
                narrative = float(reported[0].replace(',', ''))
                if narrative != area:
                    area_note = (f'Planted area differs: the release narrative reports {narrative:,.0f} ha; '
                                 f'the workbook reports {area:,.0f} ha. Check both sources before using a whole-crop total.')
            else:
                area_note = 'The release narrative’s area basis was not reconciled with this workbook. Check the originals before using a whole-crop total.'
        groups.append({'country_id': COUNTRY_ID, 'country': 'United Kingdom', 'berry_id': CROPS[crop],
                       'commodity': crop + ' · Defra fruit tables', 'period': year + ' calendar year',
                       'source': SOURCE, 'source_url': source_url, 'notice_url': notice_url,
                       'locator': 'Defra horticulture · fruit tables 4, 5 and 6 · ' + year,
                       'published_date': published.isoformat(), 'source_updated_at': '',
                       'accessed_date': stamp.date().isoformat(), 'methodology_url': notice_url,
                       'status': 'Official provisional estimates · workbook series', 'date_note': area_note,
                       'basis': ('Provisional estimates from Defra’s fruit tables. Planted area and marketed production/yield '
                                 'keep the workbook’s reporting basis and rounding. Glasshouse fruit is listed separately. '
                                 'Do not combine these figures with total-harvest or USDA utilization figures. ' + area_note),
                       'metrics': values})
    if not groups:
        raise ValueError('No reported UK figures; retain existing references.')
    return {'year': year, 'published_date': published.isoformat(), 'source_cells': cells, 'groups': groups}


def fetch_capture(*, captured_at, fetch=fetch_bytes):
    landing = fetch(LANDING, maximum=1_000_000)
    page = Page(landing.decode('utf-8'))
    urls = {urljoin(LANDING, link) for link in page.links if dataset_url(urljoin(LANDING, link))}
    if len(urls) != 1:
        raise ValueError('Choose the current official dataset after its location is checked.')
    source_url = urls.pop()
    release_year = '20' + re.search(r'hort-dataset-(\d{2})-', source_url).group(1)
    notice_url = LANDING + '/horticulture-statistics-' + release_year
    notice = fetch(notice_url, maximum=1_000_000)
    workbook = fetch(source_url, maximum=2_000_000)
    captured = workbook_capture(workbook, source_url=source_url, notice_text=Page(notice.decode('utf-8')).text,
                                notice_url=notice_url, captured_at=captured_at)
    return captured, {'landing.html': landing, 'notice.html': notice, 'original.ods': workbook}


def validate_group(group):
    """Source/country/crop/period/unit checks also protect saved history."""
    if group.get('source') != SOURCE or group.get('country_id') != COUNTRY_ID or group.get('country') != 'United Kingdom':
        raise ValueError('Invalid UK reference scope.')
    crop = next((crop for crop, bid in CROPS.items() if bid == group.get('berry_id')), None)
    if crop is None or group.get('commodity') != crop + ' · Defra fruit tables':
        raise ValueError('Invalid UK crop category.')
    if any(not isinstance(group.get(k), str) or not group[k] or len(group[k]) > limit for k, limit in
           {'period': 40, 'source_url': 3000, 'locator': 500, 'status': 200, 'basis': 2000}.items()):
        raise ValueError('Incomplete UK reference.')
    if not re.fullmatch(r'\d{4} calendar year', group['period']) or not dataset_url(group['source_url']):
        raise ValueError('Invalid source period or URL.')
    published = date.fromisoformat(group['published_date'])
    accessed = date.fromisoformat(group['accessed_date'])
    year = group['period'][:4]
    notice = LANDING + '/horticulture-statistics-' + year
    if (group.get('notice_url') != notice or group.get('methodology_url') != notice
            or group.get('source_updated_at') != '' or published > accessed
            or not group['source_url'].endswith(f'hort-dataset-{year[-2:]}-{published:%Y%m%d}.ods')):
        raise ValueError('The UK source identity or dates disagree.')
    if not isinstance(group.get('date_note'), str) or len(group['date_note']) > 600:
        raise ValueError('Invalid source qualifications.')
    metrics = group.get('metrics')
    if not isinstance(metrics, list) or not 1 <= len(metrics) <= 3:
        raise ValueError('No usable source figures.')
    indicators = {row[0]: (name, *row[1:3]) for name, row in TABLES.items()}
    seen = set()
    for metric in metrics:
        if not isinstance(metric, dict):
            raise ValueError('Invalid figure.')
        code = metric.get('source_code')
        if code not in indicators or code in seen:
            raise ValueError('Repeated or unknown UK figure.')
        sheet, label, unit = indicators[code]
        value = metric.get('value')
        if (type(value) not in {int, float} or not math.isfinite(value) or value < 0
                or (metric.get('label'), metric.get('unit')) != (label, unit)
                or metric.get('classification') != 'Provisional estimate'):
            raise ValueError('Invalid figure unit, definition or qualification.')
        if not isinstance(metric.get('definition'), str) or not 1 <= len(metric['definition']) <= 500:
            raise ValueError('Missing source definition.')
        if not re.fullmatch(re.escape(sheet) + r' · row [1-9]\d{0,3} · column (?:[1-9]|[1-5]\d|6[0-4]) · ' + year, metric.get('source_cell', '')):
            raise ValueError('Invalid source cell reference.')
        seen.add(code)
