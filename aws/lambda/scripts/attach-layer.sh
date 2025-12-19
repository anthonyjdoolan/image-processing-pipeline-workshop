#!/bin/bash

FUNCTION_NAME="oarc-image-process"
LAYER_NAME="oarc-image-process-layer"
REGION="us-west-2"

# Get the latest layer version ARN
LAYER_ARN=$(aws lambda list-layer-versions --layer-name ${LAYER_NAME} --region ${REGION} --query 'LayerVersions[0].LayerVersionArn' --output text)

echo "Attaching layer ${LAYER_ARN} to function ${FUNCTION_NAME}..."

# Update function configuration to use the layer
aws lambda update-function-configuration \
    --function-name ${FUNCTION_NAME} \
    --layers ${LAYER_ARN} \
    --region ${REGION}

echo "Layer attached successfully!"
