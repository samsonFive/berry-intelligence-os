"""Warm read-only News metadata before serving; other workspaces load on demand."""
import logging


def warm_news_cache():
    from app.personal_digest_routes import world
    from app.services import news_workspace
    try:
        main, context, records, entities = world()
        news_workspace.model(records=records, entities=entities, relationships=main.all_relationships(),
                             facts=main.all_facts(), state=context["state"], params={})
        # Keep the daily entry point ready without holding login/health behind
        # unrelated variety matching, briefing or publication-review work.
        # Those workspaces retain their existing on-demand loaders and caches.
        # No collection, review action or seen-state change runs here.
    except Exception:
        # Optional performance work must never prevent login or health checks.
        logging.getLogger(__name__).warning("News cache warm-up unavailable; the first request will load normally.")
