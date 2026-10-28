"""Durability, trust, source scope and concurrency regressions; no live models."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.services.living_workspaces import Store, Conflict, compose_brief, feed_matches


def overview_result(prompt, kwargs, ids, text="The issuer describes research."):
    from types import SimpleNamespace
    if "checks" in kwargs["schema"]["properties"]:
        packet = json.loads(prompt.split("\n", 1)[1])
        evidence = {row["id"]: row for row in packet["evidence"]}
        checks = []
        for index, row in enumerate(packet["paragraphs"]):
            quotes = [{"source_id": key, "quote": next(evidence[key][field] for field in ("quote", "statement", "saved_article_text") if evidence[key].get(field))[:1000]} for key in row["source_ids"]]
            checks.append({"paragraph": index, "supported": True, "evidence": quotes})
        return SimpleNamespace(parsed={"checks": checks}, provider="perplexity-agent", model="fixture")
    sections = ["The picture", "Key developments", "Key developments", "Why it matters", "What to watch", "What to watch"]
    return SimpleNamespace(parsed={"sentences": [{"text": text, "source_ids": ids, "section": section} for section in sections]}, provider="perplexity-agent", model="fixture")


def token():
    return uuid4().hex


def test_linked_landscapes_are_bidirectional_cited_and_invalidate_summary(client, monkeypatch):
    from app import main
    from app.services import workspace_landscapes as links
    landscape = {"id": "gene-editing", "title": "Breeding landscape", "href": "/landscapes/explorer?topic=gene-editing&adjacent=1", "basis": "v1", "data": {"companies": [{"name": "Example company"}], "gaps": "No trial outcomes established"}}
    monkeypatch.setattr(links, "resolve", lambda main, request, keys: [deepcopy(landscape)] if keys else [])
    page = client.post('/api/workspaces', json={"title": "Combined research", "token": token()}).json()
    page["landscape_links"] = ["gene-editing"]
    saved = client.put('/api/workspaces/page/' + page["id"], json=page).json()
    assert saved["landscape_links"] == ["gene-editing"]
    assert links.backlinks(main, 'gene-editing')[0]["id"] == page["id"]
    generated = client.post('/api/workspaces/generate/' + page["id"], json={"token": token(), "version": saved["version"], "target": "overview"}).json()
    assert generated["overview"]["citations"][0]["kind"] == 'landscape'
    assert 'Example company' in generated["overview"]["text"]
    assert not client.get('/api/workspaces/page/' + page["id"]).json()["overview_stale"]
    landscape["basis"] = 'v2'
    assert client.get('/api/workspaces/page/' + page["id"]).json()["overview_stale"]
    generated["landscape_links"] = []
    assert client.put('/api/workspaces/page/' + page["id"], json=generated).status_code == 200
    assert links.backlinks(main, 'gene-editing') == []
    assert client.post('/workspaces/link-landscape', data={"page_id": page["id"], "landscape_key": "gene-editing"}, headers={"Origin": "https://hostile.example"}).status_code == 403
    relink = client.post('/workspaces/link-landscape', data={"page_id": page["id"], "landscape_key": "gene-editing"}, follow_redirects=False)
    assert relink.status_code == 303
    assert client.get('/api/workspaces/page/' + page["id"]).json()["page"]["landscape_links"] == ['gene-editing']
    generated = client.get('/api/workspaces/page/' + page["id"]).json()["page"]
    generated["landscape_links"] = ['https://attacker.example']
    assert client.put('/api/workspaces/page/' + page["id"], json=generated).status_code == 422


def test_combined_model_packet_requires_landscape_and_page_citations(store, source):
    from types import SimpleNamespace
    from app.services import living_workspaces as living, workspace_landscapes as links
    saved = capture(store, source)
    page = saved["page"]
    items = {saved["item"]["id"]: saved["item"]}
    block = living.compose_overview(page, items, {source["id"]: source})
    links.add_summary_context(block, items, [{"id": "gene-editing", "title": "Landscape", "href": "/landscapes/explorer?topic=gene-editing", "basis": "one", "data": {"companies": [], "gaps": "Trials unknown"}}])
    def complete(prompt, **kwargs):
        assert 'Trials unknown' in prompt
        assert 'Repeated quote.' in prompt
        return overview_result(prompt, kwargs, list(items), "The page and landscape leave trial outcomes unknown.")
    result = living.model_narrative(deepcopy(block), items, completer=complete, sources={source["id"]: source})
    assert result["method"] == 'configured model + cited evidence digest'
    def omit_landscape(prompt, **kwargs):
        return SimpleNamespace(parsed={"sentences": [{"text": "Only page evidence.", "source_ids": [saved["item"]["id"]], "section": "Key developments"}]}, provider='test', model='test')
    rejected = living.model_narrative(deepcopy(block), items, completer=omit_landscape, sources={source["id"]: source})
    assert 'generation_notice' in rejected


def test_preview_repairs_original_eleven_company_scope_once(tmp_path):
    from scripts.preview_living_workspaces import seed, ROOT
    preview, research = tmp_path / 'preview', tmp_path / 'research'
    store = Store(preview)
    with store.transaction() as db:
        store.put(db, 'page', {'id': 'wp-gene-preview', 'title': 'User title', 'blocks': [Store.block('briefing', 'Keep my brief')], 'feed': {'mode': 'any', 'paused': False, 'entity_ids': ['company-ohalo-genetics']}, 'dismissed': []}, 'test')
    seed(research, preview)
    page = store.get('wp-gene-preview')
    ids = {row['entity_id'] for row in json.loads((ROOT / 'data/imports/gene-editing-2026-10-20/snapshot.json').read_text(encoding='utf-8'))['companies']}
    assert len(ids) == 11 and set(page['feed']['entity_ids']) == ids
    assert page['title'] == 'User title' and page['blocks'][0]['text'] == 'Keep my brief'
    assert page['landscape_links'] == ['gene-editing']
    page['feed']['entity_ids'].remove('company-planasa')
    page['landscape_links'] = []
    store.save_page(page['id'], page, 'test')
    seed(research, preview)
    assert 'company-planasa' not in store.get(page['id'])['feed']['entity_ids']
    assert store.get(page['id'])['landscape_links'] == []


def test_social_workspace_reference_preserves_removal_and_avoids_text_copies(client):
    from pathlib import Path
    from app import main
    from app.services.social_intelligence.store import Store as SocialStore, now
    fixture = json.loads((Path(__file__).resolve().parents[1] / 'benchmarks/social-blueberry-fixtures.json').read_text(encoding='utf-8'))['records'][0]
    real = deepcopy(fixture)
    real.update(mode='manual', native_id='workspace-social-test', text='A source-linked social observation for a private unit test.', language='en', translation=None, collected_at=now())
    social = SocialStore(main.INBOX_DIR)
    key = social.ingest([real], main.all_entities())[0]
    sample = social.ingest([fixture], main.all_entities())[0]
    page = client.post('/api/workspaces', json={'title': 'Social notes', 'token': token()}).json()
    payload = {'article_id': key, 'kind': 'social', 'quote': '', 'page_id': page['id'], 'token': token()}
    assert client.post('/api/workspaces/social', json=payload, headers={'Origin': 'https://hostile.example'}).status_code == 403
    saved = client.post('/api/workspaces/social', json=payload)
    assert saved.status_code == 200, saved.text
    assert client.post('/api/workspaces/social', json=payload).json() == saved.json()
    loaded = client.get('/api/workspaces/page/' + page['id']).json()
    assert loaded['social'][0]['text'] == real['text']
    assert real['text'] not in json.dumps(loaded['page'])
    assert client.get('/api/workspaces/history/' + page['id']).text.find(real['text']) == -1
    assert client.post('/api/workspaces/social', json={**payload, 'article_id': sample, 'token': token()}).status_code == 422
    assert client.post('/api/workspaces/social', json={**payload, 'quote': real['text'], 'token': token()}).status_code == 422
    assert 'data-social-workspace-save' in client.get('/api/social/' + key + '/reader').text
    social.remove(key)
    assert client.get('/api/workspaces/page/' + page['id']).json()['social'] == []
    assert client.post('/api/workspaces/social', json={**payload, 'token': token()}).status_code == 422


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "inbox")


@pytest.fixture
def source(store):
    return store.snapshot({"id": "ev-original", "title": "Plant research", "source_url": "https://example.org/article", "source_name": "Research issuer", "published_date": "2026-10-01"}, "Repeated quote. Some context. Repeated quote.", "body_available")


def capture(store, source, **changes):
    payload = {"token": token(), "quote": "Repeated quote.", "locator": {"start": 30}, "kind": "statement", "text": "Issuer reports plant research"}
    payload.update(changes)
    return store.capture(payload, source, "analyst", {"company-a": {}, "company-b": {}})


def test_layout_preferences_follow_account_across_clients_and_reject_stale_writes(client, monkeypatch):
    from app import main
    user = ["alice"]
    monkeypatch.setattr(main, "session_username", lambda request: user[0])
    values = {"view": "cards", "widths": [32, 40, 100, 420, 90, 120, 90, 70], "order": [0, 1, 3, 2, 4, 5, 6, 7], "card_columns": "3", "source_sort": "asc"}
    assert client.get('/api/workspaces/preferences/layout').json()["values"] is None
    payload = {"version": 0, "values": values, "token": token()}
    saved = client.put('/api/workspaces/preferences/layout', json=payload)
    assert saved.status_code == 200, saved.text
    assert client.put('/api/workspaces/preferences/layout', json=payload).json() == saved.json()
    other_device = TestClient(main.app)
    assert other_device.get('/api/workspaces/preferences/layout').json()["values"] == values
    assert other_device.put('/api/workspaces/preferences/layout', json={**payload, "token": token()}).status_code == 409
    user[0] = "bob"
    assert other_device.get('/api/workspaces/preferences/layout').json()["values"] is None
    assert other_device.get('/api/workspaces/history/' + saved.json()["id"]).status_code == 404
    assert other_device.put('/api/workspaces/preferences/layout', json=payload).status_code == 409
    user[0] = "alice"
    assert client.put('/api/workspaces/preferences/layout', json={**payload, "version": 1, "token": token(), "values": {**values, "order": [0]*8}}).status_code == 422
    assert client.put('/api/workspaces/preferences/layout', json={**payload, "version": 1, "token": token(), "values": {**values, "widths": [1]*8}}).status_code == 422
    assert client.put('/api/workspaces/preferences/layout', json={**payload, "version": 1, "token": token()}, headers={"Origin": "https://hostile.example"}).status_code == 403
    assert other_device.get('/api/workspaces/preferences/layout').json() == saved.json()
    changed = {**values, "view": "grid", "widths": [32, 40, 100, 510, 90, 120, 110, 70], "order": [0, 1, 6, 3, 2, 4, 5, 7]}
    updated = other_device.put('/api/workspaces/preferences/layout', json={"version": 1, "values": changed, "token": token()})
    assert updated.status_code == 200, updated.text
    assert client.get('/api/workspaces/preferences/layout').json()["values"] == changed
    assert TestClient(main.app).get('/api/workspaces/preferences/layout').json()["values"] == changed
    assert Store(main.INBOX_DIR).layout_preferences("alice")["values"] == changed


def test_default_berry_workspaces_are_durable_and_preserve_captures(store, source):
    ids = store.ensure_berry_workspaces()
    assert set(ids) == {"blueberry", "blackberry", "raspberry", "strawberry"}
    original = store.get(ids["raspberry"])
    saved = capture(store, source, page_id=ids["raspberry"])
    assert saved["page"]["id"] == ids["raspberry"]
    assert saved["item"]["verification_state"] == "unverified"
    reopened = Store(store.inbox)
    assert reopened.ensure_berry_workspaces() == ids
    assert reopened.get(ids["raspberry"])["blocks"] == saved["page"]["blocks"]
    assert reopened.get(ids["raspberry"])["version"] == saved["page"]["version"]
    assert reopened.get(ids["blueberry"])["version"] == original["version"]
    assert len(reopened.rows("page")) == 4


def test_restart_exact_occurrence_and_projection(store, source):
    start = source["text"].rindex("Repeated quote.")
    saved = capture(store, source, locator={"start": start})
    reopened = Store(store.inbox)
    item = reopened.get(saved["item"]["id"])
    assert item["quote"] == "Repeated quote."
    assert item["locator"]["start"] == start
    assert item["locator"]["state"] == "exact"
    assert reopened.get(item["source_id"])["text"] == source["text"]
    evidence = json.loads((store.inbox / "evidence" / (item["id"] + ".json")).read_text())
    assert evidence["status"] == "in_review"
    assert evidence["verification_state"] == "unverified"
    assert evidence["workspace_capture"]["quote"] == item["quote"]


def test_wrong_position_never_jumps_to_first_quote(store, source):
    item = capture(store, source, locator={"start": 1})["item"]
    assert item["locator"]["state"] == "unresolved"
    assert "start" not in item["locator"]


def test_retry_and_shared_item_undo_only_removes_placement(store, source):
    key = token()
    first = capture(store, source, token=key)
    again = capture(store, source, token=key)
    assert first == again
    assert len(store.rows("item")) == 1
    assert len(store.get(first["page"]["id"])["blocks"]) == 1
    with pytest.raises(Conflict):
        capture(store, source, token=key, text="different")
    other = store.create_page("Second", None, "analyst", token())
    second = capture(store, source, page_id=other["id"])
    assert first["item"]["id"] == second["item"]["id"]
    page = store.get(first["page"]["id"])
    page["blocks"] = []
    store.save_page(page["id"], page, "analyst")
    assert store.get(other["id"])["blocks"][0]["item_id"] == first["item"]["id"]
    assert store.get(first["item"]["id"])


def test_stale_and_simultaneous_updates_cannot_erase_capture(store, source):
    saved = capture(store, source)
    original = deepcopy(saved["page"])
    capture(store, source, text="Another source claim")
    with pytest.raises(Conflict):
        store.save_page(original["id"], original, "other analyst")
    page = store.get(original["id"])
    def save(index):
        try:
            store.save_page(page["id"], {**page, "title": str(index)}, "analyst")
            return True
        except Conflict:
            return False
    with ThreadPoolExecutor(max_workers=2) as workers:
        assert sum(workers.map(save, range(2))) == 1
    assert len(store.get(page["id"])["blocks"]) == 2


def test_sources_versioned_not_mutated_and_review_not_overwritten(store, source):
    saved = capture(store, source)
    item = saved["item"]
    evidence_path = store.inbox / "evidence" / (item["id"] + ".json")
    evidence = json.loads(evidence_path.read_text())
    evidence["verification_state"] = "verified_primary"
    evidence_path.write_text(json.dumps(evidence))
    capture(store, source)
    assert json.loads(evidence_path.read_text())["verification_state"] == "verified_primary"
    revised = deepcopy(source)
    revised["text"] += " A revision."
    revised["id"] += "revision"
    result = capture(store, revised)
    assert result["item"]["source_id"] != item["source_id"]
    assert store.get(item["source_id"])["text"] == source["text"]


def test_failed_projection_recovers_outbox(store, source, monkeypatch):
    original = store.flush
    monkeypatch.setattr(store, "flush", lambda: (_ for _ in ()).throw(OSError("disk unavailable")))
    key = token()
    with pytest.raises(OSError):
        capture(store, source, token=key)
    monkeypatch.setattr(store, "flush", original)
    store.flush()
    saved = capture(store, source, token=key)
    assert (store.inbox / "evidence" / (saved["item"]["id"] + ".json")).exists()
    assert len(store.rows("item")) == 1


def test_relationship_nature_is_not_verification_or_comention(store, source):
    plain = capture(store, source, entity_ids=["company-a", "company-b"])
    assert plain["item"]["relation"] is None
    relation = {"subject_id": "company-a", "object_id": "company-b", "predicate": "partners_with", "nature": "analyst_hypothesis", "scope": "Preview only"}
    saved = capture(store, source, kind="relationship", relation=relation, allowed_predicates=["partners_with"])
    assert saved["item"]["nature"] == "analyst_hypothesis"
    assert saved["item"]["verification_state"] == "unverified"
    with pytest.raises(ValueError):
        capture(store, source, relation={**relation, "object_id": "ambiguous-name"}, allowed_predicates=["partners_with"])


def test_feed_scopes_and_pause():
    row = {"entity_ids": ["company-a"], "title": "Strawberry genetics", "source_id": "src-a"}
    config = {"mode": "any", "entity_ids": ["company-a"], "keywords": ["blackberry"]}
    assert feed_matches(row, config) == ["entity: company-a"]
    assert not feed_matches(row, {**config, "mode": "all"})
    assert not feed_matches(row, {**config, "paused": True})
    assert not feed_matches(row, {"mode": "any"})


def test_generation_cites_only_selected_curated_material(store, source):
    first = capture(store, source)
    second = capture(store, source, kind="hypothesis", text="Preview hypothesis")
    page = second["page"]
    items = {i["id"]: i for i in store.rows("item")}
    sources = {s["id"]: s for s in store.rows("source")}
    brief = compose_brief(page, items, sources, [first["block_id"]])
    assert len(brief["citations"]) == 1
    assert "Preview hypothesis" not in brief["text"]
    assert brief["source_versions"][0]["id"] == first["item"]["id"]
    all_brief = compose_brief(page, items, sources, [])
    assert "Analyst hypothesis (speculative)" in all_brief["text"]
    assert "Source states (unverified)" in brief["text"]
    assert "https://example.org/article" in brief["text"]
    with pytest.raises(ValueError):
        compose_brief(page, items, sources, ["missing-block"])


def test_page_authored_notes_enter_existing_evidence_review(store):
    page = store.create_page("Notes", None, "Johnny", token())
    page["blocks"] = [store.block("hypothesis", "Could additional trials be useful?")]
    saved = store.save_page(page["id"], page, "Johnny")
    store.flush()
    key = saved["blocks"][0]["item_id"]
    assert store.get(key)["nature"] == "analyst_hypothesis"
    assert (store.inbox / "evidence" / (key + ".json")).exists()
    saved["blocks"][0]["text"] = "Revised analyst question"
    revised = store.save_page(page["id"], saved, "Johnny")
    assert revised["blocks"][0]["item_id"] != key
    assert store.get(key)["text"] == "Could additional trials be useful?"


def test_model_failure_and_invalid_citations_keep_grounded_digest(store, source):
    from types import SimpleNamespace
    from app.services.living_workspaces import model_narrative
    saved = capture(store, source)
    items = {saved["item"]["id"]: saved["item"]}
    block = compose_brief(saved["page"], items, {source["id"]: source}, [])
    original = block["text"]
    def bad(*args, **kwargs):
        return SimpleNamespace(parsed={"sentences": [{"text": "An unsupported acquisition occurred", "source_ids": ["unselected"]}]}, provider="fixture", model="fixture")
    result = model_narrative(block, items, completer=bad)
    assert result["text"] == original
    assert "invalid" in result["generation_notice"]
    def valid(*args, **kwargs):
        return SimpleNamespace(parsed={"sentences": [{"text": "The issuer reports research.", "source_ids": list(items)}]}, provider="fixture", model="fixture")
    result = model_narrative(block, items, completer=valid)
    assert "Generated interpretation of unverified source claims" in result["text"]
    assert result["model"] == "fixture"
    from app.services.ai_gateway.errors import GatewayAuthError
    def exhausted(*args, **kwargs):
        raise GatewayAuthError("HTTP failure (401): insufficient_quota")
    result = model_narrative(block, items, completer=exhausted)
    assert "credits are exhausted" in result["generation_notice"]
    assert "HTTP failure" not in result["generation_notice"]


@pytest.fixture
def client(tmp_path, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "all_entities", lambda: [{"id": "company-a", "name": "A", "entity_type": "company"}])
    monkeypatch.setattr(main, "entity_index", lambda: {"company-a": {"name": "A"}})
    monkeypatch.setattr(main, "published_evidence", lambda: [])
    return TestClient(main.app)


def test_private_routes_readonly_auth_csrf_and_stale(client, monkeypatch):
    from app import main
    request = {"title": "Research", "token": token()}
    assert client.post('/api/workspaces', json=request, headers={"Origin": "https://hostile.example"}).status_code == 403
    page = client.post('/api/workspaces', json=request).json()
    assert page["title"] == "Research"
    assert client.put('/api/workspaces/page/' + page["id"], json=page).status_code == 200
    assert client.put('/api/workspaces/page/' + page["id"], json=page).status_code == 409
    assert client.get('/workspaces/' + page["id"]).status_code == 200
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    assert client.get('/api/workspaces').status_code == 403
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setenv('BIOS_REMOTE_INTERACTIVE', 'true')
    monkeypatch.setenv('BIOS_REVIEW_USERNAME', 'tester')
    monkeypatch.setenv('BIOS_REVIEW_PASSWORD', 'test-pass')
    monkeypatch.setenv('BIOS_SESSION_SECRET', 'test-secret-that-is-long-enough-for-this-test')
    assert client.get('/api/workspaces', follow_redirects=False).status_code == 302


def test_server_resolves_sources_and_feed_arrivals(client, monkeypatch):
    from app import main, living_workspace_routes as routes
    source_record = {"id": "ev-source", "title": "Plant genetics", "source_url": "https://example.org", "source_name": "Issuer", "article": {"full_text": "Complete source prose " * 40}, "entity_ids": ["company-a"]}
    monkeypatch.setattr(routes, "personal_source_record", lambda key: source_record if key == 'ev-source' else None)
    page = client.post('/api/workspaces', json={"title": "Research", "token": token()}).json()
    payload = {"token": token(), "page_id": page["id"], "article_id": "ev-source", "kind": "evidence", "quote": "Complete source prose", "locator": {"start": 0}, "entity_ids": ["company-a"]}
    saved = client.post('/api/workspaces/capture', json=payload)
    assert saved.status_code == 200, saved.text
    assert client.post('/api/workspaces/capture', json=payload).json() == saved.json()
    assert client.post('/api/workspaces/capture', json={**payload, "article_id": "missing", "token": token()}).status_code == 404
    page = client.get('/api/workspaces/page/' + page["id"]).json()["page"]
    page["feed"] = {"mode": "all", "entity_ids": ["company-a"], "keywords": ["genetics"], "paused": False}
    client.put('/api/workspaces/page/' + page["id"], json=page)
    records = {}
    monkeypatch.setattr(routes, "world", lambda: (main, {}, records, {}))
    assert client.get('/api/workspaces/feed/' + page["id"]).json()["items"] == []
    records["ev-source"] = source_record
    records["ev-unrelated"] = {"id": "ev-unrelated", "title": "Unrelated"}
    feed = client.get('/api/workspaces/feed/' + page["id"]).json()
    assert [r["id"] for r in feed["items"]] == ["ev-source"]
    assert 'class="digest-card news-card"' in feed["html"]
    assert 'data-open-reader href="/intelligence/ev-source?personal=1"' in feed["html"]
    assert 'data-personal-action="save"' in feed["html"]
    assert 'data-workspace-feed-action="feature"' in feed["html"]
    assert 'data-workspace-feed-action="annotate"' in feed["html"]
    assert 'data-workspace-feed-action="dismiss"' in feed["html"]
    assert 'Unreviewed' in feed["html"]
    source_record["title"] = 'Plant genetics <script>alert(1)</script>'
    source_record["source_name"] = '<script>publisher</script>'
    escaped = client.get('/api/workspaces/feed/' + page["id"]).json()["html"]
    assert '<script>alert(1)</script>' not in escaped
    assert '&lt;script&gt;' in escaped
    brief = client.post('/api/workspaces/generate/' + page["id"], json={"token": token(), "version": page["version"] + 1, "selected": []})
    assert brief.status_code == 200, brief.text
    assert client.get('/api/workspaces/export/' + page["id"]).status_code == 200
    assert client.get('/workspaces/evidence/' + saved.json()["item"]["id"]).status_code == 200


def test_item_revision_has_separate_unverified_review_identity(client, source):
    from app import main
    store = Store(main.INBOX_DIR)
    saved = capture(store, source)
    item = saved["item"]
    revised = client.patch('/api/workspaces/item/' + item["id"], json={"version": item["version"], "text": "Revised interpretation"})
    assert revised.status_code == 200, revised.text
    review_id = revised.json()["review_evidence_id"]
    assert review_id != item["id"]
    draft = json.loads((main.INBOX_DIR / 'evidence' / (review_id + '.json')).read_text())
    assert draft["verification_state"] == "unverified"
    assert draft["workspace_capture"]["item_version"] == 2
    assert store.get(item["id"])["quote"] == item["quote"]


def test_move_is_atomic_idempotent_and_stale_safe(client, source):
    from app import main
    store = Store(main.INBOX_DIR)
    saved = capture(store, source)
    target = store.create_page("Destination", None, "analyst", token())
    payload = {"token": token(), "from_page": saved["page"]["id"], "to_page": target["id"], "block_id": saved["block_id"], "from_version": saved["page"]["version"], "to_version": target["version"] - 1}
    assert client.post('/api/workspaces/move', json=payload).status_code == 409
    assert store.get(saved["page"]["id"])["blocks"]
    assert not store.get(target["id"])["blocks"]
    payload["to_version"] = target["version"]
    response = client.post('/api/workspaces/move', json=payload)
    assert response.status_code == 200, response.text
    assert client.post('/api/workspaces/move', json=payload).json() == response.json()
    assert not store.get(saved["page"]["id"])["blocks"]
    assert len(store.get(target["id"])["blocks"]) == 1
    assert store.get(saved["item"]["id"])


def test_overview_is_manual_versioned_and_freshness_tracks_material(client, source, monkeypatch):
    from app import main
    from app.services.ai_gateway import untrusted_complete
    monkeypatch.setattr(untrusted_complete, "maybe_untrusted_completer", lambda: None)
    store = Store(main.INBOX_DIR)
    captured = capture(store, source)
    page = captured["page"]
    unavailable = client.post('/api/workspaces/generate/' + page["id"], json={"token": token(), "version": page["version"], "target": "overview", "use_model": True})
    assert unavailable.status_code == 422
    assert store.get(page["id"]) == page
    payload = {"token": token(), "version": page["version"], "target": "overview", "use_model": False}
    response = client.post('/api/workspaces/generate/' + page["id"], json=payload)
    assert response.status_code == 200, response.text
    summary_page = response.json()
    assert summary_page["blocks"] == page["blocks"]
    assert summary_page["content_updated_at"] == page["content_updated_at"]
    assert summary_page["overview"]["generated_at"]
    assert summary_page["overview"]["citations"][0]["item_id"] == captured["item"]["id"]
    assert client.post('/api/workspaces/generate/' + page["id"], json=payload).json() == summary_page
    loaded = client.get('/api/workspaces/page/' + page["id"]).json()
    assert loaded["overview_stale"] is False
    old_overview = summary_page["overview"]
    summary_page["blocks"].append(store.block("paragraph", "New analyst context"))
    updated = client.put('/api/workspaces/page/' + page["id"], json=summary_page).json()
    assert updated["overview"] == old_overview
    assert updated["content_updated_at"] > page["content_updated_at"]
    assert client.get('/api/workspaces/page/' + page["id"]).json()["overview_stale"] is True
    exported = client.get('/api/workspaces/export/' + page["id"]).text
    assert "Page overview · generated" in exported
    assert "https://example.org/article" in exported
    item = store.get(captured["item"]["id"])
    client.patch('/api/workspaces/item/' + item["id"], json={"version": item["version"], "text": "Revised claim"})
    assert client.get('/api/workspaces/page/' + page["id"]).json()["overview_stale"] is True


def test_overview_model_uses_saved_article_and_link_only_from_curated_page(client, source, monkeypatch):
    from types import SimpleNamespace
    from app import main
    from app.services.ai_gateway import untrusted_complete
    store = Store(main.INBOX_DIR)
    saved = capture(store, source, kind="article", quote="", text="")
    other = store.snapshot({"id": "unfeatured", "title": "Excluded"}, "UNFEATURED SECRET", "body_available")
    prompts = []
    def complete(prompt, **kwargs):
        prompts.append(prompt)
        return overview_result(prompt, kwargs, [saved["item"]["id"]])
    monkeypatch.setattr(untrusted_complete, "maybe_untrusted_completer", lambda: complete)
    monkeypatch.delenv("BIOS_PERPLEXITY_AGENT_BASE_URL", raising=False)
    page = saved["page"]
    response = client.post('/api/workspaces/generate/' + page["id"], json={"token": token(), "version": page["version"], "target": "overview", "use_model": True})
    assert response.status_code == 200, response.text
    packet = json.loads(prompts[0].split('\n', 1)[1])
    assert len(packet) == 1
    assert packet[0]["saved_article_text"] == source["text"]
    assert packet[0]["source_url"] == source["url"]
    assert packet[0]["availability"] == source["availability"]
    assert packet[0]["source_version"] == source["id"]
    assert other["text"] not in prompts[0]
    assert response.json()["overview"]["provider"] == "perplexity-agent"
    assert "## Key developments" in response.json()["overview"]["text"]
    assert "The issuer describes research." in response.json()["overview"]["text"]
    assert "Generated interpretation" not in response.json()["overview"]["text"]
    assert "## Evidence limits" not in response.json()["overview"]["text"]
    assert response.json()["overview"]["supporting_digest"]
    monkeypatch.setenv("BIOS_PERPLEXITY_AGENT_BASE_URL", "https://other.example/v1/agent")
    blocked = client.post('/api/workspaces/generate/' + page["id"], json={"token": token(), "version": response.json()["version"], "target": "overview", "use_model": True})
    assert blocked.status_code == 422
    assert len(prompts) == 2
    assert "approved Perplexity endpoint" in blocked.json()["detail"]
    assert client.get('/api/workspaces/page/' + page["id"]).json()["page"]["overview"] == response.json()["overview"]

    monkeypatch.delenv("BIOS_PERPLEXITY_AGENT_BASE_URL")
    def unsupported(prompt, **kwargs):
        result = overview_result(prompt, kwargs, [saved["item"]["id"]])
        if "checks" in result.parsed:
            result.parsed["checks"][0]["supported"] = False
        return result
    monkeypatch.setattr(untrusted_complete, "maybe_untrusted_completer", lambda: unsupported)
    before = store.get(page["id"])
    failed = client.post('/api/workspaces/generate/' + page["id"], json={"token": token(), "version": before["version"], "target": "overview", "use_model": True})
    assert failed.status_code == 422
    assert "unsupported claims" in failed.json()["detail"]
    assert store.get(page["id"]) == before


def test_publication_review_preserves_workspace_nature(monkeypatch, tmp_path):
    from app import main
    from tests.test_review_publish_portability import _restore, _publish, SOURCE_ID
    inbox, data = tmp_path / "inbox", tmp_path / "data"
    monkeypatch.setattr(main, 'INBOX_DIR', inbox)
    monkeypatch.setattr(main, 'DATA_DIR', data)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    repos = main.get_repositories(data, main.SCHEMAS_DIR)
    repos.sources.create({"id": SOURCE_ID, "name": "Source fixture"})
    key = _restore(inbox)
    path = inbox / 'evidence' / (key + '.json')
    draft = json.loads(path.read_text())
    draft.update(workspace_capture={"nature": "analyst_hypothesis", "quote": "Preserved source quote", "source_version": "src-fixture"}, verification_state="unverified")
    path.write_text(json.dumps(draft))
    result = _publish(TestClient(main.app), key)
    assert result.status_code == 303, result.text
    published = repos.evidence.get(key)
    assert published["workspace_capture"]["nature"] == "analyst_hypothesis"
    assert published["verification_state"] == "unverified"
