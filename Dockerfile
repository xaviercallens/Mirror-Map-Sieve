# Mirror Map Sieve - Full Environment
# Includes Python 3.11+, SageMath, and Lean 4

FROM sagemath/sagemath:10.2

USER root

# Install dependencies for Python and Lean 4
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Create user
RUN useradd -m -s /bin/bash socrate
USER socrate
WORKDIR /home/socrate/app

# Install Elan (Lean version manager)
RUN curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh -s -- -y --default-toolchain leanprover/lean4:v4.31.0
ENV PATH="/home/socrate/.elan/bin:${PATH}"

# Copy application
COPY --chown=socrate:socrate . .

# Setup Python virtual environment
RUN python3 -m venv /home/socrate/venv
ENV PATH="/home/socrate/venv/bin:$PATH"

# Install requirements
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

CMD ["/bin/bash"]
