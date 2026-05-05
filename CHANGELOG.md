# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `/metrics` Prometheus endpoint exposing `maango_mcp_tool_requests_total{tool,status}`
  and `maango_mcp_tool_duration_seconds{tool}` histograms.
- Per-tool-call `req_id` propagated via a contextvar and emitted on every
  log line for cross-component tracing.
- Structured JSON logging on stderr (one object per line, log-shipper friendly).
- `SECURITY.md` (vulnerability disclosure policy) and `CONTRIBUTING.md`
  (development workflow + PR checklist).
- `CHANGELOG.md` (this file).
- Dependabot config for `pip`, `docker`, and `github-actions` ecosystems.
- Release workflow: tag-driven (`v*`), runs tests, builds + pushes the
  Docker image to GHCR, creates a GitHub Release with auto-generated notes.
- PyPI publish workflow: tag-driven (`v*`), builds sdist + wheel, uploads
  via Trusted Publisher (OIDC). One-time PyPI configuration documented in
  the workflow header.

### Changed

- Multi-stage Dockerfile — runtime image no longer ships `pip` / `uv`,
  cuts ~150 MB.
- Upstream error messages returned to MCP clients are now sanitized
  (HTML stripped, length-capped at 200 chars) to prevent leaking stack
  traces or markup. The full upstream payload is still logged at WARNING
  level for operators.

## [0.1.0] — 2026-04-24

Initial published version. Source repo migrated from a private collaborator
fork to `maango-io/maango-mcp` (via interim transit through `7mehul/maango-mcp`).

### Added

- 7 MCP tools: `check_permission`, `lookup_domain`, `lookup_domain_full`,
  `lookup_domain_conflicts`, `search_domains`, `batch_check`,
  `get_changelog`.
- Three transports: `stdio`, `sse`, `streamable-http` (selected via
  `MAANGO_MCP_TRANSPORT`).
- `_evaluate_compliance` 7-branch decision tree covering bot-blocks,
  stance, per-use-case allow/block, fallbacks, and unspecified actions.
- Action → use-case mapping for `train / training / scrape / search /
  index / cache / summarize / inference / ai_input`.
- Hetzner deploy script (`deploy/deploy.sh`) — idempotent Docker + nginx
  + certbot installer with per-IP rate limits and `--env-file` secrets.
- `/health` endpoint + Docker `HEALTHCHECK`.
- 87-test suite covering client, decision tree, resilience, and tool
  output shapes.
- MIT license.
- GitHub Actions CI: pytest matrix on Python 3.10/3.11/3.12 + Docker
  buildx smoke test.
- `uv.lock` committed for reproducible builds.

[Unreleased]: https://github.com/maango-io/maango-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/maango-io/maango-mcp/releases/tag/v0.1.0
