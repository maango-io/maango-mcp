"""Phase 2 — HTTP client tests with respx mocking httpx at the transport layer.

Zero network. Verifies auth, headers, error handling, endpoint paths, params.
"""

from __future__ import annotations

import os

import httpx
import pytest
import respx

from maango_mcp.client import MaangoClient


BASE = "https://api.maango.test"


@pytest.fixture(autouse=True)
def _env_setup(monkeypatch):
    monkeypatch.setenv("MAANGO_API_BASE_URL", BASE)
    monkeypatch.delenv("MAANGO_API_KEY", raising=False)
    yield


# --- Auth header --------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_auth_header_sent_when_api_key_set(monkeypatch):
    monkeypatch.setenv("MAANGO_API_KEY", "maango_sk_test123")
    route = respx.get(f"{BASE}/v1/domain/example.com").mock(
        return_value=httpx.Response(200, json={"found": True})
    )
    client = MaangoClient()
    await client.lookup_domain("example.com")
    assert route.called
    req = route.calls.last.request
    assert req.headers["Authorization"] == "Bearer maango_sk_test123"


@pytest.mark.asyncio
@respx.mock
async def test_no_auth_header_when_no_api_key():
    route = respx.get(f"{BASE}/v1/domain/example.com").mock(
        return_value=httpx.Response(200, json={"found": True})
    )
    client = MaangoClient()
    await client.lookup_domain("example.com")
    req = route.calls.last.request
    assert "Authorization" not in req.headers


@pytest.mark.asyncio
@respx.mock
async def test_user_agent_set_on_every_request():
    route = respx.get(f"{BASE}/v1/domain/example.com").mock(
        return_value=httpx.Response(200, json={})
    )
    client = MaangoClient()
    await client.lookup_domain("example.com")
    assert route.calls.last.request.headers["User-Agent"] == "maango-mcp/0.1.0"


@pytest.mark.asyncio
async def test_empty_api_key_treated_as_no_key(monkeypatch):
    monkeypatch.setenv("MAANGO_API_KEY", "   ")  # whitespace only
    client = MaangoClient()
    assert "Authorization" not in client._client.headers


# --- Base URL handling --------------------------------------------------------


@pytest.mark.asyncio
async def test_trailing_slash_stripped_from_base_url(monkeypatch):
    monkeypatch.setenv("MAANGO_API_BASE_URL", "https://api.maango.test/")
    client = MaangoClient()
    assert str(client.base_url) == "https://api.maango.test"


@pytest.mark.asyncio
async def test_base_url_overridable_via_env(monkeypatch):
    monkeypatch.setenv("MAANGO_API_BASE_URL", "http://localhost:9999")
    client = MaangoClient()
    assert client.base_url == "http://localhost:9999"


# --- Response handling --------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_200_returns_parsed_json():
    respx.get(f"{BASE}/v1/domain/example.com").mock(
        return_value=httpx.Response(200, json={"found": True, "stance": "selective"})
    )
    client = MaangoClient()
    result = await client.lookup_domain("example.com")
    assert result == {"found": True, "stance": "selective"}


@pytest.mark.asyncio
@respx.mock
async def test_4xx_returns_error_dict():
    respx.get(f"{BASE}/v1/domain/example.com").mock(
        return_value=httpx.Response(
            401, json={"message": "Invalid API key"}
        )
    )
    client = MaangoClient()
    result = await client.lookup_domain("example.com")
    assert result["error"] is True
    assert result["status"] == 401
    assert "Invalid API key" in result["message"]


@pytest.mark.asyncio
@respx.mock
async def test_5xx_returns_error_dict():
    respx.get(f"{BASE}/v1/domain/example.com").mock(
        return_value=httpx.Response(500, json={"message": "Internal error"})
    )
    client = MaangoClient()
    result = await client.lookup_domain("example.com")
    assert result["error"] is True
    assert result["status"] == 500


@pytest.mark.asyncio
@respx.mock
async def test_429_rate_limit_returns_error_dict():
    respx.get(f"{BASE}/v1/domain/example.com").mock(
        return_value=httpx.Response(429, json={"message": "Rate limited"})
    )
    client = MaangoClient()
    result = await client.lookup_domain("example.com")
    assert result["error"] is True
    assert result["status"] == 429


@pytest.mark.asyncio
@respx.mock
async def test_network_error_returns_error_dict():
    respx.get(f"{BASE}/v1/domain/example.com").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )
    client = MaangoClient()
    result = await client.lookup_domain("example.com")
    assert result["error"] is True
    assert "Connection error" in result["message"]


@pytest.mark.asyncio
@respx.mock
async def test_timeout_returns_error_dict():
    respx.get(f"{BASE}/v1/domain/example.com").mock(
        side_effect=httpx.ReadTimeout("Timed out")
    )
    client = MaangoClient()
    result = await client.lookup_domain("example.com")
    assert result["error"] is True


@pytest.mark.asyncio
@respx.mock
async def test_non_json_response_handled():
    respx.get(f"{BASE}/v1/domain/example.com").mock(
        return_value=httpx.Response(502, text="Bad Gateway — upstream timeout")
    )
    client = MaangoClient()
    result = await client.lookup_domain("example.com")
    assert result["error"] is True
    assert "Bad Gateway" in result["message"]


# --- Endpoint paths -----------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_lookup_domain_hits_correct_path():
    route = respx.get(f"{BASE}/v1/domain/example.com").mock(
        return_value=httpx.Response(200, json={})
    )
    client = MaangoClient()
    await client.lookup_domain("example.com")
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_lookup_domain_full_hits_full_endpoint():
    route = respx.get(f"{BASE}/v1/domain/example.com/full").mock(
        return_value=httpx.Response(200, json={})
    )
    client = MaangoClient()
    await client.lookup_domain_full("example.com")
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_lookup_domain_conflicts_hits_conflicts_endpoint():
    route = respx.get(f"{BASE}/v1/domain/example.com/conflicts").mock(
        return_value=httpx.Response(200, json={})
    )
    client = MaangoClient()
    await client.lookup_domain_conflicts("example.com")
    assert route.called


# --- Search params ------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_search_passes_stance_filter():
    route = respx.get(f"{BASE}/v1/search").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    client = MaangoClient()
    await client.search_domains("news", "blocks_all_ai", 10, 0)
    req = route.calls.last.request
    assert "stance=blocks_all_ai" in str(req.url)
    assert "q=news" in str(req.url)
    assert "limit=10" in str(req.url)


@pytest.mark.asyncio
@respx.mock
async def test_search_omits_stance_when_none():
    route = respx.get(f"{BASE}/v1/search").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    client = MaangoClient()
    await client.search_domains("news", None, 20, 0)
    req = route.calls.last.request
    assert "stance" not in str(req.url)


# --- Batch --------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_batch_check_posts_json_body():
    route = respx.post(f"{BASE}/v1/batch").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    client = MaangoClient()
    await client.batch_check(["a.com", "b.com", "c.com"])
    req = route.calls.last.request
    import json as _json
    body = _json.loads(req.content)
    assert body == {"domains": ["a.com", "b.com", "c.com"]}


# --- Changelog ----------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_changelog_no_filters():
    route = respx.get(f"{BASE}/v1/changelog").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    client = MaangoClient()
    await client.get_changelog(None, None, 50, 0)
    req = route.calls.last.request
    assert "domain" not in str(req.url)
    assert "change_type" not in str(req.url)


@pytest.mark.asyncio
@respx.mock
async def test_changelog_with_domain_filter():
    route = respx.get(f"{BASE}/v1/changelog").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    client = MaangoClient()
    await client.get_changelog("nytimes.com", None, 50, 0)
    req = route.calls.last.request
    assert "domain=nytimes.com" in str(req.url)
