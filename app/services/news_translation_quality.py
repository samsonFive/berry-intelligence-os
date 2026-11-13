"""Source-conserving checks for untrusted, offline English presentation."""
from collections import Counter
from calendar import month_name,month_abbr
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from html import unescape
import re
import unicodedata

LOCAL_METHOD = 'local-argos-ctranslate2'
_NUMBER = re.compile(r'(?<!\d)[+-]?\d+(?:[.,]\d+)*')
_SCALES = {'mil millones': 10**9, 'billion': 10**9, 'billions': 10**9,
           'milliards': 10**9, 'milliard': 10**9, 'milliarden': 10**9, 'مليار': 10**9,
           'million': 10**6, 'millions': 10**6, 'millones': 10**6, 'millón': 10**6,
           'millionen': 10**6, 'milhões': 10**6, 'مليون': 10**6,
           'thousand': 1000, 'thousands': 1000, 'mil': 1000, 'آلاف': 1000,
           '万':10000,'萬':10000,'亿':10**8,'億':10**8}
_SCALE_PATTERN = re.compile(r'\s*(?:(?:'+'|'.join(sorted((re.escape(k) for k in _SCALES if k not in '万萬亿億'),key=len,reverse=True))+r')(?!\w)|[万萬亿億])',re.I)
_PERCENT = re.compile(r'\s*(?:%|percent\b|per cent\b|por ciento\b|por cento\b|pour cent\b|Prozent\b|procent\b|في المئة|بالمئة|في المائة|بالمائة|パーセント)',re.I)
_PLACES = ('Melipilla','Ñuble','La Libertad','Lambayeque','Huelva','Odemira','Mucugê',
           'Loukkos','Larache','Tochigi','Mahabaleshwar','Panchgani')


def _currency_markers(text):
    codes=re.findall(r'(?<![A-Za-z])(?:USD|EUR|GBP|COP|AUD|CAD|NZD|CNY|JPY)(?![A-Za-z])',text)
    prefixes=re.findall(r'(?<!\w)[A-Z]{1,3}\$',text)
    return Counter(codes+[('USD' if value=='US$' else value) for value in prefixes])


def plain_source(text, source_name=''):
    value=re.sub(r'&\s+#\s*(\d{1,7})\s*;',r'&#\1;',str(text or ''))
    value=re.sub(r'&\s+(nbsp|amp|lt|gt|quot|apos)\s*;',r'&\1;',value)
    value=re.sub(r'</?[A-Za-z][A-Za-z0-9:-]*(?:\s+[^>]*|/?)>',' ',unescape(value))
    if source_name:
        # Only a declared trailing credit, not an arbitrary last headline clause.
        value=re.sub(r'(?:\s+[-–—|]\s*|\s{2,})'+re.escape(source_name)+r'\s*$','',value,flags=re.I)
    return ' '.join(value.split())


def _fold(text):
    return ''.join(c for c in unicodedata.normalize('NFKD',text.casefold()) if not unicodedata.combining(c))


def _decimal(raw, language):
    raw=''.join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in raw)
    decimal_comma=language in {'es','pt','de','fr','pl'}
    if ',' in raw and '.' in raw:
        decimal_separator=',' if raw.rfind(',')>raw.rfind('.') else '.'
        other='.' if decimal_separator==',' else ','
        raw=raw.replace(other,'').replace(decimal_separator,'.')
    elif ',' in raw:
        raw=raw.replace(',','.' if decimal_comma else '')
    elif '.' in raw and decimal_comma:
        groups=raw.lstrip('+-').split('.')
        if len(groups)>1 and groups[0]!='0' and all(len(g)==3 for g in groups[1:]):
            raw=raw.replace('.','')
    return Decimal(raw)


def quantities(text,language,*,numeric_months=False):
    text=unicodedata.normalize('NFKC',text).replace('−','-')
    if language=='en' and numeric_months:
        for month in range(1,13):
            names=rf'(?:{month_name[month]}|{month_abbr[month]}\.?)'
            text=re.sub(r'\b'+names+rf'\s+(\d{{1,2}})(?!\d)',rf'{month} \1',text,flags=re.I)
    # French and other publisher feeds commonly group thousands with spaces.
    for _ in range(3):
        text=re.sub(r'(?<!\w)(\d{1,3})[ \u00a0\u202f](\d{3})(?!\d)',r'\1\2',text)
    result=Counter()
    for match in _NUMBER.finditer(text):
        try:value=_decimal(match[0],language)
        except InvalidOperation:raise ValueError('Unparseable source quantity') from None
        tail=text[match.end():]
        scale=_SCALE_PATTERN.match(tail)
        if scale:value*=_SCALES[scale[0].strip().casefold()]
        percent=_PERCENT.match(tail) or text[:match.start()].endswith('百分之')
        result[(value,'percent' if percent else 'number')]+=1
    return result


def _repair_terms(source,english):
    # Source-reviewed Polish idiom in a plant-breeding headline. This narrow
    # repair changes presentation only; originals and cached output are kept.
    if (source == 'Jak powstają nowe odmiany borówki? Beata i Paweł Korfanty pokazują hodowlę od zaplecza'
            and re.search(r'\brearing from the back\b', english, re.I)):
        english = re.sub(r'\brearing from the back\b', 'the breeding process behind the scenes', english, flags=re.I)
    # Generic Spanish arándano follows the existing berry vocabulary, except
    # explicit cranberry/red-fruit wording, which must never be rewritten.
    red=re.search(r'ar[aá]ndanos?\s+rojos?|cranberr|macrocarpon|ocean\s*spray',source,re.I)
    blueberry=re.search(r'ar[aá]ndanos?|blueberr(?:y|ies)|myrtilles?|mirtilos?|Heidelbeeren?|Blaubeeren?|التوت الأزرق|蓝莓|ブルーベリー',source,re.I)
    if blueberry and not red:
        english=re.sub(r'\bcranberries\b','blueberries',english,flags=re.I)
        english=re.sub(r'\bcranberry\b','blueberry',english,flags=re.I)
        english=re.sub(r'\bblue\s+tuts?\b|\bblue\s+berries\b','blueberries',english,flags=re.I)
    if re.search(r'\bMelipilla\b',source) and not re.search(r'\bMelilla\b',source):
        english=re.sub(r'\bMelilla\b','Melipilla',english)
    return english


@lru_cache(maxsize=8192)
def _checked_fields(title,summary,out_title,out_summary,language,source_name):
    checked=[]
    for source,english in ((title,out_title),(summary,out_summary)):
        source=plain_source(source,source_name)[:2400]
        english=_repair_terms(source,plain_source(english,source_name))
        numeric_months=bool(re.search(r'\d{1,2}\s*[月월]|\b\d{1,4}[-/]\d{1,2}[-/]\d{1,4}\b',source))
        if quantities(source,language)!=quantities(english,'en',numeric_months=numeric_months):
            return None
        if Counter(c for c in source if c in '$€£')!=Counter(c for c in english if c in '$€£'):
            return None
        if _currency_markers(source)!=_currency_markers(english):
            return None
        original_fold,english_fold=_fold(source),_fold(english)
        for place in _PLACES:
            token=re.compile(r'(?<!\w)'+re.escape(_fold(place))+r'(?!\w)')
            named=re.search(r'(?<!\w)'+re.escape(place)+r'(?!\w)',source) or re.search(r'(?<!\w)'+re.escape(place.upper())+r'(?!\w)',source)
            if named and token.search(original_fold) and not token.search(english_fold):
                return None
        checked.append(english)
    return tuple(checked)


def checked_translation(title,summary,result,*,source_name=''):
    """Keep originals/cache immutable; unsafe local output stays untranslated."""
    if not isinstance(result,dict):return None
    if not str(result.get('translation_method') or '').startswith(LOCAL_METHOD):
        return result
    fields=_checked_fields(str(title or ''),str(summary or ''),str(result.get('title') or ''),
        str(result.get('summary') or ''),str(result.get('source_language') or 'und'),str(source_name or ''))
    if fields is None:return None
    return {**result,'title':fields[0],'summary':fields[1]}
