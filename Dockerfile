FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency resolution
RUN pip install uv

# Copy requirements and dependencies
COPY requirements.txt .

# We need to explicitly install Google Antigravity, Mistral dependencies, and torch if they aren't in requirements.txt
# Since torch is massive, we use cpu version for the Cloud Run Job to keep image size small
RUN uv pip install --system -r requirements.txt \
    "torch" "torch-geometric" "networkx" "python-dotenv" "requests" "google-genai"

# Copy the application code
COPY . .

# Set PYTHONPATH
ENV PYTHONPATH=/app

# Default command
CMD ["python3", "scripts/generate_callens_conjectures.py"]
