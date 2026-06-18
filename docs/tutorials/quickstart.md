<!-- Copyright (c) 2026 Xavier Callens / Socrate AI Lab, Paris, France -->
<!-- SPDX-License-Identifier: Apache-2.0 AND CC-BY-NC-ND-4.0 -->
<!-- Patent: US-PAT-PEND-2026-0525 -->

# Tutorial: Quick Start — SocrateAI Scientific Agora

> Get the Agora running in 5 minutes.

---

## Prerequisites

| Requirement | Minimum Version | Check Command |
|---|---|---|
| Python | 3.11+ | `python --version` |
| Rust | 1.85+ | `rustc --version` |
| Lean 4 | 4.8.0+ | `lean --version` |
| Docker | 24.0+ | `docker --version` |
| GCP CLI | 470+ | `gcloud --version` |

---

## Step 1: Clone the Repository

```bash
git clone https://github.com/socrate-ai-lab/SocrateAI-Scientific-Agora.git
cd SocrateAI-Scientific-Agora
```

---

## Step 2: Install Python Dependencies

```bash
# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install the Agora package with all extras
pip install -e ".[dev,benchmark,docs]"
```

This installs:
- `agora` — Core Python package (agents, budget, config)
- `lm-evaluation-harness` — Benchmark framework
- `statsmodels` — Statistical tests (Wilson CI, McNemar)
- `pyo3` — Rust-Python bindings for rusty-SUNDIALS

---

## Step 3: Build Rust Crates

```bash
# Build all Rust crates (solvers + RunuX stubs)
cargo build --release --workspace

# Run the test suite (134 solver tests)
cargo test --workspace
```

Expected output:
```
running 134 tests
...
test result: ok. 134 passed; 0 failed; 0 ignored
```

---

## Step 4: Build Lean 4 Proofs

```bash
cd verifiers/lean4
lake build
cd ../..
```

This compiles all 20 Lean 4 specifications and verifies the 13 proven theorems.

---

## Step 5: Configure the Agora

Copy the example configuration and set your budget:

```bash
cp agora.example.toml agora.toml
```

Edit `agora.toml`:

```toml
[agora]
version = "1.0.0"
budget_usd = 100.0    # Your experiment budget ceiling
max_cycles = 5

[symbrain]
version = "v5"
early_stop_ms = 500

# ... (see docs/SPECS.md §10 for full schema)
```

---

## Step 6: Run the Agora

### Option A: Quick Test (Local, No GPU)

```bash
# Run a simple test with the Socrates orchestrator
python -m agora.cli run \
    --query "Solve the ODE dy/dt = -2y, y(0) = 1" \
    --budget 1.00 \
    --local
```

Expected output:
```
🏛️ Socrates: Parsing query...
🔭 Galileo: Generating hypotheses (MCTS, depth=4)...
🔭 Galileo: Hypothesis 1: y(t) = e^{-2t} (confidence: 0.98)
🔭 Galileo: Running numerical simulation (CVODE BDF)...
🔭 Galileo: Simulation confirms y(5) ≈ 4.54e-5 (rtol=1e-8)
📐 Euler: Verifying y(t) = e^{-2t}...
📐 Euler: ✅ PROVEN in Lean 4 (0.3s)
🏛️ Socrates: CONSENSUS REACHED

Result:
  Solution: y(t) = e^{-2t}
  Confidence: 1.00 (formally proven)
  Cost: $0.02
  Budget remaining: $0.98
```

### Option B: Full Deployment (GCP Cloud Run)

```bash
# Authenticate with GCP
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Deploy all services (min_replicas=0)
cd deploy/terraform
terraform init
terraform apply

# Verify deployment
gcloud run services list --region=europe-west1
```

---

## Step 7: Verify Installation

Run the health check:

```bash
python -m agora.cli health

# Expected output:
# ✅ Python packages: OK
# ✅ Rust crates: OK (134/134 tests pass)
# ✅ Lean 4: OK (13/13 theorems verified)
# ✅ Configuration: OK (agora.toml valid)
# ✅ Budget guard: OK ($100.00 remaining)
# ⚠️ GCP: Not configured (--local mode only)
# ⚠️ NVIDIA NIM: Not configured (--local mode only)
```

---

## Next Steps

| Tutorial | Description | Time |
|---|---|---|
| [First Experiment](first_experiment.md) | Run a full scientific experiment with Galileo | 15 min |
| [Adding an Agent](adding_agent.md) | Create a custom agent for the Agora | 30 min |

## Reference Documentation

| Document | Description |
|---|---|
| [ARCHITECTURE.md](../ARCHITECTURE.md) | System architecture and topology |
| [SPECS.md](../SPECS.md) | Technical specifications |
| [BUDGET_POLICY.md](../BUDGET_POLICY.md) | Cost governance |
| [API: Agents](../api/agents.md) | Agent API reference |
| [API: Solvers](../api/solvers.md) | Solver API reference |
| [API: Verifiers](../api/verifiers.md) | Verifier API reference |

---

*Copyright © 2026 Xavier Callens / Socrate AI Lab, Paris, France.*
*Licensed under Apache 2.0 (framework) and CC-BY-NC-ND 4.0 (proprietary content).*
*Patent Pending: US-PAT-PEND-2026-0525*
