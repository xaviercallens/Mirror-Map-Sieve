#!/usr/bin/env bash
# ─── Hilbert Agent v2.1 — Full GCP Deployment Script ───────────────────────
# Deploys: LeanBERT weights to GCS, DeepSeek-Prover-V2-7B to Cloud Run GPU,
#          and runs the sorry completion sweep.
#
# Cost budget: ~$5 total (T4 GPU ~$0.35/hr, build ~$2, storage ~$0.50)
# ────────────────────────────────────────────────────────────────────────────
set -euo pipefail

export PATH="/Users/xcallens/google-cloud-sdk/bin:$PATH"

PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1"
AR_REPO="agora"
BUCKET="gs://${PROJECT_ID}-hilbert-artifacts"
LEANBERT_WEIGHTS_DIR="/Users/xcallens/xdev/SocrateAI-Lean-Verification/autoresearch/data"

echo "═══════════════════════════════════════════════════════════════"
echo "  Hilbert Agent v2.1 — GCP Deployment"
echo "  Project: ${PROJECT_ID} | Region: ${REGION}"
echo "═══════════════════════════════════════════════════════════════"

# ── Step 1: Train LeanBERT weights locally if not present ─────────────────
echo ""
echo "── Step 1: LeanBERT Model Weights ──────────────────────────────"

if [ -f "${LEANBERT_WEIGHTS_DIR}/best_generator.pt" ] && [ -f "${LEANBERT_WEIGHTS_DIR}/lean4_vocab.json" ]; then
    echo "✓ LeanBERT weights found locally"
else
    echo "⏳ Training LeanBERT GAN (5 epochs, CPU)..."
    cd /Users/xcallens/xdev/SocrateAI-Lean-Verification/autoresearch
    /Users/xcallens/xdev/SocrateAI-Scientific-Agora/.venv/bin/python train.py \
        --epochs 5 \
        --batch-size 32 \
        --save-dir "${LEANBERT_WEIGHTS_DIR}" 2>&1 | tail -20
    echo "✓ LeanBERT training complete"
fi

# Upload weights to GCS
echo "⏳ Uploading LeanBERT weights to ${BUCKET}/leanbert/..."
gcloud storage buckets create "${BUCKET}" --location="${REGION}" 2>/dev/null || true
gcloud storage cp "${LEANBERT_WEIGHTS_DIR}/best_generator.pt" "${BUCKET}/leanbert/" 2>/dev/null || true
gcloud storage cp "${LEANBERT_WEIGHTS_DIR}/best_critic.pt" "${BUCKET}/leanbert/" 2>/dev/null || true
gcloud storage cp "${LEANBERT_WEIGHTS_DIR}/lean4_vocab.json" "${BUCKET}/leanbert/" 2>/dev/null || true
echo "✓ LeanBERT weights uploaded to GCS"

# ── Step 2: Build & Deploy DeepSeek-Prover-V2-7B ─────────────────────────
echo ""
echo "── Step 2: DeepSeek-Prover-V2-7B Container ────────────────────"

cd /Users/xcallens/xdev/SocrateAI-Scientific-Agora

# Use Cloud Build to build the container (avoids local Docker/GPU issues)
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/deepseek-prover-v2:1.0.0"

echo "⏳ Building container image via Cloud Build..."
echo "   (This downloads 7B model weights during build — ~15 minutes)"
gcloud builds submit \
    --config=/dev/stdin \
    --timeout=3600 \
    --machine-type=e2-highcpu-32 \
    deploy/ <<EOF
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', '${IMAGE}', '-f', 'deepseek-prover.Dockerfile', '.']
images: ['${IMAGE}']
EOF

echo "✓ DeepSeek-Prover-V2-7B container built"

# Deploy to Cloud Run with GPU
echo "⏳ Deploying to Cloud Run with T4 GPU..."
gcloud run deploy deepseek-prover-v2 \
    --image="${IMAGE}" \
    --region="${REGION}" \
    --platform=managed \
    --no-allow-unauthenticated \
    --ingress=internal \
    --cpu=4 \
    --memory=16Gi \
    --gpu=1 \
    --gpu-type=nvidia-l4 \
    --min-instances=0 \
    --max-instances=1 \
    --timeout=300 \
    --concurrency=2 \
    --set-env-vars="MODEL_ID=deepseek-ai/DeepSeek-Prover-V2-7B,QUANTIZE=awq,GPU_MEMORY_UTILIZATION=0.90,MAX_TOKENS=1024,PORT=8080" \
    --execution-environment=gen2 \
    --cpu-boost

DEEPSEEK_URL=$(gcloud run services describe deepseek-prover-v2 --region="${REGION}" --format="value(status.url)")
echo "✓ DeepSeek-Prover-V2-7B deployed at: ${DEEPSEEK_URL}"

# ── Step 3: Deploy Sorry Completion Cloud Run Job ─────────────────────────
echo ""
echo "── Step 3: Sorry Completion Sweep (Cloud Run Job) ─────────────"

# Get Gemini API key from Secret Manager
GEMINI_KEY=$(gcloud secrets versions access latest --secret=gemini-api-key 2>/dev/null || echo "${GEMINI_API_KEY:-}")

# Run the sweep directly via Cloud Run Job
echo "⏳ Running sorry completion sweep (max_difficulty=medium)..."
gcloud run jobs create sorry-completion-sweep \
    --image="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/agora-hilbert:latest" \
    --region="${REGION}" \
    --cpu=4 \
    --memory=8Gi \
    --max-retries=1 \
    --task-timeout=1800 \
    --set-env-vars="DEEPSEEK_PROVER_ENDPOINT=${DEEPSEEK_URL}/prove,GEMINI_API_KEY=${GEMINI_KEY}" \
    --command="python" \
    --args="-m,agents.hilbert.tools.sorry_completer,--root,Agora,--apply,--max-difficulty,medium" \
    2>/dev/null || \
gcloud run jobs update sorry-completion-sweep \
    --image="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/agora-hilbert:latest" \
    --region="${REGION}" \
    --set-env-vars="DEEPSEEK_PROVER_ENDPOINT=${DEEPSEEK_URL}/prove,GEMINI_API_KEY=${GEMINI_KEY}" 2>/dev/null

gcloud run jobs execute sorry-completion-sweep --region="${REGION}" --wait

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✓ Deployment Complete"
echo "  DeepSeek Endpoint: ${DEEPSEEK_URL}"
echo "  LeanBERT Weights:  ${BUCKET}/leanbert/"
echo "═══════════════════════════════════════════════════════════════"
