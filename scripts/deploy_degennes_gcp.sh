#!/usr/bin/env bash
# Deploy DeGennes Agent to Google Cloud Run Jobs

set -e

PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1"
IMAGE_NAME="gcr.io/${PROJECT_ID}/degennes-agent"
JOB_NAME="degennes-research-job"

echo "============================================================"
echo "🚀 Deploying DeGennes Agent to GCP Cloud Run Jobs"
echo "============================================================"

# 1. Build the Docker image
echo "[1/3] Building Docker Image..."
docker build -t ${IMAGE_NAME} -f agents/Dockerfile .

# 2. Push to Google Container Registry
echo "[2/3] Pushing to GCR..."
docker push ${IMAGE_NAME}

# 3. Create or update the Cloud Run Job
echo "[3/3] Deploying to Cloud Run Jobs..."
gcloud run jobs create ${JOB_NAME} \
    --image ${IMAGE_NAME} \
    --region ${REGION} \
    --tasks 1 \
    --max-retries 0 \
    --memory 2Gi \
    --cpu 1 \
    --set-secrets="GEMINI_API_KEY=gemini-api-key:latest" || \
gcloud run jobs update ${JOB_NAME} \
    --image ${IMAGE_NAME} \
    --region ${REGION} \
    --set-secrets="GEMINI_API_KEY=gemini-api-key:latest"

echo "============================================================"
echo "✅ Deployment Successful!"
echo "To execute the DeGennes agent, run:"
echo "gcloud run jobs execute ${JOB_NAME} --region ${REGION}"
echo "============================================================"
