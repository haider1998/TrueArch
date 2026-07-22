"""Regression tests for the streamable-HTTP deployment path (Hugging Face Spaces).

Two production bugs motivated this file, both of which left the deployed Space
completely unusable as an MCP server while /health still returned 200:

  1. `mcp.streamable_http_app()` was mounted inside FastAPI, but mounting an ASGI
     sub-app does not run that sub-app's lifespan. The session manager's task
     group was therefore never started and every MCP request died with
     "Task group is not initialized. Make sure to use run()."

  2. FastMCP's `streamable_http_path` defaults to "/mcp"; mounting that app at
     "/mcp" produced the endpoint "/mcp/mcp", so the documented URL 404'd.

These tests drive the real ASGI app over the real protocol, so they fail if
either regression returns.
"""
import json

import pytest
from fastapi.testclient import TestClient

from src.mcp.server import _build_http_app

_MCP_URL = "/mcp/"
_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def _rpc(client: TestClient, method: str, params: dict, req_id: int = 1):
    """Make a JSON-RPC call and parse the SSE-framed response body."""
    resp = client.post(
        _MCP_URL,
        headers=_HEADERS,
        content=json.dumps(
            {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
        ),
    )
    assert resp.status_code == 200, f"{method} → HTTP {resp.status_code}: {resp.text[:300]}"
    # Streamable HTTP frames the payload as Server-Sent Events.
    for line in resp.text.splitlines():
        if line.startswith("data: "):
            return json.loads(line[len("data: "):])
    raise AssertionError(f"No SSE data frame in response: {resp.text[:300]}")


@pytest.fixture(scope="module")
def http_client():
    """TestClient over the real HTTP app — enters the lifespan, as uvicorn would.

    TestClient sends `Host: testserver`, which the SDK's localhost-only
    DNS-rebinding default rejects with 421 — the same way a real deployment
    behind *.hf.space is rejected. Requests are sent with a localhost Host so
    these tests exercise the transport rather than the host policy (which
    test_host_policy.py covers directly).
    """
    with TestClient(_build_http_app(), base_url="http://localhost:8001") as client:
        yield client


def test_health_endpoint_reports_loaded_frameworks(http_client):
    body = http_client.get("/health").json()
    assert body["status"] == "ok"
    assert body["frameworks_loaded"] > 0


def test_mcp_initialize_handshake_succeeds(http_client):
    """Guards bug #1: without the lifespan wiring this raises RuntimeError."""
    body = _rpc(
        http_client,
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "1.0"},
        },
    )
    assert "error" not in body, body
    assert body["result"]["serverInfo"]["name"] == "truearch-intelligence"


def test_mcp_endpoint_is_at_slash_mcp_not_slash_mcp_mcp(http_client):
    """Guards bug #2: the documented endpoint must be the one that answers."""
    assert http_client.post("/mcp/mcp", headers=_HEADERS, content="{}").status_code == 404


def test_tools_list_exposes_the_daily_loop_tools(http_client):
    body = _rpc(http_client, "tools/list", {}, req_id=2)
    names = {t["name"] for t in body["result"]["tools"]}
    # The daily-loop hero tools must always be reachable over HTTP.
    assert {"validate_code", "latest_stable_versions", "quick_context"} <= names


def test_validate_code_over_http_catches_a_deprecated_api(http_client):
    """The full product claim, exercised over the wire the way a client uses it."""
    body = _rpc(
        http_client,
        "tools/call",
        {
            "name": "validate_code",
            "arguments": {
                "code": "import pinecone\npinecone.init(api_key='k', environment='us-west1')",
                "framework_id": "pinecone",
            },
        },
        req_id=3,
    )
    assert body["result"]["isError"] is False
    payload = json.loads(body["result"]["content"][0]["text"])
    assert payload["violations_found"] >= 1
    assert "PCN-001" in {v["pattern_id"] for v in payload["violations"]}
