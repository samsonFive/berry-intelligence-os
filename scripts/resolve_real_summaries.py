"""Resolve real article content for auto-captured evidence whose summary is
just the headline repeated (Google News search results never provide a real
excerpt -- see is_redundant_summary() / ARCHITECTURE.md "Making the newsfeed
actually useful").

Google News's redirect links don't resolve to the real article via a plain
HTTP follow (confirmed earlier -- it's a client-side JS redirect), so this
uses a real headless browser (Playwright) to load each one, wait for the
redirect, and pull the publisher's own meta description -- real text the
publisher wrote about their own article, not a paraphrase or summary
generated here.

Usage:
    python scripts/resolve_real_summaries.py [--limit N] [--delay SECONDS]

Conservative by design given this hits Google News at volume: sequential
(no concurrency), a randomized delay between requests, and it stops the
whole run the moment it sees a sign of being rate-limited or blocked,
rather than continuing to hammer a blocked endpoint. Each record is saved
to disk immediately after resolving, so a stopped run never loses progress
-- rerunning only processes what's still unresolved.
"""
from __future__ import annotations

import argparse
import glob
import json
import random
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright  # noqa: E402

from app.main import is_redundant_summary  # noqa: E402

MIN_DESCRIPTION_LENGTH = 40
BLOCK_SIGNALS = (
    "unusual traffic",
    "verify you are a human",
    "our systems have detected",
    "captcha",
    "sorry.google.com",
    "consent.google.com",
)


def find_candidates() -> list[Path]:
    paths = []
    for path_str in glob.glob(str(ROOT / "data" / "evidence" / "*.json")):
        path = Path(path_str)
        record = json.loads(path.read_text(encoding="utf-8"))
        if not record.get("validated"):
            continue
        if record.get("source_type") != "news_search":
            continue
        if is_redundant_summary(record.get("summary", ""), record.get("title", "")):
            paths.append(path)
    return paths


def looks_blocked(url: str, title: str, body_text: str) -> bool:
    haystack = f"{url} {title} {body_text[:2000]}".lower()
    return any(signal in haystack for signal in BLOCK_SIGNALS)


def extract_description(page) -> str | None:
    for selector in ('meta[property="og:description"]', 'meta[name="description"]'):
        el = page.locator(selector).first
        if el.count():
            content = (el.get_attribute("content") or "").strip()
            if len(content) >= MIN_DESCRIPTION_LENGTH:
                return content
    for p in page.locator("p").all()[:15]:
        text = (p.inner_text() or "").strip()
        if len(text) >= MIN_DESCRIPTION_LENGTH:
            return text
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=1.5, help="base delay between requests, seconds")
    args = parser.parse_args()

    candidates = find_candidates()
    if args.limit:
        candidates = candidates[: args.limit]

    print(f"{len(candidates)} records to resolve.")

    resolved = 0
    no_description = 0
    failed = 0
    blocked_skipped = 0
    blocked_at = None
    recent_block_indices: list[int] = []
    STOP_IF_N_BLOCKS_WITHIN_WINDOW = 3
    BLOCK_WINDOW = 20

    def launch_browser_and_page(playwright_instance):
        browser = playwright_instance.chromium.launch(headless=True)
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        return browser, page

    with sync_playwright() as p:
        browser, page = launch_browser_and_page(p)

        for i, path in enumerate(candidates, start=1):
            record = json.loads(path.read_text(encoding="utf-8"))
            try:
                # "networkidle" (no network activity for 500ms) is too
                # strict for real news sites -- many never go fully idle
                # within any reasonable timeout (ads, analytics, chat
                # widgets keep polling), which measured a ~33% timeout rate
                # on a 15-record trial even though the pages themselves
                # loaded fine. "commit" only waits for navigation to start,
                # so the wait_for_url below carries the real work: give
                # Google's client-side redirect JS time to actually leave
                # news.google.com, then wait for that landing page's DOM.
                page.goto(record["source_url"], wait_until="commit", timeout=20000)
                try:
                    page.wait_for_url(lambda u: "news.google.com" not in u, timeout=10000)
                except Exception:  # noqa: BLE001
                    pass  # still on Google -- handled by the checks below
                page.wait_for_load_state("domcontentloaded", timeout=10000)

                final_url = page.url
                title = page.title()
                body_text = page.locator("body").inner_text() if page.locator("body").count() else ""

                if looks_blocked(final_url, title, body_text):
                    # Many news sites run a brief Cloudflare "checking your
                    # browser" interstitial that resolves on its own --
                    # caught one mid-run that looked exactly like a real
                    # block and turned out to be this (the same URL loaded
                    # cleanly seconds later). One retry after a real pause
                    # distinguishes that from an actual sustained block
                    # before stopping the whole run over a false positive.
                    time.sleep(5)
                    page.reload(wait_until="domcontentloaded", timeout=15000)
                    final_url = page.url
                    title = page.title()
                    body_text = page.locator("body").inner_text() if page.locator("body").count() else ""
                    if looks_blocked(final_url, title, body_text):
                        # Still blocked after a real pause+reload -- treat
                        # as this specific destination site's own bot
                        # protection (seen: an active Cloudflare challenge
                        # token in the URL), not Google-wide rate-limiting.
                        # Skip just this record rather than halting hundreds
                        # of remaining good records over one stubborn site
                        # -- but track how often this happens: several
                        # blocks in a short window would mean something
                        # systemic (e.g. this machine's IP actually being
                        # rate-limited), which is when stopping for real is
                        # the right call.
                        blocked_skipped += 1
                        recent_block_indices.append(i)
                        recent_block_indices[:] = [idx for idx in recent_block_indices if i - idx <= BLOCK_WINDOW]
                        if len(recent_block_indices) >= STOP_IF_N_BLOCKS_WITHIN_WINDOW:
                            blocked_at = i
                            print(
                                f"[{i}/{len(candidates)}] {len(recent_block_indices)} block signals within "
                                f"the last {BLOCK_WINDOW} records -- looks systemic, stopping run."
                            )
                            break
                        print(f"[{i}/{len(candidates)}] BLOCK SIGNAL at {final_url} (site-specific) -- skipping, continuing.")
                        time.sleep(args.delay)
                        continue
                    print(f"[{i}/{len(candidates)}] Transient block signal at {final_url} cleared on retry, continuing.")

                if urlparse(final_url).netloc == "news.google.com":
                    failed += 1
                    print(f"[{i}/{len(candidates)}] Did not leave news.google.com for {record['id']}")
                    time.sleep(args.delay)
                    continue

                description = extract_description(page)
                if not description:
                    no_description += 1
                    print(f"[{i}/{len(candidates)}] No usable description at {final_url}")
                    time.sleep(args.delay)
                    continue

                record["summary"] = description
                record["origin_domain"] = urlparse(final_url).netloc.lower().removeprefix("www.")
                path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                resolved += 1
                if i % 25 == 0 or i == len(candidates):
                    print(f"[{i}/{len(candidates)}] resolved={resolved} no_description={no_description} failed={failed}")
            except Exception as exc:  # noqa: BLE001
                # Covers everything in the block above, not just
                # navigation: a mid-run "Target crashed" (the Chromium tab
                # itself dying on some page, unrelated to blocking) took
                # down the entire batch here once already, losing the rest
                # of a long run to one bad page. Recreate the page so a
                # crashed tab doesn't take every subsequent record with it.
                failed += 1
                print(f"[{i}/{len(candidates)}] UNEXPECTED ERROR {record['id']}: {exc}")
                try:
                    page.close()
                    page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
                except Exception as page_exc:  # noqa: BLE001
                    # A crash severe enough to take the whole browser
                    # process with it (not just the tab) shows up here as
                    # new_page() itself failing -- happened once already
                    # ("Connection closed while reading from the driver"),
                    # which propagated past the old single-level recovery
                    # and killed the entire run. Relaunch the browser too.
                    print(f"[{i}/{len(candidates)}] Page recreation failed ({page_exc}); relaunching browser.")
                    try:
                        browser.close()
                    except Exception:  # noqa: BLE001
                        pass
                    browser, page = launch_browser_and_page(p)
                time.sleep(args.delay)
                continue

            time.sleep(args.delay + random.uniform(0, args.delay))

        browser.close()

    print()
    print(f"Resolved: {resolved}")
    print(f"No usable description found: {no_description}")
    print(f"Failed/timeout: {failed}")
    print(f"Blocked (site-specific, skipped): {blocked_skipped}")
    if blocked_at:
        print(f"Stopped early at record {blocked_at}/{len(candidates)}: block signals looked systemic.")


if __name__ == "__main__":
    main()
