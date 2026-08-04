from __future__ import annotations

import json

from app import main

PUBLISHED_RECORD = {
    "id": "ev-static-test",
    "record_type": "evidence",
    "status": "published",
    "source_type": "article",
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

    draft_folder = inbox_dir / "evidence"
    draft_folder.mkdir(parents=True, exist_ok=True)
    (draft_folder / f"{DRAFT_RECORD['id']}.json").write_text(json.dumps(DRAFT_RECORD), encoding="utf-8")

    import scripts.build_static as build_static

    output_dir = tmp_path / "generated"
    monkeypatch.setattr(build_static, "OUTPUT_DIR", output_dir)

    assert build_static.main() == 0

    index_html = (output_dir / "index.html").read_text(encoding="utf-8")
    assert "Static build published item" in index_html
    assert "Secret unpublished draft title" not in index_html
    assert DRAFT_RECORD["id"] not in index_html

    evidence_html = (output_dir / "evidence" / PUBLISHED_RECORD["id"] / "index.html").read_text(encoding="utf-8")
    assert "Static build published item" in evidence_html

    css = (output_dir / "static" / "app.css").read_text(encoding="utf-8")
    assert css

    for html_file in output_dir.rglob("*.html"):
        content = html_file.read_text(encoding="utf-8")
        assert DRAFT_RECORD["id"] not in content
        assert "Secret unpublished draft title" not in content
        assert 'href="/' not in content, f"unrewritten absolute href in {html_file}"


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
