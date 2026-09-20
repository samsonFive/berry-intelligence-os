"""Dashboard secret slugs alias to canonical repo env names.

Never invent keys. Tests use dummy tokens only — not live secrets.
"""

from __future__ import annotations

from app.services.industry_pulse.apitube import ApiTubeSearchProvider
from app.services.industry_pulse.credentials import (
    apitube_key,
    catchall_key,
    exa_key,
    has_apitube,
    has_catchall,
    has_exa,
    has_perplexity,
)
from app.services.industry_pulse.errors import ProviderAuthError
from app.services.industry_pulse.exa import ExaSearchProvider
from app.services.industry_pulse.matrix import PulseQuery


def _query() -> PulseQuery:
    return PulseQuery(
        id="alias:test",
        text="blueberry harvest",
        berry="blueberry",
        geography="global",
        topic="industry_pulse",
        kind="today_berry",
        hl="en-US",
        gl="US",
        ceid="US:en",
    )


def test_dashboard_aliases_unlock_has_flags(monkeypatch):
    for name in (
        "EXA_API_KEY",
        "exa_api",
        "APITUBE_API_KEY",
        "apitube",
        "NEWSCATCHER_API_KEY",
        "CATCHALL_API_KEY",
        "newscatcher_events_api",
    ):
        monkeypatch.delenv(name, raising=False)

    assert has_exa() is False
    assert has_apitube() is False
    assert has_catchall() is False

    monkeypatch.setenv("exa_api", "dummy-exa-alias")
    monkeypatch.setenv("apitube", "dummy-apitube-alias")
    monkeypatch.setenv("newscatcher_events_api", "dummy-newscatcher-alias")

    assert has_exa() is True
    assert has_apitube() is True
    assert has_catchall() is True
    assert exa_key() == "dummy-exa-alias"
    assert apitube_key() == "dummy-apitube-alias"
    assert catchall_key() == "dummy-newscatcher-alias"


def test_canonical_names_win_over_dashboard_aliases(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "dummy-exa-canonical")
    monkeypatch.setenv("exa_api", "dummy-exa-alias")
    monkeypatch.setenv("APITUBE_API_KEY", "dummy-apitube-canonical")
    monkeypatch.setenv("apitube", "dummy-apitube-alias")
    monkeypatch.setenv("NEWSCATCHER_API_KEY", "dummy-newscatcher-canonical")
    monkeypatch.setenv("newscatcher_events_api", "dummy-newscatcher-alias")

    assert exa_key() == "dummy-exa-canonical"
    assert apitube_key() == "dummy-apitube-canonical"
    assert catchall_key() == "dummy-newscatcher-canonical"


def test_providers_refuse_when_neither_canonical_nor_alias_is_set(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    monkeypatch.delenv("exa_api", raising=False)
    monkeypatch.delenv("APITUBE_API_KEY", raising=False)
    monkeypatch.delenv("apitube", raising=False)
    try:
        ExaSearchProvider().discover(_query())
        raise AssertionError("exa should refuse")
    except ProviderAuthError as exc:
        assert "EXA_API_KEY" in str(exc)
    try:
        ApiTubeSearchProvider().discover(_query())
        raise AssertionError("apitube should refuse")
    except ProviderAuthError as exc:
        assert "APITUBE_API_KEY" in str(exc)


def test_perplexity_canonical_name_is_unchanged(monkeypatch):
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    assert has_perplexity() is False
    monkeypatch.setenv("PERPLEXITY_API_KEY", "dummy-perplexity")
    assert has_perplexity() is True
