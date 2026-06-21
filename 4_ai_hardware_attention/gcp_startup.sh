#!/bin/bash
# GCP L4 GPU startup — CY-Sieve GPU phase (tests.md §4 parity / §5 quality / §6 perf).
# Runs run_gpu_phase.py, uploads results to GCS, then self-terminates.
# v3 — replaces the stale gpu_benchmark_s20.py path with the CY-Sieve orchestrator.
set -uo pipefail   # no -e: we handle errors and always try to upload + self-delete

RESULTS_BUCKET="gs://gen-lang-client-0625573011-cy-sieve-bench"
WORKDIR="/tmp/Mirror-Map-Sieve/4_ai_hardware_attention"
STAMP="$(date +%Y%m%d_%H%M%S)"
RESULTS_FILE="/tmp/gpu_phase_results_${STAMP}.json"
LOG_FILE="/tmp/gpu_phase_${STAMP}.log"

exec > >(tee -a "$LOG_FILE") 2>&1
echo "=========================================="
echo "CY-Sieve GPU phase — startup $(date -u)"
echo "=========================================="

# ── GPU diagnostics ──
nvidia-smi || { echo "ERROR: nvidia-smi not found (no GPU?)"; }

# ── Dependencies. The DLVM images ship torch+triton; add the quality-gate deps.
#    pytest is NOT on the image (§4 needs it); xxhash is required by datasets to
#    actually load WikiText-2 (without it the gate silently falls back to its tiny
#    synthetic corpus and every scheme scores ppl~1.0 — a vacuous PASS).
pip3 install --quiet pytest xxhash 2>&1 | tail -3 || true
pip3 install --quiet --no-deps datasets 2>&1 | tail -3 || true
pip3 install --quiet "requests>=2.32.2" huggingface_hub fsspec pyarrow 2>&1 | tail -3 || true

python3 - <<'PY'
import torch
print(f"PyTorch {torch.__version__}, CUDA {torch.version.cuda}")
print(f"GPU: {torch.cuda.get_device_name(0)}")
print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory/1e9:.1f} GB")
try:
    import triton; print(f"Triton {triton.__version__}")
except Exception as e:
    print(f"Triton import failed: {e}")
PY

# ── Clone the repo ──
cd /tmp
rm -rf Mirror-Map-Sieve
git clone --depth 1 https://github.com/xaviercallens/Mirror-Map-Sieve.git
cd "$WORKDIR"

# ── Run the full GPU phase (§4 + §5 + §6) ──
echo ""
echo "Starting CY-Sieve GPU phase at $(date -u)..."
python3 run_gpu_phase.py --output "$RESULTS_FILE" 2>&1
BENCH_EXIT=$?
echo ""
echo "GPU phase exit code: $BENCH_EXIT at $(date -u)"

# ── Upload results + the per-section JSONs + log ──
for f in "$RESULTS_FILE" \
         "$WORKDIR/cy_sieve_quality_results.json" \
         "$WORKDIR/cy_sieve_perf_results.json"; do
    [ -f "$f" ] && gsutil cp "$f" "${RESULTS_BUCKET}/cy_sieve/$(basename "$f" .json)_${STAMP}.json" \
        && echo "✅ uploaded $(basename "$f")" || echo "⚠ could not upload $f"
done
gsutil cp "$LOG_FILE" "${RESULTS_BUCKET}/cy_sieve/$(basename "$LOG_FILE")" 2>/dev/null || true

# ── Self-terminate ──
echo "Self-terminating instance at $(date -u)..."
ZONE=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/zone | cut -d/ -f4)
INSTANCE=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/name)
gcloud compute instances delete "$INSTANCE" --zone="$ZONE" --quiet 2>/dev/null || shutdown -h now
