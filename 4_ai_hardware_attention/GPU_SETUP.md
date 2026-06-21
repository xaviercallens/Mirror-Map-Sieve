# CY-Sieve — GPU phase setup

The CPU work (reference, numerics, online-softmax parity, retrieval proxy) is
complete and runs anywhere. This note is the runbook for the **GPU phase**
(Stage B GPU half + Stage C quality gate) when CUDA hardware is available.

## What already works on CPU (the parity oracle)
- `cy_sieve_reference.py` — tiers 1/2/3, per-head τ ladder, recurrence-mod-p
  generator. Tests: `test_cy_sieve.py` (39).
- `cy_sieve_attention.py` — dense SDPA + **FlashAttention online-softmax** with
  the CY-Sieve bias; matches dense to ~3e-16. Tests: `test_cy_sieve_attention.py`
  (13, incl. the §5 retrieval proxy).
- `cy_sieve_triton.py` — the Triton kernel (GPU-guarded; imports fine on CPU).
- `test_cy_sieve_triton.py` — Triton↔reference parity; **auto-skips without CUDA**.

## On the GPU box
```bash
pip install -r 4_ai_hardware_attention/requirements-gpu.txt   # torch+triton+transformers
# 1) kernel smoke test
python 4_ai_hardware_attention/cy_sieve_triton.py
# 2) Stage B GPU half — Triton vs CPU reference parity (tests.md §4 T4.1)
pytest 4_ai_hardware_attention/test_cy_sieve_triton.py -v
```
`test_cy_sieve_triton.py` compares the Triton kernel against
`cy_sieve_attention.flash_sdpa_with_bias` (the CPU oracle) within FP16/BF16
tolerance (rel. err < 2⁻⁸).

## One-shot GPU phase entrypoint
```bash
pip install -r 4_ai_hardware_attention/requirements-gpu.txt
python 4_ai_hardware_attention/run_gpu_phase.py            # §4 + §5 + §6, one JSON
python 4_ai_hardware_attention/run_gpu_phase.py --quick    # fast functional check
```
`gcp_startup.sh` (v3) runs exactly this on an L4 and uploads to
`gs://agora-autoresearch-001-benchmark-results/cy_sieve/`, then self-terminates.

## Stage C — the quality gate (tests.md §5, the decisive test)
Implemented in `cy_sieve_quality_gate.py`. **Methodology note (important):** an
earlier attempt zero-shot-swapped the positional scheme on a *frozen* pretrained
GPT-2. That is **invalid** — it was verified to collapse *every* scheme equally
(native ppl 32.5 vs ALiBi 1641, sliding 2529, CY-Sieve ~7180 on WikiText-2),
because GPT-2 was trained with learned absolute positions; the result measures
train/test mismatch, not the scheme. Reporting it would break the §7 honesty
guards.

The gate therefore uses the ALiBi-paper methodology — **train small GPTs FROM
SCRATCH**, identical arch/data/steps/compute, one per scheme:
1. `learned` (control), `alibi`, `sliding-window`, `cy_sieve` (per-head τ ladder
   + a single-τ sweep). The CY-Sieve bias is the only thing that differs.
2. **Validation perplexity** at the training context **and length-extrapolation**
   perplexity at 2×/4× the training context.
3. (NIAH at 4K/16K/64K is the natural follow-up once the trained checkpoints
   exist; the perplexity-extrapolation curve is the first decisive signal.)

**PASS:** CY-Sieve within +1% of the best baseline (ideally lower). **Kill
criterion (do not soften):** if perplexity regresses > 5% vs the best baseline,
or extrapolation collapses, report a **negative result** — do not ship.

## Known constraints surfaced on CPU (carry into the GPU design)
- **τ is mandatory.** Native τ=1 underflows FP16 by d≈6 → a ~6-token window.
  Use the per-head ALiBi-style ladder (`alibi_style_tau_ladder`); sweep it.
- **Tier 2 (mod-p router) is disabled** — the proposed keep-rule keeps only
  ~0.8% of distances (nearest 125–226). Do not enable without a new rule that
  beats sliding-window of equal density.
- **SRAM recurrence needs a reseed table.** The order-4 leading coefficient
  P₄(n) vanishes mod p at ~p/80 points; the on-the-fly GF(p) generator must
  carry the true values there (see `recurrence_vanishing_points`).
- **Tier-1 fixed-point tail is coarse** (table[13]=2). Prefer the exact integer
  in-window; the fixed-point table is the integer-ALU artifact.
