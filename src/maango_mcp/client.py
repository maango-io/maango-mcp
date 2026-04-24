"""Thin async HTTP client for the Maango API.

Deployed mode: the MCP server holds ONE service API key (MAANGO_API_KEY) and
calls the Maango REST API on behalf of every connected MCP client. End-users
connecting to mcp.maango.io do not need their own key.

Local mode: developers running the server via stdio for Claude Desktop supply
their own MAANGO_API_KEY in .env. Anonymous (no key) is also accepted — the
server will still start and rely on the API's public surface area.
"""

import os

import httpx


class MaangoClient:

    def __init__(self) -> None:
        self.base_url = os.environ.get(
            "MAANGO_API_BASE_URL", "https://api.maango.io"
        ).rstrip("/")
        api_key = os.environ.get("MAANGO_API_KEY", "").strip()
        headers: dict[str, str] = {"User-Agent": "maango-mcp/0.1.0"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=15.0,
            follow_redirects=True,
        )

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            resp = await self._client.request(method, path, **kwargs)
            if 200 <= resp.status_code < 300:
                return resp.json()
            try:
                body = resp.json()
                msg = body.get("message", str(body))
            except Exception:
                msg = resp.text
            return {"error": True, "status": resp.status_code, "message": msg}
        except httpx.HTTPError as e:
            return {"error": True, "message": f"Connection error: {e}"}

    async def lookup_domain(self, domain: str) -> dict:
        return await self._request("GET", f"/v1/domain/{domain}")

    async def lookup_domain_full(self, domain: str) -> dict:
        return await self._request("GET", f"/v1/domain/{domain}/full")

    async def lookup_domain_conflicts(self, domain: str) -> dict:
        return await self._request("GET", f"/v1/domain/{domain}/conflicts")

    async def search_domains(
        self, q: str, stance: str | None, limit: int, offset: int
    ) -> dict:
        params: dict = {"q": q, "limit": limit, "offset": offset}
        if stance:
            params["stance"] = stance
        return await self._request("GET", "/v1/search", params=params)

    async def batch_check(self, domains: list[str]) -> dict:
        return await self._request("POST", "/v1/batch", json={"domains": domains})

    async def get_changelog(
        self, domain: str | None, change_type: str | None, limit: int, offset: int
    ) -> dict:
        params: dict = {"limit": limit, "offset": offset}
        if domain:
            params["domain"] = domain
        if change_type:
            params["change_type"] = change_type
        return await self._request("GET", "/v1/changelog", params=params)
