from __future__ import annotations

import scripts.resolve_real_summaries as resolve_real_summaries


def test_looks_blocked_detects_known_signals() -> None:
    assert resolve_real_summaries.looks_blocked(
        "https://sorry.google.com/blocked", "Error", ""
    )
    assert resolve_real_summaries.looks_blocked(
        "https://example.com/article", "Just a moment...", "Please verify you are a human"
    )


def test_looks_blocked_false_for_ordinary_page() -> None:
    assert not resolve_real_summaries.looks_blocked(
        "https://freshplaza.com/article/123",
        "SanLucar acquires controlling stake in Twin River Berries",
        "SanLucar has announced the acquisition of a controlling stake in Twin River Berries.",
    )
