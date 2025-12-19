#!/bin/bash

cd ../../model

# Create model.tar.gz from model directory contents
tar --exclude='code/__pycache__' -czvf ../aws/s3/files/sam3-model.tar.gz *

echo "Created model.tar.gz"
ls -la ../aws/s3/files/sam3-model.tar.gz
