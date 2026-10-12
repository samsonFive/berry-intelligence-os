"""Explorer trust boundaries and a complete generic vertical slice."""
from copy import deepcopy
import csv
from datetime import date
from io import StringIO
import json
from pathlib import Path
import time
from xml.etree import ElementTree

from fastapi.testclient import TestClient
import pytest

import app.main as main
from app.services import landscape_explorer as lx
from app.services import landscape_explorer_export as exports


@pytest.fixture
def world():
    def node(key, name, kind, berries=None):
        return {"id": key, "name": name, "entity_type": kind, "berry_ids": berries or [], "aliases": []}
    entities = {row["id"]: row for row in [node("berry-blueberry", "Blueberry", "berry"), node("berry-strawberry", "Strawberry", "berry"),
        node("company-a", "Alpha", "company", ["berry-blueberry"]), node("company-b", "Beta", "company", ["berry-blueberry"]),
        node("breeding_program-a", "Program A", "breeding_program", ["berry-blueberry"]),
        node("variety-a", "Azure", "variety", ["berry-blueberry"]), node("variety-s", "Strawberry cultivar", "variety", ["berry-strawberry"]),
        node("geography-peru", "Peru", "geography"), node("geography-chile", "Chile", "geography"), node("geography-china", "China", "geography"),
        node("geography-subregion", "Subregion", "geography")]}
    evidence = [{"id": "ev-a", "title": "A blueberry announcement", "summary": "A source summary, not a quote", "status": "published", "source_name": "Origin A", "source_url": "https://example.com/a?source=1&b=2", "published_date": "2026-09-01", "captured_date": "2026-10-01", "berry_ids": ["berry-blueberry"]}]
    def edge(key, left, role, right, **extras):
        return {"id": key, "subject_id": left, "object_id": right, "predicate": role, "status": "active", "evidence_ids": ["ev-a"], **extras}
    relationships = [edge("r-peru", "company-a", "operates_in", "geography-peru"), edge("r-chile", "company-a", "operates_in", "geography-chile"),
        edge("r-program", "company-a", "owns", "breeding_program-a"), edge("r-develops", "breeding_program-a", "develops", "variety-a"),
        edge("r-license", "company-b", "licenses", "variety-a"), edge("r-other-berry", "company-a", "develops", "variety-s")]
    return {"entities": entities, "relationships": relationships, "evidence": evidence}


def build(world, **params):
    return lx.build_bundle(**world, params=params, today=date(2026, 10, 6))


def test_real_role_trace_has_no_inferred_growing(world):
    before = deepcopy(world)
    result = build(world)
    assert {r["id"] for r in result["edges"]} == {"r-peru", "r-chile", "r-program", "r-develops", "r-license"}
    assert result["coverage"]["genetic_location_links"] == 0
    assert result["coverage"]["company_location_links"] == 2
    assert result["nodes"]["variety-a"]["label"] == "Azure"
    assert next(r for r in result["edges"] if r["id"] == "r-license")["role"] == "Licensee"
    assert world == before


def test_compact_market_and_portfolio_context_preserves_exact_paths(world):
    result = build(world)
    row = next(row for row in result["market_rows"] if row["actor"]["id"] == "company-a")
    assert {m["country"] for m in row["markets"] if m["edges"]} == {"Chile", "Peru"}
    assert [v["id"] for v in row["varieties"]] == ["variety-a"]
    assert [edge["id"] for edge in row["portfolio_edges"]] == ["r-develops"]
    assert "r-program" in {edge["id"] for edge in row["edges"]}
    assert result["coverage"]["genetic_location_links"] == 0
    for insight in result["insights"]:
        assert set(insight["relationship_ids"]) <= {edge["id"] for edge in result["edges"]}
        assert set(insight["evidence_ids"]) <= {source["id"] for source in result["sources"]}


def test_source_named_varieties_surface_as_review_links_not_graph_edges(world):
    world["evidence"][0]["summary"] = "Blueberry varieties including Azure and Prelude."
    result = build(world)
    names = {row["name"]: row for row in result["sources"][0]["varieties"]}
    assert names["Azure"]["catalog_id"] == "variety-a"
    assert names["Prelude"]["href"].startswith("/varieties/candidates?")
    assert [row["name"] for row in result["catalog_gaps"]] == ["Prelude"]
    assert len(result["edges"]) == 5 and "variety-prelude" not in result["nodes"]
    world["evidence"][0]["summary"] = "Company operations in Peru."
    assert not build(world)["catalog_gaps"]


def test_direct_genetics_links_across_countries_are_first_class(world):
    world["relationships"] += [{"id": "r-g-"+country, "subject_id": "variety-a", "object_id": "geography-"+country, "predicate": "operates_in", "status": "active", "evidence_ids": ["ev-a"]} for country in ["peru", "chile"]]
    result = build(world, focus="variety-a", question="genetics")
    assert result["coverage"]["genetic_location_links"] == 2
    assert len([row for row in result["explanation"]["findings"] if row["relationship_ids"][0].startswith("r-g-")]) == 2
    assert "variety-a" in result["neighborhood"]


def test_country_scope_uses_containment_not_headquarters_or_names(world):
    world["relationships"].append({"id": "r-contain", "subject_id": "geography-subregion", "object_id": "geography-peru", "predicate": "part_of", "status": "active", "evidence_ids": ["ev-a"]})
    world["relationships"].append({"id": "r-local", "subject_id": "company-b", "object_id": "geography-subregion", "predicate": "operates_in", "status": "active", "evidence_ids": ["ev-a"]})
    result = build(world, countries="geography-peru")
    assert "r-local" in {r["id"] for r in result["edges"]}
    assert "r-chile" not in {r["id"] for r in result["edges"]}
    assert {n["label"] for n in result["lanes"][0]["actors"]} == {"Alpha", "Beta"}
    assert build(world, countries="geography-china")["edges"] == []


def test_mentions_and_annotation_like_records_do_not_create_edges(world):
    world["evidence"][0]["entity_ids"] = ["variety-a", "geography-china", "company-a"]
    result = build(world, countries="geography-china")
    assert result["edges"] == []


def test_role_filter_preserves_country_roots_and_focusing_does_not_drift(world):
    assert {edge["id"] for edge in build(world, countries="geography-peru", predicate="licenses")["edges"]} == {"r-license"}
    initial = build(world)
    for key in initial["nodes"]:
        if initial["nodes"][key]["type"] in lx.ACTOR_TYPES:
            assert {edge["id"] for edge in build(world, focus=key)["edges"]} == {edge["id"] for edge in initial["edges"]}


@pytest.mark.parametrize("path", ["/landscapes/explorer", "/api/landscapes/explorer", "/landscapes/explorer/briefing", "/landscapes/explorer/export/html", "/landscapes/explorer/export/svg", "/landscapes/explorer/export/csv"])
def test_remote_auth_covers_new_routes(client_world, monkeypatch, path):
    monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "true")
    monkeypatch.setenv("BIOS_REVIEW_USERNAME", "review-operator")
    monkeypatch.setenv("BIOS_REVIEW_PASSWORD", "test-only-password")
    monkeypatch.setenv("BIOS_SESSION_SECRET", "test-only-signing-secret-with-adequate-length")
    response = client_world.get(path, follow_redirects=False)
    assert response.status_code in (302, 401)
    assert "r-peru" not in response.text


def test_alias_search_does_not_merge_ambiguous_companies(world):
    for key in ("company-a", "company-b"):
        world["entities"][key]["aliases"] = ["Shared name"]
    result = build(world, countries="", q="Shared name")
    assert {"company-a", "company-b"} <= set(result["nodes"])
    assert "variety-s" not in result["nodes"]


@pytest.mark.parametrize("params", [{"countries": "missing"}, {"berry": "missing"}, {"focus": "missing"}, {"status": "confirmed"}, {"time": "pretend"}, {"window": "custom", "start": "2026-10-03", "end": "2026-10-01"}, {"limit": "bad"}, {"predicate": "breeds"}])
def test_invalid_selection_rejected(world, params):
    with pytest.raises(ValueError):
        build(world, **params)


def test_source_policy_excludes_private_and_pending_by_default(world):
    world["evidence"][0]["status"] = "in_review"
    assert build(world)["edges"] == []
    assert len(build(world, evidence="all")["edges"]) == 5
    world["evidence"][0]["status"] = "draft"
    assert build(world, evidence="all")["edges"] == []


def test_disputes_history_and_legacy_intent_are_explicit(world):
    world["relationships"][0].update(status="historical")
    world["relationships"][1].update(status="disputed", notes="Stated intention; treat as an intent signal, not an established operation.")
    result = build(world)
    assert next(r for r in result["edges"] if r["id"] == "r-chile")["caveat"].startswith("Intent only")
    assert next(r for r in result["edges"] if r["id"] == "r-peru")["status_label"] == "Historical relationship"
    assert not any("withdraw" in r["label"] for r in result["edges"])
    assert {r["id"] for r in build(world, countries="", status="disputed")["edges"]} == {"r-chile"}


@pytest.mark.parametrize("notes,caveat", [
    ("confidence=low; Inferred only from a reported portfolio; no direct statement retrieved.", "Limited support"),
    ("Breeding origin is not stated in the source.", "Limited support"),
    ("Substituted predicate: sells stands in for markets.", "Legacy role mapping"),
])
def test_legacy_inferences_and_substituted_roles_keep_visible_caveats(world, notes, caveat):
    world["relationships"][3]["notes"] = notes
    result = build(world, focus="breeding_program-a", question="genetics")
    edge = next(row for row in result["edges"] if row["id"] == "r-develops")
    assert edge["caveat"].startswith(caveat)
    assert edge["predicate"] == "develops"  # Canonical data is preserved, not reclassified.
    assert any(caveat in row["text"] for row in result["explanation"]["findings"])
    assert caveat in exports.html_export(result)
    assert caveat in exports.svg_export(result)
    assert caveat in exports.csv_export(result)
    assert notes == world["relationships"][3]["notes"]


def test_three_clocks_and_no_fictional_history(world):
    world["relationships"][0]["effective_date"] = "2025-05-01"
    captured = build(world, window="7d", time="documented")
    assert len(captured["changes"]) == 5
    assert not build(world, window="7d", time="event")["changes"]
    assert not build(world, window="7d", time="published")["changes"]
    assert len(build(world, window="custom", start="2025-05-01", end="2025-05-01", time="event")["changes"]) == 1
    assert len(build(world, window="7d", time="event")["edges"]) == 5
    explanation = build(world, window="7d", question="changes")["explanation"]
    assert all("Newly documented" in row["text"] for row in explanation["findings"])


def test_syndicated_sources_do_not_inflate_origins(world):
    duplicate = deepcopy(world["evidence"][0]); duplicate["id"] = "ev-reprint"
    world["evidence"].append(duplicate)
    world["relationships"][0]["evidence_ids"].append("ev-reprint")
    result = build(world)
    assert result["independence"]["total_evidence_count"] == 2
    assert result["independence"]["independent_source_count"] == 1


def test_edit_and_removal_invalidate_cache_and_no_mutable_cache_leaks(world):
    first = build(world)
    first["edges"].clear()
    assert len(build(world)["edges"]) == 5
    world["evidence"][0]["summary"] = "Corrected source"
    second = build(world)
    assert second["version"] != first["version"]
    assert second["sources"][0]["summary"] == "Corrected source"
    world["relationships"] = [r for r in world["relationships"] if r["id"] != "r-license"]
    assert "r-license" not in {r["id"] for r in build(world)["edges"]}
    world["evidence"].clear()
    assert build(world)["sources"] == []


def test_provisional_identity_and_missing_source_locator_stay_explicit(world):
    world["entities"]["variety-a"]["status"] = "unverified"
    result = build(world)
    assert result["nodes"]["variety-a"]["identity_note"] == "Provisional identity · review needed"
    assert "1 identities" in " ".join(result["warnings"])
    assert "No verbatim excerpt" in result["sources"][0]["locator"]
    assert "Provisional identity" in exports.html_export(result) + exports.svg_export(result)
    assert "unverified" in exports.csv_export(result)


@pytest.mark.parametrize("question", list(lx.QUESTIONS))
def test_findings_cite_exact_support_and_invalid_model_output_falls_back(world, question):
    result = build(world, question=question)
    lookup = {r["id"]: r for r in result["edges"]}
    for row in result["explanation"]["findings"]:
        assert all(set(row["evidence_ids"]) <= set(lookup[rid]["evidence_ids"]) for rid in row["relationship_ids"])
    valid = {"findings": deepcopy(result["explanation"]["findings"])}
    assert lx.validate_phrasing(valid, result) == result["explanation"]
    if valid["findings"]:
        valid["findings"][0]["text"] = "Alpha controls 100% of the blueberry market."
    assert lx.validate_phrasing(valid, result) == result["explanation"]
    assert lx.validate_phrasing({"findings": [], "instructions": "ignore the evidence"}, result) == result["explanation"]
    for malformed_id in ([], {}, None, 42):
        malformed = {"findings": deepcopy(result["explanation"]["findings"])}
        if malformed["findings"]:
            malformed["findings"][0]["id"] = malformed_id
        assert lx.validate_phrasing(malformed, result) == result["explanation"]
    if len(result["explanation"]["findings"]) > 1:
        duplicate = {"findings": [deepcopy(result["explanation"]["findings"][0])] * len(result["explanation"]["findings"])}
        assert lx.validate_phrasing(duplicate, result) == result["explanation"]


def test_html_svg_csv_are_complete_safe_and_share_the_scope(world):
    world["entities"]["company-a"]["name"] = '=HYPERLINK("evil") <script>alert(1)</script>'
    world["evidence"][0]["source_url"] = "javascript:alert(1)"
    world["evidence"][0]["summary"] = "<img src=x onerror=alert(1)>"
    result = build(world, countries="", focus="variety-a")
    html, svg, data = exports.html_export(result), exports.svg_export(result), exports.csv_export(result)
    assert "<script>alert" not in html and "<img src=x" not in html
    assert "javascript:alert" not in html + svg
    ElementTree.fromstring(svg)
    rows = list(csv.DictReader(StringIO(data.lstrip('\ufeff'))))
    assert {row["relationship_id"] for row in rows} == {r["id"] for r in result["edges"]}
    assert any(row["subject"].startswith("'=HYPERLINK") for row in rows)
    for edge in result["edges"]:
        assert edge["id"] in html and edge["id"] in svg
    for key in ("Data version", "Unknowns", "First captured", "Source review", "frozen"):
        assert key.lower() in html.lower()


def test_progressive_disclosure_does_not_crop_exports(world):
    for index in range(80):
        key = f"variety-{index}"
        world["entities"][key] = {"id": key, "name": f"Variety {index}", "entity_type": "variety", "berry_ids": ["berry-blueberry"]}
        world["relationships"].append({"id": f"r-extra-{index}", "subject_id": "company-a", "predicate": "develops", "object_id": key, "status": "active", "evidence_ids": ["ev-a"]})
    result = build(world, countries="", limit="20")
    assert result["coverage"]["truncated_display"]
    assert result["coverage"]["hidden_nodes"] > 0
    assert "r-extra-79" in exports.html_export(result)
    assert "r-extra-79" in exports.svg_export(result)
    assert len(list(csv.DictReader(StringIO(exports.csv_export(result).lstrip('\ufeff'))))) == 85


@pytest.fixture
def client_world(world, monkeypatch, tmp_path):
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "all_entities", lambda: list(world["entities"].values()))
    monkeypatch.setattr(main, "all_relationships", lambda: world["relationships"])
    monkeypatch.setattr(main, "all_evidence", lambda: world["evidence"])
    return TestClient(main.app)


def test_ui_api_export_match_and_registered_berry_validation(client_world):
    query = "countries=geography-peru&focus=variety-a&theme=dark&window=30d"
    api = client_world.get("/api/landscapes/explorer?" + query)
    assert api.status_code == 200
    assert api.headers["cache-control"] == "private, no-store"
    page = client_world.get("/landscapes/explorer?" + query)
    assert page.status_code == 200, page.text
    assert 'data-theme="dark"' in page.text
    assert "r-peru" in page.text and "r-chile" not in page.text
    assert 'data-focus="geography-' not in page.text
    for format in ("html", "svg", "csv"):
        response = client_world.get("/landscapes/explorer/export/" + format + "?" + query)
        assert response.status_code == 200
        assert api.json()["version"] in response.text
        assert "r-peru" in response.text and "r-chile" not in response.text
    strawberry = client_world.get("/landscapes/explorer?berry=berry-strawberry")
    assert strawberry.status_code == 200
    assert '<option value="berry-strawberry" selected>Strawberry</option>' in strawberry.text
    assert client_world.get("/landscapes/explorer?berry=berry-unknown").status_code == 422
    assert client_world.get("/landscapes/explorer?edge=missing").status_code == 422


@pytest.mark.parametrize('berry,role', [('berry-strawberry','licenses'),
    ('berry-raspberry','markets'),('berry-blackberry','grows')])
def test_new_crop_routes_preserve_genetic_identity_role_and_source(client_world,world,berry,role):
    before=deepcopy(world)
    key='variety-'+berry.removeprefix('berry-')+'-specific'
    source='ev-'+berry
    world['entities'][berry]={'id':berry,'name':berry.removeprefix('berry-').title(),'entity_type':'berry'}
    world['entities'][key]={'id':key,'name':'Crop-specific cultivar','entity_type':'variety','berry_ids':[berry]}
    world['evidence'].append({'id':source,'title':'Recorded crop-specific source','status':'published',
        'source_url':'https://example.test/'+berry,'berry_ids':[berry]})
    world['relationships'].append({'id':'crop-specific-role','subject_id':'company-b','predicate':role,
        'object_id':key,'status':'active','evidence_ids':[source]})
    query='countries=&berry='+berry
    response=client_world.get('/api/landscapes/explorer?'+query)
    assert response.status_code==200
    bundle=response.json()
    edge=next(e for e in bundle['edges'] if e['id']=='crop-specific-role')
    assert edge['predicate']==role and edge['evidence_ids']==[source]
    assert key in bundle['nodes'] and 'variety-a' not in bundle['nodes']
    assert bundle['coverage']['genetic_location_links']==0
    assert 'r-license' not in {e['id'] for e in bundle['edges']}
    for kind in ('html','svg','csv'):
        exported=client_world.get('/landscapes/explorer/export/'+kind+'?'+query)
        assert exported.status_code==200 and 'crop-specific-role' in exported.text
        assert berry.removeprefix('berry-')+'-landscape-' in exported.headers['content-disposition']
    assert before['entities']['variety-a']==world['entities']['variety-a']


def test_nonblueberry_defaults_do_not_impose_blueberry_markets(world):
    strawberry=lx.selection({'berry':'berry-strawberry'},world['entities'])
    assert strawberry['countries']==[]
    explicit=lx.selection({'berry':'berry-strawberry','countries':'geography-peru'},world['entities'])
    assert explicit['countries']==['geography-peru']
    assert lx.selection({},world['entities'])['countries']==['geography-chile','geography-china','geography-peru']


def test_all_berries_preserves_distinct_genetics_and_deduplicates_shared_records(world):
    world['entities']['variety-s']['name'] = 'Azure'
    single = {crop: build(world, berry=crop, countries='') for crop in ('berry-blueberry','berry-strawberry')}
    result = build(world, berry='all', countries='')
    assert set(result['nodes']) == set().union(*(set(b['nodes']) for b in single.values()))
    assert {e['id'] for e in result['edges']} == set().union(*({e['id'] for e in b['edges']} for b in single.values()))
    assert result['nodes']['variety-a']['label'] == result['nodes']['variety-s']['label'] == 'Azure'
    assert result['coverage']['genetic_location_links'] == 0
    assert len(result['sources']) == 1  # the source is shared, not duplicated
    edge = next(e for e in result['edges'] if e['id'] == 'r-other-berry')
    assert edge['berry_ids'] == ['berry-strawberry']
    assert all(row['berry_label'] == 'Strawberry' for row in result['portfolios'] if any(v['id'] == 'variety-s' for v in row['varieties']))
    assert lx.selection({'berry':'all'}, world['entities'])['countries'] == []


def test_union_does_not_follow_cross_crop_company_shortcut(world):
    world['entities']['company-c'] = {'id':'company-c','name':'Gamma','entity_type':'company','berry_ids':['berry-strawberry']}
    world['evidence'].append({'id':'ev-s','status':'published','title':'Strawberry roles','berry_ids':['berry-strawberry']})
    world['relationships'].extend([
        {'id':'s-peru','subject_id':'company-c','predicate':'operates_in','object_id':'geography-peru','status':'active','evidence_ids':['ev-s']},
        {'id':'s-partner','subject_id':'company-c','predicate':'partners_with','object_id':'company-b','status':'active','evidence_ids':['ev-s'],'berry_ids':['berry-strawberry']},
    ])
    # No blueberry actor is linked to China; strawberry links cannot pull a
    # disconnected blueberry portfolio into the aggregate's country scope.
    world['relationships'] = [e for e in world['relationships'] if e['id'] not in {'r-peru','r-chile'}]
    result = build(world, berry='all', countries='geography-peru')
    assert not {'r-license','r-program','r-develops'}.intersection(e['id'] for e in result['edges'])
    assert 'variety-a' not in result['nodes']


def test_explicit_relationship_crop_overrides_multi_crop_actor_tags(world):
    world['entities']['company-a']['berry_ids'] = ['berry-blueberry','berry-strawberry']
    world['entities']['company-b']['berry_ids'] = ['berry-blueberry','berry-strawberry']
    world['relationships'].append({'id':'s-partner-only','subject_id':'company-a','predicate':'partners_with','object_id':'company-b','status':'active','berry_ids':['berry-strawberry'],'evidence_ids':['ev-a']})
    result=build(world,berry='all',countries='')
    assert next(e for e in result['edges'] if e['id']=='s-partner-only')['berry_ids']==['berry-strawberry']


def test_comparison_limits_report_actual_display_and_export_complete_scope(world):
    for index in range(60):
        for crop,suffix in [('berry-blueberry','b'),('berry-strawberry','s')]:
            key=f'variety-{suffix}-{index}'
            world['entities'][key]={'id':key,'name':f'{suffix} {index}','entity_type':'variety','berry_ids':[crop]}
            world['relationships'].append({'id':'r-'+key,'subject_id':'company-a','predicate':'develops','object_id':key,'status':'active','evidence_ids':['ev-a']})
    result=build(world,berry='berry-blueberry',compare='berry-strawberry',view='compare',countries='',limit=100)
    assert len(result['visible_nodes']) <= 100
    assert result['coverage']['hidden_nodes']==len(result['nodes'])-len(result['visible_nodes'])
    assert result['coverage']['hidden_relationships']==len(result['edges'])-len(result['visible_edges'])
    assert result['coverage']['truncated_display']
    assert all('r-variety-'+suffix+'-59' in exports.html_export(result) for suffix in ('s','b'))
    compact=lx.browser_bundle(result)
    assert compact['nodes']==result['nodes'] and compact['edges']==result['edges'] and compact['sources']==result['sources']
    assert 'portfolios' not in compact and 'market_rows' not in compact


def test_comparison_has_exact_common_actors_separate_scopes_and_focus(world):
    result = build(world, berry='berry-blueberry', compare='berry-strawberry', view='compare', countries='', focus='variety-s')
    assert result['title'] == 'Blueberry vs Strawberry landscapes'
    assert result['common_actor_ids'] == ['company-a']
    crops = {c['id']:c for c in result['crop_scopes']}
    assert 'variety-s' not in crops['berry-blueberry']['node_ids']
    assert 'variety-a' not in crops['berry-strawberry']['node_ids']
    assert 'focus=variety-s' not in crops['berry-blueberry']['url']
    assert 'focus=variety-s' in crops['berry-strawberry']['url']
    restored = lx.build_bundle(**world, params=dict(__import__('urllib.parse',fromlist=['parse_qsl']).parse_qsl(result['url'].split('?',1)[1])), today=date(2026,10,6))
    assert result == restored
    for view in ('portrait','changes','explain','relationships'):
        alternate = lx.build_bundle(**world, params={**result['filters'],'countries':'','view':view}, today=date(2026,10,6))
        assert {e['id'] for e in alternate['edges']} == {e['id'] for e in result['edges']}
        assert alternate['filters']['pair']=='1' and alternate['title']==result['title']


@pytest.mark.parametrize('params', [dict(berry='all',view='compare'), dict(berry='berry-blueberry',compare='berry-blueberry',view='compare'), dict(compare='missing')])
def test_invalid_comparison_is_recoverable(client_world, params):
    from urllib.parse import urlencode
    assert client_world.get('/landscapes/explorer?'+urlencode(params)).status_code == 422
    assert client_world.get('/api/landscapes/explorer?'+urlencode(params)).status_code == 422


def test_comparison_filters_and_exports_keep_exact_crop_source_parity(client_world, world):
    world['evidence'].append({'id':'ev-private','status':'in_review','title':'Unreviewed strawberry source','berry_ids':['berry-strawberry']})
    world['relationships'][5]['evidence_ids'] = ['ev-private']
    query = 'berry=berry-blueberry&compare=berry-strawberry&view=compare&countries=&theme=dark'
    reviewed = client_world.get('/api/landscapes/explorer?'+query).json()
    assert reviewed['crop_scopes'][1]['coverage']['relationships'] == 0
    query += '&evidence=all'
    bundle = client_world.get('/api/landscapes/explorer?'+query).json()
    page = client_world.get('/landscapes/explorer?'+query)
    assert page.status_code == 200 and 'Strawberry landscape comparison' in page.text
    assert 'Shared actor' in page.text and 'Unreviewed strawberry source' in page.text
    assert 'data-theme="dark"' in page.text
    assert page.text.count('class="lx-crop-coverage"') == 1
    for kind in ('html','svg','csv'):
        response = client_world.get('/landscapes/explorer/export/'+kind+'?'+query)
        assert response.status_code == 200
        assert bundle['version'] in response.text
        assert 'r-other-berry' in response.text and 'Unreviewed strawberry source' in response.text
    csv_rows = list(csv.DictReader(StringIO(exports.csv_export(bundle).lstrip('\ufeff'))))
    assert next(r for r in csv_rows if r['relationship_id']=='r-other-berry')['relationship_berry_scopes']=='berry-strawberry'
    assert all(r['generated_at']==bundle['generated_at'] for r in csv_rows)
    world['evidence'].pop()
    updated = client_world.get('/api/landscapes/explorer?'+query).json()
    assert updated['version'] != bundle['version'] and not any(e['id']=='r-other-berry' for e in updated['edges'])


def test_wrong_crop_genetic_focus_cannot_enter_a_landscape(client_world,world):
    response=client_world.get('/api/landscapes/explorer?berry=berry-strawberry&focus=variety-a')
    assert response.status_code==422 and 'outside the selected berry' in response.json()['detail']
    # A company can be explored across crops; its actual supported genetic links determine the result.
    assert lx.selection({'berry':'berry-strawberry','focus':'company-a'},world['entities'])['focus']=='company-a'


def test_explorer_saved_selection_reopens_refreshes_and_preserves_old_views(client_world,world):
    from app.services import landscape_workspace as workspace
    old=workspace.save_view(main.INBOX_DIR,name='Original overview',filters={'company':'company-a','section':'companies'})
    initial=deepcopy(world)
    response=client_world.post('/landscapes/explorer/views',data={'name':'Two crops','berry':'berry-blueberry','compare':'berry-strawberry','view':'compare','countries':'','evidence':'all','window':'30d','private_article':'do not store'},follow_redirects=False)
    assert response.status_code==303
    row=next(r for r in workspace.load_views(main.INBOX_DIR)['views'].values() if r.get('kind')=='explorer')
    assert row['filters']['pair']=='1' and 'private_article' not in row['filters']
    assert workspace.load_views(main.INBOX_DIR)['views'][old['id']]==old
    assert world==initial
    location=response.headers['location']
    before=client_world.get('/api'+location).json()
    assert before['filters']['berry']=='berry-blueberry' and before['filters']['view']=='compare'
    assert before['filters']['window']=='30d' and before['filters']['evidence']=='all'
    world['evidence'][0]['title']='Edited source title'
    after=client_world.get('/api'+location).json()
    assert after['version']!=before['version'] and after['sources'][0]['title']=='Edited source title'
    page=client_world.get(location)
    assert page.status_code==200 and 'data-save-selection' in page.text and 'name="revision" value="1"' in page.text
    assert 'reopen it with current data' in page.text
    assert client_world.get('/landscapes/explorer/export/html?saved_view='+row['id']).status_code==200


def test_saved_explorer_revision_copy_archive_restore_and_surface_safety(client_world):
    from app.services import landscape_workspace as workspace
    from urllib.parse import parse_qs,urlsplit
    created=client_world.post('/landscapes/explorer/views',data={'name':'Crop watch','berry':'all','countries':''},follow_redirects=False)
    key=parse_qs(urlsplit(created.headers['location']).query)['saved_view'][0]
    updated=client_world.post('/landscapes/explorer/views',data={'saved_view':key,'view_id':key,'revision':'1','name':'Renamed','q':'Alpha'},follow_redirects=False)
    assert updated.status_code==303
    store_path=main.INBOX_DIR/workspace.VIEW_FILE
    before=store_path.read_bytes()
    conflict=client_world.post('/landscapes/explorer/views',data={'saved_view':key,'view_id':key,'revision':'1','name':'Lost update'},follow_redirects=False)
    assert conflict.status_code==409 and store_path.read_bytes()==before
    copied=client_world.post('/landscapes/explorer/views',data={'saved_view':key,'view_id':key,'revision':'2','action':'copy','name':'Separate scope'},follow_redirects=False)
    assert copied.status_code==303 and key not in copied.headers['location']
    wrong_surface=client_world.post('/landscapes/views',data={'view_id':key,'revision':'2','name':'Invalid conversion'},follow_redirects=False)
    assert wrong_surface.status_code==422
    # The overview's existing archive/restore controls must retain Explorer fields.
    archived=client_world.post('/landscapes/views',data={'view_id':key,'revision':'2','action':'archive'},follow_redirects=False)
    assert archived.status_code==303
    assert client_world.get('/landscapes/explorer?saved_view='+key).status_code==422
    restored=client_world.post('/landscapes/views',data={'view_id':key,'revision':'3','action':'restore'},follow_redirects=False)
    assert restored.status_code==303 and restored.headers['location']==workspace.view_href(workspace.load_views(main.INBOX_DIR)['views'][key])
    row=workspace.load_views(main.INBOX_DIR)['views'][key]
    assert row['kind']=='explorer' and row['filters']['berry']=='all' and row['filters']['q']=='Alpha' and row['revision']==4


def test_saved_explorer_validation_and_cross_site_writes_do_not_change_store(client_world):
    from app.services import landscape_workspace as workspace
    path=main.INBOX_DIR/workspace.VIEW_FILE
    assert client_world.post('/landscapes/explorer/views',data={'name':'Bad','berry':'missing'},follow_redirects=False).status_code==422
    assert not path.exists()
    for headers in ({'origin':'https://other.test'},{'sec-fetch-site':'cross-site'}):
        assert client_world.post('/landscapes/explorer/views',data={'name':'Blocked'},headers=headers,follow_redirects=False).status_code==403
    assert not path.exists()
    assert client_world.get('/landscapes/explorer?saved_view=missing').status_code==422
    path.write_text('broken saved-view JSON',encoding='utf-8')
    before=path.read_bytes()
    assert client_world.post('/landscapes/explorer/views',data={'name':'Must not overwrite'},follow_redirects=False).status_code==422
    assert path.read_bytes()==before


def test_repeated_country_controls_survive_saved_view_context(client_world):
    bundle=client_world.get('/api/landscapes/explorer?countries=geography-peru&countries=geography-chile').json()
    assert bundle['filters']['countries']==['geography-chile','geography-peru']
    assert {'r-chile','r-peru'}<={e['id'] for e in bundle['edges']}


def test_saved_relative_date_window_refreshes_without_rewriting_selection(client_world,monkeypatch):
    from app.services import landscape_workspace as workspace
    from urllib.parse import parse_qs,urlsplit
    class ReviewDate(date):
        current=date(2026,10,1)
        @classmethod
        def today(cls):
            return cls.current
    monkeypatch.setattr(lx,'date',ReviewDate)
    created=client_world.post('/landscapes/explorer/views',data={'name':'Rolling dates','window':'30d','countries':''},follow_redirects=False)
    assert created.status_code==303
    key=parse_qs(urlsplit(created.headers['location']).query)['saved_view'][0]
    store_path=main.INBOX_DIR/workspace.VIEW_FILE
    before=store_path.read_bytes()
    ReviewDate.current=date(2026,10,15)
    refreshed=client_world.get('/api/landscapes/explorer?saved_view='+key).json()
    assert refreshed['filters']['start']=='2026-09-16' and refreshed['filters']['end']=='2026-10-15'
    assert store_path.read_bytes()==before


def test_explorer_saved_writes_require_authoring_and_remote_login(client_world,monkeypatch):
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    assert client_world.post('/landscapes/explorer/views',data={'name':'Blocked'},follow_redirects=False).status_code==403
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    monkeypatch.setenv('BIOS_REMOTE_INTERACTIVE','1')
    monkeypatch.setenv('BIOS_REVIEW_USERNAME','fixture-analyst')
    monkeypatch.setenv('BIOS_REVIEW_PASSWORD','fixture-password')
    monkeypatch.setenv('BIOS_SESSION_SECRET','fixture-secret-not-password-with-adequate-signing-length')
    response=client_world.post('/landscapes/explorer/views',data={'name':'Blocked'},follow_redirects=False)
    assert response.status_code in {302,303,307} and '/login' in response.headers['location']


def test_landscape_respects_canonical_deleted_source_holds_without_erasing_history(client_world,world,monkeypatch,tmp_path):
    from app.services.social_intelligence.store import Store
    template=json.loads((Path(__file__).resolve().parents[1]/'benchmarks/social-blueberry-fixtures.json').read_text(encoding='utf-8'))['records'][0]
    store=Store(main.INBOX_DIR)
    row=dict(template,mode='live',translation=None,native_id='landscape-test-post')
    key=store.ingest([row],[],mode='live')[0]
    world['evidence'][0]['social_observation']={'id':key,'source':row['source'],'native_id':row['native_id'],'mode':'live'}
    before=deepcopy(world)
    data=tmp_path/'canonical-fixtures'
    for name,records in [('evidence',world['evidence']),('relationships',world['relationships']),('facts',[]),('signals',[]),('assessments',[]),('recommendations',[])]:
        folder=data/name;folder.mkdir(parents=True)
        for record in records:(folder/(record['id']+'.json')).write_text(json.dumps(record),encoding='utf-8')
    monkeypatch.setattr(main,'DATA_DIR',data)
    snapshot={p:p.read_bytes() for p in data.rglob('*.json')}
    visible=client_world.get('/api/landscapes/explorer').json()
    assert len(visible['edges'])==5
    store.remove(key,state='unavailable')
    assert len(client_world.get('/api/landscapes/explorer').json()['edges'])==5
    store.remove(key,state='deleted')
    hidden=client_world.get('/api/landscapes/explorer').json()
    assert not hidden['edges'] and not hidden['sources'] and hidden['version']!=visible['version']
    assert 'A blueberry announcement' not in client_world.get('/landscapes/explorer/export/html').text
    assert world==before and all(p.read_bytes()==body for p,body in snapshot.items())


def test_portrait_role_summary_does_not_transfer_program_roles_to_owner(client_world, world):
    import re

    world["relationships"][4].update(status="disputed", notes="confidence=low; Inferred only from a reported portfolio; no direct statement retrieved.")
    before = deepcopy(world)
    page = client_world.get("/landscapes/explorer")
    assert page.status_code == 200
    table = page.text.split('class="lx-portfolio-table"', 1)[1].split("</table>", 1)[0]
    owner = re.search(r'<tr data-node="company-a">(.*?)</tr>', table, re.S).group(1)
    licensee = re.search(r'<tr data-node="company-b">(.*?)</tr>', table, re.S).group(1)
    assert "Owner / rights holder · Program A" in owner
    assert "Breeder / developer" not in owner
    assert 'aria-label="Alpha owns Program A"' in owner
    assert "Licensee · Disputed" in licensee
    assert "Limited support" in licensee
    assert "Azure" in licensee
    assert world == before


def test_controller_restores_explicit_focus_and_independent_evidence():
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required to execute the production browser controller")
    result = subprocess.run([node, str(Path(__file__).with_name("landscape_url_restore_checks.js"))], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("path", ["/landscapes/explorer", "/api/landscapes/explorer", "/landscapes/explorer/briefing", "/landscapes/explorer/export/html", "/landscapes/explorer/export/svg", "/landscapes/explorer/export/csv"])
def test_all_formats_are_analyst_only(client_world, monkeypatch, path):
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    assert client_world.get(path).status_code == 404


def test_invalid_page_scope_has_recovery_and_api_keeps_structured_error(client_world):
    page = client_world.get("/landscapes/explorer?countries=missing")
    assert page.status_code == 422
    assert page.headers["content-type"].startswith("text/html")
    assert "Adjust your selection" in page.text and "Reset landscape selection" in page.text
    assert "Choose registered countries or regions." in page.text
    api = client_world.get("/api/landscapes/explorer?countries=missing")
    assert api.status_code == 422 and api.json()["detail"] == "Choose registered countries or regions."


def test_bounded_synthetic_scale_100_nodes_200_edges(world):
    for index in range(100):
        key = f"variety-{index}"
        world["entities"][key] = {"id": key, "name": f"Variety {index}", "entity_type": "variety", "berry_ids": ["berry-blueberry"]}
        for role in ("develops", "markets"):
            world["relationships"].append({"id": f"r-{role}-{index}", "subject_id": "company-a", "predicate": role, "object_id": key, "status": "active", "evidence_ids": ["ev-a"]})
    started = time.perf_counter()
    result = build(world, countries="", limit="100")
    elapsed = time.perf_counter() - started
    assert result["coverage"]["relationships"] == 205
    assert result["coverage"]["hidden_relationships"] > 0
    assert elapsed < 2.0


def test_canonical_preview_contains_no_synthetic_geography_assertion():
    root = Path(__file__).resolve().parents[1] / "data"
    entities = {row["id"]: row for file in (root / "entities").rglob('*.json') if (row := json.loads(file.read_text(encoding='utf-8'))).get('record_type') == 'entity'}
    relationships = [json.loads(file.read_text(encoding='utf-8')) for file in (root / "relationships").glob('*.json')]
    evidence = [json.loads(file.read_text(encoding='utf-8')) for file in (root / "evidence").glob('*.json')]
    result = lx.build_bundle(entities, relationships, evidence, {})
    assert result["coverage"]["company_location_links"] >= 2
    assert result["coverage"]["genetic_location_links"] == 0
    assert "rel-fall-creek-operates-sekoya" in {row['id'] for row in result['edges']}
    assert all(row["id"] in {rel["id"] for rel in relationships} for row in result["edges"])
