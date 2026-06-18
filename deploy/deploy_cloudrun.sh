#!/bin/bash
set -e

PROJECT_ID="gen-lang-client-0625573011"
SERVICE_NAME="open-room"
REGION="us-central1"

echo "Submitting build to Google Cloud Build..."
gcloud builds submit /Users/xcallens/xdev/SocrateAI-Scientific-Agora/lmms-lab-writer \
  --tag gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --project $PROJECT_ID \
  --timeout 1200s

echo "Deploying to Google Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --project $PROJECT_ID

echo "Deployment finished successfully!"
