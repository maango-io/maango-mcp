# Maango MCP Server

[![CI](https://github.com/maango-io/maango-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/maango-io/maango-mcp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Docker (GHCR)](https://img.shields.io/badge/docker-ghcr.io%2Fmaango--io%2Fmaango--mcp-2496ed)](https://github.com/maango-io/maango-mcp/pkgs/container/maango-mcp)

> **The permissions layer for AI agents on the web.** Before your agent scrapes, summarises, trains on, or otherwise uses content from a website, ask Maango what's allowed. One call, canonical answer.

## Why

Every site that publishes a `robots.txt`, `ai.txt`, `llms.txt`, TDM-Rep header, or AI-specific ToS clause is telling agents what they can and can't do. Today no one parses all eight standards. NYT, Reddit, and Stack Overflow are suing over training data; the EU AI Act now requires opt-out compliance. Building this gate from scratch is weeks of work per agent.

Maango aggregates **1,000,000+ domains × 8 AI-policy standards** into one canonical answer. Your agent calls `check_permission(domain, action)` and gets back `allowed: true/false` + a structured reason. That's it.

- **Hosted endpoint:** `https://mcp.maango.io/sse` (free, no key required)
- **Protocol:** [Model Context Protocol](https://modelcontextprotocol.io)
- **Registry coverage:** 1,000,000+ domains, 8 AI-policy standards aggregated
- **Transports:** `stdio` (local), `sse` + `streamable-http` (remote)
- **Image:** [`ghcr.io/maango-io/maango-mcp`](https://github.com/maango-io/maango-mcp/pkgs/container/maango-mcp)
- **Package:** [`pip install maango-mcp`](https://pypi.org/project/maango-mcp/)

## Tools exposed

| Tool | What it does |
|---|---|
| `check_permission(domain, action, agent_id?)` | Decide in one call whether an action is allowed. Returns `allowed` + reason code + explanation + stance + signals. |
| `lookup_domain(domain)` | Summary of a domain's AI policy — stance, use-cases, bots, signals. |
| `lookup_domain_full(domain)` | Full raw policy data including robots.txt, ai.txt, llms.txt, TDM-Rep, meta tags. |
| `lookup_domain_conflicts(domain)` | Cross-signal conflicts (e.g. robots.txt vs ToS). |
| `search_domains(query, stance?, limit?, offset?)` | Prefix search the registry with optional stance filter. |
| `batch_check(domains[])` | Compare policies across 2–25 domains side by side. |
| `get_changelog(domain?, change_type?, limit?, offset?)` | Policy change history. |

## Reason codes returned by `check_permission`

- `compliant` — action explicitly permitted
- `action_blocked` — the specific use-case (training/search/ai_input) is blocked
- `bot_blocked` — the named `agent_id` is on the domain's blocked-bots list
- `stance_blocks_all` — domain blocks all AI access site-wide
- `no_policy` — no policy on file; conservative default is deny
- `unspecified` — action or use-case not addressed by the policy
- `lookup_error` — registry could not be reached

## Installation

### Claude Desktop (remote, recommended)

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "maango": {
      "url": "https://mcp.maango.io/sse"
    }
  }
}
```

Restart Claude Desktop. Ask: *"Check if I can scrape nytimes.com for training data."*

### Cursor

`Settings → MCP → Add new MCP Server`:

```json
{
  "maango": {
    "url": "https://mcp.maango.io/sse"
  }
}
```

### Cline / Zed / any MCP client

Point them at `https://mcp.maango.io/sse`. No auth required for the hosted endpoint.

### Local development (stdio)

```bash
git clone https://github.com/maango-io/maango-mcp.git
cd maango-mcp
uv venv && source .venv/bin/activate
uv pip install -e .
cp .env.example .env          # optionally add MAANGO_API_KEY for higher rate limits
maango-mcp                    # runs with stdio transport
```

Then in Claude Desktop:

```json
{
  "mcpServers": {
    "maango": {
      "command": "maango-mcp"
    }
  }
}
```

## Self-hosting

Any platform that can run a Python HTTP service works. Quick Docker path:

```bash
docker build -t maango-mcp .
docker run -p 8000:8000 \
  -e MAANGO_API_KEY=maango_sk_xxx \
  -e MAANGO_MCP_TRANSPORT=sse \
  maango-mcp
```

Environment variables:

| Var | Default | Purpose |
|---|---|---|
| `MAANGO_MCP_TRANSPORT` | `stdio` | `stdio` \| `sse` \| `streamable-http` |
| `MAANGO_MCP_HOST` | `0.0.0.0` | Bind address (remote transports only) |
| `MAANGO_MCP_PORT` | `8000` | Bind port (remote transports only) |
| `MAANGO_API_BASE_URL` | `https://api.maango.io` | Maango REST API base URL |
| `MAANGO_API_KEY` | _(none)_ | Optional bearer token for higher rate limits |

## How it works

```
┌────────────────┐     MCP (sse/streamable-http)     ┌─────────────────┐
│ Claude Desktop │ ◄───────────────────────────────► │  mcp.maango.io  │
│  Cursor, …     │                                   │  (this server)  │
└────────────────┘                                   └────────┬────────┘
                                                              │ HTTPS
                                                              ▼
                                                     ┌─────────────────┐
                                                     │  api.maango.io  │
                                                     │  (REST, 1M      │
                                                     │   domains)      │
                                                     └─────────────────┘
```

The MCP server is a thin wrapper. The real data lives in the Maango REST API. We normalise the response into MCP-friendly tool output and handle the action → use-case mapping (e.g. `"scrape"` → training policy check).

## Observability

The server exposes two HTTP endpoints when running on `sse` or
`streamable-http` transports (not `stdio` — there's no port to bind):

- `GET /health` — cheap liveness probe, no upstream call. Used by
  Docker `HEALTHCHECK`, nginx, and uptime monitors.
- `GET /metrics` — Prometheus exposition. Tracks
  `maango_mcp_tool_requests_total{tool,status}` and
  `maango_mcp_tool_duration_seconds{tool}` (histogram).

Logs are emitted as one JSON object per stderr line with a per-tool-call
`req_id` that propagates through the client and decision-tree. Pipe stderr
to your log shipper of choice (Loki / Datadog / CloudWatch).

## Development

See [CONTRIBUTING.md](./CONTRIBUTING.md) for the full workflow. Quick start:

```bash
uv sync --extra dev
uv run pytest -q
uv run maango-mcp                                # stdio
MAANGO_MCP_TRANSPORT=sse uv run maango-mcp       # SSE on :8000
```

Security disclosures: see [SECURITY.md](./SECURITY.md).

## Roadmap (not in v0.1)

- Web Bot Auth signature verification
- Capability-token issuance (Biscuits / Macaroons)
- Payment-required flow via x402
- Receipt IDs with tamper-evident Merkle proof
- Real-time policy negotiation (Phase 3)

The roadmap is shaped by what users actually need — see
[Issues](https://github.com/maango-io/maango-mcp/issues) for the live list.

## Contributing

If you find this useful:

- ⭐ Star the repo — that's how more agents find it.
- 🐛 [Open an issue](https://github.com/maango-io/maango-mcp/issues/new) for bugs, missing domains, or anything in a tool's output that surprised you. Include the `req_id` from the JSON log line if you have it.
- 💡 Have a use case the current 7 tools don't cover? File an issue with a *real* example — that beats abstract feature requests every time.
- 🛠 PRs welcome — see [CONTRIBUTING.md](./CONTRIBUTING.md) for the dev workflow and PR checklist.
- 🔒 Security disclosures: [SECURITY.md](./SECURITY.md). Email instead of opening an issue.

## Links

- Main site: https://maango.io
- API docs: https://maango.io/docs
- Spec: https://github.com/maango-io/agent-permissions
- Issues: https://github.com/maango-io/maango-mcp/issues
- Changelog: [CHANGELOG.md](./CHANGELOG.md)

## License

MIT — see [LICENSE](./LICENSE).
