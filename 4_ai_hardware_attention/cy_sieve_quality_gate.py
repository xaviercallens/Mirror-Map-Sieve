#!/usr/bin/env python3
"""
cy_sieve_quality_gate.py — tests.md §5, the DECISIVE quality gate (DONE RIGHT).

The whole CY-Sieve bet is worthless if it degrades model quality. The honest way
to measure that is the ALiBi-paper methodology: TRAIN small GPT models FROM
SCRATCH — identical architecture, data, steps and compute — one per positional
scheme, then compare validation perplexity at the training context AND
length-extrapolation perplexity at 2x/4x the training context.

  WHY NOT zero-shot-swap a pretrained model? We tried; it is invalid. A frozen
  GPT-2 was trained with learned absolute positions; zeroing them and injecting
  ANY unfamiliar bias collapses perplexity equally (native 32.5 vs ALiBi 1641,
  sliding 2529, CY-Sieve ~7180 on WikiText-2). That measures train/test mismatch,
  not the scheme — and reporting it would violate the project's §7 honesty guards.

Schemes (each is purely a positional-bias choice; the rest of the net is shared):
  * learned   — learned absolute position embeddings (the GPT-2-style control)
  * alibi     — ALiBi linear bias  -m_h*(i-j),  m_h = 2^(-8h/H)
  * sliding   — sliding-window local mask of fixed width (no other positions)
  * cy_sieve  — CY-Sieve per-head tau-ladder bias from cy_sieve_reference

PASS (do not soften): CY-Sieve val-perplexity within +1% of the best baseline
(ideally lower) AND length-extrapolation not worse beyond noise. KILL: >5%
regression vs the best baseline, or extrapolation collapse → NEGATIVE result.

CPU-runnable tiny (for a smoke dry-run); the real run is on the L4 (see
GPU_SETUP.md / run_gpu_phase.py). Single-GPU, fp32/bf16, no external trainer.

Author: SocrateAI Laboratory (X. Callens) + Claude (Opus 4.8). License: MIT.
"""
from __future__ import annotations
import argparse, json, math, os, sys, time

import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(__file__))
import cy_sieve_reference as cy


# ---------------------------------------------------------------------------
# Positional bias  ->  additive [H, L, L] (built once per (scheme, H, L)).
# bias[h, i, j] added to the pre-softmax score; causal handled by the model.
# ---------------------------------------------------------------------------

def _dist(L, device):
    idx = torch.arange(L, device=device)
    return idx[:, None] - idx[None, :]            # i - j


def alibi_bias(H, L, device, dtype):
    d = _dist(L, device).clamp(min=0).to(dtype)
    slopes = torch.tensor([2.0 ** (-8.0 * h / H) for h in range(1, H + 1)],
                          device=device, dtype=dtype)
    return -slopes[:, None, None] * d[None]


def sliding_bias(H, L, device, dtype, window=128):
    d = _dist(L, device)
    keep = (d >= 0) & (d < window)
    b = torch.where(keep, torch.zeros((), device=device, dtype=dtype),
                    torch.full((), float("-inf"), device=device, dtype=dtype))
    return b[None].expand(H, L, L).contiguous()


def cy_sieve_bias(H, L, device, dtype, taus=None, flat_tau=None, seq="S20"):
    if flat_tau is not None:
        taus = [float(flat_tau)] * H
    if taus is None:
        taus = cy.alibi_style_tau_ladder(H)
    assert len(taus) == H
    d = _dist(L, device).clamp(min=0)
    out = torch.empty(H, L, L, device=device, dtype=dtype)
    for h, tau in enumerate(taus):
        bv = torch.tensor(cy.build_bias_vector(L, seq, tau), device=device,
                          dtype=dtype)
        out[h] = bv[d]
    return out


def build_bias(scheme, H, L, device, dtype, **kw):
    if scheme in ("learned", "none"):
        return None
    if scheme == "alibi":
        return alibi_bias(H, L, device, dtype)
    if scheme == "sliding":
        return sliding_bias(H, L, device, dtype, window=kw.get("window", 128))
    if scheme == "cy_sieve":
        return cy_sieve_bias(H, L, device, dtype, taus=kw.get("taus"),
                             flat_tau=kw.get("flat_tau"), seq=kw.get("seq", "S20"))
    raise ValueError(scheme)


# ---------------------------------------------------------------------------
# A small GPT.  Positional bias is supplied to attention; only the `learned`
# scheme additionally uses a learned wpe. Everything else is shared so the
# comparison isolates the positional scheme.
# ---------------------------------------------------------------------------

class Block(nn.Module):
    def __init__(self, d_model, n_head, d_ff):
        super().__init__()
        self.ln1 = nn.LayerNorm(d_model)
        self.ln2 = nn.LayerNorm(d_model)
        self.qkv = nn.Linear(d_model, 3 * d_model)
        self.proj = nn.Linear(d_model, d_model)
        self.mlp = nn.Sequential(nn.Linear(d_model, d_ff), nn.GELU(),
                                 nn.Linear(d_ff, d_model))
        self.n_head = n_head
        self.d_head = d_model // n_head

    def forward(self, x, pos_bias):
        B, L, _ = x.shape
        h = self.ln1(x)
        q, k, v = self.qkv(h).split(h.shape[-1], dim=-1)
        q = q.view(B, L, self.n_head, self.d_head).transpose(1, 2)
        k = k.view(B, L, self.n_head, self.d_head).transpose(1, 2)
        v = v.view(B, L, self.n_head, self.d_head).transpose(1, 2)
        attn_mask = None
        if pos_bias is not None:
            attn_mask = pos_bias[None, :, :L, :L]      # [1,H,L,L], may hold -inf
        out = F.scaled_dot_product_attention(q, k, v, attn_mask=attn_mask,
                                             is_causal=(pos_bias is None))
        out = out.transpose(1, 2).contiguous().view(B, L, -1)
        x = x + self.proj(out)
        x = x + self.mlp(self.ln2(x))
        return x


class TinyGPT(nn.Module):
    def __init__(self, vocab, d_model=256, n_layer=4, n_head=4, d_ff=1024,
                 max_len=2048, learned_pos=False):
        super().__init__()
        self.wte = nn.Embedding(vocab, d_model)
        self.learned_pos = learned_pos
        if learned_pos:
            self.wpe = nn.Embedding(max_len, d_model)
        self.blocks = nn.ModuleList(
            [Block(d_model, n_head, d_ff) for _ in range(n_layer)])
        self.ln_f = nn.LayerNorm(d_model)
        self.head = nn.Linear(d_model, vocab, bias=False)
        self.head.weight = self.wte.weight       # tie
        self.n_head = n_head

    def forward(self, idx, pos_bias, targets=None):
        B, L = idx.shape
        x = self.wte(idx)
        if self.learned_pos:
            pos = torch.arange(L, device=idx.device)
            x = x + self.wpe(pos)[None]
        # causal mask when no additive bias supplies it
        if pos_bias is not None:
            causal = torch.tril(torch.ones(L, L, device=idx.device, dtype=torch.bool))
            pb = pos_bias[:, :L, :L].clone()
            pb = pb.masked_fill(~causal[None], float("-inf"))
        else:
            pb = None
        for blk in self.blocks:
            x = blk(x, pb)
        x = self.ln_f(x)
        logits = self.head(x)
        loss = None
        if targets is not None:
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)),
                                   targets.view(-1), ignore_index=-100)
        return logits, loss


# ---------------------------------------------------------------------------
# Data — byte-level tokenization of WikiText-2 (no tokenizer dependency, fully
# offline-safe). Falls back to a bundled text if `datasets` is unavailable.
# ---------------------------------------------------------------------------

def load_corpus(max_chars=2_000_000):
    """Returns (train_txt, val_txt, source). `source` is "wikitext-2-raw-v1" for
    the real corpus or "SYNTHETIC-FALLBACK" when datasets is unavailable — the
    caller MUST record this, because the synthetic corpus is trivially memorized
    (every scheme scores ppl~1.0) and a PASS on it is scientifically vacuous."""
    try:
        from datasets import load_dataset
        tr = load_dataset("wikitext", "wikitext-2-raw-v1", split="train")
        va = load_dataset("wikitext", "wikitext-2-raw-v1", split="validation")
        train_txt = "\n".join(t for t in tr["text"] if t.strip())[:max_chars]
        val_txt = "\n".join(t for t in va["text"] if t.strip())[:max_chars // 8]
        return train_txt, val_txt, "wikitext-2-raw-v1"
    except Exception as e:
        print(f"  [warn] datasets unavailable ({e}); using bundled sample. "
              f"RESULTS WILL BE VACUOUS (ppl~1.0). Install datasets+xxhash.")
        base = (_FALLBACK_TEXT + "\n") * 4000
        return base[:max_chars], base[:max_chars // 8], "SYNTHETIC-FALLBACK"


_FALLBACK_TEXT = (
    "The mirror map sends the complex structure modulus of one Calabi Yau "
    "threefold to the Kahler modulus of its mirror, and its q expansion "
    "coefficients are conjecturally integers. The weight five Apery like "
    "sequence satisfies an order four Picard Fuchs recurrence with a rank four "
    "maximally unipotent monodromy block.")


def to_bytes(text):
    return torch.tensor(list(text.encode("utf-8", errors="ignore")),
                        dtype=torch.long)


def batch_iter(data, ctx, batch, device, gen):
    n = data.size(0) - ctx - 1
    while True:
        ix = torch.randint(0, n, (batch,), generator=gen)
        x = torch.stack([data[i:i + ctx] for i in ix]).to(device)
        y = torch.stack([data[i + 1:i + 1 + ctx] for i in ix]).to(device)
        yield x, y


@torch.no_grad()
def eval_ppl(model, data, ctx, device, scheme, H, dtype, kw, n_batches=20,
             batch=8):
    model.eval()
    pos_bias = build_bias(scheme, H, ctx, device, dtype, **kw)
    gen = torch.Generator().manual_seed(1234)
    it = batch_iter(data, ctx, batch, device, gen)
    tot, cnt = 0.0, 0
    for _ in range(n_batches):
        x, y = next(it)
        _, loss = model(x, pos_bias, targets=y)
        if math.isfinite(loss.item()):
            tot += loss.item(); cnt += 1
    model.train()
    return math.exp(tot / max(cnt, 1))


# ---------------------------------------------------------------------------
# Train one scheme from scratch
# ---------------------------------------------------------------------------

def train_scheme(scheme, train_data, val_data, cfg, device, kw):
    torch.manual_seed(0)
    H = cfg["n_head"]
    dtype = torch.float32
    model = TinyGPT(vocab=256, d_model=cfg["d_model"], n_layer=cfg["n_layer"],
                    n_head=H, d_ff=cfg["d_ff"], max_len=cfg["max_extrap"],
                    learned_pos=(scheme == "learned")).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    opt = torch.optim.AdamW(model.parameters(), lr=cfg["lr"], betas=(0.9, 0.95),
                            weight_decay=0.1)
    ctx = cfg["ctx"]
    pos_bias = build_bias(scheme, H, ctx, device, dtype, **kw)
    gen = torch.Generator().manual_seed(42)
    it = batch_iter(train_data, ctx, cfg["batch"], device, gen)
    model.train()
    t0 = time.perf_counter()
    for step in range(1, cfg["steps"] + 1):
        x, y = next(it)
        _, loss = model(x, pos_bias, targets=y)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if step % max(1, cfg["steps"] // 5) == 0 or step == 1:
            print(f"    {scheme:>9} step {step:>5}/{cfg['steps']} "
                  f"loss {loss.item():.4f}")
    train_s = time.perf_counter() - t0

    # Validation at train ctx + length extrapolation at 2x / 4x.
    results = {}
    for L in [ctx, 2 * ctx, 4 * ctx]:
        if L > cfg["max_extrap"]:
            continue
        ppl = eval_ppl(model, val_data, L, device, scheme, H, dtype, kw)
        results[str(L)] = round(ppl, 4)
        tag = "train" if L == ctx else f"{L // ctx}x-extrap"
        print(f"    {scheme:>9} val ppl @ L={L:<5} ({tag}): {ppl:.3f}")
    del model
    if device == "cuda":
        torch.cuda.empty_cache()
    return {"scheme": scheme, "params": n_params, "train_seconds": round(train_s, 1),
            "ppl_by_ctx": results, "tau": kw.get("flat_tau", "ladder")
            if scheme == "cy_sieve" else None}


def _verdict(runs, ctx):
    L = str(ctx)
    def ppl(r):
        return r["ppl_by_ctx"].get(L, float("inf"))
    base = {r["scheme"]: ppl(r) for r in runs if r["scheme"] != "cy_sieve"}
    best_base = min(base.values()) if base else float("inf")
    cyr = [(r.get("tau"), ppl(r)) for r in runs if r["scheme"] == "cy_sieve"]
    best_tau, best_cy = min(cyr, key=lambda x: x[1]) if cyr else (None, float("inf"))
    if not (math.isfinite(best_cy) and math.isfinite(best_base)):
        return {"status": "ERROR", "summary": "non-finite perplexity"}
    delta = (best_cy - best_base) / best_base * 100
    status = ("KILL (negative result)" if delta > 5 else
              "PASS" if delta <= 1 else "MARGINAL")
    return {"status": status, "delta_pct": round(delta, 3),
            "best_cy_ppl": best_cy, "best_cy_tau": best_tau,
            "best_baseline_ppl": best_base,
            "best_baseline": min(base, key=base.get) if base else None,
            "baselines": base, "train_ctx": ctx,
            "summary": f"best CY-Sieve {best_cy:.3f} (tau={best_tau}) vs best "
                       f"baseline {best_base:.3f}: {delta:+.2f}%"}


# Preset sizes: 'smoke' for CPU dry-run sanity, 'l4' for the real GPU run.
PRESETS = {
    "smoke": dict(d_model=128, n_layer=2, n_head=4, d_ff=512, ctx=128,
                  batch=8, steps=60, lr=3e-4, max_extrap=512),
    "l4": dict(d_model=512, n_layer=8, n_head=8, d_ff=2048, ctx=512,
               batch=24, steps=6000, lr=3e-4, max_extrap=2048),
}


def main():
    ap = argparse.ArgumentParser(description="CY-Sieve §5 quality gate (from scratch)")
    ap.add_argument("--preset", choices=list(PRESETS), default="smoke")
    ap.add_argument("--steps", type=int, default=None)
    ap.add_argument("--window", type=int, default=128)
    ap.add_argument("--seq", default="S20")
    ap.add_argument("--tau_sweep", type=float, nargs="+", default=[128.0])
    ap.add_argument("--cy_ladder", action="store_true", default=True)
    ap.add_argument("--output", default="cy_sieve_quality_results.json")
    args = ap.parse_args()

    cfg = dict(PRESETS[args.preset])
    if args.steps:
        cfg["steps"] = args.steps
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("=" * 74)
    print(f"  CY-Sieve §5 QUALITY GATE (from-scratch) — preset={args.preset} "
          f"on {device}")
    print(f"  arch d_model={cfg['d_model']} L={cfg['n_layer']} H={cfg['n_head']} "
          f"ctx={cfg['ctx']} steps={cfg['steps']}")
    print("=" * 74)

    train_txt, val_txt, corpus_source = load_corpus()
    train_data, val_data = to_bytes(train_txt), to_bytes(val_txt)
    print(f"  corpus: {corpus_source} | train {train_data.numel():,} bytes | "
          f"val {val_data.numel():,} bytes\n")

    runs = []
    for sch in ("learned", "alibi", "sliding"):
        print(f"[{sch}]")
        kw = {"window": args.window}
        runs.append(train_scheme(sch, train_data, val_data, cfg, device, kw))
        print()

    if args.cy_ladder:
        print("[cy_sieve / per-head tau ladder]")
        runs.append(train_scheme("cy_sieve", train_data, val_data, cfg, device,
                                 {"taus": None, "seq": args.seq}))
        print()
    for tau in args.tau_sweep:
        print(f"[cy_sieve / tau={tau}]")
        r = train_scheme("cy_sieve", train_data, val_data, cfg, device,
                         {"flat_tau": tau, "seq": args.seq})
        runs.append(r)
        print()

    verdict = _verdict(runs, cfg["ctx"])
    if corpus_source == "SYNTHETIC-FALLBACK":
        verdict["status"] = "INVALID (synthetic corpus)"
        verdict["summary"] = ("ran on the synthetic fallback corpus (ppl~1.0, "
                              "trivially memorized) — NOT a real quality result. "
                              + verdict.get("summary", ""))
    out = {"preset": args.preset, "device": device, "config": cfg,
           "corpus_source": corpus_source,
           "window": args.window, "seq": args.seq, "runs": runs,
           "verdict": verdict}
    json.dump(out, open(args.output, "w"), indent=2)
    print("=" * 74)
    print(f"  VERDICT: {verdict['status']} — {verdict.get('summary','')}")
    print(f"  results -> {args.output}")
    print("=" * 74)
    return out


if __name__ == "__main__":
    main()
