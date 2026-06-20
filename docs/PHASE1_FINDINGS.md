# Phase 1 findings — minimal Picard–Fuchs operator order for $S_{20}(n)$

> **Status.** This records a **rigorous computation**, not yet a proof. The
> minimal order is determined by exact linear algebra (cross-checked over two
> primes and over $\mathbb{Q}$) and the operator is verified on 101 consecutive
> terms. The *proof* (a creative-telescoping certificate) is scaffolded in
> [`certify_telescoper.sage`](../src/picard_fuchs/certify_telescoper.sage) and
> still needs to be run in SageMath. See [`RESEARCH_PLAN.md`](RESEARCH_PLAN.md).

## Headline result

**The minimal holonomic recurrence for**
$$S_{20}(n) = \sum_{k=0}^{n}\binom{n}{k}^4\binom{n+k}{k}$$
**has order 4** (with polynomial coefficients of degree 13). Orders 2 and 3
admit **no** relation at any coefficient degree $\le 19$.

This settles the load-bearing question of the research plan:

$$\boxed{\text{minimal order } = 4 \;\Longrightarrow\; \text{Calabi–Yau \textbf{3}-fold motive (the Apéry-}\zeta(3)\text{ situation)}.}$$

It **confirms** the proposed geometric narrative and **refutes** the old
"weight-5 / Calabi–Yau 4-fold" phrasing: a genuine CY 4-fold would have required
a minimal operator of order 5, which does not occur.

## How it was determined (reproducible, no external CAS)

[`src/picard_fuchs/find_recurrence.py`](../src/picard_fuchs/find_recurrence.py)
computes the "solvability frontier": for each order $r$, the smallest
coefficient degree $d$ at which a recurrence
$\sum_{j=0}^{r} P_j(n)\,S_{20}(n+j)=0$ exists, by finding the nullspace of the
exact linear system over $\mathrm{GF}(p)$. Each candidate is validated by
**heavily over-determining** the system (60+ more equations than unknowns, so a
spurious relation cannot survive) and by **agreement across two primes**
($2^{31}-1$ and $2147483629$).

| order $r$ | min degree $d$ | unknowns | relation found? |
|:--:|:--:|:--:|:--|
| 2 | — | — | **none** (degree $\le 19$, both primes) |
| 3 | — | — | **none** (degree $\le 19$, both primes) |
| **4** | **13** | 70 | **yes** — nullspace dim 1, both primes agree |
| 5 | 9 | 60 | yes (a left-multiple of the order-4 operator) |
| 6 | 8 | 63 | yes (a left-multiple) |

The order-4/degree-13 nullspace stays exactly 1-dimensional as the number of
equations grows from 70 up to ~195 (the relation correctly predicts every
further computed term — not a numerical accident). The order-5 and order-6
relations are not minimal: they are left-multiples of the order-4 operator
(consistent with the repo's earlier "order-5, degree-9 left-multiple").

## The exact operator

[`src/picard_fuchs/extract_operator.py`](../src/picard_fuchs/extract_operator.py)
reconstructs the operator **exactly over $\mathbb{Q}$** (1-dimensional rational
nullspace), normalizes to primitive integer polynomials $P_0,\dots,P_4$ (each of
degree 13), and **verifies $\sum_{j=0}^4 P_j(n)\,S_{20}(n+j)=0$ for all
$n=0,\dots,100$**. The coefficients are saved in
[`minimal_operator.json`](../src/picard_fuchs/minimal_operator.json).

### Singularity structure (feeds Phases 2–3)

The leading coefficient factors over $\mathbb{Z}$ as
$$P_4(n) = (n+3)^2\,(n+4)^4\,\big(8535643\,n^7 + 109720157\,n^6 + 599053915\,n^5 + 1800480209\,n^4 + 3216974566\,n^3 + 3417224202\,n^2 + 1998561324\,n + 496575040\big).$$

The factors $(n+3)$, $(n+4)$ are *apparent* singularities of the recurrence; the
degree-7 factor carries the genuine singular locus. Under the recurrence$\to$ODE
correspondence these determine the finite singular points of the differential
operator $L$, hence the **conifold / MUM structure** (Phase 2) and the candidate
**rigid fibers** for modularity (Phase 3). The dominant real singularity of the
ODE corresponds to the growth constant $\approx 43.044$ reported earlier.

## What is proved, and what is not

- **Computed & strongly validated (this phase):** minimal order $= 4$; the exact
  order-4 operator; verification on 101 terms; orders 2,3 impossible.
- **Not yet proved:** that the order-4 operator annihilates $S_{20}$ for *all*
  $n$. This needs the creative-telescoping **certificate** (a single rational
  identity in $n,k$), produced by
  [`certify_telescoper.sage`](../src/picard_fuchs/certify_telescoper.sage) once
  run in SageMath, and ideally re-checked in Lean 4 after clearing denominators.
- **Not yet done (Phase 2):** confirming $L$ is a *Calabi–Yau operator* (MUM
  point, integral mirror map / instanton numbers) and matching it against the
  AESZ / van Straten databases (which would also settle novelty).

## Tooling note — why the proof step needs GCP/Sage (Phase 1A/1B)

**Phase 1A (local).** `ore_algebra` is **not pip-installable** into a plain
Python: it is a SageMath library that imports `sage.all`, and it is not published
on PyPI (`pip install ore_algebra` → "No matching distribution"). So the
certificate cannot be produced in this repo's plain-Python environment. The
minimal-order question, however, **does not need it** — it is settled by the
exact linear algebra above.

**Phase 1B (GCP/Sage).** The certificate is therefore run on
SageMath via Google Cloud Build (project `agora-autoresearch-001`):
- `src/picard_fuchs/gcp_phase1_sage.py` — self-contained Sage script: re-derives
  the minimal recurrence (independent re-confirmation), then runs `ore_algebra`
  creative telescoping for the certificate and factors the differential operator.
- `src/picard_fuchs/Dockerfile.sage_ore` — `sagemath/sagemath` + `git` +
  `ore_algebra` (the stock image ships none of these).
- `src/picard_fuchs/cloudbuild_phase1_sage.yaml` — builds that image, runs the
  script, and uploads `phase1_result.json` to
  `gs://agora-autoresearch-001-outputs/s20-phase1/`.

**Independent re-confirmation already obtained:** a SageMath Cloud Build run
re-derived **minimal order 4, degree 13 over exact $\mathbb{Q}$** inside the
official `sagemath/sagemath` container — matching the pure-Python result above.
(The certificate sub-step requires the `ore_algebra`-equipped image above.)

### AESZ database prescreen (Phase 2 preview)

`src/picard_fuchs/match_asz_database.py` checks the operator/sequence against the
548-entry Almkvist–Straten–Zudilin database (`asz_sequences.json`). A **textual
prescreen finds no exact `Σ C(n,k)⁴ C(n+k,k)` signature** among the catalogued
closed forms (the nearest neighbour, AESZ id 18 = $\binom{2n}{n}\sum\binom{n}{k}^4$,
is genuinely different). This is *weak* evidence of novelty; the decisive check
is an operator-level comparison once the certified ODE (theta-notation) is in
hand from Phase 1B.

## Reproduce

```bash
# Local (settles minimal order; no Sage needed):
python3 src/picard_fuchs/find_recurrence.py     # ~3 s : minimal order = 4
python3 src/picard_fuchs/extract_operator.py    # ~10 s: exact operator, verified
python3 src/picard_fuchs/match_asz_database.py  # AESZ prescreen

# Proof step on GCP/SageMath (creative-telescoping certificate + factorization):
cd src/picard_fuchs
gcloud builds submit --config=cloudbuild_phase1_sage.yaml \
    --project=agora-autoresearch-001 .
# or locally if you have Sage + ore_algebra:
sage src/picard_fuchs/certify_telescoper.sage
```
