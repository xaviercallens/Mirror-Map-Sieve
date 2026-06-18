# Ramsey Search — GCP GPU Deployment Guide

## Architecture

```
┌────────────────────────────────────────────────┐
│  GCP Cloud Run / Compute Engine                │
│                                                │
│  ┌──────────────┐  ┌──────────────┐            │
│  │  ramsey_sat  │  │ ramsey_gpu   │            │
│  │  (CaDiCaL)   │  │ (CuPy/CUDA) │            │
│  │  n=27..30    │  │ batch=10000  │            │
│  └──────┬───────┘  └──────┬───────┘            │
│         │                  │                    │
│  ┌──────┴──────────────────┴───────┐            │
│  │       Verification Layer        │            │
│  │  Full O(n³) violation recount   │            │
│  │  Ground-truth gate (Lesson #6)  │            │
│  └──────────────┬──────────────────┘            │
│                 │                               │
│  ┌──────────────┴──────────────────┐            │
│  │     Lean 4 Formalization        │            │
│  │  0 sorry, 0 axiom target       │            │
│  └─────────────────────────────────┘            │
└────────────────────────────────────────────────┘
```

## GCP Instance Configuration

### For SAT Search (CPU-intensive)
```yaml
# Compute Engine: c3-highcpu-44 (44 vCPUs, 88 GB RAM)
machine_type: c3-highcpu-44
zone: us-central1-a
boot_disk:
  image: ubuntu-2404-lts
  size_gb: 100
startup_script: |
  apt-get update && apt-get install -y build-essential cmake git
  # Install kissat (state-of-the-art SAT solver)
  git clone https://github.com/arminbiere/kissat
  cd kissat && ./configure && make -j$(nproc)
  # Install CaDiCaL
  git clone https://github.com/arminbiere/cadical
  cd cadical && ./configure && make -j$(nproc)
  # Install Python + pysat
  pip install python-sat numpy
```

### For GPU Parallel Search
```yaml
# Compute Engine: a2-highgpu-1g (1× A100 40GB)
machine_type: a2-highgpu-1g
zone: us-central1-a
accelerator:
  type: nvidia-tesla-a100
  count: 1
boot_disk:
  image: ubuntu-2404-lts
  size_gb: 200
startup_script: |
  # CUDA + CuPy
  apt-get update && apt-get install -y python3-pip
  pip install cupy-cuda12x numpy
```

### For Rust-Accelerated Search
```yaml
# Rust SAT solver compilation
startup_script: |
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
  source ~/.cargo/env
  # Install splr (Rust SAT solver)
  cargo install splr
  # Or build custom Ramsey solver
  git clone https://github.com/xaviercallens/SocrateAI-Scientific-Agora
  cd SocrateAI-Scientific-Agora/discovery/rust_ramsey
  cargo build --release
```

## Autoresearch Strategy

### Phase 1: Exhaustive SAT (CPU)
- Run CaDiCaL/kissat on n=27, 28, 29, 30
- Timeout: 1 hour per instance
- Expected: SAT for n≤29 (R(3,3,4) ≥ 30 is known)

### Phase 2: GPU Parallel BLS (GPU)
- 10,000 parallel instances on A100
- Paley/Cayley algebraic initialization
- Breakout perturbation when stuck
- Target: K_29 coloring (0 violations)

### Phase 3: Algebraic Construction (Mathematical)
- Replicate Piwakowski-Radziszowski construction
- Cayley graph over specific group G ⊂ Z_p × Z_q
- Cubic residue 3-coloring with symmetry breaking

### Phase 4: Neural Search (TPU)
- Train RL agent (Wagner 2021 style) to construct colorings
- State: partial coloring, Action: assign next edge color
- Reward: -violations
- Architecture: GNN on the graph structure
- TPU v4 for training, then deploy

## Cost Estimates

| Method | Instance | Time | Cost |
|--------|----------|------|------|
| SAT (n≤30) | c3-highcpu-44 | ~4h | ~$8 |
| GPU BLS | a2-highgpu-1g | ~2h | ~$12 |
| Rust SAT | c3-highcpu-44 | ~2h | ~$4 |
| Neural (TPU) | v4-8 | ~8h | ~$32 |

Total budget: ~$56 for comprehensive search.

## Dockerfile

```dockerfile
FROM nvidia/cuda:12.4-base-ubuntu24.04 AS gpu

RUN apt-get update && apt-get install -y python3-pip git
RUN pip install cupy-cuda12x numpy python-sat

COPY discovery/ /app/discovery/
WORKDIR /app

# Run GPU parallel search
CMD ["python3", "discovery/ramsey_gpu_search.py", \
     "--method", "both", "--n-start", "26", "--n-end", "30", \
     "--batch", "10000", "--steps", "10000000"]
```
