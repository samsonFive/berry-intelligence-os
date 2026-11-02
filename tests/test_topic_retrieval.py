"""Deterministic fixtures, distinct from separately recorded live discovery."""
from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.services.topic_retrieval import plan_query, match_record, retrieve
from app.services.topic_discovery import discover_topic


def test_discovery_preserves_publisher_heading_and_original_date_for_native_scope(tmp_path):
    from app.services.default_keyword_monitors import metadata
    from app.services.keyword_backfill import _scope_matches
    class Client:
        def search(self, *a, **kw):
            return SimpleNamespace(provider='fixture', hits=[SimpleNamespace(title='Raspberry varieties',
                url='https://example.org/native', snippet='Raspberry varieties', published_date='2026-10-27')])
    def capture(url):
        return dict(headline='Nowe polskie odmiany malin', canonical_url=url, published_date='2026-01-15',
            published_date_basis='publisher_metadata', passages=['Nowe odmiany malin mają jędrne owoce. ' * 10], availability='full')
    result = discover_topic(plan_query('raspberry variety'), inbox_dir=tmp_path, client=Client(), fetcher=capture)
    assert len(result['items']) == 1
    item = result['items'][0]
    assert item['title'] == 'Nowe polskie odmiany malin' and item['search_title'] == 'Raspberry varieties'
    assert item['published_date'] == '2026-01-15' and item['search_date'] == '2026-10-27'
    assert _scope_matches(metadata('monitor:raspberry-polish'), item)
    warm = discover_topic(plan_query('raspberry variety'), inbox_dir=tmp_path, client=Client(), fetcher=capture)
    assert warm['cache_hit'] and warm['queries_this_request'] == 0


def source(**changes):
    return {"id": "fixture-introduction", "title": "A cultivar introduction", "published_date": "2026-02-08", "source_url": "https://example.org/introduction", "article": {"paragraphs": [{"index": 0, "text": "Synthetic fixture: a breeding programme introduced Ervin, a blackberry for floricane production, after regional trials."}]} , **changes}


@pytest.mark.parametrize("query", ["Blackberry Floricans", "blackberry floricanes", "New blackberry varieties that fruit on second-year canes", "Blackberry floricane-fruiting"])
def test_domain_query_variants_retrieve_body(query):
    assert match_record(source(), plan_query(query))


def test_original_wording_and_unknown_names_are_preserved():
    assert plan_query('Blackberry Floricans "ZZQ Unfamiliar" -software').raw_query.endswith('-software')
    assert "ZZQ Unfamiliar" in plan_query('Blackberry Floricans "ZZQ Unfamiliar"').interpreted_query
    assert not match_record(source(), plan_query("Blackberry Floricans", use_original=True))
    assert not match_record(source(), plan_query('blackberry floricane "absent phrase"'))
    assert not match_record(source(), plan_query('blackberry floricane -Ervin'))
    assert plan_query('Blackberry "Floricans"').interpreted_query == 'Blackberry "Floricans"'


def test_dates_require_publication_evidence_and_preserve_boundaries():
    plan = plan_query("blackberry floricane 2026-01-01 through 2026-10-26")
    assert match_record(source(), plan)
    assert not match_record(source(published_date="2025-12-31", captured_date="2026-10-26"), plan)
    assert not match_record(source(published_date="", modified_date="2026-02-08"), plan)
    with pytest.raises(ValueError):
        plan_query("blackberry 2026-12-01 through 2026-01-01")


def test_long_source_matches_later_passage():
    record = source(article={"full_text": "Introductory context " * 400 + "\n\nA trial tested floricane blackberry fruit quality."})
    row = match_record(record, plan_query("blackberry floricane"))
    assert "trial tested" in row["passage"]


def test_recommendation_text_keeps_its_own_source_and_crop_context():
    from app.services.topic_retrieval import record_passages
    record=source(title='Cherry partnership',article={'paragraphs':[
        {'index':0,'text':'A cherry partnership was announced.'}, {'index':1,'text':'Related articles'},
        {'index':2,'text':'A new floricane blackberry was introduced.'}]})
    assert not match_record(record,plan_query('Floricane blackberry developments'))
    assert record['article']['paragraphs'][2]['text'].endswith('introduced.')
    assert [loc for loc,_ in record_passages(record) if loc.startswith('article:')]==['article:0']
    raspberry=source(title='New raspberry licensing agreement',article={'paragraphs':[
        {'index':0,'text':'The company has a blackberry business.'},
        {'index':1,'text':'This raspberry variety produces a floricane crop and was licensed.'}]})
    assert not match_record(raspberry,plan_query('Floricane blackberry developments'))
    raspberry['article']['paragraphs'].append({'index':2,'text':'A floricane blackberry trial also yielded new results.'})
    assert match_record(raspberry,plan_query('Floricane blackberry developments'))


def test_a_cultivar_introduction_is_background_for_a_licensing_question():
    record=source(title='Blackberry introduction',article={'paragraphs':[
        {'index':0,'text':'A new floricane blackberry was introduced in the United States.'}]})
    plan=plan_query('Floricane blackberry licensing outside the United States')
    assert match_record(record,plan)['relevance']=='background'
    record['article']['paragraphs'].append({'index':1,'text':'It was licensed for development outside the United States.'})
    assert match_record(record,plan)['relevance']=='direct'


def test_raspberry_pi_policy_is_not_raspberry_crop_evidence_but_agtech_can_match():
    tech=source(title='Raspberry Pi and European regulation',article={'paragraphs':[
        {'index':0,'text':'Raspberry Pi computers are digital products subject to European regulation.'}]})
    assert not match_record(tech,plan_query('Raspberry developments Europe'))
    tech['article']['paragraphs'].append({'index':1,'text':'In Europe, raspberry growers used a Raspberry Pi to monitor fruit during harvest trials.'})
    assert match_record(tech,plan_query('Raspberry developments Europe'))


def test_fruiting_habit_requires_linked_classification_evidence():
    record = source(article={}, title="Ervin blackberry introduced", entity_ids=["variety-ervin"])
    entity = {"name": "Ervin", "attributes": {"traits": [{"trait": "trait-fruiting-habit", "value": "floricane", "evidence_ids": []}]}}
    assert not match_record(record, plan_query("blackberry floricane"), entities={"variety-ervin": entity})
    entity["attributes"]["traits"][0]["evidence_ids"] = ["classification-source"]
    assert match_record(record, plan_query("blackberry floricane"), entities={"variety-ervin": entity})["classification_evidence_ids"] == ["classification-source"]


def test_primocane_release_is_adjacent_but_floricane_crop_trial_is_direct():
    record = source(title="Primocane blackberry release", article={"full_text": "A primocane blackberry was released. Floricane varieties provide comparison."})
    assert match_record(record, plan_query("blackberry floricane"))["relevance"] == "adjacent"
    trial = source(title="Primocane blackberry trial results", article={"full_text": "The trial evaluated the floricane crop of a primocane blackberry."})
    assert match_record(trial, plan_query("blackberry floricane"))["relevance"] == "direct"
    assert not match_record(source(title="BlackBerry cybersecurity release", article={}), plan_query("blackberry"))


def test_canonical_duplicate_does_not_merge_later_licensing():
    rows = retrieve([source(), source(id="duplicate", source_url="https://example.org/introduction/?utm_source=feed"), source(id="licensing", source_url="https://example.org/licensing", published_date="2026-09-01")], plan_query("blackberry floricane"))
    assert len(rows) == 2
    assert rows[0]["id"] == "licensing"


def test_discovery_capture_provenance_cache_and_retry(tmp_path):
    calls = []
    class Client:
        def search(self, query, **kwargs):
            calls.append(query)
            return SimpleNamespace(provider="fixture", hits=[SimpleNamespace(title="Cultivar introduction", url="https://example.org/introduction", snippet="blackberry floricane trial", published_date="2026-02-08")])
    def capture(url):
        return {"passages": ["Synthetic source: a new blackberry floricane cultivar was introduced after trials."], "availability": "full"}
    first = discover_topic(plan_query("Blackberry Floricans"), inbox_dir=tmp_path, client=Client(), fetcher=capture)
    assert first["items"] and first["items"][0]["source_version"]
    count = len(calls)
    warm = discover_topic(plan_query("Blackberry Floricans"), inbox_dir=tmp_path, client=Client(), fetcher=capture)
    assert warm["cache_hit"] and warm["queries_this_request"] == 0 and len(calls) == count
    class Failed:
        def search(self, *args, **kwargs):
            raise TimeoutError("secret must never surface")
    failed = discover_topic(plan_query("blackberry trial"), inbox_dir=tmp_path, client=Failed(), fetcher=capture)
    assert failed["status"] == "failed" and "secret" not in str(failed)
    assert discover_topic(plan_query("blackberry trial"), inbox_dir=tmp_path, client=Client(), fetcher=capture)["status"] == "complete"


def test_report_preview_generate_reload_and_workspace_capture(monkeypatch, tmp_path):
    from app import main
    from app.services.living_workspaces import Store
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "maybe_untrusted_completer", lambda: None)
    calls = []
    def discovery(plan, **kwargs):
        calls.append(plan.raw_query)
        return {"items": [{**source(), "passage": "Synthetic fixture: Ervin blackberry was introduced as a floricane cultivar.", "passage_locator": "article:0", "source_version": "fixture-sha", "relevance": "direct", "match_reason": "Matched source passage", "capture_status": "full", "retrieved_at": "2026-10-26T00:00:00Z"}], "status": "complete", "failures": []}
    monkeypatch.setattr("app.services.report_builder.topic_report.discover_topic", discovery)
    client = TestClient(main.app)
    preview = client.post("/reports/new", data={"step": "interpret", "request_text": "Blackberry Floricans", "source_scope": "combined"})
    assert preview.status_code == 200 and "Discovered evidence" in preview.text and "Synthetic fixture" in preview.text
    response = client.post("/reports/new", data={"step": "generate", "research_query": "Blackberry Floricans", "source_scope": "combined", "berry": "berry-blackberry"}, follow_redirects=False)
    assert response.status_code == 303
    url = response.headers["location"]
    before = len(calls)
    report = client.get(url)
    assert report.status_code == 200 and "Attributed source findings" in report.text
    assert len(calls) == before  # saved source version, no paid replay on reload
    saved = client.post(url + "/topic-source/fixture-introduction/save", follow_redirects=False)
    assert saved.status_code == 303
    again = client.post(url + "/topic-source/fixture-introduction/save", follow_redirects=False)
    assert again.status_code == 303
    items = Store(tmp_path).rows("item")
    assert len(items) == 1 and items[0]["verification_state"] == "unverified"


def test_archive_only_report_never_calls_provider(monkeypatch, tmp_path):
    from app.services.report_builder.scope import ResolvedScope
    from app.services.report_builder.topic_report import attach_topic_research, topic_sections
    monkeypatch.setattr("app.services.report_builder.topic_report.discover_topic", lambda *a, **k: pytest.fail("Archive scope must not call web"))
    scope = ResolvedScope("market_landscape", "berry-blackberry", (), (), (), None, None, "", research_query="Blackberry Floricans", source_scope="archive")
    packet = attach_topic_research({"topic_matches": []}, scope, entities={}, inbox_dir=tmp_path)
    assert packet["topic_research"]["discovery"]["status"] == "not_requested"
    assert "No inspected" in topic_sections(packet)[1].prose
    row = source()
    row.update(match_record(row, plan_query(scope.research_query)))
    captured = attach_topic_research({"topic_matches": [row]}, scope, entities={}, inbox_dir=tmp_path)
    assert captured["topic_research"]["local"][0]["source_version"]
    assert captured["topic_research"]["local"][0]["retrieved_at"]


def test_snippet_only_discovery_cannot_become_report_claim(monkeypatch, tmp_path):
    from app.services.report_builder.scope import ResolvedScope
    from app.services.report_builder.topic_report import attach_topic_research, topic_sections
    scope = ResolvedScope("market_landscape", None, (), (), (), None, None, "", research_query="blackberry floricane", source_scope="combined")
    monkeypatch.setattr("app.services.report_builder.topic_report.discover_topic", lambda *a, **k: {"items": [{**source(), "passage": "UNSUPPORTED SNIPPET", "capture_status": "blocked"}], "status": "complete", "failures": []})
    packet = attach_topic_research({"topic_matches": []}, scope, entities={}, inbox_dir=tmp_path)
    assert "UNSUPPORTED SNIPPET" not in topic_sections(packet)[1].prose


def test_explicit_article_footer_publication_date_is_not_site_footer_date():
    from app.services.article_acquisition import publisher_publication_date
    body = '<main><article><p>Source text</p><footer><time itemprop="datePublished" datetime="2026-09-03T13:31:00.0000000">September 3</time></footer></article></main><footer><time itemprop="datePublished" datetime="2026-10-26">Today</time></footer>'
    assert publisher_publication_date(body, "https://example.org/story") == ("2026-09-03", "publisher_display_date")


def test_neighboring_licensing_context_is_retained_and_snippet_is_not_grounding():
    record = source(article={"paragraphs": [{"index": 0, "text": "Ervin is a floricane blackberry introduction."}, {"index": 1, "text": "It has been licensed for development outside the United States."}]}, snippet="UNSUPPORTED SEARCH TEXT blackberry floricane")
    row = match_record(record, plan_query("Blackberry Floricans"))
    assert "licensed for development outside" in row["passage"]
    assert "UNSUPPORTED SEARCH TEXT" not in row["passage"]
    text = "Ervin is a floricane blackberry introduction."
    repeated = source(article={"full_text": text}, supporting_excerpt=text)
    assert match_record(repeated, plan_query("Blackberry Floricans"))["passage"].count(text) == 1


def test_legacy_feed_and_feed_first_use_source_body():
    from app import main
    from app.services.feed_first import _matches
    record = source()
    assert main.filter_evidence([record], q="Blackberry Floricans") == [record]
    item = {"id": record["id"], "record": record, "headline": record["title"], "deck": "", "source_name": "Fixture", "entities": [], "crops": ["blackberry"], "decision": {"reaction": "", "read": False, "saved": False}, "highest_tier": "", "body_availability": "full"}
    filters = dict.fromkeys(["q", "tier", "entity", "crop", "source", "state"], "") | {"q": "Blackberry Floricans"}
    assert _matches(item, filters)


def test_verified_cultivar_code_matches_the_identity_not_scattered_address_tokens():
 entities={'ervin':{'id':'ervin','entity_type':'variety','name':'Ervin','aliases':['NC 740'],'berry_ids':['berry-blackberry']}}
 cultivar=source(title='Ervin blackberry introduction',article={'paragraphs':[{'index':0,'text':'Ervin is a new blackberry cultivar introduced after field trials.'}]})
 address=source(id='address',title='740 Blackberry Trail, Sapphire NC',article={'paragraphs':[{'index':0,'text':'Property at 740 Blackberry Trail in Sapphire NC is listed for sale.'}]})
 for query in ['NC 740 blackberry','NC740 blackberry','NC-740 blackberry','NC‑740 blackberry','nc 740 blackberry']:
  rows=retrieve([address,cultivar],plan_query(query),entities=entities)
  assert [r['id'] for r in rows]==[cultivar['id']]
  assert rows[0]['match_reason']=='Matched verified cultivar-code alias'
 assert not match_record(cultivar,plan_query('blackberry "NC 740"'),entities=entities)


def test_ambiguous_code_does_not_expand_into_an_arbitrary_variety_name():
 entities={i:{'id':i,'entity_type':'variety','name':name,'aliases':['AB 123']} for i,name in [('a','Alpha'),('b','Bravo')]}
 row=source(title='Alpha blackberry release',article={'paragraphs':[{'index':0,'text':'Alpha is a new blackberry cultivar.'}]})
 assert not match_record(row,plan_query('AB 123 blackberry'),entities=entities)


def test_cultivar_code_expansion_does_not_match_the_namesake_grower_in_body_only():
 entities={'ervin':{'id':'ervin','entity_type':'variety','name':'Ervin','aliases':['NC 740']}}
 obituary=source(title='Remembering an industry grower',article={'paragraphs':[{'index':0,'text':'Ervin Lineberger grew blackberry crops for many years.'}]})
 assert not match_record(obituary,plan_query('NC 740 blackberry'),entities=entities)


def test_discovery_uses_local_verified_codes_without_exporting_registry_details(tmp_path):
 entities={'v':{'id':'v','entity_type':'variety','name':'Ervin','aliases':['NC 740'],'attributes':{'private_note':'PRIVATE STRATEGY'}}}
 calls=[]
 class Client:
  def search(self,query,**kwargs):
   calls.append(query)
   return SimpleNamespace(provider='fixture',hits=[SimpleNamespace(url='https://example.org/ervin',title='Ervin blackberry introduction',snippet='',published_date='2026-09-01')])
 def fetch(url):return {'headline':'Ervin blackberry introduction','published_date':'2026-09-01','availability':'full','passages':['Ervin is a new blackberry cultivar introduced after field trials.']}
 plan=plan_query('NC 740 blackberry')
 result=discover_topic(plan,inbox_dir=tmp_path,entities=entities,client=Client(),fetcher=fetch)
 assert result['items'] and all('PRIVATE STRATEGY' not in query for query in calls)
 without_alias=discover_topic(plan,inbox_dir=tmp_path,entities={},client=Client(),fetcher=fetch)
 assert not without_alias['cache_hit'] and without_alias['items']==[]
