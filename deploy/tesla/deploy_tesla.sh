#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# deploy_tesla.sh — Master deployment script for Tesla
#                   Prototyping Pipeline on Cloud Run
# Project: gen-lang-client-0625573011
# Region:  us-central1
# Service: tesla-prototyping-pipeline
# ─────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_ID="gen-lang-client-0625573011"
REGION="us-central1"
SERVICE_NAME="tesla-prototyping-pipeline"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Color helpers
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }
header(){ echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════${NC}"; echo -e "${BOLD}${CYAN}  $*${NC}"; echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════${NC}\n"; }

# ── Pre-flight checks ────────────────────────────────────────
header "Pre-flight Checks"

if ! command -v gcloud &>/dev/null; then
    error "gcloud CLI not found. Install: https://cloud.google.com/sdk/docs/install"
    exit 1
fi
info "gcloud CLI found: $(gcloud --version 2>&1 | head -1)"

# Verify authentication
ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null || true)
if [[ -z "${ACCOUNT}" ]]; then
    error "No active gcloud account. Run: gcloud auth login"
    exit 1
fi
info "Authenticated as: ${ACCOUNT}"

# Set project
gcloud config set project "${PROJECT_ID}" --quiet
info "Project set to: ${PROJECT_ID}"

# Verify required files exist
for f in "${SCRIPT_DIR}/Dockerfile.tesla" "${SCRIPT_DIR}/cloudbuild_tesla.yaml" "${SCRIPT_DIR}/setup_secrets.sh"; do
    if [[ ! -f "${f}" ]]; then
        error "Required file not found: ${f}"
        exit 1
    fi
done
info "All required deployment files present."

# Enable required APIs
info "Enabling required GCP APIs..."
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    secretmanager.googleapis.com \
    artifactregistry.googleapis.com \
    --project="${PROJECT_ID}" --quiet
info "APIs enabled."

# ── Step 1: Setup Secrets ────────────────────────────────────
header "Step 1/3 — Secret Manager Setup"

read -rp "Run secret setup? (Y/n): " run_secrets
if [[ ! "${run_secrets}" =~ ^[Nn]$ ]]; then
    chmod +x "${SCRIPT_DIR}/setup_secrets.sh"
    bash "${SCRIPT_DIR}/setup_secrets.sh"
else
    warn "Skipping secret setup. Ensure secrets exist in Secret Manager."
fi

# ── Step 2: Submit Cloud Build ───────────────────────────────
header "Step 2/3 — Cloud Build Submission"

info "Submitting build from project root: ${PROJECT_ROOT}"
info "Build config: deploy/tesla/cloudbuild_tesla.yaml"
echo ""

# Use a short SHA substitute for manual builds (no git SHA available in local)
SHORT_SHA=$(git -C "${PROJECT_ROOT}" rev-parse --short HEAD 2>/dev/null || echo "manual-$(date +%Y%m%d%H%M%S)")
info "Image tag: ${SHORT_SHA}"

gcloud builds submit "${PROJECT_ROOT}" \
    --config="${SCRIPT_DIR}/cloudbuild_tesla.yaml" \
    --project="${PROJECT_ID}" \
    --substitutions="SHORT_SHA=${SHORT_SHA}" \
    --region="${REGION}" \
    --quiet

info "Cloud Build completed successfully."

# ── Step 3: Print Service URL ────────────────────────────────
header "Step 3/3 — Deployment Summary"

SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --format='value(status.url)' 2>/dev/null || echo "")

if [[ -n "${SERVICE_URL}" ]]; then
    echo ""
    info "╔══════════════════════════════════════════════════╗"
    info "║  🚀 Tesla Prototyping Pipeline deployed!         ║"
    info "╚══════════════════════════════════════════════════╝"
    echo ""
    info "Service: ${SERVICE_NAME}"
    info "Region:  ${REGION}"
    info "URL:     ${SERVICE_URL}"
    info "Tag:     ${SHORT_SHA}"
    echo ""
    info "Useful commands:"
    info "  Logs:    gcloud run services logs read ${SERVICE_NAME} --region=${REGION} --project=${PROJECT_ID}"
    info "  Desc:    gcloud run services describe ${SERVICE_NAME} --region=${REGION} --project=${PROJECT_ID}"
    info "  Invoke:  curl -H \"Authorization: Bearer \$(gcloud auth print-identity-token)\" ${SERVICE_URL}"
    echo ""
else
    warn "Could not retrieve service URL. Check the Cloud Run console:"
    warn "  https://console.cloud.google.com/run/detail/${REGION}/${SERVICE_NAME}?project=${PROJECT_ID}"
fi
