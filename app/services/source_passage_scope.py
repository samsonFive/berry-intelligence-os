"""Exclude explicit publisher recommendation tails from article evidence.

This is an ownership boundary, not a semantic relevance or truth judgment.
Original captures and their paragraph indices remain unchanged.
"""
import re

_RECOMMENDATIONS = {'related articles', 'related posts', 'recommended articles', 'you may also like', 'read next'}


def owned_article_passages(rows):
    """Yield (locator, text) until a standalone recommendation heading."""
    for locator, text in rows:
        heading = re.sub(r'\s+', ' ', str(text)).strip().casefold().rstrip(':')
        if heading in _RECOMMENDATIONS:
            break
        # News attribution marks the end of owned prose in flattened captures.
        text=re.split(r'(?:\n|(?<=[.!?])\s+)Source\s*:',str(text),maxsplit=1,flags=re.I)[0]
        yield locator, text
