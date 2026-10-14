"""Warm read-only News metadata decisions before the live server accepts users."""
import logging


def warm_news_cache():
    from app.personal_digest_routes import world
    from app.services import news_workspace
    try:
        main, context, records, entities = world()
        news_workspace.model(records=records, entities=entities, relationships=main.all_relationships(),
                             facts=main.all_facts(), state=context["state"], params={})
    except Exception:
        # Optional performance work must never prevent login or health checks.
        logging.getLogger(__name__).warning("News cache warm-up unavailable; the first request will load normally.")
