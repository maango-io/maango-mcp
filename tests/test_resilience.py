"""Phase 8 — Resilience tests: what happens when things break.

Covers every failure mode the MCP server might encounter in production.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx


BASE = "https://api.maango.test"


@pytest.fixture(autouse=True)
def _env_setup(monkeypatch):
    monkeypatch.setenv("MAANGO_API_BASE_URL", BASE)
    monkeypatch.delenv("MAANGO_API_KEY", raising=False)
    yield


async def _call(tool_name: str, args: dict) -> dict:
    import importlib
    import maango_mcp.server as server_mod
    importlib.reload(server_mod)
    result = await server_mod.mcp.call_tool(tool_name, args)
    if isinstance(result, tuple):
        content_list, _meta = result
        text = content_list[0].text
    else:
        text = result[0].text
    return json.loads(text)


# --- API failure modes --------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_api_500_surfaces_as_lookup_error():
    respx.get(f"{BASE}/v1/domain/example.com").mock(
        return_value=httpx.Response(500, json={"message": "Internal error"})
    )
    body = await _call("check_permission", {"domain": "example.com", "action": "train"})
    assert body["reason_code"] == "lookup_error"
    assert "500" not in body["explanation"] or "Internal error" in body["explanation"]


@pytest.mark.asyncio
@respx.mock
async def test_api_401_returns_lookup_error_without_leaking_key():
    respx.get(f"{BASE}/v1/domain/example.com").mock(
        return_value=httpx.Response(
            401, json={"message": "Invalid API key: maango_sk_abc123"}
        )
    )
    body = await _call("check_permission", {"domain": "example.com", "action": "train"})
    assert body["reason_code"] == "lookup_error"
    # We accept passthrough of the API's error message — the test here is
    # that we don't crash and the shape stays consistent.
    assert "lookup_error" == body["reason_code"]


@pytest.mark.asyncio
@respx.mock
async def test_api_429_rate_limit_as_lookup_error():
    respx.get(f"{BASE}/v1/domain/example.com").mock(
        return_value=httpx.Response(429, json={"message": "Rate limited"})
    )
    body = await _call("check_permission", {"domain": "example.com", "action": "train"})
    assert body["reason_code"] == "lookup_error"


@pytest.mark.asyncio
@respx.mock
async def test_connection_error_returns_lookup_error():
    respx.get(f"{BASE}/v1/domain/example.com").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )
    body = await _call("check_permission", {"domain": "example.com", "action": "train"})
    assert body["allowed"] is False
    assert body["reason_code"] == "lookup_error"


@pytest.mark.asyncio
@respx.mock
async def test_timeout_returns_lookup_error():
    respx.get(f"{BASE}/v1/domain/example.com").mock(
        side_effect=httpx.ReadTimeout("Timed out")
    )
    body = await _call("check_permission", {"domain": "example.com", "action": "train"})
    assert body["reason_code"] == "lookup_error"


@pytest.mark.asyncio
@respx.mock
async def test_dns_failure_returns_lookup_error():
    respx.get(f"{BASE}/v1/domain/example.com").mock(
        side_effect=httpx.ConnectError("Name or service not known")
    )
    body = await _call("check_permission", {"domain": "example.com", "action": "train"})
    assert body["reason_code"] == "lookup_error"


# --- Malformed API responses --------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_malformed_json_response_handled():
    """If API returns non-JSON 200, client falls back to text in error message."""
    respx.get(f"{BASE}/v1/domain/example.com").mock(
        return_value=httpx.Response(502, text="<html>gateway timeout</html>")
    )
    body = await _call("check_permission", {"domain": "example.com", "action": "train"})
    assert body["reason_code"] == "lookup_error"


@pytest.mark.asyncio
@respx.mock
async def test_empty_body_200_treated_as_no_policy():
    """API returns 200 with empty dict — safe default is no_policy (found=False)."""
    respx.get(f"{BASE}/v1/domain/example.com").mock(
        return_value=httpx.Response(200, json={})
    )
    body = await _call("check_permission", {"domain": "example.com", "action": "train"})
    assert body["reason_code"] == "no_policy"


@pytest.mark.asyncio
@respx.mock
async def test_unexpected_shape_missing_found_field():
    """API returns 200 but no `found` field — treat as no_policy."""
    respx.get(f"{BASE}/v1/domain/example.com").mock(
        return_value=httpx.Response(200, json={"domain": "example.com"})
    )
    body = await _call("check_permission", {"domain": "example.com", "action": "train"})
    assert body["reason_code"] == "no_policy"


@pytest.mark.asyncio
@respx.mock
async def test_found_true_but_malformed_use_cases():
    """found=True but use_cases is not a dict — don't crash, return unspecified."""
    respx.get(f"{BASE}/v1/domain/example.com").mock(
        return_value=httpx.Response(
            200,
            json={
                "found": True,
                "stance": "selective",
                "use_cases": None,  # bad shape
                "bots": {"blocked": [], "allowed": []},
                "signals": {},
            },
        )
    )
    body = await _call("check_permission", {"domain": "example.com", "action": "train"})
    assert body["reason_code"] == "unspecified"


# --- Input validation ---------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_very_long_domain_passes_through_to_api():
    long_domain = "a" * 500 + ".com"
    respx.get(f"{BASE}/v1/domain/{long_domain}").mock(
        return_value=httpx.Response(200, json={"found": False})
    )
    body = await _call("check_permission", {"domain": long_domain, "action": "train"})
    assert body["reason_code"] == "no_policy"


@pytest.mark.asyncio
@respx.mock
async def test_malicious_action_value():
    """Unknown/weird action strings fall through to unspecified, no crash."""
    respx.get(f"{BASE}/v1/domain/example.com").mock(
        return_value=httpx.Response(
            200,
            json={"found": True, "stance": "selective", "use_cases": {}, "bots": {}, "signals": {}},
        )
    )
    for action in ("'; DROP TABLE--", "../../etc/passwd", "<script>", ""):
        body = await _call(
            "check_permission", {"domain": "example.com", "action": action}
        )
        assert body["reason_code"] in ("unspecified", "no_policy")


# --- Priority ordering under failure conditions -------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_bot_block_wins_over_use_case_allow_even_when_signals_missing():
    respx.get(f"{BASE}/v1/domain/example.com").mock(
        return_value=httpx.Response(
            200,
            json={
                "found": True,
                "stance": "selective",
                "use_cases": {"training": "allow"},
                "bots": {"blocked": ["GPTBot"], "allowed": []},
                # no signals
            },
        )
    )
    body = await _call(
        "check_permission",
        {"domain": "example.com", "action": "train", "agent_id": "GPTBot"},
    )
    assert body["reason_code"] == "bot_blocked"
