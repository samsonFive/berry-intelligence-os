"""Suite defaults. /today must not poll live lanes during unit tests."""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def _pre_admission_catalog(tmp_path_factory):
    """Historical discovery scenarios before the delegated October 27 admissions."""
    import json
    import shutil
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    target = tmp_path_factory.mktemp('pre-admission-catalog') / 'data'
    manifest = json.loads((root / 'data/imports/variety-catalog-admission-2026-10-27/manifest.json').read_text(encoding='utf8'))
    admitted_files = {row['variety_id'] + '.json' for row in manifest['created']}
    # Exclude only explicit admissions while copying into the isolated test catalog.
    shutil.copytree(root / 'data', target, ignore=lambda folder, names: admitted_files.intersection(names)
                    if Path(folder) == root / 'data/entities/varieties' else [])
    return target


@pytest.fixture
def pre_admission_catalog(monkeypatch, _pre_admission_catalog):
    from app import main
    monkeypatch.setattr(main, 'DATA_DIR', _pre_admission_catalog)


@pytest.fixture(scope="session")
def _legacy_seed_catalog(tmp_path_factory):
    """Retain original seed scenarios strictly inside an isolated test catalog."""
    import shutil
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    target = tmp_path_factory.mktemp('legacy-seed-catalog') / 'data'
    shutil.copytree(root / 'data', target)
    shutil.copytree(root / 'tests/fixtures/legacy_seed/data', target, dirs_exist_ok=True)
    return target


@pytest.fixture
def legacy_seed_data(monkeypatch, tmp_path, _legacy_seed_catalog):
    from app import main
    monkeypatch.setattr(main, 'DATA_DIR', _legacy_seed_catalog)
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path / 'inbox')


@pytest.fixture(autouse=True)
def _stub_feed_first_live_http(monkeypatch, request):
    if request.node.get_closest_marker("live_today"):
        return
    from app.services import feed_first_live

    monkeypatch.setattr(
        feed_first_live,
        "live_feed_bundle",
        lambda **kwargs: {
            "today": "2026-09-21",
            "fetched_at": "2026-09-21T12:00:00+00:00",
            "lanes": ["google_news_rss", "specialist_rss", "official_site", "perplexity"],
            "lane_errors": [],
            "stats": {
                "same_day": 0,
                "week": 0,
                "discovered": 0,
                "qualified": 0,
                "dropped_not_today": 0,
                "dropped_undated": 0,
                "dropped_unqualified": 0,
                "official_hosts_polled": 6,
                "official_hits": 0,
            },
            "records": [],
        },
    )
