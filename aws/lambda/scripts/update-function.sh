#!/bin/bash

FUNCTION_NAME="oarc-image-process"
REGION="us-west-2"

echo "Updating Lambda function..."

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create deployment package
zip -j function.zip "${SCRIPT_DIR}/../lambda_function.py"

# Update function code
aws lambda update-function-code \
    --function-name ${FUNCTION_NAME} \
    --zip-file fileb://function.zip \
    --region ${REGION}

echo "Lambda function updated successfully!"

# Clean up
rm function.zip
