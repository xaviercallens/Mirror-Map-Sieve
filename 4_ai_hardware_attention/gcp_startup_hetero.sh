#!/bin/bash
# GCP L4 startup — GPU validation of the hetero-positional hypothesis:
# does per-head softmax temperature (cb_softmax_temp) beat alibi_learn at scale?
set -uo pipefail
RESULTS_BUCKET="gs://gen-lang-client-0625573011-cy-sieve-bench"
WORKDIR="/tmp/Mirror-Map-Sieve/4_ai_hardware_attention"
STAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="/tmp/hetero_${STAMP}.log"
exec > >(tee -a "$LOG_FILE") 2>&1
echo "=== hetero-pos GPU validation — startup $(date -u) ==="
nvidia-smi || echo "WARN no nvidia-smi"
pip3 install --quiet "datasets>=2.19" xxhash multiprocess pandas "requests>=2.32.2" \
    huggingface_hub fsspec pyarrow 2>&1 | tail -3 || true
python3 -c "import torch,datasets;print('torch',torch.__version__,'cuda',torch.cuda.is_available())" || true
cd /tmp; rm -rf Mirror-Map-Sieve
git clone --depth 1 https://github.com/xaviercallens/Mirror-Map-Sieve.git
cd "$WORKDIR"
echo "=== run hetero-pos (full preset) $(date -u) ==="
python3 cy_sieve_hetero_pos.py --preset full \
    --modes alibi_fixed alibi_learn nope content_balance cb_softmax_temp \
    --output "/tmp/hetero_full_${STAMP}.json" 2>&1
echo "rc=$? at $(date -u)"
for f in "/tmp/hetero_full_${STAMP}.json" "$LOG_FILE"; do
    [ -f "$f" ] && gsutil cp "$f" "${RESULTS_BUCKET}/hetero/$(basename "$f")" \
        && echo "uploaded $(basename "$f")" || echo "WARN upload $f"
done
echo "=== self-terminate $(date -u) ==="
ZONE=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/zone | cut -d/ -f4)
INSTANCE=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/name)
gcloud compute instances delete "$INSTANCE" --zone="$ZONE" --quiet 2>/dev/null || shutdown -h now
