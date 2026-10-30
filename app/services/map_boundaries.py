"""Map selector metadata, separate from intelligence or statistical coverage."""
from functools import lru_cache
import json
from pathlib import Path
import re


def catalog(features, corrections):
    countries = {
        row['properties']['ISO3166-1-Alpha-2']: row['properties']['name']
        for row in features
        if re.fullmatch(r'[A-Z]{2}', row['properties']['ISO3166-1-Alpha-2'])
    }
    references = {}
    if corrections.get('version') != 1 or not isinstance(corrections.get('overrides'), list) or len(corrections['overrides']) > 10:
        raise ValueError('Unreadable country reference metadata')
    for row in corrections['overrides']:
        code = row.get('alpha_2', '')
        if not re.fullmatch(r'[A-Z]{2}', code) or not re.fullmatch(r'[A-Z]{3}', row.get('alpha_3', '')):
            raise ValueError('Invalid country reference code')
        if row.get('expected_alpha_2') != '-99' or row.get('expected_alpha_3') != '-99':
            raise ValueError('Only missing boundary metadata may be corrected')
        candidates = [f for f in features if f['properties']['name'] == row.get('feature_name')]
        if len(candidates) != 1 or code in countries or code in references:
            continue
        props = candidates[0]['properties']
        if (props.get('ISO3166-1-Alpha-2') != row['expected_alpha_2']
                or props.get('ISO3166-1-Alpha-3') != row['expected_alpha_3']):
            continue  # A changed source needs review, not an automatic override.
        countries[code] = props['name']
        references[code] = {key: row[key] for key in ('feature_name', 'expected_alpha_2', 'expected_alpha_3')}
    return countries, references


@lru_cache(maxsize=1)
def load():
    assets = Path(__file__).resolve().parents[1] / 'static'
    features = json.loads((assets / 'countries.geojson').read_text(encoding='utf-8'))['features']
    corrections = json.loads((assets / 'country-reference-metadata.json').read_text(encoding='utf-8'))
    return catalog(features, corrections)
