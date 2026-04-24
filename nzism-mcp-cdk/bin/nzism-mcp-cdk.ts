#!/usr/bin/env node
import "source-map-support/register";
import * as cdk from "aws-cdk-lib/core";
import { NzismMcpCdkStack } from "../lib/nzism-mcp-cdk-stack";

const app = new cdk.App();

// Stack in us-east-1: WAF WebACLs with scope CLOUDFRONT must be in us-east-1.
// CloudFront is global so the endpoint is accessible from anywhere.
new NzismMcpCdkStack(app, "NzismMcpCdkStack", {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: "us-east-1",
  },
});
