"""Retain public disclosure text anchored to already extracted article prose.

This reads publisher markup, never executes a page or expands arbitrary hidden
content. Source text and ordering survive; no identity or trust decisions follow.
"""
from copy import deepcopy
from collections import Counter, defaultdict

from lxml import etree, html as html_parser


def _key(text):
    return ' '.join(text.split())


def _excluded(node):
    return any(str(p.tag).lower() in {'nav', 'aside', 'footer', 'header', 'form',
                                     'script', 'style', 'template'}
               or 'hidden' in p.attrib or p.get('aria-hidden') == 'true'
               for p in [node, *node.iterancestors()])


def _text(node):
    copy = deepcopy(node)
    for br in copy.iter('br'):
        br.tag = 'span'
        br.text = '\n'
    return '\n'.join(_key(line) for line in copy.text_content().splitlines() if _key(line))


def retained_disclosure_passages(source, passages):
    """Add only controls' public content within a proven article section.

    A region needs a unique reciprocal button/region ID pair, or a native
    details/summary pair. Its nearest section/article/main must contain exact,
    unique extracted prose. Navigation, hard-hidden ancestors, templates,
    interactive forms and unanchored widgets remain excluded. Link-heavy
    cultivar lists are content when these conditions hold.
    """
    try:
        tree = html_parser.fromstring(source)
    except (etree.ParserError, ValueError, TypeError):
        return list(passages)
    counts = Counter(_key(p) for p in passages)
    indexes = {_key(p): i for i, p in enumerate(passages)
               if len(_key(p)) >= 80 and counts[_key(p)] == 1}
    ids = defaultdict(list)
    positions = {node: i for i, node in enumerate(tree.iter())}
    for node in tree.xpath('//*[@id]'):
        ids[node.get('id')].append(node)
    additions, selected_panels = defaultdict(list), set()
    for panel in tree.xpath('//details | //*[@role="region"]'):
        if any(p in selected_panels for p in panel.iterancestors()):
            continue
        if _excluded(panel) or panel.xpath('.//form|.//input|.//select|.//textarea|.//button'):
            continue
        if panel.tag == 'details':
            labels = panel.xpath('./summary')
            if len(labels) != 1:
                continue
            control = labels[0]
        else:
            pid, cid = panel.get('id'), panel.get('aria-labelledby')
            if not pid or not cid or len(ids[pid]) != 1 or len(ids[cid]) != 1:
                continue
            control = ids[cid][0]
            if (control.get('role') != 'button' or control.get('aria-controls') != pid
                    or control.get('aria-expanded') not in {'true', 'false'}
                    or control.get('aria-disabled') == 'true'):
                continue
        label = _text(control)
        if _excluded(control) or not label or len(label) > 150:
            continue
        scopes = [p for p in panel.iterancestors()
                  if p.tag in {'section', 'article', 'main'} or p.get('role') == 'main']
        if not scopes:
            continue
        scope = scopes[0]
        if control not in set(scope.iter()):
            continue
        ordered = list(scope.iter())
        anchors = [(pos, indexes[_key(n.text_content())]) for pos, n in enumerate(ordered)
                   if n.tag == 'p' and not _excluded(n) and _key(n.text_content()) in indexes]
        if not anchors:
            continue
        def retain(node, text):
            position = ordered.index(node)
            preceding = [(pos, idx) for pos, idx in anchors if pos < position]
            slot = preceding[-1][1] + 1 if preceding else anchors[0][1]
            additions[slot].append((positions[node], text))
        blocks = [n for n in panel.iter() if n.tag in {'p', 'li', 'h2', 'h3', 'h4', 'h5', 'h6'}
                  and not _excluded(n)
                  and not any(c.tag in {'p', 'li', 'h2', 'h3', 'h4', 'h5', 'h6'} for c in n.iterdescendants())]
        missing = []
        for node in blocks:
            text = _text(node)
            # Some extractors already keep a br-separated list as individual
            # paragraphs. Do not duplicate a fully retained list in that case.
            represented = _key(text) in counts or (text and all(_key(line) in counts for line in text.splitlines()))
            if text and not represented:
                missing.append((node, text))
        if missing:
            retain(control, label)
            for node, text in missing:
                retain(node, text)
            selected_panels.add(panel)
    if sum(map(len, additions.values())) > 250 or sum(len(t) for rows in additions.values() for _, t in rows) > 100_000:
        raise ValueError('Publisher disclosure text exceeds the bounded capture limit')
    result = []
    for i in range(len(passages) + 1):
        result.extend(text for _, text in sorted(additions[i]))
        if i < len(passages):
            result.append(passages[i])
    return result
