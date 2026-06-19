# Mirror Map Sieve — TODO

## Immediate Focus: Holonomic INT64 Attention (CS & AI Hardware Pivot)

### 1. OpenAI Triton Kernel Implementation (`s20_attention.py`)
- [ ] Set up Triton development environment and test standard FlashAttention implementation.
- [ ] Implement the SRAM-based exact INT64 recurrence generator for $S_{20}$.
- [ ] Create the inverse mapping $Mask(d) \propto 1 / S_{20}(d)$ directly in SRAM, bypassing HBM loads.
- [ ] Implement super-exponential sparsity: apply strict algorithmic cutoff for tokens where $d \ge 3$.
- [ ] Bypass the SoftMax denominator normalization layer using the Markovian local routing layer.

### 2. Benchmarking & Verification
- [ ] Benchmark memory throughput (GB/s) against standard FlashAttention.
- [ ] Benchmark FLOPs and latency savings from the $d \ge 3$ cutoff.
- [ ] Verify zero floating-point drift over context lengths up to 1M+ tokens.
- [ ] Compare VRAM usage with baseline models using RoPE/ALiBi.

### 3. Publication
- [ ] Outline paper: "Holonomic INT64 Attention: Bypassing SoftMax with Exact Calabi-Yau Geometries".
- [ ] Draft abstract and introduction focusing on the "precision wall" and floating-point drift.
- [ ] Generate benchmarking visualizations showing exact INT64 stability vs floating-point degradation.
- [ ] Prepare NeurIPS 2026 submission package.

## Secondary Focus: Mathematical Open Problems

### Supercongruences
- [ ] Prove Lucas Congruence: $S(mp+r) \equiv S(m)S(r) \pmod p$
- [ ] Prove Apéry-style Congruence: $S(p-1) \equiv 1 \pmod{p^3}$
- [ ] Resolve Cubic Congruence: $S(p) \equiv 3 \pmod{p^3}$ (Requires deep number theory / CY 4-fold formal group law)

### Diagonal Representation
- [ ] Discover $F(x_1,...,x_5)$ such that $Diag(F) = S(n)$. This is a major open research problem.
