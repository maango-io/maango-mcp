# Contributing to Maango MCP

Thanks for taking the time to contribute. This server gates AI access to the
web — every change ships under that responsibility, so we keep the bar high
for tests and documentation.

## Quick start

```bash
git clone https://github.com/maango-io/maango-mcp.git
cd maango-mcp

# uv handles python version + venv + install in one step.
uv sync --extra dev

# Run the test suite (no network, fully mocked).
uv run pytest -q

# Run the server locally over stdio.
uv run maango-mcp

# Or over SSE for browser/Claude-Desktop testing.
MAANGO_MCP_TRANSPORT=sse uv run maango-mcp
```

If you don't have `uv`: `brew install uv` (macOS) or
`curl -LsSf https://astral.sh/uv/install.sh | sh`.

## Project structure

```
src/maango_mcp/
  server.py     # MCP server, 7 tools, /health, /metrics, JSON logger
  client.py     # async httpx wrapper for api.maango.io, error sanitization
tests/
  test_client.py        # HTTP client (auth, params, error shapes)
  test_decision_tree.py # _evaluate_compliance — every reason code
  test_resilience.py    # 5xx, 401, timeouts, malformed responses
  test_tools.py         # tool registration + each tool's output shape
deploy/
  deploy.sh     # idempotent Hetzner installer
  README.md     # walkthrough
```

## Pull-request checklist

- [ ] Tests cover the change (every new branch in compliance logic, every new
      error case, every new tool). The existing 87 tests pass: `uv run pytest -q`
- [ ] If you add or change a tool, update its docstring — that's what MCP
      clients see.
- [ ] If you add a dependency, justify it in the PR description.
      `prometheus-client` and `httpx` are the only runtime deps for a reason.
- [ ] If you change `client.py` error handling, double-check we're not
      leaking the API key or stack traces.
- [ ] If you change `deploy/deploy.sh`, run `bash -n deploy/deploy.sh`.
- [ ] CI is green (pytest matrix on 3.10/3.11/3.12 + Docker build).

## Style

- Type hints on public functions (we target Python 3.10+).
- One JSON object per stderr log line (use `logger.info("event_name", extra={…})`,
  not f-strings — see `_JsonFormatter` in `server.py`).
- Don't add ORM, frameworks, or async magic without discussion. The server
  is intentionally a thin wrapper over the upstream API.

## Reporting bugs

Open an issue with:

- The version (`maango-mcp --help` or `git rev-parse HEAD`)
- Transport (`stdio` / `sse` / `streamable-http`)
- Steps to reproduce, ideally with the JSON log lines around the failure
  (search for the `req_id` of the failing call)

For security issues, see [SECURITY.md](./SECURITY.md). Don't open a public
issue for vulnerabilities.

## Releases

Releases are tag-driven:

```bash
# bump version in pyproject.toml + src/maango_mcp/server.py
git tag v0.1.1
git push origin v0.1.1
```

Pushing the tag triggers two workflows in parallel:

- [.github/workflows/release.yml](./.github/workflows/release.yml) — runs
  pytest, builds the multi-stage Docker image, pushes
  `ghcr.io/maango-io/maango-mcp:<tag>` and `:latest`, creates a GitHub Release.
- [.github/workflows/publish-pypi.yml](./.github/workflows/publish-pypi.yml)
  — builds sdist + wheel, publishes to PyPI via Trusted Publisher (OIDC,
  no API token). One-time PyPI setup is documented at the top of that file.

## License

By contributing, you agree your contributions are licensed under the MIT
License (see [LICENSE](./LICENSE)).
