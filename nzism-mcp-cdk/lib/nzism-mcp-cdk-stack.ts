import * as cdk from "aws-cdk-lib/core";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as logs from "aws-cdk-lib/aws-logs";
import * as apigateway from "aws-cdk-lib/aws-apigateway";
import * as cloudfront from "aws-cdk-lib/aws-cloudfront";
import * as origins from "aws-cdk-lib/aws-cloudfront-origins";
import * as wafv2 from "aws-cdk-lib/aws-wafv2";
import * as acm from "aws-cdk-lib/aws-certificatemanager";
import * as route53 from "aws-cdk-lib/aws-route53";
import * as route53Targets from "aws-cdk-lib/aws-route53-targets";
import * as python from "@aws-cdk/aws-lambda-python-alpha";
import { Construct } from "constructs";
import * as path from "path";
import * as fs from "fs";

/**
 * Optional CDK context values for custom domain:
 *   domainName     - e.g. "nzism.example.com"
 *   hostedZoneId   - Route 53 hosted zone ID
 *   hostedZoneName - e.g. "example.com"
 *   certificateArn - ACM certificate ARN (must be in us-east-1)
 */
export class NzismMcpCdkStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // --- Optional custom domain from context ---
    const domainName = this.node.tryGetContext("domainName") as string | undefined;
    const hostedZoneId = this.node.tryGetContext("hostedZoneId") as string | undefined;
    const hostedZoneName = this.node.tryGetContext("hostedZoneName") as string | undefined;
    const certificateArn = this.node.tryGetContext("certificateArn") as string | undefined;

    const lambdaDir = path.join(__dirname, "..", "src", "lambda", "nzism-mcp");
    const dataDir = path.join(lambdaDir, "data");

    // The pre-built JSON index must exist in the sibling nzism-mcp project.
    const indexSource = path.join(
      __dirname, "..", "..", "nzism-mcp", "data", "nzism_index.json"
    );
    if (!fs.existsSync(indexSource)) {
      throw new Error(
        "nzism-mcp/data/nzism_index.json not found. " +
        "Run 'uv run python build_index.py' in the nzism-mcp/ directory first."
      );
    }

    if (!fs.existsSync(dataDir)) {
      fs.mkdirSync(dataDir, { recursive: true });
    }
    fs.copyFileSync(indexSource, path.join(dataDir, "nzism_index.json"));

    // --- Lambda ---

    const logGroup = new logs.LogGroup(this, "NzismMcpLogGroup", {
      logGroupName: "/aws/lambda/nzism-mcp",
      retention: logs.RetentionDays.ONE_MONTH,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Lambda Web Adapter layer — runs uvicorn inside Lambda
    const webAdapterLayer = lambda.LayerVersion.fromLayerVersionArn(
      this, "WebAdapterLayer",
      `arn:aws:lambda:${this.region}:753240598075:layer:LambdaAdapterLayerX86:27`
    );

    const fn = new python.PythonFunction(this, "NzismMcpFunction", {
      functionName: "nzism-mcp",
      entry: lambdaDir,
      runtime: lambda.Runtime.PYTHON_3_13,
      index: "server.py",
      handler: "app",
      memorySize: 256,
      timeout: cdk.Duration.seconds(30),
      tracing: lambda.Tracing.ACTIVE,
      logGroup: logGroup,
      layers: [webAdapterLayer],
      environment: {
        PYTHONUNBUFFERED: "1",
        AWS_LAMBDA_EXEC_WRAPPER: "/opt/bootstrap",
        AWS_LWA_PORT: "8080",
        AWS_LWA_READINESS_CHECK_PATH: "/mcp",
      },
    });

    // Override handler to run.sh — Lambda Web Adapter uses this as the startup script
    const cfnFunction = fn.node.defaultChild as cdk.CfnResource;
    cfnFunction.addPropertyOverride("Handler", "run.sh");

    // --- API Gateway ---

    const api = new apigateway.LambdaRestApi(this, "NzismMcpApi", {
      handler: fn,
      proxy: true,
      restApiName: "nzism-mcp",
      endpointTypes: [apigateway.EndpointType.REGIONAL],
    });

    // --- WAF ---

    const webAcl = new wafv2.CfnWebACL(this, "NzismMcpWaf", {
      defaultAction: { allow: {} },
      scope: "CLOUDFRONT",
      visibilityConfig: {
        cloudWatchMetricsEnabled: true,
        metricName: "nzism-mcp-waf",
        sampledRequestsEnabled: true,
      },
      rules: [
        {
          name: "RateLimit",
          priority: 1,
          action: { block: {} },
          visibilityConfig: {
            cloudWatchMetricsEnabled: true,
            metricName: "nzism-mcp-rate-limit",
            sampledRequestsEnabled: true,
          },
          statement: {
            rateBasedStatement: {
              limit: 1000,
              aggregateKeyType: "IP",
            },
          },
        },
      ],
    });

    // --- CloudFront ---

    // API Gateway origin — strip the stage name path from the origin
    const apiDomainName = `${api.restApiId}.execute-api.${this.region}.amazonaws.com`;
    const origin = new origins.HttpOrigin(apiDomainName, {
      originPath: `/${api.deploymentStage.stageName}`,
    });

    let distributionProps: cloudfront.DistributionProps = {
      defaultBehavior: {
        origin: origin,
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
        cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
        originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
      },
      webAclId: webAcl.attrArn,
    };

    if (domainName && certificateArn) {
      const certificate = acm.Certificate.fromCertificateArn(
        this, "Certificate", certificateArn
      );
      distributionProps = {
        ...distributionProps,
        domainNames: [domainName],
        certificate: certificate,
      };
    }

    const distribution = new cloudfront.Distribution(
      this, "NzismMcpDistribution", distributionProps
    );

    // --- Route 53 alias record (if custom domain configured) ---

    if (domainName && hostedZoneId && hostedZoneName) {
      const overwriteDns = this.node.tryGetContext("overwriteDns") as boolean | undefined;

      const dns = require("dns");
      let recordExists = false;
      try {
        dns.resolve4Sync(domainName);
        recordExists = true;
      } catch {
        // NXDOMAIN — safe to create
      }

      if (recordExists && !overwriteDns) {
        throw new Error(
          `DNS record for ${domainName} already exists. ` +
          `Set context value "overwriteDns": true to update it, ` +
          `or choose a different domainName.`
        );
      }

      const hostedZone = route53.HostedZone.fromHostedZoneAttributes(
        this, "HostedZone", {
          hostedZoneId: hostedZoneId,
          zoneName: hostedZoneName,
        }
      );

      new route53.ARecord(this, "AliasRecord", {
        zone: hostedZone,
        recordName: domainName,
        target: route53.RecordTarget.fromAlias(
          new route53Targets.CloudFrontTarget(distribution)
        ),
      });
    }

    // --- Outputs ---

    const endpoint = domainName
      ? `https://${domainName}/`
      : `https://${distribution.distributionDomainName}/`;

    new cdk.CfnOutput(this, "McpEndpoint", {
      value: endpoint,
      description: "NZISM MCP server endpoint (use this in your MCP client config)",
    });

    new cdk.CfnOutput(this, "DistributionId", {
      value: distribution.distributionId,
      description: "CloudFront distribution ID",
    });
  }
}
