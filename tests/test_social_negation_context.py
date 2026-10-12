import json
from pathlib import Path
import pytest
from app.services.social_intelligence.extraction import analyze

ROWS=json.loads((Path(__file__).resolve().parents[1]/'benchmarks/social-blueberry-fixtures.json').read_text(encoding='utf-8'))['records']

@pytest.mark.parametrize('native_id,expected',[('demo-en-6','not sweet'),('demo-es-5','no dulce'),('demo-pt-5','não doce'),('demo-zh-5','不甜'),('demo-ja-5','甘いわけではない')])
def test_negation_has_inspectable_exact_context(native_id,expected):
    row=next(r for r in ROWS if r['native_id']==native_id)
    aspect=next(a for a in analyze(row,[])['aspects'] if a['aspect']=='flavor')
    assert aspect['sentiment']=='uncertain'
    hit=aspect['evidence'][0];span=hit['negation_context']
    assert span['text']==expected==row['text'][span['start']:span['end']]
    assert row['text'][hit['span']['start']:hit['span']['end']]==hit['span']['text']


def test_unnegated_sweetness_does_not_claim_negation():
    row=dict(ROWS[0],text='Blueberries are sweet.',language='en')
    aspect=next(a for a in analyze(row,[])['aspects'] if a['aspect']=='flavor')
    assert aspect['sentiment']=='positive'
    assert 'negation_context' not in aspect['evidence'][0]
