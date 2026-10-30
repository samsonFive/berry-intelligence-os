"""Unambiguous Polish/Portuguese crop names shared by collection and retrieval."""
import re

EXTRA_CROP_TERMS = {
    'blueberry': ('mirtilo', 'mirtilos', 'borówka', 'borówki', 'borówek', 'borowka', 'borowki'),
    'strawberry': ('morango', 'morangos', 'truskawka', 'truskawki', 'truskawek'),
    'raspberry': ('framboesa', 'framboesas', 'malina', 'maliny', 'malin'),
    'blackberry': ('amora-preta', 'amoras-pretas', 'amora preta', 'amoras pretas', 'jeżyna', 'jeżyny', 'jeżyn', 'jezyna', 'jezyny'),
}
NATIVE_INDUSTRY_TERMS = ('odmiana', 'odmiany', 'odmian', 'hodowla', 'hodowli', 'licencja', 'licencje',
                         'variedade', 'variedades', 'melhoramento', 'licenciamento', 'produção', 'cultivo')
NATIVE_CONCEPTS = {'variety': ('odmiana', 'odmiany', 'odmian', 'variedade', 'variedades'),
                   'breeding': ('hodowla', 'hodowli', 'melhoramento'),
                   'license': ('licencja', 'licencje', 'licenciamento')}
NATIVE_GENETICS_TERMS = tuple(term for terms in NATIVE_CONCEPTS.values() for term in terms)


def canonicalize_crop_words(text):
    for crop, aliases in EXTRA_CROP_TERMS.items():
        text = re.sub(r'(?<!\w)(?:' + '|'.join(re.escape(a) for a in sorted(aliases, key=len, reverse=True)) + r')(?!\w)',
                      crop, text, flags=re.I)
    return text


def canonicalize_industry_words(text):
    for concept, aliases in NATIVE_CONCEPTS.items():
        text = re.sub(r'(?<!\w)(?:' + '|'.join(aliases) + r')(?!\w)', concept, text, flags=re.I)
    return text
