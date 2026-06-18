# DeepSeek-Prover-V2-7B — T4 GPU + AWQ 4-bit Quantization
# Optimized for cost: ~$0.35/hr on T4, scale-to-zero when idle
FROM nvidia/cuda:12.4.0-runtime-ubuntu22.04

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-dev git curl \
    && rm -rf /var/lib/apt/lists/*

# Install vLLM + dependencies (T4-compatible build)
RUN pip3 install --no-cache-dir \
    vllm>=0.6.0 \
    flask \
    torch>=2.4.0 \
    transformers>=4.45.0 \
    huggingface_hub \
    autoawq \
    accelerate

# Pre-download model weights at build time to avoid cold-start download
# This makes the image larger (~8GB) but eliminates runtime latency
ARG MODEL_ID=deepseek-ai/DeepSeek-Prover-V2-7B
RUN python3 -c "from huggingface_hub import snapshot_download; snapshot_download('${MODEL_ID}', cache_dir='/app/models')"

# Copy serving code
COPY deepseek-prover-serve.py /app/serve.py

# Environment
ENV MODEL_ID=${MODEL_ID}
ENV QUANTIZE=awq
ENV GPU_MEMORY_UTILIZATION=0.90
ENV MAX_TOKENS=1024
ENV PORT=8080
ENV TRANSFORMERS_CACHE=/app/models
ENV HF_HOME=/app/models

EXPOSE 8080

# Health check for Cloud Run
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["python3", "serve.py"]
