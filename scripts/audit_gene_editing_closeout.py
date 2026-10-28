"""Public-source access audit; never calls an inference API or changes trust.

Run explicitly with --fetch. Full captures stay private. Versioned audit rows
contain only source metadata, hashes, and whether the retained excerpt matches.
Browser captures are permitted only for pages actually read in the browser.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import sys

import httpx
from lxml import html
from pypdf import PdfReader
import trafilatura

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/imports/gene-editing-2026-10-28'
CAPTURES=ROOT/'inbox/gene-editing-closeout-captures'
PRIOR=ROOT/'data/imports/gene-editing-2026-10-20/snapshot.json'
NEW=[
 ('fda-meetings','FDA','https://www.hfpappexternal.fda.gov/scripts/fdcc/?set=GenomeEditedPlants'),
 ('fda-simplot','FDA','https://www.hfpappexternal.fda.gov/scripts/fdcc/?id=0002&set=GenomeEditedPlants'),
 ('fda-pairwise','FDA','https://www.hfpappexternal.fda.gov/scripts/fdcc/?id=0011&set=GenomeEditedPlants'),
 ('canada-s4a','Health Canada','https://www.canada.ca/en/health-canada/services/food-nutrition/genetically-modified-foods-other-novel-foods/transparency-initiative/list-non-novel-products-plant-breeding-food-use.html'),
 ('uk-confirmation','Defra','https://assets.publishing.service.gov.uk/media/6a731929f0c3e4287c214d25/Precision_bred_confirmation_letter_-_PBM-26-FRAN-008.pdf'),
 ('mara-soybean','China Ministry of Agriculture and Rural Affairs','https://www.moa.gov.cn/ztzl/zjyqwgz/spxx/202401/P020240118484537271708.pdf'),
 ('psg-history','Plant Sciences Genetics','https://www.plantsciencesgenetics.com/about-us'),
 ('psg-research','Plant Sciences Genetics','https://www.plantsciencesgenetics.com/research'),
 ('heritable-products','Heritable Agriculture','https://heritable.ag/products'),
 ('planasa-rd','Planasa','https://planasa.com/rd/'),
 ('uf-ohalo-report','Florida Strawberry Research and Education Foundation / UF IFAS','https://member.floridastrawberry.org/wp-content/uploads/2025/11/14_FSREF_report_2024-25_S-Lee_2_neopestalotiopsis-resistance.pdf'),
 ('fall-creek-affiliation','PubMed / Horticulture Research','https://pubmed.ncbi.nlm.nih.gov/41635864/'),
 ('shunfeng-recruitment','China Agricultural University / Shunfeng','https://cbs.cau.edu.cn/module/download/downfile.jsp?classid=0&filename=7c00cfc203104491929b69f13b894b22.pdf'),
 ('hrb-financing','Hudson River Biotechnology','https://www.hudsonriver.bio/news/hudson-river-raises-new-financing-for-novel-breeding-techniques'),
 ('planasa-owner','Planasa','https://planasa.com/planasa-acquires-sweet-corn-breeder-ifsi/'),
 ('simplot-case-study','Simplot / SCRA','https://specialtycropassistance.org/wp-content/uploads/2026/04/S5-1_SCRA2026_Koch_Strawberry_Simplot_CaseStudy_260401.pdf'),
]


def normalize(value):
    return re.sub(r'[^\w]+','',value.casefold())


def fetch(spec):
    key,publisher,url,excerpt=spec
    row=dict(key=key,publisher=publisher,url=url,accessed_at=datetime.now(timezone.utc).isoformat(),
             status='unavailable',method='public HTTP GET; no paid research')
    browser=CAPTURES/(key+'.txt') if key in {'psg-history','psg-research','heritable-products'} else None
    try:
        if browser and browser.exists():
            text=browser.read_text(encoding='utf-8')
            row.update(method='rendered browser DOM; page opened and read',canonical_url=url)
        else:
            r=httpx.get(url,follow_redirects=True,timeout=35,headers={'User-Agent':'BerryIntelligenceResearch/1.0'})
            row.update(http_status=r.status_code,canonical_url=str(r.url))
            if r.status_code!=200:
                row['status']='blocked' if r.status_code in (401,403,429) else 'unavailable'
                return row
            if 'application/pdf' in r.headers.get('content-type','') or url.endswith('.pdf'):
                text='\n'.join(p.extract_text() or '' for p in PdfReader(BytesIO(r.content)).pages)
                (CAPTURES/(key+'.pdf')).write_bytes(r.content)
            else:
                document=trafilatura.bare_extraction(r.text,url=str(r.url),with_metadata=True)
                text=(document.text if document else '') or ''
                if 'pairwise.com/insights/' in url:
                    nodes=html.fromstring(r.text).xpath('//div[contains(concat(" ",normalize-space(@class)," ")," article-content ")]')
                    if nodes:text=nodes[-1].text_content()
                # FDA/Health Canada tables are evidence, not navigation noise.
                if 'hfpappexternal.fda.gov' in url or 'canada.ca' in url or key=='planasa-rd':
                    doc=html.fromstring(r.text)
                    for node in doc.xpath('//script|//style'):node.drop_tree()
                    text=doc.text_content()
                (CAPTURES/(key+'.html')).write_text(r.text,encoding='utf-8')
                row['page_date']=(document.date if document else None)
        (CAPTURES/(key+'.txt')).write_text(text,encoding='utf-8')
        row.update(status='readable' if len(text)>180 and '{{data.' not in text else 'no_readable_text',
                   characters=len(text),text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                   retained_excerpt_match=bool(excerpt and normalize(excerpt) in normalize(text)))
    except Exception as exc:
        row['error']=type(exc).__name__
    return row


def main():
    p=argparse.ArgumentParser();p.add_argument('--fetch',action='store_true');args=p.parse_args()
    if not args.fetch:raise SystemExit('Explicit --fetch required; this command accesses public sources only.')
    BASE.mkdir(parents=True,exist_ok=True);CAPTURES.mkdir(parents=True,exist_ok=True)
    old=json.loads(PRIOR.read_text(encoding='utf-8'))
    specs=[(r['id'].removeprefix('ev-gene-'),r['source_name'],r['source_url'],r.get('supporting_excerpt','')) for r in old['evidence']]
    specs += [(k,p,u,'') for k,p,u in NEW if u not in {s[2] for s in specs}]
    with ThreadPoolExecutor(max_workers=4) as pool:checks=list(pool.map(fetch,specs))
    (BASE/'source-audit.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'attempted':len(checks),'status':{s:sum(r['status']==s for r in checks) for s in sorted({r['status'] for r in checks})}}))


if __name__=='__main__':main()
