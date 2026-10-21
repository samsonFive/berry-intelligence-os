"""Only test feed URLs explicitly advertised by fetched publisher HTML."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urljoin
from lxml import html
import httpx
import feedparser

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/imports/gene-editing-2026-10-20'

def main():
    checks=json.loads((BASE/'source-checks.json').read_text(encoding='utf-8'))
    candidates={}
    for row in checks:
        path=ROOT/'inbox/gene-editing-captures'/f"{row['key']}.html"
        if not path.exists():
            continue
        for node in html.fromstring(path.read_text(encoding='utf-8')).xpath('//link[@rel="alternate"]'):
            if node.get('type') in ('application/rss+xml','application/atom+xml') and node.get('href'):
                candidates.setdefault(urljoin(row['url'],node.get('href')),[]).append(row['key'])
    def check(pair):
        url,keys=pair
        row={'url':url,'advertised_by':keys,'checked_at':datetime.now(timezone.utc).isoformat()}
        try:
            response=httpx.get(url,timeout=40,follow_redirects=True)
            parsed=feedparser.parse(response.content)
            row.update(http_status=response.status_code,entries=len(parsed.entries),
                status='verified' if response.status_code==200 and parsed.version and parsed.entries else 'unverified')
        except Exception as exc:
            row.update(status='blocked',error=type(exc).__name__)
        return row
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(check,candidates.items()))
    (BASE/'feed-checks.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(results))

if __name__=='__main__':
    main()
