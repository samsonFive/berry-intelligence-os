"""Private, bidirectional research links; never writes into the Landscape registry."""
from app.services import landscape_workspace, living_workspaces as living


def choices(main):
    rows = [{"id": "gene-editing", "title": "Gene Editing & Advanced Breeding · all 11 companies", "href": "/landscapes/explorer?topic=gene-editing&adjacent=1"}]
    rows.extend({"id": row["id"], "title": row["name"], "href": landscape_workspace.view_href(row)}
                for row in landscape_workspace.load_views(main.INBOX_DIR)["views"].values() if not row["archived"])
    return rows


def backlinks(main, key):
    if not main.AUTHORING_MODE or not key:
        return []
    return [{"id": row["id"], "title": row["title"], "updated_at": row.get("content_updated_at", row.get("updated_at")),
             "summary": (row.get("overview") or {}).get("text", ""),
             "generated_at": (row.get("overview") or {}).get("generated_at"),
             "combined": any(ref["id"] == key for ref in (row.get("overview") or {}).get("landscape_versions", [])),
             "notes": [b.get("text", "") for b in row["blocks"] if b["type"] in {"paragraph", "note", "callout", "hypothesis"} and b.get("text")],
             "captures": sum(bool(b.get("item_id")) for b in row["blocks"])}
            for row in living.Store(main.INBOX_DIR).rows("page") if key in row.get("landscape_links", [])]


def panel(main, key):
    linked = backlinks(main, key)
    return {"linked_workspaces": linked, "landscape_link_key": key if main.AUTHORING_MODE else "",
            "linkable_workspaces": [{"id": row["id"], "title": row["title"]} for row in living.Store(main.INBOX_DIR).rows("page")
                                    if row["id"] not in {page["id"] for page in linked}] if main.AUTHORING_MODE and key else []}


def resolve(main, request, keys):
    options = {row["id"]: row for row in choices(main)}
    result = []
    for key in keys:
        if key not in options:
            raise ValueError("Linked Landscape is unavailable or archived. Relink it before generating.")
        option = options[key]
        if key == "gene-editing":
            from app.landscape_explorer_routes import context
            _, _, bundle, _, _ = context(request, {"topic": "gene-editing", "adjacent": "1"})
            model = bundle["gene_editing"]
            fields = ("entity_id", "name", "summary", "editing_status", "identity_notes", "gaps", "evidence_ids")
            data = {"companies": [{k: row.get(k) for k in fields} for row in model["companies"]],
                    "programs": [{k: v for k, v in row.items() if k != "sources"} for row in model["programs"]],
                    "relationships": [{k: v for k, v in row.items() if k != "sources"} for row in model["relationships"]],
                    "research_status": model["research_status"], "counts": model["counts"]}
            sources = {s["id"]: s for c in model["companies"] for s in c["sources"]}
        else:
            view = landscape_workspace.load_views(main.INBOX_DIR)["views"][key]
            if view.get("kind") == "explorer":
                from app.landscape_explorer_routes import context
                _, _, bundle, _, _ = context(request, {"saved_view": key})
                data = {"filters": bundle["filters"], "nodes": bundle["nodes"], "edges": bundle["edges"]}
                sources = {row["id"]: row for row in bundle["sources"]}
            else:
                from app.landscape_routes import context
                _, model, _, _, _ = context({**view["filters"], "configured": "1"})
                data = {"filters": model["filters"], "panels": {k: v for k, v in model["panels"].items() if k != "sources"}}
                sources = {row["id"]: row for row in model["panels"]["sources"]}
        data["sources"] = [{k: row.get(k) for k in ("id", "title", "source_url", "published_date", "verification_state", "status", "summary", "supporting_excerpt")} for row in sources.values()]
        result.append({**option, "basis": living.digest(data), "data": data})
    return result


def add_summary_context(block, items, landscapes):
    """Cited Landscape context is ephemeral, never a captured or trusted claim."""
    for landscape in landscapes:
        key = "landscape-" + landscape["id"]
        text = living.encoded(landscape["data"])
        items[key] = {"id": key, "nature": "landscape_context", "kind": "landscape", "quote": "", "text": text,
                      "note": "Landscape context, not independent corroboration. Preserve gaps and review status; membership proves no capability.", "version": landscape["basis"]}
        ref = {"number": len(block["citations"]) + 1, "item_id": key, "source_id": key, "title": landscape["title"],
               "url": landscape["href"], "quote": "", "kind": "landscape", "basis": landscape["basis"]}
        block["citations"].append(ref)
        companies = landscape["data"].get("companies", landscape["data"].get("panels", {}).get("companies", []))
        names = ", ".join(row.get("name", row.get("entity_id", row.get("id", "Unknown"))) for row in companies)
        block["text"] += "\n\n## Linked Landscape\n" + landscape["title"] + " [" + str(ref["number"]) + "]\n" + ("Company scope: " + names + ". " if names else "") + "Landscape programs, source references, review states and gaps are available through the linked view; membership alone establishes no capability."
    block["landscape_versions"] = [{"id": row["id"], "basis": row["basis"]} for row in landscapes]
    return block
