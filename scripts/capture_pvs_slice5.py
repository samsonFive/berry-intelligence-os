#!/usr/bin/env python3
"""Browser verification for PVS Production Slice 5 (Reading Queue)."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "artifacts" / "product-visual-system-production-slice5"
OPT = Path("/opt/cursor/artifacts")


def copy_opt(out: Path, name: str) -> None:
    src = out / name
    if src.exists():
        shutil.copy(src, OPT / f"pvs-slice5-{name}")
        print("copied", name, src.stat().st_size)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:18795")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    OPT.mkdir(parents=True, exist_ok=True)
    base = args.base_url.rstrip("/")

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            record_video_dir=str(out / "_video_raw"),
            record_video_size={"width": 1280, "height": 720},
        )
        page = context.new_page()
        page.set_default_timeout(60000)
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        page.goto(f"{base}/queues/reading", wait_until="domcontentloaded")
        assert page.locator('[data-pvs-slice="5"]').count() == 1
        assert page.locator('link[href="/static/reading_pvs.css"]').count() == 1
        page.screenshot(path=str(out / "01_desktop_reading_queue.png"), full_page=False)
        copy_opt(out, "01_desktop_reading_queue.png")

        if page.locator('.reading-band-nav a[data-band="top_priority"]').count():
            page.evaluate("document.getElementById('bucket-top_priority')?.scrollIntoView({block:'start'})")
            page.wait_for_timeout(250)
            page.screenshot(path=str(out / "02_desktop_reading_top_priority.png"), full_page=False)
            copy_opt(out, "02_desktop_reading_top_priority.png")

        if page.locator('.reading-band-nav a[data-band="saved"]').count():
            page.evaluate("document.getElementById('bucket-saved')?.scrollIntoView({block:'start'})")
            page.wait_for_timeout(250)
            page.screenshot(path=str(out / "03_desktop_reading_saved.png"), full_page=False)
            copy_opt(out, "03_desktop_reading_saved.png")

        page.goto(f"{base}/queues/reading?show_completed=1", wait_until="domcontentloaded")
        page.screenshot(path=str(out / "04_desktop_reading_completed.png"), full_page=False)
        copy_opt(out, "04_desktop_reading_completed.png")

        # isolation
        page.goto(f"{base}/queues/monitoring", wait_until="domcontentloaded")
        assert page.locator('[data-pvs-slice="4"]').count() == 1
        assert page.locator('[data-pvs-slice="5"]').count() == 0
        page.goto(f"{base}/today", wait_until="domcontentloaded")
        assert page.locator('[data-pvs-slice="1"]').count() == 1
        assert page.locator('[data-pvs-slice="5"]').count() == 0

        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(f"{base}/queues/reading", wait_until="domcontentloaded")
        page.wait_for_selector('[data-pvs-slice="5"]')
        page.screenshot(path=str(out / "05_mobile_reading_queue.png"), full_page=False)
        copy_opt(out, "05_mobile_reading_queue.png")

        page.set_viewport_size({"width": 1280, "height": 720})
        page.goto(f"{base}/queues/reading", wait_until="domcontentloaded")
        page.wait_for_timeout(400)
        page.evaluate("document.getElementById('bucket-top_priority')?.scrollIntoView({block:'start'})")
        page.wait_for_timeout(400)
        page.evaluate("document.getElementById('bucket-backlog')?.scrollIntoView({block:'start'})")
        page.wait_for_timeout(400)
        page.goto(f"{base}/queues/reading?show_completed=1", wait_until="domcontentloaded")
        page.wait_for_timeout(500)

        video = Path(page.video.path()) if page.video else None
        context.close()
        browser.close()

        if video and video.exists():
            webm = out / "walkthrough.webm"
            shutil.move(str(video), str(webm))
            mp4 = out / "walkthrough.mp4"
            try:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        str(webm),
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        "-vf",
                        "scale=960:-2",
                        "-an",
                        "-movflags",
                        "+faststart",
                        str(mp4),
                    ],
                    check=True,
                    capture_output=True,
                )
                shutil.copy(mp4, OPT / "pvs-slice5-walkthrough.mp4")
                print("wrote", mp4)
            except Exception as exc:  # noqa: BLE001
                print("ffmpeg skipped", exc, file=sys.stderr)
            shutil.rmtree(out / "_video_raw", ignore_errors=True)

        (out / "browser-console.txt").write_text("\n".join(errors) if errors else "(no page/console errors)\n")
        print("errors", len(errors))
        print("ALL CAPTURES DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
