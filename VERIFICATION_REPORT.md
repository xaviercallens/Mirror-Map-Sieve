# Verification & Reproducibility Report — S₂₀(n) (v6)

This report records the exact, reproducible verification performed for the
weight-5 Apéry-like sequence

$$S_{20}(n) = \sum_{k=0}^{n} \binom{n}{k}^4 \binom{n+k}{k}.$$

> **Honesty notes.** (1) The proposed OEIS identifier **A397213 is a draft
> pending editorial review — not an accepted OEIS sequence.** (2) The items
> labelled *EMPIRICAL / conjectural* below are computational evidence, not
> theorems. (3) This is a preprint awaiting community review.

Environment:
- **Lean toolchain**: `leanprover/lean4:v4.31.0`
- **Mathlib revision**: `ec6e08b4dfb414460f0ee7b4ce9678e7e04fb584`
- **Python**: 3.12 (standard library only — `math.comb`)

---

## 1. Numerical verification (Python)

Run:

```bash
python3 python/verify_all.py     # exit code 0 ⟺ all checks pass
```

Result: **ALL NUMERICAL CHECKS PASSED.**

| # | Check | Range tested | Outcome |
|---|-------|--------------|---------|
| 1 | Terms match independent reference | $n = 0..17$ | ✅ exact |
| 2 | Cubic supercongruence $S_{20}(p)\equiv 3 \pmod{p^3}$ | primes $5..200$ (44) | ✅ (proven) |
| 3 | Apéry-style $S_{20}(p-1)\equiv 1 \pmod p$ | primes $2..200$ (46) | ✅ (proven) |
| 3′ | Proof mechanism $p \mid \binom{p-1+k}{k}$, $1\le k\le p-1$ | primes $5..100$ | ✅ |
| 3″ | **Empirical only** $S_{20}(p-1)\equiv 1 \pmod{p^3}$ | primes $5..200$ | ✅ **(OPEN — not proven)** |
| 4 | Wolstenholme $\binom{2p}{p}\equiv 2 \pmod{p^3}$ | primes $5..200$ | ✅ (proven) |
| 4′ | Babbage $\binom{2p}{p}\equiv 2 \pmod{p^2}$ | primes $2..200$ | ✅ (proven) |
| 5 | Collapse $S_{20}(p)\equiv 1+\binom{2p}{p} \pmod{p^3}$, interior $\equiv 0$ | primes $5..100$ | ✅ (proven) |
| 6 | Diagonal of $1/(\prod(1-x_i) - x_1x_2x_3x_4)$ equals $S_{20}(n)$ | $n = 0..6$ | ✅ |

First ten terms:
`1, 3, 55, 1155, 29751, 852753, 26097499, 840454275, 28064517175, 964417304253`.

---

## 2. Formal verification (Lean 4)

Build & kernel-check:

```bash
cd src/lean_proofs && lake build MirrorMapSieve
```

Result: **`Build completed successfully`** — no errors, no `sorry`, no `admit`.

### Axiom audit (`#print axioms`)

Every headline theorem depends **only** on Lean's three standard foundational
axioms (`propext`, `Classical.choice`, `Quot.sound`) — i.e. **no `sorryAx` and
no project-specific axioms**:

| Theorem (namespace `MirrorMapSieve.CallabiYau`) | Statement | Axioms |
|---|---|---|
| `Supercongruence.supercongruence_unconditional` | $S_{20}(p)\equiv 3 \pmod{p^3}$, $p\ge 5$ | standard only |
| `Supercongruence.supercongruence_mod_sq` | $S_{20}(p)\equiv 3 \pmod{p^2}$, all $p$ | standard only |
| `Wolstenholme.wolstenholme` | $\binom{2p}{p}\equiv 2 \pmod{p^3}$, $p\ge 5$ | standard only |
| `Wolstenholme.babbage` | $\binom{2p}{p}\equiv 2 \pmod{p^2}$, all $p$ | standard only |
| `AperyCongruence.apery_congruence` | $S_{20}(p-1)\equiv 1 \pmod p$, all $p$ | standard only |

Reproduce the audit:

```bash
cd src/lean_proofs
echo 'import MirrorMapSieve
open MirrorMapSieve.CallabiYau
#print axioms Supercongruence.supercongruence_unconditional
#print axioms Wolstenholme.wolstenholme
#print axioms AperyCongruence.apery_congruence' > /tmp/Audit.lean
lake env lean /tmp/Audit.lean
```

### Scope of the formal proofs (honest)

- **Proven, unconditional, axiom-clean**: the cubic supercongruence
  $S_{20}(p)\equiv 3\pmod{p^3}$ ($p\ge5$), Wolstenholme $\binom{2p}{p}\equiv 2
  \pmod{p^3}$ ($p\ge5$), Babbage mod $p^2$ (all $p$), and the Apéry-style
  congruence $S_{20}(p-1)\equiv 1\pmod p$ (all $p$).
- **NOT formalized in general**: the order-4/5 linear recurrence for general
  $n$ (Lean verifies only small base cases; the general statement rests on a
  creative-telescoping certificate not re-derived here), and the **mod $p^3$
  refinement** of the Apéry-style congruence (open).
- **Conjectural**: the Calabi-Yau period / mirror-symmetry interpretation and
  Lian–Yau integrality beyond the tested range.

---

## 3. AI-hardware kernels (exploratory — not a verified result)

The kernels in `4_ai_hardware_attention/` are an exploratory proof-of-concept.
Using $S_{20}$ as an attention-decay profile is a heuristic; reported GPU
speedups are the generic consequence of block-sparse windowing and are **not**
evidence that $S_{20}$ outperforms other sparse-attention methods. These should
be independently benchmarked before being relied upon.

---

*Generated as part of the v6 release. Corrections and independent verification
are warmly welcomed via GitHub issues / pull requests.*
