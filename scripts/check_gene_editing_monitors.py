"""Exercise the existing free news_search_rss adapter for company monitoring.

This is source acquisition, not a substitute for the incomplete Perplexity
research. Topic tagging remains independent of these company queries.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlencode
import httpx
import feedparser

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/imports/gene-editing-2026-10-20'
NAMES={'simplot':'"Simplot" (strawberry OR breeding OR CRISPR)',
       'plant-sciences':'("Plant Sciences Inc" OR "Plant Sciences Genetics") (berry OR breeding)',
       'ohalo':'"Ohalo" (breeding OR strawberry OR potato)',
       'pairwise':'"Pairwise" (plant OR berry OR CRISPR)',
       'hudson-river':'"Hudson River Biotechnology"', 'plantik':'"Plantik" (plant OR strawberry OR breeding)',
       'fall-creek':'"Fall Creek" (blueberry OR nursery)', 'planasa':'"Planasa" (berry OR breeding OR nursery)',
       'heritable':'"Heritable Agriculture"', 'qi-biodesign':'"Qi Biodesign" OR "齐禾生科"',
       'shunfeng':'"Shunfeng Bio" OR "舜丰生物"'}

def main():
    def fetch(pair):
        slug,query=pair
        url='https://news.google.com/rss/search?'+urlencode({'q':query,'hl':'en-US','gl':'US','ceid':'US:en'})
        row={'slug':slug,'query':query,'feed_url':url,'adapter':'news_search_rss','checked_at':datetime.now(timezone.utc).isoformat()}
        try:
            response=httpx.get(url,timeout=40,follow_redirects=True)
            parsed=feedparser.parse(response.content)
            row.update(http_status=response.status_code,feed_version=parsed.version,entries=len(parsed.entries),
                status='verified' if response.status_code==200 and parsed.version else 'unverified',
                sample=[{'title':e.get('title'),'url':e.get('link'),'published':e.get('published')} for e in parsed.entries[:3]])
        except Exception as exc:
            row.update(status='blocked',error=type(exc).__name__)
        return row
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows=list(pool.map(fetch,NAMES.items()))
    (BASE/'monitor-checks.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print({status:sum(r['status']==status for r in rows) for status in {r['status'] for r in rows}})

if __name__=='__main__':
    main()
