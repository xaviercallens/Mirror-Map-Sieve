#!/usr/bin/env python3
"""
publish_cy_sieve_results.py — publish the HONEST CY-Sieve GPU-phase results to
HuggingFace: a dataset repo (per-scheme perplexities, perf/HBM, raw run JSON+log,
findings writeup) and a corrected model-repo README that reports the §5 KILL
negative result + the §6 memory-vs-latency tradeoff.

Supersedes publish_to_hf.py, whose "zero overhead" / quality-win claims were
falsified by the 2026-06-22 L4 run (run3). Uses HF_TOKEN from the environment.

    python publish_cy_sieve_results.py            # publish
    python publish_cy_sieve_results.py --dry-run  # show what would happen
"""
import argparse, os, sys
from huggingface_hub import HfApi

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "4_ai_hardware_attention", "gpu_phase_runs")
DS = os.path.join(RUNS, "dataset")
PHASE3 = os.path.join(HERE, "docs", "PHASE3_CYSIEVE_GPU_FINDINGS.md")

DATASET_REPO = "callensxavier/cy-sieve-attention-benchmark"
MODEL_REPO = "callensxavier/s20-attention-kernel"

# Honest model-repo README (overwrites the misleading "zero overhead" version).
MODEL_README = r"""---
license: mit
tags:
- attention
- positional-encoding
- efficient-attention
- number-theory
- calabi-yau
- negative-result
datasets:
- callensxavier/cy-sieve-attention-benchmark
---

# CY-Sieve Attention Kernel — a falsifiable experiment (NEGATIVE result)

A positional-attention bias derived from the weight-5 Apéry-like binomial sum

$$S_{20}(n) = \sum_{k=0}^{n} \binom{n}{k}^4 \binom{n+k}{k}$$

whose holonomic structure is a Calabi–Yau **3-fold** period (an order-4 MUM block;
the geometry fixes the long-range decay slope $\log\lambda = 3.762$ and curvature
$\beta = 2$). The engineering bet: generate the positional bias *on the fly* from
the order-4 recurrence, costing **O(L)** HBM instead of an **O(L²)** table.

> **Code:** [GitHub — Mirror-Map-Sieve](https://github.com/xaviercallens/Mirror-Map-Sieve)
> · **Math paper:** [Zenodo 10.5281/zenodo.20747943](https://doi.org/10.5281/zenodo.20747943)
> · **Benchmark data:** [callensxavier/cy-sieve-attention-benchmark](https://huggingface.co/datasets/callensxavier/cy-sieve-attention-benchmark)

## ⚠️ Honest result (2026-06-22, NVIDIA L4): the quality gate KILLED it

This card **corrects** an earlier version that claimed "zero overhead" and implied
a win. Those numbers came from an invalid method (monkey-patching the bias into a
*frozen* pretrained model, which collapses every alternative scheme equally). The
correct test — **training small GPTs from scratch**, one per positional scheme, on
real WikiText-2 — gives:

| scheme | ppl @512 (train) | @1024 (2×) | @2048 (4×) |
|---|---|---|---|
| **learned-absolute** | **4.22** | 12.10 | 20.82 |
| ALiBi | 10.74 | 11.73 | 11.35 |
| **sliding-window** | **4.99** | **5.07** | **5.03** |
| CY-Sieve τ-ladder | 11.33 | 12.31 | 12.05 |
| CY-Sieve τ=128 | 6.80 | 7.12 | 7.00 |
| CY-Sieve τ=512 | 4.65 | 6.08 | 10.62 |

**Verdict: KILL (+10.15%).** Best CY-Sieve (4.65) vs best baseline (4.22) exceeds
the pre-committed >5% kill threshold; a plain **sliding window won outright**. The
geometry-fixed slope is too steep for a drop-in positional scheme.

## What *did* hold up

- **§4 kernel correctness — PASS.** The Triton kernel matches the NumPy reference
  within FP16 tolerance (4/4 tests).
- **§6 memory claim — confirmed.** The on-the-fly bias reads **O(L)** bytes of HBM
  vs **O(L²)** for a materialized table (**8192× less at L=16384**). *But* the
  current unfused kernel is **~4–6× slower** than fused dense SDPA — a
  memory-traffic win, **not** a latency win. Per the project's reporting rule,
  with the quality gate failing, these numbers are **not** a contribution.

## Why publish a negative result?

Because a fast, correct kernel that degrades model quality is a *failed* kernel,
and saying so is the point. The Calabi–Yau geometry is a sound **prior** for the
bias shape, not the right **value** — pinning the attention slope to the
sequence's growth rate was the mistake. Redesign directions (learnable
geometry-initialized slope; exact-local-window + gentle-tail hybrid; β=2 ablation)
are in the [findings writeup](https://github.com/xaviercallens/Mirror-Map-Sieve/blob/main/docs/PHASE3_CYSIEVE_GPU_FINDINGS.md).

## Reproduce

```bash
git clone https://github.com/xaviercallens/Mirror-Map-Sieve.git
cd Mirror-Map-Sieve
pip install -r 4_ai_hardware_attention/requirements-gpu.txt
python 4_ai_hardware_attention/run_gpu_phase.py   # §4 parity + §5 quality + §6 perf
```

## Citation

```bibtex
@misc{callens2026cysieve,
  author = {Callens, Xavier},
  title  = {CY-Sieve Attention: a Calabi--Yau positional bias and its negative quality result},
  year   = {2026},
  url    = {https://huggingface.co/callensxavier/s20-attention-kernel},
  doi    = {10.5281/zenodo.20747943}
}
```
"""

DATASET_FILES = [
    (os.path.join(DS, "quality_perplexity.csv"), "quality_perplexity.csv"),
    (os.path.join(DS, "perf_hbm.csv"), "perf_hbm.csv"),
    (os.path.join(DS, "README.md"), "README.md"),
    (os.path.join(RUNS, "run3_20260622_l4_quality.json"), "raw/run3_quality.json"),
    (os.path.join(RUNS, "run3_20260622_l4_perf.json"), "raw/run3_perf.json"),
    (os.path.join(RUNS, "run3_20260622_l4_gpu_phase.json"), "raw/run3_gpu_phase.json"),
    (os.path.join(RUNS, "run3_20260622_l4.log"), "raw/run3.log"),
    (PHASE3, "PHASE3_CYSIEVE_GPU_FINDINGS.md"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not token:
        sys.exit("HF_TOKEN not set in environment.")

    missing = [src for src, _ in DATASET_FILES if not os.path.exists(src)]
    if missing:
        sys.exit("Missing artifacts:\n  " + "\n  ".join(missing))

    if args.dry_run:
        print(f"[dry-run] dataset repo: {DATASET_REPO}")
        for src, dst in DATASET_FILES:
            print(f"  + {dst:35s} <- {os.path.relpath(src, HERE)}")
        print(f"[dry-run] model repo README rewrite: {MODEL_REPO}")
        return

    api = HfApi(token=token)

    # 1) Dataset repo
    print(f"Creating/updating dataset repo {DATASET_REPO} …")
    api.create_repo(repo_id=DATASET_REPO, repo_type="dataset", exist_ok=True)
    for src, dst in DATASET_FILES:
        print(f"  uploading {dst}")
        api.upload_file(path_or_fileobj=src, path_in_repo=dst,
                        repo_id=DATASET_REPO, repo_type="dataset")
    print(f"✅ dataset: https://huggingface.co/datasets/{DATASET_REPO}")

    # 2) Corrected model-repo README
    print(f"Rewriting model README {MODEL_REPO} …")
    api.create_repo(repo_id=MODEL_REPO, repo_type="model", exist_ok=True)
    api.upload_file(path_or_fileobj=MODEL_README.encode(), path_in_repo="README.md",
                    repo_id=MODEL_REPO, repo_type="model")
    print(f"✅ model: https://huggingface.co/{MODEL_REPO}")


if __name__ == "__main__":
    main()
