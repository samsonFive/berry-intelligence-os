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
