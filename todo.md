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
- [open] Fold Phase 1/2 results into the v6 paper (proofs + honest caveats).
- [open] Submit the OEIS draft (A397213 is a **pending** proposed id, not yet
  accepted) once an editor reviews it.
- [parked] **AI-hardware INT64 attention** (`4_ai_hardware_attention/`):
  exploratory only. Re-labelled as heuristic; benchmarks need an independent GPU
  run. Not a research priority and unrelated to the mathematical contribution —
  parked unless someone wants to benchmark it rigorously.
