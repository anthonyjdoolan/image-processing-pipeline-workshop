from aws_cdk import (
    BundlingOptions,
    Duration,
    Stack,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_s3 as s3,
    aws_s3_notifications as s3_notifications,
)
from constructs import Construct

class AdjusterStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        source_bucket_name = self.node.try_get_context("sourceBucketName") or "oarc-ws-image-processing-pipeline"
        prompt_key = self.node.try_get_context("promptKey") or "adjuster_prompt.txt"
        model_id = self.node.try_get_context("bedrockModelId") or "us.anthropic.claude-sonnet-4-20250514-v1:0"
        disable_docker_bundling = str(self.node.try_get_context("disableDockerBundling") or "").lower() in {
            "1",
            "true",
            "yes",
        }

        source_bucket = s3.Bucket.from_bucket_name(self, "SourceComparedBucket", source_bucket_name)

        routing_table = dynamodb.Table(
            self,
            "RoutingTable",
            partition_key=dynamodb.Attribute(name="routing_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        )

        lambda_code = _lambda.Code.from_asset(
            ".",
            bundling=BundlingOptions(
                image=_lambda.Runtime.PYTHON_3_12.bundling_image,
                command=[
                    "bash",
                    "-c",
                    "pip install -r lambda-requirements.txt -t /asset-output && cp adjuster_lambda.py /asset-output/",
                ],
            ),
        )

        if disable_docker_bundling:
            lambda_code = _lambda.Code.from_asset(
                ".",
                exclude=[
                    "cdk.out",
                    "cdk.out/**",
                    ".venv",
                    ".venv/**",
                    ".git",
                    ".git/**",
                    "tests",
                    "tests/**",
                    "__pycache__",
                    "**/__pycache__/**",
                    "*.pyc",
                    "**/*.pyc",
                ],
            )

        adjuster_lambda = _lambda.Function(
            self,
            "DownstreamAdjusterFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="adjuster_lambda.lambda_handler",
            code=lambda_code,
            timeout=Duration.seconds(120),
            memory_size=1024,
            environment={
                "ROUTING_TABLE_NAME": routing_table.table_name,
                "PROMPT_S3_KEY": prompt_key,
                "BEDROCK_MODEL_ID": model_id,
            },
        )

        routing_table.grant_write_data(adjuster_lambda)
        source_bucket.grant_read(adjuster_lambda)

        adjuster_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=["*"],
            )
        )

        source_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3_notifications.LambdaDestination(adjuster_lambda),
            s3.NotificationKeyFilter(prefix="compared/"),
        )
