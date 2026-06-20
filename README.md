# Mirror Map Sieve: A Weight-5 Apéry-like Sequence S₂₀(n)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20747943.svg)](https://doi.org/10.5281/zenodo.20747943)
[![OEIS A397213 (draft)](https://img.shields.io/badge/OEIS-A397213%20(pending%20review)-lightgrey)](https://oeis.org/draft/A397213)
[![GitHub Actions](https://github.com/xaviercallens/Mirror-Map-Sieve/actions/workflows/ci.yml/badge.svg)](https://github.com/xaviercallens/Mirror-Map-Sieve/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Status: exploratory preprint seeking expert review. We do not claim a
> discovery.** This is a reproducible study of one member of a well-studied
> family of binomial sums — not a peer-reviewed result and not a breakthrough.
> $S_{20}$ being previously untabulated (if confirmed) would make it *new* only
> in the narrow sense that this exact sum may not have been recorded before; it
> would not, by itself, be mathematically significant. We are actively seeking
> review from specialists in Apéry-like sequences and Calabi-Yau differential
> operators, and we welcome corrections, counter-examples, and the news that
> this is already known. Please see
> [**Calibrated significance & call for expert review**](#calibrated-significance--call-for-expert-review),
> [**How to contribute / review**](#how-to-contribute--review), and
> [**Honest scope & limitations**](#honest-scope--limitations).

> **⚠️ OEIS status.** The proposed sequence identifier **A397213 is a draft
> submission and has _not_ been approved by the OEIS editors.** Until a maintainer
> accepts it, A397213 is a placeholder, not an official OEIS entry, and the
> sequence may not yet appear in a public OEIS search. Do not cite it as an
> accepted OEIS sequence. See [`OEIS_SUBMISSION.md`](OEIS_SUBMISSION.md).

---

## What this repository studies

The integer sequence

$$ S_{20}(n) = \sum_{k=0}^{n} \binom{n}{k}^4 \binom{n+k}{k} = 1,\ 3,\ 55,\ 1155,\ 29751,\ 852753,\ \dots $$

a **weight-5 Apéry-like binomial sum**. We provide reproducible code and Lean 4
formalizations exploring the following, in decreasing order of how firmly each
is established:

| Claim | Status | Evidence |
|-------|--------|----------|
| The first ~80 terms and the closed-form sum | **Verified** | Exact integer arithmetic, reproducible |
| This exact sum is not previously tabulated (we did **not** find it) | **Unconfirmed; not a significance claim** | Manual search returned no match; A397213 **pending editor review**. Absence from OEIS reflects attention, not depth — see significance note |
| Cubic supercongruence $S_{20}(p)\equiv 3\pmod{p^3}$, $p\ge 5$ | **Proven in Lean 4 (but shallow — see note)** | Unconditional, axiom-clean; the proof is elementary and applies to any such sum with $\binom{n}{k}$ to a power $\ge 3$ |
| Minimal **order-4** linear recurrence | **Proved for all $n$** (certificate) | Order 4 from four independent derivations; a Maxima/Zeilberger creative-telescoping **certificate** (computed on GCP/SageMath) proves it for all $n$. Lean re-check of the certificate still pending. See [`docs/PHASE1_FINDINGS.md`](docs/PHASE1_FINDINGS.md) |
| Mirror-map (Lian–Yau) integrality for $q_d$, small $d$ | **Computational evidence** | Exact rational arithmetic for $d \le 16$ |
| Minimal **differential** operator order of $f(z)$ | **Computed: order 6, degree 15** | Exact nullspace + `ore_algebra`; indicial eq. $-715\,s^4(s-1)^2$ ⇒ order-4 **MUM block** + order-2 apparent singularity. See [`docs/PHASE2_FINDINGS.md`](docs/PHASE2_FINDINGS.md) |
| Calabi-Yau **3-fold** period interpretation | **Conjectural — evidence strengthened** | Two strands now point to a CY **3-fold** (order-4 MUM block; $q_d\in\mathbb{Z}$), refuting "4-fold". Still needs the explicit $L_6=L_4\cdot L_2$ factorization to be a claim |
| Instanton-number integrality | **Unresolved (honest negative)** | Placeholder Yukawa gave non-integers (denominators $\sim d^3$ — a normalization artifact); the correct coupling needs $L_4$. Not evidence against CY-ness |
| INT64 attention kernels (AI hardware) | **Exploratory proof-of-concept** | Heuristic; benchmarks largely CPU — see caveats |

If you find an error in any row above, please open an issue — that is exactly
the kind of feedback this preprint is published to receive.

---

## The one result we state without hedging

**Cubic supercongruence (formally verified, unconditional for primes $p \ge 5$):**

$$ S_{20}(p) \equiv 3 \pmod{p^3}. $$

This is machine-checked in Lean 4 (`src/lean_proofs/MirrorMapSieve/CallabiYau/`),
with **no `sorry`, no `admit`, and no custom axioms** — the only dependencies are
Lean's three standard foundational axioms (`propext`, `Classical.choice`,
`Quot.sound`). The proof combines:

1. a "collapse" of the interior of the sum modulo $p^3$ (the original step), and
2. a from-first-principles formalization of **Wolstenholme's theorem**
   $\binom{2p}{p}\equiv 2 \pmod{p^3}$, which is not present in our pinned Mathlib.

An unconditional mod-$p^2$ version holds for **all** primes (via Babbage's
congruence). Reproduce with `cd src/lean_proofs && lake build`.

> **We are proud of the formalization, not the theorem.** The Lean proof is
> clean and axiom-free, but the *result* is elementary: because $\binom{n}{k}$
> enters the sum to the **fourth** power, each interior term is divisible by
> $p^4$ and the sum collapses to $1+\binom{2p}{p}$, after which Wolstenholme
> finishes it. The same argument gives $S(p)\equiv 3 \pmod{p^3}$ for **any**
> sum $\sum_k \binom{n}{k}^a \binom{n+k}{k}$ with $a\ge 3$. An expert will (correctly)
> see this as low-hanging fruit, not arithmetic depth. We state it plainly so
> the formalization is not mistaken for a deep discovery.

---

## Calibrated significance & call for expert review

We want to be candid about how significant this is likely to be, because
over-claiming would waste reviewers' time and our own credibility.

**Honest self-assessment.** $S_{20}$ is the $(A,B)=(4,1)$ member of the family
$\sum_k \binom{n}{k}^A \binom{n+k}{k}^B$ (the Apéry numbers are the $(2,2)$
case). This family has been searched systematically by Zagier, Almkvist–Zudilin,
Cooper, and others. A previously-unlisted member of a well-mapped family is, at
best, **a modest contribution — a possible new row in the
Almkvist–van Straten–Zudilin tables — not a breakthrough.** "Not in OEIS"
measures attention, not importance, and the cubic supercongruence we proved is
elementary (see the note above). The genuinely interesting questions — a
certified finite-order Picard–Fuchs recurrence, a real Calabi–Yau period
identification, modularity — are exactly the ones this repository leaves
*conjectural or merely computed*.

**The most defensible framing of this work is:**
> "A binomial sum in the Apéry-like family that we did not find previously
> recorded; it satisfies the expected cubic supercongruence (now formally
> verified in Lean), and *appears* to have an order-4 recurrence and Lian–Yau
> integrality that we have not yet proven."

That is true and modest, and it is the claim we stand behind. We explicitly do
**not** claim a "discovery" or "breakthrough."

**What would actually move the needle — and where we ask for expert help:**

- **Is this sum already known?** A pointer to a prior appearance (possibly under
  a different normalization, or in the AESZ Calabi–Yau database) would be the
  single most useful response. We would gladly retract the novelty wording.
- **Is the order-4 Picard–Fuchs operator genuinely new** among catalogued
  Calabi–Yau / Apéry-like operators, or a known one in disguise?
- **What is the correct geometry?** The order-4 operator points to a Calabi–Yau
  **3-fold**; please correct our "weight-5 / 4-fold" phrasing if it is wrong.
- **A verified recurrence certificate** (a checked WZ/creative-telescoping
  proof) and **a proof or refutation** of the mod-$p^3$ Apéry-style conjecture.

If you are a specialist in Apéry-like sequences or Calabi–Yau differential
equations, we would be grateful for even a brief, skeptical reading. Please open
a [GitHub issue](https://github.com/xaviercallens/Mirror-Map-Sieve/issues).

A detailed, falsifiable plan for attacking these questions — a certified
Picard–Fuchs operator, a Calabi–Yau period identification, and modularity,
together with a proposed resolution of the "weight-5 / 4-fold" inconsistency —
is in [`docs/RESEARCH_PLAN.md`](docs/RESEARCH_PLAN.md).

**Phase 1 — progress (the minimal recurrence is now proved).** The **minimal
recurrence order is 4** (degree-13 coefficients), not 5 — which points to a
Calabi–Yau **3-fold**, not a 4-fold, resolving the inconsistency in favour of the
3-fold narrative. This order is now established by **four independent
derivations** (pure-Python GF($p$) nullspace, exact $\mathbb{Q}$ reconstruction,
`ore_algebra` `guess`, and Maxima `Zeilberger`), and a creative-telescoping
**certificate** — computed on SageMath via Google Cloud Build — **proves the
recurrence for all $n$** (not merely the 101 verified terms). The exact operator,
the certificate, and the full run are in
[`docs/PHASE1_FINDINGS.md`](docs/PHASE1_FINDINGS.md) and
[`src/picard_fuchs/`](src/picard_fuchs/). Still open: a Lean 4 re-check of the
certificate identity.

**Phase 2 — progress (Calabi–Yau structure, with one honest negative).** The
minimal *differential* operator for $f(z)$ has order **6** (degree 15, exact
nullspace) — but its indicial equation at $z=0$ is $-715\,s^4(s-1)^2$, i.e. an
**order-4 maximal-unipotent-monodromy (MUM) block** (the Calabi–Yau **3-fold**
hallmark) plus an order-2 **apparent-singularity** factor. With the integral
mirror map ($q_d\in\mathbb{Z}$, $d\le16$), two independent strands now support a
CY **3-fold** — consistent with the proved order-4 recurrence, and definitively
*not* a 4-fold. **Honest negative:** a placeholder Yukawa normalization gives
**non-integer** instanton numbers (denominators $\sim d^3$ — a normalization
artifact, not a refutation), so instanton integrality is **unresolved**. The
CY identification stays **conjectural** pending the explicit $L_6=L_4\cdot L_2$
factorization and the correct coupling. Details:
[`docs/PHASE2_FINDINGS.md`](docs/PHASE2_FINDINGS.md).

---

## Honest scope & limitations

We want to be upfront about what is *not* established, echoing our own internal
audit ([`journal.md`](journal.md)):

- **OEIS A397213 is not approved.** It is a draft awaiting editorial review.
- **The general recurrence is not fully formalized.** Lean verifies small base
  cases; the general-$n$ statement relies on a creative-telescoping certificate
  that we have not re-verified independently inside this repository.
- **The Calabi-Yau / mirror-symmetry narrative is interpretive.** The integrality
  and period statements are computational evidence and analogy, not theorems.
- **The AI-hardware kernels are exploratory.** Using $S_{20}$ as an attention
  decay is a heuristic; any fast-growing integer sequence yields a similar
  reciprocal decay. The shipped benchmark numbers were collected largely on CPU
  — treat any GPU figures as unverified placeholders pending an independent run.
  The "0% perplexity degradation" and "topological" framings are suggestive, not
  rigorous, and should be reproduced before being relied upon.
- **No external peer review yet.** Everything here is pre-publication.

---

## Key computational findings (please scrutinize)

### Closed form and first terms
$S_{20}(n) = \sum_{k=0}^n \binom{n}{k}^4\binom{n+k}{k}$. The first ten terms are
$1, 3, 55, 1155, 29751, 852753, 26097499, 840454275, 28064517175, 964417304253$.

### Linear recurrence (computed)
$S_{20}(n)$ appears to satisfy a minimal order-4, degree-13 linear recurrence
(with an order-5, degree-9 left-multiple), obtained from a $\mathbb{Q}$-nullspace
computation. The coefficients are reproducible; the *general* proof is not yet
self-contained here (see limitations).

### Mirror-map integrality (evidence)
The mirror-map coefficients $q_d$ computed with exact rational arithmetic are
integers for $d \le 16$. This is consistent with Lian–Yau integrality but is
presented as evidence, not a closed proof.

### Diagonal representation (conjectural)
We explore whether $S_{20}(n)$ is the main diagonal of a rational function. The
diagonal-search code is honest research code and reports both successes and
failures.

---

## AI hardware exploration (proof-of-concept)

The [`4_ai_hardware_attention/`](4_ai_hardware_attention/) directory contains an
**experimental** study of using the exact integer sequence $S_{20}(d)$ as a
deterministic INT64 attention-decay table, as an alternative to floating-point
positional decays (ALiBi/RoPE-style). This is a curiosity-driven prototype, not a
validated method. Please read the in-file caveats and reproduce before drawing
conclusions.

### Block-sparse long-context timings (please interpret carefully)

Using the rapid decay of $S_{20}$ to justify a fixed attention window $W$ turns
the kernel into ordinary **block-sparse attention**, which lowers prefill cost
from $\mathcal{O}(N^2)$ to $\mathcal{O}(N\cdot W)$. The following prefill
latencies were reported on a single NVIDIA L4 GPU:

| Sequence length | Dense SDPA | $S_{20}$ block-sparse ($W$ fixed) | Ratio |
| :--- | :--- | :--- | :--- |
| 8,192 (8k) | 3.81 ms | 1.20 ms | 3.2× |
| 16,384 (16k) | 19.16 ms | 3.23 ms | 5.9× |
| 32,768 (32k) | 75.62 ms | 6.38 ms | 11.9× |
| 65,536 (64k) | 311.88 ms | 12.89 ms | 24.2× |
| 131,072 (128k) | 1,602.37 ms | 26.01 ms | 61.6× |

**Honest reading of this table.** The speedup is the *generic* consequence of
replacing dense $\mathcal{O}(N^2)$ attention with a fixed-window
$\mathcal{O}(N\cdot W)$ kernel — **any** windowing scheme (sliding-window, local
attention, etc.) gives the same asymptotics; $S_{20}$ only supplies one
particular justification for the window size. It is **not** evidence that
$S_{20}$ outperforms other sparse-attention methods, and it says nothing about
model *quality* (perplexity/accuracy), which a windowed kernel can degrade.
These are single-run numbers on one GPU, not a controlled benchmark; we publish
them only as a reproducibility target and would welcome a rigorous comparison
against established sparse-attention baselines.

---

## How to contribute / review

This project is published *specifically to invite community involvement.* We are
not claiming a finished result, and we would rather find mistakes now than later.
Concretely, we would welcome:

- **Independent verification** of the term values, recurrence coefficients, and
  the Lean proofs (`lake build` and `#print axioms`).
- **A self-contained proof of the general recurrence** (a verified WZ /
  creative-telescoping certificate) to replace the current reliance on an
  external certificate.
- **OEIS expertise** — help confirming novelty and shepherding the A397213 draft
  through editorial review (or pointing out a prior appearance we missed).
- **A rigorous take on the Calabi-Yau interpretation** — is the mirror-period
  identification actually correct, and can it be proven?
- **Counter-evidence or critique** of the AI-hardware kernels, including proper
  GPU benchmarks.
- **General corrections** to any overstatement in the docs or paper.

Please open a [GitHub issue](https://github.com/xaviercallens/Mirror-Map-Sieve/issues)
or pull request. Mathematical disagreement and skeptical review are explicitly
welcome.

---

## Reproducibility

```bash
git clone https://github.com/xaviercallens/Mirror-Map-Sieve.git
cd Mirror-Map-Sieve

# Compute the sequence (exact integer arithmetic)
python python/compute_s20.py

# Build and kernel-check the Lean 4 proofs
cd src/lean_proofs && lake build

# Mirror-map verification (exact rational arithmetic)
python src/mirror_map/verify_mirror_map.py
```

See the [Reproducibility Guide](docs/reproducibility.md) for details.

---

## Citation

This is a preprint; please cite it as such, and please do **not** describe
A397213 as an accepted OEIS sequence until it has been approved.

```bibtex
@misc{Callens2026MirrorMapSieve,
  author  = {Xavier Callens},
  title   = {Mirror Map Sieve: A Weight-5 Apéry-like Sequence $S_{20}(n)$ and its Cubic Supercongruence (preprint, under review)},
  year    = {2026},
  doi     = {10.5281/zenodo.20747943},
  url     = {https://github.com/xaviercallens/Mirror-Map-Sieve},
  note    = {Proposed OEIS A397213 is a draft submission pending editorial review.}
}
```

**DOI**: [10.5281/zenodo.20747943](https://doi.org/10.5281/zenodo.20747943)
**Proposed OEIS id (pending review)**: A397213
