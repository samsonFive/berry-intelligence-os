"""Session-authorized, bounded transport to the explicitly configured local agent.

This module does not select a model, start a runtime or fall back to a provider.
The runtime owns provider credentials; cookies and browser authorization headers
are never forwarded. No provider call occurs on application startup.
"""
from __future__ import annotations

import os
from urllib.parse import urlsplit

import anyio
import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

from app.experience_routes import PRIVATE_HEADERS, _private_main
from app.personal_digest_routes import require_edit

router = APIRouter()
MAX_BODY_BYTES = 65_536


def runtime_configuration():
    address = os.environ.get("BIOS_COPILOT_RUNTIME_URL", "").strip()
    token = os.environ.get("BIOS_COPILOT_RUNTIME_TOKEN", "")
    if not address or len(token) < 32:
        return None
    try:
        parts = urlsplit(address)
        if (parts.scheme != "http" or parts.hostname not in {"127.0.0.1", "::1"}
                or parts.username or parts.password or parts.query or parts.fragment
                or not parts.port or parts.path not in {"", "/", "/copilot"}):
            return None
    except ValueError:
        return None
    return address.rstrip("/"), token


@router.get("/api/investigations/v1/copilot/status")
def copilot_status():
    _private_main()
    return JSONResponse({"api_v": 1, "configured": runtime_configuration() is not None,
                         "conversation_retention": "session-only", "requires_explicit_command": True},
                        headers=PRIVATE_HEADERS)


@router.api_route("/api/investigations/v1/copilot", methods=["GET", "POST", "OPTIONS"])
async def copilot_transport(request: Request):
    _private_main()
    # SDK metadata and commands have the same session and same-origin boundary.
    require_edit(request)
    configuration = runtime_configuration()
    if configuration is None:
        raise HTTPException(503, "Copilot is not configured. Direct investigation controls remain available.")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BODY_BYTES:
            raise HTTPException(413, "This command exceeds the bounded conversation size")
    address, token = configuration
    client = httpx.AsyncClient(trust_env=False, timeout=httpx.Timeout(120, connect=5))
    headers = {"X-Berry-Runtime-Token": token,
               "Content-Type": "application/json",
               "Accept": "application/json, text/event-stream"}
    # The browser cannot select a destination, route suffix or forwarded cookie.
    # Any protocol query is interpreted only by the one configured runtime.
    query = request.url.query
    destination = address + ("?" + query if query else "")
    try:
        outgoing = client.build_request(request.method, destination, headers=headers, content=bytes(body))
        upstream = await client.send(outgoing, stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(503, "Copilot is unavailable. Continue with the direct investigation controls.") from exc
    except BaseException:
        with anyio.CancelScope(shield=True):
            await client.aclose()
        raise

    closed = False

    async def close():
        nonlocal closed
        if closed:
            return
        closed = True
        # Disconnect cancellation must not interrupt transport cleanup.
        with anyio.CancelScope(shield=True):
            try:
                await upstream.aclose()
            finally:
                await client.aclose()

    async def stream():
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await close()

    return StreamingResponse(stream(), status_code=upstream.status_code,
                             media_type=upstream.headers.get("content-type", "application/json"),
                             headers={**PRIVATE_HEADERS, "X-Accel-Buffering": "no"},
                             background=BackgroundTask(close))
