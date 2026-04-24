"""
NZISM MCP Server — FastAPI app for Lambda Web Adapter.

Based on the aws-samples reference implementation:
https://github.com/aws-samples/sample-serverless-mcp-servers/blob/main/stateless-mcp-on-lambda-python/

Lambda Web Adapter runs uvicorn inside Lambda and proxies requests to it,
enabling SSE streaming for the MCP Streamable HTTP transport.
"""

import json
from pathlib import Path

from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP

# Load the pre-built JSON index once (persists across warm invocations)
INDEX_PATH = Path(__file__).parent / "data" / "nzism_index.json"

with open(INDEX_PATH) as f:
    _index = json.load(f)

SECTIONS: list[dict] = _index["sections"]
DEEPLINKS: dict[str, str] = _index["deeplinks"]

print(f"Loaded {len(SECTIONS)} sections, {len(DEEPLINKS)} deeplinks")

DEFAULT_MAX_RESULTS = 20
BASE_URL = "https://nzism.gcsb.govt.nz/ism-document"


def format_result(section: dict) -> str:
    """Format a single section result with citation."""
    lines = [f"[{section['id']}] {section['breadcrumb']}"]
    lines.append(section["text"])
    anchor = DEEPLINKS.get(section["id"])
    if anchor:
        lines.append(f"Source: {BASE_URL}#{anchor} (ref: {section['id']})")
    else:
        lines.append(f"Source: {BASE_URL} (ref: {section['id']})")
    return "\n".join(lines)


# Create the MCP server
mcp = FastMCP("nzism", stateless_http=True, host="0.0.0.0", port=8080)


@mcp.tool()
def query_nzism(
    query: str,
    match_all: bool = False,
    max_results: int = DEFAULT_MAX_RESULTS,
) -> str:
    """
    Search the NZISM (New Zealand Information Security Manual) for sections
    matching the given keywords.

    By default, sections are ranked by how many keywords they match (OR mode).
    Set match_all=True to require all keywords to appear (AND mode).

    Args:
        query: Free text search query. Multiple words are matched independently.
        match_all: If True, ALL keywords must appear (AND). If False (default),
                   results are ranked by number of matching keywords (OR).
        max_results: Maximum number of results to return (default 20).

    Returns:
        Matching NZISM sections with their reference IDs, breadcrumb paths,
        and source links.
    """
    keywords = query.lower().split()
    if not keywords:
        return "Please provide a search query."

    scored = []
    for section in SECTIONS:
        searchable = f"{section['breadcrumb']} {section['text']}".lower()
        hits = sum(1 for kw in keywords if kw in searchable)
        if match_all and hits < len(keywords):
            continue
        if hits > 0:
            scored.append((hits, section))

    if not scored:
        return f"No NZISM sections found matching: {query}"

    scored.sort(key=lambda x: x[0], reverse=True)
    total = len(scored)
    scored = scored[:max_results]

    lines = [f"Found {total} NZISM sections matching '{query}' (showing {len(scored)}):"]
    lines.append("")
    for hits, section in scored:
        lines.append(format_result(section))
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
def get_nzism_section(section_number: str, max_results: int = 50) -> str:
    """
    Retrieve all NZISM paragraphs under a given section number prefix.

    Use this when you know the section number (e.g. "17.4" for TLS,
    "16.1" for access control). Returns all paragraphs whose ID starts
    with the given prefix.

    Args:
        section_number: Section number prefix, e.g. "17.4" or "22.1".
                        Do not include a trailing dot.
        max_results: Maximum number of paragraphs to return (default 50).

    Returns:
        All paragraphs in the section with their reference IDs, breadcrumb
        paths, and source links.
    """
    prefix = section_number.strip().rstrip(".")
    prefix_dot = prefix + "."

    matches = [s for s in SECTIONS if s["id"].startswith(prefix_dot)]

    if not matches:
        return f"No NZISM paragraphs found under section {section_number}"

    total = len(matches)
    matches = matches[:max_results]

    lines = [f"Found {total} paragraphs under section {section_number} (showing {len(matches)}):"]
    lines.append("")
    for section in matches:
        lines.append(format_result(section))
        lines.append("")

    return "\n".join(lines)


# FastAPI app with MCP mounted — Lambda Web Adapter runs this under uvicorn
app = FastAPI(title="NZISM MCP", lifespan=lambda app: mcp.session_manager.run())
app.mount("/", mcp.streamable_http_app())
