from pathlib import Path
import json
import pytest
from app.services.social_intelligence.extraction import analyze

BASE=json.loads((Path(__file__).resolve().parents[1]/'benchmarks/social-blueberry-fixtures.json').read_text(encoding='utf-8'))['records'][0]

@pytest.mark.parametrize('text,language',[
 ('A Raspberry Pi monitors soil moisture in blueberry plantings.','en'),
 ('Raspberry Pi controla el riego de arándanos.','es'),
 ('Raspberry Pi monitora irrigação de mirtilos.','pt'),
 ('Raspberry Pi监测蓝莓灌溉。','zh'),
 ('Raspberry Piでブルーベリーの栽培を監視する。','ja'),
])
def test_explicit_blueberry_crop_technology_stays_relevant(text,language):
    result=analyze(dict(BASE,text=text,language=language),[])
    assert result['relevance']=='relevant'
    assert result['berry_ids']==['berry-blueberry']
    assert result['entity_links']==[]

@pytest.mark.parametrize('text',[
 'A Raspberry Pi computer with a new keyboard.',
 'Blueberry is the hostname on my Raspberry Pi.',
 'Raspberry Pi soil moisture sensor without a named berry crop.',
])
def test_device_or_unspecified_crop_does_not_create_fruit_scope(text):
    result=analyze(dict(BASE,text=text,language='en'),[])
    assert result['relevance']=='excluded-nonfruit'
    assert result['berry_ids']==[]


def test_raspberry_device_name_does_not_replace_explicit_fruit_reference():
    result=analyze(dict(BASE,text='Raspberry Pi measures irrigation for raspberries.',language='en'),[])
    assert result['berry_ids']==['berry-raspberry']
