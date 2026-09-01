"""Lightweight stakeholder screenshot harness. Not a full visual-regression suite."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:18082"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("inbox/stakeholder-frontend-qa")
VIEWPORTS = {
    "1440": {"width": 1440, "height": 900},
    "1366": {"width": 1366, "height": 768},
    "768": {"width": 768, "height": 1024},
}
PAGES = [
    ("today", "/today"),
    ("search_planasa", "/search?q=Planasa"),
    ("company_planasa", "/entities/company/company-planasa"),
    ("variety_sekoya", "/entities/variety/variety-sekoya-grande"),
    ("geography_europe", "/geographies/geography-europe"),
    ("reports", "/reports"),
]


def inspect(page) -> dict:
    return page.evaluate(
        """() => {
      const doc = document.documentElement;
      const body = document.body;
      const overflowX = Math.max(doc.scrollWidth, body.scrollWidth) > doc.clientWidth + 2;
      const berryLinks = [...document.querySelectorAll('.today-berries a')].map((a) => ({
        text: (a.innerText || '').trim(),
        width: a.getBoundingClientRect().width,
      }));
      const raw = (document.body.innerText || '').match(
        /no_canonical_identity_match|genetics_licensor|elapsed_ms|wall-clock-naive/gi
      ) || [];
      const firstCompany = (() => {
        const group = document.querySelector('[data-search-group="companies"]');
        if (!group) return '';
        const title = group.querySelector('.sh-search-title, .v2-search-title');
        return title ? title.textContent.trim() : '';
      })();
      return {
        title: document.title,
        h1: (document.querySelector('h1') || {}).innerText || '',
        overflowX,
        navCount: document.querySelectorAll('.sh-nav-desktop a').length,
        opsBadges: document.querySelectorAll('.v2-count-action').length,
        berryLinks,
        raw,
        firstCompany,
      };
    }"""
    )


def main() -> None:
    shots = OUT / "shots"
    shots.mkdir(parents=True, exist_ok=True)
    rows = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context()
        page = context.new_page()
        page.goto(f"{BASE}/login", wait_until="networkidle")
        if page.locator("#username").count():
            page.fill("#username", "audit")
            page.fill("#password", "audit-local-only")
            page.click("button[type=submit]")
            page.wait_for_load_state("networkidle")
        for name, path in PAGES:
            for vp_name, vp in VIEWPORTS.items():
                page.set_viewport_size(vp)
                page.goto(f"{BASE}{path}", wait_until="networkidle")
                metrics = inspect(page)
                shot = shots / f"{name}-{vp_name}.png"
                page.screenshot(path=str(shot), full_page=True)
                rows.append({"page": name, "viewport": vp_name, "shot": str(shot), **metrics})
        browser.close()
    (OUT / "metrics.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(json.dumps({"count": len(rows), "out": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
