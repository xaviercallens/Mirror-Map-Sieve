# Mirror Map Sieve: A Weight-5 Apéry-like Sequence S₂₀(n)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20747943.svg)](https://doi.org/10.5281/zenodo.20747943)
[![OEIS A397213 (draft)](https://img.shields.io/badge/OEIS-A397213%20(pending%20review)-lightgrey)](https://oeis.org/draft/A397213)
[![GitHub Actions](https://github.com/xaviercallens/Mirror-Map-Sieve/actions/workflows/ci.yml/badge.svg)](https://github.com/xaviercallens/Mirror-Map-Sieve/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Status: research preprint, under community review.** This is an
> exploratory, reproducible study — not a peer-reviewed result. Several claims
> below are computational evidence rather than settled theorems, and the
> identifications with Calabi-Yau geometry are conjectural. We would genuinely
> value corrections, counter-examples, and independent verification. Please see
> [**How to contribute / review**](#how-to-contribute--review) and
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
| Sequence appears absent from OEIS (novelty) | **Likely, not certified** | Manual search returned no match; A397213 **pending editor review** |
| Cubic supercongruence $S_{20}(p)\equiv 3\pmod{p^3}$, $p\ge 5$ | **Proven in Lean 4** | Unconditional, axiom-clean; see below |
| Order-4/5 linear recurrence | **Computed; base cases formalized** | Q-nullspace solver; Lean checks small $n$, general case rests on a WZ/creative-telescoping certificate we have **not** independently re-derived in this repo |
| Mirror-map (Lian–Yau) integrality for $q_d$, small $d$ | **Computational evidence** | Exact rational arithmetic for $d \le 16$ |
| Calabi-Yau period / mirror-symmetry interpretation | **Conjectural** | Structural analogy, not a proof |
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
