#!/usr/bin/env python3
"""
openweight_learnable_alibi.py — validate LEARNABLE-ALiBi on a REAL open-weight LLM.

CHAIN OF THOUGHT (why this experiment, and why it is built this way):
  Phases 4-6 (docs/PHASE{4,5,6}_*.md, paper learnable_positional_bias.pdf) selected
  ONE scheme by elimination: a learnable per-head linear positional bias
  ("learnable-ALiBi"). Every from-scratch toy result needs validation on a real,
  deployed-style model — but you CANNOT positional-swap a frozen RoPE model
  (Llama/Mistral/Qwen): that is the invalid "frozen-swap" that gave this project its
  original VACUOUS PASS (every scheme collapses equally; see cy_sieve_quality_gate).

  => The only VALID, CHEAP first test is an ALiBi-NATIVE open-weight model whose
     fixed per-head slopes a_h = 2^(-8h/H) we make TRAINABLE, initialized AT the
     released ladder (so step 0 == the shipped model, no quality cliff), then a short
     parameter-efficient continued-pretrain. Models: bigscience/bloom-560m|1b1 (RAIL),
     mosaicml/mpt-7b (Apache-2.0) at scale. Full rationale: docs/BENCHMARK_SPEC_OPENWEIGHT.md.

  HOW we unfreeze the slopes: BLOOM does not store slopes as parameters — it rebuilds
  them every forward in transformers...modeling_bloom.build_alibi_tensor(mask,H,dtype).
  We use this project's established global-monkey-patch pattern: replace that function
  with one that reads a learnable nn.Parameter `log_slopes` (init = log of the model's
  OWN extracted slopes), reconstructing the alibi tensor with the IDENTICAL formula and
  layout. A built-in step-0 equivalence assert guarantees we changed nothing but
  learnability. Slopes are shared across layers (faithful to BLOOM, whose alibi is
  identical per layer); per-layer slopes are a documented future extension.

MODES:
  frozen_fixed     released model, slopes frozen — BASELINE (eval only, no training)
  learnable_slopes unfreeze the H slopes + short continued-pretrain — THE HYPOTHESIS
  (LoRA on attention is an optional add-on via --lora, if `peft` is installed)

PRIMARY METRIC (ties to the energy thesis): train-short / serve-long extrapolation —
  validation perplexity at L = ctx * {1,2,4,8}, and the "usable-context multiple"
  (largest kx within a degradation band). KILL: if learnable_slopes does not improve
  the usable-context multiple over frozen_fixed (see docs/BENCHMARK_SPEC_OPENWEIGHT.md §6).

  NOTE: this is SCAFFOLDING. RULER / passkey-retrieval harnesses and a measured
  kWh/CO2e accounting are stubbed as TODOs (Section "TODO" below) — the runnable core
  here is the slope-unfreezing surgery + continued-pretrain + sliding-window-ppl
  extrapolation (the ALiBi paper's own metric), which is the decisive first signal.

CPU smoke (tiny random BLOOM): python openweight_learnable_alibi.py --preset smoke
GPU full:   python openweight_learnable_alibi.py --preset full --model bigscience/bloom-560m
Author: SocrateAI Lab (X. Callens) + Claude. MIT.
"""
from __future__ import annotations
import argparse, json, math, os, sys, time

# This Mac's SSL_CERT_FILE points at a company CA that breaks HF downloads; force
# certifi (harmless on the GPU VM, where certifi is already correct).
try:
    import certifi
    os.environ["SSL_CERT_FILE"] = certifi.where()
except Exception:
    pass

import torch, torch.nn as nn, torch.nn.functional as F

sys.path.insert(0, os.path.dirname(__file__))
import cy_sieve_quality_gate as qg   # reuse load_corpus (real WikiText, records source)


# ---------------------------------------------------------------------------
# Learnable-slope monkey-patch for BLOOM's ALiBi construction.
# ---------------------------------------------------------------------------

class SlopeHolder(nn.Module):
    """Holds H learnable log-slopes (positivity via exp). Init = the model's own
    extracted slopes, so exp(log_slopes) reproduces the released alibi at step 0."""
    def __init__(self, init_slopes: torch.Tensor):
        super().__init__()
        self.log_slopes = nn.Parameter(torch.log(init_slopes.clamp(min=1e-8)))

    def slopes(self) -> torch.Tensor:
        return torch.exp(self.log_slopes)


def _extract_bloom_slopes(orig_build, num_heads: int) -> torch.Tensor:
    """Recover the released per-head slopes by calling the ORIGINAL builder on a
    length-2 full mask: alibi[:, 0, 1] == slope * 1 == slope. Version-independent."""
    mask = torch.ones(1, 2, dtype=torch.long)
    alibi = orig_build(mask, num_heads, torch.float32)        # (num_heads, 1, 2)
    return alibi.reshape(num_heads, 2)[:, 1].detach().clone()


def patch_bloom_with_learnable_slopes(model, learnable: bool):
    """Replace modeling_bloom.build_alibi_tensor with a version driven by a learnable
    SlopeHolder. Returns the holder (its parameter is the ONLY thing we train as the
    positional scheme). `learnable` toggles requires_grad on the slopes."""
    import transformers.models.bloom.modeling_bloom as bloom_mod
    if not hasattr(bloom_mod, "build_alibi_tensor"):
        raise RuntimeError(
            "this transformers version does not expose modeling_bloom.build_alibi_tensor; "
            "pin a version where BLOOM builds alibi via the module-level function, or "
            "extend this patch to override BloomAttention.forward.")
    orig_build = bloom_mod.build_alibi_tensor
    num_heads = model.config.n_head
    holder = SlopeHolder(_extract_bloom_slopes(orig_build, num_heads)).to(
        next(model.parameters()).device)
    holder.log_slopes.requires_grad_(learnable)

    def learnable_build_alibi_tensor(attention_mask, num_heads_, dtype):
        # Reconstruct with the IDENTICAL formula/layout as BLOOM, slopes -> learnable.
        batch, seq = attention_mask.shape
        slopes = holder.slopes().to(attention_mask.device)             # (H,)
        arange_tensor = ((attention_mask.cumsum(dim=-1) - 1) * attention_mask)[:, None, :]
        alibi = slopes[..., None] * arange_tensor                      # (batch, H, seq)
        return alibi.reshape(batch * num_heads_, 1, seq).to(dtype)

    # Step-0 equivalence guard: with the freshly-extracted slopes the learnable
    # builder must reproduce the original alibi bit-for-bit (we changed only learnability).
    mask = torch.ones(2, 5, dtype=torch.long)
    a0 = orig_build(mask, num_heads, torch.float32)
    a1 = learnable_build_alibi_tensor(mask, num_heads, torch.float32)
    assert torch.allclose(a0, a1, atol=1e-5), "step-0 alibi equivalence FAILED — patch is unfaithful"

    bloom_mod.build_alibi_tensor = learnable_build_alibi_tensor
    model._orig_build_alibi = orig_build                                # keep for restore
    return holder


# ---------------------------------------------------------------------------
# Data: reuse qg.load_corpus (real WikiText, records source), tokenize with the
# model's own tokenizer, contiguous-block iterator (like qg.batch_iter but token-level).
# ---------------------------------------------------------------------------

def tokenize_corpus(text, tokenizer, max_tokens=None):
    ids = tokenizer(text, return_tensors="pt", truncation=False)["input_ids"][0]
    if max_tokens:
        ids = ids[:max_tokens]
    return ids


def token_batch_iter(ids, ctx, batch, device, gen):
    n = ids.size(0) - ctx - 1
    if n <= 0:
        raise RuntimeError(f"corpus too short ({ids.size(0)} tok) for ctx={ctx}")
    while True:
        ix = torch.randint(0, n, (batch,), generator=gen)
        x = torch.stack([ids[i:i + ctx] for i in ix]).to(device)
        y = torch.stack([ids[i + 1:i + 1 + ctx] for i in ix]).to(device)
        yield x, y


@torch.no_grad()
def perplexity(model, ids, ctx, device, n_batches=8, batch=4):
    """Sliding-window perplexity at sequence length `ctx` (the ALiBi extrapolation
    metric). For ctx > training length this measures serve-long quality directly."""
    model.eval()
    gen = torch.Generator().manual_seed(1234)
    it = token_batch_iter(ids, ctx, batch, device, gen)
    tot = cnt = 0
    for _ in range(n_batches):
        x, y = next(it)
        out = model(input_ids=x, labels=None)
        logits = out.logits
        loss = F.cross_entropy(logits.view(-1, logits.size(-1)), y.reshape(-1))
        if math.isfinite(loss.item()):
            tot += loss.item(); cnt += 1
    return math.exp(tot / max(cnt, 1))


# ---------------------------------------------------------------------------
# Continued-pretrain (slopes only, frozen base) — reuses the hetero-pos pattern:
# gamma-L2 on slopes + validation early-stopping (both proved ESSENTIAL, see
# AUTORESEARCH_HYPOTHESES.md: a short budget otherwise crowns the overfitter).
# ---------------------------------------------------------------------------

def continued_pretrain(model, holder, train_ids, val_ids, device, cfg):
    for p in model.parameters():
        p.requires_grad_(False)
    holder.log_slopes.requires_grad_(True)
    trainable = [holder.log_slopes]
    # optional LoRA on attention (only if peft present and --lora passed)
    if cfg.get("lora"):
        try:
            from peft import LoraConfig, get_peft_model
            lc = LoraConfig(r=8, lora_alpha=16, target_modules=["query_key_value"],
                            lora_dropout=0.0, bias="none", task_type="CAUSAL_LM")
            model = get_peft_model(model, lc)
            trainable += [p for p in model.parameters() if p.requires_grad]
            print("    LoRA attached (query_key_value)")
        except Exception as e:
            print(f"    [warn] LoRA requested but unavailable ({e}); slopes-only")

    opt = torch.optim.AdamW(trainable, lr=cfg["lr"], weight_decay=0.0)
    gen = torch.Generator().manual_seed(42)
    it = token_batch_iter(train_ids, cfg["ctx"], cfg["batch"], device, gen)
    ev, pmax = cfg.get("eval_every", 0), cfg.get("patience", 4)
    best, patience, best_slopes = float("inf"), 0, None
    model.train()
    for step in range(1, cfg["steps"] + 1):
        x, y = next(it)
        out = model(input_ids=x)
        loss = F.cross_entropy(out.logits.view(-1, out.logits.size(-1)), y.reshape(-1))
        loss = loss + cfg.get("gamma_l2", 0.0) * (holder.slopes() ** 2).sum()
        opt.zero_grad(set_to_none=True); loss.backward()
        nn.utils.clip_grad_norm_(trainable, 1.0); opt.step()
        if ev and step % ev == 0:
            vp = perplexity(model, val_ids, cfg["ctx"], device)
            print(f"    step {step:>5} val-ppl@{cfg['ctx']} {vp:.3f}")
            if vp < best - 1e-3:
                best, patience = vp, 0
                best_slopes = holder.log_slopes.detach().clone()
            else:
                patience += 1
                if patience >= pmax:
                    print(f"    early-stop @ {step}"); break
            model.train()
    if best_slopes is not None:
        with torch.no_grad():
            holder.log_slopes.copy_(best_slopes)
    return model, best if best < 9e8 else None


def usable_context_multiple(extrap, base_key="1x", band=0.10):
    """Largest kx whose ppl stays within `band` (relative) of the 1x ppl — the
    energy-relevant headline (how far you can serve beyond train length 'for free')."""
    base = extrap.get(base_key)
    if not base:
        return None
    best = 1
    for mult in (1, 2, 4, 8):
        v = extrap.get(f"{mult}x")
        if v is not None and v <= base * (1 + band):
            best = mult
    return best


# ---------------------------------------------------------------------------
# Presets / driver
# ---------------------------------------------------------------------------

SMOKE = dict(model="bigscience/bigscience-small-testing", ctx=32, batch=2, steps=20,
             lr=1e-2, gamma_l2=1e-3, eval_every=10, patience=3, max_tokens=20_000)
FULL = dict(model="bigscience/bloom-560m", ctx=512, batch=4, steps=2000, lr=5e-3,
            gamma_l2=1e-3, eval_every=200, patience=4, max_tokens=4_000_000)
MODES = ["frozen_fixed", "learnable_slopes"]


def run_mode(mode, train_ids, val_ids, tok, device, cfg):
    from transformers import BloomForCausalLM
    model = BloomForCausalLM.from_pretrained(cfg["model"]).to(device)
    holder = patch_bloom_with_learnable_slopes(model, learnable=(mode == "learnable_slopes"))
    init_slopes = [round(float(s), 5) for s in holder.slopes().detach().cpu()]
    best_val = None
    if mode == "learnable_slopes":
        model, best_val = continued_pretrain(model, holder, train_ids, val_ids, device, cfg)
    # PRIMARY METRIC: serve-long extrapolation at 1x/2x/4x/8x
    extrap = {}
    for mult in (1, 2, 4, 8):
        L = cfg["ctx"] * mult
        try:
            extrap[f"{mult}x"] = round(perplexity(model, val_ids, L, device), 4)
        except Exception as e:
            extrap[f"{mult}x"] = None
    final_slopes = [round(float(s), 5) for s in holder.slopes().detach().cpu()]
    # restore original builder so repeated runs in one process are clean
    import transformers.models.bloom.modeling_bloom as bloom_mod
    if hasattr(model, "_orig_build_alibi"):
        bloom_mod.build_alibi_tensor = model._orig_build_alibi
    if device == "cuda":
        del model; torch.cuda.empty_cache()
    return {"mode": mode, "extrap": extrap, "best_val": best_val,
            "usable_ctx_mult": usable_context_multiple(extrap),
            "init_slopes": init_slopes, "final_slopes": final_slopes}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", choices=["smoke", "full"], default="smoke")
    ap.add_argument("--model", default=None, help="override the preset model id")
    ap.add_argument("--modes", nargs="+", default=MODES)
    ap.add_argument("--steps", type=int, default=None)
    ap.add_argument("--lora", action="store_true", help="also LoRA-adapt attention (needs peft)")
    ap.add_argument("--output", default="openweight_learnable_alibi_results.json")
    args = ap.parse_args()
    cfg = dict(FULL if args.preset == "full" else SMOKE)
    if args.model: cfg["model"] = args.model
    if args.steps: cfg["steps"] = args.steps
    cfg["lora"] = args.lora
    device = "cuda" if torch.cuda.is_available() else "cpu"

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(cfg["model"])
    tr, va, src = qg.load_corpus(max_chars=cfg["max_tokens"] * 8)   # ~chars; trimmed by tokens
    train_ids = tokenize_corpus(tr, tok, cfg["max_tokens"])
    val_ids = tokenize_corpus(va, tok, cfg["max_tokens"] // 8)
    print(f"OPENWEIGHT learnable-ALiBi ({args.preset}) | model={cfg['model']} "
          f"corpus={src} | train={train_ids.numel()} val={val_ids.numel()} tok | "
          f"ctx={cfg['ctx']} steps={cfg['steps']} device={device}\n")
    if src == "SYNTHETIC-FALLBACK":
        print("  [warn] synthetic corpus — results VACUOUS; install datasets+xxhash.\n")

    runs = []
    for m in args.modes:
        t0 = time.perf_counter()
        try:
            r = run_mode(m, train_ids, val_ids, tok, device, cfg); runs.append(r)
            print(f"  {m:>16}: extrap {r['extrap']}  usable_ctx={r['usable_ctx_mult']}x  "
                  f"({time.perf_counter()-t0:.0f}s)")
        except Exception as e:
            print(f"  {m:>16}: ERROR {e}"); runs.append({"mode": m, "error": str(e)})

    # VERDICT: learnable_slopes vs frozen_fixed on usable-context multiple (the metric
    # that ties to energy: more serve-long headroom per unit of adaptation compute).
    def get(m): return next((r for r in runs if r.get("mode") == m), None)
    fz, lr = get("frozen_fixed"), get("learnable_slopes")
    if fz and lr and fz.get("usable_ctx_mult") and lr.get("usable_ctx_mult"):
        print(f"\n  VERDICT — usable-context multiple: frozen={fz['usable_ctx_mult']}x  "
              f"learnable={lr['usable_ctx_mult']}x  "
              f"({'IMPROVED' if lr['usable_ctx_mult'] > fz['usable_ctx_mult'] else 'NO GAIN (KILL)'})")
        print("  NOTE: scaffolding metric is sliding-window ppl; RULER/passkey + measured "
              "kWh/CO2e are the next harness (docs/BENCHMARK_SPEC_OPENWEIGHT.md TODO).")
    json.dump({"corpus": src, "cfg": {k: v for k, v in cfg.items()}, "runs": runs},
              open(args.output, "w"), indent=2)
    print(f"\n-> {args.output}")


# TODO (next harness, beyond this scaffold) — see docs/BENCHMARK_SPEC_OPENWEIGHT.md:
#   1. RULER long-context tasks (4K..128K) instead of only sliding-window ppl.
#   2. Passkey / needle-in-a-haystack retrieval (sanity that ppl gain == usable signal).
#   3. PG-19 / proof-pile streaming corpus loader (replace WikiText for serve-long).
#   4. Per-layer learnable slopes (override BloomAttention.forward) as an ablation.
#   5. MEASURED kWh / CO2e of the continued-pretrain vs a RoPE position-interpolation
#      extension pass — the actual energy claim. Report a number or retract it.
#   6. MPT-7B path (Apache-2.0) for the headline-credible scale-up.
if __name__ == "__main__":
    main()
