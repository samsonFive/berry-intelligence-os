"""Generate one local repair-verification report with all model calls disabled."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient
from app import main

# This override exists only in this verification process, never in production.
main.maybe_untrusted_completer = lambda: None
assert main.INBOX_DIR.resolve().is_relative_to(ROOT)
client = TestClient(main.app)
response = client.post("/reports/new", data={
    "step": "generate", "report_type": "competitive_landscape",
    "company_ids": "company-california-giant-berry-farms", "date_window_days": "90",
    "title": "California Giant — local coverage verification",
}, follow_redirects=False)
assert response.status_code == 303, response.status_code
route = response.headers["location"]
page = client.get(route)
assert page.status_code == 200
assert "All captured company reporting" in page.text
assert "analyst-reviewed" not in page.text
pdf = client.get(route + "/export.pdf")
assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
out = Path(__file__).parent
(out / "calgiant-local-report.pdf").write_bytes(pdf.content)
(out / "local-report-verification.json").write_text(json.dumps({
    "route": route, "model_calls": 0, "workspace_status": page.status_code,
    "pdf_status": pdf.status_code, "scope": "Local checked-in corpus; not production",
}, indent=2) + "\n", encoding="utf-8")
print(route)
