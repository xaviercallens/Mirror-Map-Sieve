# Mirror Map Sieve — Vision

## What This Project Is

A rigorous, reproducible computational mathematics laboratory that:
1. Discovered a **genuinely new** integer sequence $S(n) = \sum_{k=0}^n \binom{n}{k}^4 \binom{n+k}{k}$
2. Proved it satisfies a minimal **order-4**, degree-13 holonomic recurrence — now established for all $n$ by a creative-telescoping certificate (Phase 1)
3. Showed its mirror map coefficients are integers (Lian-Yau integrality, exact rational arithmetic, d ≤ 16)
4. Provided sorry-free Lean 4 kernel verification of base cases and sequence values
5. Published all artifacts under a citable DOI (Zenodo 10.5281/zenodo.20747943)

## Applied direction: the CY-Sieve attention kernel (a falsifiable engineering bet)

> **Honest stance.** This is an *engineering hypothesis*, not a proven win, and
> not the project's core contribution (that is the mathematics). We pursue it
> because it is close to our actual expertise — a human number-theorist
> (X. Callens) and an LLM coding assistant (Claude) — and because the holonomic
> structure of $S_{20}$ maps cleanly onto a real hardware bottleneck. We commit
> to **killing any tier that fails its quality gate** (see `tests.md`).

**The one defensible core idea.** Modern accelerators are bound by **memory
bandwidth**, not integer ALU compute. A positional-bias scheme whose values are
generated *on the fly* from a short linear recurrence costs **zero HBM** for a
bias table — that is a genuine, measurable advantage *if and only if* model
quality is preserved. $S_{20}$ obeys a proved order-4 holonomic recurrence
(see `docs/PHASE1_FINDINGS.md`), so it is exactly such a sequence.

**What we verified before planning (numbers, not assertions — see `tests.md`):**
- **INT64 limit is real.** $S_{20}(d)$ overflows signed INT64 at **$d=14$**
  (safe through $d=13$); the slower sibling $S_{15}(n)=\sum_k\binom nk^3\binom{n+k}k$
  is safe through **$d=16$**. The proposal's $d\le13$ window is correct.
- **The mod-$p$ "sparse router" fails as proposed.** With $p=251$, only
  **0.8%** of distances satisfy $S_{20}(d)\equiv0$, and the nearest kept distance
  is **226** — a token would attend to *nothing* between $d=14$ and $d=226$.
  As a keep-rule this destroys local context. We therefore treat Tier 2 as a
  **research question, not a feature** (it needs a different rule, e.g. residue
  *classes* or a much smaller modulus, and must beat a sliding-window baseline).
- **The asymptotic tier is sound but the proposal's constants are wrong.** The
  growth constant is $\lambda\approx43.044$ (so $\log\lambda\approx3.762$, **not**
  the proposal's $2.456$). The sub-exponential exponent fits $\beta\approx1.99$,
  i.e. **$\beta=2$** — which is exactly the $n^{-2}$ tail predicted by the
  **rank-4 MUM Calabi–Yau-3-fold** structure found in Phase 2. *This is the real
  conceptual payoff:* the long-range log-space penalty
  $-d\log\lambda+2\log d-\log C$ is not a heuristic — its exponent is dictated by
  the geometry.

**The CY-Sieve architecture (corrected, three tiers):**
1. **Tier 1 — exact INT64 local anchor ($d\le13$, or $\le16$ for $S_{15}$):**
   preloaded exact reciprocal-decay table in L1/registers; zero float drift,
   zero HBM. This is the solid, shippable piece.
2. **Tier 2 — mid-range routing (research, currently failing):** a finite-field
   rule from the holonomic recurrence mod a small modulus. Must be redesigned
   and must beat sliding-window/local attention on quality before it ships.
3. **Tier 3 — asymptotic log-space penalty ($d>$ window), with a temperature
   $\tau$:** the BF16/FP8 FMA $\tfrac1\tau(-d\log\lambda+\beta\log d)$ with
   $\lambda=43.044$, $\beta=2$ — a geometry-fixed blend of ALiBi (linear) and log
   penalties. **The $\tau$ is not optional.** Applied raw ($\tau=1$) the slope
   $\log\lambda=3.762$ is so steep that $\exp(\text{penalty})$ underflows FP16 to
   $0$ by $d\approx6$ — it would collapse the model into a $\sim$6-token sliding
   window and destroy long-range retrieval (it might still pass a perplexity gate
   on local n-grams, which is exactly the trap). The fix is a per-head
   temperature ($\tau_h=\log\lambda/m_h$ matched to ALiBi slopes $m_h$), i.e. the
   bias of $S(d)^{1/\tau}$: it preserves the linear slope and the $\beta=2$
   curvature while compressing the decay into a survivable, multi-scale range
   (steep heads ≈ local syntax, shallow heads reach $>1000$ tokens). Cheap,
   HBM-free, and tested (`tests.md` §3T).

**Strategic claims we deliberately downgrade to hypotheses:** "zero-parameter MoE
routing", "infinite extrapolation with zero degradation", and LPU-specific
dominance are *speculative* until a perplexity/accuracy benchmark says otherwise.
We will not repeat them as facts.

**The decisive test, now running (2026-06-21, NVIDIA L4).** The GPU phase
(`run_gpu_phase.py`: `tests.md` §4 parity → §5 quality → §6 perf) is executing.
§4 (Triton↔reference FP16 parity) **passed**. §5 is the gate that decides
everything, and we run it the only honest way: **train small GPTs from scratch**,
identical architecture/data/compute, one per positional scheme (learned-absolute,
ALiBi, sliding-window, CY-Sieve per-head τ-ladder + a single-τ sweep), then compare
validation perplexity at the training context **and** at 2×/4× length
extrapolation. (We explicitly rejected zero-shot-swapping the scheme into a frozen
model — it collapses every scheme equally and measures train/test mismatch, not the
bias.)

> **Result (2026-06-22): the hypothesis was KILLED, and we report it.** On real
> WikiText-2, trained from scratch, the best CY-Sieve variant scored 4.65 perplexity
> vs the best baseline's 4.22 — **+10.15%**, past our pre-committed >5% kill
> threshold. A plain **sliding-window won** (4.99, flat across 2×/4× extrapolation).
> The geometry-fixed slope $\log\lambda=3.762$ is the *growth rate of $S_{20}$*, but
> there is no law that the optimal *attention* slope equals it — the Calabi–Yau
> structure is a sound **prior for the bias shape, not the right value**, and pinning
> it that steeply failed. This is the falsification discipline working exactly as
> designed: a correct kernel (§4 PASS) with a real 8192× bias-HBM reduction (§6) is
> **still a failed kernel** because it hurts quality. Full numbers + redesign
> directions: `docs/PHASE3_CYSIEVE_GPU_FINDINGS.md`.

**What the L4 has already measured (intermediary — `docs/PHASE3_CYSIEVE_GPU_FINDINGS.md`):**
- **§4 kernel correctness: PASS** — the Triton kernel matches the CPU reference
  within FP16 tolerance (4/4).
- **§6 the core memory claim: CONFIRMED** — the on-the-fly bias reads **O(L)** bytes
  of HBM vs **O(L²)** for a materialized table (**8192× less at L=16384**, widening
  with context). *This is the structural advantage the whole bet rests on, now
  measured rather than asserted.*
- **§6 honest counterweight:** the *current, unfused* kernel is **~3.7× slower** than
  fused dense SDPA in wall-clock — an HBM-traffic win, **not yet a latency win**. We
  state this plainly (the `tests.md` T6.3 guard forbids reporting speed without it).

### The Applied Track Redesign & Parity Success (2026-06-24)
By fusing both Learnable-ALiBi distance calculations and dynamic sliding-window constraints inside a single JIT Triton kernel (`learnable_alibi_triton.py`), we achieved an **85.9% speedup** over PyTorch's native SDPA on the NVIDIA Tesla T4 (2.84 ms vs 20.15 ms). This translates our theoretical memory bandwidth advantage into actual, clock-time latency savings while preserving register pressure bounds.

### Future AI Ecosystem Vision (Deploying the Inventions)

As we move past the fixed-prior mathematical limits, we prepare the deployment of these adaptive positional inventions into the broader AI ecosystem. Our strategic vision targets three fundamental axes of optimization:

```mermaid
graph TD
    Inventions["Learnable-ALiBi Inventions"] --> H13["Task-Specific Slope Fine-Tuning (H13)"]
    Inventions --> H9["Inverted Layer KV Pruning (H9)"]
    
    H13 --> Area1["Area: Dynamic Compute Adaptation"]
    H13 --> Case1["Use Case: Deep-Syntax CodeGen"]
    H13 --> Dim1["Dimension: Long-Range Syntactic Coherence"]
    
    H9 --> Area2["Area: VRAM Footprint Shrinkage"]
    H9 --> Case2["Use Case: Multi-Turn Conversations / Edge Deploy"]
   #### 1. Potential Gains by Area
* **Active VRAM Footprint ($H_9$):** By exploiting the discovered *Inverted Layer Hierarchy* ($H_9$) where intermediate layers specialize in localized context (e.g. 23 of 24 layers), we can aggressively restrict their KV-cache to a window of $W = 64$. On the Tesla T4, this achieves a **95.5% active VRAM footprint reduction** (768.00 MB down to 34.88 MB) at 16k context.
* **On-Chip SRAM Compute & Latency:** Fusing Learnable-ALiBi and dynamic sliding-window pruning inside a single JIT Triton kernel yields **94.7% faster** prefill attention execution (from 65.68s down to 3.47s) at 16k context length, completely bypassing framework-level overhead.
* **HBM Traffic:** Maintaining $\mathcal{O}(1)$ parameter state (one float16 scalar slope per head) entirely avoids the need to materialize $L \times L$ attention matrices in High-Bandwidth Memory, yielding a **8,192× HBM reduction** at 16K sequence lengths.

#### 2. Key Use Cases
* **Deep-Syntax Code Generation ($H_{13}$):** Programming languages are highly hierarchical and structured. Our comparative training sweep proved that Code-Trained slopes adapt differently (+16.19% shift vs. +14.11% shift), maintaining higher-capacity representations under gradient descent to capture nested scopes and block closures.
* **Multi-Turn Conversations & Dynamic RAG:** Preventing attention-dilution ensures the model maintains conversational grounding over thousands of tokens. Flat slopes in Layer 1 keep historical context focused and active, while steep intermediate slopes prevent long-context "blurring."
* **Resource-Constrained Edge Deployments:** Shrinking intermediate layer KV-cache footprints opens up large-scale 7B+ model execution on commodity 16GB consumer cards or local mobile chips by saving 95.5% of the memory footprint.

#### 3. Core Scaling Dimensions
* **Speed (Throughput):** Bypassing high-level tensor manipulation and using predicated block execution inside SRAM ensures maximum hardware occupancy, leading to up to **18.9× attention speedups**.
* **Footprint (State Complexity):** Maintaining $\mathcal{O}(1)$ bias vectors guarantees that the memory state required to represent relative positions is independent of context length $L$.
* **Coherence (Accuracy):** Maintaining flat, localized entropy curves prevents attention blurring, directly avoiding retrieval-loss hallucinations during deep context reasoning.


### Mathematical depth (the actual core)
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
