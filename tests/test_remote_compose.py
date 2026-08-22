from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_compose_publishes_app_on_loopback_only() -> None:
    compose = (ROOT / "deploy" / "docker-compose.yml").read_text(encoding="utf-8")
    assert '"${BIOS_APP_BIND:-127.0.0.1}:${BIOS_APP_PORT:-8000}:8000"' in compose
    assert '"0.0.0.0:${BIOS_APP_PORT' not in compose
    assert 'expose:\n      - "8000"' in compose
    assert '"${BIOS_HTTP_PORT:-80}:80"' in compose
    assert '"${BIOS_HTTPS_PORT:-443}:443"' in compose
    example = (ROOT / "deploy" / ".env.example").read_text(encoding="utf-8")
    assert "BIOS_APP_BIND=127.0.0.1" in example
    bootstrap = (ROOT / "scripts" / "vps_bootstrap.sh").read_text(encoding="utf-8")
    assert "BIOS_APP_BIND=127.0.0.1" in bootstrap
    assert "--profile tls" in bootstrap
    assert "replace-me-with-a-long-random-value" not in bootstrap


def test_all_mutable_runtime_roots_are_bind_mounted_and_inbox_is_never_seeded() -> None:
    compose = (ROOT / "deploy" / "docker-compose.yml").read_text(encoding="utf-8")
    assert "${BIOS_DEMO_RUNTIME:-../demo-runtime}/data:/app/runtime/data" in compose
    assert "${BIOS_DEMO_RUNTIME:-../demo-runtime}/inbox:/app/runtime/inbox" in compose
    entrypoint = (ROOT / "docker-entrypoint.sh").read_text(encoding="utf-8")
    assert "Never seed inbox" in entrypoint
    assert "cp -a /app/seed/data/." in entrypoint
    assert "cp -a /app/seed/inbox" not in entrypoint
