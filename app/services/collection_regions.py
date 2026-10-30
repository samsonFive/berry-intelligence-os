"""Explicit article geography, including supported native country adjectives.

Neither the publisher's language nor its domain establishes article location.
"""
from app.services.topic_retrieval import normalize

NATIVE_REGION_TERMS = {
    'europe': ('polski', 'polskie', 'polskich', 'polskiego', 'polskiej', 'polską',
               'polskę', 'polskim', 'polskimi', 'europie', 'europejski', 'europejskie'),
    'americas': ('brasileiro', 'brasileira', 'brasileiros', 'brasileiras',
                 'América do Sul', 'América do Norte'),
}


def article_matches_region(region, *, title='', body=''):
    if region == 'global':
        return True
    from app.services.industry_pulse.matrix import GEO_EDITIONS
    places = GEO_EDITIONS[region]['terms'].strip('()').replace('"', '').split(' OR ')
    terms = [*places, *NATIVE_REGION_TERMS.get(region, ())]
    text = ' ' + normalize(title + ' ' + body) + ' '
    return any(' ' + normalize(term) + ' ' in text for term in terms)
