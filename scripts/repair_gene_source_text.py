"""Inspect original DOM boundaries when generic extraction picked related news."""
from pathlib import Path
from lxml import html
import re
ROOT=Path(__file__).resolve().parents[1]
for key in ('pairwise-psi','pairwise-2026','pairwise-home','psi-research','psi-identity','heritable-home','heritable-products'):
    path=ROOT/'inbox/gene-editing-captures'/f'{key}.html'
    tree=html.fromstring(path.read_text(encoding='utf-8'))
    nodes=tree.xpath('//div[contains(concat(" ",normalize-space(@class)," ")," article-content ")]')
    if nodes:
        print(key,[(i,n.text_content()[:120],len(n.text_content())) for i,n in enumerate(nodes)])
        # The current page's article-content appears after globally embedded modal
        # content. Confirm headline/intro matches before selecting the last body.
        text=nodes[-1].text_content()
    else:
        for node in tree.xpath('//script|//style|//nav|//footer'):
            node.drop_tree()
        text=tree.text_content()
    text=re.sub(r'\s+',' ',text).strip()
    (path.with_suffix('.txt')).write_text(text,encoding='utf-8')
    print(key,text[:400])
