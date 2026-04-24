"""Phase 3 — Each MCP tool's dispatch and output shape.

Calls tools through the MCP framework (mcp.call_tool) with respx-mocked API.
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
    """Invoke an MCP tool through the framework and return the parsed JSON body."""
    # Force fresh import so client picks up the test base URL from env.
    import importlib
    import maango_mcp.server as server_mod
    importlib.reload(server_mod)
    result = await server_mod.mcp.call_tool(tool_name, args)
    # FastMCP returns a tuple (content_list, metadata_dict).
    if isinstance(result, tuple):
        content_list, _meta = result
        text = content_list[0].text
    else:
        text = result[0].text if isinstance(result, list) else result.get("result", "{}")
    return json.loads(text)


# --- check_permission ---------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_check_permission_compliant():
    respx.get(f"{BASE}/v1/domain/example.com").mock(
        return_value=httpx.Response(
            200,
            json={
                "found": True,
                "stance": "selective",
                "use_cases": {"training": "allow"},
                "bots": {"blocked": [], "allowed": []},
                "signals": {"robots_txt": True},
            },
        )
    )
    body = await _call("check_permission", {"domain": "example.com", "action": "train"})
    assert body["allowed"] is True
    assert body["reason_code"] == "compliant"
    assert body["domain"] == "example.com"
    assert body["action"] == "train"


@pytest.mark.asyncio
@respx.mock
async def test_check_permission_action_blocked():
    respx.get(f"{BASE}/v1/domain/example.com").mock(
        return_value=httpx.Response(
            200,
            json={
                "found": True,
                "stance": "selective",
                "use_cases": {"training": "block"},
                "bots": {"blocked": [], "allowed": []},
                "signals": {},
            },
        )
    )
    body = await _call("check_permission", {"domain": "example.com", "action": "train"})
    assert body["allowed"] is False
    assert body["reason_code"] == "action_blocked"
    assert body["use_case"] == "training"


@pytest.mark.asyncio
@respx.mock
async def test_check_permission_bot_blocked():
    respx.get(f"{BASE}/v1/domain/example.com").mock(
        return_value=httpx.Response(
            200,
            json={
                "found": True,
                "stance": "selective",
                "use_cases": {"training": "allow"},
                "bots": {"blocked": ["GPTBot"], "allowed": []},
                "signals": {},
            },
        )
    )
    body = await _call(
        "check_permission",
        {"domain": "example.com", "action": "train", "agent_id": "GPTBot"},
    )
    assert body["allowed"] is False
    assert body["reason_code"] == "bot_blocked"


@pytest.mark.asyncio
@respx.mock
async def test_check_permission_no_policy():
    respx.get(f"{BASE}/v1/domain/unknown.test").mock(
        return_value=httpx.Response(200, json={"found": False})
    )
    body = await _call("check_permission", {"domain": "unknown.test", "action": "train"})
    assert body["allowed"] is False
    assert body["reason_code"] == "no_policy"


@pytest.mark.asyncio
@respx.mock
async def test_check_permission_lookup_error():
    respx.get(f"{BASE}/v1/domain/example.com").mock(
        return_value=httpx.Response(500, text="Server error")
    )
    body = await _call("check_permission", {"domain": "example.com", "action": "train"})
    assert body["allowed"] is False
    assert body["reason_code"] == "lookup_error"


@pytest.mark.asyncio
@respx.mock
async def test_check_permission_output_has_all_fields():
    respx.get(f"{BASE}/v1/domain/example.com").mock(
        return_value=httpx.Response(
            200,
            json={
                "found": True,
                "stance": "selective",
                "use_cases": {"training": "allow"},
                "bots": {"blocked": [], "allowed": []},
                "signals": {"robots_txt": True, "tdmrep": False},
            },
        )
    )
    body = await _call(
        "check_permission",
        {"domain": "example.com", "action": "train", "agent_id": "TestBot"},
    )
    for field in (
        "domain",
        "action",
        "agent_id",
        "allowed",
        "reason_code",
        "explanation",
        "signals_checked",
    ):
        assert field in body, f"missing field: {field}"
    assert body["agent_id"] == "TestBot"


# --- lookup_domain ------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_lookup_domain_returns_full_api_response():
    respx.get(f"{BASE}/v1/domain/example.com").mock(
        return_value=httpx.Response(
            200,
            json={
                "found": True,
                "stance": "blocks_all_ai",
                "use_cases": {"training": "block", "search": "block", "ai_input": "block"},
            },
        )
    )
    body = await _call("lookup_domain", {"domain": "example.com"})
    assert body["stance"] == "blocks_all_ai"
    assert body["use_cases"]["training"] == "block"


@pytest.mark.asyncio
@respx.mock
async def test_lookup_domain_surfaces_errors():
    respx.get(f"{BASE}/v1/domain/example.com").mock(
        return_value=httpx.Response(404, json={"message": "not found"})
    )
    body = await _call("lookup_domain", {"domain": "example.com"})
    assert body["error"] is True
    assert body["status"] == 404


# --- lookup_domain_full -------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_lookup_domain_full_hits_full_endpoint():
    respx.get(f"{BASE}/v1/domain/example.com/full").mock(
        return_value=httpx.Response(200, json={"full": True})
    )
    body = await _call("lookup_domain_full", {"domain": "example.com"})
    assert body["full"] is True


# --- lookup_domain_conflicts --------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_lookup_domain_conflicts_empty_when_none():
    respx.get(f"{BASE}/v1/domain/example.com/conflicts").mock(
        return_value=httpx.Response(200, json={"conflicts": []})
    )
    body = await _call("lookup_domain_conflicts", {"domain": "example.com"})
    assert body["conflicts"] == []


# --- search_domains -----------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_search_domains_with_stance_filter():
    route = respx.get(f"{BASE}/v1/search").mock(
        return_value=httpx.Response(200, json={"results": [{"domain": "x.com"}]})
    )
    body = await _call(
        "search_domains",
        {"query": "news", "stance": "blocks_all_ai", "limit": 5, "offset": 0},
    )
    assert body["results"] == [{"domain": "x.com"}]
    assert "stance=blocks_all_ai" in str(route.calls.last.request.url)


@pytest.mark.asyncio
@respx.mock
async def test_search_domains_empty_stance_omitted():
    route = respx.get(f"{BASE}/v1/search").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    await _call("search_domains", {"query": "ns"})
    assert "stance" not in str(route.calls.last.request.url)


# --- batch_check --------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_batch_check_posts_domains():
    route = respx.post(f"{BASE}/v1/batch").mock(
        return_value=httpx.Response(
            200, json={"results": [{"domain": "a.com"}, {"domain": "b.com"}]}
        )
    )
    body = await _call("batch_check", {"domains": ["a.com", "b.com"]})
    assert len(body["results"]) == 2
    req_body = json.loads(route.calls.last.request.content)
    assert req_body == {"domains": ["a.com", "b.com"]}


# --- get_changelog ------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_changelog_no_filters_passes_through():
    respx.get(f"{BASE}/v1/changelog").mock(
        return_value=httpx.Response(200, json={"entries": []})
    )
    body = await _call("get_changelog", {})
    assert body == {"entries": []}


@pytest.mark.asyncio
@respx.mock
async def test_changelog_with_domain_filter():
    route = respx.get(f"{BASE}/v1/changelog").mock(
        return_value=httpx.Response(200, json={"entries": []})
    )
    await _call("get_changelog", {"domain": "nytimes.com"})
    assert "domain=nytimes.com" in str(route.calls.last.request.url)


# --- Tool registry ------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_seven_tools_registered():
    from maango_mcp.server import mcp
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    expected = {
        "check_permission",
        "lookup_domain",
        "lookup_domain_full",
        "lookup_domain_conflicts",
        "search_domains",
        "batch_check",
        "get_changelog",
    }
    assert names == expected


@pytest.mark.asyncio
async def test_every_tool_has_description():
    from maango_mcp.server import mcp
    tools = await mcp.list_tools()
    for tool in tools:
        assert tool.description, f"{tool.name} has empty description"
        assert len(tool.description) > 50, f"{tool.name} description too short"


@pytest.mark.asyncio
async def test_every_tool_has_input_schema():
    from maango_mcp.server import mcp
    tools = await mcp.list_tools()
    for tool in tools:
        schema = tool.inputSchema
        assert schema["type"] == "object", f"{tool.name} schema wrong type"
        assert "properties" in schema, f"{tool.name} schema missing properties"
