# Mirror Map Sieve — TODO

Status tags: **[done]**, **[open]**, **[blocked]**, **[parked]**. The mathematics
research program (see `docs/RESEARCH_PLAN.md`) is the primary focus.

## Primary focus: the Picard–Fuchs / Calabi–Yau research program

### Phase 1 — certified minimal recurrence
- [done] Determine minimal recurrence order: **4, degree 13** (four independent
  derivations; orders 2–3 impossible).
- [done] Reconstruct the exact operator over $\mathbb{Q}$; verify on 101 terms.
- [done] Creative-telescoping **certificate** (Maxima Zeilberger, GCP/SageMath) —
  proves the recurrence **for all $n$**.
- [open] **Lean 4 re-check** of the certificate's finite rational identity
  (clear denominators → `ring`/`linear_combination`). Gold-standard closure.

### Phase 2 — Calabi–Yau period identification
- [done] Minimal **ODE** order of $f(z)$: **6, degree 15** (exact nullspace).
- [done] Indicial equation at $z=0$: $-715\,s^4(s-1)^2$ → **MUM block of order 4**
  + order-2 apparent singularity ⇒ Calabi–Yau **3-fold** evidence.
- [done] Mirror-map integrality $q_d\in\mathbb{Z}$ for $d\le16$ (exact).
- [blocked] Explicit factorization $L_6=L_4\cdot L_2$ with $L_4$ irreducible —
  needs a version-matched Sage + `ore_algebra` (the `.factor()` path is broken on
  `:latest`, won't compile on 10.4). Pin a maintainer-blessed pair.
- [open] **Correct CY-3 Yukawa coupling** $K_{zzz}$ from $L_4$ → genuine
  **instanton-number integrality** test (the placeholder normalization gave
  non-integers with $\sim d^3$ denominators — unresolved, not a refutation).
- [open] Match $L_4$ against the **AESZ / van Straten** CY-operator databases
  (operator-level, up to pullback/Möbius/scaling) — settles novelty + identifies
  the 3-fold. (Textual prescreen of `asz_sequences.json` found no exact match.)

### Phase 3 — modularity (gated on $L_4$)
- [blocked] Locate rigid / conifold fibers (roots of $L_4$'s leading coefficient).
- [open] Compute Frobenius traces $a_p$; search LMFDB $S_4(\Gamma_0(N))$ for a
  matching **weight-4 newform**.
- [open] Formulate + test a Beukers/ASD-type supercongruence relating $S$ to the
  newform (the genuinely deep analog of the elementary $S(p)\equiv3$).

## Secondary: arithmetic of $S(n)$ (supercongruences)
- [done] Cubic supercongruence $S(p)\equiv 3 \pmod{p^3}$, $p\ge5$ — **proved,
  Lean-verified** (elementary; collapse + Wolstenholme).
- [done] Apéry-style $S(p-1)\equiv 1 \pmod{p}$ — **proved, Lean-verified**.
- [open] **Conjecture:** $S(p-1)\equiv 1 \pmod{p^3}$, $p\ge5$ (numeric to
  $p=200$; no proof). Likely needs a higher-order harmonic-sum analysis.
- [open] **Conjecture:** Lucas property $S(mp+r)\equiv S(m)S(r)\pmod p$ (numeric).

## Publication & housekeeping
- [done] Fold Phase 1/2 results into the v6 paper (Section "The Picard–Fuchs
  operator…", with proofs + honest caveats). Refresh the release PDF asset next.
- [open] Submit the OEIS draft (A397213 is a **pending** proposed id, not yet
  accepted) once an editor reviews it.
## Applied track: CY-Sieve attention kernel (experimental, falsifiable)

Real implementation of the holonomic structure as an HBM-free positional bias.
Engineering hypothesis — each tier killed if it fails its `tests.md` quality gate.
Architecture + verified numbers in `vision.md`; staged plan in `roadmap.md`.

- [done] Verify INT64 crossover (S20→d13, S15→d16), asymptotic λ=43.044 / β≈2,
  and that the mod-p keep-rule fails (0.78% kept, nearest 226).
- [done] **Stage A** `cy_sieve_reference.py` (CPU): Tier-1 exact table, Tier-2
  recurrence-mod-p generator, Tier-3 log-space penalty + per-head τ ladder.
- [done] **Stage A** unit tests `tests.md` §1–§3 + §3T (35 tests; caught the
  2^32 underflow bug and the native-τ FP16 collapse).
- [done] **Stage B (CPU half)** `cy_sieve_attention.py`: dense SDPA + FlashAttention
  online-softmax variant with the bias; reference-vs-reference parity ~3e-16, plus
  a CPU needle-retrieval proxy (`tests.md` §4 + §5-proxy, 13 tests). All in CI.
- [done] **Stage B scaffold** `cy_sieve_triton.py` (GPU-guarded Triton kernel:
  online softmax + bias), `requirements-gpu.txt`, `GPU_SETUP.md`, and
  `test_cy_sieve_triton.py` (parity vs CPU oracle; auto-skips without CUDA).
- [open] **Stage B (GPU run)** on a CUDA box: run the Triton kernel + the
  Triton↔NumPy FP16/BF16 parity test (`tests.md` §4 T4.1). **Needs GPU.**
- [done] **CPU obstacle work** robust recurrence-mod-p generator (the SRAM
  "generate on-the-fly" path); found+documented P₄(n)≡0 reseed points (~p/80).
- [open] **Stage C (the gate)** perplexity + NIAH vs RoPE/ALiBi/sliding-window at
  matched compute, sweeping τ; GPU throughput/HBM-traffic (`tests.md` §5–§6).
  **Kill if quality regresses >5%. Needs GPU + a model.**
- [open] **Stage D (speculative, only if C passes)** redesign Tier-2 router;
  test MoE routing via S15(d) mod E; measure 4K→long-context extrapolation.
- [parked] Legacy `4_ai_hardware_attention/` prototype kernels — superseded by
  CY-Sieve Stage A/B; keep for regression reference only.
