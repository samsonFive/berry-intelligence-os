"""Scope/quotation regressions from the source inspection; synthetic sources only."""
from app.services.topic_retrieval import match_record,plan_query,record_passages


def source(paragraphs, title='Synthetic berry study'):
    return {'id':'synthetic-scope','title':title,'source_url':'https://example.org/synthetic',
            'published_date':'2026-10-01','article':{'paragraphs':[{'index':i,'text':p}for i,p in enumerate(paragraphs)]}}


def test_pruning_question_selects_instructions_instead_of_release_counts():
    record=source(['The programme released twenty floricane blackberry varieties and licenses plants.',
                   'After harvest remove dead floricane blackberry canes. In winter prune the lateral branches.'],
                  'Synthetic blackberry pruning guide')
    row=match_record(record,plan_query('Blackberry floricane pruning'))
    assert row['relevance']=='direct'
    assert 'remove dead' in row['passage'] and 'twenty' not in row['passage']


def test_reference_entry_does_not_become_article_owned_robot_research():
    record=source(['A strawberry study describes its camera equipment.','References',
                   'Other Author. Strawberry harvesting robots: field trials. 2020. doi:10.example/reference.'])
    row=match_record(record,plan_query('Strawberry robotic harvesting field trials'))
    assert not row or row['support_status']=='scope_unverified'
    assert all('Other Author' not in p for _,p in record_passages(record))


def test_overlapping_chunks_are_not_appended_as_separate_paragraphs():
    paragraph=('Synthetic floricane blackberry licensing trial results. '*32)
    record=source([paragraph],'Synthetic floricane blackberry licensing')
    row=match_record(record,plan_query('Blackberry floricane licensing'))
    assert ';' not in row['passage_locator']
    assert row['passage'] in paragraph


def test_reprinted_study_keeps_original_year_framing():
    record=source(['An interesting 2017 study follows.','Abstract',
                   'The floricane blackberry trial compared pruning treatments and crop yield.'],
                  'Synthetic 2026 discussion')
    row=match_record(record,plan_query('Floricane blackberry developments'))
    assert '2017 study' in row['passage']
    assert row['passage_locator']=='article:0;article:1;article:2'
    assert row['relevance']=='background'


def test_blackberry_farm_and_strawberry_robot_do_not_establish_blackberry_trial():
    record=source(['This farm grows strawberries and blackberries and is trialing robotic harvesting.',
                   'The robot harvests strawberries in an outdoor field trial.'],
                  'Synthetic mixed berry farm research')
    row=match_record(record,plan_query('Blackberry robotic harvesting field trials'))
    assert not row or row['support_status']=='scope_unverified'
    strawberry=match_record(record,plan_query('Strawberry robotic harvesting field trials'))
    assert strawberry and strawberry['support_status']=='body_supported'


def test_crop_monitoring_trial_is_not_a_harvesting_trial():
    record=source(['A robotic field trial in blackberry plantings tested crop monitoring and navigation.'],
                  'Synthetic agricultural robot')
    row=match_record(record,plan_query('Blackberry robotic harvesting field trials'))
    assert not row or row['support_status']=='scope_unverified'


def test_root_zone_request_does_not_quote_overhead_cooling_as_the_intervention():
    record=source(['Raspberry trial results compared overhead cooling with shade in summer.',
                   'A separate raspberry trial reduced root-zone temperatures with mulch during summer.'])
    row=match_record(record,plan_query('Raspberry root-zone cooling summer production trials'))
    assert row and 'root-zone' in row['passage']


def test_unregistered_identifier_requires_literal_code_not_generic_crop_release():
    record=source(['A new blueberry variety was released after trials.'],'Synthetic blueberry release')
    assert not match_record(record,plan_query('Blueberry cultivar ZXQTEST-884 release announcement'))
    exact=source(['The blueberry cultivar ZXQTEST-884 was released after trials.'])
    assert match_record(exact,plan_query('Blueberry cultivar ZXQTEST-884 release announcement'))


def test_robotic_harvest_of_crop_is_a_valid_construction():
    record=source(['A field trial tested robotic harvesting of ripe strawberries.'])
    row=match_record(record,plan_query('Strawberry robotic harvesting field trials'))
    assert row and row['support_status']=='body_supported'


def test_pruning_trial_does_not_require_how_to_instruction_language():
    record=source(['A floricane blackberry trial compared pruning treatments and measured crop yield.'])
    row=match_record(record,plan_query('Blackberry floricane pruning trials'))
    assert row and row['support_status']=='body_supported'


def test_named_company_question_requires_company_in_quoted_passage():
    record=source(['Spain strawberry growers pay royalties to breeders.',
                   'Synthetic Breeder licenses strawberry varieties in Spain.'])
    entities={'company-synthetic':{'id':'company-synthetic','entity_type':'company','name':'Synthetic Breeder'}}
    row=match_record(record,plan_query('Strawberry Synthetic Breeder licensing Spain'),entities=entities)
    assert 'Synthetic Breeder' in row['passage']


def test_regional_trial_request_cannot_borrow_international_licensing():
    record=source(['A new floricane blackberry was licensed outside the United States following trials.'])
    row=match_record(record,plan_query('Blackberry floricane varieties Mediterranean trials'))
    assert not row or row['support_status']=='scope_unverified'
    positive=source(['Floricane blackberry trials in the Mediterranean compared crop yield.'])
    row=match_record(positive,plan_query('Blackberry floricane varieties Mediterranean trials'))
    assert row and row['support_status']=='body_supported'


def test_ventilation_question_does_not_quote_soil_advice():
    record=source(['Raspberry plants in high tunnels need well-drained soil and nitrogen.',
                   'A raspberry high tunnel trial compared summer ventilation using roof vents and measured air exchange.'])
    row=match_record(record,plan_query('Raspberry high tunnel summer ventilation trials'))
    assert row and 'roof vents' in row['passage']


def test_heat_stress_requires_temperature_and_experimental_location():
    query=plan_query('Raspberry crop heat stress experiments Scotland')
    wrong=source(['Raspberry stress experiments in Scotland used heatmaps to assess root infection and water deficit.'])
    row=match_record(wrong,query)
    assert not row or row['support_status']=='scope_unverified'
    positive=source(['Raspberry heat stress experiments in Scotland compared heating treatments and crop growth.'])
    row=match_record(positive,query)
    assert row and row['support_status']=='body_supported'


def test_unheaded_numbered_bibliography_is_not_owned_trial_prose():
    record=source(['Resources', '14. Example, A. (2020). Raspberry high tunnel ventilation trials. Journal 18:123.'])
    assert not any('Example, A.' in text for _,text in record_passages(record))
    index=source(['Research resources',
                  'Selected publications related to raspberry ventilation trials',
                  'Example A. Raspberry ventilation trials. Journal 2020.'])
    assert not any('ventilation trials' in text for _,text in record_passages(index) if _ not in {'title','summary','snippet'})


def test_recent_review_does_not_make_its_cited_trials_new():
    record=source(['Strawberry disease resistant cultivar trials were reported in 2021 and 2023.'],
                  'Strawberry disease resistance: current status and future directions')
    row=match_record(record,plan_query('Strawberry disease resistant cultivar trials'))
    assert row and row['relevance']=='background'
