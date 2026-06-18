#!/bin/bash
# benchmark_multi_model.sh — GCP T4/L4 startup script for S20 multi-model benchmark
# Usage: gcloud compute ssh ... -- 'bash -s' < benchmark_multi_model.sh
set -euo pipefail

echo "=== Installing dependencies ==="
pip install --quiet --upgrade pip
pip install --quiet torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124 2>/dev/null || true
pip install --quiet "transformers==4.49.0" accelerate datasets sentencepiece protobuf httpx httpcore huggingface_hub

echo ""
echo "=== Cloning benchmark ==="
if [ ! -d "Mirror-Map-Sieve" ]; then
    git clone --depth 1 https://github.com/xaviercallens/Mirror-Map-Sieve.git
fi
cd Mirror-Map-Sieve/4_ai_hardware_attention

echo ""
echo "=== Running multi-model benchmark ==="
# Run all 4 models with perplexity evaluation
python gpu_benchmark_multi_model.py \
    --models phi3 gemma2 qwen25 mistral \
    --output /tmp/multi_model_results.json 2>&1 | tee /tmp/benchmark.log

echo ""
echo "=== Uploading to GCS ==="
BUCKET="gs://agora-autoresearch-001-benchmark-results"
gsutil mb -l us-west4 "$BUCKET" 2>/dev/null || true
TIMESTAMP=$(date -u +%Y%m%dT%H%M%S)
gsutil cp /tmp/multi_model_results.json "$BUCKET/v2/${TIMESTAMP}_multi_model_results.json"
gsutil cp /tmp/benchmark.log "$BUCKET/v2/${TIMESTAMP}_benchmark.log"
echo "✅ Uploaded to $BUCKET/v2/"

echo ""
echo "=== Results JSON ==="
cat /tmp/multi_model_results.json

echo ""
echo "=== DONE ==="
