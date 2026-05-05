"""Maango MCP Server — AI policy lookup + compliance tools for Claude and any MCP agent.

Transports:
  MAANGO_MCP_TRANSPORT=stdio            (default, for local Claude Desktop)
  MAANGO_MCP_TRANSPORT=sse              (remote, /sse + /messages endpoints)
  MAANGO_MCP_TRANSPORT=streamable-http  (remote, /mcp endpoint — modern MCP spec)

Hosted mode listen address:
  MAANGO_MCP_HOST=0.0.0.0
  MAANGO_MCP_PORT=8000

Observability:
  - Logs are emitted as JSON on stderr with a per-tool-call req_id.
  - /health  — cheap liveness probe (no upstream call).
  - /metrics — Prometheus exposition (tool requests, durations, upstream errors).
"""

import contextvars
import json
import logging
import os
import sys
import time
import uuid
from functools import wraps

from mcp.server.fastmcp import FastMCP
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .client import MaangoClient

__version__ = "0.1.0"


# --- Structured logging --------------------------------------------------------
#
# One JSON object per stderr line. Compatible with log shippers (Loki, Datadog,
# CloudWatch). Per-call req_id is propagated via a contextvar so any logging
# inside the tool / client / decision tree is automatically tagged.

REQUEST_ID: contextvars.ContextVar[str] = contextvars.ContextVar(
    "maango_mcp_request_id", default="-"
)


class _JsonFormatter(logging.Formatter):
    _STD_LOGRECORD_FIELDS = frozenset(
        {
            "args", "asctime", "created", "exc_info", "exc_text", "filename",
            "funcName", "levelname", "levelno", "lineno", "message", "module",
            "msecs", "msg", "name", "pathname", "process", "processName",
            "relativeCreated", "stack_info", "taskName", "thread", "threadName",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
        payload = {
            "ts": f"{ts}.{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "req_id": REQUEST_ID.get(),
        }
        for key, value in record.__dict__.items():
            if key in self._STD_LOGRECORD_FIELDS or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def _configure_logging() -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


_configure_logging()
logger = logging.getLogger("maango_mcp")


# --- Metrics -------------------------------------------------------------------
#
# Module-private registry. Avoids duplicate-registration errors when the test
# suite reloads this module (some tests call importlib.reload to pick up env
# changes), and keeps our metrics off the global default registry.

_METRICS_REGISTRY = CollectorRegistry()

_TOOL_REQUESTS = Counter(
    "maango_mcp_tool_requests",
    "Total MCP tool calls received by this server.",
    ["tool", "status"],
    registry=_METRICS_REGISTRY,
)
_TOOL_DURATION = Histogram(
    "maango_mcp_tool_duration_seconds",
    "Time taken to handle an MCP tool call (includes upstream API latency).",
    ["tool"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=_METRICS_REGISTRY,
)


def _instrument(tool_name: str):
    """Wrap an async tool function with request ID, structured log, and metrics."""

    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            req_id = uuid.uuid4().hex[:12]
            tok = REQUEST_ID.set(req_id)
            t0 = time.monotonic()
            status = "ok"
            try:
                return await fn(*args, **kwargs)
            except Exception:
                status = "error"
                raise
            finally:
                duration = time.monotonic() - t0
                logger.info(
                    "tool_call",
                    extra={
                        "tool": tool_name,
                        "status": status,
                        "duration_ms": round(duration * 1000, 1),
                    },
                )
                _TOOL_REQUESTS.labels(tool=tool_name, status=status).inc()
                _TOOL_DURATION.labels(tool=tool_name).observe(duration)
                REQUEST_ID.reset(tok)

        return wrapper

    return decorator


# --- FastMCP setup -------------------------------------------------------------

# Host/port only matter for sse + streamable-http; FastMCP reads them from constructor.
_host = os.environ.get("MAANGO_MCP_HOST", "0.0.0.0")
_port = int(os.environ.get("MAANGO_MCP_PORT", "8000"))

mcp = FastMCP("maango", host=_host, port=_port)
client = MaangoClient()


# --- Action → use-case mapping -------------------------------------------------

# Maps action verbs agents might pass to the canonical use-case fields in our
# domain policy. Policy values are normalised to "allow" / "block" below.
_ACTION_TO_USE_CASE: dict[str, str] = {
    "train": "training",
    "training": "training",
    "scrape": "training",      # bulk content collection defaults to training concern
    "search": "search",
    "index": "search",
    "cache": "search",
    "summarize": "ai_input",
    "inference": "ai_input",
    "ai_input": "ai_input",
}


def _normalize_permission(value: str | None) -> str | None:
    if value is None:
        return None
    v = str(value).lower()
    if v in ("allow", "allowed"):
        return "allow"
    if v in ("block", "blocked"):
        return "block"
    return v


def _evaluate_compliance(policy: dict, action: str, agent_id: str) -> dict:
    """Turn a domain policy + requested action into a compliance decision."""
    if policy.get("error"):
        return {
            "allowed": False,
            "reason_code": "lookup_error",
            "explanation": f"Could not look up policy: {policy.get('message','unknown')}",
            "signals_checked": [],
        }

    if not policy.get("found", False):
        return {
            "allowed": False,
            "reason_code": "no_policy",
            "explanation": (
                "No policy found for this domain in the Maango registry. "
                "Per spec, absence of a policy is not consent — treat as block "
                "and seek permission directly from the site owner."
            ),
            "signals_checked": [],
        }

    stance = policy.get("stance")
    use_cases = policy.get("use_cases") or {}
    bots = policy.get("bots") or {}
    blocked_bots = [b.lower() for b in (bots.get("blocked") or [])]
    allowed_bots = [b.lower() for b in (bots.get("allowed") or [])]

    action_key = action.lower().strip()
    use_case_field = _ACTION_TO_USE_CASE.get(action_key)

    signals = []
    if policy.get("signals"):
        signals = [k for k, v in policy["signals"].items() if v]

    # 1. Bot-level explicit block beats everything.
    if agent_id and agent_id.lower() in blocked_bots:
        return {
            "allowed": False,
            "reason_code": "bot_blocked",
            "explanation": (
                f"Agent '{agent_id}' is explicitly listed in the blocked bots for this domain. "
                f"Access is denied for any action."
            ),
            "stance": stance,
            "bot_status": "blocked",
            "signals_checked": signals,
        }

    # 2. Domain-wide blocks_all_ai stance denies everything.
    if stance == "blocks_all_ai":
        return {
            "allowed": False,
            "reason_code": "stance_blocks_all",
            "explanation": "This domain blocks all AI access (stance: blocks_all_ai).",
            "stance": stance,
            "signals_checked": signals,
        }

    # 3. Per-use-case permission for the mapped field.
    if use_case_field:
        perm = _normalize_permission(use_cases.get(use_case_field))
        if perm == "block":
            return {
                "allowed": False,
                "reason_code": "action_blocked",
                "explanation": (
                    f"Action '{action}' maps to use-case '{use_case_field}', "
                    f"which is blocked by this domain's policy."
                ),
                "stance": stance,
                "use_case": use_case_field,
                "use_case_policy": "block",
                "bot_status": "allowed" if agent_id and agent_id.lower() in allowed_bots else None,
                "signals_checked": signals,
            }
        if perm == "allow":
            return {
                "allowed": True,
                "reason_code": "compliant",
                "explanation": (
                    f"Action '{action}' maps to use-case '{use_case_field}', "
                    f"which is allowed by this domain's policy."
                ),
                "stance": stance,
                "use_case": use_case_field,
                "use_case_policy": "allow",
                "bot_status": "allowed" if agent_id and agent_id.lower() in allowed_bots else None,
                "signals_checked": signals,
            }

    # 4. Fallback: allows_all stance with no specific override.
    if stance == "allows_all":
        return {
            "allowed": True,
            "reason_code": "compliant",
            "explanation": "Domain stance is allows_all and no specific rule blocks this action.",
            "stance": stance,
            "signals_checked": signals,
        }

    # 5. Unknown action or unspecified use-case — be conservative.
    return {
        "allowed": False,
        "reason_code": "unspecified",
        "explanation": (
            f"Action '{action}' does not map to a known use-case, or the domain "
            f"has not declared a policy for this use-case. Conservative default is deny."
        ),
        "stance": stance,
        "signals_checked": signals,
    }


# --- Tools ---------------------------------------------------------------------


@mcp.tool()
@_instrument("check_permission")
async def check_permission(domain: str, action: str, agent_id: str = "") -> str:
    """Check whether an AI agent is permitted to perform a specific action on a given domain.

    Returns a structured compliance decision with allowed (bool), a reason code,
    a human-readable explanation, the domain's stance, and the signals that informed
    the answer. Use this before your agent scrapes, summarizes, trains, or searches
    content from a site.

    Reason codes:
      compliant           — action is explicitly permitted
      action_blocked      — the specific use-case (training/search/ai_input) is blocked
      bot_blocked         — the named agent is explicitly listed as blocked
      stance_blocks_all   — the domain blocks all AI access site-wide
      no_policy           — no policy is on file; treat as block per spec guidance
      unspecified         — the action or use-case is not addressed by the policy
      lookup_error        — the registry could not be reached

    Args:
        domain:   The domain to check (e.g. "nytimes.com").
        action:   One of: train, scrape, summarize, search, index, cache, inference, ai_input.
        agent_id: Optional self-reported agent name (e.g. "GPTBot", "ClaudeBot"). If provided
                  and listed in the domain's blocked-bots list, the decision is bot_blocked.
    """
    policy = await client.lookup_domain(domain)
    decision = _evaluate_compliance(policy, action, agent_id)
    return json.dumps(
        {"domain": domain, "action": action, "agent_id": agent_id or None, **decision},
        indent=2,
    )


@mcp.tool()
@_instrument("lookup_domain")
async def lookup_domain(domain: str) -> str:
    """Look up a domain's AI policy summary from the Maango registry.

    Returns the domain's overall AI stance (blocks_all_ai, selective, allows_all,
    no_policy), per-use-case policies (training, search, inference), blocked/allowed
    bot lists, signal presence (robots.txt, ai.txt, llms.txt), and site metadata.

    Args:
        domain: The domain to look up (e.g. "nytimes.com").
    """
    result = await client.lookup_domain(domain)
    return json.dumps(result, indent=2)


@mcp.tool()
@_instrument("lookup_domain_full")
async def lookup_domain_full(domain: str) -> str:
    """Get full raw policy data for a domain from the Maango registry.

    Returns all parsed policy fields including raw robots.txt rules, ai.txt content,
    llms.txt sections, TDM-Rep data, crawl rules, meta tags, and content signals.
    Much more detailed than lookup_domain.

    Args:
        domain: The domain to look up (e.g. "nytimes.com").
    """
    result = await client.lookup_domain_full(domain)
    return json.dumps(result, indent=2)


@mcp.tool()
@_instrument("lookup_domain_conflicts")
async def lookup_domain_conflicts(domain: str) -> str:
    """Get policy conflicts for a domain from the Maango registry.

    Returns any conflicting signals between a domain's different policy files
    (e.g. robots.txt says one thing, ai.txt says another).

    Args:
        domain: The domain to check for conflicts (e.g. "nytimes.com").
    """
    result = await client.lookup_domain_conflicts(domain)
    return json.dumps(result, indent=2)


@mcp.tool()
@_instrument("search_domains")
async def search_domains(
    query: str,
    stance: str = "",
    limit: int = 20,
    offset: int = 0,
) -> str:
    """Search for domains in the Maango AI policy registry by prefix.

    Returns matching domains with their stance and Tranco rank.

    Args:
        query: Domain prefix to search for (e.g. "news", "google"). Min 2 chars.
        stance: Optional filter. One of: blocks_all_ai, selective, allows_all, no_policy, blocks_training. Leave empty for no filter.
        limit: Results per page (1-100, default 20).
        offset: Pagination offset (default 0).
    """
    result = await client.search_domains(query, stance or None, limit, offset)
    return json.dumps(result, indent=2)


@mcp.tool()
@_instrument("batch_check")
async def batch_check(domains: list[str]) -> str:
    """Compare AI policies across multiple domains using the Maango registry.

    Looks up 2-25 domains at once and returns each domain's stance, use-case
    policies, and bot lists side-by-side.

    Args:
        domains: List of 2-25 domains to compare (e.g. ["nytimes.com", "github.com"]).
    """
    result = await client.batch_check(domains)
    return json.dumps(result, indent=2)


@mcp.tool()
@_instrument("get_changelog")
async def get_changelog(
    domain: str = "",
    change_type: str = "",
    limit: int = 50,
    offset: int = 0,
) -> str:
    """Get AI policy change history from the Maango registry.

    Returns recent policy changes across domains. Filter by domain and/or change type.

    Args:
        domain: Optional domain to filter by (e.g. "nytimes.com"). Leave empty for all.
        change_type: Optional filter. One of: stance_changed, bots_changed, score_changed, signals_added, signals_removed, use_case_changed, new_policy, multiple_changes. Leave empty for all.
        limit: Results per page (1-200, default 50).
        offset: Pagination offset (default 0).
    """
    result = await client.get_changelog(domain or None, change_type or None, limit, offset)
    return json.dumps(result, indent=2)


# --- HTTP routes (sse + streamable-http only) ---------------------------------
#
# These endpoints are not part of the MCP protocol. They are public,
# unauthenticated, and intentionally cheap — used by Docker HEALTHCHECK,
# nginx liveness probes, and Prometheus scrapers.


@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> JSONResponse:
    """Cheap liveness probe — does not call upstream."""
    return JSONResponse({"status": "ok", "service": "maango-mcp", "version": __version__})


@mcp.custom_route("/metrics", methods=["GET"])
async def metrics(_request: Request) -> Response:
    """Prometheus exposition endpoint."""
    return Response(
        generate_latest(_METRICS_REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )


# --- Entry point ---------------------------------------------------------------

_VALID_TRANSPORTS = ("stdio", "sse", "streamable-http")


def main() -> None:
    transport = os.environ.get("MAANGO_MCP_TRANSPORT", "stdio").strip().lower()
    if transport not in _VALID_TRANSPORTS:
        logger.warning(
            "unknown_transport_falling_back_to_stdio",
            extra={"transport": transport, "valid": list(_VALID_TRANSPORTS)},
        )
        transport = "stdio"
    logger.info(
        "starting_server",
        extra={"transport": transport, "host": _host, "port": _port, "version": __version__},
    )
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
