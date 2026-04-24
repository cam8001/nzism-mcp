# NZISM MCP Server

An [MCP](https://modelcontextprotocol.io/) server for querying the [New Zealand Information Security Manual (NZISM)](https://nzism.gcsb.govt.nz/) using natural language. Ask your AI assistant questions about NZISM controls, and it will search the document and return relevant sections with citations.

The NZISM is a publicly available document published by the [GCSB](https://www.gcsb.govt.nz/). This tool uses only publicly accessible data — no classified or restricted information is included.

## Use it now

The server is hosted at:

```
https://nzism-mcp.camerontod.com/
```

Add it to [Kiro](https://kiro.dev) by adding the following to your MCP config (`~/.kiro/settings/mcp.json`) or agent file. Remote servers must be added by editing the config directly — `kiro-cli mcp add` only supports local stdio servers.

```json
{
  "mcpServers": {
    "nzism": {
      "url": "https://nzism-mcp.camerontod.com/"
    }
  }
}
```

This also works with Claude Desktop, Cursor, or any other MCP client that supports remote servers over Streamable HTTP.

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

Add to Kiro as a local stdio server:

```json
{
  "mcpServers": {
    "nzism": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/nzism-mcp", "python", "server.py"]
    }
  }
}
```

## AWS deployment

To deploy your own instance, see the [`nzism-mcp-cdk/`](nzism-mcp-cdk/) directory.

## Project structure

```
nzism-mcp/          Local MCP server (Python)
nzism-mcp-cdk/      CDK stack for AWS Lambda deployment
```
