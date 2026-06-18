#!/bin/bash
# GCP L4 GPU Benchmark Startup Script
# Auto-terminates after benchmark completion.
set -euo pipefail

RESULTS_BUCKET="gs://agora-autoresearch-001-benchmark-results"
RESULTS_FILE="/tmp/gpu_benchmark_results.json"
LOG_FILE="/tmp/gpu_benchmark.log"

exec > >(tee -a "$LOG_FILE") 2>&1

echo "=========================================="
echo "S20 GPU Benchmark — Startup $(date -u)"
echo "=========================================="

# ── Install dependencies ──
apt-get update -qq && apt-get install -y -qq python3-pip git > /dev/null 2>&1
pip3 install --quiet torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
pip3 install --quiet transformers accelerate huggingface_hub

# ── Clone repo ──
cd /tmp
git clone https://github.com/xaviercallens/Mirror-Map-Sieve.git
cd Mirror-Map-Sieve/4_ai_hardware_attention

# ── GPU diagnostics ──
echo ""
nvidia-smi
echo ""
python3 -c "import torch; print(f'PyTorch {torch.__version__}, CUDA {torch.version.cuda}, GPU: {torch.cuda.get_device_name(0)}')"

# ── Run benchmark ──
echo ""
echo "Starting S20 GPU benchmark..."
python3 gpu_benchmark_s20.py \
    --model microsoft/Phi-3-mini-4k-instruct \
    --seq_lens 64 128 256 512 1024 \
    --output "$RESULTS_FILE" 2>&1

echo ""
echo "Benchmark complete at $(date -u)"

# ── Upload results ──
gsutil cp "$RESULTS_FILE" "${RESULTS_BUCKET}/gpu_benchmark_results_$(date +%Y%m%d_%H%M%S).json" 2>/dev/null || \
    echo "Warning: Could not upload to GCS. Results saved locally at $RESULTS_FILE"
gsutil cp "$LOG_FILE" "${RESULTS_BUCKET}/gpu_benchmark_$(date +%Y%m%d_%H%M%S).log" 2>/dev/null || true

# ── Self-terminate ──
echo "Self-terminating instance..."
ZONE=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/zone | cut -d/ -f4)
INSTANCE=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/name)
gcloud compute instances delete "$INSTANCE" --zone="$ZONE" --quiet 2>/dev/null || \
    shutdown -h now
