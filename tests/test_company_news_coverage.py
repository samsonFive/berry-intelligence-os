from datetime import date, timedelta
from copy import deepcopy

from app.services.company_news_coverage import company_news_coverage
from app.services.report_builder.packet import build_report_packet
from app.services.report_builder.scope import ResolvedScope
from app.services.report_builder.synthesis import _grounding_digest

COMPANY = {"id": "company-calgiant-test", "entity_type": "company", "name": "California Giant Berry Farms", "aliases": ["Cal Giant"], "berry_ids": ["berry-blueberry"]}


def record(identity, **extra):
    return {"id": identity, "title": "Cal Giant announces blueberry harvest outlook", "status": "published",
            "published_date": (date.today() - timedelta(days=1)).isoformat(), "captured_date": date.today().isoformat(),
            "source_url": "https://publisher.test/" + identity, "source_name": "Publisher", "berry_ids": ["berry-blueberry"], **extra}


def test_current_company_coverage_recalls_alias_and_separates_date_unknown_and_pending():
    published = [record("current"), record("old", published_date="2021-12-14"), record("unknown", published_date=""), record("future", published_date=(date.today()+timedelta(days=1)).isoformat())]
    pending = [record("pending", status="draft", evidence_role="publication_artifact", summary="Before you continue to Google. We use cookies and data to deliver services.")]
    original = deepcopy((published, pending))
    result = company_news_coverage(COMPANY, published=published, pending=pending)
    assert {r["id"] for r in result["items"]} == {"current", "pending"}
    assert result["pending_count"] == 1
    assert [r["id"] for r in result["undated"]] == ["unknown"]
    failed = next(r for r in result["items"] if r["id"] == "pending")
    assert not failed["excerpt"] and not failed["summary"] and failed["notice"]
    assert (published, pending) == original


def test_company_report_keeps_complete_inventory_but_pending_out_of_trusted_synthesis():
    scope = ResolvedScope(report_type="competitive_landscape", company_ids=(COMPANY["id"],), date_window_days=90,
                          berry_id=None, geography_ids=(), variety_ids=(), strategic_question_id=None, focus_notes="")
    published = [record(f"article-{n}") for n in range(20)] + [record("old", published_date="2021-12-14")]
    pending = [record("pending", status="draft", evidence_role="publication_artifact")]
    packet = build_report_packet(scope, entities={COMPANY["id"]: COMPANY}, relationships=[], published_evidence=published,
                                 pending_publications=pending, facts=[], signals=[], assessments=[], strategic_questions=[],
                                 recommendations=[], variety_candidates=[{"id": "unrelated-candidate", "berry_id": "berry-blueberry"}], berry_labels={"berry-blueberry": "Blueberry"})
    assert len(packet["source_inventory"]) == 21
    assert len(packet["recent_developments"]) == 15
    assert packet["variety_candidates"] == []
    assert "pending" not in packet["known_ids"]
    assert "old" not in packet["known_ids"]
    assert all(r["id"] != "pending" for r in packet["source_trace"])
    assert "pending" not in str(_grounding_digest(packet, "recent_developments"))


def test_same_record_in_both_stores_is_counted_once_with_published_status():
    published = record("same")
    pending = record("same", status="draft")
    coverage = company_news_coverage(COMPANY, published=[published], pending=[pending])
    assert len(coverage["items"]) == 1
    assert coverage["pending_count"] == 0


def test_full_body_excerpt_and_incidental_footer_remain_distinct_from_summary():
    text = "California Giant announced a new blueberry harvest program with its growers and described the expected supply for customers. The company did not disclose sales results or acreage for this program."
    row = record("body", article={"paragraphs": [{"text": text, "index": 0}]}, summary="The source discusses a blueberry program.")
    result = company_news_coverage(COMPANY, published=[row])["items"][0]
    assert len(result["excerpt"].split()) == 25
    assert result["summary"] != result["excerpt"]
