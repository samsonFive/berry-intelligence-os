"""Measured language-specific fixture evaluation; no live/model calls."""
import json
from collections import defaultdict
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.services.social_intelligence.extraction import analyze, VERSION

def evaluate():
    fixture=json.loads((ROOT/'benchmarks/social-blueberry-fixtures.json').read_text(encoding='utf-8'))
    entities=[json.loads(p.read_text(encoding='utf-8')) for p in (ROOT/'data/entities').rglob('*.json')]
    # Explicitly synthetic identity ambiguity, never canonical registry additions.
    entities+=fixture.get('evaluation_entities',[])
    scores=defaultdict(lambda:{'cases':0,'checks':0,'correct':0,'errors':[]})
    for row,expected in zip(fixture['records'],fixture['expected'],strict=True):
        actual=analyze(row,entities)
        prediction={'relevance':actual['relevance'],'retailers':sorted({(r['name'],r['relation']) for r in actual['retailers']}),
          'aspects':{a['aspect']:a['sentiment'] for a in actual['aspects']},
          'entity_ids':sorted({l['entity_id'] for l in actual['entity_links']}),
          'purchase_market':(row.get('purchase_market') or {}).get('value'),
          'fruit_origin':(row.get('fruit_origin') or {}).get('value'),
          'author_geography':(row.get('author_geography') or {}).get('value')}
        report=scores[row['language']];report['cases']+=1
        for field,target in expected.items():
            if field=='retailers':target=[tuple(v) for v in target]
            report['checks']+=1
            if prediction[field]==target:report['correct']+=1
            else:report['errors'].append({'native_id':row['native_id'],'field':field,'expected':target,'actual':prediction[field]})
    return {'version':VERSION,'dataset':'Synthetic labeled blueberry pilot; not independent human gold or representative population',
        'by_language':{lang:{**r,'accuracy':round(r['correct']/r['checks'],4)} for lang,r in scores.items()},
        'live_sample':{'cases':0,'performance':None,'reason':'No independently graded live cases. Trial collection exists separately; no live extraction performance claim.'}}

if __name__=='__main__':
    result=evaluate();out=ROOT/'artifacts/social-blueberry/evaluation.json';out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))
