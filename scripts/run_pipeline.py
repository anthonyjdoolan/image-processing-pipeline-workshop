"""Upload test data and watch for results.

Uploads input files, then watches for and downloads the generated reports.
Also downloads DynamoDB routing table data from the adjuster stack.

Usage:
    python scripts/run_pipeline.py

Press Ctrl+C to stop watching.
"""
import json
import os
import sys
import time

import boto3
from botocore.exceptions import ClientError

from config import REGION, BUCKET_NAME, STACK_NAME

MARKDOWN_PREFIX = "markdown/"
ROUTING_ARTIFACTS_PREFIX = "routing-artifacts/annotated/"
POLL_INTERVAL_SECONDS = 30


def get_bucket_from_stack(region: str) -> str:
    """Read bucket name from CDK stack outputs."""
    cfn = boto3.client("cloudformation", region_name=region)
    try:
        response = cfn.describe_stacks(StackName=STACK_NAME)
        for output in response["Stacks"][0].get("Outputs", []):
            if output["OutputKey"] == "BucketName":
                return output["OutputValue"]
    except ClientError:
        pass
    return BUCKET_NAME


def upload_test_data(bucket: str, region: str):
    """Upload images and test input files to S3."""
    s3_client = boto3.client("s3", region_name=region)

    # Upload images first
    images_dir = os.path.join(os.path.dirname(__file__), "..", "files", "images")
    if os.path.exists(images_dir):
        image_files = sorted(os.listdir(images_dir))
        print(f"Uploading {len(image_files)} image(s) to s3://{bucket}/images/")
        for filename in image_files:
            s3_client.upload_file(os.path.join(images_dir, filename), bucket, f"images/{filename}")
            print(f"  {filename}")
        print()

    # Find input files
    inputs_dir = os.path.join(
        os.path.dirname(__file__), "..", "files", "inputs"
    )

    if not os.path.exists(inputs_dir):
        print(f"ERROR: Input directory not found: {inputs_dir}")
        return 0

    input_files = [f for f in os.listdir(inputs_dir) if f.endswith(".json")]

    if not input_files:
        print(f"ERROR: No JSON files found in {inputs_dir}")
        return 0

    print(f"Uploading {len(input_files)} input file(s) to s3://{bucket}/inputs/\n")

    for i, filename in enumerate(sorted(input_files), 1):
        local_path = os.path.join(inputs_dir, filename)
        s3_key = f"inputs/{filename}"

        print(f"[{i}/{len(input_files)}] Uploading {filename}...")
        s3_client.upload_file(local_path, bucket, s3_key)

        # Add delay between uploads to trigger separate executions
        if i < len(input_files):
            time.sleep(5)

    print(f"\nUploaded {len(input_files)} file(s). Pipeline executions starting...\n")
    return len(input_files)


def list_markdown_keys(s3_client, bucket: str) -> set:
    """List all object keys under the markdown/ prefix."""
    keys = set()
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=MARKDOWN_PREFIX):
        for obj in page.get("Contents", []):
            keys.add(obj["Key"])
    return keys


def list_routing_artifacts(s3_client, bucket: str) -> set:
    """List all annotated images under routing-artifacts/annotated/ prefix."""
    keys = set()
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=ROUTING_ARTIFACTS_PREFIX):
        for obj in page.get("Contents", []):
            keys.add(obj["Key"])
    return keys


def get_routing_table_name(region: str) -> str:
    """Get DynamoDB routing table name from adjuster stack outputs."""
    cfn = boto3.client("cloudformation", region_name=region)
    try:
        response = cfn.describe_stacks(StackName="OarcWsAdjusterStack")
        for output in response["Stacks"][0].get("Outputs", []):
            if output.get("OutputKey") == "RoutingTableName":
                return output["OutputValue"]
    except ClientError:
        pass
    return None


def download_routing_table(region: str, output_path: str) -> int:
    """Scan DynamoDB routing table and save as JSON."""
    table_name = get_routing_table_name(region)
    if not table_name:
        print("  No adjuster stack found, skipping DynamoDB export")
        return 0
    
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(table_name)
    
    try:
        response = table.scan()
        items = response.get("Items", [])
        
        # Handle pagination
        while "LastEvaluatedKey" in response:
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            items.extend(response.get("Items", []))
        
        if items:
            with open(output_path, "w") as f:
                json.dump(items, f, indent=2, default=str)
            return len(items)
        return 0
    except ClientError as e:
        print(f"  Warning: Could not read DynamoDB table: {e}")
        return 0


def watch_for_results(bucket: str, region: str, expected_count: int):
    """Watch for new markdown reports and adjuster artifacts in S3."""
    s3_client = boto3.client("s3", region_name=region)

    # Create report subdirectories
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pipeline_reports_dir = os.path.join(script_dir, "files", "reports", "pipeline")
    adjuster_reports_dir = os.path.join(script_dir, "files", "reports", "adjuster")
    os.makedirs(pipeline_reports_dir, exist_ok=True)
    os.makedirs(adjuster_reports_dir, exist_ok=True)

    print(f"Watching for {expected_count} report(s)...")
    print(f"  - Pipeline reports: s3://{bucket}/{MARKDOWN_PREFIX}")
    print(f"  - Adjuster artifacts: s3://{bucket}/{ROUTING_ARTIFACTS_PREFIX}")
    print(f"Saving to:")
    print(f"  - Pipeline: {pipeline_reports_dir}")
    print(f"  - Adjuster: {adjuster_reports_dir}")
    print(f"Poll interval: {POLL_INTERVAL_SECONDS}s. Press Ctrl+C to stop.\n")

    known_markdown = list_markdown_keys(s3_client, bucket)
    known_artifacts = list_routing_artifacts(s3_client, bucket)
    
    print(f"Found {len(known_markdown)} existing report(s).")
    print(f"Found {len(known_artifacts)} existing adjuster artifact(s).\n")

    # Download any existing reports not already saved locally
    existing_files = set(os.listdir(pipeline_reports_dir))
    for key in known_markdown:
        filename = os.path.basename(key)
        if filename not in existing_files:
            print(f"Downloading: {filename}")
            response = s3_client.get_object(Bucket=bucket, Key=key)
            content = response["Body"].read().decode()
            local_path = os.path.join(pipeline_reports_dir, filename)
            with open(local_path, "w") as f:
                f.write(content)

    reports_received = 0
    artifacts_received = 0

    try:
        while reports_received < expected_count:
            time.sleep(POLL_INTERVAL_SECONDS)
            
            current_markdown = list_markdown_keys(s3_client, bucket)
            current_artifacts = list_routing_artifacts(s3_client, bucket)
            
            new_markdown = current_markdown - known_markdown
            new_artifacts = current_artifacts - known_artifacts

            if new_markdown:
                for key in sorted(new_markdown):
                    print(f"\n{'='*60}")
                    print(f"  NEW REPORT ({reports_received + 1}/{expected_count}): {key}")
                    print(f"{'='*60}\n")

                    # Download the report
                    response = s3_client.get_object(Bucket=bucket, Key=key)
                    content = response["Body"].read().decode()

                    # Save to pipeline reports directory
                    filename = os.path.basename(key)
                    local_path = os.path.join(pipeline_reports_dir, filename)
                    with open(local_path, "w") as f:
                        f.write(content)
                    print(f"Saved to: {local_path}")

                    reports_received += 1

                known_markdown = current_markdown
            
            if new_artifacts:
                for key in sorted(new_artifacts):
                    print(f"\n{'~'*60}")
                    print(f"  ADJUSTER ARTIFACT: {key}")
                    print(f"{'~'*60}")
                    
                    # Download the annotated image
                    response = s3_client.get_object(Bucket=bucket, Key=key)
                    image_data = response["Body"].read()
                    
                    # Save to adjuster reports directory
                    filename = os.path.basename(key)
                    local_path = os.path.join(adjuster_reports_dir, filename)
                    with open(local_path, "wb") as f:
                        f.write(image_data)
                    print(f"Saved to: {local_path}\n")
                    
                    artifacts_received += 1
                
                known_artifacts = current_artifacts
            
            if not new_markdown and not new_artifacts:
                print(f"  Waiting... ({reports_received}/{expected_count} reports, {artifacts_received} adjuster artifacts)")

        print(f"\n{'='*60}")
        print(f"  All {expected_count} report(s) received!")
        print(f"  {artifacts_received} adjuster artifact(s) generated")
        print(f"{'='*60}\n")
        
        # Download DynamoDB routing table
        if artifacts_received > 0:
            print("Downloading DynamoDB routing table...")
            routing_json_path = os.path.join(adjuster_reports_dir, "routing_decisions.json")
            record_count = download_routing_table(region, routing_json_path)
            if record_count > 0:
                print(f"  Saved {record_count} routing decision(s) to: {routing_json_path}\n")

    except KeyboardInterrupt:
        print(f"\n\nStopped watching.")
        print(f"  Reports: {reports_received}/{expected_count}")
        print(f"  Adjuster artifacts: {artifacts_received}")
        
        # Try to download DynamoDB table on interrupt too
        if artifacts_received > 0:
            print("\nDownloading DynamoDB routing table...")
            routing_json_path = os.path.join(adjuster_reports_dir, "routing_decisions.json")
            record_count = download_routing_table(region, routing_json_path)
            if record_count > 0:
                print(f"  Saved {record_count} routing decision(s) to: {routing_json_path}")


def main():
    bucket = get_bucket_from_stack(REGION)

    count = upload_test_data(bucket, REGION)
    if count == 0:
        sys.exit(1)

    watch_for_results(bucket, REGION, count)


if __name__ == "__main__":
    main()
