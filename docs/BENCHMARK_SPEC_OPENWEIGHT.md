# Benchmark spec — validating learnable-ALiBi on a real open-weight LLM

A concrete, falsifiable benchmark to test the shipped scheme — **learnable
per-head ALiBi** (`PHASE6_HETERO_POS.md`, paper `learnable_positional_bias.pdf`)
— on a *real, open-weight* model rather than from-scratch toys, and to tie the
result to the energy/CO₂ thesis. Written 2026-06-23; not yet run.

## 0. The validity constraint that picks everything else

> **You cannot bolt learnable-ALiBi onto a frozen RoPE model and call the result a
> test.** Swapping a frozen model's positional scheme is exactly the invalid
> "frozen-model swap" that produced this project's original *vacuous* PASS (every
> scheme collapses equally; see `cy_sieve_quality_gate.py` and the §5 history).

A valid test must either (a) **train the scheme into the weights**, or (b) start
from a model whose bias is *already additive ALiBi*, so that making the slopes
learnable is a **minimal, in-distribution surgical edit** plus a short adaptation.
Most popular open-weight models (Llama, Mistral, Qwen, Gemma, Falcon) are **RoPE**
— off the critical path for a first valid test. This selects ALiBi-native models.

## 1. Models (open-weight, ALiBi-native → the intervention is valid + cheap)

| model | params | ctx | license | role |
|---|---|---|---|---|
| **BLOOM-560m / 1b1** (`bigscience/bloom-1b1`) | 0.56–1.1B | 2048 | RAIL | **first decisive run** — fits one L4/A100 |
| MPT-7B (`mosaicml/mpt-7b`) | 7B | 2048 | Apache-2.0 | scale-up; the canonical ALiBi model, designed to extrapolate |
| (ref.) a RoPE sibling (Pythia/Llama-class) | — | — | — | cross-family baseline only (RoPE + position-interpolation) |

**Why ALiBi-native:** the fixed per-head slopes $a_h = 2^{-8h/H}$ are already in
the architecture. Making them `nn.Parameter` is a few-hundred-scalar edit
($H \times n_{\text{layer}}$), not a positional-family transplant.

## 2. Intervention — learnable-slope continued-pretrain (parameter-efficient)

1. Load the open-weight model; **convert the fixed ALiBi slopes to trainable
   parameters** (initialize *at* the original geometric ladder, so step 0 == the
   shipped model — no quality cliff).
2. Short **continued-pretrain** at the *original* context (≈ a few hundred M
   tokens), rest of the model frozen or LoRA-adapted. Apply the lessons that
   proved essential: **ℓ2 regularization on the slopes + validation
   early-stopping** (a short budget crowns the overfitter — see
   `AUTORESEARCH_HYPOTHESES.md`).
3. Cost target: GPU-**hours**, not days. BLOOM-1b1 @ a few hundred M tokens fits a
   single-L4/A100 day on the existing launch tooling (`gcp_startup_*.sh`).

## 3. The benchmark suite — a train-short / serve-long battery

Replace WikiText-2-from-scratch with benchmarks that actually probe the thesis
(quality *beyond* the training length):

| benchmark | measures | why it is the right one |
|---|---|---|
| **RULER** (NVIDIA 2024) | 13 long-context tasks, lengths 4K→128K | modern standard; directly probes serving *beyond* train length — the energy thesis lives here |
| **PG-19 / proof-pile sliding-window ppl** | LM quality as context grows | the ALiBi paper's *own* extrapolation metric → apples-to-apples vs fixed ALiBi |
| **Passkey / needle-in-a-haystack** | retrieval at depth | cheap sanity that extrapolation isn't low-ppl-with-no-usable-signal |

## 4. Decisive comparison (base model fixed; only the positional treatment varies)

1. **Frozen fixed-ALiBi** — the shipped model, as released (baseline).
2. **Learnable-ALiBi** — our scheme, after the §2 continued-pretrain.
3. **RoPE + position-interpolation** — cross-family reference (needs a RoPE
   sibling; report separately, it is not an apples-to-apples arm).

Pre-commit the gate and the extrapolation protocol *before* running (as in every
prior phase).

## 5. Primary metric — the one that ties to energy

> **Usable-context multiple per unit of adaptation compute:** the largest $kL$ at
> which quality stays within a fixed degradation band (e.g. ≤X% ppl rise, or ≥Y%
> RULER score retained), divided by the adaptation compute spent to get there.

This operationalizes the paper's roadmap item #2: *does making slopes learnable +
a cheap continued-pretrain buy the same context extension as a full
position-interpolation pass, for less energy?* Report the adaptation cost in
**kWh and CO₂e (measured)**, or state explicitly that no saving was found. The
mechanism is free at inference ($H$ scalars fused into FlashAttention), so any
extrapolation benefit carries ~zero per-token cost — that half is defensible; the
open question is whether it *avoids* an extension fine-tune at fleet scale.

## 6. Kill criteria (pre-committed)

- **KILL** if learnable-ALiBi does not improve the usable-context multiple over
  frozen fixed-ALiBi (the whole point is better extrapolation per unit compute).
- **KILL the energy claim** if the measured adaptation cost is not below a
  published position-interpolation extension pass for equivalent usable context.
- **NULL (report, don't ship a story)** if it matches fixed-ALiBi within noise —
  consistent with "adaptability helps, but the fixed ladder was already good."

## 7. Feasibility & alternatives

- **Scaffolding exists:** `4_ai_hardware_attention/openweight_learnable_alibi.py`
  implements this spec — it unfreezes BLOOM's per-head ALiBi slopes (global
  monkey-patch of `build_alibi_tensor` → a learnable `nn.Parameter` initialized at
  the released ladder, with a **step-0 bit-for-bit equivalence assert**), reuses
  `cy_sieve_quality_gate.load_corpus` + the hetero-pos train loop (slopes-only,
  γ-L2 + val early-stop), and reports the serve-long extrapolation ppl +
  usable-context multiple. CPU smoke (`--preset smoke`, random tiny BLOOM) passes
  end-to-end; GPU run: `--preset full --model bigscience/bloom-560m`. RULER /
  passkey / measured-energy harnesses are stubbed as TODOs in the script header.
- **BLOOM-560m/1b1 first** (cheapest *valid* test on a real open-weight model;
  reuses the L4 launch pattern, see `vm-benchmarking-state`). **MPT-7B** is the
  headline-credible scale-up once it is clean.
- **From-scratch at mid-scale** (paper roadmap #1): cleanest, family-neutral, but
  ~10× compute and no real-model lineage — weaker for the "applies to deployed
  LLMs" story.
- **Cross-family RoPE→learnable-ALiBi transplant** (Llama/Mistral): most impactful
  if it works, but heavy surgery (changing the positional family + enough
  continued-pretrain to recover) — **high risk; defer** until the ALiBi-native
  result confirms the mechanism.

## 8. One-line conclusion

> The first relevant, *valid* test is **BLOOM-1b1 with learnable ALiBi slopes,
> continued-pretrained briefly, evaluated on RULER + PG-19 sliding-window vs the
> frozen fixed-ALiBi release** — measuring usable-context-multiple per unit of
> adaptation compute, with a measured kWh/CO₂e accounting. It is the cheapest
> route that is both faithful to a deployed model and decisive for the energy
> thesis. See `learnable_positional_bias.pdf` §7 and `PHASE6_HETERO_POS.md`.
