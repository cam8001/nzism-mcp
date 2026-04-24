"""
NZISM MCP Server

Provides keyword search over the New Zealand Information Security Manual (NZISM)
XML document. Returns matching sections for an LLM to interpret and synthesise.
"""

import json
import re
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Path to the NZISM XML file, relative to this script
NZISM_XML_PATH = Path(__file__).parent / "data" / "nzism.xml"

# Optional deeplinks mapping file: JSON object mapping section IDs to anchor fragments
# e.g. {"2.2.3.": "Paragraph-12345", "22.1.": "Section-17217"}
DEEPLINKS_PATH = Path(__file__).parent / "data" / "deeplinks.json"

# Maximum number of results to return per query
DEFAULT_MAX_RESULTS = 20

# Base URL for NZISM online document
BASE_URL = "https://nzism.gcsb.govt.nz/ism-document"


def strip_html(html: str) -> str:
    """Remove HTML tags and decode entities, returning plain text."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = unescape(text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_breadcrumb(chapter: str, section: str, subsection: str, block: str) -> str:
    """Build a hierarchical breadcrumb from the XML element titles."""
    parts = [p for p in [chapter, section, subsection, block] if p]
    return " > ".join(parts)


def load_nzism(xml_path: Path) -> list[dict]:
    """
    Parse the NZISM XML into a flat list of searchable sections.

    Each section is a dict with:
      - id: the paragraph title (e.g. "16.1.35.")
      - breadcrumb: hierarchical path (e.g. "16. Access Control > 16.1. ...")
      - text: plain text content of the paragraph
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    sections = []

    for chapter in root.findall("chapter"):
        ch_title = chapter.get("title", "")
        for section in chapter.findall("section"):
            sec_title = section.get("title", "")
            for subsection in section.findall("subsection"):
                sub_title = subsection.get("title", "")

                # Paragraphs can be direct children of subsection or nested in blocks
                for element in subsection:
                    if element.tag == "paragraph":
                        para_title = element.get("title", "")
                        raw = element.text or ""
                        text = strip_html(raw)
                        if text:
                            sections.append({
                                "id": para_title,
                                "breadcrumb": build_breadcrumb(ch_title, sec_title, sub_title, ""),
                                "text": text,
                            })

                    elif element.tag == "block":
                        blk_title = element.get("title", "")
                        for para in element.findall("paragraph"):
                            para_title = para.get("title", "")
                            raw = para.text or ""
                            text = strip_html(raw)
                            if text:
                                sections.append({
                                    "id": para_title,
                                    "breadcrumb": build_breadcrumb(ch_title, sec_title, sub_title, blk_title),
                                    "text": text,
                                })

    return sections


def format_result(section: dict, deeplinks: dict) -> str:
    """Format a single section result with citation."""
    lines = []
    lines.append(f"[{section['id']}] {section['breadcrumb']}")
    lines.append(section["text"])
    anchor = deeplinks.get(section["id"])
    if anchor:
        lines.append(f"Source: {BASE_URL}#{anchor} (ref: {section['id']})")
    else:
        lines.append(f"Source: {BASE_URL} (ref: {section['id']})")
    return "\n".join(lines)


# Load the NZISM data once at startup.
# Prefer the pre-built JSON index (fast); fall back to XML parsing if not found.
INDEX_PATH = Path(__file__).parent / "data" / "nzism_index.json"

if INDEX_PATH.exists():
    print(f"Loading pre-built index from {INDEX_PATH}...")
    with open(INDEX_PATH) as f:
        _index = json.load(f)
    SECTIONS = _index["sections"]
    DEEPLINKS: dict[str, str] = _index["deeplinks"]
    print(f"Loaded {len(SECTIONS)} sections, {len(DEEPLINKS)} deeplinks.")
else:
    print(f"No index found. Parsing XML from {NZISM_XML_PATH}...")
    SECTIONS = load_nzism(NZISM_XML_PATH)
    print(f"Loaded {len(SECTIONS)} sections from XML.")

    DEEPLINKS: dict[str, str] = {}
    if DEEPLINKS_PATH.exists():
        with open(DEEPLINKS_PATH) as f:
            DEEPLINKS = json.load(f)
        print(f"Loaded {len(DEEPLINKS)} deeplinks.")

    print("Tip: run 'uv run python build_index.py' to generate the index for faster startup.")

# Create the MCP server
mcp = FastMCP("nzism")


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

    # Score each section by number of keyword matches
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

    # Sort by number of keyword hits (descending)
    scored.sort(key=lambda x: x[0], reverse=True)

    total = len(scored)
    scored = scored[:max_results]

    lines = [f"Found {total} NZISM sections matching '{query}' (showing {len(scored)}):"]
    lines.append("")
    for hits, section in scored:
        lines.append(format_result(section, DEEPLINKS))
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
    # Normalise: ensure we match "17.4." prefix (with trailing dot)
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
        lines.append(format_result(section, DEEPLINKS))
        lines.append("")

    return "\n".join(lines)


def main():
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
