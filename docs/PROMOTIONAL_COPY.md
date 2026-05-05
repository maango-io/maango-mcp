# Promotional copy

Copy-paste-ready listings for every place you'd submit Maango MCP. Keep them
in this file so future versions stay aligned.

> Replace `https://your.demo.video/maango-mcp.mp4` with a real demo link
> before submitting anywhere — directories tend to convert ~3× better with
> a 30-second screen recording.

---

## Elevator pitch (one sentence, ≤180 chars)

> The permissions layer for AI agents on the web — pre-flight `check_permission(domain, action)` aggregating robots.txt, ai.txt, llms.txt, TDM-Rep, and ToS for 1M+ domains.

## Two-line pitch

> AI training and scraping is now a legal minefield (NYT v OpenAI, EU AI Act, Reddit licensing). Maango MCP lets your agent ask one question — *"is this allowed?"* — and gets a canonical answer aggregated from every machine-readable AI-policy standard, across 1M+ domains.

## Three-paragraph pitch

> **Maango MCP** is a Model Context Protocol server that gates AI access to the open web. Before your agent scrapes, summarises, or trains on a URL, it calls `check_permission(domain, action, agent_id?)` and gets back `allowed: true/false`, a structured reason code, and the signals the answer was based on.
>
> Site owners increasingly publish machine-readable opt-outs across **8 different standards** — `robots.txt`, `ai.txt`, `llms.txt`, TDM-Rep, meta tags, ai-bots HTTP header, ToS clauses, and X-Robots-Tag. Maango aggregates all of them across 1M+ domains and normalises them into one canonical answer. Your agent stops shipping its own parser per standard.
>
> Three transports (`stdio`, `sse`, `streamable-http`), seven tools (`check_permission`, `lookup_domain`, `lookup_domain_full`, `lookup_domain_conflicts`, `search_domains`, `batch_check`, `get_changelog`), one hosted endpoint at `https://mcp.maango.io/sse`. MIT-licensed, Docker image at `ghcr.io/7mehul/maango-mcp`, `pip install maango-mcp`.

---

## awesome-mcp-servers entry

For [punkpeye/awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers) — likely category: **🌐 Browser Automation** or **📑 Compliance / Policy** (open a PR adding the line under the most fitting one):

```markdown
- [7mehul/maango-mcp](https://github.com/7mehul/maango-mcp) 🐍 - Permissions layer for AI agents. Pre-flight `check_permission(domain, action)` aggregating robots.txt, ai.txt, llms.txt, TDM-Rep, and ToS into one canonical "is this allowed?" answer across 1M+ domains.
```

For [appcypher/awesome-mcp-servers](https://github.com/appcypher/awesome-mcp-servers) (alternative list, table format):

```markdown
| [7mehul/maango-mcp](https://github.com/7mehul/maango-mcp) | AI policy gate for agent web access — one call, eight standards, a million domains. | Python | MIT |
```

---

## Smithery / mcp.so / Glama submission

Most of these auto-ingest from GitHub once the repo is public. If they ask
for a manifest:

- **Name:** `maango-mcp`
- **Display name:** Maango MCP — AI Web Permissions
- **Description:** *(use the two-line pitch above)*
- **Tags:** `permissions`, `compliance`, `web-scraping`, `ai-policy`, `robots-txt`, `ai-txt`, `llms-txt`, `tdm-rep`, `legal`, `governance`
- **License:** MIT
- **Homepage:** https://maango.io
- **Repository:** https://github.com/7mehul/maango-mcp
- **Hosted endpoint:** https://mcp.maango.io/sse
- **Install command (local):** `pip install maango-mcp` or `docker pull ghcr.io/7mehul/maango-mcp:latest`

---

## Anthropic MCP Directory submission

When/if Anthropic accepts community submissions to their official directory:

- **Use case:** Compliance / governance
- **Hero example:** *"Check if I can scrape nytimes.com for training data"*
- **Why this matters:** As AI agents proliferate, every site is publishing opt-outs in different formats. Without a permissions layer, every agent author has to ship their own parser, re-implement the same legal-grey-area heuristics, and absorb the liability. Maango is one HTTP call.

---

## Hacker News / Show HN

**Title (≤80 chars):**
```
Show HN: Maango MCP – Pre-flight AI permissions check across 1M+ domains
```

**Body:**

> Hi HN — I built an MCP server that aggregates eight different AI-policy standards (robots.txt, ai.txt, llms.txt, TDM-Rep, meta tags, ai-bots header, ToS clauses, X-Robots-Tag) across 1M+ domains into one tool call.
>
> Before your agent scrapes / summarises / trains on a URL, it calls `check_permission(domain, action, agent_id?)` and gets back `allowed: true/false`, a structured reason code, and the signals that informed the answer. The seven-branch decision tree is open source and 87 tests cover it.
>
> Three transports (stdio for Claude Desktop / Cursor / Cline, SSE + streamable-HTTP for hosted), MIT-licensed, multi-stage Docker image on GHCR, `pip install maango-mcp`, hosted free at https://mcp.maango.io/sse.
>
> The motivation: every site is opting out in different formats. NYT v OpenAI is teaching the industry that "I scraped what robots.txt allowed" is not a defense if the site also published an ai.txt blocking AI use specifically. Building that compliance layer per agent is weeks of work; it should be a single MCP call.
>
> Repo, docs, and decision tree: https://github.com/7mehul/maango-mcp

---

## Twitter / X launch thread

**1/** Maango MCP is live. One MCP tool call to check whether your AI agent is allowed to scrape, summarise, or train on any URL. https://github.com/7mehul/maango-mcp

**2/** Site owners now publish opt-outs in 8 different formats — robots.txt, ai.txt, llms.txt, TDM-Rep, ai-bots header, X-Robots-Tag, ToS clauses, meta tags. Aggregating them per agent is weeks of work.

**3/** `check_permission(domain, action)` gives you one canonical answer aggregated across all 8 standards on 1M+ domains. Plus reason codes (`compliant`, `bot_blocked`, `stance_blocks_all`, …) so your agent can tell the user *why* it didn't fetch.

**4/** Hosted free at `mcp.maango.io/sse`. Self-host via `docker pull ghcr.io/7mehul/maango-mcp:latest` or `pip install maango-mcp`. MIT, 87 tests, Prometheus metrics. PRs welcome.

---

## LinkedIn announcement

> Just shipped **Maango MCP** — a Model Context Protocol server that gives AI agents a one-call answer to "am I allowed to access this site?"
>
> The problem: NYT v OpenAI, the EU AI Act, Reddit's licensing fight, and now Stack Overflow's TOS update have made AI training and scraping a real legal liability. Sites are publishing opt-outs in 8 different machine-readable formats, and nobody is parsing all of them.
>
> Maango aggregates them across 1,000,000+ domains and exposes the answer as 7 MCP tools. Your agent calls `check_permission(domain, action)` and gets back `allowed: true/false` plus a structured reason. That's the entire integration.
>
> Hosted free at mcp.maango.io. MIT-licensed. Docker image, PyPI, GHCR. Built on the spec at modelcontextprotocol.io so it works with Claude Desktop, Cursor, Cline, Zed, and any other MCP client out of the box.
>
> Code: https://github.com/7mehul/maango-mcp
> Docs: https://maango.io/docs

---

## Image / OG-card prompt

If you generate a social card via Figma / DALL-E / etc, the brief is:

> Minimal, technical aesthetic. The text "Maango MCP — Permissions for AI agents" centered. Below it, a stylised diagram: an arrow labelled `check_permission()` pointing from a generic agent silhouette into a vault icon labelled "1M domains × 8 standards", with another arrow returning carrying a green "allowed" tag. Mango-orange accent color, Inter or SF Pro font. 1200×630.
