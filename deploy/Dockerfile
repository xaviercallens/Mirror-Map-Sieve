FROM python:3.12-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Install PyTorch with CUDA 12.4 support
RUN pip install --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cu124

# Install ML stack (separate to leverage cache)
RUN pip install --no-cache-dir \
    flask \
    "transformers>=4.48.0" \
    huggingface_hub \
    accelerate \
    safetensors \
    sentencepiece

COPY deepseek-prover-serve.py /app/serve.py

ENV MODEL_ID=deepseek-ai/DeepSeek-Prover-V2-7B
ENV MAX_TOKENS=1024
ENV PORT=8080
ENV PREWARM=false

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["python3", "serve.py"]
