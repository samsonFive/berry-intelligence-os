import httpx
from fastapi.testclient import TestClient

from app import main
from app.main import app

client = TestClient(app)


def test_home_renders_sample_evidence() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Example breeder announces" in response.text


def test_feed_api_returns_published_records() -> None:
    response = client.get("/api/feed")
    assert response.status_code == 200
    body = response.json()
    assert body
    assert body[0]["record_type"] == "evidence"


def test_evidence_detail_page_shows_linked_entities() -> None:
    response = client.get("/evidence/ev-sample-variety-launch")
    assert response.status_code == 200
    assert "Example Genetics" in response.text
    assert "Example Blue" in response.text


def test_evidence_detail_404_for_unknown_id() -> None:
    response = client.get("/evidence/does-not-exist")
    assert response.status_code == 404


def test_company_entity_page_renders() -> None:
    response = client.get("/entities/company/company-example-genetics")
    assert response.status_code == 200
    assert "Example Genetics" in response.text
    assert "Example breeder announces" in response.text


def test_variety_entity_page_renders() -> None:
    response = client.get("/entities/variety/variety-example-blue")
    assert response.status_code == 200
    assert "Example Blue" in response.text


def test_entity_detail_404_when_type_mismatches() -> None:
    response = client.get("/entities/variety/company-example-genetics")
    assert response.status_code == 404


def test_entity_list_page_renders() -> None:
    response = client.get("/entities/company")
    assert response.status_code == 200
    assert "Example Genetics" in response.text
    assert "Example Nursery Partners" in response.text


def test_entity_list_404_for_unknown_type() -> None:
    response = client.get("/entities/spaceship")
    assert response.status_code == 404


def test_feed_filters_by_berry() -> None:
    response = client.get("/api/feed", params={"berry": "berry-raspberry"})
    assert response.status_code == 200
    body = response.json()
    assert body
    assert all("berry-raspberry" in item["berry_ids"] for item in body)


def test_feed_filters_combine_with_no_matches() -> None:
    response = client.get(
        "/api/feed",
        params={"berry": "berry-raspberry", "source": "field_observation"},
    )
    assert response.status_code == 200
    assert response.json() == []


def test_feed_filters_by_priority_level() -> None:
    response = client.get("/api/feed", params={"priority": "commercial_position:high"})
    assert response.status_code == 200
    body = response.json()
    assert body
    assert all(item["priority"]["commercial_position"]["level"] == "high" for item in body)


def test_feed_search_matches_title_text() -> None:
    response = client.get("/", params={"q": "raspberry"})
    assert response.status_code == 200
    assert "raspberry genetics program" in response.text


def test_feed_filters_by_competitor() -> None:
    response = client.get("/api/feed", params={"competitor": "company-example-nursery"})
    assert response.status_code == 200
    body = response.json()
    assert body
    assert all("company-example-nursery" in item["entity_ids"] for item in body)


def test_feed_filters_by_geography() -> None:
    response = client.get("/api/feed", params={"geography": "geography-europe"})
    assert response.status_code == 200
    body = response.json()
    assert body
    assert all("geography-europe" in item["geography_ids"] for item in body)

    na_response = client.get("/api/feed", params={"geography": "geography-north-america"})
    na_body = na_response.json()
    assert len(na_body) == 2
    assert {item["id"] for item in na_body} == {"ev-sample-variety-launch", "ev-sample-retail-placement"}


def test_feed_page_renders_competitor_and_geography_filter_options() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Competitor" in response.text
    assert "Geography" in response.text
    assert "Example Nursery Partners" in response.text
    assert "Europe" in response.text
    assert "North America" in response.text


def test_evidence_detail_shows_geography() -> None:
    response = client.get("/evidence/ev-sample-patent-published")
    assert response.status_code == 200
    assert "Europe" in response.text


def test_api_search_returns_evidence_and_entities() -> None:
    response = client.get("/api/search", params={"q": "example blue"})
    assert response.status_code == 200
    body = response.json()
    assert any(e["id"] == "variety-example-blue" for e in body["entities"])


def test_api_entity_detail() -> None:
    response = client.get("/api/entities/company/company-example-genetics")
    assert response.status_code == 200
    assert response.json()["name"] == "Example Genetics"


def test_intake_form_renders_with_tabs() -> None:
    response = client.get("/intake")
    assert response.status_code == 200
    assert "Add Intelligence" in response.text
    assert "Note / Observation" in response.text


def test_intake_creates_draft_outside_published_data(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)

    response = client.post(
        "/intake",
        data={
            "intake_type": "article_or_url",
            "title": "Fictional competitor launches new nursery",
            "source_url": "https://example.invalid/article",
            "summary": "A fictional summary for testing intake.",
            "submitted_by": "tester@example.invalid",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "created=" in location
    draft_id = location.split("created=")[-1]

    assert (tmp_path / "evidence" / f"{draft_id}.json").exists()

    detail = client.get(f"/intake/{draft_id}")
    assert detail.status_code == 200
    assert "Fictional competitor launches new nursery" in detail.text
    assert "unreviewed draft" in detail.text

    feed = client.get("/api/feed")
    assert all(item["id"] != draft_id for item in feed.json())


def test_intake_missing_required_field_returns_error(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)

    response = client.post(
        "/intake",
        data={
            "intake_type": "article_or_url",
            "title": "",
            "source_url": "https://example.invalid/article",
            "summary": "A fictional summary.",
            "submitted_by": "tester@example.invalid",
        },
    )
    assert response.status_code == 400
    assert "Title is required" in response.text
    assert not (tmp_path / "evidence").exists()


def test_intake_uploaded_report_requires_attachment(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)

    response = client.post(
        "/intake",
        data={
            "intake_type": "uploaded_report",
            "title": "Fictional trip report",
            "summary": "A fictional summary.",
            "submitted_by": "tester@example.invalid",
        },
    )
    assert response.status_code == 400
    assert "attachment is required" in response.text


def test_intake_attachment_round_trips(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)

    response = client.post(
        "/intake",
        data={
            "intake_type": "uploaded_report",
            "title": "Fictional trip report with attachment",
            "summary": "A fictional summary.",
            "submitted_by": "tester@example.invalid",
        },
        files={"attachment": ("note.txt", b"hello berries", "text/plain")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    draft_id = response.headers["location"].split("created=")[-1]

    download = client.get(f"/intake/{draft_id}/attachments/note.txt")
    assert download.status_code == 200
    assert download.content == b"hello berries"


def test_intake_blocked_in_readonly_mode(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", False)

    response = client.post(
        "/intake",
        data={
            "intake_type": "standalone_fact",
            "title": "Fictional fact",
            "summary": "Context.",
            "submitted_by": "tester@example.invalid",
        },
    )
    assert response.status_code == 403


def _create_draft(title: str = "Fictional nursery expands raspberry trials") -> str:
    response = client.post(
        "/intake",
        data={
            "intake_type": "article_or_url",
            "title": title,
            "source_url": "https://example.invalid/trials",
            "summary": "A fictional summary for review-flow testing.",
            "submitted_by": "tester@example.invalid",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    return response.headers["location"].split("created=")[-1]


def _isolate(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")


def test_review_queue_and_form_render(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    draft_id = _create_draft()

    queue = client.get("/review")
    assert queue.status_code == 200
    assert "Fictional nursery expands raspberry trials" in queue.text

    form = client.get(f"/review/{draft_id}")
    assert form.status_code == 200
    assert "Original submission" in form.text
    assert "Proposed structured record" in form.text


def test_review_missing_draft_404(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    response = client.get("/review/does-not-exist")
    assert response.status_code == 404


def test_publish_requires_priority_rationale(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    draft_id = _create_draft()

    response = client.post(
        f"/review/{draft_id}/publish",
        data={
            "title": "Fictional nursery expands raspberry trials",
            "summary": "A fictional summary.",
            "reviewer": "reviewer@example.invalid",
            "priority_reading_level": "high",
            "priority_reading_rationale": "",
        },
    )
    assert response.status_code == 400
    assert "rationale is required" in response.text


def test_publish_relationship_must_match_linked_entity(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    draft_id = _create_draft()

    response = client.post(
        f"/review/{draft_id}/publish",
        data={
            "title": "Fictional nursery expands raspberry trials",
            "summary": "A fictional summary.",
            "reviewer": "reviewer@example.invalid",
            "companies": "Linked Co",
            "rel_subject_1": "Unlinked Co",
            "rel_predicate_1": "trials",
            "rel_object_1": "Linked Co",
        },
    )
    assert response.status_code == 400
    assert "must match a linked" in response.text


def test_publish_creates_entities_facts_relationships_and_updates_feed(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    draft_id = _create_draft("Fictional nursery expands raspberry trials in new region")

    response = client.post(
        f"/review/{draft_id}/publish",
        data={
            "source_type": "article",
            "title": "Fictional nursery expands raspberry trials in new region",
            "summary": "A fictional summary for the published record.",
            "why_it_matters": "Testing the review-to-publish pipeline end to end.",
            "companies": "New Fictional Co",
            "varieties": "New Fictional Variety",
            "berries": ["berry-raspberry"],
            "fact_statement_1": "New Fictional Co expanded raspberry trials in a new region.",
            "fact_classification_1": "fact",
            "fact_confidence_1": "medium",
            "rel_subject_1": "New Fictional Co",
            "rel_predicate_1": "trials",
            "rel_object_1": "New Fictional Variety",
            "priority_reading_level": "high",
            "priority_reading_rationale": "New trial expansion is worth reading.",
            "priority_testing_level": "medium",
            "priority_testing_rationale": "Not yet ready to escalate testing.",
            "priority_commercial_position_level": "none",
            "priority_commercial_position_rationale": "",
            "priority_monitoring_level": "low",
            "priority_monitoring_rationale": "Keep a light watch.",
            "reviewer": "reviewer@example.invalid",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/evidence/{draft_id}"

    evidence_page = client.get(f"/evidence/{draft_id}")
    assert evidence_page.status_code == 200
    assert "New Fictional Co expanded raspberry trials" in evidence_page.text
    assert "New Fictional Co" in evidence_page.text
    assert "trials" in evidence_page.text

    company_page = client.get("/entities/company/company-new-fictional-co")
    assert company_page.status_code == 200
    assert "New Fictional Co expanded raspberry trials" in company_page.text

    feed = client.get("/api/feed")
    assert any(item["id"] == draft_id for item in feed.json())

    assert client.get(f"/intake/{draft_id}").status_code == 404


def test_publish_creates_and_links_geography_entity(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    draft_id = _create_draft("Fictional nursery expands into a new growing region")

    response = client.post(
        f"/review/{draft_id}/publish",
        data={
            "title": "Fictional nursery expands into a new growing region",
            "summary": "A fictional summary for testing geography linking.",
            "companies": "Regional Test Co",
            "geographies": "Testland",
            "reviewer": "reviewer@example.invalid",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    evidence_page = client.get(f"/evidence/{draft_id}")
    assert "Testland" in evidence_page.text

    geography_page = client.get("/entities/geography/geography-testland")
    assert geography_page.status_code == 200
    assert "Testland" in geography_page.text

    filtered = client.get("/api/feed", params={"geography": "geography-testland"})
    assert any(item["id"] == draft_id for item in filtered.json())


def test_review_flags_possible_duplicate_title(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    title = "Fictional duplicate-check nursery announcement"
    first_draft_id = _create_draft(title)
    client.post(
        f"/review/{first_draft_id}/publish",
        data={
            "title": title,
            "summary": "First published record.",
            "reviewer": "reviewer@example.invalid",
        },
    )

    second_draft_id = _create_draft(title)
    review_page = client.get(f"/review/{second_draft_id}")
    assert review_page.status_code == 200
    assert "Possible duplicate" in review_page.text


def test_publish_blocked_in_readonly_mode(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    draft_id = _create_draft()
    monkeypatch.setattr(main, "AUTHORING_MODE", False)

    response = client.post(
        f"/review/{draft_id}/publish",
        data={
            "title": "Fictional nursery expands raspberry trials",
            "summary": "A fictional summary.",
            "reviewer": "reviewer@example.invalid",
        },
    )
    assert response.status_code == 403


def test_work_queue_renders() -> None:
    response = client.get("/work-queue")
    assert response.status_code == 200
    assert "Work Queue" in response.text
    assert "Recently published" in response.text
    assert "High-priority items" in response.text
    # "Recently published" shows only the most recent few records, so which
    # specific title appears there depends on how much has been published --
    # assert against the live feed instead of a title that may have aged out.
    feed = client.get("/api/feed").json()
    assert feed
    assert feed[0]["title"] in response.text


def test_reading_queue_includes_all_nonnone_levels() -> None:
    response = client.get("/queues/reading")
    assert response.status_code == 200
    assert "Example breeder announces" in response.text
    assert "Expanded end-cap placement" in response.text
    assert "Patent published" in response.text


def test_testing_queue_excludes_none_level() -> None:
    response = client.get("/queues/testing")
    assert response.status_code == 200
    assert "Patent published" not in response.text
    assert "Example breeder announces" in response.text


def test_queue_404_for_unknown_dimension() -> None:
    response = client.get("/queues/not-a-real-dimension")
    assert response.status_code == 404


def test_strategic_question_list_and_detail() -> None:
    list_response = client.get("/strategic-questions")
    assert list_response.status_code == 200
    assert "premium flavor" in list_response.text.lower()

    detail_response = client.get("/strategic-questions/sq-premium-flavor")
    assert detail_response.status_code == 200
    assert "Example breeder announces" in detail_response.text


def test_strategic_question_404_for_unknown_id() -> None:
    response = client.get("/strategic-questions/sq-does-not-exist")
    assert response.status_code == 404


def test_signal_list_and_new_form_render() -> None:
    list_response = client.get("/signals")
    assert list_response.status_code == 200
    assert "Signals" in list_response.text

    form_response = client.get("/signals/new")
    assert form_response.status_code == 200
    assert "Supporting evidence ids" in form_response.text


def test_signal_create_requires_known_evidence_id(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    response = client.post(
        "/signals",
        data={
            "title": "Fictional signal",
            "direction": "emerging",
            "strength": "medium",
            "confidence": "medium",
            "status": "active",
            "evidence_ids": "ev-does-not-exist",
            "reviewer": "reviewer@example.invalid",
        },
    )
    assert response.status_code == 400
    assert "Unknown published evidence id" in response.text


def test_signal_create_and_detail_page(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    draft_id = _create_draft("Fictional signal source evidence")
    client.post(
        f"/review/{draft_id}/publish",
        data={
            "title": "Fictional signal source evidence",
            "summary": "A fictional summary.",
            "reviewer": "reviewer@example.invalid",
        },
    )

    response = client.post(
        "/signals",
        data={
            "title": "Fictional strengthening pattern",
            "description": "A fictional pattern for testing.",
            "direction": "strengthening",
            "strength": "high",
            "confidence": "medium",
            "status": "active",
            "evidence_ids": draft_id,
            "reviewer": "reviewer@example.invalid",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    signal_id = response.headers["location"].split("/signals/")[-1]

    detail = client.get(f"/signals/{signal_id}")
    assert detail.status_code == 200
    assert "Fictional strengthening pattern" in detail.text
    assert "Fictional signal source evidence" in detail.text

    list_page = client.get("/signals")
    assert "Fictional strengthening pattern" in list_page.text


def test_signal_create_blocked_in_readonly_mode(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", False)

    response = client.post(
        "/signals",
        data={
            "title": "Fictional signal",
            "direction": "emerging",
            "strength": "medium",
            "confidence": "medium",
            "status": "active",
            "evidence_ids": "ev-sample-variety-launch",
            "reviewer": "reviewer@example.invalid",
        },
    )
    assert response.status_code == 403


FAKE_RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
<title>Fictional Trade Press</title>
<item>
  <title>Fictional headline about blueberry licensing</title>
  <link>https://example.invalid/articles/fictional-headline</link>
  <description>A fictional description used to test source ingestion.</description>
  <pubDate>Mon, 03 Aug 2026 10:00:00 GMT</pubDate>
</item>
</channel></rss>
"""


class _FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        pass


def test_sources_page_renders_empty_and_after_add(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)

    empty = client.get("/sources")
    assert empty.status_code == 200
    assert "No sources yet" in empty.text

    response = client.post(
        "/sources",
        data={"type": "rss", "label": "Fictional Trade Press", "value": "https://example.invalid/feed.xml"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    listed = client.get("/sources")
    assert "Fictional Trade Press" in listed.text
    assert "https://example.invalid/feed.xml" in listed.text


def test_sources_add_requires_fields(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    response = client.post("/sources", data={"type": "rss", "label": "", "value": ""})
    assert response.status_code == 400
    assert "required" in response.text


def test_sources_toggle_and_delete(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    client.post("/sources", data={"type": "keyword", "label": "blueberry licensing", "value": "blueberry licensing"})
    source_id = main.load_sources()[0]["id"]

    toggled = client.post(f"/sources/{source_id}/toggle", follow_redirects=False)
    assert toggled.status_code == 303
    assert main.load_sources()[0]["enabled"] is False

    deleted = client.post(f"/sources/{source_id}/delete", follow_redirects=False)
    assert deleted.status_code == 303
    assert main.load_sources() == []


def test_google_news_rss_url_encodes_term() -> None:
    url = main.google_news_rss_url("blueberry licensing")
    assert url.startswith("https://news.google.com/rss/search?q=")
    assert "blueberry%20licensing" in url or "blueberry+licensing" in url


def test_check_source_writes_new_evidence_and_dedupes(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(main.httpx, "get", lambda *a, **k: _FakeResponse(FAKE_RSS))

    source = {
        "id": "source-test",
        "type": "rss",
        "label": "Fictional Trade Press",
        "value": "https://example.invalid/feed.xml",
        "berry_ids": [],
        "enabled": True,
    }

    written = main.check_source(source, set())
    assert written == 1

    feed = client.get("/api/feed").json()
    assert len(feed) == 1
    record = feed[0]
    assert record["title"] == "Fictional headline about blueberry licensing"
    assert record["status"] == "published"
    assert record["auto_captured"] is True
    assert record["validated"] is False
    assert record["source_url"] == "https://example.invalid/articles/fictional-headline"

    # Second check against the same feed must not create a duplicate.
    written_again = main.check_source(source, main.existing_evidence_source_urls())
    assert written_again == 0
    assert len(client.get("/api/feed").json()) == 1


def test_check_source_caps_new_items_per_check(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    items = "\n".join(
        f"<item><title>Fictional item {i}</title>"
        f"<link>https://example.invalid/articles/item-{i}</link>"
        f"<description>Fictional description {i}.</description></item>"
        for i in range(30)
    )
    big_feed = f"<?xml version='1.0'?><rss version='2.0'><channel>{items}</channel></rss>".encode()
    monkeypatch.setattr(main.httpx, "get", lambda *a, **k: _FakeResponse(big_feed))

    source = {"id": "source-test", "type": "rss", "label": "Fictional Big Feed",
              "value": "https://example.invalid/feed.xml", "berry_ids": [], "enabled": True}

    first_pass = main.check_source(source, set())
    assert first_pass == main.SOURCE_MAX_NEW_ITEMS_PER_CHECK
    assert len(client.get("/api/feed").json()) == main.SOURCE_MAX_NEW_ITEMS_PER_CHECK

    # The items left over from the cap are still "new" and get picked up
    # on a subsequent check rather than being lost.
    second_pass = main.check_source(source, main.existing_evidence_source_urls())
    assert second_pass == 30 - main.SOURCE_MAX_NEW_ITEMS_PER_CHECK
    assert len(client.get("/api/feed").json()) == 30


def test_check_all_sources_updates_last_checked_status(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(main.httpx, "get", lambda *a, **k: _FakeResponse(FAKE_RSS))
    main.save_sources(
        [
            {
                "id": "source-test",
                "type": "rss",
                "label": "Fictional Trade Press",
                "value": "https://example.invalid/feed.xml",
                "berry_ids": [],
                "enabled": True,
                "last_checked_at": None,
                "last_status": None,
            }
        ]
    )

    summary = main.check_all_sources()
    assert summary == {"sources_checked": 1, "items_written": 1}

    updated = main.load_sources()[0]
    assert updated["last_checked_at"] is not None
    assert updated["last_status"] == "ok: 1 new item(s)"


def test_check_all_sources_records_fetch_errors(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)

    def _raise(*args, **kwargs):
        raise httpx.ConnectError("simulated network failure")

    monkeypatch.setattr(main.httpx, "get", _raise)
    main.save_sources(
        [
            {
                "id": "source-test",
                "type": "rss",
                "label": "Unreachable feed",
                "value": "https://example.invalid/down.xml",
                "berry_ids": [],
                "enabled": True,
                "last_checked_at": None,
                "last_status": None,
            }
        ]
    )

    summary = main.check_all_sources()
    assert summary == {"sources_checked": 1, "items_written": 0}
    assert "error" in main.load_sources()[0]["last_status"]


def test_evidence_validate_and_purge(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(main.httpx, "get", lambda *a, **k: _FakeResponse(FAKE_RSS))
    source = {"id": "source-test", "type": "rss", "label": "Fictional Trade Press",
              "value": "https://example.invalid/feed.xml", "berry_ids": [], "enabled": True}
    main.check_source(source, set())
    record_id = client.get("/api/feed").json()[0]["id"]

    detail = client.get(f"/evidence/{record_id}")
    assert "AUTO-CAPTURED" in detail.text

    validated = client.post(f"/evidence/{record_id}/validate", follow_redirects=False)
    assert validated.status_code == 303
    assert client.get(f"/evidence/{record_id}").text.count("AUTO-CAPTURED") == 0

    purged = client.post(f"/evidence/{record_id}/purge", follow_redirects=False)
    assert purged.status_code == 303
    assert client.get(f"/evidence/{record_id}").status_code == 404


def test_purge_refuses_non_auto_captured_evidence(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    main.save_evidence(
        {
            "id": "ev-manual-fictional-record",
            "record_type": "evidence",
            "status": "published",
            "source_type": "article",
            "title": "Fictional manually published record",
            "captured_date": "2026-08-04",
            "summary": "Not auto-captured.",
            "submitted_by": "tester",
            "priority": {
                dim: {"level": "none", "rationale": ""}
                for dim in main.PRIORITY_DIMENSIONS
            },
        }
    )
    response = client.post("/evidence/ev-manual-fictional-record/purge")
    assert response.status_code == 400


def test_geography_region_default_lookup_and_unclassified() -> None:
    assert main.geography_region({"name": "Portugal", "attributes": {}}) == "Europe"
    assert main.geography_region({"name": "Australia", "attributes": {}}) == "Oceania"
    assert main.geography_region({"name": "Zambia", "attributes": {}}) == "Middle East & Africa"
    # Not in the fixed lookup -- left unclassified rather than guessed.
    assert main.geography_region({"name": "China", "attributes": {}}) is None


def test_geography_region_override_beats_lookup() -> None:
    geo = {"name": "China", "attributes": {"filter_region": "Asia-Pacific"}}
    assert main.geography_region(geo) == "Asia-Pacific"


def test_geography_region_ignores_unrelated_preexisting_region_attribute() -> None:
    # Real imported data: attributes.region already means something else
    # (the package's own taxonomy) and must not be mistaken for a correction.
    geo = {"name": "Australia", "attributes": {"region": "Asia-Pacific"}}
    assert main.geography_region(geo) == "Oceania"


def test_feed_filters_by_region() -> None:
    response = client.get("/api/feed", params={"region": "Europe"})
    assert response.status_code == 200
    body = response.json()
    assert body
    # geography-europe is linked via geography_ids on this sample record;
    # real imported evidence also legitimately matches Europe via
    # entity_ids-only geography links, so this is a subset check, not exact.
    assert any(item["id"] == "ev-sample-patent-published" for item in body)

    americas = client.get("/api/feed", params={"region": "Americas"}).json()
    americas_ids = {item["id"] for item in americas}
    assert {"ev-sample-variety-launch", "ev-sample-retail-placement"} <= americas_ids


def test_entity_list_filters_by_region() -> None:
    response = client.get("/entities/variety", params={"region": "Europe"})
    assert response.status_code == 200
    assert "Example Red" in response.text
    assert "Example Blue" not in response.text


def test_entity_list_search_matches_selection_code(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    main.save_entity(
        {
            "id": "variety-fictional-coded", "record_type": "entity", "entity_type": "variety",
            "name": "Fictional Coded Variety", "aliases": [], "status": "active", "description": "",
            "roles": [], "berry_ids": [], "evidence_ids": [], "fact_ids": [], "relationship_ids": [],
            "attributes": {"selection_code": "EB 9-12"},
        }
    )
    main.save_entity(
        {
            "id": "variety-fictional-other", "record_type": "entity", "entity_type": "variety",
            "name": "Fictional Other Variety", "aliases": [], "status": "active", "description": "",
            "roles": [], "berry_ids": [], "evidence_ids": [], "fact_ids": [], "relationship_ids": [], "attributes": {},
        }
    )
    response = client.get("/entities/variety", params={"q": "EB 9-12"})
    assert response.status_code == 200
    assert "Fictional Coded Variety" in response.text
    assert "Fictional Other Variety" not in response.text


def test_entity_list_filters_by_company_via_relationships(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    main.save_entity(
        {
            "id": "company-fictional-breeder", "record_type": "entity", "entity_type": "company",
            "name": "Fictional Breeder Co", "aliases": [], "status": "active", "description": "",
            "roles": [], "berry_ids": [], "evidence_ids": [], "fact_ids": [], "relationship_ids": [], "attributes": {},
        }
    )
    main.save_entity(
        {
            "id": "variety-fictional-one", "record_type": "entity", "entity_type": "variety",
            "name": "Fictional Developed Variety", "aliases": [], "status": "active", "description": "",
            "roles": [], "berry_ids": [], "evidence_ids": [], "fact_ids": [], "relationship_ids": [], "attributes": {},
        }
    )
    main.save_entity(
        {
            "id": "variety-fictional-two", "record_type": "entity", "entity_type": "variety",
            "name": "Fictional Unrelated Variety", "aliases": [], "status": "active", "description": "",
            "roles": [], "berry_ids": [], "evidence_ids": [], "fact_ids": [], "relationship_ids": [], "attributes": {},
        }
    )
    main.save_relationship(
        {
            "id": "rel-fictional-develops", "record_type": "relationship",
            "subject_id": "company-fictional-breeder", "predicate": "develops", "object_id": "variety-fictional-one",
            "status": "active", "evidence_ids": ["ev-placeholder"], "effective_date": None, "notes": "",
        }
    )

    response = client.get("/entities/variety", params={"company": "company-fictional-breeder"})
    assert response.status_code == 200
    assert "Fictional Developed Variety" in response.text
    assert "Fictional Unrelated Variety" not in response.text


def test_entity_regions_span_multiple_via_linked_evidence(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    for geo_id, name in [("geography-fictional-a", "Portugal"), ("geography-fictional-b", "Australia")]:
        main.save_entity(
            {
                "id": geo_id, "record_type": "entity", "entity_type": "geography", "name": name,
                "aliases": [], "status": "active", "description": "", "roles": [], "berry_ids": [],
                "evidence_ids": [], "fact_ids": [], "relationship_ids": [], "attributes": {},
            }
        )
    main.save_entity(
        {
            "id": "variety-fictional-multi", "record_type": "entity", "entity_type": "variety",
            "name": "Fictional Multi-Region Variety", "aliases": [], "status": "active", "description": "",
            "roles": [], "berry_ids": [], "evidence_ids": [], "fact_ids": [], "relationship_ids": [], "attributes": {},
        }
    )
    for i, geo_id in enumerate(["geography-fictional-a", "geography-fictional-b"], start=1):
        main.save_evidence(
            {
                "id": f"ev-fictional-multi-{i}", "record_type": "evidence", "status": "published",
                "source_type": "article", "title": f"Fictional trial {i}", "captured_date": "2026-08-04",
                "summary": "x", "submitted_by": "tester",
                "entity_ids": ["variety-fictional-multi", geo_id], "geography_ids": [geo_id],
                "priority": {dim: {"level": "none", "rationale": ""} for dim in main.PRIORITY_DIMENSIONS},
            }
        )

    response = client.get("/entities/variety/variety-fictional-multi")
    assert response.status_code == 200
    assert "Europe" in response.text
    assert "Oceania" in response.text


def test_region_and_geography_detected_when_only_in_entity_ids(monkeypatch, tmp_path) -> None:
    """Real imported data links a geography via entity_ids only, with no
    parallel geography_ids entry (that field postdates the import). Region
    and geography filtering must still find it."""
    _isolate(monkeypatch, tmp_path)
    main.save_entity(
        {
            "id": "geography-fictional-portugal", "record_type": "entity", "entity_type": "geography",
            "name": "Portugal", "aliases": [], "status": "active", "description": "", "roles": [],
            "berry_ids": [], "evidence_ids": [], "fact_ids": [], "relationship_ids": [], "attributes": {},
        }
    )
    main.save_evidence(
        {
            "id": "ev-fictional-no-geography-ids-field", "record_type": "evidence", "status": "published",
            "source_type": "article", "title": "Fictional evidence without geography_ids",
            "captured_date": "2026-08-04", "summary": "x", "submitted_by": "tester",
            "entity_ids": ["geography-fictional-portugal"],
            # Deliberately no "geography_ids" key at all.
            "priority": {dim: {"level": "none", "rationale": ""} for dim in main.PRIORITY_DIMENSIONS},
        }
    )

    region_matches = client.get("/api/feed", params={"region": "Europe"}).json()
    assert any(r["id"] == "ev-fictional-no-geography-ids-field" for r in region_matches)

    geography_matches = client.get("/api/feed", params={"geography": "geography-fictional-portugal"}).json()
    assert any(r["id"] == "ev-fictional-no-geography-ids-field" for r in geography_matches)

    options_page = client.get("/")
    assert "Portugal" in options_page.text


def test_sources_write_endpoints_blocked_in_readonly_mode(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", False)

    assert client.post(
        "/sources", data={"type": "rss", "label": "x", "value": "https://example.invalid/feed.xml"}
    ).status_code == 403
    assert client.post("/sources/source-test/toggle").status_code == 403
    assert client.post("/sources/source-test/delete").status_code == 403
    assert client.post("/sources/source-test/check-now").status_code == 403
    assert client.post("/evidence/ev-sample-variety-launch/validate").status_code == 403
