from datetime import date

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
    # The two purpose-built sample records are deliberately tagged North
    # America; other real (non-isolated) data may legitimately also match
    # -- e.g. auto-tagging finding genuine North America mentions in the
    # auto-capture backlog -- so this checks presence, not an exact count.
    assert {"ev-sample-variety-launch", "ev-sample-retail-placement"} <= {item["id"] for item in na_body}


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
    # A signal now requires >=2 evidence references (schemas/signal.schema.json,
    # V2 BL-014: "a signal built on one data point is really just a Claim") --
    # publish a second piece of evidence so this exercises a genuinely valid
    # signal, not just the single-evidence shape the schema no longer accepts.
    second_draft_id = _create_draft("Fictional second signal source evidence")
    client.post(
        f"/review/{second_draft_id}/publish",
        data={
            "title": "Fictional second signal source evidence",
            "summary": "Another fictional summary.",
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
            "evidence_ids": f"{draft_id},{second_draft_id}",
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


def test_evidence_validate_and_purge_honor_redirect_to_review(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(main.httpx, "get", lambda *a, **k: _FakeResponse(FAKE_RSS))
    source = {"id": "source-test", "type": "rss", "label": "Fictional Trade Press",
              "value": "https://example.invalid/feed.xml", "berry_ids": [], "enabled": True}
    main.check_source(source, set())
    record_id = client.get("/api/feed").json()[0]["id"]

    validated = client.post(
        f"/evidence/{record_id}/validate", data={"redirect_to": "/review"}, follow_redirects=False
    )
    assert validated.status_code == 303
    assert validated.headers["location"] == "/review"

    main.check_source(source, set())
    other_id = [r["id"] for r in client.get("/api/feed").json() if r["id"] != record_id][0]
    purged = client.post(
        f"/evidence/{other_id}/purge", data={"redirect_to": "/review"}, follow_redirects=False
    )
    assert purged.status_code == 303
    assert purged.headers["location"] == "/review"


def test_evidence_validate_ignores_unrecognized_redirect_to(monkeypatch, tmp_path) -> None:
    # redirect_to is only ever compared against a fixed allowlist, never used
    # as a raw redirect target -- this guards against it becoming an open
    # redirect if a form (or a crafted request) sends something else.
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(main.httpx, "get", lambda *a, **k: _FakeResponse(FAKE_RSS))
    source = {"id": "source-test", "type": "rss", "label": "Fictional Trade Press",
              "value": "https://example.invalid/feed.xml", "berry_ids": [], "enabled": True}
    main.check_source(source, set())
    record_id = client.get("/api/feed").json()[0]["id"]

    response = client.post(
        f"/evidence/{record_id}/validate",
        data={"redirect_to": "https://evil.example/phish"},
        follow_redirects=False,
    )
    assert response.headers["location"] == f"/evidence/{record_id}"


def test_review_queue_shows_unvalidated_auto_captured_evidence(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(main.httpx, "get", lambda *a, **k: _FakeResponse(FAKE_RSS))
    source = {"id": "source-test", "type": "rss", "label": "Fictional Trade Press",
              "value": "https://example.invalid/feed.xml", "berry_ids": [], "enabled": True}
    main.check_source(source, set())

    response = client.get("/review")
    assert response.status_code == 200
    assert "Fictional headline about blueberry licensing" in response.text
    assert "Auto-captured evidence awaiting validation (1)" in response.text
    assert 'name="redirect_to" value="/review"' in response.text


def test_pending_review_count_includes_unvalidated_auto_captured_evidence(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(main.httpx, "get", lambda *a, **k: _FakeResponse(FAKE_RSS))
    source = {"id": "source-test", "type": "rss", "label": "Fictional Trade Press",
              "value": "https://example.invalid/feed.xml", "berry_ids": [], "enabled": True}
    pending_review_count = main.templates.env.globals["pending_review_count"]

    assert pending_review_count() == 0
    main.check_source(source, set())
    assert pending_review_count() == 1

    record_id = client.get("/api/feed").json()[0]["id"]
    client.post(f"/evidence/{record_id}/validate")
    assert pending_review_count() == 0


def test_unvalidated_evidence_sorted_by_source_priority_then_oldest_first(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    main.save_evidence(
        {
            "id": "ev-low-priority-old", "record_type": "evidence", "status": "published",
            "source_type": "news_search", "title": "Low priority, older",
            "auto_captured": True, "validated": False, "source_id": "source-low",
            "captured_date": "2026-01-01",
            "summary": "Summary.", "submitted_by": "test",
            "priority": {dim: {"level": "none", "rationale": ""} for dim in main.PRIORITY_DIMENSIONS},
        }
    )
    main.save_evidence(
        {
            "id": "ev-high-priority-new", "record_type": "evidence", "status": "published",
            "source_type": "news_search", "title": "High priority, newer",
            "auto_captured": True, "validated": False, "source_id": "source-high",
            "captured_date": "2026-06-01",
            "summary": "Summary.", "submitted_by": "test",
            "priority": {dim: {"level": "none", "rationale": ""} for dim in main.PRIORITY_DIMENSIONS},
        }
    )
    main.save_evidence(
        {
            "id": "ev-high-priority-old", "record_type": "evidence", "status": "published",
            "source_type": "news_search", "title": "High priority, older",
            "auto_captured": True, "validated": False, "source_id": "source-high",
            "captured_date": "2026-01-01",
            "summary": "Summary.", "submitted_by": "test",
            "priority": {dim: {"level": "none", "rationale": ""} for dim in main.PRIORITY_DIMENSIONS},
        }
    )
    main.save_sources(
        [
            {"id": "source-low", "type": "rss", "label": "Low", "value": "https://a.invalid/feed.xml",
             "berry_ids": [], "enabled": True, "monitoring_priority": "low"},
            {"id": "source-high", "type": "rss", "label": "High", "value": "https://b.invalid/feed.xml",
             "berry_ids": [], "enabled": True, "monitoring_priority": "high"},
        ]
    )

    ordered = [r["id"] for r in main.unvalidated_auto_captured_evidence()]
    assert ordered == ["ev-high-priority-old", "ev-high-priority-new", "ev-low-priority-old"]


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


def test_us_date_formats_iso_dates_without_leading_zeros() -> None:
    assert main.us_date("2026-08-03") == "8/3/2026"
    assert main.us_date("2026-11-30") == "11/30/2026"


def test_us_date_passes_through_non_iso_values_unchanged() -> None:
    assert main.us_date(None) is None
    assert main.us_date("") == ""
    assert main.us_date("—") == "—"


def test_entity_activity_excludes_evidence_without_published_date() -> None:
    dated = {"id": "ev-1", "title": "Dated", "published_date": "2024-01-15", "source_type": "trade_press"}
    undated = {"id": "ev-2", "title": "Undated reference page", "captured_date": "2026-08-03", "source_type": "company_website"}

    activity = main.entity_activity([dated, undated], [], [], {}, {})

    assert [item["url"] for item in activity] == ["/evidence/ev-1"]


def test_entity_activity_prefers_fact_event_date_over_created_at() -> None:
    fact = {
        "id": "fact-1",
        "statement": "Acquired in 2021.",
        "event_date": "2021-10-20",
        "created_at": "2026-08-03",
        "evidence_ids": [],
        "confidence": "high",
        "status": "active",
    }

    activity = main.entity_activity([], [fact], [], {}, {})

    assert activity[0]["date"] == "2021-10-20"


def test_entity_activity_falls_back_to_created_at_without_event_date() -> None:
    fact = {
        "id": "fact-1",
        "statement": "Static claim with no dateable event.",
        "created_at": "2026-08-03",
        "evidence_ids": [],
        "confidence": "medium",
        "status": "active",
    }

    activity = main.entity_activity([], [fact], [], {}, {})

    assert activity[0]["date"] == "2026-08-03"


def test_entity_page_shows_recent_activity_with_us_formatted_dates() -> None:
    response = client.get("/entities/company/company-example-genetics")
    assert response.status_code == 200
    assert "Recent activity" in response.text
    assert "7/28/2026" in response.text


def test_as_bullets_splits_on_sentence_boundaries() -> None:
    text = "Reports the 2025 rebrand of Agrovision to Fruitist. It gives the founding year as 2012."
    assert main.as_bullets(text) == [
        "Reports the 2025 rebrand of Agrovision to Fruitist.",
        "It gives the founding year as 2012.",
    ]


def test_as_bullets_does_not_split_on_a_middle_initial() -> None:
    text = "Breeders David M. Brazelton and Adam L. Wagner are named."
    assert main.as_bullets(text) == [text]


def test_as_bullets_does_not_split_on_a_company_suffix_mid_sentence() -> None:
    text = "Fall Creek Farm & Nursery, Inc. was founded in 1978 in Lowell, Oregon."
    assert main.as_bullets(text) == [text]


def test_as_bullets_splits_after_a_company_suffix_at_a_real_sentence_end() -> None:
    text = "Costa Berry International Pty Ltd. The variety is marketed internationally."
    assert main.as_bullets(text) == [
        "Costa Berry International Pty Ltd.",
        "The variety is marketed internationally.",
    ]


def test_as_bullets_handles_empty_and_none() -> None:
    assert main.as_bullets(None) == []
    assert main.as_bullets("") == []


def test_evidence_detail_renders_multi_sentence_summary_as_bullet_list() -> None:
    response = client.get("/evidence/ev-leadersleague-atlantic-blue-2021")
    assert response.status_code == 200
    assert 'class="bullet-list"' in response.text
    assert "Atlantic Blue of Huelva" in response.text


def test_evidence_detail_renders_single_sentence_summary_as_plain_paragraph() -> None:
    response = client.get("/evidence/ev-sample-variety-launch")
    assert response.status_code == 200
    assert "<p>A fictional breeder announced a low-chill blueberry variety" in response.text


def test_text_matches_exact_and_phrase_still_work() -> None:
    assert main.text_matches("hortifrut", "Hortifrut S.A. investor page")
    assert main.text_matches("example blue", "A fictional Example Blue variety")
    assert not main.text_matches("nonexistent term", "Hortifrut S.A. investor page")


def test_text_matches_tolerates_common_typos() -> None:
    assert main.text_matches("hortifruit", "Hortifrut S.A. investor page")
    assert main.text_matches("hortifrit", "Hortifrut S.A. investor page")


def test_text_matches_does_not_fuzzy_match_short_or_unrelated_words() -> None:
    assert not main.text_matches("coast", "Costa Group Holdings Limited")
    assert not main.text_matches("cat", "Costa Group Holdings Limited")


def test_api_search_finds_entity_by_misspelled_query() -> None:
    response = client.get("/api/search", params={"q": "hortifruit"})
    assert response.status_code == 200
    body = response.json()
    assert any(e["id"] == "company-hortifrut" for e in body["entities"])


def test_next_check_due_and_source_is_due() -> None:
    weekly_recent = {"update_cadence": "weekly", "last_checked_at": date.today().isoformat() + "T00:00:00"}
    assert main.next_check_due(weekly_recent) > date.today().isoformat()
    assert not main.source_is_due(weekly_recent)

    weekly_old = {"update_cadence": "weekly", "last_checked_at": "2000-01-01T00:00:00"}
    assert main.source_is_due(weekly_old)

    never_checked = {"update_cadence": "annual", "last_checked_at": None}
    assert main.next_check_due(never_checked) == date.today().isoformat()

    event_driven = {"update_cadence": "event_driven", "last_checked_at": "2000-01-01T00:00:00"}
    assert main.next_check_due(event_driven) is None
    assert not main.source_is_due(event_driven)


def test_source_has_coverage_gap() -> None:
    assert main.source_has_coverage_gap({"berry_ids": [], "region_coverage": ["global"]})
    assert main.source_has_coverage_gap({"berry_ids": ["berry-blueberry"], "region_coverage": []})
    assert not main.source_has_coverage_gap({"berry_ids": ["berry-blueberry"], "region_coverage": ["global"]})


def test_filter_sources_by_entity_type_berry_region_priority_and_view() -> None:
    sources = [
        {"id": "s1", "entity_types": ["trade_press"], "berry_ids": ["berry-blueberry"],
         "region_coverage": ["global"], "monitoring_priority": "high", "type": "keyword",
         "update_cadence": "weekly", "last_checked_at": "2000-01-01T00:00:00"},
        {"id": "s2", "entity_types": ["government_regulatory"], "berry_ids": [],
         "region_coverage": [], "monitoring_priority": "low", "type": "reference"},
    ]
    assert [s["id"] for s in main.filter_sources(sources, entity_type="trade_press")] == ["s1"]
    assert [s["id"] for s in main.filter_sources(sources, berry="berry-blueberry")] == ["s1"]
    assert [s["id"] for s in main.filter_sources(sources, priority="low")] == ["s2"]
    assert [s["id"] for s in main.filter_sources(sources, view="gaps")] == ["s2"]
    assert [s["id"] for s in main.filter_sources(sources, view="due")] == ["s1"]


def test_group_sources_by_berry_lets_multi_berry_source_appear_in_each_group() -> None:
    sources = [{"id": "s1", "berry_ids": ["berry-blueberry", "berry-raspberry"], "monitoring_priority": "high"}]
    grouped = dict(main.group_sources(sources, "berry"))
    assert [s["id"] for s in grouped["Blueberry"]] == ["s1"]
    assert [s["id"] for s in grouped["Raspberry"]] == ["s1"]


def test_domain_of_strips_www() -> None:
    assert main.domain_of("https://www.freshfruitportal.com/article/x") == "freshfruitportal.com"
    assert main.domain_of("https://trendhunter.com/x") == "trendhunter.com"


def test_source_polling_loop_is_disabled_by_default() -> None:
    assert main.SOURCE_POLLING_ENABLED is False


def test_check_source_skips_reference_type_sources() -> None:
    written = main.check_source({"type": "reference", "id": "s1"}, set())
    assert written == 0


def test_check_all_sources_skips_reference_sources_last_checked(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    main.save_sources(
        [{"id": "source-ref", "type": "reference", "label": "Some Report", "value": "Some Report",
          "berry_ids": [], "enabled": True, "last_checked_at": None, "last_status": None}]
    )
    summary = main.check_all_sources()
    assert summary == {"sources_checked": 0, "items_written": 0}
    assert main.load_sources()[0]["last_checked_at"] is None


def test_sources_mark_checked_sets_reviewed_status(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    main.save_sources(
        [{"id": "source-ref", "type": "reference", "label": "Some Report", "value": "Some Report",
          "berry_ids": [], "enabled": True, "last_checked_at": None, "last_status": None}]
    )
    response = client.post("/sources/source-ref/mark-checked", follow_redirects=False)
    assert response.status_code == 303
    source = main.load_sources()[0]
    assert source["last_status"] == "reviewed"
    assert source["last_checked_at"] is not None


def test_evidence_validate_bumps_source_validated_count(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(main.httpx, "get", lambda *a, **k: _FakeResponse(FAKE_RSS))
    main.save_sources(
        [{"id": "source-test", "type": "rss", "label": "Fictional Trade Press",
          "value": "https://example.invalid/feed.xml", "berry_ids": [], "enabled": True}]
    )
    main.check_source(main.load_sources()[0], set())
    record_id = client.get("/api/feed").json()[0]["id"]

    client.post(f"/evidence/{record_id}/validate")

    assert main.load_sources()[0]["validated_count"] == 1


def test_evidence_purge_bumps_source_purged_count_and_can_block_domain(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(main.httpx, "get", lambda *a, **k: _FakeResponse(FAKE_RSS))
    main.save_sources(
        [{"id": "source-test", "type": "rss", "label": "Fictional Trade Press",
          "value": "https://example.invalid/feed.xml", "berry_ids": [], "enabled": True}]
    )
    main.check_source(main.load_sources()[0], set())
    record_id = client.get("/api/feed").json()[0]["id"]

    client.post(f"/evidence/{record_id}/purge", data={"block_domain": "true"})

    assert main.load_sources()[0]["purged_count"] == 1
    assert "example.invalid" in main.load_blocked_domains()


def test_check_source_skips_blocked_domains(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(main.httpx, "get", lambda *a, **k: _FakeResponse(FAKE_RSS))
    main.save_blocked_domains(["example.invalid"])

    source = {"id": "source-test", "type": "rss", "label": "Fictional Trade Press",
              "value": "https://example.invalid/feed.xml", "berry_ids": [], "enabled": True}
    written = main.check_source(source, set())

    assert written == 0
    assert client.get("/api/feed").json() == []


def test_sources_unblock_domain(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    main.save_blocked_domains(["example.invalid", "trendhunter.com"])

    response = client.post("/sources/blocked-domains/example.invalid/remove", follow_redirects=False)

    assert response.status_code == 303
    assert main.load_blocked_domains() == ["trendhunter.com"]


def test_add_blocked_domain_refuses_the_google_news_redirect_host(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)

    assert main.add_blocked_domain("news.google.com") is False
    assert main.load_blocked_domains() == []
    assert main.add_blocked_domain("trendhunter.com") is True
    assert main.load_blocked_domains() == ["trendhunter.com"]


def test_evidence_purge_block_domain_never_blocks_news_google_com(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    main.save_evidence(
        {
            "id": "ev-no-origin-domain",
            "record_type": "evidence",
            "status": "published",
            "source_type": "news_search",
            "title": "Fictional headline with no origin_domain recorded",
            "source_name": "Fictional Publisher",
            "source_url": "https://news.google.com/rss/articles/fictional",
            "captured_date": "2026-01-01",
            "summary": "x",
            "submitted_by": "tester",
            "auto_captured": True,
            "validated": False,
            "priority": {dim: {"level": "none", "rationale": ""} for dim in main.PRIORITY_DIMENSIONS},
        }
    )

    client.post("/evidence/ev-no-origin-domain/purge", data={"block_domain": "true"})

    assert main.load_blocked_domains() == []


def test_auto_tag_geography_and_entities_matches_known_names() -> None:
    record = {
        "title": "Peru blueberry exports grow as Hortifrut expands operations",
        "summary": "Peru blueberry exports grow as Hortifrut expands operations",
        "auto_captured": True,
        "validated": False,
        "geography_ids": [],
        "entity_ids": [],
    }

    tagged = main.auto_tag_geography_and_entities(record)

    assert "geography-peru" in tagged["geography_ids"]
    assert "company-hortifrut" in tagged["entity_ids"]
    assert tagged["auto_tagged"] is True


def test_auto_tag_geography_and_entities_skips_reviewed_records() -> None:
    record = {
        "title": "Peru blueberry exports grow",
        "summary": "Peru blueberry exports grow",
        "auto_captured": True,
        "validated": True,
        "geography_ids": [],
        "entity_ids": [],
    }

    tagged = main.auto_tag_geography_and_entities(record)

    assert tagged["geography_ids"] == []
    assert "auto_tagged" not in tagged


def test_auto_tag_geography_and_entities_skips_manually_authored_records() -> None:
    record = {
        "title": "Peru blueberry exports grow",
        "summary": "Peru blueberry exports grow",
        "auto_captured": False,
        "validated": False,
        "geography_ids": [],
        "entity_ids": [],
    }

    tagged = main.auto_tag_geography_and_entities(record)

    assert tagged["geography_ids"] == []
    assert "auto_tagged" not in tagged


def test_auto_tag_geography_and_entities_no_false_positive_on_unrelated_text() -> None:
    record = {
        "title": "A completely unrelated headline about nothing in particular",
        "summary": "No real content here.",
        "auto_captured": True,
        "validated": False,
        "geography_ids": [],
        "entity_ids": [],
    }

    tagged = main.auto_tag_geography_and_entities(record)

    assert tagged["geography_ids"] == []
    assert tagged["entity_ids"] == []
    assert "auto_tagged" not in tagged


def test_is_redundant_summary_detects_google_news_style_repetition() -> None:
    assert main.is_redundant_summary(
        "Breeding Better Blueberries&nbsp;&nbsp;NC State University",
        "Breeding Better Blueberries - NC State University",
    )
    assert not main.is_redundant_summary(
        "A genuine excerpt describing what actually happened in the article.",
        "Breeding Better Blueberries - NC State University",
    )


def test_feed_shows_linked_geography_tags_and_suppresses_redundant_summary(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    main.save_evidence(
        {
            "id": "ev-fictional-auto-tagged",
            "record_type": "evidence",
            "status": "published",
            "source_type": "news_search",
            "title": "Fictional headline about Peru blueberries",
            "source_name": "Fictional Publisher",
            "source_url": "https://example.invalid/x",
            "captured_date": "2026-01-01",
            "summary": "Fictional headline about Peru blueberries&nbsp;&nbsp;Fictional Publisher",
            "submitted_by": "tester",
            "auto_captured": True,
            "validated": False,
            "auto_tagged": True,
            "geography_ids": ["geography-peru"],
            "entity_ids": [],
            "priority": {dim: {"level": "none", "rationale": ""} for dim in main.PRIORITY_DIMENSIONS},
        }
    )

    response = client.get("/")

    assert "Peru" in response.text
    assert "auto-tagged, unverified" in response.text
    assert "Fictional headline about Peru blueberries&amp;nbsp;" not in response.text
    assert "read the full article" in response.text


def test_entity_page_shows_weighted_searchable_aliases() -> None:
    response = client.get("/entities/company/company-mountain-blue-orchards")
    assert response.status_code == 200
    assert 'data-pagefind-weight="10"' in response.text
    assert "Also known as:" in response.text
    assert "MBO" in response.text
    # Aliases must not be inside the ignored metadata block -- that's the
    # regression this test guards against (an alias that isn't indexed at
    # all can't be found by searching it, regardless of weight).
    ignored_block_start = response.text.index('<dl data-pagefind-ignore>')
    ignored_block_end = response.text.index('</dl>', ignored_block_start)
    assert "Also known as" not in response.text[ignored_block_start:ignored_block_end]


def test_entity_page_omits_aliases_line_when_none() -> None:
    response = client.get("/entities/company/company-example-genetics")
    assert response.status_code == 200
    assert "Also known as:" not in response.text


def test_entity_page_tagged_for_search_prioritization() -> None:
    response = client.get("/entities/company/company-mountain-blue-orchards")
    assert response.status_code == 200
    assert 'data-pagefind-filter="type:entity"' in response.text


def test_evidence_page_tagged_with_search_type_and_sort_date() -> None:
    response = client.get("/evidence/ev-sample-variety-launch")
    assert response.status_code == 200
    assert 'data-pagefind-filter="type:evidence"' in response.text
    # Prefers published_date over captured_date so the newsfeed-by-recency
    # search ordering reflects when the article actually ran, not when this
    # app happened to capture it.
    assert 'data-pagefind-sort="date:2026-07-28"' in response.text
