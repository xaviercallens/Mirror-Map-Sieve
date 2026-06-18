#!/usr/bin/env bash
# Deploy Runux AI Pipeline to Google Cloud Run Jobs

set -e

PROJECT_ID="agora-autoresearch-001"
REGION="us-central1"
IMAGE_NAME="gcr.io/${PROJECT_ID}/runux-pipeline"
JOB_NAME="runux-pipeline"

echo "============================================================"
echo "🚀 Deploying Runux AI Pipeline to GCP Cloud Run Jobs"
echo "============================================================"

# 1. Copy runux-ai-runtime source to build context
echo "[1/4] Copying runux-ai-runtime to build context..."
mkdir -p xavux
rsync -av --delete --exclude="target" --exclude=".git" --exclude=".lake" --exclude=".terraform" --exclude="*.tar.gz" --exclude="*.tgz" ../xavux/runux-ai-runtime xavux/

# 2. Build the Docker image via Cloud Build
echo "[2/4] Submitting Build to Cloud Build..."
gcloud builds submit --config cloudbuild.runux_pipeline.yaml --project ${PROJECT_ID}

# 3. Create or update the Cloud Run Job
echo "[3/4] Deploying to Cloud Run Jobs..."
gcloud run jobs create ${JOB_NAME} \
    --image ${IMAGE_NAME}:latest \
    --region ${REGION} \
    --project ${PROJECT_ID} \
    --tasks 1 \
    --max-retries 0 \
    --memory 4Gi \
    --cpu 2 \
    --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest,GALOIS_MISTRAL_KEY=MISTRAL_API_KEY:latest" || \
gcloud run jobs update ${JOB_NAME} \
    --image ${IMAGE_NAME}:latest \
    --region ${REGION} \
    --project ${PROJECT_ID} \
    --memory 4Gi \
    --cpu 2 \
    --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest,GALOIS_MISTRAL_KEY=MISTRAL_API_KEY:latest"

# 4. Trigger Execution
echo "[4/4] Triggering Cloud Run Job Execution..."
gcloud run jobs execute ${JOB_NAME} --region ${REGION} --project ${PROJECT_ID}

echo "============================================================"
echo "✅ Deployment & Execution Triggered Successfully!"
echo "============================================================"
