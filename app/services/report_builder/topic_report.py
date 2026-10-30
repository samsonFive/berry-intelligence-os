"""Topic evidence preview and deterministic, attributed report passages.

Public passages are kept on the private report, not exported to a model.
This preserves the existing Report Builder provider security boundary.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import hashlib
from pathlib import Path
from typing import Any

from app.services.report_builder.scope import ResolvedScope
from app.services.report_builder.synthesis import SectionDraft
from app.services.topic_discovery import discover_topic
from app.services.topic_retrieval import plan_query


def attach_topic_research(packet: dict[str, Any], scope: ResolvedScope, *, entities: dict, inbox_dir: Path) -> dict[str, Any]:
    if not scope.research_query:
        return packet
    plan = plan_query(scope.research_query, use_original=scope.use_original_query)
    if scope.date_window_days and not plan.start:
        plan = replace(plan, start=(date.today() - timedelta(days=scope.date_window_days)).isoformat(), end=date.today().isoformat())
    if scope.research_snapshot is not None:
        research = scope.research_snapshot
    else:
        from app.services.evidence_claim_review import trust_tier_label
        from app.services.topic_retrieval import record_passages
        local = [{key: row.get(key) for key in ("id", "title", "source_name", "source_url", "published_date", "passage", "passage_locator", "match_reason", "classification_evidence_ids", "relevance", "support_status", "source_review_hold")} | {"origin": "collected", "trust_class": trust_tier_label(row) if row.get("status") == "published" else "PENDING / UNREVIEWED"} for row in packet.get("topic_matches") or []]
        for snapshot, record in zip(local, packet.get("topic_matches") or []):
            text = "\n\n".join(p for loc, p in record_passages(record) if loc not in {"title", "summary", "snippet"})
            snapshot["source_version"] = hashlib.sha256(text.encode()).hexdigest() if text else None
            snapshot["source_version_basis"] = "stored_source_passages"
            snapshot["retrieved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        public_labels = [str(entities[eid].get("name") or "") for eid in (*scope.company_ids, *scope.variety_ids, *(g for g in scope.geography_ids if g not in scope.geography_descendant_ids)) if eid in entities]
        if scope.berry_id:
            public_labels.append(scope.berry_id.removeprefix("berry-"))
        required = [[str(name) for eid in ids if eid in entities for name in [entities[eid].get("name"), *(entities[eid].get("aliases") or [])] if name] for ids in (scope.geography_ids, scope.company_ids, scope.variety_ids) if ids]
        varieties = [str(e.get("name")) for e in entities.values() if e.get("entity_type") == "variety" and (not scope.berry_id or scope.berry_id in (e.get("berry_ids") or []))]
        web = discover_topic(plan, inbox_dir=inbox_dir, entities=entities, constraints={"public_labels": public_labels, "required_label_groups": required, "public_variety_names": varieties}) if scope.source_scope == "combined" else {"items": [], "status": "not_requested", "failures": [], "queries_this_request": 0}
        # Keep only the matched passage + identity/provenance on the report.
        web_rows = [{key: row.get(key) for key in ("id", "title", "source_name", "source_url", "published_date", "passage", "passage_locator", "match_reason", "classification_evidence_ids", "relevance", "provider", "retrieved_at", "capture_status", "capture_reason", "source_version", "support_status", "source_review_hold")} | {"origin": "web", "trust_class": "LIVE / UNREVIEWED"} for row in web.get("items") or []]
        from app.services.research_event_groups import event_groups
        groups = event_groups([*(packet.get('topic_matches') or []), *(web.get('items') or [])],entities)
        research = {"plan": plan.as_dict(), "source_scope": scope.source_scope, "retrieval_trace": packet.get("retrieval_trace"), "local": local, "web": web_rows, "discovery": {k: v for k, v in web.items() if k != "items"},
                    "event_groups":[{k:g[k] for k in ('id','member_ids','reason','label')} for g in groups if len(g['member_ids'])>1]}
    packet["topic_research"] = research
    from app.services.article_dedup import normalize_canonical_url
    rows = list(research.get("local") or [])
    identities = {normalize_canonical_url(r.get("source_url")) for r in rows if r.get("source_url")}
    rows.extend(r for r in research.get("web") or [] if normalize_canonical_url(r.get("source_url")) not in identities)
    from app.services.research_source_holds import source_quote_hold
    rows=[{**r,**({'source_review_hold':hold['reason']} if (hold:=source_quote_hold(r)) else {})} for r in rows]
    packet["topic_sources"] = rows
    packet["source_trace"] = [{**r, "href": r.get("source_url") or f"/evidence/{r['id']}", "date": r.get("published_date") or "", "date_basis": "published_date" if r.get("published_date") else "", "trust": r["trust_class"]} for r in rows]
    packet["known_ids"] = {r["id"] for r in rows}
    return packet


def topic_sections(packet: dict[str, Any], *, as_of: date | None = None) -> list[SectionDraft]:
    research = packet["topic_research"]
    plan = research["plan"]
    rows = packet.get("topic_sources") or []
    from app.services.research_source_holds import source_quote_hold
    held = [r for r in rows if r.get('source_review_hold') or source_quote_hold(r)]
    unverified = [r for r in rows if r.get('support_status')=='scope_unverified']
    supported = [r for r in rows if r not in held and r not in unverified and r.get("passage") and r.get("relevance") != "adjacent" and r.get("passage_locator") not in {"summary", "snippet", "title"} and (r["origin"] == "collected" or r.get("source_version"))]
    threshold = ((as_of or date.today()) - timedelta(days=365)).isoformat()
    recent = [r for r in supported if r.get("relevance") == "direct" and r.get("published_date") and (plan.get("start") or r["published_date"] >= threshold)]
    background = [r for r in supported if r not in recent and r.get("published_date")][:4]
    undated = [r for r in supported if not r.get("published_date")]
    def excerpts(items):
        return "\n\n".join(f"[{r['id']}] {r.get('source_name') or 'Source'} ({r.get('published_date') or 'publication date unknown'}) — source excerpt: “{r['passage']}”\n{r.get('source_url') or ''}" for r in items)
    prose = excerpts(recent)
    if not prose:
        prose = "No inspected, dated direct development supports the recent-findings section within this scope. Review discovery status, older context and undated leads separately; no unsupported narrative was generated."
    scope_text = f"Query: {plan['raw_query']}\nInterpretation: {plan['interpreted_query']}\nSources: {research['source_scope']}\nPublication window: {plan.get('start') or 'unrestricted'} to {plan.get('end') or 'present'}\nWeb discovery: {research['discovery']['status']}\nSource statements remain attributed; web discoveries are unreviewed. Recent developments and older context retain their original publication dates."
    sections = [SectionDraft("scope_method", "Research scope and coverage", scope_text, (), "structured", None, None), SectionDraft("topic_findings", "Attributed source findings — recent developments", prose, tuple(r["id"] for r in recent), "structured", None, None)]
    if background:
        sections.append(SectionDraft("topic_background", "Older developments and background", excerpts(background), tuple(r["id"] for r in background), "structured", None, None))
    if undated:
        sections.append(SectionDraft("topic_undated", "Sources requiring publication-date verification", "\n".join(f"[{r['id']}] {r.get('title')} — date unknown; inspect the source before treating this as a recent development." for r in undated), tuple(r["id"] for r in undated), "structured", None, None))
    if held or unverified:
        leads=list({r['id']:r for r in [*held,*unverified]}.values())
        text='\n'.join(f"[{r['id']}] {r.get('title')} — quotation withheld: {r.get('source_review_hold') or (source_quote_hold(r) or {}).get('reason') or 'The captured passage does not establish the requested identity, crop/cane or trial location.'}" for r in leads)
        sections.append(SectionDraft('topic_verification_leads','Sources requiring scope or claim verification',text,tuple(r['id'] for r in leads),'structured',None,None))
    groups = [g for g in research.get('event_groups',[]) if set(g['member_ids']) <= {r['id'] for r in rows}]
    if groups:
        text = '\n\n'.join('Related coverage: '+', '.join('['+i+']' for i in g['member_ids'])+'. '+g['reason']+'. Source independence is not established.' for g in groups)
        sections.append(SectionDraft('topic_related_coverage','Related source coverage',text,tuple(dict.fromkeys(i for g in groups for i in g['member_ids'])),'structured',None,None))
    return sections
