"""Human expected-name inputs remain private and do not accept source copies."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.audit_variety_name_recall import score_case
from scripts.prepare_variety_recall_review import assemble, prepare, private_output, render_worksheet, write_new


def inputs(tmp_path):
    data=tmp_path/'data'
    inbox=tmp_path/'runtime'
    (data/'evidence').mkdir(parents=True)
    (inbox/'source_fidelity/artifacts').mkdir(parents=True)
    record=dict(id='ev-one', title='Blueberry source', status='published', berry_ids=['berry-blueberry'],
                source_url='https://example.test/profile',summary='Blueberry varieties include Summary Ghost.')
    artifact=dict(evidence_id='ev-one', artifact_type='article', source_title=record['title'],
        source_url=record['source_url'], body_sha256='captured-body-hash', language='en',
        review=dict(status='pending'), artifact=dict(article=dict(full_text="Blueberry varieties include 'Named'.",
        paragraphs=[dict(text="Blueberry varieties include 'Named'.")])))
    (data/'evidence/ev-one.json').write_text(json.dumps(record),encoding='utf-8')
    path=inbox/'source_fidelity/artifacts/ev-one.json'
    path.write_text(json.dumps(artifact),encoding='utf-8')
    return data,inbox,path


def packet(data,inbox):
    return prepare(runtime_inbox=inbox,data_dir=data,review_base_url='http://127.0.0.1:8000')


def completed(data,inbox):
    result=packet(data,inbox)
    result['reviewer']='Independent test reviewer'
    result['cases'][0].update(expected_review_complete=True,expected=[dict(name='Named',berry_id='berry-blueberry')])
    return result


def test_preparation_contains_only_source_metadata_and_never_detector_answers(tmp_path):
    data,inbox,path=inputs(tmp_path)
    before={p:p.read_bytes() for parent in (data,inbox) for p in parent.rglob('*.json')}
    result=packet(data,inbox)
    assert result['cases'][0]['expected'] is None and not result['cases'][0]['expected_review_complete']
    assert result['cases'][0]['source_copy_review']=='pending'
    assert result['cases'][0]['saved_copy_url']=='http://127.0.0.1:8000/source-fidelity/ev-one?name_review=1'
    assert "Blueberry varieties include" not in json.dumps(result)
    assert not {'mentions','detected_names','canonical_variety_id','article','inputs'} & result['cases'][0].keys()
    assert {p:p.read_bytes() for parent in (data,inbox) for p in parent.rglob('*.json')}==before
    with pytest.raises(ValueError,match='complete'):
        assemble(review={**result,'reviewer':'Test'},runtime_inbox=inbox,data_dir=data)


def test_supplied_answers_use_existing_offline_scorer_without_any_gate_or_data_writes(tmp_path):
    data,inbox,path=inputs(tmp_path)
    before=path.read_bytes()
    answer=completed(data,inbox)
    supplied=deepcopy(answer)
    result=assemble(review=answer,runtime_inbox=inbox,data_dir=data)
    assert result['qualification_approved'] is False and 'separate' in result['review_status']
    assert result['cases'][0]['human_review']['source_copy_review']=='pending'
    assert result['cases'][0]['inputs']['source_text_records'][0]['status']=='in_review'
    assert score_case(result['cases'][0])['detected_names']==1
    assert 'summary' not in result['cases'][0]['inputs']['source_text_records'][0]
    assert result['cases'][0]['inputs']['source_text_records'][0]['title']=='Blueberry source'
    assert path.read_bytes()==before and answer==supplied


def test_intentional_zero_names_is_distinct_from_an_unfinished_empty_list(tmp_path):
    data,inbox,path=inputs(tmp_path)
    answer=completed(data,inbox)
    answer['cases'][0]['expected']=[]
    assert assemble(review=answer,runtime_inbox=inbox,data_dir=data)['cases'][0]['expected']==[]
    answer['cases'][0]['expected_review_complete']=False
    with pytest.raises(ValueError,match='completed'):
        assemble(review=answer,runtime_inbox=inbox,data_dir=data)


@pytest.mark.parametrize('change', ['body','url','title','language','missing_case','duplicate_case','bad_berry','duplicate_name','approval_field','blank_reviewer'])
def test_changed_inputs_or_incomplete_unsafe_answers_are_refused(tmp_path,change):
    data,inbox,path=inputs(tmp_path)
    answer=completed(data,inbox)
    row=answer['cases'][0]
    if change in ('body','url','title','language'):
        artifact=json.loads(path.read_text(encoding='utf-8'))
        if change=='body':artifact['artifact']['article']['paragraphs'][0]['text']='Changed source text'
        elif change=='url':artifact['source_url']='https://example.test/changed'
        elif change=='title':artifact['source_title']='Different captured title'
        else:artifact['language']='different'
        path.write_text(json.dumps(artifact),encoding='utf-8')
    elif change=='missing_case':answer['cases']=[]
    elif change=='duplicate_case':answer['cases'].append(deepcopy(row))
    elif change=='bad_berry':row['expected'][0]['berry_id']='berry-guessed'
    elif change=='duplicate_name':row['expected'].append(dict(name='NAMED',berry_id='berry-strawberry'))
    elif change=='approval_field':row['expected'][0]['human_qualified']=True
    elif change=='blank_reviewer':answer['reviewer']=' '
    with pytest.raises(ValueError):
        assemble(review=answer,runtime_inbox=inbox,data_dir=data)


def test_source_acceptance_change_does_not_stale_unchanged_body_or_approve_the_benchmark(tmp_path):
    data,inbox,path=inputs(tmp_path)
    answer=completed(data,inbox)
    artifact=json.loads(path.read_text(encoding='utf-8'))
    artifact['review']['status']='affirmed'
    path.write_text(json.dumps(artifact),encoding='utf-8')
    result=assemble(review=answer,runtime_inbox=inbox,data_dir=data)
    assert result['cases'][0]['human_review']['source_copy_review']=='affirmed'
    assert result['qualification_approved'] is False


def test_empty_runtime_and_wrong_source_identity_are_not_successful_packets(tmp_path):
    data,inbox,path=inputs(tmp_path)
    artifact=json.loads(path.read_text(encoding='utf-8'))
    artifact['evidence_id']='../outside'
    path.write_text(json.dumps(artifact),encoding='utf-8')
    with pytest.raises(ValueError):packet(data,inbox)
    path.unlink()
    with pytest.raises(ValueError,match='No explicit'):packet(data,inbox)


def test_private_output_and_html_escaping_prevent_publication_or_markup_execution(tmp_path):
    assert private_output(tmp_path/'inbox/packet',root=tmp_path)==tmp_path/'inbox/packet'
    for target in ('data','benchmarks','generated','outside'):
        with pytest.raises(ValueError,match='private'):
            private_output(tmp_path/target/'packet',root=tmp_path)
    data,inbox,path=inputs(tmp_path)
    result=packet(data,inbox)
    result['cases'][0]['title']='</script><img src=x onerror=alert(1)>'
    html=render_worksheet(result)
    assert '\\u003c/script\\u003e' in html and '<img src=x' not in html
    assert 'Blueberry varieties include' not in html and '__PACKET_JSON__' not in html
    assert 'fetch(' not in html and 'XMLHttpRequest' not in html


def test_export_never_overwrites_existing_human_answers_or_escapes_its_folder(tmp_path):
    folder=tmp_path/'packet'
    folder.mkdir()
    target=folder/'worksheet.json'
    write_new(target,'keep my answers',folder=folder)
    with pytest.raises(FileExistsError):
        write_new(target,'replace them',folder=folder)
    assert target.read_text(encoding='utf-8')=='keep my answers'
    with pytest.raises(ValueError,match='inside'):
        write_new(tmp_path/'outside.json','wrong destination',folder=folder)
    assert not (tmp_path/'outside.json').exists()


@pytest.mark.parametrize('url',['javascript:alert(1)','https://user:password@example.test','http://127.0.0.1:8000?token=x'])
def test_bad_review_link_is_not_embedded(tmp_path,url):
    data,inbox,path=inputs(tmp_path)
    with pytest.raises(ValueError):
        prepare(runtime_inbox=inbox,data_dir=data,review_base_url=url)
