"""Rights-recorded reference photography; never source evidence or crop attribution."""
from collections import Counter
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re

from app.services.industry_pulse.regional_news import regional_crop_ids

ROOT = Path(__file__).resolve().parents[1] / 'static/news-images'


@lru_cache(maxsize=1)
def catalog():
    entries = json.loads((ROOT / 'reference-catalog.json').read_text(encoding='utf-8'))['assets']
    return tuple(row for row in entries
        if row.get('license') in {'CC0', 'Public domain'}
        and row.get('rights_status') == 'source_license_checked'
        and re.fullmatch(r'reference/[a-z0-9-]+\.(?:jpg|png|webp)', row.get('file', ''))
        and (ROOT / row['file']).is_file())


def reference_for(record, *, used=None):
    text = ' '.join(str(record.get('original_' + key) or record.get(key) or '') for key in ('title', 'summary'))
    crops = {key.removeprefix('berry-') for key in regional_crop_ids(text)}
    if not crops:
        crops = {str(key).removeprefix('berry-') for key in record.get('berry_ids') or []}
    choices = [row for row in catalog() if row.get('crop') in crops] if crops else [row for row in catalog() if not row.get('crop')]
    if not choices:
        return None
    theme = 'general'
    for key, pattern in [('research', r'research|trial|genetic|breeding|cultivar|laborator|DNA'),
                         ('growing', r'farm|grow|plant|nurser|harvest|acreage|hectare'),
                         ('weather', r'weather|climate|water|frost|drought|rain'),
                         ('trade', r'export|import|trade|retail|price|market|supply')]:
        if re.search(pattern, text, re.I):
            theme = key
            break
    if not crops:
        choices = [row for row in choices if ('research' if theme == 'research' else 'general') in row['themes']]
        if not choices:
            return None
    key = str(record.get('id') or record.get('source_url') or text)
    selected = min(choices, key=lambda row: (
        (used or {}).get(row['id'], 0),
        -int(theme in row['themes']),
        hashlib.sha256((key + row['id']).encode()).hexdigest()))
    return {**selected, 'url': '/static/news-images/' + selected['file'],
            'credit': selected['creator'] or 'See source credit',
            'label': 'Reference photo', 'note': 'Context photo; not a photo of this article or reported event.'}


def diversify(cards):
    """Prefer unused equally relevant references on this page; publisher photos win."""
    used = Counter()
    for card in cards:
        reference = reference_for(card.get('record') or {}, used=used)
        card['reference_image'] = reference
        if reference:
            used[reference['id']] += 1
