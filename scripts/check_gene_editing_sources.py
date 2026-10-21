"""Fetch original public sources, keeping capture bodies private and checks dated.

No feed is inferred from a domain. HTTP success alone is not claim verification.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import httpx
import trafilatura
from pypdf import PdfReader
from dataclasses import asdict
from app.services.ai_gateway.perplexity_search import PerplexitySearchClient
import os
import argparse
from lxml import html

BASE = ROOT/'data/imports/gene-editing-2026-10-20'
CAPTURES = ROOT/'inbox/gene-editing-captures'
STARTING = [
 ('pairwise-fontana','Pairwise','https://www.pairwise.com/insights/pairwise-unveils-fontana-blackberry','en'),
 ('pairwise-seedless','Pairwise','https://www.pairwise.com/insights/pairwise-develops-first-seedless-blackberry-with-transformative-crispr-technology','en'),
 ('pairwise-hrb','Pairwise','https://www.pairwise.com/insights/hudson-river-biotechnology','en'),
 ('qi-berry','Apricot Capital','http://www.apricot-capital.com/news.html?id=843','zh'),
 ('simplot-alliance','Simplot','https://www.simplot.com/company/news/j-r-simplot-company-and-plant-sciences-inc','en'),
 ('simplot-license','Simplot','https://www.simplot.com/company/news/simplot-secures-license-from-corteva-agriscience-mit-harvard','en'),
 ('psi-research','Plant Sciences Genetics','https://www.plantsciencesgenetics.com/research','en'),
 ('psi-identity','Plant Sciences Genetics','https://www.plantsciencesgenetics.com/about-us','en'),
 ('ohalo-boosted','Ohalo','https://www.ohalo.com/news/ohalo-announces-the-discovery-of-boosted-breeding','en'),
 ('ohalo-strawberry','Ohalo','https://www.ohalo.com/strawberry-consortium','en'),
 ('ohalo-launch','Ohalo','https://www.ohalo.com/news/ohalo-strawberry-consortium-launch','en'),
 ('pairwise-home','Pairwise','https://www.pairwise.com/','en'),
 ('pairwise-news','Pairwise','https://www.pairwise.com/insights','en'),
 ('pairwise-psi','Pairwise','https://www.pairwise.com/insights/pairwise-and-plant-sciences-inc-psi-to-partner-to-bring-new-varieties-of-black-raspberries-red-raspberries-and-blackberries-to-market-in-the-u-s','en'),
 ('pairwise-2026','Pairwise','https://www.pairwise.com/insights/the-proof-is-in-the-products-january-2026','en'),
 ('hrb-plantik','Hudson River Biotechnology','https://www.hudsonriver.bio/news/hudson-river-and-plantik-partner-to-enhance-heat-tolerance-in-strawberries','en'),
 ('hrb-regeneration','Hudson River Biotechnology','https://www.hudsonriver.bio/news/hrb-achieves-major-crispr-breakthrough-first-ever-regeneration-of-strawberries-from-gene-edited','en'),
 ('hrb-partnering','Hudson River Biotechnology','https://www.hudsonriver.bio/partnering','en'),
 ('plantik-tech','Plantik Biosciences','https://www.plantik.bio/technology/','en'),
 ('plantik-about','Plantik Biosciences','https://www.plantik.bio/aboutus','en'),
 ('plantik-trade','AgFunderNews','https://agfundernews.com/exclusive-plantik-and-hudson-river-biotechnology-team-up-to-de-risk-heat-tolerant-strawberries','en'),
 ('plantik-hortidaily','HortiDaily','https://www.hortidaily.com/article/9877481/plantik-and-hudson-river-biotechnology-team-up-to-de-risk-heat-tolerant-strawberries/','en'),
 ('fall-creek-home','Fall Creek','https://www.fallcreeknursery.com/','en'),
 ('fall-creek-collection','Fall Creek','https://www.fallcreeknursery.com/variety-innovations/fall-creek-collection','en'),
 ('planasa-about','Planasa','https://planasa.com/about-us/','en'),
 ('planasa-news','Planasa','https://planasa.com/blog/','en'),
 ('heritable-home','Heritable Agriculture','https://heritable.ag/','en'),
 ('heritable-products','Heritable Agriculture','https://heritable.ag/products','en'),
 ('heritable-strawberry','Heritable Agriculture','https://heritable.ag/press-releases/heritable-strawberries.pdf','en'),
 ('qi-funding','Qi Biodesign / PR Newswire','https://www.prnewswire.com/news-releases/qi-biodesign-completes-75-million-in-total-funding-to-drive-genome-editing-innovations-302324632.html','en'),
 ('qi-official','Qi Biodesign','http://www.qi-biodesign.com/','zh'),
 ('qi-license','Vilmorin & Cie','https://api.vilmorincie.com/uploads/202607_Press_release_VCO_NGT_EN_229637ccd2.pdf','en'),
 ('qi-lab','Beijing International Science & Technology Innovation Center','https://www.ncsti.gov.cn/kjdt/scyq/wlkxc/wldt/202601/t20260121_236092.html','zh'),
 ('shunfeng-official','Shunfeng Bio / BellaGen','http://bellagen.cn/en/index.php?catid=18','en'),
 ('shunfeng-chinese','舜丰生物','http://bellagen.cn/','zh'),
 ('shunfeng-kws','KWS','https://www.kws.com/corp/en/media-press/news-2025/kws-and-shunfeng-bio-sign-worldwide-licensing-agreement/','en'),
 ('shunfeng-kws-de','KWS','https://www.kws.com/corp/de/medien-presse/news-2025/kws-und-shunfeng-bio-unterzeichnen-weltweite-lizenzvereinbarung/','de'),
 ('uk-simplot','Defra','https://www.gov.uk/government/publications/precision-bred-organism-marketing-notice-reference-pbm26fran008/precision-bred-organism-marketing-notice-reference-pbm26fran008','en'),
 ('us-qi','USDA APHIS','https://www.aphis.usda.gov/sites/default/files/24-116-02rsr.pdf','en'),
 ('us-simplot','USDA APHIS','https://www.aphis.usda.gov/sites/default/files/20-168-05_air_response_signed.pdf','en'),
 ('us-fda','FDA','https://www.fda.gov/food/agricultural-biotechnology/genome-editing-agricultural-biotechnology','en'),
 ('eu-ngt','European Commission','https://food.ec.europa.eu/plants/genetically-modified-organisms/new-techniques-biotechnology_en','en'),
]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--skip-perplexity',action='store_true')
    args=parser.parse_args()
    BASE.mkdir(parents=True,exist_ok=True)
    CAPTURES.mkdir(parents=True,exist_ok=True)
    prior = BASE/'source-checks.json'
    old = {r['key']:r for r in json.loads(prior.read_text(encoding='utf-8'))} if prior.exists() else {}
    def fetch(spec):
        key,publisher,url,language = spec
        if key in old:
            return old[key]
        item = {'key':key,'publisher':publisher,'url':url,'language':language,
                'accessed_at':datetime.now(timezone.utc).isoformat(),'method':'public HTTP GET / original source'}
        try:
            response = httpx.get(url, follow_redirects=True, timeout=45, headers={'User-Agent':'BerryIntelligenceResearch/1.0'})
            item.update(http_status=response.status_code, canonical_url=str(response.url))
            if response.status_code != 200:
                item['status']='blocked' if response.status_code in (401,403,429) else 'unavailable'
                return item
            if 'application/pdf' in response.headers.get('content-type','') or url.endswith('.pdf'):
                text='\n'.join(page.extract_text() or '' for page in PdfReader(BytesIO(response.content)).pages)
                title = key
                CAPTURES.joinpath(key+'.pdf').write_bytes(response.content)
                metadata_date = None
            else:
                # Extract original prose; never accept scripts or consent pages as claims.
                document=trafilatura.bare_extraction(response.text, url=str(response.url),with_metadata=True)
                text=(document.text if document else '') or ''
                if 'pairwise.com/insights/' in url:
                    nodes=html.fromstring(response.text).xpath('//div[contains(concat(" ",normalize-space(@class)," ")," article-content ")]')
                    if nodes:
                        text=nodes[-1].text_content()
                title=(document.title if document else '') or key
                metadata_date=(document.date if document else None)
                CAPTURES.joinpath(key+'.html').write_text(response.text,encoding='utf-8')
            item.update(status='readable' if len(text)>180 and '{{data.' not in text else 'no_readable_text', title=title,
                        published_date=metadata_date, text_sha256=hashlib.sha256(text.encode()).hexdigest(),characters=len(text))
            CAPTURES.joinpath(key+'.txt').write_text(text,encoding='utf-8')
        except Exception as exc:
            item.update(status='unavailable',error=type(exc).__name__)
        return item
    with ThreadPoolExecutor(max_workers=4) as pool:
        checks=list(pool.map(fetch,STARTING))
    prior.write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({s:sum(r['status']==s for r in checks) for s in {r['status'] for r in checks}}))
    cross=BASE/'research/cross-company.json'
    if not args.skip_perplexity and not cross.exists():
        client=PerplexitySearchClient(api_key=os.environ['PERPLEXITY_API_KEY'],timeout_seconds=60)
        queries=['Simplot PSI Plant Sciences Genetics PSG Pairwise strawberry blackberry partnership legal restructuring',
                 'Hudson River Plantik Pairwise Fulcrum license strawberry September 2026',
                 'Fall Creek Planasa CRISPR gene editing partnership evidence conventional breeding',
                 '齐禾生科 舜丰生物 蓝莓 草莓 基因编辑 2026 合作 官方']
        results=[]
        for q in queries:
            try:
                results.append(asdict(client.search(q,max_results=8)))
            except Exception as exc:
                results.append({'query': q, 'blocker': type(exc).__name__, 'detail': str(exc)})
                break  # No repeated quota/auth failures and no alternative provider.
        cross.write_text(json.dumps({'executed_at':datetime.now(timezone.utc).isoformat(),'capability':'Perplexity Search API cross-company follow-ups','passes':results},ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':
    main()
