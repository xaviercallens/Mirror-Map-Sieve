# Phase 2 findings — differential operator structure & Calabi–Yau evidence

> **Status.** Rigorous computations (exact arithmetic) plus one honest negative.
> Nothing here is a proof of the Calabi–Yau identification; the positive evidence
> is the MUM structure and mirror-map integrality, and one sub-computation
> (instanton normalization) is explicitly **unresolved** and flagged for expert
> review. See [`RESEARCH_PLAN.md`](RESEARCH_PLAN.md), Phase 2.

## The order-4 vs order-6 puzzle — resolved

Phase 1 proved the **recurrence in $n$ has order 4**. But the minimal **linear
ODE** for $f(z)=\sum_n S_{20}(n)z^n$ has **order 6**, established two independent
ways:
- `ore_algebra`'s series `guess` (on GCP/SageMath) → order 6;
- exact $\mathrm{GF}(p)$ / $\mathbb{Q}$ nullspace
  ([`find_ode.py`](../src/picard_fuchs/find_ode.py)) → order 6, degree 15;
  orders 1–5 impossible, nullspace stable under heavy over-determination.

These are **not contradictory**: the recurrence order in $n$ and the holonomic
rank of $f(z)$ (= minimal ODE order in $\mathrm d/\mathrm dz$) are different
invariants. The reconciliation is in the **local structure at $z=0$**.

### Indicial equation at $z=0$ (exact)

[`analyze_ode.py`](../src/picard_fuchs/analyze_ode.py) reconstructs the exact
order-6 operator in $\theta=z\,\mathrm d/\mathrm dz$ form and computes the
indicial polynomial at $z=0$:

$$ -715\,s^{4}(s-1)^{2} = 0 \quad\Longrightarrow\quad \text{local exponents } \{0,0,0,0,\;1,1\}. $$

Reading this:
- The **exponent $0$ with multiplicity $4$** is a **maximal-unipotent-monodromy
  (MUM) block of order 4** — the structural hallmark of a **Calabi–Yau 3-fold**
  Picard–Fuchs operator (the Apéry-$\zeta(3)$ situation). This is the
  geometrically essential piece, and it matches the proved order-4 recurrence.
- The extra **exponents $\{1,1\}$** are an integer-shifted, order-2 block —
  the signature of an **apparent singularity / reducible factor** that inflates
  the holonomic rank of $f(z)$ from 4 to 6 but carries **no new transcendental
  (CY) content**.

**Conclusion (evidence, not yet proof):** the essential Picard–Fuchs operator is
**order 4 with a MUM point → Calabi–Yau 3-fold**, consistent with the proved
order-4 recurrence. The "order 6" is the holonomic rank of $f$ as a whole, not
the order of the CY operator. A fully rigorous statement requires exhibiting the
factorization $L_6 = L_4\cdot L_2$ (or $L_4$ as a right factor) with $L_4$
irreducible — deferred to a version-matched Sage/`ore_algebra` or expert review.

## Mirror-map integrality (positive CY evidence)

[`verify_mirror_map.py`](../src/mirror_map/verify_mirror_map.py) computes, in
exact rational arithmetic, the mirror map $q(z)=z\exp(g/f)$ from the holomorphic
period $f$ and the standard logarithmic period
$g=\sum_n B(n)z^n$, $B(n)=\sum_k \binom nk^4\binom{n+k}k[4(H_n-H_{n-k})+(H_{n+k}-H_n)]$.
**All coefficients $q_1,\dots,q_{16}$ are integers** ($q_1=1,q_2=9,q_3=165,
q_4=4110,\dots$). Integrality of the mirror map is consistent with — and expected
for — a MUM Calabi–Yau-3-fold operator (Lian–Yau), and independently corroborates
the order-4 MUM block found above.

## Instanton numbers — UNRESOLVED (honest negative)

[`instanton_numbers.py`](../src/picard_fuchs/instanton_numbers.py) attempts the
more stringent test: the genus-0 instanton numbers $n_d$ from the normalized
Yukawa coupling $K(q)=n_0+\sum_d n_d d^3 q^d/(1-q^d)$ should be integers.

With a **placeholder** coupling ($\theta_q^2$ of the mirror map), the candidate
$n_d$ are **not** integers — and the denominators are exactly $d^3$-flavoured
($165/2^3,\,3463611/5^3,\,2144305763/7^3,\dots$). That precise denominator
pattern is the signature of a **wrong Yukawa normalization**, not a refutation of
CY-ness: the geometrically correct coupling $K_{zzz}$ requires the certified
order-4 operator's structure (the Yukawa is read off the operator, not guessed
from the periods alone). We therefore report this as **unresolved** and do **not**
claim instanton integrality.

**What would settle it:** the correct one-parameter CY-3 Yukawa
$K = f^{-2}\,(q\,\mathrm dz/(z\,\mathrm dq))^{?}\cdots$ derived from the
desingularized order-4 operator $L_4$ — a natural task once $L_4$ is extracted,
and a good item for expert input.

## Summary

| Item | Result | Status |
|------|--------|--------|
| Minimal ODE order of $f(z)$ | 6 (deg 15) | proved by exact nullspace |
| Local exponents at $z=0$ | $\{0^4,1^2\}$ | exact |
| MUM block of order 4 | present | exact (indicial) ⇒ **CY 3-fold evidence** |
| Order-2 extra factor | apparent singularity | indicated by $\{1,1\}$ exponents |
| Mirror map $q_d$ integral | yes, $d\le16$ | exact rational arithmetic |
| Instanton $n_d$ integral | **unresolved** | wrong Yukawa normalization; flagged |
| Explicit $L_6=L_4\cdot L_2$ factorization | not done | needs Sage/expert |

The Calabi–Yau **3-fold** reading is now supported by two independent strands
(order-4 MUM block; mirror-map integrality), consistent with the proved order-4
recurrence — while remaining, honestly, a **conjectural identification** pending
the operator factorization and the correct instanton normalization.
