"""Offline labeled rollout evaluation; fixtures never stand in for live accuracy."""
import json,sys
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.services.social_intelligence.model import validate_intake
from app.services.social_intelligence.extraction import analyze,VERSION

def evaluate():
    dataset=json.loads((ROOT/'benchmarks/social-all-berries-fixtures.json').read_text(encoding='utf-8'))
    entities=[json.loads(p.read_text(encoding='utf-8')) for p in (ROOT/'data/entities').rglob('*.json')]
    scores=defaultdict(lambda:{'cases':0,'checks':0,'correct':0,'errors':[]})
    for raw,expected in zip(dataset['records'],dataset['expected'],strict=True):
        row=validate_intake(raw);actual=analyze(row,entities)
        prediction={'relevance':actual['relevance'],'berry_ids':actual['berry_ids'],'aspects':{a['aspect']:a['sentiment'] for a in actual['aspects']},'retailers':sorted({(r['name'],r['relation']) for r in actual['retailers']}),'entity_ids':sorted({r['entity_id'] for r in actual['entity_links']})}
        prediction.update({k:(row.get(k) or {}).get('value') for k in ('purchase_market','fruit_origin','author_geography')})
        report=scores[row['language']];report['cases']+=1
        for field,target in expected.items():
            if field=='retailers':target=[tuple(v) for v in target]
            report['checks']+=1
            if prediction[field]==target:report['correct']+=1
            else:report['errors'].append({'case':row['native_id'],'field':field,'expected':target,'actual':prediction[field]})
    return {'version':VERSION,'dataset':dataset['label'],'by_language':dict(scores),'independent_live_accuracy':{'graded_cases':0,'precision':None,'recall':None,'reason':'No independent human labels; source acquisition counts reported separately.'}}
if __name__=='__main__':
    out=ROOT/'artifacts/social-all-berries/evaluation.json';out.parent.mkdir(parents=True,exist_ok=True);result=evaluate();out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({l:{k:v for k,v in r.items() if k!='errors'} for l,r in result['by_language'].items()}))
