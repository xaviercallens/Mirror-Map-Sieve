#!/bin/bash
# GCP L4 startup — first REAL-signal run of learnable-ALiBi on an open-weight model:
# unfreeze BLOOM-560m's per-head ALiBi slopes + short continued-pretrain, measure
# serve-long extrapolation vs the frozen released model. See
# docs/BENCHMARK_SPEC_OPENWEIGHT.md + openweight_learnable_alibi.py.
set -uo pipefail
RESULTS_BUCKET="gs://gen-lang-client-0625573011-cy-sieve-bench"
WORKDIR="/tmp/Mirror-Map-Sieve/4_ai_hardware_attention"
STAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="/tmp/openweight_${STAMP}.log"
exec > >(tee -a "$LOG_FILE") 2>&1
echo "=== openweight learnable-ALiBi GPU run — startup $(date -u) ==="
nvidia-smi || echo "WARN no nvidia-smi"
# transformers/peft for the model; datasets stack for the real WikiText corpus.
# Pin transformers <5 (5.x eagerly probes torchaudio, whose prebuilt .so is ABI-
# mismatched on this image and throws OSError at import — crashed the first run).
pip3 install --quiet "transformers>=4.40,<5" "datasets>=2.19" xxhash multiprocess pandas \
    "requests>=2.32.2" huggingface_hub fsspec pyarrow accelerate safetensors 2>&1 | tail -3 || true
# We need neither audio nor vision; remove the broken torchaudio so transformers
# treats it as cleanly-absent rather than failing to dlopen it.
pip3 uninstall -y torchaudio torchvision 2>/dev/null || true
python3 -c "import torch,transformers,datasets;print('torch',torch.__version__,'tf',transformers.__version__,'cuda',torch.cuda.is_available())" || true
cd /tmp; rm -rf Mirror-Map-Sieve
git clone --depth 1 https://github.com/xaviercallens/Mirror-Map-Sieve.git
cd "$WORKDIR"
echo "=== run openweight (full preset, bloom-560m) $(date -u) ==="
python3 openweight_learnable_alibi.py --preset full --model bigscience/bloom-560m \
    --modes frozen_fixed learnable_slopes \
    --output "/tmp/openweight_full_${STAMP}.json" 2>&1
echo "rc=$? at $(date -u)"
for f in "/tmp/openweight_full_${STAMP}.json" "$LOG_FILE"; do
    [ -f "$f" ] && gsutil cp "$f" "${RESULTS_BUCKET}/openweight/$(basename "$f")" \
        && echo "uploaded $(basename "$f")" || echo "WARN upload $f"
done
echo "=== self-terminate $(date -u) ==="
ZONE=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/zone | cut -d/ -f4)
INSTANCE=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/name)
gcloud compute instances delete "$INSTANCE" --zone="$ZONE" --quiet 2>/dev/null || shutdown -h now
