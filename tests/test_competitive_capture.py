import json

from app.services.living_workspaces import Store
from app.services.personal_digest import retained_news, source_records
from app.services.competitive_feed import select
from scripts.capture_competitive_sources import capture
from tests.test_competitive_evaluation import research


def test_real_capture_path_replay_reader_identity_and_explicit_destination(research):
    inbox, entities, _, _, _, _, _ = research
    entities['uk'] = {'id':'uk', 'entity_type':'geography'}
    selection = [{'batch_id':'B16', 'source_id':'B16-S001', 'destination_market_ids':['uk'],
                  'destination_rationale':'Explicit fruit destination in selected original source'}]
    first = capture(inbox, selection, entities=entities)
    second = capture(inbox, selection, entities=entities)
    assert first == second == {'retained_captures':1, 'selected_sources':1}
    record = retained_news(inbox)[0]
    assert record['published_date'] is None
    assert record['status'] == 'unreviewed'
    previews = source_records([], inbox, metadata_only=True)
    assert next(iter(previews.values()))['destination_market_ids'] == ['uk']
    assert select(previews, {'berry':'berry-strawberry','destination':'uk','lane':'market'})['total'] == 1
    source = next(r for r in Store(inbox).rows('competitive_record') if r['kind']=='source')
    assert source['article_id'] == record['id']


def test_unreadable_capture_is_incomplete_index_not_false_empty(research):
    inbox, *_ = research
    path=inbox/'news_packets/captures/packet-bad.json'
    path.parent.mkdir(parents=True)
    path.write_text('{bad',encoding='utf-8')
    issues=[]
    assert source_records([], inbox, index_issues=issues) == {}
    assert len(issues)==1 and 'unreadable' in issues[0]['issue']
