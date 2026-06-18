#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# deploy_discovery_pipeline.sh
# Builds and deploys the Agora Discovery Pipeline as a Cloud Run JOB.
#
# Mirrors deploy_symposium_pipeline.sh but for the 6-stage Discovery Pipeline.
#
# Usage:
#   chmod +x deploy/deploy_discovery_pipeline.sh
#   ./deploy/deploy_discovery_pipeline.sh                         # H1 validation
#   ./deploy/deploy_discovery_pipeline.sh h1_strassen_witness     # explicit
#   ./deploy/deploy_discovery_pipeline.sh h1_strassen_witness dry # dry-run (mocks)
#   ./deploy/deploy_discovery_pipeline.sh h1_strassen_witness --logs  # tail logs
#
# Secrets required in GCP Secret Manager (project: agora-autoresearch-001):
#   GEMINI_API_KEY  — Google Gemini API key (used by Darwin + Newton stages)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

DISCOVERY_TEMPLATE="${1:-h1_strassen_witness}"
MODE="${2:-}"                   # 'dry' = DRY_RUN=true, '--logs' = tail after
TAIL_LOGS=""
DRY_RUN_FLAG="false"

if [[ "${MODE}" == "dry" ]]; then
    DRY_RUN_FLAG="true"
    TAIL_LOGS="${3:-}"
elif [[ "${MODE}" == "--logs" ]]; then
    TAIL_LOGS="--logs"
fi

PROJECT_ID="agora-autoresearch-001"
REGION="us-central1"
IMAGE_NAME="discovery-pipeline"
JOB_NAME="discovery-pipeline"
IMAGE_URI="gcr.io/${PROJECT_ID}/${IMAGE_NAME}:latest"

# ── Compute SA for Secret Manager access ─────────────────────────────────────
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")
SA_EMAIL="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "════════════════════════════════════════════════════════════"
echo "  🔬  Agora Discovery Pipeline — GCP Deployment"
echo "  Project  : ${PROJECT_ID}"
echo "  Region   : ${REGION}"
echo "  Job      : ${JOB_NAME}"
echo "  Template : ${DISCOVERY_TEMPLATE}"
echo "  Dry Run  : ${DRY_RUN_FLAG}"
echo "════════════════════════════════════════════════════════════"

# ── 1. Grant Secret Manager access ───────────────────────────────────────────
echo ""
echo "[1/5] Granting secretmanager.secretAccessor to ${SA_EMAIL}..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" \
  --quiet

# ── 2. Build image with Cloud Build ──────────────────────────────────────────
echo ""
echo "[2/5] Building Docker image with Cloud Build (Dockerfile.discovery)..."
echo "      No texlive — fast build, target < 2 GB"
gcloud builds submit \
  --project="${PROJECT_ID}" \
  --config="cloudbuild.discovery.yaml" \
  --timeout="20m" \
  .

echo "  ✅ Image built: ${IMAGE_URI}"

# ── 3. Create or update the Cloud Run Job ────────────────────────────────────
echo ""
echo "[3/5] Creating / updating Cloud Run Job '${JOB_NAME}'..."
gcloud run jobs update "${JOB_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE_URI}" \
  --set-env-vars "DISCOVERY_TEMPLATE=${DISCOVERY_TEMPLATE},DRY_RUN=${DRY_RUN_FLAG}" \
  --set-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest" \
  --memory="4Gi" \
  --cpu="2" \
  --task-timeout="3600s" \
  --max-retries=1 \
  2>/dev/null || \
gcloud run jobs create "${JOB_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE_URI}" \
  --set-env-vars "DISCOVERY_TEMPLATE=${DISCOVERY_TEMPLATE},DRY_RUN=${DRY_RUN_FLAG}" \
  --set-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest" \
  --memory="4Gi" \
  --cpu="2" \
  --task-timeout="3600s" \
  --max-retries=1

echo "  ✅ Cloud Run Job configured"

# ── 4. Execute the job ────────────────────────────────────────────────────────
echo ""
echo "[4/5] Executing discovery job '${JOB_NAME}'..."
EXECUTION_NAME=$(gcloud run jobs execute "${JOB_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --format="value(metadata.name)" \
  --wait 2>/dev/null || \
  gcloud run jobs execute "${JOB_NAME}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --format="value(metadata.name)")

echo "  ✅ Execution started: ${EXECUTION_NAME}"

# ── 5. Tail logs (optional) ───────────────────────────────────────────────────
echo ""
if [[ -n "${TAIL_LOGS}" ]]; then
    echo "[5/5] Tailing logs for ${EXECUTION_NAME}..."
    gcloud logging read \
      "resource.type=cloud_run_job AND resource.labels.job_name=${JOB_NAME}" \
      --project="${PROJECT_ID}" \
      --format="value(textPayload)" \
      --freshness=10m \
      --limit=200
else
    echo "[5/5] Logs (skip tail — pass '--logs' to follow):"
    echo "      gcloud run jobs executions describe ${EXECUTION_NAME} \\"
    echo "        --project=${PROJECT_ID} --region=${REGION}"
    echo ""
    echo "  Monitor GCS output at:"
    echo "      gs://socrateai-alexandrie-vault/discovery/"
fi

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  🏁  Deployment complete"
echo "  Template: ${DISCOVERY_TEMPLATE}"
echo "  Job     : ${JOB_NAME} (${EXECUTION_NAME})"
echo "════════════════════════════════════════════════════════════"
