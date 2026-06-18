FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    flask \
    torch --index-url https://download.pytorch.org/whl/cpu \
    transformers \
    huggingface_hub \
    accelerate

COPY deepseek-prover-serve.py /app/serve.py

ENV MODEL_ID=deepseek-ai/DeepSeek-Prover-V2-7B
ENV QUANTIZE=awq
ENV GPU_MEMORY_UTILIZATION=0.90
ENV MAX_TOKENS=1024
ENV PORT=8080

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["python3", "serve.py"]
