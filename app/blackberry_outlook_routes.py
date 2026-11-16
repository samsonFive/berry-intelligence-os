"""Private 2027 blackberry leadership view; source research stays in runtime."""
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.services import blackberry_global_outlook as outlook, feed_first
from app.services.clock import utc_today
from app.services.company_source_scope import source_reviewed

router = APIRouter()


@router.get(outlook.PATH, response_class=HTMLResponse)
def blackberry_outlook(request: Request):
    from app import main

    if not main.AUTHORING_MODE:
        raise HTTPException(404, "This research view is available in the private workspace.")
    try:
        data = outlook.load(main.INBOX_DIR)
        if data is None:
            raise HTTPException(404, "The global blackberry research package is not installed.")
        entities = main.entity_index()
        view = outlook.model(data, request.query_params, entities)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    # Unified storage is the current application contract; older deployed
    # versions retain their existing read adapter until their own cutover.
    information = getattr(main, "unified_information", None) or main.published_evidence
    records, total = outlook.related_news(information(), view, today=utc_today())
    state = feed_first.load_state(main.INBOX_DIR)
    cards = []
    for row in records:
        card = feed_first.present_item(row, entities_by_id=entities, state=state,
                                       filters=feed_first.parse_filters({"window": "", "crop": "blackberry"}))
        card.update(trusted=source_reviewed(row), source_reviewed=source_reviewed(row),
                    full_reader_href=f"/intelligence/{row['id']}?personal=1")
        cards.append(card)
    news_params = {"berry": "berry-blackberry", "window": "", "view": "all"}
    if view["selected_company"] and view["selected_company"].get("entity_id") in entities:
        news_params["company"] = view["selected_company"]["entity_id"]
    if view["selected_variety"]:
        news_params["q"] = view["selected_variety"]["name"]
    return main.templates.TemplateResponse(request=request, name="blackberry_outlook.html", context={
        **view, "cards": cards, "news_total": total, "authoring_mode": True,
        "news_href": "/today?" + urlencode(news_params), "tags": False, "scoped_news": True,
    }, headers={"Cache-Control": "private, no-store"})
