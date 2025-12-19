#!/bin/bash

BUCKET="oarc-image-processing-pipeline"
REGION="us-west-2"
MARKDOWN_PREFIX="markdown/"

echo "Watching for new markdown files in s3://${BUCKET}/${MARKDOWN_PREFIX}..."

# Get initial file count
INITIAL_COUNT=$(aws s3 ls s3://${BUCKET}/${MARKDOWN_PREFIX} --region ${REGION} 2>/dev/null | wc -l)
echo "Initial markdown files: ${INITIAL_COUNT}"

while true; do
    # Check current file count
    CURRENT_COUNT=$(aws s3 ls s3://${BUCKET}/${MARKDOWN_PREFIX} --region ${REGION} 2>/dev/null | wc -l)

    if [ ${CURRENT_COUNT} -gt ${INITIAL_COUNT} ]; then
        echo "New markdown files detected!"
        echo "Listing new files:"
        aws s3 ls s3://${BUCKET}/${MARKDOWN_PREFIX} --region ${REGION} --recursive

        # Download the latest markdown file
        LATEST_FILE=$(aws s3 ls s3://${BUCKET}/${MARKDOWN_PREFIX} --region ${REGION} --recursive | sort | tail -1 | awk '{print $4}')
        if [ ! -z "${LATEST_FILE}" ]; then
            echo "Downloading latest file: ${LATEST_FILE}"
            aws s3 cp s3://${BUCKET}/${LATEST_FILE} ./$(basename ${LATEST_FILE}) --region ${REGION}
            echo "Downloaded to: ./$(basename ${LATEST_FILE})"
        fi

        INITIAL_COUNT=${CURRENT_COUNT}
    else
        echo "Checking for new files... (${CURRENT_COUNT} files found)"
    fi

    sleep 30
done
