"""Reuse Map selector identities for statistical context, never create entities."""
from copy import deepcopy
import re


def countries(entities):
    from app.services.global_explorer import boundary_countries

    boundaries = boundary_countries()
    by_code = {}
    for row in entities.values():
        code = (row.get('attributes') or {}).get('iso_3166_1_alpha_2')
        if (row.get('entity_type') == 'geography' and isinstance(code, str)
                and re.fullmatch(r'[A-Z]{2}', code) and code in boundaries
                and isinstance(row.get('id'), str) and row['id']
                and isinstance(row.get('name'), str) and row['name'].strip()):
            by_code.setdefault(code, []).append(row)
    result = {}
    for code, name in boundaries.items():
        records = by_code.get(code, [])
        if len(records) > 1:
            continue  # An ambiguous catalog identity must not become a fallback.
        row = deepcopy(records[0]) if records else {
            'id': 'iso:' + code, 'name': name, 'entity_type': 'geography',
            'attributes': {'iso_3166_1_alpha_2': code}, 'reference_only': True,
        }
        result[row['id']] = row
    return dict(sorted(result.items(), key=lambda item: (item[1]['name'].casefold(), item[0])))


def equivalent_ids(country_id, entities, *, choices=None):
    """Match a statistical country, without assigning intelligence geography.

    ISO-only references keep their captured IDs when a catalog country later
    exists. Ambiguous ISO mappings never broaden a match; exact IDs still work.
    """
    choices = countries(entities) if choices is None else choices
    result = {country_id}
    selected = choices.get(country_id)
    if not selected and country_id.startswith('iso:'):
        code = country_id[4:]
        selected = next((row for row in choices.values()
                         if row['attributes']['iso_3166_1_alpha_2'] == code), None)
    if selected:
        code = selected['attributes']['iso_3166_1_alpha_2']
        result.update((selected['id'], 'iso:' + code))
    return result
