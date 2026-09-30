"""Local-only design preview with on-demand article reading; no persisted captures."""
from __future__ import annotations

import json
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.article_acquisition import ArticleAcquisitionError, fetch_article

STUDIO = ROOT / "artifacts" / "design-sprint"
RECORDS = {r["id"]: r for r in json.loads((STUDIO / "content.json").read_text(encoding="utf-8"))["records"]}
CACHE: dict[str, dict] = {}
LOCKS = {key: threading.Lock() for key in RECORDS}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STUDIO), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def send_json(self, status, value):
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        request = urlparse(self.path)
        if request.path != "/__reader/article":
            return super().do_GET()
        # Only the fixed public sample URLs can be fetched; never accept a supplied URL.
        if self.headers.get("Host") not in {"127.0.0.1:18322", "localhost:18322"} or self.headers.get("Sec-Fetch-Site") == "cross-site":
            return self.send_json(403, {"state": "unavailable"})
        item_id = parse_qs(request.query).get("id", [""])[0]
        record = RECORDS.get(item_id)
        if not record:
            return self.send_json(404, {"state": "unavailable", "reason": "not-in-preview"})
        with LOCKS[item_id]:
            if item_id not in CACHE:
                try:
                    article = fetch_article(record["url"], timeout=12)
                    CACHE[item_id] = {
                        "state": "available", "paragraphs": [p.text for p in article.paragraphs],
                        "author": article.author or "", "url": record["url"],
                        "fetched_at": article.fetched_at,
                    }
                except ArticleAcquisitionError as exc:
                    return self.send_json(200, {"state": "unavailable", "reason": exc.category})
                except Exception:
                    return self.send_json(200, {"state": "unavailable", "reason": "reader-unavailable"})
            self.send_json(200, CACHE[item_id])


if __name__ == "__main__":
    print("Berry design preview: http://127.0.0.1:18322/", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 18322), Handler).serve_forever()
