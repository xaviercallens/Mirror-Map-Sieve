# Mirror Map Sieve — Lessons Learned (Revised After Deep Audit)

## Architecture Lessons

### 1. The Double-Loop Works — But Only for What It Covers
The AI-generated heuristic + exact verification loop is genuinely effective for *discovery*. It found a novel sequence, extracted a correct recurrence, and verified mirror map integrality. But the loop has a gap: the **bridge between finite verification (Lean) and infinite validity (WZ/SageMath) is not formalized**. This gap must be honestly communicated, not papered over.

### 2. Lean 4 Is Not a CAS — and That's OK
Lean 4 is brilliant for certifying that `(-5412650858431135013634958175726842170573378411840) * 1 + ... = 0`. It should NOT be asked to do symbolic polynomial expansion on 46-digit coefficients. The correct split:
- **SageMath/WZ**: Prove the recurrence holds for all n (creative telescoping certificate)
- **Lean 4**: Certify that the base cases and uniqueness theorem hold (kernel arithmetic)
- **Neither alone is sufficient**; together they form a complete proof

### 3. Disk Space Kills Lean Builds
A full `lake build` of Mathlib from source consumes >3.2GB. On constrained environments, always use `lake exe cache get` first. The build was killed mid-way due to filling the disk.

## Mathematical Lessons

### 4. The Sequence Is Genuinely New
OEIS search for `1,3,55,1155,29751,852753,26097499` returns **zero results**. This is rare and significant. The sum $\sum \binom{n}{k}^4 \binom{n+k}{k}$ was apparently never studied before.

### 5. The $S(p) \equiv 3 \pmod{p^3}$ Finding Is Striking
Most Apéry-like sequences satisfy $S(p) \equiv S(1) \pmod{p^3}$ — here $S(1) = 3$, so the congruence is $S(p) \equiv 3$. This COULD be trivially explained (it might just be $S(p) \equiv S(1)$), or it could reflect something deeper about the formal group. The next session must carefully check whether this is an instance of the general pattern or a new phenomenon.

### 6. The Diagonal Representation Is the Real Prize
Christol's theorem guarantees a rational function F(x₁,...,x₅) whose diagonal is S(n). Finding it explicitly would:
- Provide a Calabi-Yau model for the mirror family
- Enable direct computation of the Picard-Fuchs equation
- Likely resolve the supercongruences via known techniques
The `diagonal_search.py` code is honest — it tried several candidates, falsified all of them, and correctly labels this as an open problem.

## Process Lessons

### 7. Claims Drift When Building Fast
Under time pressure, the README accumulated claims ("formally verified", "0 Axioms", "topological attention decay") that are individually defensible but collectively misleading. A periodic audit like this one is essential.

### 8. Self-Eponymy Is a Mistake
The "S_20" naming persists in the README despite being removed from the paper. It serves no mathematical purpose and actively undermines credibility with the number theory community. The standard practice is to name sequences after their defining formula or after the first person to submit them to OEIS — and that only happens AFTER the OEIS editor assigns the name.

### 9. The AI Hardware Section Dilutes the Message
A reviewer reading a paper about Calabi-Yau periods will be confused by INT64 GPU attention kernels. These are unrelated to the mathematical contribution. Keep the repository focused on what it does best: rigorous computational number theory.

### 10. Tests Are Not Optional
A mathematics repository without tests is like a theorem without a proof. The recurrence can be verified at 70 points in under 10 seconds. There is no excuse for not having automated tests.

## Phase 1 & 2 Lessons (Picard–Fuchs research program, 2026-06-20)

### 11. `ore_algebra` Is Not pip-Installable — and Its Sage Pairing Is Fragile
`ore_algebra` imports `sage.all` and is not on PyPI; `pip install ore_algebra`
fails outright. Worse, there is a real **version matrix**: its Cython extension
won't compile against Sage 10.4's older FLINT (`unknown type name 'slong'`),
while on Sage `:latest` its symbolic `.factor()` path crashes
(`sage.rings.abc has no attribute 'SymbolicRing'`). Lesson: for CY-operator work,
either pin a maintainer-blessed Sage+`ore_algebra` pair, or route around it.
The robust route we found: use `:latest` for `guess` (which worked) and
**Maxima's `Zeilberger`** (bundled with Sage, no compilation, version-independent)
for the certificate.

### 12. Recurrence Order ≠ ODE Order — Don't Conflate Them
The recurrence in $n$ has order **4**; the minimal ODE for $f(z)$ has order
**6**. These are different invariants (the holonomic rank of $f$ need not equal
the recurrence order). We nearly misread the order-6 ODE as "CY 5-fold." The
**indicial equation** ($-715\,s^4(s-1)^2$) is what disambiguates: an order-4 MUM
block + an order-2 apparent singularity. Always compute the local exponents
before reading off a Calabi–Yau dimension.

### 13. A Certificate Beats a Guess — Insist on It
We had the order-4 operator verified on 101 terms (overwhelming, but not a
proof). The Maxima **Zeilberger certificate** turns it into a proof for *all*
$n$. The lesson from the original journal — "the finite-vs-infinite bridge is not
formalized" — is now half-closed: the certificate exists; only the Lean re-check
of its finite rational identity remains.

### 14. Instanton Integrality Is a Normalization Trap
Mirror-map ($q_d$) integrality is easy to get right and was integral. But the
**instanton numbers** $n_d$ require the *geometrically correct* Yukawa coupling,
read off the operator — not a guessed $\theta_q^2$. A wrong normalization
produces non-integers with denominators exactly $\sim d^3$, which *looks* like a
refutation but is an artifact. Lesson: report such a result as "normalization
unresolved," never as evidence against CY-ness, and never fudge it to integers.

### 15. Multiple Independent Derivations Are Worth the Cost
The order-4 result is believable precisely because four unrelated methods
(GF($p$) nullspace, $\mathbb{Q}$ reconstruction, `ore_algebra` `guess`, Maxima
`Zeilberger`) agree coefficient-for-coefficient. When a result gates a whole
geometric narrative, redundancy is not waste — it is the evidence.

### 16. Cloud Iterations Have a Budget — Stop When the Science Is Secured
Settling the certificate took several GCP Cloud Build iterations chasing version
incompatibilities. Once the decisive result was triply confirmed, the right call
was to stop iterating on a green `.factor()` and document the blockers, rather
than keep spending on diminishing returns.

## Open work carried forward (snapshot — authoritative list in roadmap.md / todo.md / memory.md)

The lesson behind keeping this list is #7 ("claims drift when building fast"):
record *exactly* what is unfinished so a later session does not re-claim it as
done. As of 2026-06-20 the remaining tasks are:
1. **Lean 4 re-check** of the Zeilberger certificate identity (the only formal
   gap left in the recurrence proof).
2. **Isolate $L_4$** (exhibit $L_6=L_4\cdot L_2$, $L_4$ irreducible) — blocked on
   a version-matched Sage + `ore_algebra`.
3. **Correct CY-3 Yukawa coupling** from $L_4$ → genuine instanton-integrality
   test (the placeholder result is unresolved, not a refutation).
4. **AESZ/van Straten operator-level match** of $L_4$ (novelty + 3-fold ID).
5. **Phase 3 modularity** (gated on $L_4$): rigid fibers → $a_p$ → weight-4
   newform → Beukers/ASD-type supercongruence.
6. **Open conjectures:** $S(p-1)\equiv1\,(p^3)$ and the Lucas property (numeric
   only; the mod-$p$ Apéry-style congruence IS proved + Lean-checked).
7. **Housekeeping:** submit the OEIS draft when reviewed; refresh the v3.0.0
   release PDF to the 9-page v6; AI-hardware kernels remain parked.
