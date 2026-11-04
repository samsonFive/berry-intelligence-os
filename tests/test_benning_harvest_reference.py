from copy import deepcopy
import json
from pathlib import Path

from app.services.learner_visuals import presentation
from app.services.variety_portfolio_coverage import reconcile_portfolios

DATA=Path(__file__).resolve().parents[1]/'data'
SOURCE=DATA/'imports/variety-portfolio-observations-2026-11-04-benning-harvest/observations.json'
VIDEO='https://www.youtube.com/watch?v=qZP6kSEL1ao'


def test_equipment_and_crop_type_never_become_named_varieties_or_roles():
    source=json.loads(SOURCE.read_text(encoding='utf-8'))['sources'][0]
    original=deepcopy(source)
    rows,candidates=reconcile_portfolios(sources=[source],varieties=[],entities=[],candidates=[])
    assert not candidates and not rows[0]['names']
    assert not rows[0]['accounting_view']['issues']
    assert source==original and source['names']==[] and source['review_state']=='unreviewed'
    assert {row['label'] for row in source['accounting']['exclusions']}=={'Rabbiteye','KATO260'}
    capture=source['capture_reference']
    assert capture['visually_checked_pages']==[1,2,3,4,5,6]
    assert capture['printed_pages']==[53,54,55,56,57,58]
    assert capture['video_reference']['resolved_url']==VIDEO


def test_harvest_lesson_keeps_user_text_media_and_input_unchanged():
    lesson={'slug':'harvest-methods','name':'My harvest lesson','what_is_it':'My edited explanation',
            'media':[{'kind':'photo','url':'https://example.com/my-source','caption':'My credit'}]}
    original=deepcopy(lesson)
    row=presentation(lesson)
    assert lesson==original and row['what_is_it']=='My edited explanation'
    assert row['media'][0]==original['media'][0]
    videos=[media for media in row['media']if media.get('url')==VIDEO]
    assert len(videos)==1 and videos[0]['kind']=='video'
    assert videos[0]['source_page'].endswith('.pdf#page=6')
    assert 'not copied, hosted or autoplayed' in videos[0]['reuse_basis']
    assert 'image_url' not in videos[0]


def test_existing_user_video_caption_is_not_overwritten_or_duplicated():
    custom={'kind':'video','url':VIDEO,'title':'My title','caption':'My own viewing notes'}
    lesson={'slug':'harvest-methods','media':[custom]};original=deepcopy(lesson)
    row=presentation(lesson)
    assert lesson==original and row['media']==[custom]
