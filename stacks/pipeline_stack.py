"""Pipeline stack - processing resources for the OARC Image Processing Pipeline.

Creates Lambda, Step Functions, EventBridge, and endpoint monitoring.
Depends on the StorageStack for the S3 bucket.

Deploy:   cdk deploy OarcWsPipelineStack
Destroy:  cdk destroy OarcWsPipelineStack
"""
import os
import aws_cdk as cdk
from constructs import Construct
from aws_cdk import (
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_s3 as s3,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_events as events,
    aws_events_targets as events_targets,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as sfn_tasks,
    aws_logs as logs,
    aws_sagemaker as sagemaker,
)

LAMBDA_DIR = os.path.join(os.path.dirname(__file__), "lambda_functions")


class PipelineStack(cdk.Stack):

    def __init__(self, scope: Construct, construct_id: str, *, bucket: s3.IBucket, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        prefix = self.node.try_get_context("resource_prefix")
        endpoint_name = self.node.try_get_context("endpoint_name")
        bedrock_model_id = self.node.try_get_context("bedrock_model_id")
        bucket_name = bucket.bucket_name

        # -----------------------------------------------------------
        # Processor Lambda (Bedrock analysis + report generation)
        # -----------------------------------------------------------
        processor = lambda_.DockerImageFunction(
            self, "ProcessorFunction",
            function_name=f"{prefix}-processor",
            code=lambda_.DockerImageCode.from_image_asset(
                os.path.join(LAMBDA_DIR, "processor"),
                platform=cdk.aws_ecr_assets.Platform.LINUX_AMD64,
            ),
            memory_size=512,
            timeout=cdk.Duration.minutes(3),
            environment={
                "BUCKET_NAME": bucket_name,
                "BEDROCK_MODEL_ID": bedrock_model_id,
            },
        )
        bucket.grant_read_write(processor)
        processor.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=[
                f"arn:{self.partition}:bedrock:*::foundation-model/{bedrock_model_id}",
                f"arn:{self.partition}:bedrock:*::foundation-model/{bedrock_model_id.removeprefix('us.')}",
                f"arn:{self.partition}:bedrock:{self.region}:{self.account}:inference-profile/{bedrock_model_id}",
            ],
        ))
        endpoint_arn = self.format_arn(service="sagemaker", resource="endpoint", resource_name=endpoint_name)
