"""Human-affirmed source recovery → private reading → identity leads, never trust."""
from copy import deepcopy
import json

import pytest

from app import main
from app.services import source_reading
from app.services.feed_first_reader import save_capture
from app.services.source_fidelity_recovery import (
    build_recovery_artifact, candidate_from_record, decide_recovery_artifact, match_recoveries,
)
from app.services.variety_universe.article_sources import available_article_sources
from tests.test_personal_digest import article, workspace
from tests.test_captured_article_variety_coverage import scan


TEXT = ('Blueberry varieties include Reviewed Blue and Horizon Blue. The breeder describes its trial programme. '
        'This is a fictional acceptance source for checking article reading and variety-name discovery. '
        'It does not describe real cultivars, company operations, growing regions or commercial performance. '
        'The stored source summary stays separate from the original paragraphs, and reading the article does '
        'not approve any claim. These words are retained exactly so the check can detect accidental rewriting '
        'or a fallback to the publication summary rather than the saved original article.')


def recovery(record, *, decision='affirmed'):
    rich = {**record, 'article': {'paragraphs':[{'index':0,'text':TEXT}],
                                 'image_url':'https://publisher.example/recovered-blueberry.jpg'}}
    candidate = candidate_from_record(rich, recovery_source='acceptance_fixture', locator='private/fixture.json')
    assert candidate is not None
    result = match_recoveries([record], [candidate])[0]
    artifact = build_recovery_artifact(result, record)
    if decision != 'pending':
        artifact = decide_recovery_artifact(artifact, record, decision=decision, reviewer='Acceptance test')
    return artifact


def persist(inbox, record, artifact):
    path = inbox/'source_fidelity'/'artifacts'/(record['id']+'.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact), encoding='utf-8')
    return path


def test_affirmed_reading_keeps_exact_source_body_and_semantic_metadata(tmp_path):
    record = article()
    artifact = recovery(record)
    path = persist(tmp_path, record, artifact)
    before, original = path.read_bytes(), deepcopy(record)
    resolved = source_reading.reviewed_original_for_reading(record, tmp_path)
    assert resolved['article'] == artifact['artifact']['article']
    assert resolved['reader_source_recovery']['state'] == 'affirmed'
    assert all(resolved[field] == record[field] for field in ('status','summary','entity_ids','berry_ids','review_state'))
    assert record == original and path.read_bytes() == before


@pytest.mark.parametrize('decision', ['pending','rejected','needs_investigation'])
def test_unaffirmed_recoveries_never_supply_article_text(tmp_path, decision):
    record = article()
    path = persist(tmp_path, record, recovery(record, decision=decision))
    before = path.read_bytes()
    assert source_reading.reviewed_original_for_reading(record, tmp_path) == record
    assert path.read_bytes() == before


@pytest.mark.parametrize('change', [
    {'evidence_id':'ev-another'}, {'source_url':'https://another.example/story'},
    {'trusted_identity_sha256':'0'*64}, {'source_fidelity_artifact_schema_version':2},
    {'source_artifact_sha256':'0'*64}, {'artifact': {'article': {'full_text':'Changed source prose'}}},
    {'review':{'status':'affirmed','reviewed_by':'','reviewed_at':'2026-10-08'}},
    {'review':{'status':'affirmed','reviewed_by':'Acceptance test'}},
])
def test_stale_wrong_identity_and_changed_bodies_are_not_read(tmp_path, change):
    record = article()
    artifact = recovery(record)
    artifact.update(change)
    path = persist(tmp_path, record, artifact)
    before = path.read_bytes()
    resolved = source_reading.reviewed_original_for_reading(record, tmp_path)
    assert 'article' not in resolved and resolved['reader_source_recovery']['state'] == 'unavailable'
    assert path.read_bytes() == before


def test_canonical_identity_edit_invalidates_old_affirmation(tmp_path):
    record = article()
    persist(tmp_path, record, recovery(record))
    record['title'] = 'Corrected publication identity'
    assert 'article' not in source_reading.reviewed_original_for_reading(record, tmp_path)


def test_operator_text_and_pending_or_atomic_records_never_open_recovery(tmp_path, monkeypatch):
    record = article()
    persist(tmp_path, record, recovery(record))
    monkeypatch.setattr(source_reading.Path,'read_text',lambda *args,**kwargs:pytest.fail('Opened an ineligible recovery'))
    for overrides in ({'article':{'full_text':'Operator-written original text.'}},
                      {'status':'draft'}, {'evidence_role':'atomic_evidence'}, {'id':'../outside'}):
        protected = {**record, **overrides}
        assert source_reading.reviewed_original_for_reading(protected, tmp_path) == protected


def test_malformed_oversized_and_linked_recoveries_fail_closed(tmp_path, monkeypatch):
    record = article()
    path = persist(tmp_path, record, recovery(record))
    path.write_text('{broken}',encoding='utf-8')
    assert 'article' not in source_reading.reviewed_original_for_reading(record,tmp_path)
    persist(tmp_path, record, recovery(record))
    monkeypatch.setattr(source_reading,'MAX_RECOVERY_BYTES',10)
    assert 'article' not in source_reading.reviewed_original_for_reading(record,tmp_path)
    monkeypatch.setattr(source_reading,'MAX_RECOVERY_BYTES',4_000_000)
    monkeypatch.setattr(source_reading.Path,'is_symlink',lambda *args:True)
    assert 'article' not in source_reading.reviewed_original_for_reading(record,tmp_path)


def test_private_variety_audit_uses_affirmed_body_not_reader_refresh(tmp_path):
    record = article()
    path = persist(tmp_path,record,recovery(record))
    before = path.read_bytes()
    save_capture(tmp_path, record['id'], {'item_id':record['id'],'requested_url':record['source_url'],
        'ok':True,'availability':'partial','passages':['Blueberry varieties include Unreviewed Refresh.']})
    selected, counts = available_article_sources([record],tmp_path)
    assert counts['readable_sources'] == counts['affirmed_recoveries'] == 1
    assert counts['reader_captures'] == counts['recovery_issues'] == 0
    report = scan(selected)
    assert {row['candidate_name'] for row in report['candidates']} == {'Reviewed Blue','Horizon Blue'}
    assert all(not row['auto_confirmed'] for row in report['candidates'])
    assert path.read_bytes() == before and 'article' not in record


def test_live_personal_and_legacy_readers_use_reviewed_body_but_feeds_do_not(workspace, monkeypatch):
    client, _ = workspace
    record = article()
    path = persist(main.INBOX_DIR,record,recovery(record))
    before = path.read_bytes()
    monkeypatch.setattr(main,'load_publication_transcript_readiness',lambda *args:{})
    for route in (f'/intelligence/{record["id"]}?personal=1', f'/api/intelligence/{record["id"]}/reader?personal=1',
                  f'/intelligence/{record["id"]}',f'/api/intelligence/{record["id"]}/reader'):
        response = client.get(route)
        assert response.status_code == 200 and TEXT in response.text and 'Source text checked' in response.text
    assert path.read_bytes() == before
    assert TEXT not in client.get('/today').text and TEXT not in client.get('/digest').text
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    monkeypatch.setattr(source_reading,'reviewed_original_for_reading',lambda *args,**kwargs:pytest.fail('Public view opened recovery'))
    for route in (f'/intelligence/{record["id"]}?personal=1', f'/api/intelligence/{record["id"]}/reader?personal=1',
                  f'/intelligence/{record["id"]}',f'/api/intelligence/{record["id"]}/reader'):
        assert TEXT not in client.get(route).text


def test_review_reset_is_visible_next_read_and_invalid_copy_has_clear_private_notice(workspace):
    client, _ = workspace
    record = article()
    artifact = recovery(record)
    path = persist(main.INBOX_DIR,record,artifact)
    route = f'/api/intelligence/{record["id"]}/reader?personal=1'
    assert TEXT in client.get(route).text
    artifact['review']['status'] = 'pending'
    persist(main.INBOX_DIR,record,artifact)
    assert TEXT not in client.get(route).text
    artifact['review']['status'] = 'affirmed'
    artifact['source_artifact_sha256'] = '0'*64
    persist(main.INBOX_DIR,record,artifact)
    response = client.get(route)
    assert TEXT not in response.text and 'A saved source copy couldn’t be verified.' in response.text
    assert '/source-fidelity/ev-digest' in response.text and str(path) not in response.text


def test_review_confirmation_controls_reading_without_publishing_new_claims(workspace):
    client, repos = workspace
    record = article()
    path = persist(main.INBOX_DIR,record,recovery(record,decision='pending'))
    before = path.read_bytes()
    route = f'/api/intelligence/{record["id"]}/reader?personal=1'
    decision = f'/source-fidelity/{record["id"]}/decision'
    assert TEXT not in client.get(route).text
    refused = client.post(decision,data={'decision':'affirmed','reviewer':'Acceptance test'},follow_redirects=False)
    assert refused.status_code == 303 and 'confirm_error=1' in refused.headers['location']
    assert path.read_bytes() == before and TEXT not in client.get(route).text
    accepted = client.post(decision,data={'decision':'affirmed','reviewer':'Acceptance test','confirm_affirm':'1'},follow_redirects=False)
    assert accepted.status_code == 303 and json.loads(path.read_text(encoding='utf-8'))['review']['status'] == 'affirmed'
    assert TEXT in client.get(route).text
    assert repos.evidence.get(record['id']) == record
    assert repos.facts.list() == []
    assert not (main.INBOX_DIR/'qualifications').exists()
    rejected = client.post(decision,data={'decision':'rejected','reviewer':'Acceptance test'},follow_redirects=False)
    assert rejected.status_code == 303 and TEXT not in client.get(route).text
    assert repos.evidence.get(record['id']) == record
