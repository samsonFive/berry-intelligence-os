"""Exclude explicit publisher recommendation tails from article evidence.

This is an ownership boundary, not a semantic relevance or truth judgment.
Original captures and their paragraph indices remain unchanged.
"""
import re


def owned_pdf_abstracts(rows):
    """Reassemble explicitly numbered proceedings abstracts, never whole pages.

    Page captures stay unchanged. Derived locators identify the section and all
    contributing pages; an explicit Keywords ending is required. Ordinary PDFs
    retain their page passages. Missing pages never form a continuous abstract.
    """
    rows = list(rows)
    if not rows or not all(re.fullmatch(r'pdf:page:\d+', loc) for loc, _ in rows):
        return rows
    numbers = [int(loc.rsplit(':', 1)[1]) for loc, _ in rows]
    if any(b != a + 1 for a, b in zip(numbers, numbers[1:])):
        return rows
    parts = []; spans = []; size = 0
    for number, (_, text) in zip(numbers, rows):
        text = re.sub(r'^\[PDF page \d+\]\s*', '', text)
        parts.append(text)
        spans.append((size, size + len(text), number))
        size += len(text) + 1
    body = '\n'.join(parts)
    markers = list(re.finditer(r'(?m)^\s*(S\d{2}-[A-Z]-[OP]-\d{1,3})\s*$', body))
    if len(markers) < 2:
        numbered = list(re.finditer(r'(?m)^[ \t]*(\d{1,2})\.[ \t]+(?=\S)', body))
        sections = []
        for start, stop in zip(numbered, numbered[1:]):
            if int(stop[1]) != int(start[1]) + 1:
                continue
            section = body[start.start():stop.start()]
            abstracts = list(re.finditer(r'(?im)^[ \t]*Abstract\s*:', section))
            if len(abstracts) != 1 or abstracts[0].start() > 1000 or len(section) > 12000:
                continue
            pages = [n for lo, hi, n in spans if lo < stop.start() and hi > start.start()]
            if 1 <= len(pages) <= 3:
                locator = f'pdf:section:{start[1]}:pages:{pages[0]}-{pages[-1]}'
                sections.append((locator, section.strip()))
        return sections if len(sections) >= 2 else rows
    sections = []
    for i, marker in enumerate(markers):
        end = markers[i + 1].start() if i + 1 < len(markers) else len(body)
        section = body[marker.start():end]
        ending = re.search(r'(?im)^\s*Keywords\s*:[^\n]*(?:\n|$)', section)
        if not ending or ending.end() > 12000:
            continue  # Partial/truncated abstracts cannot borrow another section.
        end = marker.start() + ending.end()
        pages = [n for start, stop, n in spans if start < end and stop > marker.start()]
        if len(pages) > 3:
            continue
        locator = f'pdf:section:{marker[1]}:pages:{pages[0]}-{pages[-1]}'
        sections.append((locator, body[marker.start():end].strip()))
    return sections  # Recognized proceedings: do not also quote mixed raw pages.

_RECOMMENDATIONS = {'related articles', 'related posts', 'recommended articles', 'you may also like', 'read next', 'references', 'bibliography', 'recommended citation'}
_OBJECT_START = re.compile(r'^\s*\{\s*"[^"\r\n]{1,80}"\s*:')
_OBJECT_FIELD = re.compile(r'[,{}]\s*"[^"\r\n]{1,80}"\s*:')


def owned_article_passages(rows):
    """Yield (locator, text) until a standalone recommendation heading."""
    for locator, text in rows:
        # Some direct HTML captures expose serialized application state as one
        # paragraph. Exclude it before retrieval splits it into prose chunks.
        # A truncated object can still have a recognizable field structure.
        if _OBJECT_START.match(text) and len(_OBJECT_FIELD.findall(text)) >= 3:
            continue
        heading = re.sub(r'\s+', ' ', str(text)).strip().casefold().rstrip(':')
        if heading in _RECOMMENDATIONS:
            break
        if re.match(r'^(?:selected |related )?publications (?:related to|on|about)\b',heading):
            break
        # Bibliographic indexes can omit a References heading entirely. A
        # numbered author/initial/year citation is not the host's experiment.
        if (re.match(r'^\s*(?:\d+[.)]\s+)?[A-Z][\w\u2019\'-]+,\s*[A-Z]\.', str(text))
                and re.search(r'\((?:19|20)\d{2}\)\.', str(text))):
            continue
        if (re.match(r'^\s*[A-Z][\w\u2019\'-]+,\s*[A-Z]\.', str(text))
                and re.search(r'\((?:19|20)\d{2},\s*[A-Z][a-z]+\s+\d{1,2}\)\.', str(text))
                and re.search(r'\bRetrieved from https?://', str(text))):
            continue  # Unnumbered dated reference, not the host's own result.
        # News attribution marks the end of owned prose in flattened captures.
        text=re.split(r'(?:\n|(?<=[.!?])\s+)Source\s*:',str(text),maxsplit=1,flags=re.I)[0]
        yield locator, text
