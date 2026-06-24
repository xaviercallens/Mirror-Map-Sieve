#!/usr/bin/env python3
"""
dense_extrapolation_gate.py — the PURE DENSE EXTRAPOLATION GATE (Phase 2.2).

PURPOSE (the decisive test of learnable-ALiBi's positional capability):
  Phases 4-6 selected learnable per-head ALiBi by elimination (paper
  learnable_positional_bias.pdf). The toy results train at ctx 512 and extrapolate
  to 4096. This gate raises the bar to a REAL long-document regime: zero-shot dense
  perplexity at 4k -> 32k tokens, with EVERY token able to attend to every prior
  token (no sliding-window, no eviction, no position-interpolation). It answers one
  question unambiguously:

    Does the model carry quality out to 8x its training length using ONLY the
    learned per-head slopes a_h?  (graceful curve = SUCCESS; spike at 4x/8x = the
    learned-absolute trap, slopes overfit the training length.)

PROTOCOL (as specified — do not weaken any of these):
  * STRICTLY ZERO-SHOT: evaluate the checkpoint exactly as frozen. NO
    position-interpolation, NO RoPE-scaling, NO fine-tuning pass here.
  * NO FALLBACKS: sliding-window attention MUST be disabled; full causal dense
    attention at every length. We assert the config has no sliding_window set.
  * FLASHATTENTION MANDATORY for memory: dense 32k on a 7B OOMs naively; the SDPA /
    FA-2 backend makes attention O(L) memory so pure-dense 32k fits an 80GB card.
    (FA-2 changes the kernel's memory pattern, NOT the math: it is still exact dense
    attention — every token attends to all previous tokens. This is the whole point.)
  * MEASUREMENT: validation perplexity at L in {4096, 8192, 16384, 32768}
    (1x/2x/4x/8x of a 4096 training length) on a held-out GENUINE long-document
    corpus (PG-19 by default; --dataset for LongBench/proof-pile).

ENERGY (ties the result to the project's CO2/datacenter thesis):
  We sample NVML power during each length's eval and integrate to Joules -> kWh ->
  CO2e (configurable grid intensity). This is a MEASURED inference-energy-vs-context
  curve, the honest evidence the paper's §5 said was missing. It is NOT yet the
  "avoided position-interpolation pass" number — that needs the training-side
  measurement (separate harness) — and we say so in the output.

VERDICT:
  SUCCESS  : ppl flat or improving 1x->8x (within --success-band, default 15%).
  FAILURE  : ppl spikes at 4x or 8x beyond the band (learned-absolute trap).
  Reported per-model; designed to run a learnable-ALiBi checkpoint (treatment) and
  a stock fixed-ALiBi model e.g. MPT-7B (control) on the IDENTICAL protocol.

CPU smoke:  python dense_extrapolation_gate.py --smoke
H100/A100:  python dense_extrapolation_gate.py --model mosaicml/mpt-7b \
              --lengths 4096 8192 16384 32768 --dataset pg19
Author: SocrateAI Lab (X. Callens) + Claude. MIT.
"""
from __future__ import annotations
import argparse, json, math, os, sys, threading, time

try:
    import certifi
    os.environ["SSL_CERT_FILE"] = certifi.where()
except Exception:
    pass

import torch
import torch.nn.functional as F


# ---------------------------------------------------------------------------
# NVML power sampler -> energy (Joules / kWh / CO2e). Runs in a background thread
# during each eval; integrates instantaneous power over wall-clock time.
# ---------------------------------------------------------------------------

class PowerSampler:
    def __init__(self, gpu_index=0, period_s=0.2):
        self.period = period_s; self.idx = gpu_index
        self._stop = threading.Event(); self._samples = []; self._t = None
        self._h = None
        try:
            import pynvml
            pynvml.nvmlInit()
            self._h = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
            self._pynvml = pynvml
        except Exception:
            self._pynvml = None        # graceful: report energy=None if no NVML

    def _loop(self):
        while not self._stop.is_set():
            try:
                w = self._pynvml.nvmlDeviceGetPowerUsage(self._h) / 1000.0  # mW->W
                self._samples.append((time.perf_counter(), w))
            except Exception:
                pass
            time.sleep(self.period)

    def __enter__(self):
        self._samples.clear(); self._stop.clear()
        if self._pynvml is not None:
            self._t = threading.Thread(target=self._loop, daemon=True); self._t.start()
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *a):
        self._wall = time.perf_counter() - self._t0
        self._stop.set()
        if self._t is not None:
            self._t.join(timeout=2.0)

    def joules(self):
        if len(self._samples) < 2:
            return None
        e = 0.0
        for (t0, w0), (t1, w1) in zip(self._samples, self._samples[1:]):
            e += 0.5 * (w0 + w1) * (t1 - t0)      # trapezoidal integration
        return e

    def avg_watts(self):
        return (sum(w for _, w in self._samples) / len(self._samples)) if self._samples else None


# ---------------------------------------------------------------------------
# Corpus: a genuine long-document held-out set, concatenated to one token stream.
# PG-19 (books) by default; --dataset lets you point at proof-pile / LongBench.
# ---------------------------------------------------------------------------

def load_long_corpus(tokenizer, dataset, min_tokens, smoke=False):
    if smoke:
        text = ("In the long afternoon of the eighteenth century the river moved "
                "slowly past the mill. ") * 4000
        ids = tokenizer(text, return_tensors="pt")["input_ids"][0]
        return ids, "SMOKE-SYNTHETIC"
    from datasets import load_dataset
    specs = {
        "pg19":      ("pg19", None, "test", "text"),
        "proofpile": ("hoskinson-center/proof-pile", None, "test", "text"),
        "longbench": ("THUDM/LongBench", "narrativeqa", "test", "context"),
    }
    name, cfg, split, col = specs.get(dataset, ("pg19", None, "test", "text"))
    ds = load_dataset(name, cfg, split=split, streaming=True)
    chunks, ntok = [], 0
    for row in ds:
        t = row.get(col) or ""
        if not t.strip():
            continue
        ids = tokenizer(t, return_tensors="pt")["input_ids"][0]
        chunks.append(ids); ntok += ids.numel()
        if ntok >= min_tokens:
            break
    if not chunks:
        raise RuntimeError(f"no text from dataset {dataset}")
    return torch.cat(chunks), f"{name}:{split}"


# ---------------------------------------------------------------------------
# Pure-dense perplexity at a single sequence length. NON-OVERLAPPING windows so
# every reported token is scored exactly once; full causal mask (dense).
# ---------------------------------------------------------------------------

@torch.no_grad()
def dense_ppl(model, ids, L, device, max_windows, dtype):
    model.eval()
    n = ids.numel() // L
    if n == 0:
        return None, 0
    n = min(n, max_windows)
    tot_nll, tot_tok = 0.0, 0
    for w in range(n):
        seq = ids[w * L:(w + 1) * L].unsqueeze(0).to(device)
        with torch.autocast(device_type="cuda" if device == "cuda" else "cpu",
                            dtype=dtype, enabled=(device == "cuda")):
            out = model(input_ids=seq)
            logits = out.logits[:, :-1, :]
            tgt = seq[:, 1:]
            nll = F.cross_entropy(logits.reshape(-1, logits.size(-1)),
                                  tgt.reshape(-1), reduction="sum")
        if math.isfinite(nll.item()):
            tot_nll += nll.item(); tot_tok += tgt.numel()
    if tot_tok == 0:
        return None, 0
    return math.exp(tot_nll / tot_tok), n


def assert_pure_dense(model):
    """Fail loudly if the model would silently use sliding-window / non-dense attn
    — the protocol forbids fallbacks. Returns the attn impl actually in force."""
    cfg = model.config
    sw = getattr(cfg, "sliding_window", None)
    if sw not in (None, 0):
        raise RuntimeError(
            f"sliding_window={sw} is set — pure-dense gate forbids SWA. "
            f"Disable it (cfg.sliding_window=None) before running.")
    impl = getattr(cfg, "_attn_implementation", "eager")
    return impl


def _apply_learnable_slopes(slopes_file):
    """Re-apply trained learnable-ALiBi slopes from a checkpoint's slopes.json.
    HF's build_alibi_tensor uses the FIXED geometric ladder, so a learnable-ALiBi
    checkpoint must have its learned slopes re-installed for a faithful eval — else
    we would silently gate the FIXED scheme. Monkey-patches build_alibi_tensor."""
    with open(slopes_file) as f:
        meta = json.load(f)
    slopes = torch.tensor(meta["slopes"], dtype=torch.float32)
    import transformers.models.bloom.modeling_bloom as bloom_mod

    def fixed_from_file_build(attention_mask, n_heads, dtype):
        batch, seq = attention_mask.shape
        s = slopes.to(attention_mask.device)
        arange = ((attention_mask.cumsum(dim=-1) - 1) * attention_mask)[:, None, :]
        alibi = s[..., None] * arange
        return alibi.reshape(batch * n_heads, 1, seq).to(dtype)

    bloom_mod.build_alibi_tensor = fixed_from_file_build
    print(f"  [slopes] re-applied {len(meta['slopes'])} learned slopes "
          f"(mode={meta.get('mode')}, [0,-1]={meta['slopes'][0]:.4f},{meta['slopes'][-1]:.4f})")
    return meta


def run_model(model_id, ids, lengths, device, args, slopes_file=None):
    from transformers import AutoModelForCausalLM
    dtype = torch.float16 if args.fp16 else torch.bfloat16
    slopes_meta = None
    # A learnable-ALiBi checkpoint stores its trained slopes in slopes.json; re-apply
    # them BEFORE loading the model so the gate tests the TRAINED scheme, not fixed.
    sf = slopes_file or (os.path.join(model_id, "slopes.json")
                         if os.path.isdir(model_id) and
                         os.path.exists(os.path.join(model_id, "slopes.json")) else None)
    if sf:
        slopes_meta = _apply_learnable_slopes(sf)
    # FlashAttention/SDPA backend = O(L) memory, EXACT dense attention (not sparse).
    model = AutoModelForCausalLM.from_pretrained(
        model_id, torch_dtype=dtype if device == "cuda" else torch.float32,
        attn_implementation=("sdpa" if not args.flash2 else "flash_attention_2"),
    ).to(device)
    # NO position-interpolation / RoPE-scaling: scrub any scaling config (zero-shot).
    if getattr(model.config, "rope_scaling", None):
        print(f"  [protocol] clearing rope_scaling={model.config.rope_scaling} (zero-shot)")
        model.config.rope_scaling = None
    impl = assert_pure_dense(model)
    eval_dtype = torch.float16 if args.fp16 else torch.bfloat16
    results, energy = {}, {}
    for L in lengths:
        try:
            sampler = PowerSampler(args.gpu)
            with sampler:
                ppl, nwin = dense_ppl(model, ids, L, device, args.max_windows, eval_dtype)
            j = sampler.joules()
            results[str(L)] = round(ppl, 4) if ppl else None
            energy[str(L)] = {
                "joules": round(j, 1) if j else None,
                "avg_watts": round(sampler.avg_watts(), 1) if sampler.avg_watts() else None,
                "wall_s": round(sampler._wall, 1),
                "windows": nwin,
                "kwh": round(j / 3.6e6, 6) if j else None,
                "kwh_per_1k_tok": round((j / 3.6e6) / max(nwin * L / 1000, 1), 8) if j else None,
                "co2e_g": round((j / 3.6e6) * args.grid_g_per_kwh, 3) if j else None,
            }
            print(f"  L={L:>6}: ppl={results[str(L)]}  windows={nwin}  "
                  f"E={energy[str(L)]['joules']}J  avgW={energy[str(L)]['avg_watts']}  "
                  f"CO2e={energy[str(L)]['co2e_g']}g")
        except torch.cuda.OutOfMemoryError:
            results[str(L)] = "OOM"; energy[str(L)] = None
            print(f"  L={L:>6}: OOM (need a bigger card or FA-2)")
            torch.cuda.empty_cache()
        except Exception as e:
            results[str(L)] = None; energy[str(L)] = {"error": str(e)}
            print(f"  L={L:>6}: ERROR {e}")
    if device == "cuda":
        del model; torch.cuda.empty_cache()
    return {"model": model_id, "attn_impl": impl, "ppl": results, "energy": energy,
            "scheme": (slopes_meta or {}).get("mode", "as-released-fixed-alibi"),
            "applied_slopes": (slopes_meta or {}).get("slopes")}


def verdict(ppl, lengths, band):
    """SUCCESS if no length's ppl exceeds (1+band) * the 1x ppl; else FAILURE with
    the first offending length (the learned-absolute trap)."""
    base = ppl.get(str(lengths[0]))
    if not isinstance(base, (int, float)):
        return {"status": "INCONCLUSIVE", "reason": "no 1x baseline ppl"}
    worst_mult, worst_L = 1.0, lengths[0]
    for L in lengths[1:]:
        v = ppl.get(str(L))
        if isinstance(v, (int, float)):
            m = v / base
            if m > worst_mult:
                worst_mult, worst_L = m, L
    ok = worst_mult <= 1 + band
    return {"status": "SUCCESS (graceful extrapolation)" if ok else "FAILURE (learned-absolute trap)",
            "base_ppl": base, "worst_ratio": round(worst_mult, 3),
            "worst_length": worst_L, "band": band}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None, help="checkpoint to gate (treatment or control)")
    ap.add_argument("--control", default=None, help="optional second model on the same protocol")
    ap.add_argument("--slopes-file", default=None,
                    help="path/gs to slopes.json for --model (learnable-ALiBi checkpoint); "
                         "auto-detected if --model is a dir containing slopes.json")
    ap.add_argument("--control-slopes", default=None, help="slopes.json for --control")
    ap.add_argument("--lengths", type=int, nargs="+", default=[4096, 8192, 16384, 32768])
    ap.add_argument("--dataset", default="pg19", choices=["pg19", "proofpile", "longbench"])
    ap.add_argument("--max-windows", type=int, default=16, help="non-overlapping windows per length")
    ap.add_argument("--success-band", type=float, default=0.15, help="max allowed ppl rise vs 1x")
    ap.add_argument("--grid-g-per-kwh", type=float, default=400.0, help="gCO2e/kWh grid intensity")
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--fp16", action="store_true", help="fp16 instead of bf16")
    ap.add_argument("--flash2", action="store_true", help="force flash_attention_2 impl (needs flash-attn)")
    ap.add_argument("--smoke", action="store_true", help="tiny CPU dry-run (distilgpt2, short lengths)")
    ap.add_argument("--output", default="dense_extrapolation_results.json")
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if args.smoke:
        args.model = args.model or "distilgpt2"
        args.lengths = [128, 256, 512, 1024]   # distilgpt2 max is 1024
        args.max_windows = 2
    if not args.model:
        sys.exit("--model required (or --smoke)")

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(args.model)
    min_tok = max(args.lengths) * args.max_windows + max(args.lengths)
    ids, src = load_long_corpus(tok, args.dataset, min_tok, smoke=args.smoke)
    print(f"DENSE EXTRAPOLATION GATE | corpus={src} ({ids.numel()} tok) | "
          f"lengths={args.lengths} | device={device} | band=±{args.success_band:.0%}\n")
    if src == "SMOKE-SYNTHETIC":
        print("  [smoke] synthetic corpus — plumbing only, ppl not meaningful.\n")

    out = {"corpus": src, "args": vars(args), "models": []}
    for mid, sf in [(args.model, args.slopes_file), (args.control, args.control_slopes)]:
        if not mid:
            continue
        print(f"== {mid} ==")
        r = run_model(mid, ids, args.lengths, device, args, slopes_file=sf)
        r["verdict"] = verdict(r["ppl"], args.lengths, args.success_band)
        print(f"  VERDICT: {r['verdict']['status']}  "
              f"(worst {r['verdict'].get('worst_ratio')}x @ L={r['verdict'].get('worst_length')})\n")
        out["models"].append(r)

    out["note"] = ("Energy here is INFERENCE energy vs context length (measured, NVML). "
                   "The 'avoided position-interpolation pass' energy is a TRAINING-side "
                   "number measured by a separate harness — not claimed here.")
    json.dump(out, open(args.output, "w"), indent=2)
    print(f"-> {args.output}")


if __name__ == "__main__":
    main()
