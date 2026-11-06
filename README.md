# NZISM MCP Server

An [MCP](https://modelcontextprotocol.io/) server for querying the [New Zealand Information Security Manual (NZISM)](https://nzism.gcsb.govt.nz/) using natural language. Ask your AI assistant questions about NZISM controls, and it will search the document and return relevant sections with citations.

The NZISM is a publicly available document published by the [GCSB](https://www.gcsb.govt.nz/). This tool uses only publicly accessible data — no classified or restricted information is included.

## Use it now

The server is hosted at:

```
https://nzism-mcp.camerontod.com/mcp
```

The path must be `/mcp`; the bare domain returns 404. The transport is Streamable HTTP.

### Kiro

Add the following to your MCP config (`~/.kiro/settings/mcp.json`) or agent file. Remote servers must be added by editing the config directly — `kiro-cli mcp add` only supports local stdio servers.

```json
{
  "mcpServers": {
    "nzism": {
      "url": "https://nzism-mcp.camerontod.com/mcp"
    }
  }
}
```

### Claude Code

```bash
claude mcp add --transport http nzism https://nzism-mcp.camerontod.com/mcp
```

Add `--scope user` to make it available in every project, or `--scope project` to write it to a shared `.mcp.json`. Check with `claude mcp list`, or `/mcp` inside a session.

### Claude Desktop

Add it as a custom connector (Settings → Connectors → Add custom connector) using the URL above. If your plan doesn't offer custom connectors, bridge it with [`mcp-remote`](https://www.npmjs.com/package/mcp-remote) in `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "nzism": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://nzism-mcp.camerontod.com/mcp"]
    }
  }
}
```

### Other clients

Cursor and any other MCP client that supports remote Streamable HTTP servers can use the same URL.

## Tools

- `query_nzism` — keyword search across the entire NZISM, ranked by relevance. Supports AND/OR matching.
- `get_nzism_section` — retrieve all paragraphs under a section number (e.g. `17.4` for TLS, `22.1` for cloud computing).

### Try it out

Once configured, ask your assistant things like:

- "What does the NZISM say about cloud computing?"
- "Find NZISM controls for encryption at rest"
- "Show me section 17.4 on TLS"
- "What are the password requirements in the NZISM?"

Results include section references and links to the [NZISM online document](https://nzism.gcsb.govt.nz/ism-document).

## Run locally

If you prefer to run the server locally (no network dependency), see the [`nzism-mcp/`](nzism-mcp/) directory. Requires [uv](https://docs.astral.sh/uv/) and Python 3.13+.

```bash
cd nzism-mcp
uv sync
uv run python server.py
```

Use the absolute path to the `nzism-mcp/` subdirectory (the one containing `server.py`) below.

Kiro (stdio) — add to `~/.kiro/settings/mcp.json`:

```json
{
  "mcpServers": {
    "nzism": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/nzism-mcp/nzism-mcp", "python", "server.py"]
    }
  }
}
```

Claude Code (stdio):

```bash
claude mcp add nzism -- uv run --directory /path/to/nzism-mcp/nzism-mcp python server.py
```

Claude Desktop (stdio) uses the same `command`/`args` block as the Kiro example, in `claude_desktop_config.json`.

## Updating the NZISM data

When a new NZISM version is published, download the XML in a browser from <https://nzism.gcsb.govt.nz/ism-document/xml> (the site's bot protection blocks curl), then:

```bash
cd nzism-mcp
./update.sh --check ~/Downloads/nzism.xml   # preview changes, touches nothing
./update.sh ~/Downloads/nzism.xml           # apply and rebuild the index
```

Then update the version line in `nzism-mcp/data/README.md`, check `data/deeplinks.json` (the script warns if new sections have no deeplink; there is no scraper for it yet), and redeploy. See [AGENTS.md](AGENTS.md) for details.

## AWS deployment

To deploy your own instance, see the [`nzism-mcp-cdk/`](nzism-mcp-cdk/) directory.

## Project structure

```
nzism-mcp/          Local MCP server (Python), data files, index builder, update.sh
nzism-mcp-cdk/      CDK stack for AWS Lambda deployment
AGENTS.md           Orientation for AI agents and new contributors
```
