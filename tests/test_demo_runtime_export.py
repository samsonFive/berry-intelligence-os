from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.export_demo_runtime import ExportError, export_demo_runtime


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_export_includes_specimens_and_dependencies(tmp_path: Path) -> None:
    data = tmp_path / "data"
    inbox = tmp_path / "inbox"
    _write(
        data / "evidence" / "ev-trusted.json",
        {"id": "ev-trusted", "status": "published", "title": "Trusted parent"},
    )
    _write(
        data / "configuration" / "sources.json",
        [{"id": "source-demo", "label": "Demo Source", "type": "rss"}],
    )
    item_id = "discovered-source-business-of-blueberries-podcast-39b3d4545277872a"
    draft = {
        "id": "ev-media-cfc3cc9f97414c09c483",
        "status": "draft",
        "evidence_role": "publication_artifact",
        "title": "How Peru is Preparing for the Next El Niño",
        "discovered_item_id": item_id,
    }
    _write(inbox / "evidence" / f"{draft['id']}.json", draft)
    _write(
        inbox / "discovered_media" / f"{item_id}.json",
        {"id": item_id, "title": "How Peru is Preparing for the Next El Niño"},
    )
    _write(
        inbox / "discovered_media" / "_normalized_transcripts" / f"{item_id}.json",
        {"id": f"transcript-{item_id}", "segments": [{"index": 0, "text": "hello"}]},
    )
    (inbox / "discovered_media" / "_media").mkdir(parents=True)
    (inbox / "discovered_media" / "_media" / f"{item_id}.mp3").write_bytes(b"FAKEAUDIO")
    _write(
        inbox / "evidence" / "ev-unrelated-backlog.json",
        {
            "id": "ev-unrelated-backlog",
            "status": "draft",
            "evidence_role": "publication_artifact",
            "title": "Unrelated backlog",
        },
    )

    output = tmp_path / "demo-runtime"
    manifest = export_demo_runtime(
        output,
        include_all_pending=False,
        data_dir=data,
        inbox_dir=inbox,
    )
    assert manifest["specimens"]["peru_el_nino"] is True
    assert (output / "inbox" / "evidence" / "ev-media-cfc3cc9f97414c09c483.json").is_file()
    assert (output / "inbox" / "discovered_media" / f"{item_id}.json").is_file()
    assert (
        output / "inbox" / "discovered_media" / "_normalized_transcripts" / f"{item_id}.json"
    ).is_file()
    assert not (output / "inbox" / "discovered_media" / "_media").exists()
    assert not (output / "inbox" / "evidence" / "ev-unrelated-backlog.json").exists()
    assert (output / "data" / "evidence" / "ev-trusted.json").is_file()
    assert "ev-unrelated-backlog" not in (output / "MANIFEST.json").read_text(encoding="utf-8")


def test_export_refuses_secret_bearing_files(tmp_path: Path) -> None:
    data = tmp_path / "data"
    inbox = tmp_path / "inbox"
    _write(data / "evidence" / "ev-ok.json", {"id": "ev-ok", "status": "published"})
    _write(
        inbox / "evidence" / "ev-media-cfc3cc9f97414c09c483.json",
        {
            "id": "ev-media-cfc3cc9f97414c09c483",
            "status": "draft",
            "evidence_role": "publication_artifact",
            "title": "leaky",
            "notes": "PERPLEXITY_API_KEY=should-not-export",
        },
    )
    with pytest.raises(ExportError):
        export_demo_runtime(tmp_path / "out", include_all_pending=False, data_dir=data, inbox_dir=inbox)
