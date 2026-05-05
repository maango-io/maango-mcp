# Security Policy

## Supported Versions

The most recent minor release of `maango-mcp` is supported with security
fixes. Older versions are best-effort.

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Email **security@maango.io** with:

- A description of the vulnerability
- Steps to reproduce (proof of concept welcome)
- The affected version / commit hash
- Any suggested mitigation, if you have one

You can expect:

- Acknowledgement within **2 business days**
- An initial assessment within **5 business days**
- A patch release on a coordinated disclosure timeline (typically within
  30 days for high-severity issues)

If you do not receive a response, please follow up — your report may have
been caught in a spam filter.

## Scope

In scope:

- This repository (`maango-io/maango-mcp`) — the MCP server, its Docker image,
  and the deploy script.
- Configuration that ships in this repo (Dockerfile, deploy/deploy.sh,
  nginx config templates).

Out of scope (report to the relevant project instead):

- The upstream Maango REST API at `api.maango.io` — report to
  `security@maango.io` referencing the API.
- Vulnerabilities in third-party dependencies — report upstream first;
  we'll track via Dependabot.
- Denial-of-service via traffic floods that don't involve a server-side
  bug (the deployed instance has rate limits; see [deploy/README.md](./deploy/README.md)).

## Secrets handling

- `MAANGO_API_KEY` is the only secret this server holds.
- It is loaded from environment variables — never logged, never returned
  in responses, never written to files except `/etc/maango-mcp.env`
  (created by `deploy/deploy.sh` with mode `0600`).
- Upstream error messages are sanitized (HTML stripped, length-capped)
  before being returned to MCP clients to avoid leaking stack traces.

If you believe a key has been logged or returned to a client, treat it
as a confirmed leak and report immediately.
