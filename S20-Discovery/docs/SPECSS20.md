# S₂₀ / S₁₅ GPU Benchmarks Specification (SPECSS20)

## 1. Goal
Validate and benchmark the `S20SpectralAttention` implementation against standard `F.scaled_dot_product_attention` using real GPU execution (T4/L4 for initial scale, A100/H100 for final).

## 2. Models
- **Initial:** `microsoft/phi-3-mini-4k-instruct` (3.8B) vs `meta-llama/Meta-Llama-3-8B`
- **Later:** Mistral, Qwen, Gemma

## 3. Patching Strategy
- **Phase 1 (Validation):** **Forward Hook (Option A)**. Intercept Q, K, V tensors after linear projection and apply the banded S20/S15 attention mask instead of the native attention.
- **Phase 2 (Industrialization):** **Layer Replacement (Option B)** for maximal performance optimization.

## 4. Hardware & Budget
- **Tier 1:** NVIDIA T4 / L4 (~$0.35 - $0.70/hr). Focus on small open-weights (Phi-3-mini).
- **Tier 2:** NVIDIA A100 / H100 (~$3.67 - $12.00/hr) for full industrialization.
- **Budget:** ~$65-115 total.

## 5. Phased Approach
1. **Bug Fixes:** Fix API mismatches and placeholder monkey-patching.
2. **Microbenchmarks:** Latency sweeps on GCP GPUs.
3. **Correctness:** Numerical validation of gradients and attention properties.
4. **End-to-End:** MMLU accuracy and TPOT energy measurements.
5. **Scale Up:** Industrial run on H100 with larger models.
