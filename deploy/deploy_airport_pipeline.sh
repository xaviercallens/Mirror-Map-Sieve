#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# deploy_airport_pipeline.sh
# Builds and deploys the Airport Operations Autoresearch pipeline as a
# Cloud Run JOB on project: agora-autoresearch-001
#
# Secrets injected from GCP Secret Manager:
#   - GEMINI_API_KEY   → secret: GEMINI_API_KEY  (latest version)
#   - MISTRAL_API_KEY  → secret: MISTRAL_API_KEY (latest version)
#
# Usage:
#   chmod +x deploy/deploy_airport_pipeline.sh
#   ./deploy/deploy_airport_pipeline.sh          # build + deploy + execute
#   ./deploy/deploy_airport_pipeline.sh --logs   # tail logs after execution
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_ID="agora-autoresearch-001"
REGION="us-central1"
IMAGE_NAME="airport-autoresearch"
JOB_NAME="airport-operations-autoresearch"
IMAGE_URI="gcr.io/${PROJECT_ID}/${IMAGE_NAME}:latest"

# Grant the Cloud Run SA access to Secret Manager (idempotent)
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")
SA_EMAIL="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "════════════════════════════════════════════════════════════"
echo "  🛫  Airport Operations Autoresearch — GCP Deployment"
echo "  Project : ${PROJECT_ID}"
echo "  Region  : ${REGION}"
echo "  Job     : ${JOB_NAME}"
echo "════════════════════════════════════════════════════════════"

# ── 1. Grant Secret Manager access to the default Compute SA ─────────────────
echo ""
echo "[1/5] Granting secretmanager.secretAccessor to ${SA_EMAIL}..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" \
  --quiet

# ── 2. Build container image with Cloud Build ─────────────────────────────────
echo ""
echo "[2/5] Building Docker image with Cloud Build..."
echo "      Using Dockerfile.airport for texlive + full pipeline..."
gcloud builds submit \
  --project="${PROJECT_ID}" \
  --tag="${IMAGE_URI}" \
  --dockerfile="Dockerfile.airport" \
  --timeout="20m" \
  .

echo "  ✅ Image built: ${IMAGE_URI}"

# ── 3. Create or update the Cloud Run Job ────────────────────────────────────
echo ""
echo "[3/5] Creating/updating Cloud Run Job: ${JOB_NAME}..."
gcloud run jobs create "${JOB_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE_URI}" \
  --memory="4Gi" \
  --cpu="4" \
  --task-timeout="3600" \
  --max-retries="1" \
  --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest,MISTRAL_API_KEY=MISTRAL_API_KEY:latest" \
  --command="python3" \
  --args="agents/airport_operations_autoresearch.py" \
  2>/dev/null || \
gcloud run jobs update "${JOB_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE_URI}" \
  --memory="4Gi" \
  --cpu="4" \
  --task-timeout="3600" \
  --max-retries="1" \
  --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest,MISTRAL_API_KEY=MISTRAL_API_KEY:latest"

echo "  ✅ Cloud Run Job configured."

# ── 4. Execute the Job ────────────────────────────────────────────────────────
echo ""
echo "[4/5] 🚀 Executing Cloud Run Job: ${JOB_NAME}..."
EXECUTION_NAME=$(gcloud run jobs execute "${JOB_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --format="value(metadata.name)" \
  --wait)

echo "  ✅ Job execution complete: ${EXECUTION_NAME}"

# ── 5. Tail logs ──────────────────────────────────────────────────────────────
echo ""
echo "[5/5] 📋 Fetching execution logs..."
gcloud logging read \
  "resource.type=cloud_run_job AND resource.labels.job_name=${JOB_NAME} AND resource.labels.location=${REGION}" \
  --project="${PROJECT_ID}" \
  --limit=200 \
  --format="table(timestamp,textPayload)" \
  --freshness=10m \
  | grep -v "^$" | head -150

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  🎉  Deployment complete!"
echo "  View full logs:"
echo "  gcloud run jobs executions describe ${EXECUTION_NAME} \\"
echo "    --project=${PROJECT_ID} --region=${REGION}"
echo "════════════════════════════════════════════════════════════"
