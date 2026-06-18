#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# deploy_inventory_pipeline.sh
# Builds and deploys the Agora Inventory & Applied Math Discovery Pipeline as a Cloud Run JOB.
#
# Secrets required in GCP Secret Manager (project: agora-autoresearch-001):
#   GEMINI_API_KEY      — Google Gemini API key
#   MISTRAL_API_KEY     - Mistral API key (mapped to GALOIS_MISTRAL_KEY)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_ID="agora-autoresearch-001"
REGION="us-central1"
IMAGE_NAME="inventory-pipeline"
JOB_NAME="inventory-pipeline"
IMAGE_URI="gcr.io/${PROJECT_ID}/${IMAGE_NAME}:latest"

# Compute SA for Secret Manager access
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")
SA_EMAIL="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "════════════════════════════════════════════════════════════"
echo "  📦  Agora Inventory Pipeline — GCP Deployment"
echo "  Project : ${PROJECT_ID}"
echo "  Region  : ${REGION}"
echo "  Job     : ${JOB_NAME}"
echo "════════════════════════════════════════════════════════════"

# ── 1. Grant Secret Manager access
echo ""
echo "[1/4] Granting secretmanager.secretAccessor to ${SA_EMAIL}..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" \
  --quiet

# ── 2. Build image with Cloud Build
echo ""
echo "[2/4] Building Docker image with Cloud Build (Dockerfile.inventory)..."
gcloud builds submit \
  --project="${PROJECT_ID}" \
  --config="cloudbuild.inventory.yaml" \
  --timeout="25m" \
  .

echo "  ✅ Image built: ${IMAGE_URI}"

# ── 3. Create or update the Cloud Run Job
echo ""
echo "[3/4] Creating / updating Cloud Run Job '${JOB_NAME}'..."
gcloud run jobs update "${JOB_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE_URI}" \
  --set-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest,GALOIS_MISTRAL_KEY=MISTRAL_API_KEY:latest" \
  --memory="4Gi" \
  --cpu="2" \
  --task-timeout="3600s" \
  --max-retries=0 \
  2>/dev/null || \
gcloud run jobs create "${JOB_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE_URI}" \
  --set-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest,GALOIS_MISTRAL_KEY=MISTRAL_API_KEY:latest" \
  --memory="4Gi" \
  --cpu="2" \
  --task-timeout="3600s" \
  --max-retries=0

echo "  ✅ Cloud Run Job configured"

# ── 4. Execute the job
echo ""
echo "[4/4] 🚀 Executing Cloud Run Job '${JOB_NAME}'..."
EXECUTION_NAME=$(gcloud run jobs execute "${JOB_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --format="value(metadata.name)")

echo "  ✅ Execution started: ${EXECUTION_NAME}"
echo "════════════════════════════════════════════════════════════"
echo "  🏁  Deployment complete"
echo "  Job     : ${JOB_NAME} (${EXECUTION_NAME})"
echo "════════════════════════════════════════════════════════════"
