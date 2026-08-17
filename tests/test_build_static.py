from __future__ import annotations

import json
import sys

import pytest

from app import main

PUBLISHED_RECORD = {
    "id": "ev-static-test",
    "record_type": "evidence",
    "status": "published",
    "source_type": "article",
    "source_name": "Static Test Publisher",
    "source_url": "https://example.invalid/original-article",
    "title": "Static build published item",
    "captured_date": "2026-08-04",
    "summary": "Should appear in the static build.",
    "submitted_by": "tester",
    "berry_ids": [],
    "entity_ids": [],
    "fact_ids": [],
    "relationship_ids": [],
    "strategic_question_ids": [],
    "tags": [],
    "priority": {
        "reading": {"level": "high", "rationale": "x"},
        "testing": {"level": "none", "rationale": ""},
        "commercial_position": {"level": "none", "rationale": ""},
        "monitoring": {"level": "none", "rationale": ""},
    },
}

DRAFT_RECORD = {
    "id": "ev-draft-should-not-appear",
    "record_type": "evidence",
    "status": "draft",
    "source_type": "article",
    "title": "Secret unpublished draft title",
    "captured_date": "2026-08-04",
    "summary": "Should never appear anywhere in the static build.",
    "submitted_by": "tester",
    "priority": None,
}


def test_static_build_excludes_drafts_and_includes_published(monkeypatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    inbox_dir = tmp_path / "inbox"
    monkeypatch.setattr(main, "DATA_DIR", data_dir)
    monkeypatch.setattr(main, "INBOX_DIR", inbox_dir)

    evidence_folder = data_dir / "evidence"
    evidence_folder.mkdir(parents=True, exist_ok=True)
    (evidence_folder / f"{PUBLISHED_RECORD['id']}.json").write_text(
        json.dumps(PUBLISHED_RECORD), encoding="utf-8"
    )
    config_dir = data_dir / "configuration"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "sources.json").write_text(
        json.dumps(
            [
                {
                    "id": "source-static-test",
                    "type": "rss",
                    "label": "Static Test Source",
                    "value": "https://example.invalid/feed.xml",
                    "enabled": True,
                    "entity_types": ["trade_press"],
                    "berry_ids": ["berry-blueberry"],
                    "region_coverage": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    draft_folder = inbox_dir / "evidence"
    draft_folder.mkdir(parents=True, exist_ok=True)
    (draft_folder / f"{DRAFT_RECORD['id']}.json").write_text(json.dumps(DRAFT_RECORD), encoding="utf-8")

    import scripts.build_static as build_static

    output_dir = tmp_path / "generated"
    monkeypatch.setattr(build_static, "OUTPUT_DIR", output_dir)

    assert build_static.main() == 0
    assert (output_dir / ".nojekyll").is_file()

    index_html = (output_dir / "index.html").read_text(encoding="utf-8")
    assert "Static build published item" in index_html
    assert 'href="https://example.invalid/original-article"' in index_html
    assert "Static Test Publisher" in index_html
    assert 'data-feed-region="global"' in index_html
    assert 'data-feed-region="asia"' in index_html
    assert 'data-feed-regions=""' in index_html
    assert "card.dataset.feedRegions" in index_html
    assert "Secret unpublished draft title" not in index_html
    assert DRAFT_RECORD["id"] not in index_html

    evidence_html = (output_dir / "evidence" / PUBLISHED_RECORD["id"] / "index.html").read_text(encoding="utf-8")
    assert "Static build published item" in evidence_html
    assert 'href="https://example.invalid/original-article"' in evidence_html
    assert "Static Test Publisher" in evidence_html
    assert "<h2>Provenance</h2>" not in evidence_html

    css = (output_dir / "static" / "app.css").read_text(encoding="utf-8")
    assert css

    for html_file in output_dir.rglob("*.html"):
        content = html_file.read_text(encoding="utf-8")
        assert DRAFT_RECORD["id"] not in content
        assert "Secret unpublished draft title" not in content
        assert 'href="/' not in content, f"unrewritten absolute href in {html_file}"

    search_html = (output_dir / "search" / "index.html").read_text(encoding="utf-8")
    assert 'id="pagefind-js-path"' in search_html
    assert 'href="../pagefind/pagefind.js"' in search_html
    assert 'id="search-results"' in search_html

    landscape_html = (
        output_dir / "landscapes" / "berries" / "blueberry" / "index.html"
    ).read_text(encoding="utf-8")
    assert 'href="../../../static/app.css"' in landscape_html
    assert 'class="filter-chip region-filter' in landscape_html
    assert "history.replaceState" in landscape_html
    assert 'href="../../../entities/company/' in landscape_html
    assert "Competitor × Competitive Theme Matrix" in landscape_html
    assert 'href="../../../entities/variety/' in landscape_html

    scanner_html = (output_dir / "work-queue" / "index.html").read_text(encoding="utf-8")
    assert "Scanner" in scanner_html
    assert "FOUND" in scanner_html
    assert "ACCEPTED" in scanner_html
    assert "Trusted published snapshot" in scanner_html
    assert "Interactive publication review is local-only" in scanner_html
    assert "Secret unpublished draft title" not in scanner_html
    assert DRAFT_RECORD["id"] not in scanner_html
    assert 'href="review/' not in scanner_html
    assert "/review" not in scanner_html

    sources_html = (output_dir / "sources" / "index.html").read_text(encoding="utf-8")
    assert "Sources" in sources_html
    assert "Static Test Source" in sources_html
    assert "Add a source" not in sources_html
    assert "Check now" not in sources_html
    assert "Remove" not in sources_html


def test_static_build_detects_leak_if_validation_bypassed(monkeypatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    inbox_dir = tmp_path / "inbox"
    monkeypatch.setattr(main, "DATA_DIR", data_dir)
    monkeypatch.setattr(main, "INBOX_DIR", inbox_dir)

    draft_folder = inbox_dir / "evidence"
    draft_folder.mkdir(parents=True, exist_ok=True)
    (draft_folder / f"{DRAFT_RECORD['id']}.json").write_text(json.dumps(DRAFT_RECORD), encoding="utf-8")

    import scripts.build_static as build_static

    output_dir = tmp_path / "generated"
    monkeypatch.setattr(build_static, "OUTPUT_DIR", output_dir)

    build_static.build()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "leak.html").write_text(f"oops {DRAFT_RECORD['id']}", encoding="utf-8")

    assert build_static.validate_no_drafts_leaked() != []


def test_build_search_index_skips_gracefully_without_pagefind(monkeypatch, tmp_path) -> None:
    import scripts.build_static as build_static

    monkeypatch.setattr(build_static, "OUTPUT_DIR", tmp_path)
    # A None entry in sys.modules makes `import pagefind` raise ImportError,
    # simulating an environment where the optional tool isn't installed --
    # the build must still succeed overall, just without a search index.
    monkeypatch.setitem(sys.modules, "pagefind", None)

    assert build_static.build_search_index() is False


def test_build_search_index_raises_on_pagefind_failure(monkeypatch, tmp_path) -> None:
    import scripts.build_static as build_static

    monkeypatch.setattr(build_static, "OUTPUT_DIR", tmp_path)
    pytest.importorskip("pagefind")

    class _FailedRun:
        returncode = 1
        stdout = ""
        stderr = "simulated pagefind failure"

    monkeypatch.setattr(build_static.subprocess, "run", lambda *a, **k: _FailedRun())

    with pytest.raises(RuntimeError, match="pagefind failed"):
        build_static.build_search_index()


def test_build_search_index_succeeds_when_available(monkeypatch, tmp_path) -> None:
    pytest.importorskip("pagefind")
    import scripts.build_static as build_static

    output_dir = tmp_path / "generated"
    output_dir.mkdir(parents=True)
    (output_dir / "index.html").write_text(
        "<html><body><main data-pagefind-body><h1>Fictional page</h1></main></body></html>",
        encoding="utf-8",
    )
    monkeypatch.setattr(build_static, "OUTPUT_DIR", output_dir)

    assert build_static.build_search_index() is True
    assert (output_dir / "pagefind" / "pagefind.js").exists()
