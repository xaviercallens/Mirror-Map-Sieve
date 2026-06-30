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

## CY-Sieve GPU-phase Lessons (2026-06-21, NVIDIA L4)

### 17. A Positional-Scheme Gate Must Train From Scratch — Not Swap on a Frozen Model
The first §5 quality gate zero-shot-swapped the positional bias into a *frozen*
pretrained GPT-2 (zeroing its learned position embeddings). It is **invalid**:
WikiText-2 perplexity was native 32.5 but ALiBi 1641, sliding-window 2529, and
CY-Sieve ~7180 — i.e. **every** alternative scheme collapsed equally. That measures
"how much does removing the positions the model was trained with hurt," not which
scheme is better, and reporting CY-Sieve numbers from it would have violated the
project's own §7 honesty guards. The correct, ALiBi-paper methodology is to **train
small models from scratch** under each scheme at identical compute and compare
validation perplexity + length extrapolation. Lesson: when the thing under test is
an *inductive bias*, the weights must be allowed to adapt to it.

### 18. An Explicit `[H,L,L]` Attention Bias Disables FlashAttention — Budget For It
Passing a dense additive bias as PyTorch SDPA's `attn_mask` is correct and
necessary to inject the per-head positional bias, but it forces SDPA off its fused
FlashAttention path onto the slower math kernel. Across 7 schemes × 6000 steps the
from-scratch §5 run took multiple hours on an L4 at 100% util — far longer than a
fused-kernel estimate. Lesson: either fold the bias into the kernel (the Triton
path), use a smaller step budget for a first functional result, or budget the wall
clock honestly. Not a bug — a known cost of the apples-to-apples bias injection.

### 19. The Global `GPUS_ALL_REGIONS` Quota Gates Everything
A project can have per-region L4 quota = 1 yet still fail *all* GPU launches
(on-demand and spot) because the separate **global `GPUS_ALL_REGIONS` quota is 0**.
`agora-autoresearch-001` had exactly this; the GPU phase had to move to project
**SocrateAI** (`gen-lang-client-0625573011`), which has both quotas ≥ 1. Lesson:
check the global GPU quota first, not just the per-region accelerator quota.

### 20. An HBM-Traffic Win Is Not Automatically a Latency Win
The CY-Sieve §6 measurement (NVIDIA L4) confirmed the project's central claim —
the on-the-fly positional bias reads **O(L)** bytes of HBM vs **O(L²)** for a
materialized table (**8192× less at L=16384**) — *and at the same time* showed the
current Triton kernel is **~3.7× slower than fused dench SDPA** in wall-clock,
because it is unfused and cuDNN's SDPA is heavily tuned. The two facts coexist: you
can save the memory traffic yet still lose on time until the saving is *fused*
into the attention inner loop. Lesson: report HBM and latency as **separate**
axes (the `tests.md` T6.3 guard exists for exactly this), never let "bandwidth-
optimal" imply "faster," and treat fusion as the work that converts the one into
the other. The honest framing is "memory-traffic win at long context; latency work
remaining," not "faster attention."

### 23. A Short Screen Can Crown an Overfitter — Budget for Generalization, Not Fit
The CY-Sieve autoresearch loop (propose→screen→select) cleanly demonstrated a trap.
At the **screen budget (1200 steps)** the learnable-γ Holonomic-ALiBi schemes
*beat every baseline* (holo_ladder 5.89 vs ALiBi 6.15) — a real, exciting signal.
At the **full budget (6000 steps)** the ranking **inverted**: the same schemes hit
val ppl ~13 vs the baselines' ~4.3, because the setup over-trained (~37 epochs over
a 2 MB corpus) and the *more expressive* learnable bias overfit hardest (train loss
0.42 vs 1.17 — 3× lower — but val 3× worse). Two lessons: (a) **selection on a
short screen preferentially promotes the highest-capacity hypothesis**, which is
exactly the one most prone to overfit at scale — always validate the screen winner
at the target budget before believing it; (b) the intended mechanism backfired
silently — γ was supposed to *flatten* the steep CY slope, but with no
regularization gradient descent pushed it *steeper* (max 0.13→0.21) to memorize
n-grams. Fixes that follow directly: γ-regularization (pull toward flat),
val-based early-stopping, and more data / fewer epochs — i.e. give expressive
positional biases a **generalization** budget, not just a fit budget. (One genuine
survivor: the CY shape extrapolates *flat*, 12.7→13.3 over 512→2048, where
learned-absolute collapses 4.3→20.6 — stable length-extrapolation is real even
when absolute quality is mediocre.)

### 22. The Geometry Sets a Prior, Not the Value — CY-Sieve §5 KILL
The CY-Sieve quality gate returned a clean NEGATIVE result on real WikiText-2
(train-from-scratch): best CY-Sieve 4.65 ppl vs best baseline 4.22 → **+10.15%**,
past the >5% kill threshold; a plain **sliding-window won** (4.99, flat across
2×/4× extrapolation). The seductive error we avoided: the synthetic-corpus
shakedown made CY-Sieve's extrapolation look excellent (ppl~1.0), and reporting
*that* would have been a false positive — the real corpus inverted it. The deeper
lesson: we fixed the long-range slope to logλ=3.762 because that is the *growth
rate of S₂₀*, but there is **no law that the optimal attention slope equals the
sequence's growth rate**. The Calabi–Yau geometry is a principled *prior* for the
bias shape, not the right *value* — pinning the value too steeply is what failed.
A redesign should make the slope learnable (geometry-initialized, à la
learnable-ALiBi) and/or hybridize the exact local window (Tier 1) with a far
gentler tail. Reporting this kill — not burying it — is the project working as
intended: a fast, correct kernel (§4 PASS, §6 8192× HBM) is still a FAILED kernel
if it hurts quality.

### 21. `pip install --no-deps <pkg>` Silently Cripples the Package
Trying to protect the DLVM's pre-installed CUDA torch, we ran
`pip install --no-deps datasets`. Result: `datasets` imported-failed (missing
`multiprocess`, `pandas`), so the §5 gate fell through to its synthetic corpus and
produced a *vacuous* PASS (ppl≈1.0 for every scheme). A second trap followed: a
newer `huggingface_hub` rejects the legacy bare repo id `"wikitext"` (wants
`namespace/name`) — fixed by loading `"Salesforce/wikitext"`. Lessons: (a) install
a library WITH its deps and only pin the one thing you must protect; (b) a
data-loading fallback must **record its source** and the verdict must **self-flag
INVALID** on fallback, or a tooling failure masquerades as a science result; (c)
de-risk the data path with a tiny local run before spending hours of GPU.

## Triton Fused Kernel Parity & Performance Lessons (2026-06-24)

### 24. Triton JIT Unstructured Branch Limitations
Triton JIT compilers translate Python code directly into GPU machine code. They do not support standard Python-like unstructured branch control such as `break` or `continue` inside JIT loops. Implementing causal and sliding-window boundary checks requires reformulating control flow as branch-free or predicated boolean conditions (e.g., `in_bounds`).

### 25. Online Softmax NaN Shielding
When implementing sliding-window attention, blocks that are completely in the far past (beyond `WINDOW_SIZE`) are fully masked out, resulting in attention logits of `-inf`. During block-based online softmax updates, doing subtractive exponentials like `s - m_new` on fully masked blocks results in `-inf - (-inf) = NaN`. We must safely guard and mask `-inf` variables in registers before computing exponential elements.

### 26. Registers-Level ALiBi Execution Yields Massive Gains
Fusing both Learnable-ALiBi distance calculations and dynamic sliding-window pruning inside a single JIT Triton kernel accelerated execution by **85.9%** over PyTorch's native SDPA on a Tesla T4 (2.84 ms vs. 20.15 ms). This completely bypasses the framework-level head-splitting slowdown (which was **-426.6%**) and proves that on-the-fly register-level bias calculation is the optimal path for fused hardware layouts.

## Task-Specific Slope Training (H₁₃) & Intermediate Layer Pruning (H₉) Lessons (2026-06-24, Tesla T4)

### 27. Structure-Driven Slope Adaptation ($H_{13}$)
Programming language syntax contains deeply nested, hierarchical relationships (such as classes, loops, and scope indentations) that require the attention mechanism to maintain robust connections across long relative distances. Our comparative training sweep proved that Code-Trained slopes adapt differently compared to Natural Language (+16.19% shift vs. +14.11% shift), maintaining higher-capacity representations under gradient descent to preserve structural coherence.

### 28. Sub-linear Memory Footprint reduction via Local Intermediate Pruning ($H_9$)
Because intermediate layers specialize in highly localized context relationships (the Inverted Depth Profile), we can restrict their KV-caches to a narrow sliding window ($W = 64$) using our fused Triton kernel without impacting global context representation (which is anchored by Layer 1). Doing so reduces the KV-cache VRAM footprint from **768.00 MB to 34.88 MB (95.5% savings)** at 16k context, providing a clear path to run massive contexts on memory-constrained edge hardware.

### 29. Prefill Attention Acceleration via Register Fusion ($H_9$)
Prefill/context encoding is historically bottlenecked by quadratic attention complexity. By fusing both Learnable-ALiBi distance calculations and sliding-window constraints inside our register-level Triton kernel, we can achieve up to **94.7% faster attention latency** (from 65.68s down to 3.47s) at 16k context, proving that on-the-fly registers-level pruning is extremely efficient for long-context pre-computation.

## Lean 4 Compilation & Environment Lessons (2026-06-30, Tesla T4)

### 30. Subdirectory Cache Isolation
Running `lake exe cache get` at the workspace root does *not* populate the build cache for project subdirectories containing separate Lean packages (such as `lean4_formal_proofs`). Running it directly inside the target package directory ensures that the 8,500+ precompiled Mathlib olean files are fetched and extracted, successfully avoiding building Mathlib from source and saving gigabytes of memory and disk space.

### 31. BigOperators Import and Binder Syntax Changes
Lean 4 and modern Mathlib releases require updating deprecated imports (such as replacing `Mathlib.Algebra.BigOperators.Basic` with `Mathlib.Algebra.BigOperators.Group.Finset.Basic`) and standardizing binder syntax (replacing deprecated `in` binders with `∈` in finset sums). Correcting these syntax and import changes ensures successful, clean compilation of `TelescopingBinomial.lean` and `S20Recurrence.lean`.

### 32. Typeclass Synthesis Stack Overflow on Massive Expressions
Giant bivariate rational polynomials with huge coefficients (e.g., the 21st-degree creative-telescoping certificate `cert_poly`) cause combinatorial typeclass synthesis overhead in Lean 4's elaborator when written directly as standard math operators in `ℚ`. This leads to `maximum recursion depth has been reached` and typeclass synthesis failures for heterogeneous powers (`HPow ℚ`). Large expressions must be structured as scaled, integer-evaluated, or Horner-form helper lemmas to keep arithmetic inside flat structures before division casting.

## Open work carried forward (snapshot — authoritative list in roadmap.md / todo.md / memory.md)

The lesson behind keeping this list is #7 ("claims drift when building fast"):
record *exactly* what is unfinished so a later session does not re-claim it as
done. As of 2026-06-24 the remaining tasks are:
1. **Lean 4 Compilation (Phase 4)**: Reformulate the huge bivariate certificate polynomial (`cert_poly`) into a scaled, denominator-free, or Horner-form helper lemma to bypass Lean 4's typeclass synthesis/recursion limits and complete the proof of the order-4 recurrence (`s20_recurrence_order_4`).
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
   release PDF to the 9-page v6.

