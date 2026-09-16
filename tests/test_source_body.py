"""`classify_source_body`'s discovery-provenance failure-category reading.

Regression coverage for a real, previously-undisclosed bug: this function
only read `discovery_provenance.failure_category`, but real acquisition
output stores `acquisition_failure_category` instead (as
`app.services.source_completeness.source_completeness` already correctly
checks). A record with a genuine, retryable-or-not acquisition failure
was silently misclassified as the generic `body_unavailable` instead of
the more specific `access_limited`."""

from __future__ import annotations

from app.services.source_body import classify_source_body


def _empty_record(**discovery_overrides) -> dict:
    return {
        "id": "ev-empty-1", "title": "An empty page", "source_id": "source-1",
        "discovery_provenance": discovery_overrides,
    }


def test_real_acquisition_failure_category_is_access_limited() -> None:
    record = _empty_record(acquisition_failure_category="paywall")

    body = classify_source_body(record)

    assert body["state"] == "access_limited"


def test_legacy_failure_category_key_still_works() -> None:
    record = _empty_record(failure_category="blocked")

    body = classify_source_body(record)

    assert body["state"] == "access_limited"


def test_acquisition_failure_category_takes_precedence_over_legacy_key() -> None:
    record = _empty_record(acquisition_failure_category="empty_body", failure_category="removed")

    body = classify_source_body(record)

    assert body["state"] == "access_limited"


def test_unrecognized_failure_category_is_still_body_unavailable() -> None:
    record = _empty_record(acquisition_failure_category="removed")

    body = classify_source_body(record)

    assert body["state"] == "body_unavailable"


def test_no_failure_category_at_all_is_body_unavailable() -> None:
    body = classify_source_body(_empty_record())

    assert body["state"] == "body_unavailable"
