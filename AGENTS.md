# AGENTS.md

Orientation for AI agents and new contributors. `CLAUDE.md` imports this file; Kiro and other tools read it directly.

## What this is

An MCP server for keyword search over the New Zealand Information Security Manual (NZISM, published by GCSB). Two tools: `query_nzism` (ranked keyword search) and `get_nzism_section` (all paragraphs under a section prefix such as `17.4`). Data is public; nothing classified is included.

Live endpoint: `https://nzism-mcp.camerontod.com/mcp` (Streamable HTTP). The path must be `/mcp`; the bare domain returns 404.

## Layout

```
nzism-mcp/                 Python package (uv, Python 3.13+)
  server.py                Local stdio MCP server (FastMCP)
  build_index.py           XML + deeplinks.json -> data/nzism_index.json
  update.sh                Refresh data from a downloaded XML (see "Updating the NZISM data")
  data/nzism.xml           Source document (committed)
  data/deeplinks.json      Paragraph ID -> online-document anchor (committed)
  data/nzism_index.json    Built index, loaded at startup (committed)
  data/README.md           Records the NZISM version and download date
nzism-mcp-cdk/             CDK (TypeScript) stack: CloudFront -> WAF -> API Gateway -> Lambda
  lib/nzism-mcp-cdk-stack.ts
  src/lambda/nzism-mcp/server.py   Lambda copy of the server (FastAPI + FastMCP)
```

## Commands

```bash
# Local server
cd nzism-mcp && uv sync && uv run python server.py

# Rebuild the index from data/nzism.xml
cd nzism-mcp && uv run python build_index.py

# Update data after a new NZISM release (XML must be downloaded in a browser)
cd nzism-mcp && ./update.sh --check ~/Downloads/nzism.xml
cd nzism-mcp && ./update.sh ~/Downloads/nzism.xml

# Infra
cd nzism-mcp-cdk && npm install && npx cdk synth     # safe, no AWS changes
cd nzism-mcp-cdk && npx cdk diff                      # read-only
cd nzism-mcp-cdk && npx cdk deploy                    # changes the live service
```

## Updating the NZISM data

Use the `update-nzism` skill (`.claude/skills/update-nzism/SKILL.md`) or follow these steps:

1. Download the XML in a browser from <https://nzism.gcsb.govt.nz/ism-document/xml>. `curl` gets an Incapsula bot-protection page; `update.sh` detects that and stops. Do not try to bypass the protection.
2. `./update.sh --check <file>` and read the summary (sections added/removed/changed, deeplink coverage).
3. `./update.sh <file>` to apply. This overwrites `data/nzism.xml` and `data/nzism_index.json`.
4. Edit `data/README.md`: version, month, download date.
5. If the summary says new sections lack deeplinks, `data/deeplinks.json` is stale. There is no scraper; anchors come from the HTML document at <https://nzism.gcsb.govt.nz/ism-document>. Say so rather than guessing IDs.
6. Review `git diff --stat`, commit, then deploy (ask the owner first; see Safety).

## Things that will trip you up

- **Server logic is duplicated.** `nzism-mcp/server.py` (local) and `nzism-mcp-cdk/src/lambda/nzism-mcp/server.py` (Lambda) each contain their own copy of `query_nzism`, `get_nzism_section`, and `format_result`. Change one, change the other. The Lambda copy only reads the index; the local one can fall back to parsing the XML.
- **The CDK stack copies the index at synth time** from `nzism-mcp/data/nzism_index.json` into `nzism-mcp-cdk/src/lambda/nzism-mcp/data/` (gitignored). Rebuild the index before `cdk synth`/`deploy` or you ship stale data.
- **`deeplinks.json` is partial by design.** It covers about 1,430 of about 3,990 sections. Missing anchors fall back to a link to the document root. Judge staleness by whether new sections lack a link, not by total coverage.
- **IDs are not unique.** `build_index.py` parses ~3,991 paragraphs but there are 3,989 distinct IDs. Do not assume ID uniqueness.
- **Search is plain substring matching** over `breadcrumb + text`, scored by the number of query words that appear. There is no stemming or phrase search. `get_nzism_section` is a prefix match on the paragraph ID (`"17.4"` becomes `"17.4."`).
- **XML shape:** root is `<xml>`, then `chapter > section > subsection > (paragraph | block > paragraph)`. Paragraph text is HTML inside CDATA; `build_index.py` strips it.
- **Region is pinned to us-east-1** because the CloudFront-scoped WAF requires it. Docker must be running for `PythonFunction` bundling.
- **Known bug, unverified in a deploy:** the custom-domain "DNS already exists" guard in the stack calls `dns.resolve4Sync`, which is not a Node.js API. The call throws and is swallowed by the `catch`, so the guard likely never fires.
- **No automated tests.** `nzism-mcp-cdk/test/` holds only the CDK template stub, and `jest` runs nothing meaningful. After changing search code, check manually with a few queries (`query_nzism "TLS"`, `get_nzism_section "17.4"`).

## Safety

- The endpoint is public and in production. Do not run `cdk deploy`, `cdk destroy`, or change the WAF, CloudFront, API Gateway, or DNS without the owner's explicit go-ahead. `cdk synth` and `cdk diff` are fine.
- Do not delete or weaken protections: the WAF rate limit (1000 requests per 5 minutes per IP), HTTPS-only viewer policy, log retention.
- Before changing anything that makes the service reachable differently (new routes, auth changes, new ingress), follow the owner's security guidance for exposure.
- `cdk.context.json` holds account-specific values and is gitignored. Never commit it; use `cdk.context.example.json` as the template.
- Treat downloaded XML as untrusted input: keep it out of the repo until it validates (`update.sh` does this), and do not run interpreters from inside a directory of downloaded files.

## Conventions

- Python: uv for everything (`uv run`, `uv sync`); `.python-version` pins the interpreter.
- Commit messages: short imperative summary, as in `git log`.
- Keep READMEs in sync with behaviour: root `README.md` (client setup, update steps), `nzism-mcp/data/README.md` (data provenance), `nzism-mcp-cdk/README.md` (deployment).
