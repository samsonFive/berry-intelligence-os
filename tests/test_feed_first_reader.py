from app.services.feed_first_reader import (
    bakeoff_report,
    classify_capture,
    frame_allowed,
    is_public_http_url,
    merge_capture,
    paragraphs_from_html,
    sanitize_reader_html,
)


def test_rejects_private_and_local_urls():
    assert is_public_http_url("https://freshplaza.com/story") is True
    assert is_public_http_url("http://127.0.0.1/secret") is False
    assert is_public_http_url("http://localhost/x") is False
    assert is_public_http_url("http://10.0.0.5/x") is False
    assert is_public_http_url("not-a-url") is False


def test_frame_policy_is_honest():
    assert frame_allowed({}) is True
    assert frame_allowed({"x-frame-options": "DENY"}) is False
    assert frame_allowed({"X-Frame-Options": "sameorigin"}) is False
    assert frame_allowed({"content-security-policy": "frame-ancestors 'none'"}) is False
    assert frame_allowed({"Content-Security-Policy": "frame-ancestors *"}) is True


def test_merge_capture_does_not_invent_body_when_empty():
    record = {"id": "live-1", "title": "Note", "summary": ""}
    merged = merge_capture(record, {"passages": [], "availability": "blocked", "reader_modes": ["structured_fallback"]})
    assert merged["reader_capture"]["availability"] == "blocked"
    assert "article" not in merged


def test_classify_capture_labels_partial_and_blocked():
    assert classify_capture([], status_code=200) == "metadata_only"
    assert classify_capture(["Please log in to continue. Subscribe to continue reading."], status_code=403) == "blocked"
    assert classify_capture(["x" * 120], status_code=200) == "excerpt_only"


def test_bakeoff_does_not_claim_missing_vendors():
    report = bakeoff_report(firecrawl=False, jina=False)
    assert report["direct_http"]["available"] is True
    assert report["firecrawl"]["available"] is False
    assert report["jina"]["available"] is False
    assert "unused" in report["firecrawl"]["notes"].casefold()


def test_unsafe_html_cannot_execute_in_native_reader():
    html = (
        "<p>Wish Farms cut strawberry inspection time by 70 percent this season after the Clarifresh rollout.</p>"
        "<script>alert('xss')</script>"
        "<img src=x onerror=\"alert('xss')\">"
        "<p><a href=\"javascript:alert(1)\">Open the partnership note</a> for growers.</p>"
    )
    cleaned = sanitize_reader_html(html)
    assert "<script" not in cleaned.casefold()
    assert "onerror" not in cleaned.casefold()
    assert "javascript:" not in cleaned.casefold()
    passages = paragraphs_from_html(html)
    blob = " ".join(passages).casefold()
    assert "alert" not in blob
    assert "<script" not in blob
    assert "wish farms" in blob
