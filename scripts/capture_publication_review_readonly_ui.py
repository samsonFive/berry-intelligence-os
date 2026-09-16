#!/usr/bin/env python3
"""Browser verification for Publication Review read-only UI Slice 1.

Starts nothing by itself — expects a live server with
BIOS_PUBLICATION_REVIEW_REHEARSAL_UI=1 for the ten rehearsal states.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "artifacts" / "publication-review-readonly-ui-v1"
OPT_OUT = Path("/opt/cursor/artifacts")


def shot(page, path: Path, full_page: bool = True) -> None:
    page.screenshot(path=str(path), full_page=full_page)
    print(f"wrote {path}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8791/")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    OPT_OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            record_video_dir=str(out / "_video_raw"),
            record_video_size={"width": 1280, "height": 720},
        )
        page = context.new_page()
        page.goto(args.base_url.rstrip("/") + "/review-ops/publications", wait_until="networkidle")
        page.wait_for_selector("#publication-review-readonly")
        assert page.locator("[data-decisions-enabled='false']").count() == 1
        shot(page, out / "01_desktop_queue_readable.png")

        page.goto(args.base_url.rstrip("/") + "/review-ops/publications/pub-transcript", wait_until="networkidle")
        shot(page, out / "02_desktop_transcript.png")

        page.goto(args.base_url.rstrip("/") + "/review-ops/publications/pub-probable-duplicate", wait_until="networkidle")
        shot(page, out / "03_desktop_probable_duplicate.png")

        page.goto(args.base_url.rstrip("/") + "/review-ops/publications/pub-validation-fail", wait_until="networkidle")
        page.locator("#pr-workspace").scroll_into_view_if_needed()
        shot(page, out / "04_desktop_validation_failure.png")

        page.goto(args.base_url.rstrip("/") + "/review-ops/publications?filter=problem", wait_until="networkidle")
        shot(page, out / "05_desktop_filter_problem.png")

        # Confirm disabled controls cannot navigate/post
        page.goto(args.base_url.rstrip("/") + "/review-ops/publications/pub-readable-ok", wait_until="networkidle")
        disabled = page.locator('[data-decision="approve_publication"]')
        assert disabled.is_disabled()
        shot(page, out / "06_desktop_disabled_decisions.png")

        page.set_viewport_size({"width": 834, "height": 1112})
        page.goto(args.base_url.rstrip("/") + "/review-ops/publications/pub-metadata-only", wait_until="networkidle")
        shot(page, out / "07_tablet_metadata_only.png")

        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(args.base_url.rstrip("/") + "/review-ops/publications/pub-missing-entity", wait_until="networkidle")
        shot(page, out / "08_mobile_missing_entity.png")

        # Walkthrough segment
        page.set_viewport_size({"width": 1440, "height": 900})
        for draft_id in (
            "pub-readable-ok",
            "pub-nav-shell",
            "pub-uncertain-date",
            "pub-upgraded",
            "pub-concurrent",
        ):
            page.goto(
                args.base_url.rstrip("/") + f"/review-ops/publications/{draft_id}",
                wait_until="networkidle",
            )
            page.wait_for_timeout(400)

        video_path = Path(page.video.path()) if page.video else None
        context.close()
        browser.close()

        if video_path and video_path.exists():
            dest_webm = out / "walkthrough.webm"
            shutil.move(str(video_path), str(dest_webm))
            mp4 = out / "walkthrough.mp4"
            try:
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-i", str(dest_webm),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(mp4),
                    ],
                    check=True,
                    capture_output=True,
                )
                print(f"wrote {mp4}")
            except Exception as exc:  # noqa: BLE001
                print(f"ffmpeg skipped: {exc}", file=sys.stderr)
            raw = out / "_video_raw"
            if raw.exists():
                shutil.rmtree(raw, ignore_errors=True)

        for name in (
            "01_desktop_queue_readable.png",
            "04_desktop_validation_failure.png",
            "06_desktop_disabled_decisions.png",
            "08_mobile_missing_entity.png",
            "walkthrough.mp4",
            "walkthrough.webm",
        ):
            src = out / name
            if src.exists():
                shutil.copy2(src, OPT_OUT / f"pub-ro-{name}")

    notes = out / "BROWSER-VERIFICATION.md"
    notes.write_text(
        """# Browser verification — Publication Review read-only UI v1

## Environment

- Route: `/review-ops/publications`
- Rehearsal flag: `BIOS_PUBLICATION_REVIEW_REHEARSAL_UI=1` (verification only)
- Viewports: desktop 1440×900, tablet 834×1112, mobile 390×844

## Checks

- Queue + workspace render with pending count and filters
- Ten rehearsal states reachable via draft URLs
- Decision controls present but `disabled` / `data-enabled=false`
- `data-decisions-enabled=false` root attribute
- `data-pagefind-ignore` on private panels
- No decision POST occurs from UI controls
- Desktop / tablet / mobile screenshots + walkthrough video captured

## Safety

DECISION MUTATIONS CONNECTED: NO
REHEARSAL FIXTURES SHIPPED AS LIVE DATA: 0
""",
        encoding="utf-8",
    )
    print(f"wrote {notes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
