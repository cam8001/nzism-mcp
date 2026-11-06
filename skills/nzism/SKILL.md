---
name: nzism
description: Look up controls and guidance in the New Zealand Information Security Manual (NZISM, published by GCSB) through the NZISM MCP server. Use when the user asks what the NZISM says about a topic, needs NZISM control or section references, or is working on New Zealand government information security or compliance (for example cryptography, TLS, cloud, access control, passwords, or system accreditation).
---

# NZISM lookup

Answer NZISM questions from the NZISM MCP server, not from memory. The manual changes between releases, and control wording and IDs matter for compliance work.

## Check the server is connected

This skill needs the `nzism` MCP server. Look for the tools `query_nzism` and `get_nzism_section`. They may appear with a server prefix such as `mcp__nzism__query_nzism`.

If they are missing, tell the user and offer the setup below. Do not answer from memory instead without saying so.

The server is public and read-only. It is a Streamable HTTP endpoint at `https://nzism-mcp.camerontod.com/mcp`. The path must be `/mcp`, because the bare domain returns 404.

Claude Code:

```bash
claude mcp add --transport http nzism https://nzism-mcp.camerontod.com/mcp
```

Add `--scope user` to make it available in every project.

Kiro (`~/.kiro/settings/mcp.json`) and most other clients that accept a remote URL:

```json
{
  "mcpServers": {
    "nzism": {
      "url": "https://nzism-mcp.camerontod.com/mcp"
    }
  }
}
```

Adding an MCP server changes the user's client configuration, so ask before running the command for them.

## Tools

- `query_nzism(query, match_all=False, max_results=...)` searches by keyword. It matches plain substrings in the section breadcrumb and text. Results are ranked by how many query words appear. There is no stemming and no phrase search.
- `get_nzism_section(section_number, max_results=50)` returns every paragraph whose ID starts with the given prefix. `"17.4"` returns the Transport Layer Security section. Use it when you already know the section number.

## How to search well

1. Use short, distinct keywords rather than sentences: `TLS`, `encrypt`, `password`. Substring matching means `encrypt` finds both "encrypt" and "encryption".
2. Search again with synonyms if results are thin. Both "cryptographic" and "encryption" are common in the NZISM, so try each.
3. Use `match_all=True` to narrow a broad term, for example `cloud sovereignty`. Leave it off to widen.
4. Once a search shows the relevant chapter or section, call `get_nzism_section` on that prefix to read the controls in context. Do not rely on a single matching paragraph.
5. Paragraph IDs are not guaranteed to be unique. If two results share an ID, treat them as separate paragraphs.

## Reporting results

- Quote or closely paraphrase the paragraph text, and give the paragraph ID (for example `17.4.1.`) and its breadcrumb so the user can find it.
- Include the online document link when the result provides one. Not every section has a deep link; the rest fall back to the document root, which is expected.
- Keep rationale, control and compliance wording distinct. NZISM controls carry compliance language (MUST, SHOULD, MUST NOT) with specific meanings. Preserve those words exactly and do not soften them.
- If a search returns nothing relevant, say so and report the terms you tried. Do not invent a section reference.
- The index is a snapshot of one NZISM release, not live. For anything that matters (an audit, an accreditation decision), tell the user to confirm against the current document at https://nzism.gcsb.govt.nz/ism-document.

## Limits

- This is search over the published text. It does not assess whether a system complies, and it does not replace advice from the user's security or accreditation team.
- The data covers the NZISM only. It does not include classified material or other government guidance such as the Protective Security Requirements (PSR).
