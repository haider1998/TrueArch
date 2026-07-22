"""Tests for the HTTP transport's DNS-rebinding / Host-header policy.

Production bug this guards: the MCP SDK enables DNS-rebinding protection with a
localhost-only allowlist by default. Deployed behind a real hostname (e.g.
*.hf.space) every MCP request is rejected with 421 Misdirected Request — while
/health keeps returning 200, so the server looks up but is unusable.

`TRUEARCH_ALLOWED_HOSTS` makes the allowlist deployable without weakening the
safe default for servers running on a developer's machine.
"""
import importlib

import pytest
from fastapi.testclient import TestClient


def _server_with_hosts(monkeypatch, value):
    """Reload the server module with TRUEARCH_ALLOWED_HOSTS set to `value`."""
    if value is None:
        monkeypatch.delenv("TRUEARCH_ALLOWED_HOSTS", raising=False)
    else:
        monkeypatch.setenv("TRUEARCH_ALLOWED_HOSTS", value)
    import src.mcp.server as server_mod
    return importlib.reload(server_mod)


# ── The policy object itself ─────────────────────────────────────────────────

def test_default_is_localhost_only(monkeypatch):
    """Unset must keep the safe local default — not silently open the server up."""
    mod = _server_with_hosts(monkeypatch, None)
    policy = mod._transport_security()
    assert policy.enable_dns_rebinding_protection is True
    assert "localhost:*" in policy.allowed_hosts
    assert not any("hf.space" in h for h in policy.allowed_hosts)


def test_wildcard_disables_rebinding_protection(monkeypatch):
    """"*" is the public-deployment escape hatch."""
    mod = _server_with_hosts(monkeypatch, "*")
    assert mod._transport_security().enable_dns_rebinding_protection is False


def test_explicit_hosts_are_allowed_with_and_without_port(monkeypatch):
    mod = _server_with_hosts(monkeypatch, "truearch.hf.space, example.com")
    policy = mod._transport_security()
    assert policy.enable_dns_rebinding_protection is True
    assert "truearch.hf.space" in policy.allowed_hosts
    assert "truearch.hf.space:*" in policy.allowed_hosts
    assert "example.com" in policy.allowed_hosts
    # Both schemes accepted as Origin — deployments are https, local dev is http.
    assert "https://truearch.hf.space" in policy.allowed_origins
    assert "http://example.com" in policy.allowed_origins


# ── End-to-end: does a deployed hostname actually get served? ────────────────

_RPC = {
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "pytest", "version": "1.0"},
    },
}
_HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


def test_deployed_hostname_is_rejected_by_default(monkeypatch):
    """Documents the failure mode: this is exactly what broke the Space."""
    mod = _server_with_hosts(monkeypatch, None)
    with TestClient(mod._build_http_app(), base_url="https://truearch.hf.space") as c:
        assert c.post("/mcp/", headers=_HEADERS, json=_RPC).status_code == 421


def test_deployed_hostname_is_served_when_allowlisted(monkeypatch):
    """...and that the fix actually serves that same request."""
    mod = _server_with_hosts(monkeypatch, "truearch.hf.space")
    with TestClient(mod._build_http_app(), base_url="https://truearch.hf.space") as c:
        resp = c.post("/mcp/", headers=_HEADERS, json=_RPC)
        assert resp.status_code == 200, resp.text[:300]
        assert "truearch-intelligence" in resp.text


def test_wildcard_serves_any_hostname(monkeypatch):
    """The setting the Docker image ships with must serve an arbitrary host."""
    mod = _server_with_hosts(monkeypatch, "*")
    with TestClient(mod._build_http_app(), base_url="https://anything.example.org") as c:
        resp = c.post("/mcp/", headers=_HEADERS, json=_RPC)
        assert resp.status_code == 200, resp.text[:300]


@pytest.fixture(autouse=True, scope="module")
def _restore_server_module():
    """Leave the module in its default state for other test files."""
    yield
    import src.mcp.server as server_mod
    importlib.reload(server_mod)
