# Agent Memory Bank — SocrateAI Scientific Agora

> **Last updated:** 2026-06-14  
> **Status:** Active

---

## Known Bounds

### Ramsey Numbers

| Quantity | Bound | Source | Status |
|----------|-------|--------|--------|
| R(3,3) | = 6 | Classical (Greenwood–Gleason 1955) | ✅ Verified (Lean 4) |
| R(3,3,4) | = 30 (exact) | Codish, Frank, Itzhakov, Miller 2016; Radziszowski DS1 | ✅ RESOLVED |
| R(5,5) | ∈ [43, 46] | Angeltveit & McKay 2024 (≤46); Exoo 1989 (≥43) | 🔬 Open |

> [!CAUTION]
> **R(3,3,4) = 30 is EXACT — SETTLED SINCE 2016.**
> Codish et al. proved this via SAT with abstraction + symmetry breaking.
> Earlier values in this codebase ([51,62], [30,31]) were ALL incorrect.
> Our SAT search for n=30 WILL be UNSAT — this is not a bug, it's mathematics.

> [!IMPORTANT]
> **New pivot targets (AlphaEvolve, Google DeepMind, March 2026):**
> These Ramsey lower bounds were recently improved and more may be possible:
> | R(s,t) | Old LB | New LB (AlphaEvolve) |
> |--------|--------|----------------------|
> | R(3,13) | 60 | 61 |
> | R(3,18) | 99 | 100 |
> | R(4,13) | 138 | 139 |
> | R(4,14) | 147 | 148 |
> | R(4,16) | 170 | 174 |
> | R(4,18) | 205 | 209 |
> | R(4,19) | 213 | 219 |
> | R(4,20) | 234 | 237 |

### Matrix Multiplication

| Quantity | Value | Source | Status |
|----------|-------|--------|--------|
| Strassen ω exponent rank | R = 49 | Direct computation | ✅ Verified (NumPy) |

---

## Verified Results

### Formal Verification (Lean 4)

| Result | Method | sorry | axiom | Status |
|--------|--------|-------|-------|--------|
| R(3,3) ≥ 6 | Lean 4 proof | 0 | 0 | ✅ Verified |
| ExactRationalWitness | Lean 4 proof | 0 | 0 | ✅ Publishable (ITP/CPP) |
| 49 combinatorial identity instances | `native_decide` | 0 | 0 | ✅ Verified |
| ChargingAlgebra | Lean 4 proof | 0 | 0 | ⚠️ Correct but trivial (definitional tautologies) |

### Computational Verification

| Result | Method | Status |
|--------|--------|--------|
| R(3,3,4) ≥ 26 | Simulated annealing | ✅ Verified |
| Strassen R = 49 | NumPy computation | ✅ Verified |

---

## Key References

| Reference | Venue | Relevance |
|-----------|-------|-----------|
| **Mattheus & Verstraëte (2024)** | *Annals of Mathematics* | Solved r(4, t) via pseudorandom graphs from finite geometry — breakthrough algebraic construction method |
| **Radziszowski DS1 rev 18** | Dynamic survey | Authoritative source for small Ramsey number bounds |
| **Bläser (2003)** | — | Strassen-like algorithm bounds — should have been checked before computation |

---

## Discovery Pipeline Status

| Metric | Value |
|--------|-------|
| Total hypotheses evaluated | 18 |
| Verified | 12 |
| Potentially new | 2 |
| Combinatorial identities verified | 49 (via `native_decide`) |

### Module Assessment

| Module | Verdict |
|--------|---------|
| **ExactRationalWitness** | ✅ 0 sorry, 0 axiom — publishable quality (target: ITP/CPP) |
| **ChargingAlgebra** | ⚠️ Formally correct but unexciting — definitional tautologies, not novel |
| **8 "verified" modules** | ⚠️ Mostly trivial — definitional tautologies that inflate metrics |

---

## Infrastructure

### Available Tools

| Script | Purpose | Status |
|--------|---------|--------|
| `ramsey_algebraic.py` | Algebraic construction search | 🔧 Ready, not fully run |
| `ramsey_sat.py` | SAT-based Ramsey bounds | 🔧 Ready, not fully run |
| `ramsey_bls.py` | Bounded local search | 🔧 Ready, not fully run |

### Known Limitations

- **Simulated annealing** hits a hard wall at n ≈ 26–28 for R(3,3,4) lower bounds
- **Tabu search** had 2 bugs producing false positives (now fixed)
- **LLM-generated claims** are ~85% hallucination — always verify independently

---

## Action Items

- [ ] **Resolve bound inconsistency:** Audit all files referencing R(3,3,4) bounds and correct any that cite [51, 62] to [30, 31]
- [ ] **Run algebraic construction pipeline:** `ramsey_algebraic.py` has not been fully exercised
- [ ] **Run SAT solver pipeline:** `ramsey_sat.py` may push beyond the SA wall at n = 26–28
- [ ] **Prepare ExactRationalWitness for submission:** Target ITP or CPP venue
- [ ] **Evaluate 2 "potentially new" results:** Determine if they survive full literature check

---

## Weekend Session Memory (2026-06-14 — 2026-06-15)

### New Agents Created
- **Tesla** (PROTOTYPER role): Director of Prototyping and Applied Engineering. Specification-driven, test-driven prototype builder.

### New Pipelines Created
- **Prototyping Pipeline v2** (6 stages): Literature Review → SPECS & DESIGN (3 loops) → Prototype Loop (5-10 iterations) → Mistral Peer Review → Code Optimization (deterministic) → Final Delivery
- **Patent Generation Pipeline v2** (8 stages): Literature Review → Ideation → Selection & Drafting → Numeric Validation → Lean 4 Formalization → Business Case → Peer Review (3× multi-model) → Final Compilation

### GCP Deployment
- `deploy/tesla/`: Dockerfile.tesla, cloudbuild_tesla.yaml, setup_secrets.sh, deploy_tesla.sh
- Secret Manager integration: gemini-api-key, mistral-api-key
- Cloud Run: 2Gi, 2CPU, 3600s timeout, gen2 execution

### Demo System
- `demo/demo_prototype.py`: 649 lines, 70 tests (91.4% pass rate), pure Fraction arithmetic
- `demo/demo_rust_solver.rs`: 561 lines, 22 tests (100% pass rate), i128 rational arithmetic
- `demo/record_demo.sh`: asciinema recording → GIF video generation

### Patent Portfolio Generated
- `alexandrie/patent_portfolio_1781455106.pdf`: 155KB, 3 USPTO-style patents with appendices
- Peer reviewed by 2 independent models (7/10, REVISE)

### Prototype Specifications Generated
- `alexandrie/prototype_1781460267/`: Motion Planning (Autonomous Systems)
- `alexandrie/prototype_1781460523/`: HFT Deterministic Execution
- `alexandrie/prototype_1781460762/`: Telesurgery Force-Feedback

### Key Technical Facts
- Agora now has **28 agents** (22 active, 6 stubs)
- Agora now has **14 pipelines**
- Antigravity SDK only supports Google models (not Mistral)
- `gemini-2.0-flash` is deprecated — use `gemini-2.5-flash`
- Direct HTTP API to Mistral works (aiohttp, Bearer token)
- `AgentResult` has `slots=True` — cannot add arbitrary fields
- `AbstractAgent._stop_timer()` signature: `(start: float, label: str) -> float`

---

## Midweek Session Memory (2026-06-17)

### New Pipelines Created
- **NewTheoryDocumentationPipeline**: Formally documents mathematical discoveries (like the Callens-Schmidt Sequence), compiling LaTeX note and PDF drafts, verifying Lean 4 proof targets, running simulations, and archiving vault artifacts.
- **h3_callens_schmidt template**: Added the new Agora discovery template configuration.

### New Discoveries & Invariants
- **Callens-Schmidt Sequence ($S_{20}$)**: Apéry-like sequence $S_{20}(n) = \sum_{k=0}^n \binom{n}{k}^4 \binom{n+k}{k}$.
- Recurrence: minimal order-5 degree-9 recurrence (coefficients up to $10^{46}$).
- Growth constant: $G \approx 43.04432867$.
- Calabi-Yau slice diagonal: $F(x_1, \dots, x_5) = \frac{1}{1 - x_1(1-x_2)(1-x_3)(1-x_4)(1-x_5) - x_1 x_2 x_3 x_4 x_5}$.
- Modular Super-Congruences: $S_{20}(p n) \equiv S_{20}(n) \pmod{p^2}$ for $p=2, 3$ and $\pmod{p^3}$ for $p=5, 7$.

### GCP Deployments
- Deployed Room 3: The Arithmetic Geometer to Firebase Hosting.

### Key Technical Facts
- Agora now has **15 pipelines** (added `newtheorydocumentation`)
- Added new Socratic capability `SK-017` (Socrates Taste Sieve) in the skills registry.
- `np.math.comb` is deprecated in NumPy 2.0+; use python's standard `math.comb`.
- LaTeX compilation fails if `&` is not properly escaped as `\&` inside section headers.

