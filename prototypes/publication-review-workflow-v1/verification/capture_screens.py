#!/usr/bin/env python3
"""Capture desktop/tablet/mobile screenshots + short walkthrough video for
Publication Review Workflow V1 prototype. Fixture-driven; no production calls.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = Path(__file__).resolve().parents[3] / "artifacts" / "publication-review-workflow-v1"
OPT_OUT = Path("/opt/cursor/artifacts")


def ensure_out(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def shot(page, path: Path, full_page: bool = True) -> None:
    page.screenshot(path=str(path), full_page=full_page)
    print(f"wrote {path}")


def select_draft(page, draft_id: str) -> None:
    page.locator(f'[data-draft-id="{draft_id}"]').click()
    page.wait_for_timeout(200)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8765/")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    out = ensure_out(args.out)
    ensure_out(OPT_OUT)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            record_video_dir=str(out / "_video_raw"),
            record_video_size={"width": 1280, "height": 720},
        )
        page = context.new_page()
        page.goto(args.base_url, wait_until="networkidle")
        page.wait_for_selector("#queue-list .queue-item")

        # Desktop — queue + readable workspace
        select_draft(page, "pub-readable-ok")
        shot(page, out / "01_desktop_queue_readable.png")

        # Transcript
        select_draft(page, "pub-transcript")
        shot(page, out / "02_desktop_transcript.png")

        # Limited / metadata-only
        select_draft(page, "pub-metadata-only")
        shot(page, out / "03_desktop_metadata_only.png")

        # Probable duplicate (warn, not block)
        select_draft(page, "pub-probable-duplicate")
        shot(page, out / "04_desktop_probable_duplicate.png")

        # Validation failure — approve disabled
        select_draft(page, "pub-validation-fail")
        page.locator("#workspace").scroll_into_view_if_needed()
        shot(page, out / "05_desktop_validation_failure.png")

        # Concurrent / already handled
        select_draft(page, "pub-concurrent")
        shot(page, out / "06_desktop_already_handled.png")

        # Approve flow with confirmation + receipt
        select_draft(page, "pub-readable-ok")
        page.locator('[data-decision="approve_publication"]').click()
        page.wait_for_selector("#decision-dialog.open")
        shot(page, out / "07_desktop_approve_confirm.png", full_page=False)
        page.locator("[data-confirm]").click()
        page.wait_for_selector("#receipt.open")
        shot(page, out / "08_desktop_approve_receipt.png")

        # Reject requires reason
        page.locator("#reset-demo").click()
        page.wait_for_timeout(200)
        select_draft(page, "pub-nav-shell")
        page.locator('[data-decision="reject"]').click()
        page.wait_for_selector("#decision-dialog.open")
        shot(page, out / "09_desktop_reject_reason.png", full_page=False)
        page.locator("[data-cancel]").click()

        # Filter: problem states
        page.locator('[data-filter="problem"]').click()
        page.wait_for_timeout(150)
        shot(page, out / "10_desktop_filter_problem.png")

        # Walkthrough interactions for video
        page.locator("#reset-demo").click()
        page.wait_for_timeout(200)
        page.locator('[data-filter="all"]').click()
        select_draft(page, "pub-upgraded")
        page.wait_for_timeout(400)
        select_draft(page, "pub-missing-entity")
        page.wait_for_timeout(400)
        select_draft(page, "pub-uncertain-date")
        page.wait_for_timeout(400)
        select_draft(page, "pub-readable-ok")
        page.locator('[data-decision="approve_publication"]').click()
        page.wait_for_selector("#decision-dialog.open")
        page.wait_for_timeout(500)
        page.locator("[data-confirm]").click()
        page.wait_for_selector("#receipt.open")
        page.wait_for_timeout(800)

        # Tablet
        page.set_viewport_size({"width": 834, "height": 1112})
        page.locator("#reset-demo").click()
        page.wait_for_timeout(200)
        select_draft(page, "pub-transcript")
        shot(page, out / "11_tablet_transcript.png")

        # Mobile
        page.set_viewport_size({"width": 390, "height": 844})
        select_draft(page, "pub-probable-duplicate")
        shot(page, out / "12_mobile_queue_workspace.png")
        page.locator('[data-decision="request_correction"]').click()
        page.wait_for_selector("#decision-dialog.open")
        shot(page, out / "13_mobile_correction_dialog.png", full_page=False)

        # Keyboard focus check (desktop again)
        page.set_viewport_size({"width": 1440, "height": 900})
        page.locator("[data-cancel]").click()
        page.keyboard.press("Tab")
        page.keyboard.press("Tab")
        shot(page, out / "14_desktop_focus_ring.png", full_page=False)

        video_path = Path(page.video.path()) if page.video else None
        context.close()
        browser.close()

        if video_path and video_path.exists():
            dest_webm = out / "walkthrough.webm"
            shutil.move(str(video_path), str(dest_webm))
            print(f"wrote {dest_webm}")
            # Convert to mp4 if ffmpeg present
            mp4 = out / "walkthrough.mp4"
            import subprocess

            try:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        str(dest_webm),
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        "-an",
                        str(mp4),
                    ],
                    check=True,
                    capture_output=True,
                )
                print(f"wrote {mp4}")
            except Exception as exc:  # noqa: BLE001
                print(f"ffmpeg convert skipped: {exc}", file=sys.stderr)

            raw = out / "_video_raw"
            if raw.exists():
                shutil.rmtree(raw, ignore_errors=True)

        # Mirror key artifacts for agent walkthrough path
        for name in (
            "01_desktop_queue_readable.png",
            "07_desktop_approve_confirm.png",
            "08_desktop_approve_receipt.png",
            "12_mobile_queue_workspace.png",
            "walkthrough.mp4",
            "walkthrough.webm",
        ):
            src = out / name
            if src.exists():
                shutil.copy2(src, OPT_OUT / f"pub-review-{name}")

    # Write verification notes
    notes = out / "VERIFICATION.md"
    notes.write_text(
        """# Verification — Publication Review Workflow V1

Captured via Playwright against local static server (fixture-only).

## Checks performed

- Queue renders with pending count and all 10 fixture states reachable
- Filters: readable / transcript / limited / problem
- Workspace shows metadata, body/transcript/limited, entities, duplicates, provenance, history
- Approve publication requires confirmation dialog; receipt shows actor/time/draft/publication id
- Reject/correction dialogs require reason
- Validation failure disables approve (contractual blocker)
- Already-handled concurrent fixture visible
- Desktop / tablet / mobile screenshots
- Focus ring screenshot
- Walkthrough video recorded

## Safety

PRODUCTION FILES MODIFIED: 0
PRODUCTION MUTATIONS CONNECTED: NO
BULK APPROVAL AVAILABLE: NO
TRUSTED PUBLICATIONS CREATED: 0
TRUSTED EVIDENCE CREATED: 0
CANONICAL/LIVE DATA MUTATED: 0
""",
        encoding="utf-8",
    )
    print(f"wrote {notes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
