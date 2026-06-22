#!/usr/bin/env python3
"""
cy_sieve_memory_experiments.py — local CPU experiments for the 3 selected future
directions, judged on the question that matters: can we keep the ~2% quality gain
AND turn it into a real MEMORY win (not the illusory bias-table comparison)?

  H-C  learnable-γ Holonomic-ALiBi bias        — the quality reference (~2% vs ALiBi)
  H-A  holonomic KV-cache eviction schedule    — the real memory lever (KV cache)
  H-F  holonomic decay prior for a gated        — O(L) is native; geometry as a
       linear-attention (SSM-style) gate           forget-gate prior

H-A is the centerpiece: at a FIXED KV budget B<<L, which keep-policy preserves
perplexity best? A pure holonomic curve is monotone ⇒ "keep highest-weight" = keep
recent (the trap). So the holonomic policy keeps a DENSE recent window + a
holonomically-STRIDED sample of the deep past (graceful degradation), vs
StreamingLLM's sink+recent and a plain recent window.

Tiny by design (CPU, minutes). Reuses cy_sieve_quality_gate corpus + cy_sieve_
autoresearch bias modules.

Author: SocrateAI Laboratory (X. Callens) + Claude (Opus 4.8). License: MIT.
"""
from __future__ import annotations
import argparse, json, math, os, sys, time
import torch, torch.nn as nn, torch.nn.functional as F

sys.path.insert(0, os.path.dirname(__file__))
import cy_sieve_reference as cy
import cy_sieve_quality_gate as qg
import cy_sieve_autoresearch as ar


# ===========================================================================
# Shared tiny GPT (reuses ar.Block/TinyGPT but we need eval-time KV masks)
# ===========================================================================

CFG = dict(d_model=128, n_layer=3, n_head=4, d_ff=512, ctx=512, batch=12,
           steps=800, lr=3e-4, max_extrap=1024)


def train_base(bias_name, train_data, val_data, device, cfg=CFG, gamma_l2=1e-3):
    """Train one tiny GPT with the given positional-bias scheme. Returns model."""
    torch.manual_seed(0)
    H, maxd = cfg["n_head"], cfg["max_extrap"]
    learned_pos, factory, static = ar.make_scheme(bias_name, H, maxd)
    bias_mod = factory() if factory else None
    model = ar.TinyGPT(256, cfg["d_model"], cfg["n_layer"], H, cfg["d_ff"],
                       maxd, learned_pos, bias_mod).to(device)
    if static:
        model._static = ar.static_bias(static, H, cfg["ctx"], device); model._static_scheme = static
    opt = torch.optim.AdamW(model.parameters(), lr=cfg["lr"], weight_decay=0.1)
    gen = torch.Generator().manual_seed(42)
    it = qg.batch_iter(train_data, cfg["ctx"], cfg["batch"], device, gen)
    model.train()
    for step in range(1, cfg["steps"] + 1):
        x, y = next(it)
        _, loss = model(x, targets=y)
        if gamma_l2 and bias_mod is not None and hasattr(bias_mod, "scales"):
            loss = loss + gamma_l2 * (bias_mod.scales() ** 2).sum()
        opt.zero_grad(set_to_none=True); loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
    return model, bias_mod


@torch.no_grad()
def ppl(model, data, ctx, device, n_batches=15, batch=8):
    model.eval()
    if getattr(model, "_static_scheme", None):
        model._static = ar.static_bias(model._static_scheme, model.n_head, ctx, device)
    gen = torch.Generator().manual_seed(1234)
    it = qg.batch_iter(data, ctx, batch, device, gen)
    tot = cnt = 0
    for _ in range(n_batches):
        x, y = next(it); _, loss = model(x, targets=y)
        if math.isfinite(loss.item()): tot += loss.item(); cnt += 1
    model.train(); return math.exp(tot / max(cnt, 1))


# ===========================================================================
# H-A — KV-eviction keep-masks at a fixed budget B
# Returns a boolean [L,L] keep mask (True = key j visible to query i), causal.
# ===========================================================================

def keep_recent(L, B):
    i = torch.arange(L)[:, None]; j = torch.arange(L)[None, :]
    return (j <= i) & (j > i - B)

def keep_sink_recent(L, B, sink=4):
    i = torch.arange(L)[:, None]; j = torch.arange(L)[None, :]
    causal = j <= i
    recent = (j > i - (B - sink))
    isink = j < sink
    return causal & (recent | isink)

def keep_holonomic_strided(L, B, seq="S20"):
    """Dense recent window of size w=B//2, then a holonomically-strided sample of
    the deep past: density of kept older tokens ∝ holonomic attention weight at
    that distance (so the deep past degrades gracefully instead of going black).
    Total kept per query ≈ B."""
    w = max(2, B // 2)
    # build per-distance keep stride: stride(d) grows as the holonomic weight falls.
    # weight(d) = exp(cy_sieve_bias(d, tau=large)) normalized; stride = round(1/weight)
    taus = 128.0
    keep_row = torch.zeros(L, L, dtype=torch.bool)
    # precompute a stride schedule over distance buckets
    import numpy as np
    weights = np.array([math.exp(cy.cy_sieve_bias(d, seq, tau=taus)) for d in range(L)])
    weights = weights / weights[1] if L > 1 else weights      # normalize at d=1
    for i in range(L):
        row = keep_row[i]
        lo = max(0, i - w + 1)
        row[lo:i + 1] = True                                   # dense recent
        budget_left = B - (i + 1 - lo)
        # sample older tokens with probability ∝ weight(distance), greedily by weight
        if budget_left > 0 and lo > 0:
            ds = list(range(w, i + 1))                         # distances into the past
            ds_sorted = sorted(ds, key=lambda d: -weights[min(d, L - 1)])
            for d in ds_sorted[:budget_left]:
                row[i - d] = True
    return keep_row

KV_POLICIES = {
    "full":         lambda L, B: torch.tril(torch.ones(L, L, dtype=torch.bool)),
    "recent":       keep_recent,
    "sink+recent":  keep_sink_recent,
    "holo-strided": keep_holonomic_strided,
}


@torch.no_grad()
def ppl_with_kv_mask(model, data, ctx, device, keep_mask, n_batches=15, batch=8):
    """Eval ppl where attention is restricted to keep_mask (KV-budget proxy)."""
    model.eval()
    add_mask = torch.where(keep_mask, 0.0, float("-inf")).to(device)   # [L,L]
    # monkeypatch each block's attention by injecting the mask through pos_bias path
    orig = model._pos_bias
    def patched(L, dev):
        b = orig(L, dev)                       # [1,H,L,L] or None
        m = add_mask[:L, :L][None, None]
        return (b + m) if b is not None else m.expand(1, model.n_head, L, L)
    model._pos_bias = patched
    try:
        gen = torch.Generator().manual_seed(1234)
        it = qg.batch_iter(data, ctx, batch, device, gen)
        tot = cnt = 0
        for _ in range(n_batches):
            x, y = next(it); _, loss = model(x, targets=y)
            if math.isfinite(loss.item()): tot += loss.item(); cnt += 1
    finally:
        model._pos_bias = orig
    model.train(); return math.exp(tot / max(cnt, 1))


# ===========================================================================
# H-F — minimal gated linear attention (SSM-style), decay-gate init variants
# ===========================================================================

class GLALayer(nn.Module):
    """One gated-linear-attention layer with a per-head scalar decay α∈(0,1).
    O(L) memory recurrence: state_t = α·state_{t-1} + k_t⊗v_t ; out_t = q_t·state_t."""
    def __init__(self, d_model, n_head, decay_init):
        super().__init__()
        self.h = n_head; self.dh = d_model // n_head
        self.qkv = nn.Linear(d_model, 3 * d_model); self.proj = nn.Linear(d_model, d_model)
        self.ln = nn.LayerNorm(d_model)
        # logit so sigmoid(logit)=decay_init per head
        di = torch.tensor(decay_init, dtype=torch.float32).clamp(1e-3, 1 - 1e-3)
        self.decay_logit = nn.Parameter(torch.log(di / (1 - di)))

    def forward(self, x):
        B, L, D = x.shape; h, dh = self.h, self.dh
        q, k, v = self.ln(x).chunk(3, -1) if False else self.qkv(self.ln(x)).chunk(3, -1)
        q = q.view(B, L, h, dh); k = k.view(B, L, h, dh); v = v.view(B, L, h, dh)
        q = F.elu(q) + 1; k = F.elu(k) + 1                      # positive feature map
        alpha = torch.sigmoid(self.decay_logit)                 # [h]
        out = torch.zeros(B, L, h, dh)
        state = torch.zeros(B, h, dh, dh)                       # kv outer-product state
        for t in range(L):
            kt = k[:, t]; vt = v[:, t]                          # [B,h,dh]
            state = alpha[None, :, None, None] * state + kt[..., None] * vt[..., None, :]
            num = (q[:, t][..., None] * state).sum(-2)          # [B,h,dh]
            out[:, t] = num
        out = out.reshape(B, L, D)
        return x + self.proj(out)


class GLAModel(nn.Module):
    def __init__(self, vocab, d_model, n_layer, n_head, decay_init):
        super().__init__()
        self.wte = nn.Embedding(vocab, d_model)
        self.layers = nn.ModuleList([GLALayer(d_model, n_head, decay_init) for _ in range(n_layer)])
        self.ln_f = nn.LayerNorm(d_model); self.head = nn.Linear(d_model, vocab, bias=False)
        self.head.weight = self.wte.weight

    def forward(self, idx, targets=None):
        x = self.wte(idx)
        for l in self.layers: x = l(x)
        logits = self.head(self.ln_f(x))
        loss = None if targets is None else F.cross_entropy(
            logits.view(-1, logits.size(-1)), targets.view(-1), ignore_index=-100)
        return logits, loss


def holonomic_decay_init(n_head, seq="S20"):
    """Per-head decay α_h derived from the holonomic curve: steeper heads (faster
    forgetting) ↔ smaller α. Map the τ-ladder reach to α∈(0.85,0.999)."""
    reaches = [cy.effective_context(seq, t) for t in cy.alibi_style_tau_ladder(n_head)]
    r = torch.tensor(reaches, dtype=torch.float32).clamp(min=2)
    return (1 - 1.0 / r).clamp(0.85, 0.999).tolist()            # longer reach → α→1


def train_gla(decay_init, train_data, val_data, device, cfg=CFG, steps=400):
    torch.manual_seed(0)
    m = GLAModel(256, cfg["d_model"], 2, cfg["n_head"], decay_init).to(device)
    opt = torch.optim.AdamW(m.parameters(), lr=cfg["lr"], weight_decay=0.1)
    gen = torch.Generator().manual_seed(42)
    it = qg.batch_iter(train_data, 128, 8, device, gen)         # shorter ctx (GLA loop is slow)
    m.train()
    for step in range(1, steps + 1):
        x, y = next(it); _, loss = m(x, targets=y)
        opt.zero_grad(set_to_none=True); loss.backward()
        nn.utils.clip_grad_norm_(m.parameters(), 1.0); opt.step()
    # eval
    m.eval(); gen = torch.Generator().manual_seed(1234)
    it = qg.batch_iter(val_data, 128, 8, device, gen); tot = cnt = 0
    with torch.no_grad():
        for _ in range(10):
            x, y = next(it); _, loss = m(x, targets=y)
            if math.isfinite(loss.item()): tot += loss.item(); cnt += 1
    afinal = [round(float(a), 4) for a in torch.sigmoid(m.layers[0].decay_logit)]
    return math.exp(tot / max(cnt, 1)), afinal


# ===========================================================================
# Driver
# ===========================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", nargs="+", default=["HC", "HA", "HF"])
    ap.add_argument("--steps", type=int, default=CFG["steps"])
    ap.add_argument("--output", default="memory_experiments_results.json")
    args = ap.parse_args()
    CFG["steps"] = args.steps
    device = "cpu"
    tr, va, src = qg.load_corpus(max_chars=2_000_000)
    td, vd = qg.to_bytes(tr), qg.to_bytes(va)
    print(f"corpus={src} train={td.numel():,}B  device={device}  steps={CFG['steps']}")
    out = {"corpus": src, "cfg": CFG, "results": {}}

    # ---- H-C: quality reference (holo-γ vs alibi vs sliding) ----
    if "HC" in args.which:
        print("\n=== H-C: learnable-γ Holonomic-ALiBi vs baselines ===")
        hc = {}
        for s in ["alibi", "sliding", "holo_ladder_pos"]:
            t0 = time.perf_counter()
            m, _ = train_base(s, td, vd, device)
            p = ppl(m, vd, CFG["ctx"], device)
            hc[s] = round(p, 4); print(f"  {s:>16}: ppl {p:.3f}  ({time.perf_counter()-t0:.0f}s)")
        base = min(hc[k] for k in ("alibi", "sliding"))
        gain = (base - hc["holo_ladder_pos"]) / base * 100
        hc["gain_vs_best_baseline_pct"] = round(gain, 2)
        print(f"  -> holo gain vs best baseline: {gain:+.2f}%")
        out["results"]["H-C"] = hc

    # ---- H-A: KV-eviction at fixed budget (the memory lever) ----
    if "HA" in args.which:
        print("\n=== H-A: KV-cache eviction at fixed budget (memory win) ===")
        m, _ = train_base("holo_ladder_pos", td, vd, device)   # train once
        L = CFG["ctx"]; ha = {}
        full = ppl_with_kv_mask(m, vd, L, device, KV_POLICIES["full"](L, L))
        ha["full_ppl"] = round(full, 4)
        print(f"  full (B=L={L}): ppl {full:.3f}  [ceiling]")
        for B in [64, 128]:
            ha[f"B{B}"] = {}
            for pol in ["recent", "sink+recent", "holo-strided"]:
                mask = KV_POLICIES[pol](L, B)
                kept = mask.float().sum(1).mean().item()       # avg kept/query
                p = ppl_with_kv_mask(m, vd, L, device, mask)
                ha[f"B{B}"][pol] = {"ppl": round(p, 4), "avg_kept": round(kept, 1)}
                print(f"  B={B:3d} {pol:>13}: ppl {p:.3f} (avg kept {kept:.1f}, "
                      f"+{(p-full)/full*100:.1f}% vs full)")
        out["results"]["H-A"] = ha

    # ---- H-F: holonomic decay prior for GLA gates ----
    if "HF" in args.which:
        print("\n=== H-F: holonomic decay prior for gated linear attention ===")
        H = CFG["n_head"]; hf = {}
        variants = {
            "holo_init":   holonomic_decay_init(H),
            "retnet_fixed":[1 - 2 ** (-5 - i) for i in range(H)],   # RetNet-style
            "uniform_0.95":[0.95] * H,
        }
        for name, di in variants.items():
            t0 = time.perf_counter()
            p, afinal = train_gla(di, td, vd, device)
            hf[name] = {"ppl": round(p, 4), "decay_init": [round(x, 3) for x in di],
                        "decay_final": afinal}
            print(f"  {name:>13}: ppl {p:.3f}  α_final={afinal}  ({time.perf_counter()-t0:.0f}s)")
        out["results"]["H-F"] = hf

    json.dump(out, open(args.output, "w"), indent=2)
    print(f"\n-> {args.output}")
    return out


if __name__ == "__main__":
    main()
