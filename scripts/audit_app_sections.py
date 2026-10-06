"""Read-render audit in an isolated empty runtime; never exercises live/action URLs.

Run from the repository root. Outputs only route status, headings and form metadata.
The operator's inbox is never opened. This checks rendering, not workflow correctness.
"""
from __future__ import annotations

import json
import os
import re
import socket
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RUNTIME = ROOT / "inbox" / "design-section-audit"
RUNTIME.mkdir(parents=True, exist_ok=True)
RUNTIME = Path(tempfile.mkdtemp(prefix="run-", dir=RUNTIME))
os.environ["BIOS_DATA_DIR"] = str(ROOT / "data")
os.environ["BIOS_INBOX_DIR"] = str(RUNTIME / "inbox")
os.environ["BIOS_REVIEW_STATE_DIR"] = str(RUNTIME / "review_state")
os.environ["BIOS_MODE"] = "readonly"
os.environ["ENABLE_SOURCE_POLLING"] = "false"
os.environ["BIOS_REMOTE_INTERACTIVE"] = "false"
os.environ["BIOS_BASIC_AUTH"] = "false"
os.environ["BIOS_PUBLICATION_REVIEW_REHEARSAL_UI"] = "0"

from html.parser import HTMLParser


class PageOutline(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.headings = []
        self.forms = []
        self.capture = ""
        self.parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"title", "h1", "h2"}:
            self.capture, self.parts = tag, []
        if tag == "form":
            self.forms.append({"method": attrs.get("method", "get").upper(), "action": attrs.get("action", "")})

    def handle_data(self, data):
        if self.capture:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == self.capture:
            value = " ".join(" ".join(self.parts).split())
            if tag == "title":
                self.title = value
            else:
                self.headings.append(value)
            self.capture = ""

from fastapi.testclient import TestClient
from app.main import app


def run():
    nav = (ROOT / "docs/v2/DESIGN-NAVIGATION-INVENTORY.md").read_text(encoding="utf-8")
    paths = list(dict.fromkeys(re.findall(r"\| `(/[^`]*)` \|", nav)))
    extras = [
        "/news", "/industry-pulse", "/research", "/radar", "/moves", "/whitespace",
        "/search", "/design-system", "/today?view=briefing", "/landscapes?view=feed",
        "/landscapes/berries/blueberry", "/entities/variety?view=compete",
        "/entities/variety?view=observations", "/entities/company/compare",
        "/entities/variety/compare", "/entities/company/company-planasa",
        "/entities/company/company-planasa?view=legacy",
        "/entities/company/company-planasa/portfolio", "/entities/variety/variety-zara",
        "/geographies/geography-peru", "/explorer/snapshot", "/reports/new",
        "/review-ops/publications", "/review-ops/session",
        "/facts/fact-agrovision-peru-scale",
    ]
    paths = list(dict.fromkeys(paths + extras))
    results = []
    blocked = []

    def no_network(*args, **kwargs):
        blocked.append("Outbound socket attempt blocked")
        raise RuntimeError("Network disabled for section audit")

    # TestClient uses an in-process transport, not a network connection.
    with TestClient(app, raise_server_exceptions=False, follow_redirects=False) as client:
        with patch.object(socket.socket, "connect", no_network):
            for path in paths:
                response = client.get(path)
                outline = PageOutline()
                outline.feed(response.text)
                row = {
                    "path": path, "mode": "readonly", "status": response.status_code,
                    "redirect": response.headers.get("location", ""),
                    "title": outline.title,
                    "headings": outline.headings[:18],
                    "forms": outline.forms,
                }
                results.append(row)
                print(response.status_code, path, flush=True)
        with patch("app.main.AUTHORING_MODE", True), patch.object(socket.socket, "connect", no_network):
            for path in ["/varieties/candidates", "/entities/identity", "/coverage-assurance", "/industry-pulse"]:
                response=client.get(path)
                outline=PageOutline()
                outline.feed(response.text)
                results.append({"path":path,"mode":"authoring (isolated)","status":response.status_code,"redirect":response.headers.get("location", ""),"title":outline.title,"headings":outline.headings[:18],"forms":outline.forms})
                print(response.status_code, path, "authoring", flush=True)
    output = {
        "date": "2026-09-30", "mode": "readonly; committed data; isolated empty inbox; outbound sockets blocked",
        "limits": "Render smoke check only. No live providers, user runtime, action submissions, export binaries or authenticated deployment tested. Empty private queues are expected, not evidence of abandoned features.",
        "blocked_network_attempts": len(blocked), "results": results,
    }
    target = ROOT / "artifacts/design-sprint/section-render-audit.json"
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Saved", len(results), "route variants; blocked network attempts:", len(blocked), flush=True)


if __name__ == "__main__":
    run()
