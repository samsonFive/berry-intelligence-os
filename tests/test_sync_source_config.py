"""scripts/sync_source_config.py -- additive-only deployed-runtime source
config sync.

Real bug this exists to fix: docker-entrypoint.sh seeds a runtime's
data/configuration/sources.json exactly once (only on a genuinely empty
volume). A real production VPS was seeded before Fresh Fruit Portal,
Fresh Plaza, and Produce Report (the article_rss sources) were added to
canonical -- so its recurring collector kept discovering zero web_article
items, correctly, despite the sources existing in every subsequent git
checkout. These tests prove the sync is additive-only: it introduces
newly-shipped sources without ever touching an id already present at
runtime (whether from the original seed or added live via the authoring
UI), and never touches anything outside the source-config file itself.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.sync_source_config import sync_source_config

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, sources: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sources), encoding="utf-8")


def test_adds_a_seed_source_missing_from_runtime(tmp_path: Path) -> None:
    seed = tmp_path / "seed.json"
    runtime = tmp_path / "runtime.json"
    _write(seed, [{"id": "source-a", "label": "A"}, {"id": "source-b", "label": "B"}])
    _write(runtime, [{"id": "source-a", "label": "A"}])

    result = sync_source_config(seed, runtime)

    assert result == {"added": ["source-b"], "skipped_missing_seed": False}
    saved = json.loads(runtime.read_text(encoding="utf-8"))
    assert {s["id"] for s in saved} == {"source-a", "source-b"}


def test_never_overwrites_an_existing_runtime_source_even_if_seed_differs(tmp_path: Path) -> None:
    """An operator's live edit (e.g. via the authoring 'Add source' form,
    or a manual correction) must survive every future deploy."""
    seed = tmp_path / "seed.json"
    runtime = tmp_path / "runtime.json"
    _write(seed, [{"id": "source-a", "label": "Seed Label", "update_cadence": "weekly"}])
    _write(runtime, [{"id": "source-a", "label": "Operator-Edited Label", "update_cadence": "monthly"}])

    sync_source_config(seed, runtime)

    saved = json.loads(runtime.read_text(encoding="utf-8"))
    assert saved == [{"id": "source-a", "label": "Operator-Edited Label", "update_cadence": "monthly"}]


def test_creates_runtime_file_from_seed_when_missing(tmp_path: Path) -> None:
    seed = tmp_path / "seed.json"
    runtime = tmp_path / "does-not-exist" / "runtime.json"
    _write(seed, [{"id": "source-a"}, {"id": "source-b"}])

    result = sync_source_config(seed, runtime)

    assert set(result["added"]) == {"source-a", "source-b"}
    saved = json.loads(runtime.read_text(encoding="utf-8"))
    assert {s["id"] for s in saved} == {"source-a", "source-b"}


def test_missing_seed_file_is_a_safe_no_op(tmp_path: Path) -> None:
    seed = tmp_path / "does-not-exist.json"
    runtime = tmp_path / "runtime.json"
    _write(runtime, [{"id": "source-a"}])

    result = sync_source_config(seed, runtime)

    assert result == {"added": [], "skipped_missing_seed": True}
    assert json.loads(runtime.read_text(encoding="utf-8")) == [{"id": "source-a"}]


def test_running_twice_is_idempotent(tmp_path: Path) -> None:
    seed = tmp_path / "seed.json"
    runtime = tmp_path / "runtime.json"
    _write(seed, [{"id": "source-a"}, {"id": "source-b"}])
    _write(runtime, [{"id": "source-a"}])

    first = sync_source_config(seed, runtime)
    second = sync_source_config(seed, runtime)

    assert first["added"] == ["source-b"]
    assert second["added"] == []
    saved = json.loads(runtime.read_text(encoding="utf-8"))
    assert len(saved) == 2
    assert sorted(s["id"] for s in saved) == ["source-a", "source-b"]


def test_no_op_when_runtime_already_has_every_seed_source(tmp_path: Path) -> None:
    seed = tmp_path / "seed.json"
    runtime = tmp_path / "runtime.json"
    sources = [{"id": "source-a"}, {"id": "source-b"}]
    _write(seed, sources)
    _write(runtime, sources)
    original_mtime = runtime.stat().st_mtime

    result = sync_source_config(seed, runtime)

    assert result["added"] == []
    # File is not rewritten when there is nothing to add.
    assert runtime.stat().st_mtime == original_mtime


def test_a_freshly_synced_runtime_gains_the_real_article_sources(tmp_path: Path) -> None:
    """Prove against the *real* canonical data/configuration/sources.json
    (not a synthetic fixture) that a runtime seeded before article_rss
    sources existed -- exactly the VPS's real starting state -- ends up
    with them, enabled, after one sync. This is the actual regression
    test for the deployment bug: a real deployed runtime's recurring
    collector had zero web_article sources despite three being live in
    canonical, because nothing had ever re-synced this file."""
    seed = REPO_ROOT / "data" / "configuration" / "sources.json"
    assert seed.is_file(), "canonical source registry must exist for this test to be meaningful"

    # Simulate the VPS's real starting condition: an empty runtime,
    # standing in for "seeded before article sources were added."
    runtime = tmp_path / "runtime-sources.json"
    _write(runtime, [])

    result = sync_source_config(seed, runtime)

    saved = {s["id"]: s for s in json.loads(runtime.read_text(encoding="utf-8"))}
    article_sources = {
        source_id: record
        for source_id, record in saved.items()
        if (record.get("discovery") or {}).get("adapter") == "article_rss"
    }
    assert len(article_sources) >= 3, "expected at least the 3 known article_rss sources to sync in"
    for record in article_sources.values():
        assert (record.get("discovery") or {}).get("feed_url"), "each article source must carry a real feed_url"
    assert set(result["added"]) >= set(article_sources)
