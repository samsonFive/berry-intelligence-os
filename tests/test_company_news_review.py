from copy import deepcopy
import hashlib
import json

import pytest

from app.services.report_builder import company_news as news


def entity(name="ABZ Seeds", identifier="company-abz", aliases=None):
    return {"id": identifier, "name": name, "entity_type": "company", "status": "active", "aliases": aliases or [], "berry_ids": ["berry-strawberry"]}


def record(identifier="ev-launch", *, company="ABZ Seeds", stamp="2025-07-01", body=True, url=None):
    row = {"id": identifier, "title": company + " introduces a new strawberry variety", "status": "published", "source_name": "Example Grower Journal",
           "published_date": stamp, "source_url": url or "https://grower.example/" + identifier, "berry_ids": ["berry-strawberry"], "entity_ids": []}
    if body:
        row["article"] = {"paragraphs": [{"text": company + " introduced a new strawberry cultivar called Ruby. The breeding company reported a commercial variety launch for growers in Spain, with plans to expand nursery supply next season."}]}
    else:
        row["summary"] = company + " introduces a new strawberry cultivar."
    return row


def review(*, roster="ABZ Seeds", companies=None, source_scope="archive", **kw):
    return news.create_review(roster, entities=companies or [entity()], from_date="2025-07-01", through_date="2026-11-13", as_of="2026-11-13", berry_id="berry-strawberry", source_scope=source_scope, **kw)


def step(snapshot, rows, tmp_path, **kwargs):
    return news.research_one_company(snapshot, news.next_company_key(snapshot), entities=[entity()], archive_records=rows, inbox_dir=tmp_path, **kwargs)


def test_roster_exact_alias_and_ambiguity_preserve_requested_names():
    companies = [entity(aliases=["ABZ"]), entity("Another Seeds", "company-other", ["Shared"]), entity("Third Seeds", "company-third", ["Shared"])]
    result = review(roster="- ABZ\nGenetics Unknown\nShared", companies=companies)
    assert [r["requested_name"] for r in result["companies"]] == ["ABZ", "Genetics Unknown", "Shared"]
    assert [r["resolution"] for r in result["companies"]] == ["resolved", "unresolved", "ambiguous"]
    assert result["companies"][2]["candidate_ids"] == ["company-other", "company-third"]
    assert all(r["disposition"] == "pending" for r in result["companies"])


@pytest.mark.parametrize("kwargs", [
    {"from_date": "2026-13-01"}, {"from_date": "2026-11-14"}, {"through_date": "2026-11-14"},
    {"as_of": "2999-01-01"}, {"source_scope": "secret-provider"}, {"berry_id": "berry-cannabis"},
])
def test_scope_validation_never_silently_changes_requested_dates(kwargs):
    options = dict(roster="ABZ", entities=[entity(aliases=["ABZ"])], from_date="2025-07-01", through_date="2026-11-13", as_of="2026-11-13", source_scope="archive", berry_id="berry-strawberry")
    options.update(kwargs)
    with pytest.raises(ValueError):
        news.create_review(**options)


def test_roster_limit_errors_instead_of_truncating():
    with pytest.raises(ValueError, match="100"):
        review(roster=[f"Company {i}" for i in range(101)])


def test_legal_company_commas_are_not_split_into_fabricated_roster_rows():
    result = review(roster="Plant Sciences, Inc.", companies=[entity("Plant Sciences, Inc.")])
    assert len(result["companies"]) == 1
    assert result["companies"][0]["requested_name"] == "Plant Sciences, Inc."
    assert result["companies"][0]["resolution"] == "resolved"


def test_twenty_seven_companies_each_receive_a_completed_attempt(tmp_path):
    entities = [entity(f"Seed Company {i:02}", f"company-{i:02}") for i in range(27)]
    result = review(roster=[e["name"] for e in entities], companies=entities)
    while key := news.next_company_key(result):
        result = news.research_one_company(result, key, entities=entities, archive_records=[], inbox_dir=tmp_path)
    assert result["completed_company_count"] == 27
    assert len(result["companies"]) == 27
    assert all(c["disposition"] == "no_qualifying_findings" for c in result["companies"])
    assert result["status"] == "complete" and news.next_company_key(result) is None


def test_archive_first_inclusive_window_and_no_silent_web(tmp_path):
    initial = review()
    untouched = deepcopy(initial)
    rows = [record("ev-start"), record("ev-end", stamp="2026-11-13"), record("ev-old", stamp="2025-06-30"), record("ev-future", stamp="2026-11-14")]
    result = step(initial, rows, tmp_path, discoverer=lambda *a, **k: pytest.fail("archive-only must not call the web"))
    assert initial == untouched
    assert {s["published_date"] for s in result["sources"]} == {"2025-07-01", "2026-11-13"}
    assert len(result["entries"]) == 2
    assert all(e["included"] and e["entry_type"] == "development" for e in result["entries"])
    assert all("plans" in e["qualification"] for e in result["entries"])
    assert result["companies"][0]["archive_status"] == "complete"
    assert result["companies"][0]["web_status"] == "not_requested"


def test_metadata_and_undated_sources_are_excluded_leads(tmp_path):
    result = step(review(), [record("ev-meta", body=False), record("ev-unknown", stamp="2026-07")], tmp_path)
    assert len(result["entries"]) == 2
    assert all(not e["included"] and not e["summary"] and e["entry_type"] == "lead" for e in result["entries"])
    assert {s["eligibility"] for s in result["sources"]} == {"metadata_only", "undated"}
    assert any("2026-07" in s["qualification"] for s in result["sources"])
    assert all(not s["published_date"] for s in result["sources"] if s["eligibility"] == "undated")


def test_web_gap_fill_runs_after_archive_even_when_archive_has_findings(tmp_path):
    calls = []
    def discover(plan, **kwargs):
        calls.append((plan, kwargs))
        assert plan.start == "2025-07-01" and plan.end == "2026-11-13"
        assert kwargs["constraints"]["public_labels"][0] == "ABZ Seeds"
        assert "archive" not in json.dumps(kwargs["constraints"])
        return {"items": [], "status": "complete", "candidate_count": 0, "queries_this_request": 1}
    result = step(review(source_scope="combined"), [record()], tmp_path, discoverer=discover)
    assert len(calls) == 1
    assert result["companies"][0]["disposition"] == "has_findings"
    assert result["companies"][0]["counts"]["web_queries"] == 1


def test_blocked_and_budget_exclusions_cannot_be_successful_coverage(tmp_path):
    def discover(plan, **kwargs):
        kwargs["capture_audit"]([{"capture_status": "blocked"}, {"capture_status": "budget_excluded"}])
        return {"items": [], "status": "complete", "candidate_count": 45, "queries_this_request": 1}
    result = step(review(source_scope="combined"), [], tmp_path, discoverer=discover)
    company = result["companies"][0]
    assert company["web_status"] == "partial" and company["disposition"] == "incomplete"
    assert result["status"] == "partial" and not result["entries"]
    assert company["counts"]["web_budget_excluded"] == 1
    assert news.next_company_key(result) is None


def test_provider_failure_is_sanitized_and_not_a_no_hit_result(tmp_path):
    def discover(*args, **kwargs):
        raise RuntimeError("https://provider.invalid?api_key=DO_NOT_LOG")
    result = step(review(source_scope="combined"), [], tmp_path, discoverer=discover)
    assert result["companies"][0]["disposition"] == "incomplete"
    assert "DO_NOT_LOG" not in json.dumps(result)
    assert "RuntimeError" in json.dumps(result)


def test_unresolved_identity_can_retain_leads_without_guessing(tmp_path):
    result = step(review(roster="Unknown Seeds"), [record(company="Unknown Seeds")], tmp_path)
    assert result["companies"][0]["resolution"] == "unresolved"
    assert result["companies"][0]["disposition"] == "identity_unresolved"
    assert result["entries"] and all(not e["included"] for e in result["entries"])
    assert all(s["eligibility"] == "identity_unresolved" for s in result["sources"])


def test_same_url_archive_web_duplicate_preserves_archive_trust(tmp_path):
    row = record()
    def discover(plan, **kwargs):
        return {"items": [{**row, "support_status": "body_supported", "passage": row["article"]["paragraphs"][0]["text"], "passage_locator": "article:0", "source_version": "web-version", "capture_status": "full"}], "status": "complete", "candidate_count": 1}
    result = step(review(source_scope="combined"), [row], tmp_path, discoverer=discover)
    assert len(result["sources"]) == 1 and result["sources"][0]["origin"] == "archive"
    assert len(result["entries"]) == 1


def test_completed_steps_do_not_refresh_or_clobber_analyst_edits(tmp_path):
    result = step(review(), [record()], tmp_path)
    result["entries"][0]["edits"] = {"headline": "Analyst headline", "summary": "Checked source statement", "source_ids": ["invented"]}
    result["entries"][0]["included"] = False
    repeated = news.research_one_company(result, result["companies"][0]["key"], entities=[entity()], archive_records=[], inbox_dir=tmp_path)
    assert repeated == result
    effective = news.effective_entry(result["entries"][0])
    assert effective["headline"] == "Analyst headline" and effective["summary"] == "Checked source statement"
    assert effective["source_ids"] == result["entries"][0]["source_ids"]
    assert effective["analyst_edited"]
    assert "Analyst headline" not in "\n".join(s.prose for s in news.review_sections(result))


def test_existing_reader_capture_is_hydrated_without_network_or_mutation(tmp_path):
    from app.services.feed_first_reader import capture_path
    row = record(body=False)
    saved = {"item_id": row["id"], "url": row["source_url"], "availability": "full", "passages": [record()["article"]["paragraphs"][0]["text"]]}
    path = capture_path(tmp_path, row["id"])
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(saved), encoding="utf-8")
    original = deepcopy(row)
    hydrated = news.prepare_archive_records({row["id"]: row}, tmp_path)
    assert hydrated[0]["article"]["paragraphs"] and row == original
    result = step(review(), hydrated, tmp_path)
    assert result["entries"][0]["included"]
    assert json.loads(path.read_text(encoding="utf-8")) == saved


def test_archive_limit_exposes_overflow_and_marks_incomplete(tmp_path, monkeypatch):
    monkeypatch.setattr(news, "ARCHIVE_SOURCE_LIMIT", 2)
    result = step(review(), [record(f"ev-{i}", stamp=f"2025-07-{i+1:02}") for i in range(5)], tmp_path)
    company = result["companies"][0]
    assert company["counts"]["archive_matched"] == 5
    assert company["counts"]["archive_retained"] == 2 and company["counts"]["archive_overflow"] == 3
    assert company["archive_status"] == "partial" and company["disposition"] == "incomplete"


def test_narrative_and_packet_use_saved_effective_rows(tmp_path):
    result = step(review(), [record()], tmp_path)
    result["entries"][0]["edits"] = {"headline": "Reviewed variety launch", "summary": "Editor verified the source.", "event_date": "2025-07-01"}
    sections = news.review_sections(result)
    assert "Reviewed variety launch" in sections[0].prose
    assert "Editor verified the source." in sections[0].prose
    packet = news.review_packet(result)
    assert set(sections[0].citation_ids) <= packet["known_ids"]
    assert packet["source_trace"][0]["href"].startswith("https://")


def test_global_budgets_are_explicit_and_do_not_drop_roster_or_buy_more_searches(tmp_path, monkeypatch):
    monkeypatch.setattr(news, "MAX_SNAPSHOT_SOURCES", 1)
    monkeypatch.setattr(news, "MAX_SNAPSHOT_ENTRIES", 1)
    entities = [entity(), entity("Second Seeds", "company-second")]
    result = review(roster=[e["name"] for e in entities], companies=entities, source_scope="combined")
    calls = []
    def discover(*args, **kwargs):
        calls.append(args[0].raw_query)
        return {"items": [], "status": "complete", "candidate_count": 0}
    rows = [record(), record("ev-second", company="Second Seeds")]
    while key := news.next_company_key(result):
        result = news.research_one_company(result, key, entities=entities, archive_records=rows, inbox_dir=tmp_path, discoverer=discover)
    assert len(result["companies"]) == result["completed_company_count"] == 2
    assert len(calls) == len(result["sources"]) == len(result["entries"]) == 1
    assert result["companies"][1]["disposition"] == "incomplete"
    assert result["companies"][1]["counts"]["snapshot_source_budget_excluded"] == 1
    assert any("budget" in note for note in result["companies"][1]["notes"])


def test_deleted_source_url_cannot_be_reintroduced_from_web(tmp_path):
    row = record()
    def discover(*args, **kwargs):
        return {"items": [row], "status": "complete", "candidate_count": 1}
    initial = review(source_scope="combined")
    initial["excluded_source_urls"] = [row["source_url"]]
    result = step(initial, [row], tmp_path, discoverer=discover)
    assert not result["sources"] and not result["entries"]
    assert result["companies"][0]["counts"]["deleted_source_exclusions"] == 2


def test_human_source_hold_survives_shared_retrieval_projection(tmp_path):
    row = record()
    row["source_review_hold"] = "Original edition must be checked"
    result = step(review(), [row], tmp_path)
    assert result["sources"][0]["eligibility"] == "scope_unverified"
    assert result["sources"][0]["excerpt"] == ""
    assert not result["entries"][0]["included"]
    assert "Original edition" in result["sources"][0]["qualification"]


def test_capture_search_and_modification_dates_never_substitute_for_publication(tmp_path):
    rows = []
    for i, basis in enumerate(("captured_at", "search_result_date", "last_modified", "retrieval_date")):
        row = record(f"ev-date-{i}")
        row["published_date_basis"] = basis
        rows.append(row)
    result = step(review(), rows, tmp_path)
    assert all(s["published_date"] == "" and s["eligibility"] == "undated" for s in result["sources"])
    assert all(not e["included"] for e in result["entries"])


def test_corrupt_stored_reader_body_is_partial_not_a_successful_no_hit(tmp_path):
    from app.services.feed_first_reader import capture_path
    row = record(body=False)
    path = capture_path(tmp_path, row["id"])
    path.parent.mkdir(parents=True)
    path.write_text("not-json", encoding="utf-8")
    hydrated = news.prepare_archive_records([row], tmp_path)
    result = step(review(), hydrated, tmp_path)
    assert result["companies"][0]["archive_status"] == "partial"
    assert result["companies"][0]["disposition"] == "incomplete"
    assert result["companies"][0]["counts"]["archive_source_read_issues"] == 1


def test_malformed_source_does_not_discard_other_valid_company_findings(tmp_path):
    malformed_body = record("ev-bad-body")
    malformed_body["article"] = {"paragraphs": 7}
    malformed_provenance = record("ev-bad-provenance")
    malformed_provenance["capture_provenance"] = "not an object; DO_NOT_LEAK"
    result = step(review(), [malformed_body, malformed_provenance, record()], tmp_path)
    assert len(result["entries"]) == 1 and result["entries"][0]["included"]
    assert result["companies"][0]["archive_status"] == "partial"
    assert result["companies"][0]["counts"]["archive_source_errors"] == 2
    assert len(result["companies"][0]["source_errors"]) == 2
    assert "DO_NOT_LEAK" not in json.dumps(result)


def test_spanish_business_announcement_is_retained_for_verification_not_false_background(tmp_path):
    row = record()
    row["title"] = "ABZ Seeds: nuevo acuerdo comercial de fresas"
    row["article"] = {"paragraphs": [{"text": "ABZ Seeds presentó un nuevo acuerdo comercial de fresas con una red de supermercados. La empresa confirmó su presencia en varios mercados europeos para la próxima campaña."}]}
    result = step(review(), [row], tmp_path)
    assert result["entries"] and not result["entries"][0]["included"]
    assert result["sources"][0]["eligibility"] == "editorial_verification"
    assert result["companies"][0]["disposition"] == "incomplete"
    assert "language" in result["sources"][0]["qualification"]


def test_untranslated_japanese_company_announcement_does_not_disappear(tmp_path):
    name = "ミヨシグループ"
    company = entity(name, "company-miyoshi")
    row = record(company=name)
    row["title"] = name + "がイチゴの新品種販売契約を発表"
    row["article"] = {"paragraphs": [{"text": name + "はイチゴの新品種について新しい販売契約を発表しました。日本国内の生産者への苗の供給を進めます。"}]}
    row["berry_ids"] = []
    result = news.research_one_company(review(roster=name, companies=[company]), news.next_company_key(review(roster=name, companies=[company])), entities=[company], archive_records=[row], inbox_dir=tmp_path)
    assert result["sources"][0]["title"] == row["title"]
    assert result["sources"][0]["eligibility"] == "scope_unverified"
    assert not result["entries"][0]["included"]
    assert result["companies"][0]["disposition"] == "incomplete"


def test_nonkeyword_english_business_wording_is_verification_not_no_new_activity(tmp_path):
    row = record()
    row["title"] = "ABZ Seeds now on the shelves of a major strawberry retailer"
    row["article"] = {"paragraphs": [{"text": "ABZ Seeds strawberries are now on the shelves of an additional national supermarket chain. The company described the arrangement and the countries covered by it."}]}
    result = step(review(), [row], tmp_path)
    assert result["sources"][0]["eligibility"] == "editorial_verification"
    assert result["companies"][0]["disposition"] == "incomplete"


def test_brief_generated_quote_and_requested_dates_in_public_query(tmp_path):
    calls = []
    row = record()
    row["article"]["paragraphs"][0]["text"] += " " + " ".join(f"detail{i}" for i in range(100))
    def discover(plan, **kwargs):
        calls.append(plan.raw_query)
        return {"items": [], "status": "complete"}
    result = step(review(source_scope="combined"), [row], tmp_path, discoverer=discover)
    quote = result["entries"][0]["summary"].split("“", 1)[1].rsplit("”", 1)[0]
    assert len(quote.split()) <= 25 and len(quote) <= 201
    assert "2025-07-01" in calls[0] and "2026-11-13" in calls[0]


def test_real_discovery_adapter_keeps_unranked_native_capture_as_a_lead(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import app.services.topic_discovery as discovery
    import app.services.open_research_copy as copies
    name = "ミヨシグループ"
    company = entity(name, "company-miyoshi")
    url = "https://grower.example/native"
    calls = []
    class Search:
        def search(self, query, **kwargs):
            calls.append(query)
            return SimpleNamespace(provider="fixture", hits=[SimpleNamespace(url=url, title=name + " strawberry announcement", snippet="", published_date="2025-07-01")])
        def diagnostics(self):
            return {}
    def fetch(url):
        return {"headline": name + "がイチゴの新品種を発表", "canonical_url": url, "published_date": "2025-07-01", "published_date_basis": "article_datePublished", "availability": "full", "passages": [name + "はイチゴの新品種の販売について発表しました。生産者への苗の供給を進めます。"]}
    real_discover = discovery.discover_topic
    monkeypatch.setattr(copies, "fetch_topic_source", fetch)
    monkeypatch.setattr(discovery, "discover_topic", lambda plan, **kwargs: real_discover(plan, client=Search(), **kwargs))
    initial = review(roster=name, companies=[company], source_scope="combined")
    result = news.research_one_company(initial, news.next_company_key(initial), entities=[company], archive_records=[], inbox_dir=tmp_path)
    assert calls and all("2025-07-01" in query for query in calls)
    assert result["sources"][0]["url"] == url
    assert result["sources"][0]["source_version"]
    assert result["sources"][0]["eligibility"] == "scope_unverified"
    assert result["companies"][0]["disposition"] == "incomplete"
    assert not result["entries"][0]["included"]


def _cache_public(tmp_path, row):
    from app.services.research_source_cache import remember_sources
    body = "\n".join(p["text"] for p in row["article"]["paragraphs"])
    captured = {**row, "capture_status": "full", "publication_date_basis": "article_datePublished",
                "source_version": hashlib.sha256(body.encode()).hexdigest()}
    assert remember_sources(tmp_path, [captured])["stored"] == 1
    return captured


def test_archive_only_reuses_stored_public_research_without_promoting_trust(tmp_path):
    captured = _cache_public(tmp_path, record())
    database = tmp_path / "research_public_sources.sqlite3"
    before = database.read_bytes()
    result = step(review(), [], tmp_path, discoverer=lambda *a, **k: pytest.fail("archive-only must not search web"))
    assert len(result["entries"]) == 1 and result["entries"][0]["included"]
    source = result["sources"][0]
    assert source["origin"] == "archive" and source["archive_source_type"] == "public_research_cache"
    assert source["capture_channel"] == "public_research_cache"
    assert source["trust_class"] == "LIVE / UNREVIEWED" and source["evidence_id"] == ""
    assert source["source_version"] == captured["source_version"]
    assert database.read_bytes() == before


def test_stored_unspaced_japanese_cache_is_found_before_any_web_search(tmp_path):
    name = "ミヨシグループ"
    company = entity(name, "company-miyoshi")
    row = record(company=name)
    row["title"] = name + "がイチゴの新品種を発表"
    row["article"] = {"paragraphs": [{"text": name + "はイチゴの新品種の苗の販売について発表しました。国内の生産者への供給を進めます。"}]}
    row["berry_ids"] = []
    captured = _cache_public(tmp_path, row)
    initial = review(roster=name, companies=[company])
    result = news.research_one_company(initial, news.next_company_key(initial), entities=[company], archive_records=[], inbox_dir=tmp_path)
    source = result["sources"][0]
    assert source["title"] == row["title"] and source["source_version"] == captured["source_version"]
    assert source["trust_class"] == "LIVE / UNREVIEWED" and source["origin"] == "archive"
    assert result["companies"][0]["counts"]["archive_literal_cache_candidates"] == 1
    assert result["companies"][0]["disposition"] == "incomplete"
    assert not result["entries"][0]["included"]


def test_malformed_web_source_does_not_discard_valid_web_capture(tmp_path):
    def captured(identifier):
        row = record(identifier)
        return {**row, "support_status": "body_supported", "relevance": "direct", "passage": row["article"]["paragraphs"][0]["text"], "passage_locator": "article:0", "source_version": "stored-version", "capture_status": "full"}
    valid, invalid = captured("web-valid"), captured("web-invalid")
    invalid["capture_provenance"] = "bad-shape DO_NOT_LEAK"
    result = step(review(source_scope="combined"), [], tmp_path, discoverer=lambda *a, **k: {"items": [invalid, valid], "status": "complete", "candidate_count": 2})
    assert len(result["entries"]) == 1 and result["entries"][0]["included"]
    assert result["companies"][0]["web_status"] == "partial"
    assert result["companies"][0]["counts"]["web_source_errors"] == 1
    assert "DO_NOT_LEAK" not in json.dumps(result)


def test_qualified_event_timing_text_is_retained_without_making_it_an_exact_date(tmp_path):
    row = record()
    row["event_date"] = "2026/27 planned season"
    result = step(review(), [row], tmp_path)
    assert result["entries"][0]["event_date"] == "2026/27 planned season"
    assert "not an exact verified date" in result["sources"][0]["qualification"]


@pytest.mark.parametrize("marker", [
    {"workspace_capture": {"nature": "analyst_interpretation", "quote": "PRIVATE_ANALYST_TEXT"}},
    {"source_type": "analyst_note"}, {"is_demo": True}, {"demo": True}, {"illustrative": True},
    {"fixture": True}, {"is_fixture": True}, {"data_class": "synthetic"}, {"mode": "fixture"},
    {"source_type": "fixture"}, {"record_type": "illustrative"},
    {"social_observation": {"mode": "fixture"}},
])
def test_derived_analyst_and_explicit_test_records_are_not_primary_news_sources(tmp_path, marker):
    derived = {**record("ev-derived"), **marker}
    derived["title"] = "ABZ Seeds PRIVATE_ANALYST_TEXT strawberry launch interpretation"
    result = step(review(), [derived, record("ev-original")], tmp_path)
    assert len(result["sources"]) == len(result["entries"]) == 1
    assert result["sources"][0]["evidence_id"] == "ev-original"
    assert result["companies"][0]["counts"]["archive_non_source_exclusions"] == 1
    assert "PRIVATE_ANALYST_TEXT" not in json.dumps(result)


def test_excluded_workspace_input_is_not_reader_or_transcript_hydrated(tmp_path, monkeypatch):
    import app.services.feed_first_reader as reader
    derived = {**record(), "workspace_capture": {"nature": "analyst_interpretation"}}
    monkeypatch.setattr(reader, "load_capture", lambda *a: pytest.fail("excluded input must not hydrate stored reader bodies"))
    prepared = news.prepare_archive_records([derived], tmp_path)
    result = step(review(), prepared, tmp_path)
    assert not result["sources"] and not result["entries"]
    assert result["companies"][0]["counts"]["archive_non_source_exclusions"] == 1


@pytest.mark.parametrize("status,required", [("unverified", False), ("active", True)])
def test_exact_directory_match_preserves_unverified_identity_gap_and_useful_sources(tmp_path, status, required):
    company = {**entity("Provisional Seeds", "company-provisional"), "status": status,
               "attributes": {"identity_review_required": required}}
    initial = review(roster="Provisional Seeds", companies=[company])
    matched = initial["companies"][0]
    assert matched["resolution"] == "resolved" and matched["company_id"] == "company-provisional"
    assert matched["identity_status"] == status and matched["identity_verification_required"]
    result = news.research_one_company(initial, matched["key"], entities=[company], archive_records=[record(company="Provisional Seeds")], inbox_dir=tmp_path)
    assert result["companies"][0]["disposition"] == "identity_unresolved"
    assert len(result["sources"]) == len(result["entries"]) == 1
    assert result["sources"][0]["excerpt"] and result["sources"][0]["source_version"]
    assert result["sources"][0]["eligibility"] == "identity_unresolved"
    assert result["entries"][0]["entry_type"] == "lead" and not result["entries"][0]["included"]


def test_existing_directory_review_resolves_identity_only_in_a_new_snapshot(tmp_path):
    company = {**entity("Provisional Seeds", "company-provisional"), "status": "unverified"}
    original = review(roster="Provisional Seeds", companies=[company])
    reviewed = {**company, "status": "active", "attributes": {"identity_review_required": False}}
    updated = review(roster="Provisional Seeds", companies=[reviewed])
    result = news.research_one_company(updated, news.next_company_key(updated), entities=[reviewed], archive_records=[record(company="Provisional Seeds")], inbox_dir=tmp_path)
    assert original["companies"][0]["identity_verification_required"]
    assert not result["companies"][0]["identity_verification_required"]
    assert result["entries"][0]["included"] and result["entries"][0]["entry_type"] == "development"
