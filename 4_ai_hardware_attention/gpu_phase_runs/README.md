# CY-Sieve GPU-phase runs

Archived raw artifacts from real GPU runs of `run_gpu_phase.py` (tests.md §4/§5/§6).

## run_20260621_l4 — NVIDIA L4, project SocrateAI (first end-to-end run)

**Honest status: partial / shakedown run.** It exercised the whole pipeline on a
real L4 and surfaced three fixable issues (all addressed in the next commit). Read
the numbers with the caveats below — do **not** cite the §5 verdict.

### §4 — Triton↔reference parity: NOT RUN (tooling gap, not a parity failure)
`pytest` is absent from the DLVM image and the startup script didn't install it
(`No module named pytest`), so the parity test never executed. Reported as FAIL by
the orchestrator (correctly conservative). Kernel correctness on the L4 is
therefore **untested**, not refuted. Fix: install pytest in `gcp_startup.sh` +
on-demand in `run_gpu_phase.py`.

### §5 — quality gate: INVALID (synthetic corpus)
`datasets` could not load WikiText-2 (missing `xxhash`, old `requests`), so the
gate silently fell back to its tiny repeating synthetic corpus. Every scheme
memorized it → validation perplexity ≈ 1.0, and the "+/−0.01%" PASS is
**scientifically vacuous**. Fix: install `xxhash` + `requests>=2.32.2`; the gate
now records `corpus_source` and stamps the verdict INVALID on fallback.

**One real signal survived anyway — length extrapolation (ppl by eval context):**

| scheme | @512 (train) | @1024 (2×) | @2048 (4×) |
|---|---|---|---|
| learned-absolute | 1.007 | **2495** | **251818** |
| ALiBi | 1.008 | 1.004 | 1.002 |
| sliding-window | 1.006 | 1.003 | 1.002 |
| **CY-Sieve τ-ladder** | 1.006 | 1.003 | 1.002 |
| CY-Sieve τ=20 | 1.006 | 1.003 | 1.002 |
| CY-Sieve τ=128 | 1.006 | 1.003 | 1.002 |
| CY-Sieve τ=512 | 1.007 | 2.73 | 6.27 |

Even on a trivial corpus this reproduces the textbook result — **learned-absolute
positions blow up past the training length** — while CY-Sieve (τ-ladder, τ≤128)
extrapolates as cleanly as ALiBi/sliding, and an over-shallow τ=512 degrades.
Directionally consistent with the per-head-τ design, but NOT a quality claim;
the real gate needs the WikiText run.

### §6 — performance: real data (then OOM at the last size)
Ran 1K–16K, crashed materializing the 32768² bias table (4 GiB alloc, fragmented
VRAM). Numbers that landed (NVIDIA L4, D=64, fp16, τ=128):

| L | CY-Sieve (ms) | dense SDPA (ms) | table-bias SDPA (ms) | CY bias HBM | table bias HBM |
|---|---|---|---|---|---|
| 1024 | 0.056 | 0.054 | 0.060 | 4 KB | 2 MB |
| 2048 | 0.104 | 0.054 | 0.117 | 8 KB | 8 MB |
| 4096 | 0.259 | 0.060 | 0.270 | 16 KB | 32 MB |
| 8192 | 1.166 | 0.316 | 0.805 | 32 KB | 128 MB |
| 16384 | 3.969 | 1.063 | 3.862 | 64 KB | 512 MB |

**Reading:**
- **Bias-path HBM (the core claim) — confirmed.** CY-Sieve reads O(L) bytes vs
  O(L²) for a materialized table: **8192× less at L=16384** (64 KB vs 512 MB),
  and the gap widens with L. This is the memory-bandwidth thesis, measured.
- **Latency — honest mixed result.** The current (unfused) Triton kernel is
  *slower* than fused dense SDPA (3.97 vs 1.06 ms at 16K) and roughly *matches* the
  table-bias SDPA. So the kernel demonstrates the HBM reduction but is **not yet a
  latency win** — reported per T6.3 rather than cherry-picked. Fusing the bias into
  the FlashAttention inner loop is the optimization that would convert the HBM
  saving into wall-clock.

Fix for the OOM: tighter VRAM budget for the table baseline + skip-with-notice on
sizes that don't fit (cap effectively ~16K on a 24 GB L4).
