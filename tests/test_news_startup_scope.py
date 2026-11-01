"""News readiness must not depend on unrelated analyst-workspace preparation."""
import asyncio
from types import SimpleNamespace

import pytest

from app import main, personal_digest_routes
from app.runtime_config import RemoteInteractiveMisconfigured
from app.services import news_workspace
from app.services.news_warmup import warm_news_cache


def install_news_fixture(monkeypatch):
    calls = []
    records = {'story': {'id': 'story', 'title': 'Fixture source metadata'}}
    entities = {'company': {'id': 'company', 'name': 'Fixture company'}}
    relationships = [{'id': 'fixture-relationship'}]
    facts = [{'id': 'fixture-reviewed-statement'}]
    state = {'company_lists': [{'id': 'shared-fixture-list'}]}
    monkeypatch.setattr(main, 'all_relationships', lambda: relationships)
    monkeypatch.setattr(main, 'all_facts', lambda: facts)
    monkeypatch.setattr(main, 'variety_candidate_universe',
                        lambda: pytest.fail('News startup must not prepare variety matching'))
    monkeypatch.setattr(main, '_assemble_morning_brief',
                        lambda **kwargs: pytest.fail('News startup must not prepare another briefing'))
    from app.services import review_workbench
    monkeypatch.setattr(review_workbench, 'load_publication_transcript_readiness',
                        lambda *args: pytest.fail('News startup must not prepare publication review'))

    def world():
        calls.append('world')
        return main, {'state': state}, records, entities

    def model(**kwargs):
        calls.append(kwargs)
        return {'fixture': True}

    monkeypatch.setattr(personal_digest_routes, 'world', world)
    monkeypatch.setattr(news_workspace, 'model', model)
    expected = dict(records=records, entities=entities, relationships=relationships,
                    facts=facts, state=state, params={})
    return calls, expected


def test_news_warmup_keeps_exact_news_inputs_without_specialist_dependencies(monkeypatch):
    calls, expected = install_news_fixture(monkeypatch)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    warm_news_cache()
    assert calls == ['world', expected]


def test_optional_news_failure_does_not_expose_exception_details_or_prevent_startup(monkeypatch, caplog):
    install_news_fixture(monkeypatch)

    def unavailable():
        raise RuntimeError('fixture private diagnostic detail')

    monkeypatch.setattr(personal_digest_routes, 'world', unavailable)
    warm_news_cache()
    assert 'News cache warm-up unavailable' in caplog.text
    assert 'fixture private diagnostic detail' not in caplog.text


def test_real_lifespan_warms_news_after_auth_validation_without_specialist_work(monkeypatch, tmp_path):
    calls, expected = install_news_fixture(monkeypatch)
    # Exercise the real production startup branch without modifying Python's
    # global module registry or actually starting source polling or a server.
    monkeypatch.setattr(main, 'sys', SimpleNamespace(modules={}))
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    monkeypatch.setattr(main, 'SOURCE_POLLING_ENABLED', False)
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path / 'inbox')
    monkeypatch.setenv('BIOS_REMOTE_INTERACTIVE', 'true')
    monkeypatch.setenv('BIOS_REVIEW_USERNAME', 'fixture-startup')
    monkeypatch.setenv('BIOS_REVIEW_PASSWORD', 'fixture-startup-only')
    monkeypatch.setenv('BIOS_SESSION_SECRET', 'fixture-startup-secret-at-least-32-characters')
    validate = main.validate_remote_interactive_config

    def validated():
        validate()
        calls.append('auth_validated')

    monkeypatch.setattr(main, 'validate_remote_interactive_config', validated)

    async def boot():
        async with main.lifespan(main.app):
            assert calls == ['auth_validated', 'world', expected]

    asyncio.run(boot())
    assert (tmp_path / 'inbox/evidence').is_dir()


def test_misconfigured_remote_startup_still_fails_before_warmup_or_directory_writes(monkeypatch, tmp_path):
    calls, _ = install_news_fixture(monkeypatch)
    monkeypatch.setattr(main, 'sys', SimpleNamespace(modules={}))
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    monkeypatch.setattr(main, 'SOURCE_POLLING_ENABLED', False)
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path / 'must-not-exist')
    monkeypatch.setenv('BIOS_REMOTE_INTERACTIVE', 'true')
    monkeypatch.setenv('BIOS_REVIEW_USERNAME', 'fixture-startup')
    monkeypatch.delenv('BIOS_REVIEW_PASSWORD', raising=False)
    monkeypatch.setenv('BIOS_SESSION_SECRET', 'fixture-startup-secret-at-least-32-characters')

    async def boot():
        async with main.lifespan(main.app):
            pytest.fail('Misconfigured application must not become ready')

    with pytest.raises(RemoteInteractiveMisconfigured):
        asyncio.run(boot())
    assert not calls and not (tmp_path / 'must-not-exist').exists()
