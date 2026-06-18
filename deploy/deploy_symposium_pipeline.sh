#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# deploy_symposium_pipeline.sh
# Builds and deploys the Agora Symposium pipeline as a Cloud Run JOB
# on project: agora-autoresearch-001
#
# Secrets injected from GCP Secret Manager:
#   - GEMINI_API_KEY   → secret: GEMINI_API_KEY  (latest version)
#   - MISTRAL_API_KEY  → secret: MISTRAL_API_KEY (latest version)
#
# Usage:
#   chmod +x deploy/deploy_symposium_pipeline.sh
#   ./deploy/deploy_symposium_pipeline.sh                              # default template
#   ./deploy/deploy_symposium_pipeline.sh plasma_fusion_iter           # custom template
#   ./deploy/deploy_symposium_pipeline.sh cycloreactor_environment --logs  # tail logs
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SYMPOSIUM_TEMPLATE="${1:-cycloreactor_environment}"
TAIL_LOGS="${2:-}"

PROJECT_ID="agora-autoresearch-001"
REGION="us-central1"
IMAGE_NAME="symposium-pipeline"
JOB_NAME="symposium-pipeline"
IMAGE_URI="gcr.io/${PROJECT_ID}/${IMAGE_NAME}:latest"

# Grant the Cloud Run SA access to Secret Manager (idempotent)
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")
SA_EMAIL="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "════════════════════════════════════════════════════════════"
echo "  🏛️  Agora Symposium Pipeline — GCP Deployment"
echo "  Project  : ${PROJECT_ID}"
echo "  Region   : ${REGION}"
echo "  Job      : ${JOB_NAME}"
echo "  Template : ${SYMPOSIUM_TEMPLATE}"
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
echo "      Using Dockerfile.symposium for texlive-full + Symposium pipeline..."
gcloud builds submit \
  --project="${PROJECT_ID}" \
  --config="cloudbuild.symposium.yaml" \
  --timeout="25m" \
  .

echo "  ✅ Image built: ${IMAGE_URI}"

# ── 3. Create or update the Cloud Run Job ────────────────────────────────────
# 4 CPU, 8Gi RAM, 2-hour timeout for 150-page monograph generation
echo ""
echo "[3/5] Creating/updating Cloud Run Job: ${JOB_NAME}..."
gcloud run jobs create "${JOB_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE_URI}" \
  --memory="8Gi" \
  --cpu="4" \
  --task-timeout="7200" \
  --max-retries="1" \
  --set-secrets="MISTRAL_API_KEY=MISTRAL_API_KEY:latest" \
  --set-env-vars="SYMPOSIUM_TEMPLATE=${SYMPOSIUM_TEMPLATE},DEEPSEEK_PROVER_ENDPOINT=https://deepseek-prover-v2-291479295008.us-central1.run.app/prove,GEMINI_API_KEY=${GEMINI_API_KEY}" \
  --command="python3" \
  --args="agents/symposium_runner.py" \
  2>/dev/null || \
gcloud run jobs update "${JOB_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE_URI}" \
  --memory="8Gi" \
  --cpu="4" \
  --task-timeout="7200" \
  --max-retries="1" \
  --set-secrets="MISTRAL_API_KEY=MISTRAL_API_KEY:latest" \
  --set-env-vars="SYMPOSIUM_TEMPLATE=${SYMPOSIUM_TEMPLATE},DEEPSEEK_PROVER_ENDPOINT=https://deepseek-prover-v2-291479295008.us-central1.run.app/prove,GEMINI_API_KEY=${GEMINI_API_KEY}" \

echo "  ✅ Cloud Run Job configured."

# ── 4. Execute the Job ────────────────────────────────────────────────────────
echo ""
echo "[4/5] 🚀 Executing Cloud Run Job: ${JOB_NAME} (template=${SYMPOSIUM_TEMPLATE})..."
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
  --freshness=15m \
  | grep -v "^$" | head -150

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  🎉  Symposium deployment complete!"
echo "  Template: ${SYMPOSIUM_TEMPLATE}"
echo "  View full logs:"
echo "  gcloud run jobs executions describe ${EXECUTION_NAME} \\"
echo "    --project=${PROJECT_ID} --region=${REGION}"
echo "════════════════════════════════════════════════════════════"
