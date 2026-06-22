#!/bin/bash
# GCP L4 startup — CY-Sieve AUTORESEARCH: screen 13 schemes, then full-train the
# top-3 hypotheses + baselines. Uploads to GCS, self-terminates.
set -uo pipefail

RESULTS_BUCKET="gs://gen-lang-client-0625573011-cy-sieve-bench"
WORKDIR="/tmp/Mirror-Map-Sieve/4_ai_hardware_attention"
STAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="/tmp/autoresearch_${STAMP}.log"

exec > >(tee -a "$LOG_FILE") 2>&1
echo "=== CY-Sieve autoresearch — startup $(date -u) ==="
nvidia-smi || echo "WARN no nvidia-smi"

pip3 install --quiet "datasets>=2.19" xxhash multiprocess pandas \
    "requests>=2.32.2" huggingface_hub fsspec pyarrow 2>&1 | tail -3 || true
python3 -c "import torch,datasets; print('torch',torch.__version__,'datasets',datasets.__version__,'cuda',torch.cuda.is_available())" \
    || echo "WARN dep check failed"

cd /tmp; rm -rf Mirror-Map-Sieve
git clone --depth 1 https://github.com/xaviercallens/Mirror-Map-Sieve.git
cd "$WORKDIR"

echo "=== PHASE 1: SCREEN (13 schemes, reduced budget) $(date -u) ==="
python3 cy_sieve_autoresearch.py --phase screen \
    --manifest "/tmp/autoresearch_screen_${STAMP}.json" 2>&1
SCREEN_RC=$?
echo "screen rc=$SCREEN_RC at $(date -u)"

# upload the screen manifest immediately (so we keep it even if full fails)
gsutil cp "/tmp/autoresearch_screen_${STAMP}.json" \
    "${RESULTS_BUCKET}/autoresearch/screen_${STAMP}.json" 2>/dev/null \
    && echo "uploaded screen manifest" || echo "WARN screen upload failed"

echo "=== PHASE 2: FULL (top-3 CY + learned + sliding) $(date -u) ==="
python3 cy_sieve_autoresearch.py --phase full \
    --manifest "/tmp/autoresearch_screen_${STAMP}.json" \
    --output "/tmp/autoresearch_full_${STAMP}.json" 2>&1
echo "full rc=$? at $(date -u)"

# upload everything
for f in "/tmp/autoresearch_screen_${STAMP}.json" \
         "/tmp/autoresearch_full_${STAMP}.json" "$LOG_FILE"; do
    [ -f "$f" ] && gsutil cp "$f" "${RESULTS_BUCKET}/autoresearch/$(basename "$f")" \
        && echo "uploaded $(basename "$f")" || echo "WARN upload $f"
done

echo "=== self-terminate $(date -u) ==="
ZONE=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/zone | cut -d/ -f4)
INSTANCE=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/name)
gcloud compute instances delete "$INSTANCE" --zone="$ZONE" --quiet 2>/dev/null || shutdown -h now
