"""Bounded regional Google News queries and shared material-news vocabulary."""

import re
from dataclasses import replace

from app.services.berry_vocabulary import EXTRA_CROP_TERMS
from app.services.industry_pulse.matrix import (
    BERRIES,
    BERRY_IDS,
    BERRY_TERMS,
    GEO_EDITIONS,
    PULSE_TOPICS,
    PulseQuery,
    regional_language_queries,
)

REGIONAL_NEWS_PROVIDER = "regional_google_news"
EXACT_PUBLISHER_ROUTES = frozenset({"direct_rss", "direct_json", "indexed"})

ENGLISH_RISKS = (
    "farm closure", "farm closures", "layoff", "layoffs", "water allocation",
    "water restrictions", "labor dispute", "labour dispute", "labor strike",
    "recall", "tariff", "drought", "soil fumigation", "fewer chemicals",
    "labor hire", "labour hire", "worker underpayments", "wage underpayments",
    "underpaid workers", "minimum wage", "back-payments", "court penalties",
    "worker safety", "labor shortage", "labour shortage", "water rights",
    "irrigation restrictions", "recall warning", "recalled",
    "food safety", "norovirus", "listeria", "salmonella", "hepatitis A", "pesticide residues",
)
NATIVE_TOPICS = {
    "es": ("variedad", "cultivo", "exportación", "cosecha", "vivero", "patente",
           "despido", "despidos", "cierre de finca", "cierre de fincas", "sequía", "aranceles",
           "plantación", "hectárea", "hectáreas", "fumigación", "precios", "precio",
           "temporada de arándanos", "temporada de frutillas"),
    "fr": ("variété", "récolte", "exportation", "pépinière", "cultivar", "licenciements",
           "fermeture de ferme", "sécheresse", "rappel sanitaire", "rappel de", "rappelés", "rappelées",
           "droits de douane", "prix", "rendement", "rendements", "production", "exportations",
           "main-d’œuvre", "main-d'œuvre", "main-d'oeuvre", "canicule", "irrigation", "gel printanier", "gelées tardives"),
    "pt": ("variedade", "melhoramento", "produção", "exportação", "colheita", "cultivo",
           "demissões", "fechamento de fazenda", "seca", "tarifas"),
    "pl": ("odmiana", "odmiany", "hodowla", "uprawa", "eksport", "zbiory", "susza",
           "zwolnienia", "cła"),
    "zh": ("品种", "种植", "出口", "育种", "裁员", "农场关闭", "干旱", "关税"),
    "ja": ("品種", "栽培", "輸出", "育種", "解雇", "農場閉鎖", "干ばつ", "関税"),
    "ar": ("زراعة", "الزراعة", "مزارع", "المزارع", "حصاد", "الحصاد", "إنتاج", "الإنتاج",
           "تصدير", "التصدير", "صادرات", "الصادرات", "استيراد", "جفاف", "الجفاف", "رسوم جمركية"),
    "de": ("Anbau", "Ernte", "Erzeuger", "Erzeugerpreise", "Exporte", "Importe", "Züchtung",
           "Sorten", "Dürre", "Frost", "Rückruf", "Plantagen", "Landwirtschaft"),
    "sr": ("izvoz", "izvozni", "izvoza", "uvoz", "proizvodnja", "proizvodnje", "proizvođači",
           "otkup", "otkupna cena", "cene", "berba", "suša", "navodnjavanje", "prinos",
           "извоз", "извозни", "извоза", "увоз", "производња", "производње", "произвођачи",
           "откуп", "откупна цена", "цене", "берба", "суша", "наводњавање", "принос"),
    "vi": ("xuất khẩu", "nhập khẩu", "sản xuất", "sản lượng", "thu hoạch", "trồng",
           "giống mới", "hạn hán", "thu hồi", "nông nghiệp", "thị trường"),
}
EAST_ASIAN_CROPS = {
    "blueberry": ("蓝莓", "ブルーベリー"),
    "strawberry": ("草莓", "イチゴ", "いちご"),
    "raspberry": ("覆盆子", "ラズベリー"),
    "blackberry": ("黑莓", "ブラックベリー"),
}


def _or_terms(terms: tuple[str, ...]) -> str:
    return " OR ".join(f'"{term}"' if " " in term else term for term in terms)


def regional_news_queries() -> list[PulseQuery]:
    rows = [
        PulseQuery(
            id=f"today:regional:en:{berry}:{region}",
            text=f"{BERRY_TERMS[berry]} {edition['terms']} ({PULSE_TOPICS} OR {_or_terms(ENGLISH_RISKS)})",
            berry=berry, geography=region, topic="industry_pulse", kind="regional_news",
            hl=edition["hl"], gl=edition["gl"], ceid=edition["ceid"],
        )
        for berry in BERRIES
        for region, edition in GEO_EDITIONS.items() if region != "global"
    ]
    for query in regional_language_queries():
        language = query.hl.split("-", 1)[0]
        crop_and_place, _, _ = query.text.rpartition(" (")
        rows.append(replace(query, id=f"today:regional:{query.geography}:{query.gl}:{language}",
                            text=f"{crop_and_place} ({_or_terms(NATIVE_TOPICS[language])})"))
    for language, region, country, crops, place in (
        ("pt", "americas", "BR", ("mirtilo", "morango", "framboesa", "amora-preta"), "Brasil"),
        ("pl", "europe", "PL", ("borówka", "truskawka", "malina", "jeżyna"), "Polska"),
        ("fr", "americas", "CA", ("fraise", "framboise", "bleuet", "myrtille", "petits fruits"), "Québec"),
        ("es", "americas", "PE", ("arándanos", "fresas", "frambuesas", "zarzamoras"), '("La Libertad" OR Lambayeque OR Ica OR Perú)'),
        ("es", "americas", "CL", ("arándanos", "frutillas", "frambuesas", "zarzamoras"), '(Ñuble OR Maule OR Chile)'),
        ("es", "americas", "CO", ("arándanos", "fresas", "frambuesas", "mora de Castilla"), 'Colombia'),
        ("ar", "africa", "MA", ("الفراولة", "الفريز", "التوت الأزرق"), '(المغرب OR العرائش OR اللوكوس)'),
        ("ar", "africa", "EG", ("الفراولة", "الفريز", "التوت الأزرق"), 'مصر'),
        ("de", "europe", "DE", ("Heidelbeeren", "Erdbeeren", "Himbeeren", "Brombeeren"), 'Deutschland'),
        ("sr", "europe", "RS", ("maline", "kupine", "borovnice", "jagode", "малине", "купине", "боровнице", "јагоде"), '(Srbija OR Србија)'),
        ("vi", "apac", "VN", ("việt quất", "dâu tây", "phúc bồn tử", "mâm xôi đen"), '("Việt Nam" OR "Đà Lạt" OR "Sơn La")'),
    ):
        rows.append(PulseQuery(
            id=f"today:regional:{region}:{country}:{language}",
            text=f"({_or_terms(crops)}) {place} ({_or_terms(NATIVE_TOPICS[language])})",
            berry=None, geography=region, topic="industry_pulse", kind="regional_language",
            hl=f"{language}-{country}", gl=country, ceid=f"{country}:{language}",
        ))
    return [row.with_window("7d") for row in rows]


def _whole_words(terms: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile(r"(?<!\w)(?:" + "|".join(map(re.escape, terms)) + r")(?!\w)", re.I)


_LATIN_SCRIPT_TOPICS = tuple(term for language in ("es", "fr", "pt", "pl", "de", "ar", "sr", "vi") for term in NATIVE_TOPICS[language])
_REGIONAL_TOPIC_WORDS = _whole_words((*ENGLISH_RISKS, *_LATIN_SCRIPT_TOPICS))
_EAST_ASIAN_TOPICS = (*NATIVE_TOPICS["zh"], *NATIVE_TOPICS["ja"])
_ADDITIONAL_CROPS = {
    "blueberry": ("arándano", "arándanos", "arandano", "arandanos",
                  "bleuets de marque", "bleuets frais", "bleuets surgelés"),
    "raspberry": ("frambuesa", "frambuesas"),
}
_CROP_WORDS = {
    crop: _whole_words((crop, crop.removesuffix("y") + "ies", *EXTRA_CROP_TERMS[crop],
                        *_ADDITIONAL_CROPS.get(crop, ())))
    for crop in BERRY_IDS
}


def uses_regional_metadata(provider: str | None, publisher_route: str | None) -> bool:
    return provider == REGIONAL_NEWS_PROVIDER or (
        provider == "specialist_rss" and publisher_route in EXACT_PUBLISHER_ROUTES
    )


def has_regional_news_topic(text: str) -> bool:
    return bool(_REGIONAL_TOPIC_WORDS.search(text) or any(term in text for term in _EAST_ASIAN_TOPICS))


def regional_crop_ids(text: str) -> list[str]:
    return [
        BERRY_IDS[crop] for crop, words in _CROP_WORDS.items()
        if words.search(text) or any(term in text for term in EAST_ASIAN_CROPS[crop])
    ]
