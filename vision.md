# Mirror Map Sieve — Vision

## What This Project Is

A rigorous, reproducible computational mathematics laboratory that:
1. Discovered a **genuinely new** integer sequence $S(n) = \sum_{k=0}^n \binom{n}{k}^4 \binom{n+k}{k}$
2. Proved it satisfies an order-5, degree-9 holonomic recurrence (via exact integer nullspace computation)
3. Showed its mirror map coefficients are integers (Lian-Yau integrality, exact rational arithmetic, d ≤ 16)
4. Provided sorry-free Lean 4 kernel verification of base cases and sequence values
5. Published all artifacts under a citable DOI (Zenodo 10.5281/zenodo.20747943)

## What This Project Should Become

### Phase 2: Computer Science & AI Hardware (The Deep Tech Pivot)
**The Goal:** Revolutionize LLM context efficiency by replacing floating-point heuristic attention with exact topological geometry.
The AI industry is currently hitting a "precision wall" where Softmax and relative positional encodings (RoPE, ALiBi) rely heavily on floating-point arithmetic and transcendental exponentials, causing drift and memory bottlenecks.

We propose a new paradigm: **Holonomic INT64 Attention**.
1. **The Callens-Schmidt Positional Decay Kernel**: Replace continuous float decay with exact inverse Calabi-Yau 3-fold period: $Mask(d) \propto 1 / S_{20}(d)$.
2. **The Hardware GPU Hack**: Compute decay weights dynamically in ultra-fast SRAM using pure INT64 arithmetic (via the exact order-4 linear integer recurrence).
3. **Super-Exponential Sparsity**: Enforce extreme local sparsity (growth $G \approx 43.04$) to create a "Markovian" routing layer, bypassing the need for SoftMax denominator normalization and saving massive VRAM and FLOPs.

### Phase 3: Mathematical Depth
- **Prove the supercongruences** — these are the highest-impact open problems in this project
- **Submit to OEIS** — the sequence needs an A-number to become a permanent part of mathematics
- **Find the diagonal representation** — this is the deepest open problem (Christol guarantees existence; finding it is research)

### Phase 4: Community Recognition
- **arXiv submission** with proper cross-listings (math.AG, math.NT, cs.SC)
- **Submit to NeurIPS 2026** — "Holonomic INT64 Attention: Bypassing SoftMax with Exact Calabi-Yau Geometries"
- **Submit to a journal** — Experimental Mathematics or Journal of Number Theory are the natural targets

### What This Project Should NOT Be
- ❌ A branding exercise (self-eponymy undermines scientific credibility)
- ❌ A claim of formal proof for something only computationally verified at finite points

## Guiding Principles
1. **Understate rather than overstate.** Let the mathematics speak for itself.
2. **Reproducibility is non-negotiable.** Every claim must be verifiable by running code.
3. **Separate speculation from proof.** Conjectures are clearly labeled. Verified results are clearly stated.
4. **Standard mathematical practice.** OEIS submission, arXiv, peer-reviewed journal. No shortcuts.
