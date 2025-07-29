#!/bin/bash
set -e  # Exit immediately if any command fails

echo "🔄 Checking AWS authentication..."
if command -v aws &>/dev/null; then
    aws sts get-caller-identity || echo "🚨 AWS authentication failed!"
else
    echo "⚠️ AWS CLI not installed inside container!"
fi

echo "📥 Downloading FAISS data from S3..."
python /src/download_s3.py || { echo "🚨 FAISS Download Failed!"; exit 1; }

echo "🔄 Checking downloaded files..."
ls -la /src/data || { echo "🚨 FAISS directory is empty!"; exit 1; }

echo "🚀 Starting the application..."
python /src/main.py  # Exec ensures proper signal handling (graceful shutdown)
