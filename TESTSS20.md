# S₂₀ / S₁₅ Test Plan (TESTSS20)

## Unit Tests
1. **Sequence Tests:** Verify exact values of $S_{15}$ and $S_{20}$.
2. **Attention Unit Tests:**
   - Output shape preservation.
   - Attention weights non-negativity and row-sum-to-one (L1 norm).
   - Banded structure enforced (zeros outside window).
   - Causal mask enforced.
   - Gradients flow properly without NaNs.
3. **Patching Tests:**
   - Model produces different logits when S20 patched vs unpatched.
   - Forward hook attaches correctly to nested attention layers.
4. **Numerical Tests:**
   - Jacobian correctness vs autograd.
   - fp16 and bf16 stability.

## GPU Benchmarks
1. **Latency & Memory Sweep:**
   - Dimensions: seq_len ∈ {512..8192}, window_size ∈ {4..64}.
   - Validating non-OOM up to 8192 context.
2. **MMLU Accuracy:**
   - Verify accuracy delta between baseline and S20-patched Phi-3-mini.
3. **TPOT & Energy:**
   - Time per output token and Joules/token measured via `nvidia-smi` daemon.
