# Research Plan — $S_{20}(n)$: Picard–Fuchs operator, Calabi–Yau period, modularity

> **Status.** This is a *plan*, not a set of results. Nothing here is claimed as
> proved. It is written to invite collaboration and to be falsified where wrong.
> See the [call for expert review](../README.md#calibrated-significance--call-for-expert-review).

This document lays out how we propose to study three open questions about the
weight-5 Apéry-like sequence

$$S_{20}(n) = \sum_{k=0}^{n} \binom{n}{k}^{4}\binom{n+k}{k},
\qquad f(z) = \sum_{n\ge 0} S_{20}(n)\,z^{n},$$

and how we propose to resolve an internal inconsistency in the project's current
geometric language. We state effort, validation criteria, and failure modes
honestly. We do **not** expect a breakthrough; each phase is designed to produce
a checkable artifact even if the overarching narrative fails.

---

## 0. The conceptual correction that drives everything

The current phrase **"weight-5 / Calabi–Yau 4-fold"** conflates two unrelated
notions and should be retired.

- **"Weight-5"** here is just the count of binomial factors
  ($\binom{n}{k}^4\cdot\binom{n+k}{k}\to 4+1$). This is **not** a Hodge-theoretic
  invariant and corresponds to nothing in the Calabi–Yau operator literature.
- The genuine classifier is the **order of the minimal Picard–Fuchs operator**
  $L$ annihilating $f(z)$. The standard dictionary (Almkvist–van Straten–Zudilin)
  is rigid:

  | operator order | CY dimension | (if modular) modular weight | classical example |
  |:--:|:--:|:--:|:--|
  | 2 | elliptic curve (CY 1-fold) | 2 | central binomial sums |
  | 3 | K3 (CY 2-fold) | 3 | Apéry $\zeta(2)$ / Beukers |
  | **4** | **CY 3-fold** | **4** | **Apéry $\zeta(3)$** |
  | 5 | CY 4-fold | 5 | — |

  So **order 4 $\Rightarrow$ Calabi–Yau 3-fold $\Rightarrow$ (if modular) a
  weight-4 form.** The number 4 is never a CY *dimension*, and 5 appears nowhere
  in the order-4 picture — the original narrative is internally contradictory.

### Proposed sound geometric narrative

The contradiction dissolves once we separate the **ambient construction** from
the **minimal motive**:

> The diagonal representation
> $S_{20}(n) = \operatorname{Diag}\!\big[\,1/((1-x_1)\cdots(1-x_5) - x_1x_2x_3x_4)\,\big]$
> realises $S_{20}(n)$ as a **torus period of a 4-dimensional ambient family**
> (a 5-variable rational function integrated over a 4-torus cycle). This is the
> honest origin of the "5 / 4-fold" intuition. **But the period $f(z)$ satisfies
> a minimal order-4 operator, so the arithmetically meaningful object is the
> rank-4 sub-Hodge-structure cut out by $L$ — a Calabi–Yau 3-fold motive** with
> Hodge numbers $h^{3,0}=h^{2,1}=h^{1,2}=h^{0,3}=1$. The ambient is
> 4-dimensional; the CY piece carrying the period is a 3-fold.

This matches exactly how the field treats the Apéry $\zeta(3)$ numbers, and it
turns "an embarrassing inconsistency" into a precise statement about *ambient
vs. transcendental motive*.

**Recommended public phrasing (adopt only after Phase 1):**
> *"An Apéry-like sum whose minimal Picard–Fuchs operator is (conjecturally) a
> 4th-order Calabi–Yau operator, hence attached to a Calabi–Yau 3-fold and,
> conjecturally, a weight-4 modular form."* Drop "weight-5 / 4-fold" entirely.

> **Load-bearing caveat.** The repo's "order 4" is a claim about the *recurrence
> in $n$*. The recurrence order in $n$ and the ODE order in $z$ need not coincide,
> and the operator may factor. **Establishing the true minimal ODE order is
> Phase 1; the geometry is conditional on it.** If the minimal operator is order
> 5, the narrative flips to a genuine CY 4-fold and "weight-5" would partly
> rehabilitate. This is why Phase 1 is the gate for everything else.

---

## Phase 1 — A certified minimal-order Picard–Fuchs operator

> **Result (see [`PHASE1_FINDINGS.md`](PHASE1_FINDINGS.md)).** The minimal
> recurrence order is **4** (degree-13 coefficients) — established by **four
> independent derivations** (pure-Python GF(p) nullspace, exact $\mathbb{Q}$
> reconstruction, `ore_algebra` `guess`, and Maxima `Zeilberger`), with the exact
> operator verified on 101 terms; orders 2 and 3 are impossible. This **confirms
> the CY 3-fold narrative and refutes "CY 4-fold."** The **creative-telescoping
> certificate** (Maxima, on GCP/SageMath) now proves the recurrence **for all
> $n$**. Still open: a Lean 4 re-check of the certificate identity, and pinning
> the minimal *irreducible differential* order (series-guessed ODE order is 6 —
> apparent singularities — vs. the order-4 essential piece).

**Goal.** A machine-checkable proof that $f(z)$ satisfies an explicit operator
$L$, plus a determination of the **minimal** order $m$ (is $L$ irreducible?).

**Method.**
1. **Rigorous creative telescoping — the certificate *is* the proof.** Apply
   Zeilberger / creative telescoping to the hypergeometric summand
   $t(n,k)=\binom{n}{k}^4\binom{n+k}{k}$ in **two independent systems**
   (Sage `ore_algebra`; Koutschan's `HolonomicFunctions` in Mathematica),
   cross-checked against Maple `Mgfun`. Emit the telescoper **and** the
   certificate $R(n,k)$. The recurrence's validity then reduces to a *single
   rational-function identity* in $n,k$ — that identity, not the algorithm, is
   what must be trusted.
2. **Recurrence $\leftrightarrow$ ODE, then factor.** Convert to the differential
   operator (`ore_algebra` supports this) and **factor it over $\mathbb{Q}(z)$**.
   Minimality $=$ the order-$m$ right factor annihilating $f$ is **irreducible**.
   This step decides order 4 vs. 5 vs. other — and thus the geometry.
3. **Gold-standard certification in Lean 4.** Full formalization of telescoping
   is out of reach, but after clearing denominators the certificate identity is a
   **finite polynomial identity in $n,k$** — checkable by `ring` /
   `linear_combination` / `polyrith` in Lean. Deliverable: a Lean lemma "*given
   this explicit $R(n,k)$, the telescoping identity holds*," yielding a
   kernel-checked proof of the recurrence. This is a real upgrade over the
   current base-cases-only Lean formalization, and it is achievable.

**Deliverables.** Explicit $L$ with certificate $R(n,k)$; a reproducible
`ore_algebra` notebook; a Lean certificate-checker; the determined minimal order
$m$.

**Validation.** $\ge 2$ CAS agree on $L$; the certificate identity verifies
symbolically and (after clearing denominators) in Lean; the minimal right factor
is irreducible.

**Effort / risk.** Days to ~2 weeks. The wildcard is certificate *size*
(degree-13 coefficients suggest a large $R$); the Lean check may need
`linear_combination`/`polyrith` rather than raw `ring`.

---

## Phase 2 — Calabi–Yau period identification

**Goal.** Decide whether $L$ is a *Calabi–Yau operator*, and if so identify the
3-fold. (Conditional on Phase 1 giving order 4.)

**Method.**
1. **Test the AESZ Calabi–Yau-operator criteria** on $L$:
   - a **MUM point** (maximal unipotent monodromy) at $z=0$;
   - the $N=4$ self-duality / antisymmetry of the connection;
   - **integrality of the mirror map** $q(z)=z\exp(g(z)/f(z))$ — extend the repo's
     current $q_d\in\mathbb{Z}$ ($d\le 16$) to $d\le 200{+}$, recomputed with the
     *certified* operator;
   - integral, geometric **instanton numbers** $n_d$ from the Yukawa coupling.
2. **Database match (also addresses novelty).** Search the AESZ "Tables of
   Calabi–Yau equations" and van Straten's CY-operator database for $L$, up to
   the standard operator equivalences (pullback, Möbius in $z$, scaling). A hit
   *identifies* the 3-fold and settles whether this operator is new; a miss
   strengthens the "not previously recorded" statement with real evidence.
3. **Explicit geometry from the diagonal.** Use Bostan–Lairez–Salvy ("Multiple
   binomial sums") and the diagonal to write $S_{20}(n)$ as a period integral,
   then reduce the 4-torus integral to the residual CY 3-fold (Griffiths–Dwork
   reduction on the associated hypersurface). Target: an explicit one-parameter
   family of CY 3-folds whose holomorphic period is $f(z)$.

**Deliverables.** A CY-operator checklist verdict; mirror map + instanton numbers
$n_d$ with integrality evidence; an AESZ match (or a documented non-match); a
candidate explicit family.

**Validation.** Integrality of $q_d$ and $n_d$; Yukawa-coupling consistency;
high-precision numerical agreement of the period with $f(z)$.

**Honest expectation.** *Modest.* Even a clean positive result is "a new (or
known) row in the AESZ tables," not a breakthrough — and it may be a known
operator in disguise.

---

## Phase 3 — Modularity

**Goal.** Test whether the CY 3-fold motive is modular (a weight-4 newform), and
connect that to the congruence data. (Depends on Phase 2's rigid-fiber data.)

**Method.**
1. **Locate rigid / special fibers.** Modularity is cleanest where the CY 3-fold
   becomes **rigid** ($h^{2,1}=0$) — typically the conifold points (apparent
   singularities / roots of the leading coefficient of $L$). Rigid CY 3-folds
   over $\mathbb{Q}$ are modular (Gouvêa–Yui) with a **weight-4** Hecke eigenform.
2. **Compute candidate Frobenius traces** $a_p$ via point counts, the operator's
   $p$-curvature, or directly from the truncated period mod $p$ (the
   Atkin–Swinnerton-Dyer route), for $p$ up to a few hundred.
3. **Match against a weight-4 newform.** Search LMFDB / Magma / Sage newform
   spaces $S_4(\Gamma_0(N))$ at the conductor $N$ suggested by the bad primes of
   $L$; match $a_p$ to Hecke eigenvalues.
4. **Upgrade the congruences to the real target.** The current
   $S_{20}(p)\equiv 3\pmod{p^3}$ is elementary and detects none of this. The deep
   analogue — the genuine prize — is a **Beukers / Atkin–Swinnerton-Dyer-type
   supercongruence** linking $S_{20}$ to the weight-4 form's eigenvalues (model:
   Ahlgren–Ono's proof of the Apéry-$\zeta(3)$ supercongruence via
   $\eta(2\tau)^4\eta(4\tau)^4$). Formulate the precise conjecture, test
   numerically, and only then attempt a proof.

**Deliverables.** A candidate $a_p$ table; a conjectural weight-4 newform with
conductor; an LMFDB identification (or non-match); a precisely stated,
numerically tested supercongruence conjecture.

**Validation.** $a_p$ match a newform across many primes and respect the Hecke
relations; the congruence holds to the tested bound.

---

## Cross-cutting matters

**Tooling.** Sage (`ore_algebra`), Mathematica (`HolonomicFunctions`), Maple
(`Mgfun`), PARI/GP, Magma, LMFDB; Lean 4 + Mathlib for the certificate check; the
AESZ and van Straten CY-operator databases.

**Sequencing & gates.**
- **Phase 1 is the gate.** Do **not** advance the geometric narrative publicly
  until the minimal order is certified.
- Phases 2 and 3 may overlap once $m$ is fixed; Phase 3 depends on Phase 2's
  rigid-fiber data.
- Update the README/paper narrative to the "ambient-4-fold vs. minimal-CY-3-fold
  motive" framing **only after Phase 1** confirms order 4.

**Effort (honest).** Phase 1 ≈ days–2 weeks; Phase 2 ≈ weeks (benefits greatly
from one expert consult); Phase 3 ≈ weeks–months (most likely to need a
specialist co-author).

**Failure modes (stated up front).**
- (a) Minimal order $\ne 4$ → the geometry changes; revise the narrative.
- (b) $L$ is not a CY operator (no MUM / non-integral instantons) → drop the CY
  framing entirely.
- (c) $L$ is a known AESZ entry → novelty evaporates, but we gain a clean
  identification (a good outcome to report).
- (d) Not modular / no rigid fiber → state that plainly.

**Documentation discipline.** Tag every claim **proved / certified-numerically /
conjectural**, consistent with the v6 paper's honest-scope table. No phase
requires a breakthrough to be useful: each yields a checkable artifact.

---

## How to help

If you are a specialist in Apéry-like sequences, holonomic functions, or
Calabi–Yau differential operators, the highest-value contributions are:
1. a **prior appearance** of $L$ (or of $S_{20}$) in the literature or the AESZ /
   van Straten databases — we will gladly acknowledge and amend;
2. a **certified creative-telescoping certificate** for the recurrence;
3. confirmation or correction of the **minimal operator order** and the
   **CY-operator status**;
4. a **weight-4 newform** matching the Frobenius traces, with conductor;
5. a proof or refutation of the conjectural mod-$p^3$ Apéry-style congruence.

Please open a [GitHub issue](https://github.com/xaviercallens/Mirror-Map-Sieve/issues)
or pull request.
