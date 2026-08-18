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
