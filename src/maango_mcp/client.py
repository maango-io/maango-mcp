"""Thin async HTTP client for the Maango API.

Deployed mode: the MCP server holds ONE service API key (MAANGO_API_KEY) and
calls the Maango REST API on behalf of every connected MCP client. End-users
connecting to mcp.maango.io do not need their own key.

Local mode: developers running the server via stdio for Claude Desktop supply
their own MAANGO_API_KEY in .env. Anonymous (no key) is also accepted — the
server will still start and rely on the API's public surface area.

Error responses returned to MCP tools are sanitized: HTML tags stripped,
whitespace collapsed, length-capped. The full upstream payload is logged
internally at WARNING level so operators can debug from the JSON logs
without exposing it to the end-user agent.
"""

import logging
import os
import re

import httpx

logger = logging.getLogger("maango_mcp.client")

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MAX_ERROR_MESSAGE_LEN = 200


def _sanitize_error_message(msg: object, max_len: int = _MAX_ERROR_MESSAGE_LEN) -> str:
    """Strip HTML tags, collapse whitespace, truncate.

    Upstream APIs sometimes return raw HTML error pages (gateway timeouts,
    misconfigured proxies) or verbose stack traces. Forwarding those to MCP
    clients leaks internal details. Keep the response shape stable while
    redacting the noise.
    """
    text = str(msg) if not isinstance(msg, str) else msg
    text = _HTML_TAG_RE.sub("", text)
    text = " ".join(text.split())
    if len(text) > max_len:
        text = text[: max_len - 1] + "…"
    return text


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

            # Try JSON shape first, fall back to raw text.
            raw_msg: str
            try:
                body = resp.json()
                raw_msg = body.get("message") if isinstance(body, dict) else str(body)
                if not raw_msg:
                    raw_msg = str(body)
            except Exception:
                raw_msg = resp.text

            # Log the full context for ops; return a sanitized version.
            logger.warning(
                "upstream_error",
                extra={
                    "endpoint": path,
                    "method": method,
                    "upstream_status": resp.status_code,
                    "upstream_message": str(raw_msg)[:500],
                },
            )
            return {
                "error": True,
                "status": resp.status_code,
                "message": _sanitize_error_message(raw_msg),
            }
        except httpx.HTTPError as e:
            logger.warning(
                "upstream_connection_error",
                extra={
                    "endpoint": path,
                    "method": method,
                    "exception": type(e).__name__,
                    "detail": str(e)[:200],
                },
            )
            return {
                "error": True,
                "message": f"Connection error: {_sanitize_error_message(str(e))}",
            }

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
