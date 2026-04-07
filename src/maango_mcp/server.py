"""Maango MCP Server — AI policy lookup tools for Claude and other agents."""

import json
import logging
import sys

from mcp.server.fastmcp import FastMCP

from .client import MaangoClient

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger("maango_mcp")

mcp = FastMCP("maango")
client = MaangoClient()


@mcp.tool()
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


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
