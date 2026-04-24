# NZISM MCP — AWS Deployment

CDK stack that deploys the NZISM MCP server as a publicly accessible Lambda function behind CloudFront and WAF.

Based on the [aws-samples serverless MCP server reference implementation](https://github.com/aws-samples/sample-serverless-mcp-servers/tree/main/stateless-mcp-on-lambda-python).

## Architecture

- CloudFront distribution (HTTPS only, public)
- WAF WebACL with rate limiting (1000 requests per 5 minutes per IP)
- API Gateway (regional, proxy mode) → Lambda
- Lambda runs [Lambda Web Adapter](https://github.com/awslabs/aws-lambda-web-adapter) + FastAPI + uvicorn, enabling SSE streaming for the MCP Streamable HTTP transport
- CloudWatch log group (`/aws/lambda/nzism-mcp`, 30 day retention)
- X-Ray tracing enabled

The stack deploys to us-east-1 (required for CloudFront-scoped WAF). CloudFront is global so the endpoint is accessible from anywhere.

## Prerequisites

- The JSON index must exist at `../nzism-mcp/data/nzism_index.json`. Run `uv run python build_index.py` in the `nzism-mcp/` directory first.
- Docker (required by `PythonFunction` for dependency bundling).

## Deploy

```bash
npm install
npx cdk deploy
```

The MCP endpoint URL is printed as a stack output.

## Custom domain (optional)

To use a custom domain, copy `cdk.context.example.json` to `cdk.context.json` and fill in your values:

```json
{
  "domainName": "nzism.example.com",
  "hostedZoneId": "Z1234567890",
  "hostedZoneName": "example.com",
  "certificateArn": "arn:aws:acm:us-east-1:123456789:certificate/abc-123"
}
```

- `domainName` — the FQDN for the MCP endpoint
- `hostedZoneId` / `hostedZoneName` — your Route 53 hosted zone (must already exist)
- `certificateArn` — ACM certificate ARN (must be in us-east-1)

All four values are required for custom domain setup. If omitted, the stack uses the default `d1234.cloudfront.net` domain.

If the subdomain already resolves to something, the deploy will fail with an error to prevent accidentally overwriting a live domain. Set `"overwriteDns": true` in your context to update an existing record.

## Connecting

Add the endpoint to your MCP client config:

```json
{
  "mcpServers": {
    "nzism": {
      "url": "https://nzism.example.com/mcp"
    }
  }
}
```
