#!/bin/bash
# GCP L4 GPU Benchmark Startup Script (v2 — uses pre-installed PyTorch)
# Auto-terminates after benchmark completion.
set -uo pipefail  # Don't use -e, we handle errors ourselves

RESULTS_BUCKET="gs://agora-autoresearch-001-benchmark-results"
RESULTS_FILE="/tmp/gpu_benchmark_results.json"
LOG_FILE="/tmp/gpu_benchmark.log"

exec > >(tee -a "$LOG_FILE") 2>&1

echo "=========================================="
echo "S20 GPU Benchmark — Startup $(date -u)"
echo "=========================================="

# ── GPU diagnostics ──
nvidia-smi || { echo "ERROR: nvidia-smi not found"; exit 1; }
echo ""

# ── Install only what's needed (don't reinstall torch — it's pre-installed) ──
pip3 install --quiet --no-deps transformers==4.49.0 accelerate huggingface_hub sentencepiece protobuf 2>&1 | tail -5
# Pin transformers to 4.49 which doesn't have the torchaudio import issue

echo ""
python3 -c "
import torch
print(f'PyTorch {torch.__version__}, CUDA {torch.version.cuda}')
print(f'GPU: {torch.cuda.get_device_name(0)}')
print(f'VRAM: {torch.cuda.get_device_properties(0).total_mem / 1e9:.1f} GB')
import transformers
print(f'Transformers: {transformers.__version__}')
"

# ── Clone repo ──
cd /tmp
rm -rf Mirror-Map-Sieve
git clone --depth 1 https://github.com/xaviercallens/Mirror-Map-Sieve.git
cd Mirror-Map-Sieve/4_ai_hardware_attention

# ── Run benchmark ──
echo ""
echo "Starting S20 GPU benchmark at $(date -u)..."
python3 gpu_benchmark_s20.py \
    --model microsoft/Phi-3-mini-4k-instruct \
    --seq_lens 64 128 256 512 1024 \
    --output "$RESULTS_FILE" 2>&1

BENCH_EXIT=$?
echo ""
echo "Benchmark exit code: $BENCH_EXIT at $(date -u)"

# ── Upload results ──
if [ -f "$RESULTS_FILE" ]; then
    gsutil cp "$RESULTS_FILE" "${RESULTS_BUCKET}/gpu_benchmark_results_$(date +%Y%m%d_%H%M%S).json" 2>/dev/null && \
        echo "✅ Results uploaded to GCS" || \
        echo "⚠ Could not upload to GCS. Results saved locally at $RESULTS_FILE"
fi
gsutil cp "$LOG_FILE" "${RESULTS_BUCKET}/gpu_benchmark_$(date +%Y%m%d_%H%M%S).log" 2>/dev/null || true

# ── Self-terminate ──
echo "Self-terminating instance at $(date -u)..."
ZONE=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/zone | cut -d/ -f4)
INSTANCE=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/name)
gcloud compute instances delete "$INSTANCE" --zone="$ZONE" --quiet 2>/dev/null || \
    shutdown -h now
