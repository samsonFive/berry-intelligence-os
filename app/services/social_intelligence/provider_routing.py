"""Task routing only; existing explicit job guards remain the execution boundary."""
from .adapters import AccessBlocked

VERSION = "social-provider-routing-1"

def route(source, task, *, already_captured=False):
    if task not in {"discovery", "detail"}:
        raise ValueError("Task must be discovery or detail")
    if source not in {"linkedin", "facebook", "instagram", "reddit", "tiktok", "x", "youtube", "pinterest"}:
        raise AccessBlocked("Platform has no measured routing policy")
    if already_captured and task == "discovery":
        return {"version": VERSION, "action": "reuse", "provider": None, "reason": "Reuse retained source identity; do not collect the same discovery twice"}
    if source == "linkedin" and task == "detail":
        return {"version": VERSION, "action": "manual-guarded-job", "provider": "apify", "actor": "harvestapi/linkedin-post-search", "max_items": 5, "max_charge_usd": 0.10, "reason": "Matched supplier sample returned richer post media; no discovery advantage demonstrated"}
    return {"version": VERSION, "action": "manual-guarded-request", "provider": "sociavault", "max_requests": 1, "reason": "Broad discovery or existing source-specific retrieval; fresh free access and retained reserve required"}
