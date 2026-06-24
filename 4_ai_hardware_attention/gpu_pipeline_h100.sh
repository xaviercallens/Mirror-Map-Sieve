#!/bin/bash
# gpu_pipeline_h100.sh — full train->gate pipeline for an 80GB node (H100/A100-80G).
#
# Runs the WHOLE experiment unattended on a fresh GPU box, writing everything to GCS
# (the dev box is disk-full; the GPU node is ephemeral — NOTHING valuable stays local):
#   1. train a LEARNABLE-ALiBi model FROM SCRATCH at 4k ctx -> checkpoint to GCS
#   2. train a FIXED-ALiBi control (identical arch) FROM SCRATCH -> checkpoint to GCS
#   3. run the PURE-DENSE extrapolation gate (1x/2x/4x/8x = 4k..32k) on BOTH, on PG-19,
#      with NVML energy/CO2e -> results to GCS
#   4. self-terminate (GCP) or shutdown (other clouds)
#
# CLOUD-AGNOSTIC: the body assumes only `python3`, a CUDA GPU, and gsutil+ADC for GCS.
#   * GCP DLVM: works as-is (gsutil + metadata self-delete present).
#   * AWS p5 / Lambda H100: set GCS auth first (see "PORTABLE AUTH" below); the
#     metadata self-delete is skipped and it falls back to `shutdown -h now`.
#
# CONFIG via env (with defaults):
#   PRESET=base   TOKENS=10000000000   DATASET=pg19   CTX=4096
#   GATE_LENGTHS="4096 8192 16384 32768"
#   BUCKET=gs://gen-lang-client-0625573011-cy-sieve-bench
set -uo pipefail

PRESET="${PRESET:-base}"
TOKENS="${TOKENS:-10000000000}"
DATASET="${DATASET:-pg19}"
CTX="${CTX:-4096}"
GATE_LENGTHS="${GATE_LENGTHS:-4096 8192 16384 32768}"
BUCKET="${BUCKET:-gs://gen-lang-client-0625573011-cy-sieve-bench}"
STAMP="$(date +%Y%m%d_%H%M%S)"
RUN="h100_${PRESET}_${STAMP}"
CKPT_GCS="${BUCKET}/checkpoints/${RUN}"
RESULTS_GCS="${BUCKET}/dense_gate"
LOG_FILE="/tmp/${RUN}.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== H100 train->gate pipeline | run=${RUN} | $(date -u) ==="
nvidia-smi || echo "WARN no nvidia-smi"

# --- deps (pin transformers<5: 5.x dlopens a broken torchaudio on DLVM; drop it) ---
pip3 install --quiet "transformers>=4.40,<5" "datasets>=2.19" accelerate safetensors \
    huggingface_hub xxhash multiprocess pandas pyarrow fsspec "requests>=2.32.2" \
    pynvml 2>&1 | tail -3 || true
pip3 uninstall -y torchaudio torchvision 2>/dev/null || true
# FlashAttention-2 (best-effort; the gate falls back to PyTorch SDPA, also O(L) memory)
pip3 install --quiet flash-attn --no-build-isolation 2>&1 | tail -2 || echo "  (flash-attn unavailable; using SDPA)"
python3 -c "import torch,transformers;print('torch',torch.__version__,'tf',transformers.__version__,'cuda',torch.cuda.is_available())" || true

# --- code ---
cd /tmp; rm -rf Mirror-Map-Sieve
git clone --depth 1 https://github.com/xaviercallens/Mirror-Map-Sieve.git
cd /tmp/Mirror-Map-Sieve/4_ai_hardware_attention

# Use FA-2 in the gate only if it imported cleanly.
FLASH_FLAG=""; python3 -c "import flash_attn" 2>/dev/null && FLASH_FLAG="--flash2"

# --- 1+2. train both checkpoints from scratch (stream corpus, checkpoint to GCS) ---
for MODE in learnable fixed; do
  echo "=== train ${MODE}-ALiBi from scratch (${PRESET}, ${TOKENS} tok) $(date -u) ==="
  python3 train_learnable_alibi_scratch.py --preset "$PRESET" --mode "$MODE" \
      --tokens "$TOKENS" --ctx "$CTX" --dataset "$DATASET" --bf16 \
      --save-dir "/tmp/ckpt_${MODE}" --gcs "${CKPT_GCS}/${MODE}/" --ckpt-every 2000
  echo "  ${MODE} train rc=$? at $(date -u)"
done

# --- 3. pure-dense extrapolation gate on BOTH (PG-19, energy) ---
echo "=== dense extrapolation gate (lengths ${GATE_LENGTHS}) $(date -u) ==="
python3 dense_extrapolation_gate.py \
    --model "/tmp/ckpt_learnable" --slopes-file "/tmp/ckpt_learnable/slopes.json" \
    --control "/tmp/ckpt_fixed"   --control-slopes "/tmp/ckpt_fixed/slopes.json" \
    --lengths $GATE_LENGTHS --dataset pg19 --max-windows 16 --bf16 $FLASH_FLAG \
    --output "/tmp/dense_gate_${RUN}.json"
echo "  gate rc=$? at $(date -u)"

# --- upload results + log ---
for f in "/tmp/dense_gate_${RUN}.json" "$LOG_FILE"; do
  [ -f "$f" ] && gsutil cp "$f" "${RESULTS_GCS}/$(basename "$f")" && echo "uploaded $(basename "$f")" \
    || echo "WARN upload $f"
done

# --- 4. self-terminate ---
echo "=== self-terminate $(date -u) ==="
ZONE=$(curl -s -m 3 -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/zone 2>/dev/null | cut -d/ -f4)
INSTANCE=$(curl -s -m 3 -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/name 2>/dev/null)
if [ -n "${ZONE:-}" ] && [ -n "${INSTANCE:-}" ]; then
  gcloud compute instances delete "$INSTANCE" --zone="$ZONE" --quiet 2>/dev/null || shutdown -h now
else
  echo "non-GCP node (no metadata server) — shutting down"; shutdown -h now
fi

# =====================================================================
# PORTABLE AUTH (AWS p5 / Lambda — run BEFORE this script, not part of it):
#   1. Copy a GCS-writer service-account key to the node, then:
#        export GOOGLE_APPLICATION_CREDENTIALS=/path/key.json
#        gcloud auth activate-service-account --key-file=$GOOGLE_APPLICATION_CREDENTIALS
#   2. pip install gsutil  (or use `gcloud storage`), then run this script.
# GCP LAUNCH (only if A100-80G/H100 quota is granted — currently 0 in this project):
#   gcloud compute instances create cy-h100-gate --project=<P> --zone=<Z> \
#     --machine-type=a3-highgpu-1g --accelerator=type=nvidia-h100-80gb,count=1 \   # or a2-ultragpu-1g + nvidia-a100-80gb
#     --maintenance-policy=TERMINATE --provisioning-model=STANDARD \
#     --image-family=pytorch-2-9-cu129-ubuntu-2204-nvidia-580 \
#     --image-project=deeplearning-platform-release \
#     --boot-disk-size=300GB --scopes=https://www.googleapis.com/auth/cloud-platform \
#     --metadata-from-file=startup-script=gpu_pipeline_h100.sh
#   ALWAYS arm a killswitch whose margin EXCEEDS the full train+gate runtime
#   (base preset ~ many hours): see /tmp/l4_retry_launch.sh for the scheduler pattern.
# =====================================================================
