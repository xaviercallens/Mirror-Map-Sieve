#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# setup_secrets.sh — Create/update Secret Manager secrets for
#                    the Tesla Prototyping Pipeline
# Project: gen-lang-client-0625573011
# ─────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_ID="gen-lang-client-0625573011"
REGION="us-central1"

# Color helpers
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── Pre-flight checks ────────────────────────────────────────
if ! command -v gcloud &>/dev/null; then
    error "gcloud CLI not found. Install it from https://cloud.google.com/sdk/docs/install"
    exit 1
fi

info "Using project: ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}" --quiet

# Enable required APIs (idempotent)
info "Enabling Secret Manager API..."
gcloud services enable secretmanager.googleapis.com --project="${PROJECT_ID}" --quiet

# ── Resolve service account ──────────────────────────────────
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
CLOUD_RUN_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

info "Cloud Run service account: ${CLOUD_RUN_SA}"

# ── Helper: create or update a secret ────────────────────────
create_or_update_secret() {
    local secret_name="$1"
    local prompt_msg="$2"

    if gcloud secrets describe "${secret_name}" --project="${PROJECT_ID}" &>/dev/null; then
        warn "Secret '${secret_name}' already exists."
        read -rp "  → Add a new version? (y/N): " update_choice
        if [[ "${update_choice}" =~ ^[Yy]$ ]]; then
            read -rsp "  → Enter new value for ${secret_name}: " secret_value
            echo
            echo -n "${secret_value}" | gcloud secrets versions add "${secret_name}" \
                --data-file=- \
                --project="${PROJECT_ID}"
            info "New version added to '${secret_name}'."
        else
            info "Skipping update for '${secret_name}'."
        fi
    else
        info "Creating secret '${secret_name}'..."
        read -rsp "  → ${prompt_msg}: " secret_value
        echo
        if [[ -z "${secret_value}" ]]; then
            error "Secret value cannot be empty. Aborting."
            exit 1
        fi
        echo -n "${secret_value}" | gcloud secrets create "${secret_name}" \
            --data-file=- \
            --replication-policy="automatic" \
            --project="${PROJECT_ID}"
        info "Secret '${secret_name}' created."
    fi
}

# ── Helper: grant accessor role (idempotent) ─────────────────
grant_secret_access() {
    local secret_name="$1"
    local sa="$2"

    info "Granting secretAccessor on '${secret_name}' to ${sa}..."
    gcloud secrets add-iam-policy-binding "${secret_name}" \
        --member="serviceAccount:${sa}" \
        --role="roles/secretmanager.secretAccessor" \
        --project="${PROJECT_ID}" \
        --quiet \
        --condition=None 2>/dev/null || true
    info "Access granted for '${secret_name}'."
}

# ── Create/update secrets ────────────────────────────────────
echo ""
info "=== Setting up Secret Manager secrets ==="
echo ""

create_or_update_secret "gemini-api-key" "Enter your GEMINI_API_KEY"
create_or_update_secret "mistral-api-key" "Enter your MISTRAL_API_KEY"

# ── Grant access to Cloud Run service account ────────────────
echo ""
info "=== Granting Cloud Run service account access ==="
echo ""

grant_secret_access "gemini-api-key" "${CLOUD_RUN_SA}"
grant_secret_access "mistral-api-key" "${CLOUD_RUN_SA}"

echo ""
info "✅ Secret Manager setup complete!"
info "Secrets are ready for Cloud Run deployment."
