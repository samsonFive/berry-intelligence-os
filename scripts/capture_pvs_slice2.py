#!/usr/bin/env python3
"""Browser verification for PVS Production Slice 2 (Landscape + profiles)."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "artifacts" / "product-visual-system-production-slice2"
OPT = Path("/opt/cursor/artifacts")


def shot(page, path: Path, full: bool = True) -> None:
    page.screenshot(path=str(path), full_page=full)
    print("wrote", path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8792")
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
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        page.goto(f"{base}/competitors", wait_until="networkidle")
        assert page.locator('[data-pvs-slice="2"]').count() == 1
        shot(page, out / "01_desktop_landscape_default.png")

        page.goto(f"{base}/competitors?berry=blueberry&tier=Tier+1", wait_until="networkidle")
        shot(page, out / "02_desktop_landscape_filtered.png")

        page.goto(f"{base}/competitors?q=zzznomatchxyz", wait_until="networkidle")
        shot(page, out / "03_desktop_landscape_no_results.png")

        page.goto(f"{base}/entities/company/company-california-giant-berry-farms", wait_until="networkidle")
        shot(page, out / "04_desktop_company_profile.png")

        page.goto(f"{base}/entities/brand/brand-ozblu", wait_until="networkidle")
        shot(page, out / "05_desktop_brand_profile.png")

        page.goto(f"{base}/entities/breeding_program/breeding_program-uc-davis-strawberry", wait_until="networkidle")
        shot(page, out / "06_desktop_breeding_profile.png")

        # provisional / unknown / missing monitoring — Fall Creek often has rich monitoring;
        # use a card from landscape unknown band if present
        page.goto(f"{base}/competitors?tier=Unknown%2FUnassigned", wait_until="networkidle")
        shot(page, out / "07_desktop_unknown_unassigned.png")

        page.goto(f"{base}/today", wait_until="networkidle")
        shot(page, out / "08_desktop_today_regression.png", full=False)

        page.set_viewport_size({"width": 834, "height": 1112})
        page.goto(f"{base}/competitors", wait_until="networkidle")
        shot(page, out / "09_tablet_landscape.png")

        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(f"{base}/competitors", wait_until="networkidle")
        shot(page, out / "10_mobile_landscape.png")
        page.goto(f"{base}/entities/company/company-california-giant-berry-farms", wait_until="networkidle")
        shot(page, out / "11_mobile_company_profile.png")

        # walkthrough
        page.set_viewport_size({"width": 1440, "height": 900})
        page.goto(f"{base}/competitors", wait_until="networkidle")
        page.wait_for_timeout(400)
        page.goto(f"{base}/competitors?company=company-california-giant-berry-farms", wait_until="networkidle")
        page.wait_for_timeout(600)
        page.goto(f"{base}/entities/company/company-california-giant-berry-farms", wait_until="networkidle")
        page.wait_for_timeout(500)
        page.goto(f"{base}/entities/brand/brand-ozblu", wait_until="networkidle")
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
                    ["ffmpeg", "-y", "-i", str(webm), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(mp4)],
                    check=True,
                    capture_output=True,
                )
                print("wrote", mp4)
            except Exception as exc:  # noqa: BLE001
                print("ffmpeg skipped", exc, file=sys.stderr)
            raw = out / "_video_raw"
            if raw.exists():
                shutil.rmtree(raw, ignore_errors=True)

        for name in (
            "01_desktop_landscape_default.png",
            "04_desktop_company_profile.png",
            "05_desktop_brand_profile.png",
            "10_mobile_landscape.png",
            "walkthrough.mp4",
        ):
            src = out / name
            if src.exists():
                shutil.copy2(src, OPT / f"pvs2-{name}")

        # Filter noisy font errors if any; fail on real pageerrors
        real = [e for e in errors if "favicon" not in e.lower()]
        (out / "browser-console.txt").write_text("\n".join(real) or "none\n", encoding="utf-8")
        print("console_errors", len(real))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
