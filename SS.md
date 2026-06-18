# SocrateSkills (SS.md)

This file tracks reusable skills and patterns developed during the S₂₀ / S₁₅ project.

## 1. Falsification-First Benchmarking
**Pattern:** Never trust simulated or hardcoded results. Always build an end-to-end measurement pipeline on real hardware before analyzing metrics.
**Implementation:** `s15_kernel/benchmarks/benchmark_tpot.py` uses a daemon thread polling `nvidia-smi` rather than relying on theoretical FLOP counts.

## 2. Safe Monkey-Patching via Hooks
**Pattern:** For rapid prototyping of custom attention mechanisms in HuggingFace models, prefer `register_forward_hook` over layer replacement to avoid breaking model-specific structural assumptions (e.g., KV cache formats, rotary embeddings).
**Implementation:** `s15_kernel/patching.py` intercepts `(Q, K, V)` tuples post-projection.

## 3. Math Kernel Stability
**Pattern:** Custom attention mechanisms lacking softmax require explicit L1 or L2 normalization, or gradients will explode.
**Implementation:** `S20SpectralAttention` uses $L2$ normalization on Q and K, followed by $L1$ row normalization after applying the banded decay mask.
