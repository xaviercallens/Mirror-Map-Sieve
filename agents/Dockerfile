FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Lean 4 via elan (optional, for formal proofs if run locally)
RUN curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh -s -- -y
ENV PATH="/root/.elan/bin:${PATH}"

# Setup working directory
WORKDIR /app

# Copy requirements if any (assume google-antigravity is needed)
RUN pip install --no-cache-dir google-antigravity pydantic requests asyncio

# Copy the agent codebase
COPY agents /app/agents
COPY SocrateAI-Scientific-AlienMathematics-Foundation /app/SocrateAI-Scientific-AlienMathematics-Foundation

# Run the agent
CMD ["python", "agents/degennes_agent.py"]
