"""Unambiguous native crop terms shared by collection and retrieval."""
import re

EXTRA_CROP_TERMS = {
    'blueberry': ('mirtilo', 'mirtilos', 'borówka', 'borówki', 'borówek', 'borowka', 'borowki', 'myrtille', 'myrtilles', 'arándano azul', 'arándanos azules'),
    'strawberry': ('morango', 'morangos', 'truskawka', 'truskawki', 'truskawek', 'fresa', 'fresas', 'fraise', 'fraises'),
    'raspberry': ('framboesa', 'framboesas', 'malina', 'maliny', 'malin', 'framboise', 'framboises'),
    'blackberry': ('amora-preta', 'amoras-pretas', 'amora preta', 'amoras pretas', 'jeżyna', 'jeżyny', 'jeżyn', 'jezyna', 'jezyny', 'zarzamora', 'zarzamoras'),
}
# Keep generic Arabic "توت" (also mulberry) out of crop identity.
for _crop, _terms in {
    'blueberry': ('Heidelbeere', 'Heidelbeeren', 'Blaubeere', 'Blaubeeren', 'bleuets sauvages', 'bleuets en corymbe', 'التوت الأزرق', 'توت أزرق',
                  'borovnica', 'borovnice', 'borovnicu', 'боровница', 'боровнице', 'боровницу', 'việt quất'),
    'strawberry': ('Erdbeere', 'Erdbeeren', 'frutilla', 'frutillas', 'الفراولة', 'فراولة', 'الفريز',
                   'jagoda', 'jagode', 'jagodu', 'јагода', 'јагоде', 'јагоду', 'dâu tây'),
    'raspberry': ('Himbeere', 'Himbeeren', 'maline', 'malinu', 'malinama', 'малина', 'малине', 'малину', 'малинама',
                  'phúc bồn tử', 'mâm xôi đỏ'),
    'blackberry': ('Brombeere', 'Brombeeren', 'mora de Castilla', 'kupina', 'kupine', 'kupinu', 'kupinama',
                   'купина', 'купине', 'купину', 'купинама', 'mâm xôi đen', 'mûres surgelées', 'mûres fraîches', 'rappel de mûres'),
}.items():
    EXTRA_CROP_TERMS[_crop] += _terms

NATIVE_INDUSTRY_TERMS = ('odmiana', 'odmiany', 'odmian', 'hodowla', 'hodowli', 'licencja', 'licencje',
                         'variedade', 'variedades', 'melhoramento', 'licenciamento', 'produção', 'cultivo',
                         'producción agrícola', 'produccion agricola', 'agricultura de exportación',
                         'agricultura de exportacion', 'experiencias productivas',
                         'industria del arándano', 'industria del arandano',
                         'industria global del arándano', 'industria global del arandano',
                         'mejoramiento genético', 'mejoramiento genetico')
NATIVE_CONCEPTS = {'variety': ('odmiana', 'odmiany', 'odmian', 'variedade', 'variedades'),
                   'breeding': ('hodowla', 'hodowli', 'melhoramento'),
                   'license': ('licencja', 'licencje', 'licenciamento'),
                   'commercial': ('comercial', 'comerciales'),
                   'production': ('producción', 'produccion', 'produção')}
NATIVE_GENETICS_TERMS = tuple(
    term for concept in ("variety", "breeding", "license") for term in NATIVE_CONCEPTS[concept]
)


def _compile_aliases(vocabulary):
    return tuple(
        (term, re.compile(
            r'(?<!\w)(?:' + '|'.join(re.escape(alias) for alias in sorted(aliases, key=len, reverse=True)) + r')(?!\w)',
            re.I,
        ))
        for term, aliases in vocabulary.items()
    )


_CROP_PATTERNS = _compile_aliases(EXTRA_CROP_TERMS)
_INDUSTRY_PATTERNS = _compile_aliases(NATIVE_CONCEPTS)


def canonicalize_crop_words(text):
    for crop, pattern in _CROP_PATTERNS:
        text = pattern.sub(crop, text)
    return text


def canonicalize_industry_words(text):
    for concept, pattern in _INDUSTRY_PATTERNS:
        text = pattern.sub(concept, text)
    return text
