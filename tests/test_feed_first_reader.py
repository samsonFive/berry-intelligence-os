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


def test_cached_passages_fill_blank_rows_but_preserve_existing_article_text():
    capture = {"passages": ["Publisher text from the selected cache."], "availability": "excerpt_only"}
    empty = {"id": "live-1", "article": {"paragraphs": [{"text": " "}]}}
    assert merge_capture(empty, capture)["article"]["paragraphs"] == [{"text": capture["passages"][0]}]
    assert empty["article"]["paragraphs"] == [{"text": " "}]
    edited = {"id": "live-1", "article": {"paragraphs": [{"text": "My existing source text", "locator": "p1"}]}}
    assert merge_capture(edited, capture)["article"] == edited["article"]
    full_text = {"id": "live-1", "article": {"full_text": "Existing full-text artifact."}}
    assert merge_capture(full_text, capture)["article"] == full_text["article"]


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


def test_explicit_recommendation_tail_is_not_part_of_article_capture():
    html='<article><p>A cherry breeding partnership was announced after extensive field evaluation.</p><h2>Related articles</h2><p>A named blackberry cultivar was released with compact architecture for growers.</p></article>'
    passages=paragraphs_from_html(html)
    assert len(passages)==1 and 'cherry' in passages[0]
    assert paragraphs_from_html('<h2>Related articles</h2><p>A named blackberry cultivar was released with compact architecture for growers.</p>')==[]
    prose='<article><p>A trial compared blackberry varieties after several seasons in replicated plots.</p><h2>Related research</h2><p>Related articles were reviewed by the researchers when planning this blackberry trial.</p></article>'
    assert any('reviewed by the researchers' in p for p in paragraphs_from_html(prose))


def test_technical_results_beyond_intro_keep_table_context_and_owned_lists():
    intro = ''.join(f'<p>Introduction paragraph {i}: the trial compared harvest timing and fruit quality.</p>' for i in range(30))
    html = ('<nav><li>Menu blackberry trial</li></nav><article>' + intro +
            '<h2>Results</h2><table><caption>Kent 2024 yield, kg per plant</caption>'
            '<tr><th>Cultivar</th><th>Yield</th></tr><tr><td>Trial A</td><td>2.4</td></tr></table>'
            '<ul><li>Trial B: plants were grown under rain covers at the same site.</li></ul>'
            '<aside><li>Recommended commercial supplier</li></aside></article>')
    rows = paragraphs_from_html(html)
    assert rows.index('Kent 2024 yield, kg per plant') < rows.index('Cultivar | Yield') < rows.index('Trial A | 2.4')
    assert any('Trial B:' in row for row in rows)
    assert not any('Menu' in row or 'supplier' in row for row in rows)
    assert len(paragraphs_from_html(html, limit=24)) == 24
    assert not any('Cultivar | Yield' in row for row in paragraphs_from_html(html.replace('<article>', '<div>').replace('</article>', '</div>')))


def test_unnumbered_dated_bibliography_does_not_become_host_trial():
    from app.services.source_passage_scope import owned_article_passages
    prose = 'Researchers compared fruit firmness in a refrigerated storage experiment.'
    reference = 'Ames, Z. R., Corn, R., & Deltsidis, A. (2025, April 18). Postharvest Quality and Sensory Evaluation of Blackberries. Retrieved from https://smallfruits.org/2025/04/postharvest-quality-and-sensory-evaluation-of-blackberries/'
    assert list(owned_article_passages(enumerate([prose, reference]))) == [(0, prose)]


def test_evaluation_requires_its_operation_and_registered_trial_place():
    from app.services.topic_retrieval import plan_query
    from app.services.topic_support import support_context, passage_intent_supported, trial_location_in_passage
    plan = plan_query('Blackberry refrigerated shelf life evaluation Serbia')
    entities = {'s': {'id': 's', 'entity_type': 'geography', 'name': 'Serbia', 'aliases': []}}
    scope = support_context(plan, entities, [])
    assert scope['trial_places'] == [('serbia',)]
    prose = 'Blackberries are delicate and easily damaged during storage.'
    assert not passage_intent_supported(prose, plan)
    assert not trial_location_in_passage('A storage evaluation was performed in Oregon.', scope['trial_places'])
    assert trial_location_in_passage('A storage evaluation was performed in Serbia.', scope['trial_places'])
