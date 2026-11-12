"""Private, bidirectional research links; never writes into the Landscape registry."""
from app.services import landscape_workspace, living_workspaces as living

LIVE_INVESTIGATION_NOTICE = "Open this live investigation in Landscape; authored generation supports existing saved Landscape views."


def choices(main):
    rows = [{"id": "gene-editing", "title": "Gene Editing & Advanced Breeding · all 11 companies", "href": "/landscapes/explorer?topic=gene-editing&adjacent=1"}]
    rows.extend({"id": row["id"], "title": row["name"], "href": landscape_workspace.view_href(row)}
                for row in landscape_workspace.load_views(main.INBOX_DIR)["views"].values()
                if not row["archived"] and str((row.get("filters") or {}).get("ctx_v") or "") != "1")
    if main.AUTHORING_MODE:
        rows.extend({'id': row['id'], 'title': 'Saved competitive comparison · '+row['title'],
                     'href': '/competitive-evaluation?saved='+row['id']}
                    for row in living.Store(main.INBOX_DIR).rows('competitive_comparison'))
    return rows


def coverage_scope(page, landscapes):
    """Carry explicit page/comparison scope; never reinterpret geography as destination."""
    companies = set((page.get('feed') or {}).get('entity_ids') or [])
    berries = set((page.get('feed') or {}).get('berry_ids') or [])
    destinations = set()
    for row in landscapes:
        data = row.get('data') or {}
        scope = data.get('scope') or data.get('filters') or {}
        if scope.get('empty_cohort'):
            continue
        companies.update(str(scope.get('companies') or '').split(','))
        if scope.get('focus'):
            companies.add(scope['focus'])
        berries.update(str(scope.get('berry') or '').split(','))
        destination = scope.get('destination') or scope.get('destination_market') or ''
        if str(destination).startswith('geography-'):
            destinations.add(destination)
    companies = sorted(key for key in companies if key.startswith(('company-', 'brand-', 'program-', 'breeding_program-', 'retailer-', 'seed-org-')))
    berries = sorted(key for key in berries if key.startswith('berry-'))
    return {'companies': companies, 'berry': ','.join(berries),
            'destination_market': next(iter(destinations)) if len(destinations) == 1 else '',
            'empty_cohort': bool(landscapes) and not companies and not berries}


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
            saved = landscape_workspace.load_views(main.INBOX_DIR)["views"].get(key)
            if saved and not saved["archived"] and str((saved.get("filters") or {}).get("ctx_v") or "") == "1":
                raise ValueError(LIVE_INVESTIGATION_NOTICE)
            raise ValueError("Linked Landscape is unavailable or archived. Relink it before generating.")
        option = options[key]
        if key.startswith('comparison-'):
            saved = living.Store(main.INBOX_DIR).get(key)
            if not saved or 'snapshot' not in saved:
                raise ValueError('Saved comparison is unavailable')
            snapshot = saved['snapshot']
            data = {k: snapshot[k] for k in ('scope', 'assessments', 'captured_at')}
            data['narrative'] = saved.get('narrative', '')
            data['trust_effect'] = 'Immutable cited research snapshot; no publication or Atomic Evidence promotion'
            sources = {s['id']: {'id':s.get('article_id') or s['id'], 'title':s['fields'].get('title_original') or s['local_id'],
                                'source_url':s['fields']['original_url'], 'published_date':s['fields'].get('published_date'),
                                'status':'unreviewed', 'verification_state':s['verification']['status']}
                       for a in snapshot['assessments'] for s in a.get('sources', [])}
        elif key == "gene-editing":
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
            if view.get('surface') == 'watchlist':
                from app.services import global_watchlist
                from app.services import feed_first
                from app.services.watchlist import load_watches
                model = global_watchlist.build(entities=main.all_entities(), evidence=main.published_evidence(),
                    relationships=main.all_relationships(), signals=main.all_signals(), assessments=main.all_assessments(),
                    data_dir=main.DATA_DIR, store=living.Store(main.INBOX_DIR), watches=load_watches(main.INBOX_DIR),
                    params=landscape_workspace.watchlist_scope(view), sources=main.load_sources(),
                    tracking_state=feed_first.load_state(main.INBOX_DIR))
                data = {'filters': view['filters'], 'scope': {'companies': ','.join(row['id'] for row in model['rows']),
                    'berry': view['filters'].get('berry', ''),
                    'empty_cohort': bool(any(view['filters'].get(key) for key in ('favorites', 'company_tier', 'list'))) and not model['rows']},
                    'companies': [{field: row[field] for field in ('id', 'name', 'roles', 'tier', 'confidence', 'regions')} for row in model['rows']],
                    'coverage_note': model['data_note']}
                sources = {source['id']: source for group in model['news'] for source in group['sources']}
            elif view.get("kind") == "explorer":
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
