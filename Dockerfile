# Use a base image with Python
FROM ubuntu:22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Install Lean 4
RUN curl -sSf https://leanprover.github.io/lean4_install.sh | sh
ENV PATH="/root/.elan/bin:${PATH}"

# Copy the repository
COPY . /app
WORKDIR /app

# Set up Lean project
RUN cd /app/src/lean_proofs && lake build

# Default command: Run the algebraic shielding solver
CMD ["python3", "/app/src/algebraic_shielding/guess_s20_recurrence_int.py"]
