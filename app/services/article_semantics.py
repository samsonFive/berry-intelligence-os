"""Conservative repair of article prose incorrectly wrapped in HTML navigation."""
from lxml import etree, html as html_parser


def _text(node) -> str:
    return ' '.join(node.text_content().split())


def prose_navigation_html(source: str) -> str | None:
    """Repair one clearly bounded report region, never arbitrary menu content.

    Some publisher templates put an entire report inside ``nav``. Only consider
    a prose-heavy region within declared main/article content, in a section
    whose sole H1 matches the page title. Ambiguous, interactive, hidden and
    link-heavy regions stay untouched. Use only after normal extraction fails.
    """
    try:
        tree = html_parser.fromstring(source)
    except (etree.ParserError, TypeError, ValueError):
        return None
    title = ' '.join(tree.xpath('string(//title)').split()).casefold()
    if not title:
        return None
    eligible = []
    for node in tree.xpath('//nav'):
        lineage = [node, *node.iterancestors()]
        if any(str(parent.tag).lower() in {'aside', 'footer', 'header', 'template'}
               or 'hidden' in parent.attrib or parent.get('aria-hidden') == 'true'
               for parent in lineage):
            continue
        if not node.xpath("ancestor::article|ancestor::main|ancestor::*[@role='main']"):
            continue
        sections = node.xpath('ancestor::section[.//h1]')
        if not sections:
            continue
        headings = sections[-1].xpath('.//h1')
        if len(headings) != 1 or _text(headings[0]).casefold() != title:
            continue
        if node.xpath('.//form|.//button|.//input|.//select|.//textarea'):
            continue
        text = _text(node)
        if (len(text) < 1000 or sum(len(_text(p)) >= 100 for p in node.xpath('.//p')) < 4
                or not node.xpath('.//h2|.//h3')
                or sum(len(_text(a)) for a in node.xpath('.//a')) > len(text) * .10):
            continue
        eligible.append(node)
    if len(eligible) != 1:
        return None
    eligible[0].tag = 'div'
    eligible[0].attrib.pop('role', None)
    return etree.tostring(tree, encoding='unicode', method='html')
