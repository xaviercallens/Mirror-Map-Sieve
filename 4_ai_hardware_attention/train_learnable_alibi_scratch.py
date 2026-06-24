#!/usr/bin/env python3
"""
train_learnable_alibi_scratch.py — train a learnable-ALiBi model FROM SCRATCH, the
checkpoint the pure-dense extrapolation gate (dense_extrapolation_gate.py) consumes.

WHY FROM SCRATCH (the lesson that motivates this):
  The L4 BLOOM-560m run (2026-06-24) only UNFROZE the slopes of an already-converged
  fixed-ALiBi model and continued-pretrained briefly: result was a TIE (+0.28%), the
  slopes barely moved, and 4x/8x couldn't even be evaluated. That is the wrong
  experiment — a pretrained model's ALiBi slopes are already near-optimal, so there
  is nothing for slope-tuning to find. To actually TEST whether learnable per-head
  slopes beat fixed ones, the slopes must be trainable FROM INITIALIZATION so the
  model co-adapts its weights to whatever slopes gradient descent chooses. This is
  the ALiBi-paper methodology (train-from-scratch, one positional scheme per model)
  applied to the learnable variant, at a real context length (default 4096) so the
  dense gate can probe 1x..8x = 4k..32k.

WHAT IT PRODUCES:
  A HuggingFace BloomForCausalLM checkpoint (config + safetensors) saved with
  save_pretrained, so dense_extrapolation_gate.py loads it via from_pretrained with
  NO custom code. The per-head slopes are LEARNABLE during training via the same
  global monkey-patch used in openweight_learnable_alibi.py (build_alibi_tensor ->
  learnable nn.Parameter). The final learned slopes are also dumped to slopes.json
  so the gate can re-apply them (HF's build_alibi_tensor is otherwise fixed).
  --mode fixed trains the IDENTICAL architecture with frozen ALiBi slopes = the
  control checkpoint for an apples-to-apples gate.

STORAGE: streaming corpus (datasets streaming=True, NO local corpus file) and
  checkpoints pushed to GCS (--gcs gs://.../checkpoints/RUN/) via `gsutil cp -r`,
  so nothing large lands on local disk (the dev box is disk-full; GPU VM is
  ephemeral). Local save dir is a scratch staging area only.

SCALES (config presets, override individually):
  smoke : tiny, CPU, ~1 min — plumbing only.
  small : ~125M params, 4k ctx — fits an L4/A100-40G, a few hours for ~1-2B tokens.
  base  : ~760M params, 4k ctx — needs A100-80G/H100, the credible checkpoint.
  The token budget is set by --tokens (default scales with preset); we report the
  realized epoch count so over-training is visible (the overfit lesson).

CPU smoke:  python train_learnable_alibi_scratch.py --preset smoke
GPU run:    python train_learnable_alibi_scratch.py --preset base --mode learnable \
              --tokens 10_000_000_000 --gcs gs://<bucket>/checkpoints/run1/
Author: SocrateAI Lab (X. Callens) + Claude. MIT.
"""
from __future__ import annotations
import argparse, json, math, os, subprocess, sys, time

try:
    import certifi
    os.environ["SSL_CERT_FILE"] = certifi.where()
except Exception:
    pass

import torch
import torch.nn as nn
import torch.nn.functional as F


# ---------------------------------------------------------------------------
# Learnable-slope monkey-patch (shared design with openweight_learnable_alibi.py):
# BLOOM rebuilds alibi each forward in modeling_bloom.build_alibi_tensor; we route
# the slopes through a learnable nn.Parameter so they train from initialization.
# ---------------------------------------------------------------------------

class SlopeHolder(nn.Module):
    def __init__(self, init_slopes: torch.Tensor, learnable: bool):
        super().__init__()
        self.log_slopes = nn.Parameter(torch.log(init_slopes.clamp(min=1e-8)),
                                       requires_grad=learnable)

    def slopes(self):
        return torch.exp(self.log_slopes)


def _default_alibi_slopes(num_heads: int) -> torch.Tensor:
    # The standard ALiBi geometric ladder a_h = 2^(-8h/H) (BLOOM's own init).
    return torch.tensor([2.0 ** (-8.0 * h / num_heads) for h in range(1, num_heads + 1)],
                        dtype=torch.float32)


def patch_bloom_learnable_slopes(num_heads: int, device, learnable: bool):
    import transformers.models.bloom.modeling_bloom as bloom_mod
    if not hasattr(bloom_mod, "build_alibi_tensor"):
        raise RuntimeError("transformers version lacks modeling_bloom.build_alibi_tensor; "
                           "pin transformers<5 (the 4.x line exposes it).")
    holder = SlopeHolder(_default_alibi_slopes(num_heads), learnable).to(device)

    def learnable_build_alibi_tensor(attention_mask, n_heads, dtype):
        batch, seq = attention_mask.shape
        slopes = holder.slopes().to(attention_mask.device)
        arange = ((attention_mask.cumsum(dim=-1) - 1) * attention_mask)[:, None, :]
        alibi = slopes[..., None] * arange
        return alibi.reshape(batch * n_heads, 1, seq).to(dtype)

    bloom_mod.build_alibi_tensor = learnable_build_alibi_tensor
    return holder


# ---------------------------------------------------------------------------
# Streaming corpus -> contiguous token blocks of length ctx. NO local corpus file.
# ---------------------------------------------------------------------------

def stream_token_blocks(tokenizer, dataset, ctx, batch, smoke=False):
    """Infinite generator of (input_ids[batch,ctx]) from a streaming dataset, packed
    into contiguous ctx-length blocks (GPT-style packing). Re-streams on exhaustion."""
    if smoke:
        text = ("the river moved slowly past the old mill in the long afternoon "
                "of a forgotten century ") * 2000
        ids = tokenizer(text, return_tensors="pt")["input_ids"][0]
        buf = ids.tolist()
        while True:
            need = batch * ctx
            while len(buf) < need:
                buf += ids.tolist()
            blk = torch.tensor(buf[:need]).view(batch, ctx); buf = buf[need:]
            yield blk
    from datasets import load_dataset
    specs = {"pg19": ("pg19", None, "train", "text"),
             "c4": ("allenai/c4", "en", "train", "text"),
             "wikitext": ("Salesforce/wikitext", "wikitext-103-raw-v1", "train", "text")}
    name, cfg, split, col = specs.get(dataset, specs["pg19"])
    buf = []
    while True:  # re-stream from the top if the iterator is exhausted
        ds = load_dataset(name, cfg, split=split, streaming=True)
        for row in ds:
            t = row.get(col) or ""
            if not t.strip():
                continue
            buf += tokenizer(t, return_tensors="pt")["input_ids"][0].tolist()
            need = batch * ctx
            while len(buf) >= need:
                blk = torch.tensor(buf[:need]).view(batch, ctx); buf = buf[need:]
                yield blk


# ---------------------------------------------------------------------------
# Model: a fresh (randomly initialized) BloomForCausalLM at the chosen scale.
# ---------------------------------------------------------------------------

def build_fresh_bloom(vocab, d_model, n_layer, n_head, device, dtype):
    from transformers import BloomConfig, BloomForCausalLM
    cfg = BloomConfig(vocab_size=vocab, hidden_size=d_model, n_layer=n_layer,
                      n_head=n_head, attention_dropout=0.0, hidden_dropout=0.0,
                      use_cache=False)
    model = BloomForCausalLM(cfg).to(device=device, dtype=dtype)
    return model


PRESETS = {
    "smoke": dict(d_model=128, n_layer=2, n_head=4, ctx=64, batch=2, tokens=200_000,
                  lr=3e-4, dataset="pg19", eval_every=50, warmup=20),
    "small": dict(d_model=768, n_layer=12, n_head=12, ctx=4096, batch=8, tokens=2_000_000_000,
                  lr=3e-4, dataset="pg19", eval_every=500, warmup=200),
    "base":  dict(d_model=1536, n_layer=24, n_head=16, ctx=4096, batch=8, tokens=10_000_000_000,
                  lr=2e-4, dataset="pg19", eval_every=1000, warmup=500),
}


def gcs_sync(local_dir, gcs_uri):
    if not gcs_uri:
        return
    try:
        subprocess.run(["gsutil", "-m", "cp", "-r", local_dir, gcs_uri],
                       check=True, capture_output=True)
        print(f"    [gcs] synced {local_dir} -> {gcs_uri}")
    except Exception as e:
        print(f"    [gcs] WARN sync failed: {e}")


@torch.no_grad()
def quick_val(model, val_iter, device, n=8):
    model.eval(); tot = cnt = 0
    for _ in range(n):
        blk = next(val_iter).to(device)
        out = model(input_ids=blk)
        loss = F.cross_entropy(out.logits[:, :-1].reshape(-1, out.logits.size(-1)),
                               blk[:, 1:].reshape(-1))
        if math.isfinite(loss.item()):
            tot += loss.item(); cnt += 1
    model.train(); return math.exp(tot / max(cnt, 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", choices=list(PRESETS), default="smoke")
    ap.add_argument("--mode", choices=["learnable", "fixed"], default="learnable",
                    help="learnable = trainable per-head slopes (treatment); fixed = control")
    ap.add_argument("--tokens", type=int, default=None, help="token budget (overrides preset)")
    ap.add_argument("--ctx", type=int, default=None)
    ap.add_argument("--batch", type=int, default=None)
    ap.add_argument("--lr", type=float, default=None)
    ap.add_argument("--dataset", default=None, choices=["pg19", "c4", "wikitext"])
    ap.add_argument("--gamma-l2", type=float, default=1e-3, help="L2 on slopes (the overfit fix)")
    ap.add_argument("--save-dir", default="/tmp/learnable_alibi_ckpt")
    ap.add_argument("--gcs", default=None, help="gs://.../checkpoints/RUN/  (no local hoarding)")
    ap.add_argument("--ckpt-every", type=int, default=0, help="steps between GCS checkpoints (0=final only)")
    ap.add_argument("--bf16", action="store_true")
    args = ap.parse_args()

    cfg = dict(PRESETS[args.preset])
    for k in ("tokens", "ctx", "batch", "lr", "dataset"):
        if getattr(args, k) is not None:
            cfg[k] = getattr(args, k)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if (args.bf16 and device == "cuda") else torch.float32
    smoke = args.preset == "smoke"

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained("bigscience/bloom-560m")  # BPE vocab, ALiBi-native
    vocab = tok.vocab_size

    holder = patch_bloom_learnable_slopes(cfg["n_head"], device, learnable=(args.mode == "learnable"))
    model = build_fresh_bloom(vocab, cfg["d_model"], cfg["n_layer"], cfg["n_head"], device, dtype)
    nparams = sum(p.numel() for p in model.parameters())

    steps = max(1, cfg["tokens"] // (cfg["batch"] * cfg["ctx"]))
    print(f"TRAIN learnable-ALiBi FROM SCRATCH | preset={args.preset} mode={args.mode} "
          f"params={nparams/1e6:.1f}M ctx={cfg['ctx']} batch={cfg['batch']} "
          f"tokens={cfg['tokens']:,} steps={steps:,} dataset={cfg['dataset']} device={device}\n")
    print(f"  init slopes: {[round(float(s),4) for s in holder.slopes().detach().cpu()]}")

    train_iter = stream_token_blocks(tok, cfg["dataset"], cfg["ctx"], cfg["batch"], smoke)
    val_iter = stream_token_blocks(tok, cfg["dataset"], cfg["ctx"], cfg["batch"], smoke)

    params = list(model.parameters())
    if args.mode == "learnable":
        params += [holder.log_slopes]
    opt = torch.optim.AdamW(params, lr=cfg["lr"], weight_decay=0.1, betas=(0.9, 0.95))
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1.0, s / max(1, cfg.get("warmup", 1))) *
                       (0.5 * (1 + math.cos(math.pi * min(1.0, s / steps)))))

    os.makedirs(args.save_dir, exist_ok=True)
    model.train(); t0 = time.perf_counter()
    for step in range(1, steps + 1):
        blk = next(train_iter).to(device)
        out = model(input_ids=blk)
        loss = F.cross_entropy(out.logits[:, :-1].reshape(-1, out.logits.size(-1)),
                               blk[:, 1:].reshape(-1))
        if args.mode == "learnable":
            loss = loss + args.gamma_l2 * (holder.slopes() ** 2).sum()
        opt.zero_grad(set_to_none=True); loss.backward()
        nn.utils.clip_grad_norm_(params, 1.0); opt.step(); sched.step()
        if step % cfg["eval_every"] == 0 or step == steps:
            vp = quick_val(model, val_iter, device)
            tok_seen = step * cfg["batch"] * cfg["ctx"]
            print(f"  step {step:>7}/{steps} val-ppl {vp:.3f}  tok {tok_seen:,}  "
                  f"slopes[0,-1]={float(holder.slopes()[0]):.4f},{float(holder.slopes()[-1]):.4f}  "
                  f"({time.perf_counter()-t0:.0f}s)")
        if args.ckpt_every and step % args.ckpt_every == 0:
            _save(model, tok, holder, args, cfg, step, nparams)
            gcs_sync(args.save_dir, args.gcs)

    _save(model, tok, holder, args, cfg, steps, nparams)
    gcs_sync(args.save_dir, args.gcs)
    print(f"\n  final slopes: {[round(float(s),4) for s in holder.slopes().detach().cpu()]}")
    print(f"  -> {args.save_dir}  (gcs: {args.gcs or 'none'})")


def _save(model, tok, holder, args, cfg, step, nparams):
    # HF-native save so the dense gate loads with from_pretrained, no custom code.
    model.save_pretrained(args.save_dir, safe_serialization=True)
    tok.save_pretrained(args.save_dir)
    meta = {"mode": args.mode, "preset": args.preset, "step": step, "cfg": cfg,
            "params": nparams,
            "slopes": [float(s) for s in holder.slopes().detach().cpu()],
            "note": "learnable-ALiBi from-scratch checkpoint; slopes.json drives the "
                    "dense gate's build_alibi_tensor (HF's is otherwise fixed)."}
    json.dump(meta, open(os.path.join(args.save_dir, "slopes.json"), "w"), indent=2)


if __name__ == "__main__":
    main()
