from __future__ import annotations

import scripts.resolve_real_summaries as resolve_real_summaries


def test_looks_blocked_detects_known_signals() -> None:
    assert resolve_real_summaries.looks_blocked(
        "https://sorry.google.com/blocked", "Error", ""
    )
    assert resolve_real_summaries.looks_blocked(
        "https://example.com/article", "Just a moment...", "Please verify you are a human"
    )


def test_looks_blocked_detects_px_captcha_and_hcaptcha_walls() -> None:
    # Found via a live diagnostic pass over the unresolved backlog:
    # thepacker.com (PerimeterX) and canr.msu.edu (hCaptcha) both gate
    # automated access with pages matching these exact phrases, but were
    # previously misreported as "no description found" rather than
    # "blocked" since neither contained the word "captcha" in visible body
    # text (it's in a meta tag / not yet rendered).
    assert resolve_real_summaries.looks_blocked(
        "https://www.thepacker.com/news/some-article",
        "Access to this page has been denied",
        "",
    )
    assert resolve_real_summaries.looks_blocked(
        "https://www.canr.msu.edu/news/some-article",
        "",
        "www.canr.msu.edu Additional security check is required I am human",
    )


def test_looks_blocked_false_for_ordinary_page() -> None:
    assert not resolve_real_summaries.looks_blocked(
        "https://freshplaza.com/article/123",
        "SanLucar acquires controlling stake in Twin River Berries",
        "SanLucar has announced the acquisition of a controlling stake in Twin River Berries.",
    )
