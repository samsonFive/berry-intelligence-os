"""Explicit, resumable mission research. Never runs during tests or imports.

Uses public queries only; credentials stay in the environment. Existing Search
client is the follow-up transport. Deep Research is attempted before fallback.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import httpx
from app.services.ai_gateway.perplexity_search import PerplexitySearchClient

COMPANIES = {
    "simplot": "J.R. Simplot Company / Simplot Plant Sciences",
    "plant-sciences": "Plant Sciences Inc Watsonville PSI Plant Sciences Genetics PSG",
    "ohalo": "Ohalo Genetics Boosted Breeding strawberry consortium",
    "pairwise": "Pairwise Plants Fulcrum berries seedless blackberry PSI",
    "hudson-river": "Hudson River Biotechnology HRB strawberry Plantik",
    "plantik": "Plantik Biosciences strawberry heat tolerance",
    "fall-creek": "Fall Creek Farm Nursery blueberry breeding gene editing",
    "planasa": "Planasa Group berry breeding gene editing",
    "heritable": "Heritable Agriculture heritable.ag genome editing",
    "qi-biodesign": "Qi Biodesign 齐禾生科 genome editing",
    "shunfeng": "Shandong Shunfeng Biotechnology 山东舜丰生物科技有限公司 舜丰生物 KWS",
}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT/'data/imports/gene-editing-2026-10-20/research')
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--retry-deep', action='store_true', help='Retry only snapshots with failed Deep Research; preserve searches')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    key = os.environ.get('PERPLEXITY_API_KEY', '')
    if not key:
        raise SystemExit('PERPLEXITY_API_KEY is not configured')
    def run(pair):
        slug, name = pair
        path = args.output/f'{slug}.json'
        previous = json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
        if previous and (not args.retry_deep or previous.get('deep_research')):
            return
        prompt = (f'Deep investigation of {name} as of October 20 2026. Resolve official domain, legal identity, aliases, parents and subsidiaries. '
                  'Investigate plant editing versus conventional/advanced breeding, technologies, crops, berry programs, traits, named products, '
                  'partners (especially PSI, Simplot, Pairwise, Plantik, HRB, Fall Creek, Planasa), IP licenses, financing, dated historical and latest milestones, '
                  'program geography distinct from HQ, commercial availability and regulatory status by product/jurisdiction/date. '
                  'Use original company/partner announcements, papers, patents and regulators; use native Chinese for Chinese companies. '
                  'Provide source URLs, dates, short exact supporting excerpts, attribution, conflicts and evidence gaps. '
                  'Do not equate Boosted Breeding with CRISPR or assume all roster companies edit berries. Distinguish announced versus demonstrated/field-tested/commercial. '
                  'Explicitly say not established in this research pass when evidence is missing. Exclude anything after October 20 2026.')
        result = previous or {'company':name, 'executed_at':datetime.now(timezone.utc).isoformat(), 'query':prompt, 'passes':[]}
        try:
            response = httpx.post('https://api.perplexity.ai/chat/completions',
                headers={'Authorization':'Bearer '+key},
                json={'model':'sonar-deep-research','messages':[{'role':'user','content':prompt}],
                      'max_tokens':6500}, timeout=900)
            if response.status_code == 200:
                result['deep_research'] = response.json()
                result['capability'] = 'sonar-deep-research'
                result.pop('deep_research_blocker', None)
            else:
                result['deep_research_blocker'] = f'HTTP {response.status_code}'
                result.setdefault('attempts', []).append({'status': response.status_code, 'at': datetime.now(timezone.utc).isoformat()})
                result['capability'] = 'iterative Perplexity Search API'
        except httpx.HTTPError as exc:
            result['deep_research_blocker'] = type(exc).__name__
            result['capability'] = 'iterative Perplexity Search API'
        # Two focused follow-up passes per company, even when Deep Research succeeds.
        client = PerplexitySearchClient(api_key=key, timeout_seconds=60)
        for query in [f'{name} official company identity technology berry breeding CRISPR partnership licensing',
                      f'{name} 2025 2026 strawberry blueberry genome editing commercialization milestones research evidence']:
            if any(p.get('query') == query and p.get('hits') for p in result['passes']):
                continue
            try:
                result['passes'].append(asdict(client.search(query,max_results=8)))
            except Exception as exc:
                result['passes'].append({'query':query,'blocker':type(exc).__name__})
        path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(slug, result['capability'], flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(run, COMPANIES.items()))

if __name__ == '__main__':
    main()
