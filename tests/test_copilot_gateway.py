"""The optional agent transport preserves the private application's boundary."""
import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app import copilot_gateway as gateway


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.delenv("BIOS_REMOTE_INTERACTIVE", raising=False)
    monkeypatch.delenv("BIOS_COPILOT_RUNTIME_URL", raising=False)
    monkeypatch.delenv("BIOS_COPILOT_RUNTIME_TOKEN", raising=False)
    return TestClient(main.app, follow_redirects=False)


@pytest.mark.parametrize("address", ["https://127.0.0.1:4321/copilot", "http://external.example:4321/copilot",
    "http://127.0.0.1/copilot", "http://user:password@127.0.0.1:4321/copilot", "http://127.0.0.1:4321/other",
    "http://127.0.0.1:4321/copilot?destination=external", "http://127.0.0.1:bad/copilot"])
def test_runtime_cannot_become_an_arbitrary_proxy(monkeypatch, address):
    monkeypatch.setenv("BIOS_COPILOT_RUNTIME_URL", address)
    monkeypatch.setenv("BIOS_COPILOT_RUNTIME_TOKEN", "test-runtime-token-never-a-provider-secret")
    assert gateway.runtime_configuration() is None


def test_unconfigured_agent_is_bounded_and_direct_actions_remain_available(client):
    response = client.get("/api/investigations/v1/copilot/status")
    assert response.status_code == 200 and response.json()["configured"] is False
    assert response.json()["requires_explicit_command"] is True
    assert "runtime" not in response.text.lower()
    assert client.post("/api/investigations/v1/copilot", json={}).status_code == 503
    assert client.get("/api/investigations/v1/demo/sensory").status_code == 200


def test_runtime_auth_and_origin_are_checked_before_transport(client, monkeypatch):
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    assert client.get("/api/investigations/v1/copilot/status").status_code == 403
    assert client.post("/api/investigations/v1/copilot", json={}).status_code == 403
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    assert client.post("/api/investigations/v1/copilot", json={}, headers={"origin": "https://other.example"}).status_code == 403


@pytest.mark.parametrize("fail_stream", [False, True])
def test_stream_forwards_only_internal_auth_and_closes_resources(client, monkeypatch, fail_stream):
    token = "test-internal-runtime-token-more-than32characters"
    monkeypatch.setenv("BIOS_COPILOT_RUNTIME_URL", "http://127.0.0.1:4321/copilot")
    monkeypatch.setenv("BIOS_COPILOT_RUNTIME_TOKEN", token)
    captured = {}

    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: {"type":"RUN_FINISHED"}\n\n'
            if fail_stream:
                raise RuntimeError("upstream interrupted")
        async def aclose(self):
            captured["stream_closed"] = True

    class LocalClient:
        def __init__(self, **kwargs):
            assert kwargs["trust_env"] is False
        def build_request(self, method, url, **kwargs):
            request = httpx.Request(method, url, **kwargs)
            captured["request"] = request
            return request
        async def send(self, request, stream):
            assert stream is True
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=Stream())
        async def aclose(self):
            captured["client_closed"] = True

    monkeypatch.setattr(gateway.httpx, "AsyncClient", LocalClient)
    def submit():
        return client.post("/api/investigations/v1/copilot", json={"method": "info"},
                           headers={"cookie": "private_browser_cookie=never-forward", "authorization": "Bearer browser-value"})
    if fail_stream:
        with pytest.raises(RuntimeError, match="upstream interrupted"):
            submit()
        assert captured["stream_closed"] and captured["client_closed"]
        return
    response = submit()
    assert response.status_code == 200 and "RUN_FINISHED" in response.text
    request = captured["request"]
    assert str(request.url) == "http://127.0.0.1:4321/copilot"
    assert request.headers["x-berry-runtime-token"] == token
    assert "cookie" not in request.headers and "authorization" not in request.headers
    assert response.headers["cache-control"] == "private, no-store"
    assert captured["stream_closed"] and captured["client_closed"]


def test_command_body_is_bounded_before_contacting_runtime(client, monkeypatch):
    monkeypatch.setenv("BIOS_COPILOT_RUNTIME_URL", "http://127.0.0.1:4321/copilot")
    monkeypatch.setenv("BIOS_COPILOT_RUNTIME_TOKEN", "test-internal-runtime-token-more-than32characters")
    def forbidden(*args, **kwargs):
        raise AssertionError("Oversized commands must not contact the runtime")
    monkeypatch.setattr(gateway.httpx, "AsyncClient", forbidden)
    assert client.post("/api/investigations/v1/copilot", content=b"x" * (gateway.MAX_BODY_BYTES + 1)).status_code == 413
