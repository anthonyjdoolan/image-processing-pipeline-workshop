#!/bin/bash

# Configuration variables
MODEL_S3_PATH="s3://oarc-image-processing-pipeline/sam3-model.tar.gz"
ROLE_ARN="arn:aws:iam::123456789123:role/service-role/AmazonSageMaker-ExecutionRole-20251125T111068"
OUTPUT_S3_PATH="s3://oarc-image-processing-pipeline/async-out/"
FAILURE_S3_PATH="s3://oarc-image-processing-pipeline/async-failure/"
MODEL_NAME="sam3-model-v1"
ENDPOINT_CONFIG_NAME="sam3-config-v1"
ENDPOINT_NAME="sam3-seg-endpoint"
REGION="us-west-2"

# Create SageMaker Model if it doesn't exist
if aws sagemaker describe-model --model-name "$MODEL_NAME" --region "$REGION" &>/dev/null; then
    echo "Model $MODEL_NAME already exists, skipping creation"
else
    echo "Creating Model: $MODEL_NAME"
    aws sagemaker create-model \
        --model-name "$MODEL_NAME" \
        --primary-container Image=763104351884.dkr.ecr.us-west-2.amazonaws.com/pytorch-inference:2.6.0-gpu-py312-cu124-ubuntu22.04-sagemaker,ModelDataUrl="$MODEL_S3_PATH" \
        --execution-role-arn "$ROLE_ARN" \
        --region "$REGION"
    echo "Created Model: $MODEL_NAME"
fi

# Create Endpoint Configuration if it doesn't exist
if aws sagemaker describe-endpoint-config --endpoint-config-name "$ENDPOINT_CONFIG_NAME" --region "$REGION" &>/dev/null; then
    echo "EndpointConfig $ENDPOINT_CONFIG_NAME already exists, skipping creation"
else
    echo "Creating EndpointConfig: $ENDPOINT_CONFIG_NAME"
    aws sagemaker create-endpoint-config \
        --endpoint-config-name "$ENDPOINT_CONFIG_NAME" \
        --production-variants VariantName=primary,ModelName="$MODEL_NAME",InitialInstanceCount=1,InstanceType=ml.g4dn.xlarge \
        --async-inference-config OutputConfig="{S3OutputPath=$OUTPUT_S3_PATH,S3FailurePath=$FAILURE_S3_PATH}",ClientConfig="{MaxConcurrentInvocationsPerInstance=1}" \
        --region "$REGION"
    echo "Created EndpointConfig: $ENDPOINT_CONFIG_NAME"
fi

# Delete existing endpoint if it exists
if aws sagemaker describe-endpoint --endpoint-name "$ENDPOINT_NAME" --region "$REGION" &>/dev/null; then
    echo "Deleting existing endpoint: $ENDPOINT_NAME"
    aws sagemaker delete-endpoint --endpoint-name "$ENDPOINT_NAME" --region "$REGION"

    # Wait for deletion
    echo "Waiting for endpoint deletion..."
    aws sagemaker wait endpoint-deleted --endpoint-name "$ENDPOINT_NAME" --region "$REGION"
    echo "Endpoint deletion complete"
else
    echo "Endpoint not found or already deleted"
fi

# Create new endpoint
echo "Creating Endpoint: $ENDPOINT_NAME"
aws sagemaker create-endpoint \
    --endpoint-name "$ENDPOINT_NAME" \
    --endpoint-config-name "$ENDPOINT_CONFIG_NAME" \
    --region "$REGION"

# Wait for endpoint to be ready
echo "Waiting for endpoint to be ready..."
while true; do
    STATUS=$(aws sagemaker describe-endpoint --endpoint-name "$ENDPOINT_NAME" --region "$REGION" --query 'EndpointStatus' --output text)
    echo "Endpoint status: $STATUS"

    if [ "$STATUS" = "InService" ]; then
        echo "Endpoint is ready!"
        break
    elif [ "$STATUS" = "Failed" ]; then
        echo "Endpoint failed to start!"
        exit 1
    fi

    sleep 30
done

echo "Waiting additional 120 seconds for warmup..."
sleep 120
echo "Endpoint ready for use!"
