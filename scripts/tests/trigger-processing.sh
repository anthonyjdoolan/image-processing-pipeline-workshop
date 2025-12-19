#!/bin/bash

BUCKET="oarc-image-processing-pipeline"
REGION="us-west-2"

echo "Uploading input files to trigger processing..."

# Upload all JSON files from inputs directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for file in "${SCRIPT_DIR}/../../aws/s3/files/inputs"/*.json; do
    if [ -f "$file" ]; then
        filename=$(basename "$file")
        echo "Uploading $filename..."
        aws s3 cp "$file" s3://${BUCKET}/inputs/${filename} --region ${REGION}
        echo "Uploaded $filename - processing should start automatically"
        sleep 5  # Small delay between uploads
    fi
done

echo "All input files uploaded!"
