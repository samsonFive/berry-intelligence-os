"""Isolated, authenticated local preview using already acquired gene research.

No acquisition, paid research, publication or production writes. The example
hypothesis exists only in this explicitly named preview inbox.
"""
from pathlib import Path
import argparse
import json
import os
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def seed(research_inbox: Path, preview_inbox: Path):
    from app.services.living_workspaces import Store, compose_brief
    store = Store(preview_inbox)
    # One-time, explicitly requested roster repair. Later user scope edits survive restart.
    roster = json.loads((ROOT / 'data/imports/gene-editing-2026-10-20/snapshot.json').read_text(encoding='utf-8'))
    company_ids = [row['entity_id'] for row in roster['companies']]
    if len(set(company_ids)) != 11:
        raise SystemExit('Expected the original eleven-company roster')
    with store.transaction() as db:
        page = store.get('wp-gene-preview', db)
        if page and not store.get('setup-gene-roster-v2', db):
            page['feed']['entity_ids'] = list(dict.fromkeys([key for key in page['feed'].get('entity_ids', []) if key != 'company-ohalo-genetics'] + company_ids))
            page['landscape_links'] = list(dict.fromkeys(page.get('landscape_links', []) + ['gene-editing']))
            store.put(db, 'page', page, 'approved eleven-company preview scope', page['version'])
            store.put(db, 'setup', {'id': 'setup-gene-roster-v2', 'company_ids': company_ids}, 'preview setup')
    # Bring over the original private research sources, never overwrite later review.
    aliases_path = research_inbox / 'gene_editing/evidence_aliases.json'
    aliases = json.loads(aliases_path.read_text(encoding='utf-8')) if aliases_path.exists() else {}
    evidence_ids = {key for row in roster['companies'] for key in row.get('evidence_ids', [])}
    evidence_ids.update(key for row in roster['programs'] for key in row.get('evidence_ids', []))
    for key in evidence_ids:
        source = research_inbox / 'evidence' / (aliases.get(key, key) + '.json')
        target = preview_inbox / 'evidence' / source.name
        if source.exists() and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
    if aliases:
        target = preview_inbox / 'gene_editing/evidence_aliases.json'
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(aliases), encoding='utf-8')
    if any(b["type"] == "briefing" for b in (store.get("wp-gene-preview") or {}).get("blocks", [])):
        return "wp-gene-preview"
    entities = {}
    for file in (ROOT / "data/entities").rglob("*.json"):
        record = json.loads(file.read_text(encoding="utf-8"))
        if isinstance(record, dict) and record.get("id"):
            entities[record["id"]] = record
    folder = preview_inbox / "evidence"
    folder.mkdir(parents=True, exist_ok=True)
    selected = []
    for name in ("pairwise-hrb", "simplot-alliance", "ohalo-launch"):
        original = research_inbox / "evidence" / ("ev-gene-" + name + ".json")
        html = research_inbox / "gene-editing-captures" / (name + ".html")
        if not original.exists() or not html.exists():
            raise SystemExit("Archived gene research required: " + str(original) + " and " + str(html))
        record = json.loads(original.read_text(encoding="utf-8"))
        # Reuse permitted acquisition parsing on archived original HTML, without
        # its network path. No shortened mission excerpt is called a full article.
        text = (research_inbox / "gene-editing-captures" / (name + ".txt")).read_text(encoding="utf-8").strip()
        if len(text) < 1000:
            raise SystemExit("Archived source has insufficient readable text: " + name)
        record["article"] = {"full_text": text, "completeness": "full", "acquisition": {"method": "previously-acquired publisher readable text", "captured_date": "2026-10-21"}}
        record["preview_context"] = "isolated living workspace review"
        target = folder / (record["id"] + ".json")
        if not target.exists():
            target.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        selected.append((record, store.snapshot(record, text, "body_available")))
    with store.transaction() as db:
        if not store.get("wp-gene-preview", db):
            store.put(db, "page", {"id": "wp-gene-preview", "title": "Gene Editing & Advanced Breeding", "parent_id": None, "blocks": [store.block("callout", "ISOLATED REVIEW PREVIEW · Public source claims remain unverified. Watchlist membership does not establish an editing program. Earlier 11-company deep research still has documented gaps.")], "feed": {"mode": "any", "paused": False, "entity_ids": company_ids}, "landscape_links": ["gene-editing"], "dismissed": []}, "preview setup")
    store.flush()
    first = selected[0]
    record, source = first
    store.capture({"token": "preview-full-article-v1", "page_id": "wp-gene-preview", "kind": "article", "quote": ""}, source, "preview setup", entities)
    for index, (record, source) in enumerate(selected):
        # Reuse exact supporting excerpts if they occur in the archived text.
        quote = record.get("supporting_excerpt", "")
        if not quote or quote not in source["text"]:
            marker = "have signed a licensing agreement" if index == 0 else ""
            start = source["text"].find(marker) if marker else 0
            start = max(0, start)
            quote = source["text"][start:start+240]
        start = source["text"].index(quote)
        store.capture({"token": f"preview-passage-{index}-v1", "page_id": "wp-gene-preview", "kind": "statement", "quote": quote, "locator": {"start": start}, "text": record["summary"], "entity_ids": record.get("entity_ids", [])}, source, "preview setup", entities)
    quote = source["text"][:180]
    # Licensed platform relationship is supported by the preserved Pairwise release.
    record, source = first
    start = source["text"].find("have signed a licensing agreement")
    start = max(0, start)
    quote = source["text"][start:start+350]
    store.capture({"token": "preview-relationship-v1", "page_id": "wp-gene-preview", "kind": "relationship", "quote": quote, "locator": {"start": start}, "text": "The issuer reports Hudson River licensing access to Pairwise's Fulcrum platform.", "allowed_predicates": ["licenses"], "relation": {"subject_id": "company-hudson-river-biotechnology", "object_id": "company-pairwise", "predicate": "licenses", "nature": "source_statement", "scope": "Fulcrum editing platform; not proof of a commercial berry variety"}}, source, "preview setup", entities)
    store.capture({"token": "preview-hypothesis-v1", "page_id": "wp-gene-preview", "kind": "relationship", "quote": quote, "locator": {"start": start}, "text": "DEMONSTRATION ONLY: Could the licensed platform lead to additional joint berry research? This is a question, not an asserted partnership.", "note": "Synthetic analyst question in isolated preview. No business relationship is established by this hypothesis.", "allowed_predicates": ["partners_with"], "relation": {"subject_id": "company-hudson-river-biotechnology", "object_id": "company-pairwise", "predicate": "partners_with", "nature": "analyst_hypothesis", "scope": "DEMONSTRATION ONLY"}}, source, "preview setup", entities)
    child = store.create_page("Source questions & unresolved gaps", "wp-gene-preview", "preview setup", "preview-child-page-v1")
    page = store.get("wp-gene-preview")
    page["blocks"].extend([store.block("table", rows=[["Company / platform", "Issuer statement", "Limits"], ["Pairwise / Hudson River", "Fulcrum platform license", "Source-stated; not independent corroboration"], ["Simplot / PSI", "Strawberry research alliance", "Announcement does not establish current sales"], ["Ohalo", "Strawberry consortium", "Advanced breeding is not automatically CRISPR"]]), store.block("entity", entity_id="company-pairwise"), store.block("page", page_id=child["id"]), store.block("map"), store.block("feed")])
    page["blocks"].append(compose_brief(page, {i["id"]: i for i in store.rows("item")}, {s["id"]: s for s in store.rows("source")}, []))
    store.save_page(page["id"], page, "preview setup")
    return page["id"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research-inbox", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18773)
    args = parser.parse_args()
    preview = ROOT / "inbox/living-preview-v2"
    page_id = seed(args.research_inbox.resolve(), preview)
    secret_path = preview / ".session-secret"
    if not secret_path.exists():
        secret_path.write_text(secrets.token_hex(32), encoding="utf-8")
    os.environ.update(BIOS_INBOX_DIR=str(preview), BIOS_MODE="authoring", ENABLE_SOURCE_POLLING="false", BIOS_REMOTE_INTERACTIVE="true", BIOS_REVIEW_USERNAME="local-preview", BIOS_REVIEW_PASSWORD="local-workspace-review", BIOS_SESSION_SECRET=secret_path.read_text(encoding="utf-8").strip())
    # Preview-only credentials, never copied from production. Access instructions
    # stay in ignored local runtime rather than committed documentation.
    (preview / "preview-access.txt").write_text("Username: local-preview\nPassword: local-workspace-review\n", encoding="utf-8")
    import uvicorn
    from app import main
    # Warmup need not poll or load the news universe for an isolated document QA.
    import app.services.news_warmup
    app.services.news_warmup.warm_news_cache = lambda: None
    print(f"Living workspace preview: http://127.0.0.1:{args.port}/workspaces/{page_id}")
    uvicorn.run(main.app, host="127.0.0.1", port=args.port)
