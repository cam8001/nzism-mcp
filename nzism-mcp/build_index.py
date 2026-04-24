#!/usr/bin/env python3
"""
Build script: pre-processes the NZISM XML and deeplinks into a single JSON index
for fast Lambda cold starts. Run this before deploying.

Usage: uv run python build_index.py
"""

import json
import re
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
XML_PATH = DATA_DIR / "nzism.xml"
DEEPLINKS_PATH = DATA_DIR / "deeplinks.json"
INDEX_PATH = DATA_DIR / "nzism_index.json"


def strip_html(html: str) -> str:
    """Remove HTML tags and decode entities, returning plain text."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def build_breadcrumb(chapter: str, section: str, subsection: str, block: str) -> str:
    """Build a hierarchical breadcrumb from the XML element titles."""
    parts = [p for p in [chapter, section, subsection, block] if p]
    return " > ".join(parts)


def parse_xml(xml_path: Path) -> list[dict]:
    """Parse the NZISM XML into a flat list of sections."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    sections = []

    for chapter in root.findall("chapter"):
        ch_title = chapter.get("title", "")
        for section in chapter.findall("section"):
            sec_title = section.get("title", "")
            for subsection in section.findall("subsection"):
                sub_title = subsection.get("title", "")

                for element in subsection:
                    if element.tag == "paragraph":
                        para_title = element.get("title", "")
                        text = strip_html(element.text or "")
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
                            text = strip_html(para.text or "")
                            if text:
                                sections.append({
                                    "id": para_title,
                                    "breadcrumb": build_breadcrumb(ch_title, sec_title, sub_title, blk_title),
                                    "text": text,
                                })

    return sections


def main():
    if not XML_PATH.exists():
        print(f"ERROR: {XML_PATH} not found. Place the NZISM XML in data/nzism.xml")
        return

    print(f"Parsing {XML_PATH}...")
    sections = parse_xml(XML_PATH)
    print(f"  Parsed {len(sections)} sections")

    # Load deeplinks if available
    deeplinks = {}
    if DEEPLINKS_PATH.exists():
        with open(DEEPLINKS_PATH) as f:
            deeplinks = json.load(f)
        print(f"  Loaded {len(deeplinks)} deeplinks")

    # Write combined index
    index = {"sections": sections, "deeplinks": deeplinks}
    with open(INDEX_PATH, "w") as f:
        json.dump(index, f, separators=(",", ":"))

    size_kb = INDEX_PATH.stat().st_size / 1024
    print(f"  Written {INDEX_PATH} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
