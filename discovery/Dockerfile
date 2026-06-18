# Discovery Pipeline — Cloud Run Deployment
# Socrate AI Lab — Combinatorial Identity Discovery Engine
#
# This container runs the mathematical discovery pipeline,
# which generates, tests, and verifies combinatorial identities
# using exact ℚ-arithmetic (no floating point errors).
#
# Design: Serverless execution on Cloud Run for scalable search.

FROM python:3.12-slim

# Metadata
LABEL maintainer="Xavier Callens / Socrate AI Lab"
LABEL description="Combinatorial Identity Discovery Pipeline"
LABEL version="0.1.0"

# Set working directory
WORKDIR /app

# Install system dependencies
# (none needed — pure Python with standard library)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy discovery pipeline code
COPY discovery/ /app/discovery/

# Copy any existing results for reference
COPY output/discovery/ /app/output/discovery/ 2>/dev/null || true

# Set Python path so imports work
ENV PYTHONPATH=/app
# Unbuffered output for real-time logging in Cloud Run
ENV PYTHONUNBUFFERED=1

# Cloud Run requires listening on PORT env var, but we're a batch job.
# Use a simple HTTP wrapper that triggers the pipeline on request.
COPY discovery/server.py /app/server.py

EXPOSE 8080

# Run the HTTP server that wraps the pipeline
CMD ["python", "server.py"]
