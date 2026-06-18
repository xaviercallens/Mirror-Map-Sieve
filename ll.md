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
The "Callens-ALIX" naming persists in the README despite being removed from the paper. It serves no mathematical purpose and actively undermines credibility with the number theory community. The standard practice is to name sequences after their defining formula or after the first person to submit them to OEIS — and that only happens AFTER the OEIS editor assigns the name.

### 9. The AI Hardware Section Dilutes the Message
A reviewer reading a paper about Calabi-Yau periods will be confused by INT64 GPU attention kernels. These are unrelated to the mathematical contribution. Keep the repository focused on what it does best: rigorous computational number theory.

### 10. Tests Are Not Optional
A mathematics repository without tests is like a theorem without a proof. The recurrence can be verified at 70 points in under 10 seconds. There is no excuse for not having automated tests.
