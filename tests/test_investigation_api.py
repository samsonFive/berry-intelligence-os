"""Investigation adapters keep scope, trust and interaction domains distinct."""
from copy import deepcopy
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.services import investigation_api as api
from app import investigation_routes as routes


@pytest.fixture
def world():
    def node(key, name, kind, **extra):
        return {"id": key, "name": name, "entity_type": kind, "aliases": [], "status": "active",
                "berry_ids": ["berry-blueberry"] if kind in {"company", "variety", "breeding_program"} else [], **extra}
    entities = {row["id"]: row for row in [
        node("berry-blueberry", "Blueberry", "berry"), node("berry-strawberry", "Strawberry", "berry"),
        node("geography-peru", "Peru", "geography"), node("geography-chile", "Chile", "geography"),
        node("geography-china", "China", "geography"),
        node("company-a", "Alpha Blueberries", "company", roles=["breeder"]),
        node("company-b", "Beta Blueberries", "company", roles=["grower"]),
        node("company-outside", "Outside Blueberries", "company"),
        node("variety-a", "Azure", "variety", attributes={"private_note": "must not leak"}),
        node("variety-outside", "Beyond", "variety"),
        node("breeding_program-a", "Program Alpha", "breeding_program"),
    ]}
    source = {"id": "ev-a", "title": "Alpha blueberry breeding expands in Peru", "status": "published",
              "summary": "Blueberry breeding source summary.", "source_type": "trade_press",
              "source_name": "Trade publisher", "source_url": "https://example.com/blueberry",
              "published_date": "2026-08-01", "captured_date": "2026-10-01",
              "berry_ids": ["berry-blueberry"], "entity_ids": ["company-a", "variety-a", "geography-peru"],
              "article": {"text": "Unselected full article MUST NOT leak"},
              "supporting_excerpt": "Unselected excerpt MUST NOT leak"}
    def edge(key, left, predicate, right, **extra):
        return {"id": key, "subject_id": left, "predicate": predicate, "object_id": right,
                "status": "active", "evidence_ids": ["ev-a"], **extra}
    relationships = [
        edge("r-peru", "company-a", "operates_in", "geography-peru", notes="Variety validation programme"),
        edge("r-program", "company-a", "owns", "breeding_program-a"),
        edge("r-develops", "breeding_program-a", "develops", "variety-a"),
        edge("r-license", "company-b", "licenses", "variety-a"),
        edge("r-outside", "company-outside", "develops", "variety-outside"),
        edge("r-chile", "company-outside", "operates_in", "geography-chile"),
    ]
    main = SimpleNamespace(all_facts=lambda: [], all_signals=lambda: [], all_assessments=lambda: [])
    return api.World(main, entities, relationships, [source], {}, _news={"ev-a": source})


def context(**values):
    return api.normalize_context({"berry": "berry-blueberry", "countries": "geography-peru", **values})[0]


def test_normalization_round_trip_is_allowlisted_and_legacy_compatible():
    ctx, problems = api.normalize_context({"berry": "blueberry", "focus": "company:company-a",
        "countries": "", "cohort_companies": "company-a,company-a,company-b", "secret": "excluded"})
    assert ctx["berry"] == "berry-blueberry"
    assert ctx["focus"] == "company-a"
    assert ctx["countries"] == ""
    assert ctx["cohort_companies"] == "company-a,company-b"
    assert "secret" not in ctx and not problems
    from urllib.parse import parse_qs
    serialized = {key: value[0] for key, value in parse_qs(api.context_query(ctx), keep_blank_values=True).items()}
    assert api.normalize_context(serialized)[0] == ctx


@pytest.mark.parametrize("values", [
    {"ctx_v": "2"}, {"berry": "apple"}, {"countries": "../private"}, {"focus": "https://example.com"},
    {"news_from": "2026-02-30"}, {"news_from": "2026-09-01", "news_to": "2026-08-01"},
    {"relationship_types": "invented_role"}, {"detail_path": "~".join(["source:ev-a"] * 9)},
    {"q": "x" * 201}, {"saved_revision": "-1"},
])
def test_invalid_selectors_are_rejected_without_scope_broadening(values):
    with pytest.raises(ValueError):
        api.normalize_context(values)


def test_overflow_stays_visible_in_selectors_and_diagnostics():
    ctx, problems = api.normalize_context({"cohort_companies": ",".join(f"company-{n}" for n in range(7))})
    assert len(api.ids(ctx["cohort_companies"])) == 7
    assert [(row["code"], row["id"]) for row in problems] == [("overflow", "company-5"), ("overflow", "company-6")]


def test_focus_and_detail_do_not_seed_or_rewrite_scope(world):
    initial = api.base_bundle(world, context())
    focused = api.base_bundle(world, context(focus="company-outside", detail_path="company:company-outside~source:ev-a"))
    assert {row["id"] for row in initial["edges"]} == {row["id"] for row in focused["edges"]}
    assert "company-outside" not in focused["nodes"]
    assert api.selection_issues(world, context(focus="company-outside"), focused)[0]["code"] == "outside_scope"
    assert initial["explanation"] == focused["explanation"]


def test_explicit_empty_country_scope_is_all_and_unknown_country_fails(world):
    assert "company-outside" in api.base_bundle(world, context(countries=""))["nodes"]
    with pytest.raises(ValueError, match="not broadened"):
        api.base_bundle(world, context(countries="geography-unknown"))


def test_news_dates_never_erase_standing_relationships(world):
    old = api.base_bundle(world, context(news_from="2026-10-01", news_to="2026-10-31"))
    assert "r-peru" in {edge["id"] for edge in old["edges"]}
    assert old["filters"]["window"] == "all"
    assert old["filters"]["focus"] == ""


def test_company_geography_does_not_create_variety_growing_and_reviews_do_not_approve_claims(world):
    bundle = api.base_bundle(world, context())
    assert not any(edge["genetic_geography"] for edge in bundle["edges"])
    assert next(edge for edge in bundle["edges"] if edge["id"] == "r-peru")["location_label"] == "Variety validation programme"
    assert "claims retain their own review" in api.source_metadata(world.evidence[0])["review"]


def activity_world(world):
    world.entities["company-a"]["aliases"] = ["Alpha"]
    world.entities["company-b"]["aliases"] = ["Beta"]
    world.evidence.append({**world.evidence[0], "id": "ev-china", "title": "China platform source"})
    world.relationships.extend([
        {"id": "r-a-china", "subject_id": "company-a", "predicate": "operates_in", "object_id": "geography-china",
         "status": "active", "evidence_ids": ["ev-china"], "notes": "Stated intention for market entry; not an established operation."},
        {"id": "r-b-china", "subject_id": "company-b", "predicate": "operates_in", "object_id": "geography-china",
         "status": "active", "evidence_ids": ["ev-china"], "notes": "Named growing country and licensing region."},
    ])
    return world


def test_scope_findings_show_typed_activity_contrast_and_exact_citations(world, monkeypatch):
    activity_world(world)
    monkeypatch.setattr(api, "developments_data", lambda *args: {"cards": []})
    model = api.landscape_data(world, context(countries="geography-peru,geography-china"))
    findings = model["findings"]
    assert findings[0]["text"] == ("Alpha — China: Planned market entry (Intent only · not an established operation); "
                                    "Peru: Variety validation programme.")
    assert findings[0]["relationship_ids"] == ["r-a-china", "r-peru"]
    assert findings[0]["evidence_ids"] == ["ev-a", "ev-china"]
    assert findings[1]["text"] == "Beta — China: Growing & licensing region."
    assert findings[2]["text"] == "Alpha → Program Alpha: Owner / rights holder."
    assert findings[2]["relationship_ids"] == ["r-program"]
    edges = {edge["id"]: edge for edge in model["edges"]}
    for row in findings:
        assert set(row["evidence_ids"]) == {sid for key in row["relationship_ids"] for sid in edges[key]["evidence_ids"]}
        assert "has a location record" not in row["text"]


def test_scope_findings_ignore_focus_cohort_detail_lens_and_development_window(world, monkeypatch):
    activity_world(world)
    monkeypatch.setattr(api, "developments_data", lambda *args: {"cards": []})
    scope = context(countries="geography-peru,geography-china")
    expected = api.landscape_data(world, scope)["findings"]
    for selection in [
        {"focus": "company-outside"}, {"focus": "company-b"},
        {"cohort_companies": "company-b,company-a", "lens": "comparison"},
        {"detail_path": "company:company-a~source:ev-china"},
        {"lens": "sensory", "news_from": "2026-10-01", "news_to": "2026-10-31"},
    ]:
        assert api.landscape_data(world, {**scope, **selection})["findings"] == expected
    reduced = api.landscape_data(world, {**scope, "countries": "geography-peru"})["findings"]
    assert reduced != expected and all("China:" not in row["text"] for row in reduced)


def test_scope_findings_prioritize_activity_contrast_over_country_inventory(world, monkeypatch):
    activity_world(world)
    next(edge for edge in world.relationships if edge["id"] == "r-chile")["notes"] = "Registered office; growing is not established."
    for country in ("peru", "china"):
        world.relationships.append({"id": "r-office-" + country, "subject_id": "company-outside", "predicate": "operates_in",
            "object_id": "geography-" + country, "status": "active", "evidence_ids": ["ev-a"], "notes": "Test station; variety presence is not established."})
    monkeypatch.setattr(api, "developments_data", lambda *args: {"cards": []})
    model = api.landscape_data(world, context(countries="geography-chile,geography-peru,geography-china"))
    assert model["findings"][0]["id"] == "finding-activity-company-a"
    assert model["findings"][1]["id"] == "finding-activity-company-b"
    assert "company-outside" in model["nodes"]  # The complete scope still retains the other actor.
    assert {"r-chile", "r-office-peru", "r-office-china"} <= {edge["id"] for edge in model["edges"]}


def test_scope_findings_keep_disputed_qualifiers_and_do_not_invent_program_links(world, monkeypatch):
    activity_world(world)
    world.relationships = [edge for edge in world.relationships if edge["id"] != "r-program"]
    next(edge for edge in world.relationships if edge["id"] == "r-a-china")["status"] = "disputed"
    monkeypatch.setattr(api, "developments_data", lambda *args: {"cards": []})
    model = api.landscape_data(world, context(countries="geography-peru,geography-china"))
    text = " ".join(row["text"] for row in model["findings"])
    assert "Intent only · not an established operation; Disputed / review required" in text
    assert "Alpha → Program Alpha" not in text
    assert "Beta → Azure: Licensee" in text
    assert all("r-program" not in row["relationship_ids"] for row in model["findings"])


def test_generic_location_and_missing_coverage_are_not_leading_findings(world):
    bundle = api.base_bundle(world, context(countries="geography-chile"))
    geographic = [edge for edge in bundle["edges"] if edge["company_geography"]]
    assert geographic and api._scope_findings(bundle["nodes"], geographic) == []


def test_landscape_is_metadata_only_and_preserves_exact_roles(world, monkeypatch):
    monkeypatch.setattr(api, "developments_data", lambda *args: {"cards": []})
    before = deepcopy(world.evidence)
    model = api.landscape_data(world, context())
    assert model["nodes"]["variety-a"]["label"] == "Azure"
    assert "attributes" not in model["nodes"]["variety-a"]
    assert next(edge for edge in model["edges"] if edge["id"] == "r-license")["role"] == "Licensee"
    assert not any(key in model["sources"][0] for key in ("article", "transcript", "locator", "summary"))
    assert "MUST NOT leak" not in str(model) and "private_note" not in str(model)
    assert world.evidence == before
    assert all(set(row["evidence_ids"]) <= {source["id"] for source in model["sources"]} for row in model["findings"])


def test_authored_actor_roles_are_separate_from_relationship_predicates(world, monkeypatch):
    monkeypatch.setattr(api, "developments_data", lambda *args: {"cards": []})
    result = api.landscape_data(world, context(actor_roles="breeder"))
    assert "company-a" in result["nodes"] and "company-b" not in result["nodes"]
    with pytest.raises(ValueError, match="authored actor roles"):
        api.base_bundle(world, context(actor_roles="develops"))
    assert api.landscape_data(world, context(relationship_types="licenses"))["edges"][0]["predicate"] == "licenses"


def test_comparison_keeps_presenter_caps_roles_and_explicit_full_profile_basis(world):
    result = api.comparison_data(world, context(cohort_companies="company-a,company-b,company-outside"))
    assert result["count"] == 3 and result["comparison_kind"] == "company"
    beta = next(row for row in result["companies"] if row["id"] == "company-b")
    assert beta["roles"]["licensee"][0]["id"] == "variety-a"
    assert "full selected profiles" in result["scope_applicability"]["countries"]
    result = api.comparison_data(world, context(comparison_kind="variety", cohort_varieties="variety-a,variety-outside"))
    assert result["count"] == 2 and result["varieties"][0]["coverage"]["observation_count"] == 0
    assert not result["dimensions"]  # No synthesized sensory or performance observations.


def test_catalog_only_options_do_not_claim_evaluated_scope(world):
    result = api.catalog_options(world, context())
    assert result["scope_evaluated"] is False and result["search_basis"] == "catalog"
    assert {row["id"] for row in result["countries"]} == {"geography-peru", "geography-chile", "geography-china"}
    assert all(row["in_scope"] is None for row in result["companies"])
    assert result["berries"][0] == {"id": "all", "label": "All berries", "name": "All berries"}


def test_catalog_match_basis_distinguishes_authored_exact_alias_from_substring(world):
    world.entities["company-a"].update(name="Zeta Farm", aliases=["Orchard"])
    world.entities["company-b"].update(name="A Orchard Supplier", aliases=[])
    result = api.catalog_options(world, context(q=" orchard ", q_scope="catalog"))
    assert [(row["id"], row["match_basis"], row["matched_label"]) for row in result["companies"]] == [
        ("company-a", "exact_alias", "Orchard"), ("company-b", "substring", "A Orchard Supplier")]
    assert all(row["status"] == "active" for row in result["companies"])
    world.entities["company-a"].update(name="Orchard", aliases=["Orchard"])
    assert api.catalog_options(world, context(q="Orchard"))["companies"][0]["match_basis"] == "exact_name"


def test_catalog_multiple_authored_exact_aliases_remain_ambiguous_and_geography_aliases_are_exposed(world):
    for key in ("company-a", "company-b"):
        world.entities[key]["aliases"] = ["Shared name"]
    world.entities["geography-china"]["aliases"] = ["CN"]
    rows = api.catalog_options(world, context(q="shared name"))["companies"]
    assert len(rows) == 2 and all(row["match_basis"] == "exact_alias" for row in rows)
    assert {row["id"] for row in rows} == {"company-a", "company-b"}
    countries = api.catalog_options(world, context(q="CN"))["countries"]
    selected = next(row for row in countries if row["id"] == "geography-china")
    assert selected["match_basis"] == "exact_alias" and selected["matched_label"] == "CN"
    assert len(countries) == 3  # Catalog geography options are not narrowed.
    assert all("matched_label" not in row for row in countries if row["id"] != selected["id"])


def test_catalog_exact_matches_survive_the_existing_150_row_cap_without_changing_empty_query_order(world):
    for number in range(151):
        key = f"company-substring-{number}"
        world.entities[key] = {**world.entities["company-a"], "id": key, "name": f"A Target {number:03d}", "aliases": []}
    world.entities["company-a"].update(name="Zeta Farm", aliases=["Target"])
    result = api.catalog_options(world, context(q="Target"))
    assert len(result["companies"]) == 150 and result["matching_count"] == 152
    assert result["companies"][0]["id"] == "company-a"
    assert result["companies"][0]["match_basis"] == "exact_alias"
    assert result["companies"][1]["label"] == "A Target 000"
    unfiltered = api.catalog_options(world, context())["companies"]
    assert unfiltered[0]["label"] == "A Target 000"
    assert all(row["match_basis"] == "unfiltered" and "matched_label" not in row for row in unfiltered)


def test_developments_precedence_filters_before_pagination_and_never_widens(world, monkeypatch):
    from app.services import news_workspace
    world._news["ev-unrelated"] = {**world.evidence[0], "id": "ev-unrelated", "entity_ids": ["company-outside"]}
    observed = []
    def model(**kwargs):
        observed.append(kwargs)
        return {"cards": [{"id": key, "headline": row["title"]} for key, row in kwargs["records"].items()],
                "matching": len(kwargs["records"])}
    monkeypatch.setattr(news_workspace, "model", model)
    bundle = api.base_bundle(world, context())
    pinned = context(cohort_companies="company-outside", focus="company-a")
    assert api.developments_data(world, pinned, bundle)["basis"] == "focus"
    compared = {**pinned, "lens": "comparison"}
    result = api.developments_data(world, compared, bundle)
    assert result["basis"] == "comparison" and result["subject_ids"] == ["company-outside"]
    assert [card["id"] for card in result["cards"]] == ["ev-unrelated"]
    assert observed[-1]["params"]["countries"] == "geography-peru"
    assert observed[-1]["params"]["berry"] == "berry-blueberry"
    empty = api.developments_data(world, context(lens="comparison", cohort_companies="company-b"), bundle)
    assert empty["basis"] == "comparison" and empty["cards"] == []
    outside = api.developments_data(world, context(focus="company-outside"), bundle)
    assert outside["basis"] == "scope"
    detail = api.developments_data(world, context(detail_path="company:company-outside~source:ev-unrelated"), bundle)
    assert detail["basis"] == "scope"


def test_real_news_adapter_uses_publication_date_not_capture_date(world, monkeypatch):
    from app.services import news_workspace
    monkeypatch.setattr(news_workspace, "_berry_identity", lambda *args: True)
    monkeypatch.setattr(news_workspace, "_qualifying_news", lambda *args: True)
    bundle = api.base_bundle(world, context())
    result = api.developments_data(world, context(news_from="2026-10-01", news_to="2026-10-31"), bundle)
    assert result["cards"] == [] and result["matching_count"] == 0
    result = api.developments_data(world, context(news_from="2026-08-01", news_to="2026-08-31"), bundle)
    assert [row["id"] for row in result["cards"]] == ["ev-a"]
    assert result["cards"][0]["source_reviewed"] is True
    assert result["cards"][0]["trusted"] is False  # No approved supporting Fact.


def test_stored_comention_is_related_context_without_unreviewed_link_claim(world, monkeypatch):
    from app.services import news_workspace
    world.evidence[0]["title"] = "Alpha Blueberries expands breeding in Peru"
    world.evidence[0]["entity_ids"].append("company-b")
    monkeypatch.setattr(news_workspace, "_berry_identity", lambda *args: True)
    monkeypatch.setattr(news_workspace, "_qualifying_news", lambda *args: True)
    ctx = context(lens="comparison", cohort_companies="company-b")
    result = api.developments_data(world, ctx, api.base_bundle(world, ctx))
    card = result["cards"][0]
    assert card["scope_match"]["kind"] == "related_context"
    assert card["scope_match"]["primary_label"] == "Alpha Blueberries"
    assert card["scope_match"]["subject_labels"] == ["Beta Blueberries"]
    assert card["scope_match"]["basis"] == "recorded_link"
    assert card["company_mentions"] == []
    assert card["source_reviewed"] is True and card["trusted"] is False
    primary = {**ctx, "cohort_companies": "company-a"}
    assert api.developments_data(world, primary, api.base_bundle(world, primary))["cards"][0]["scope_match"]["kind"] == "primary"


def test_alias_recalled_context_keeps_its_unreviewed_link_basis(world, monkeypatch):
    from app.services import news_workspace
    world.evidence[0]["title"] = "Alpha Blueberries expands breeding in Peru"
    world.evidence[0]["summary"] = "Blueberry source mentioning Beta Blueberries."
    monkeypatch.setattr(news_workspace, "_berry_identity", lambda *args: True)
    monkeypatch.setattr(news_workspace, "_qualifying_news", lambda *args: True)
    ctx = context(focus="company-b")
    card = api.developments_data(world, ctx, api.base_bundle(world, ctx))["cards"][0]
    assert card["scope_match"]["kind"] == "related_context"
    assert card["scope_match"]["basis"] == "unreviewed_mention"
    assert card["company_mentions"][0]["id"] == "company-b"


def test_scoped_attribution_reuses_one_index_and_never_reads_source_body(world, monkeypatch):
    from app.services import news_workspace, draft_attribution
    world.evidence[0]["title"] = "Alpha Blueberries expands breeding in Peru"
    world.evidence[0]["entity_ids"].append("company-b")
    extra = {**world.evidence[0], "id": "ev-second"}
    world._news[extra["id"]] = extra
    calls = []
    original = draft_attribution.build_attribution_match_index
    monkeypatch.setattr(draft_attribution, "build_attribution_match_index", lambda entities: calls.append("index") or original(entities))
    original_attribute = draft_attribution.attribute_draft
    def attribute(record, entities, **kwargs):
        assert kwargs["include_body"] is False
        return original_attribute(record, entities, **kwargs)
    monkeypatch.setattr(draft_attribution, "attribute_draft", attribute)
    monkeypatch.setattr(news_workspace, "model", lambda **kwargs: {
        "cards": [{"id": key, "headline": row["title"]} for key, row in kwargs["records"].items()], "matching": len(kwargs["records"])})
    ctx = context(lens="comparison", cohort_companies="company-b")
    result = api.developments_data(world, ctx, api.base_bundle(world, ctx))
    assert len(result["cards"]) == 2 and calls == ["index"]
    assert all(card["scope_match"]["primary_id"] == "company-a" for card in result["cards"])


def test_corrected_excluded_source_association_is_not_reintroduced(world, monkeypatch):
    from app.services import company_source_scope, news_workspace
    monkeypatch.setattr(company_source_scope, "links", lambda record, subjects: (set(), []))
    def model(**kwargs):
        assert kwargs["records"] == {}
        return {"cards": [], "matching": 0}
    monkeypatch.setattr(news_workspace, "model", model)
    ctx = context(focus="company-a")
    result = api.developments_data(world, ctx, api.base_bundle(world, ctx))
    assert result["cards"] == []
    assert api.source_metadata({**world.evidence[0], "live": True})["review"] == "Unreviewed source"


def test_full_developments_export_keeps_same_subject_scope_and_all_pages(world, monkeypatch):
    from app.services import news_workspace
    page_calls = []
    def model(**kwargs):
        page = int(kwargs["params"].get("page", 1))
        page_calls.append((page, kwargs["params"]["countries"], set(kwargs["records"])))
        return {"cards": [{"id": "ev-a", "headline": "Page " + str(page)}], "matching": 3, "pages": 3}
    monkeypatch.setattr(news_workspace, "model", model)
    ctx = context(focus="company-a")
    result = api.developments_data(world, ctx, api.base_bundle(world, ctx), all_cards=True)
    assert [card["headline"] for card in result["cards"]] == ["Page 1", "Page 2", "Page 3"]
    assert all(country == "geography-peru" and records == {"ev-a"} for _, country, records in page_calls)
    assert result["basis"] == "focus" and len(result["sources"]) == 3


def test_source_detail_hydrates_selected_only_and_disables_automatic_capture(world, monkeypatch):
    from app import personal_digest_routes
    calls = []
    monkeypatch.setattr(personal_digest_routes, "personal_source_record", lambda key: calls.append(key) or world.evidence[0])
    monkeypatch.setattr(personal_digest_routes, "reader_context", lambda request, record: {
        "card": {"id": record["id"], "headline": record["title"]}, "summary": "Source summary",
        "article_text": ["Selected source prose"], "article_blocks": [], "document_blocks": [],
        "article_available": True, "auto_capture": True, "spoken_media": False, "media_transcript": {},
    })
    detail = api.detail_data(world, context(), api.base_bundle(world, context()), "source", "ev-a")
    assert calls == ["ev-a"] and detail["article_text"] == ["Selected source prose"]
    assert detail["body_availability"]["auto_acquisition"] is False


def test_selected_source_missing_publication_keeps_capture_as_a_separate_clock(world, monkeypatch):
    from app import personal_digest_routes
    from app.services import feed_first
    record = {**world.evidence[0], "published_date": "", "captured_date": "2026-10-01"}
    card = feed_first.present_item(record, entities_by_id=world.entities,
                                   state=feed_first.empty_state(), filters=feed_first.parse_filters({}))
    monkeypatch.setattr(personal_digest_routes, "personal_source_record", lambda key: record)
    monkeypatch.setattr(personal_digest_routes, "reader_context", lambda request, selected: {
        "card": card, "summary": "A source without a recorded publication date.",
        "article_text": [], "article_blocks": [], "document_blocks": [],
        "article_available": False, "spoken_media": False, "media_transcript": {},
    })
    detail = api.detail_data(world, context(), api.base_bundle(world, context()), "source", record["id"])
    assert not detail["sources"][0]["published"]
    assert detail["sources"][0]["captured"] == "2026-10-01"
    assert detail["card"]["published_at"] == ""
    assert detail["card"]["date_uncertain"] is True
    assert detail["card"]["captured_at"] == "2026-10-01"


@pytest.fixture
def client(world, monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(api, "load_world", lambda: world)
    monkeypatch.setattr(api, "developments_data", lambda *args: {"cards": [], "basis": "scope"})
    app = FastAPI()
    from app.session_auth import EnvSessionMiddleware, remote_auth_middleware
    app.middleware("http")(remote_auth_middleware)
    app.add_middleware(EnvSessionMiddleware)
    routes.register(app)
    return TestClient(app)


def test_api_envelope_revision_private_cache_and_invalid_scope(client):
    response = client.get("/api/investigations/v1/landscape", params={**context(), "revision": "17"})
    assert response.status_code == 200
    envelope = response.json()
    assert envelope["api_v"] == 1 and envelope["revision"] == 17 and len(envelope["scope_key"]) == 24
    assert response.headers["cache-control"] == "private, no-store"
    assert envelope["applied_scope"]["news_from"] == "not applied"
    assert client.get("/api/investigations/v1/landscape?countries=missing").status_code == 422
    assert client.get("/api/investigations/v1/landscape?revision=-1").status_code == 422


@pytest.mark.parametrize("endpoint", ["landscape", "comparison", "detail", "developments", "options", "monitoring", "news"])
def test_api_denies_public_only_mode(client, monkeypatch, endpoint):
    import app.main as main
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    assert client.get("/api/investigations/v1/" + endpoint).status_code == 403


@pytest.mark.parametrize("endpoint", ["landscape", "comparison", "detail", "developments", "options", "monitoring", "news"])
def test_api_denies_unauthenticated_remote_session(client, monkeypatch, endpoint):
    monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "1")
    monkeypatch.setenv("BIOS_REVIEW_USERNAME", "test-review")
    monkeypatch.setenv("BIOS_REVIEW_PASSWORD", "test-only-password")
    monkeypatch.setenv("BIOS_SESSION_SECRET", "test-only-secret-for-authenticated-investigation")
    assert client.get("/api/investigations/v1/" + endpoint, follow_redirects=False).status_code in {302, 401}


def _monitoring_world(world, tmp_path):
    world.main.INBOX_DIR = tmp_path / "inbox"
    return world


def test_company_set_is_independent_and_legacy_missing_default_is_all():
    assert context()["company_set"] == "all"
    selection, issues = api.normalize_context({"lens": "news", "company_set": "watched",
        "cohort_companies": ",".join(f"company-{index}" for index in range(7))})
    assert selection["company_set"] == "watched" and selection["lens"] == "news"
    assert len(issues) == 2  # Comparison alone remains capped at five.
    for value in ("", "personal", "company-a"):
        with pytest.raises(ValueError):
            api.normalize_context({"company_set": value})


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "limit=2&limit=3", "offset=-1", "offset=2.5", "offset=9007199254740992"])
def test_monitoring_pagination_rejects_ambiguous_or_unsupported_pages(query):
    from starlette.datastructures import QueryParams
    with pytest.raises(ValueError):
        api.pagination(QueryParams(query))


def test_monitoring_default_page_and_safe_large_offset():
    from starlette.datastructures import QueryParams
    assert api.pagination(QueryParams()) == {"limit": 36, "offset": 0}
    assert api.pagination(QueryParams("offset=9007199254740991&limit=1"))["offset"] == 9007199254740991


def test_watched_roster_pages_all_45_members_without_comparison_or_scope_cap(world, tmp_path, monkeypatch):
    from app.services.watchlist import add_watch
    from app.services import competitor_registry
    world = _monitoring_world(world, tmp_path)
    for index in range(45):
        key = f"company-monitored-{index:02}"
        world.entities[key] = {**world.entities["company-a"], "id": key, "name": f"Monitored {index:02}", "aliases": [f"Alias {index:02}"]}
        add_watch(world.main.INBOX_DIR, "company", key)
    before = (world.main.INBOX_DIR / "watchlist_state.json").read_bytes()
    ctx = context(company_set="watched", focus="company-a", cohort_companies="company-a,company-b")
    frozen = deepcopy(ctx)
    bundle = api.base_bundle(world, ctx)
    calls = []
    monkeypatch.setattr(competitor_registry, "monitoring_state_for_entity", lambda key, **kwargs: calls.append(key) or {"state": "no_supported_source", "detail": "No linked source"})
    pages = [api.monitoring_data(world, ctx, bundle, offset=offset, limit=10) for offset in range(0, 50, 10)]
    assert [len(page["companies"]) for page in pages] == [10, 10, 10, 10, 5]
    assert all(page["total"] == page["universe_count"] == 45 for page in pages)
    assert len({row["id"] for page in pages for row in page["companies"]}) == 45
    assert len(calls) == 45  # Health work happens after pagination, never for hidden rows.
    assert all(not row["in_scope"] and row["watched"] for page in pages for row in page["companies"])
    assert pages[-1]["next_offset"] is None and not pages[-1]["has_more"]
    assert ctx == frozen and before == (world.main.INBOX_DIR / "watchlist_state.json").read_bytes()
    search = api.monitoring_data(world, {**ctx, "q": "ALIAS 44", "q_scope": "catalog"}, bundle)
    assert search["universe_count"] == 45 and search["matching_count"] == 1
    assert search["companies"][0]["id"] == "company-monitored-44"
    assert api.monitoring_data(world, {**ctx, "q": "Alias 44", "q_scope": "scope"}, bundle)["total"] == 0


def test_roster_geography_is_scoped_cited_activity_and_not_automatic_monitoring(world, tmp_path):
    world = _monitoring_world(world, tmp_path)
    ctx = context()
    data = api.monitoring_data(world, ctx, api.base_bundle(world, ctx))
    alpha = next(row for row in data["companies"] if row["id"] == "company-a")
    outside = next(row for row in data["companies"] if row["id"] == "company-outside")
    assert alpha["in_scope"] and not outside["in_scope"] and not outside["geographies"]
    assert alpha["geographies"][0]["activity"] == "Variety validation programme"
    assert alpha["geographies"][0]["evidence_ids"] == ["ev-a"]
    assert alpha["monitoring"]["state"] == "no_supported_source"


def _news_records(world, count=2):
    first = world.evidence[0]
    for index in range(count):
        key = f"ev-beta-{index:03}"
        world.news[key] = {**first, "id": key, "title": f"Beta blueberries cultivation research update {index}",
            "entity_ids": ["company-b", "geography-peru"], "source_url": f"https://example.com/{key}"}


def test_news_watches_filter_before_pagination_and_ignore_comparison_focus(world, tmp_path):
    from app.services.watchlist import add_watch
    world = _monitoring_world(world, tmp_path)
    _news_records(world, 79)
    add_watch(world.main.INBOX_DIR, "company", "company-b")
    ctx = context(lens="news", company_set="watched", focus="company-a", cohort_companies="company-a")
    before = deepcopy(ctx)
    bundle = api.base_bundle(world, ctx)
    full = api.news_data(world, ctx, bundle, all_cards=True)
    assert full["matching_count"] == len(full["cards"]) == 79
    assert full["basis"] == "workspace_watches"
    expected = [row["id"] for row in full["cards"]]
    paged = api.news_data(world, ctx, bundle, offset=34, limit=10)
    assert [row["id"] for row in paged["cards"]] == expected[34:44]
    assert paged["next_offset"] == 44 and paged["matching_count"] == 79
    assert not api.news_data(world, ctx, bundle, offset=200)["cards"]
    assert {card["id"] for card in full["cards"]} == {row["id"] for row in full["sources"]}
    assert all("source_reviewed" in row and "trusted" in row and "published_at" in row for row in full["cards"])
    assert all(set(card) <= set(api.NATIVE_NEWS_FIELDS) for card in full["cards"])
    leaked = "MUST NOT leak" in str(full)
    assert leaked is False, "Native News metadata must not expose unselected source bodies or excerpts"
    assert ctx == before
    older = api.news_data(world, {**ctx, "news_from": "2026-09-01"}, bundle)
    assert older["matching_count"] == 0
    wrong_place = api.news_data(world, {**ctx, "countries": "geography-china"}, api.base_bundle(world, {**ctx, "countries": "geography-china"}))
    assert wrong_place["matching_count"] == 0


def test_empty_or_missing_watches_never_widen_news_and_all_includes_unattributed_industry(world, tmp_path):
    from app.services.watchlist import add_watch
    world = _monitoring_world(world, tmp_path)
    unattributed = {**world.evidence[0], "id": "ev-industry", "title": "Blueberry cultivation sector expands in Peru",
                    "entity_ids": ["geography-peru"], "source_url": "https://example.com/industry"}
    world.news[unattributed["id"]] = unattributed
    ctx = context(lens="news", company_set="watched")
    bundle = api.base_bundle(world, ctx)
    assert api.news_data(world, ctx, bundle)["matching_count"] == 0
    add_watch(world.main.INBOX_DIR, "company", "company-gone")
    stale = api.news_data(world, ctx, bundle)
    assert stale["matching_count"] == 0 and stale["unavailable_watch_count"] == 1
    all_news = api.news_data(world, {**ctx, "company_set": "all"}, bundle)
    assert "ev-industry" in {row["id"] for row in all_news["cards"]}
    assert "unattributed" in all_news["briefing_scope_note"]


def test_news_export_hash_changes_with_watch_membership_even_when_both_feeds_empty(world, tmp_path):
    from app.services.watchlist import add_watch
    from app.services import investigation_export as export
    world = _monitoring_world(world, tmp_path)
    ctx = context(lens="news", company_set="watched", news_from="2026-10-01")
    first = export.preview(world, ctx, ["developments"])
    assert first["sections"][0]["row_count"] == 0
    add_watch(world.main.INBOX_DIR, "company", "company-b")
    second = export.preview(world, ctx, ["developments"])
    assert second["sections"][0]["row_count"] == 0
    assert first["content_hash"] != second["content_hash"]
    with pytest.raises(export.ContentChangedError):
        export.pdf(world, ctx, ["developments"], False, first["content_hash"])


def test_real_ten_company_model_reuses_active_canonical_identities():
    import json
    from pathlib import Path
    keys = ("driscolls", "fall-creek-farm-and-nursery", "costa-group-holdings", "hortifrut", "planasa",
            "agrovision", "berryworld", "mountain-blue-orchards", "naturipe-farms", "wish-farms")
    folder = Path(__file__).resolve().parents[1] / "data" / "entities" / "companies"
    rows = [json.loads((folder / f"company-{key}.json").read_text(encoding="utf-8")) for key in keys]
    assert len({row["id"] for row in rows}) == 10
    assert all(row["entity_type"] == "company" and row["status"] == "active" for row in rows)


def test_watch_selector_and_news_lens_save_as_references_not_member_snapshot(tmp_path):
    from app.services import landscape_workspace as workspace
    from urllib.parse import parse_qs, urlsplit
    selected = context(lens="news", company_set="watched", cohort_companies="company-a,company-b")
    saved = workspace.save_view(tmp_path / "inbox", name="Shared watches News", kind="explorer", filters=selected)
    assert saved["filters"]["company_set"] == "watched" and saved["filters"]["lens"] == "news"
    assert saved["filters"]["cohort_companies"] == "company-a,company-b"
    assert not any(key in saved["filters"] for key in ("watched_ids", "company_set_key", "members"))
    query = {key: values[0] for key, values in parse_qs(urlsplit(workspace.view_href(saved)).query, keep_blank_values=True).items()}
    assert api.normalize_context(query)[0]["company_set"] == "watched"


def test_monitoring_and_news_http_envelope_page_and_private_read_boundaries(world, tmp_path, monkeypatch):
    world = _monitoring_world(world, tmp_path)
    monkeypatch.setattr(api, "load_world", lambda: world)
    monkeypatch.setattr(routes, "_private", lambda: None)
    app = FastAPI()
    routes.register(app)
    with TestClient(app) as client:
        for endpoint in ("monitoring", "news"):
            response = client.get(f"/api/investigations/v1/{endpoint}", params={**context(), "limit": 1, "offset": 0, "revision": 7})
            assert response.status_code == 200
            assert response.headers["cache-control"] == "private, no-store"
            payload = response.json()
            assert payload["api_v"] == 1 and payload["revision"] == 7
            assert payload["data"]["limit"] == 1 and payload["data"]["offset"] == 0
            assert client.get(f"/api/investigations/v1/{endpoint}?limit=1&limit=2").status_code == 422
            assert client.post(f"/api/investigations/v1/{endpoint}").status_code == 405
