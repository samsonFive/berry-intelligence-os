import pytest
from app.services.social_intelligence.provider_routing import route
from app.services.social_intelligence.adapters import AccessBlocked

def test_linkedin_detail_selects_only_tested_actor():
    result = route("linkedin", "detail")
    assert result["provider"] == "apify"
    assert result["actor"] == "harvestapi/linkedin-post-search"
    assert result["max_charge_usd"] == .1
    assert result["max_items"] == 5

def test_discovery_and_cached_identity_avoid_dual_collection():
    for source in ["linkedin", "facebook", "instagram", "reddit", "tiktok", "x", "youtube", "pinterest"]:
        assert route(source, "discovery")["provider"] == "sociavault"
        assert route(source, "discovery", already_captured=True)["action"] == "reuse"
    assert route("x", "detail")["provider"] != "apify"

def test_unknown_routes_fail_closed():
    with pytest.raises(AccessBlocked): route("weibo", "discovery")
    with pytest.raises(ValueError): route("linkedin", "schedule")
