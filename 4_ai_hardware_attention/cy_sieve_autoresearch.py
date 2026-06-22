#!/usr/bin/env python3
"""
cy_sieve_autoresearch.py — propose→screen→select loop (Karpathy-autoresearch style)
to overturn the §5 KILL, testing 10 hypotheses built on two directions:

  A) Holonomic-ALiBi: bias_h(d) = -gamma_h * log S20(d), gamma_h LEARNABLE per head.
  B) Comet: 0 bias for d<=W (exact local), -gamma_h * log S20(d-W) for d>W.

The decisive change vs the killed design: gamma is an nn.Parameter, so gradient
descent picks the steepness (the geometry only fixes the curve SHAPE). The O(L)
bias-generation property is preserved — gamma is just H scalars over the
recurrence-generated log-S20 vector.

Phases:
  --phase screen : train all schemes at reduced budget; rank; write a manifest.
  --phase full   : train the named schemes at full budget; emit verdict.

Reuses cy_sieve_quality_gate's corpus loader + TinyGPT skeleton, but the attention
bias is a LEARNABLE module here (the gate's biases were static).

Author: SocrateAI Laboratory (X. Callens) + Claude (Opus 4.8). License: MIT.
"""
from __future__ import annotations
import argparse, json, math, os, sys, time

import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(__file__))
import cy_sieve_reference as cy
import cy_sieve_quality_gate as qg          # corpus loader, byte tokenizer


# ---------------------------------------------------------------------------
# Learnable positional-bias modules. Each returns an additive [H, L, L] bias
# (causal masking applied by the model). log S20(d) is a fixed buffer; gamma is
# the only learnable part (per head). This keeps O(L) generation: the shape is
# the precomputed length-L log-S20 vector, scaled by H scalars.
# ---------------------------------------------------------------------------

def _logS20_vector(max_d, seq="S20"):
    """v[d] = log S20(d) for d>=1, v[0]=0. Uses the reference's tiered bias:
    exact log within the INT64 window (d<=13) and the THEORY asymptotic
    (d*logλ - β*log d + logC) beyond — NOT exact S20(d), which is an
    astronomically large bignum for large d (computing it would hang). Since
    cy.cy_sieve_bias(d, tau=1) == -log S20(d), we negate it."""
    v = [0.0] + [-cy.cy_sieve_bias(d, seq, tau=1.0) for d in range(1, max_d + 1)]
    return torch.tensor(v, dtype=torch.float32)


class HolonomicBias(nn.Module):
    """bias_h(d) = -softplus(gamma_h) * logS20(d)   (Direction A).
    softplus keeps the scale >0 (a decay, never a sign flip). gamma init sets the
    starting steepness; GD flattens/steepens per head."""
    def __init__(self, H, max_d, init_gamma, seq="S20", curvature_only=False,
                 clamp_pos=False):
        super().__init__()
        if curvature_only:                 # -beta*log d only (no linear slope)
            d = torch.arange(max_d + 1, dtype=torch.float32)
            shape = torch.where(d >= 1, cy.S20_BETA * torch.log(d.clamp(min=1)),
                                torch.zeros_like(d))
        else:
            shape = _logS20_vector(max_d, seq)
        self.register_buffer("shape", shape)          # [max_d+1], >=0, increasing
        g = torch.tensor(init_gamma, dtype=torch.float32)
        # store raw param; effective scale = softplus(raw) (>0) or clamped
        self.raw = nn.Parameter(torch.log(torch.expm1(g.clamp(min=1e-4))))  # softplus^-1
        self.clamp_pos = clamp_pos

    def scales(self):
        s = F.softplus(self.raw)
        return s.clamp(min=0.0) if self.clamp_pos else s

    def forward(self, L, device):
        s = self.scales().to(device)                  # [H]
        idx = torch.arange(L, device=device)
        d = (idx[:, None] - idx[None, :]).clamp(min=0)  # causal distance
        shp = self.shape.to(device)[d.clamp(max=self.shape.numel() - 1)]  # [L,L]
        return -s[:, None, None] * shp[None]           # [H,L,L]


class CometBias(nn.Module):
    """Direction B: 0 for d<=W (exact local), -gamma_h*logS20(d-W) for d>W.
    Optional linear ramp over [W-ramp, W] for a soft onset (no hard cliff)."""
    def __init__(self, H, max_d, window, init_gamma, seq="S20", ramp=0,
                 per_head_windows=None):
        super().__init__()
        self.register_buffer("shape", _logS20_vector(max_d, seq))
        g = torch.tensor(init_gamma, dtype=torch.float32)
        self.raw = nn.Parameter(torch.log(torch.expm1(g.clamp(min=1e-4))))
        self.window = window
        self.ramp = ramp
        self.per_head_windows = per_head_windows   # list[H] or None

    def scales(self):
        return F.softplus(self.raw)

    def forward(self, L, device):
        s = self.scales().to(device)               # [H]
        H = s.numel()
        idx = torch.arange(L, device=device)
        d = (idx[:, None] - idx[None, :]).clamp(min=0).float()   # [L,L]
        shp = self.shape.to(device)
        out = torch.zeros(H, L, L, device=device)
        for h in range(H):
            W = self.per_head_windows[h] if self.per_head_windows else self.window
            beyond = (d - W).clamp(min=0).long().clamp(max=shp.numel() - 1)
            tail = -s[h] * shp[beyond]             # [L,L]
            if self.ramp > 0:
                # linear 0->1 ramp of the tail over [W-ramp, W]
                w = ((d - (W - self.ramp)) / self.ramp).clamp(0, 1)
                tail = tail * w
            out[h] = torch.where(d > W, tail, torch.zeros_like(tail))
        return out


# Non-learnable baselines (re-used shapes from the gate, as fixed [H,L,L]).
def static_bias(scheme, H, L, device, window=512):
    if scheme == "alibi":
        return qg.alibi_bias(H, L, device, torch.float32)
    if scheme == "sliding":
        return qg.sliding_bias(H, L, device, torch.float32, window=window)
    return None   # learned-absolute => no bias (uses wpe)


# ---------------------------------------------------------------------------
# TinyGPT with a pluggable (possibly learnable) bias module.
# ---------------------------------------------------------------------------

class Block(nn.Module):
    def __init__(self, d_model, n_head, d_ff):
        super().__init__()
        self.ln1 = nn.LayerNorm(d_model); self.ln2 = nn.LayerNorm(d_model)
        self.qkv = nn.Linear(d_model, 3 * d_model); self.proj = nn.Linear(d_model, d_model)
        self.mlp = nn.Sequential(nn.Linear(d_model, d_ff), nn.GELU(), nn.Linear(d_ff, d_model))
        self.n_head = n_head; self.d_head = d_model // n_head

    def forward(self, x, pos_bias):
        B, L, _ = x.shape
        h = self.ln1(x)
        q, k, v = self.qkv(h).split(h.shape[-1], dim=-1)
        q = q.view(B, L, self.n_head, self.d_head).transpose(1, 2)
        k = k.view(B, L, self.n_head, self.d_head).transpose(1, 2)
        v = v.view(B, L, self.n_head, self.d_head).transpose(1, 2)
        out = F.scaled_dot_product_attention(
            q, k, v, attn_mask=pos_bias, is_causal=(pos_bias is None))
        out = out.transpose(1, 2).contiguous().view(B, L, -1)
        x = x + self.proj(out)
        return x + self.mlp(self.ln2(x))


class TinyGPT(nn.Module):
    def __init__(self, vocab, d_model, n_layer, n_head, d_ff, max_len,
                 learned_pos, bias_module):
        super().__init__()
        self.wte = nn.Embedding(vocab, d_model)
        self.learned_pos = learned_pos
        if learned_pos:
            self.wpe = nn.Embedding(max_len, d_model)
        self.blocks = nn.ModuleList([Block(d_model, n_head, d_ff) for _ in range(n_layer)])
        self.ln_f = nn.LayerNorm(d_model)
        self.head = nn.Linear(d_model, vocab, bias=False); self.head.weight = self.wte.weight
        self.bias_module = bias_module       # nn.Module or None (learnable lives here)
        self.n_head = n_head

    def _pos_bias(self, L, device):
        if self.bias_module is None and not hasattr(self, "_static"):
            return None
        if self.bias_module is not None:
            b = self.bias_module(L, device)             # [H,L,L], differentiable
        else:
            b = self._static[:, :L, :L]
        causal = torch.tril(torch.ones(L, L, device=device, dtype=torch.bool))
        return b.masked_fill(~causal[None], float("-inf"))[None]   # [1,H,L,L]

    def forward(self, idx, targets=None):
        B, L = idx.shape
        x = self.wte(idx)
        if self.learned_pos:
            x = x + self.wpe(torch.arange(L, device=idx.device))[None]
        pb = self._pos_bias(L, idx.device)
        for blk in self.blocks:
            x = blk(x, pb)
        logits = self.head(self.ln_f(x))
        loss = None
        if targets is not None:
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)), targets.view(-1),
                                   ignore_index=-100)
        return logits, loss


# ---------------------------------------------------------------------------
# Hypothesis registry — returns (learned_pos, bias_module_factory, static_scheme)
# ---------------------------------------------------------------------------

def make_scheme(name, H, max_d):
    ladder = cy.alibi_style_tau_ladder(H)
    # γ-ladder mapped from τ-ladder: gamma_h = 1/tau_h (so steep heads ~ small tau)
    gamma_ladder = [1.0 / t for t in ladder]
    if name == "learned":   return True,  None, None
    if name == "alibi":     return False, None, "alibi"
    if name == "sliding":   return False, None, "sliding"
    if name == "holo_ladder":
        return False, (lambda: HolonomicBias(H, max_d, gamma_ladder)), None
    if name == "holo_tiny":
        return False, (lambda: HolonomicBias(H, max_d, [0.02] * H)), None
    if name == "holo_curv":
        return False, (lambda: HolonomicBias(H, max_d, gamma_ladder, curvature_only=True)), None
    if name == "holo_ladder_pos":
        return False, (lambda: HolonomicBias(H, max_d, gamma_ladder, clamp_pos=True)), None
    # NOTE: comet windows MUST be < training ctx (512) or the CY tail never
    # activates during training and γ gets no gradient. So windows are 64/128/256
    # (the "512" names are kept for continuity but mapped to a sub-ctx window).
    if name == "comet512_fixed":      # fixed γ, window 128
        def f():
            b = CometBias(H, max_d, 128, [1/128.0] * H); b.raw.requires_grad_(False); return b
        return False, f, None
    if name == "comet512_learn":      # learnable γ, window 128 (the headline A×B bet)
        return False, (lambda: CometBias(H, max_d, 128, [1/128.0] * H)), None
    if name == "comet256_learn":      # window 64
        return False, (lambda: CometBias(H, max_d, 64, [1/128.0] * H)), None
    if name == "comet1024_learn":     # window 256
        return False, (lambda: CometBias(H, max_d, 256, [1/128.0] * H)), None
    if name == "comet_perhead_W":     # per-head windows 8..256, all < ctx
        whs = [min(8 * 2 ** h, 256) for h in range(H)]
        return False, (lambda: CometBias(H, max_d, 128, [1/128.0] * H, per_head_windows=whs)), None
    if name == "comet512_soft":       # window 128, soft ramp
        return False, (lambda: CometBias(H, max_d, 128, [1/128.0] * H, ramp=64)), None
    raise ValueError(name)


ALL_SCHEMES = ["learned", "alibi", "sliding",
               "holo_ladder", "holo_tiny", "holo_curv", "holo_ladder_pos",
               "comet512_fixed", "comet512_learn", "comet256_learn",
               "comet1024_learn", "comet_perhead_W", "comet512_soft"]


# ---------------------------------------------------------------------------
# Train / eval
# ---------------------------------------------------------------------------

def train_one(name, train_data, val_data, cfg, device):
    torch.manual_seed(0)
    H = cfg["n_head"]; max_d = cfg["max_extrap"]
    learned_pos, factory, static = make_scheme(name, H, max_d)
    bias_mod = factory() if factory else None
    model = TinyGPT(256, cfg["d_model"], cfg["n_layer"], H, cfg["d_ff"],
                    max_d, learned_pos, bias_mod).to(device)
    if static:
        model._static = static_bias(static, H, cfg["ctx"], device,
                                    window=cfg.get("window", 512))
        # static bias for eval at other L rebuilt on the fly:
        model._static_scheme = static
    n_params = sum(p.numel() for p in model.parameters())
    opt = torch.optim.AdamW(model.parameters(), lr=cfg["lr"], betas=(0.9, 0.95),
                            weight_decay=0.1)
    gen = torch.Generator().manual_seed(42)
    it = qg.batch_iter(train_data, cfg["ctx"], cfg["batch"], device, gen)
    # Anti-overfit (v2): γ-regularization pulls the learnable scale toward FLAT
    # (the killed/overfit run let γ drift steeper); + early-stopping on a held-out
    # val ppl checkpoint (the over-trained run kept going past the val optimum).
    gamma_l2 = cfg.get("gamma_l2", 0.0)
    eval_every = cfg.get("eval_every", 0)        # 0 disables early-stop
    best_val = float("inf"); best_res = None; best_gamma = None; patience = 0
    max_patience = cfg.get("patience", 3)

    model.train(); t0 = time.perf_counter()
    for step in range(1, cfg["steps"] + 1):
        x, y = next(it)
        _, loss = model(x, targets=y)
        if gamma_l2 > 0 and bias_mod is not None and hasattr(bias_mod, "scales"):
            loss = loss + gamma_l2 * (bias_mod.scales() ** 2).sum()
        opt.zero_grad(set_to_none=True); loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
        if step % max(1, cfg["steps"] // 4) == 0 or step == 1:
            extra = ""
            if bias_mod is not None and hasattr(bias_mod, "scales"):
                g = bias_mod.scales().detach().cpu()
                extra = f" | gamma[min,med,max]={g.min():.4f},{g.median():.4f},{g.max():.4f}"
            print(f"    {name:>16} step {step:>5}/{cfg['steps']} loss {loss.item():.4f}{extra}")
        # early-stop on val ppl @ train ctx
        if eval_every and step % eval_every == 0:
            vp = eval_ppl(model, val_data, cfg["ctx"], device)
            if vp < best_val - 1e-3:
                best_val = vp; patience = 0
                best_res = {str(L): round(eval_ppl(model, val_data, L, device), 4)
                            for L in [cfg["ctx"], 2 * cfg["ctx"], 4 * cfg["ctx"]]
                            if L <= max_d}
                if bias_mod is not None and hasattr(bias_mod, "scales"):
                    best_gamma = [round(float(v), 5) for v in bias_mod.scales().detach().cpu()]
            else:
                patience += 1
                if patience >= max_patience:
                    print(f"    {name:>16} early-stop at step {step} (best val {best_val:.3f})")
                    break
    train_s = time.perf_counter() - t0

    # use early-stop checkpoint if we have one, else final
    if best_res is not None:
        res, gamma_final = best_res, best_gamma
    else:
        res = {str(L): round(eval_ppl(model, val_data, L, device), 4)
               for L in [cfg["ctx"], 2 * cfg["ctx"], 4 * cfg["ctx"]] if L <= max_d}
        gamma_final = ([round(float(v), 5) for v in bias_mod.scales().detach().cpu()]
                       if bias_mod is not None and hasattr(bias_mod, "scales") else None)
    del model
    if device == "cuda":
        torch.cuda.empty_cache()
    return {"scheme": name, "params": n_params, "train_seconds": round(train_s, 1),
            "ppl_by_ctx": res, "gamma_final": gamma_final, "best_val": round(best_val, 4)
            if best_res is not None else None}


@torch.no_grad()
def eval_ppl(model, data, ctx, device, n_batches=20, batch=8):
    model.eval()
    if getattr(model, "_static_scheme", None):    # rebuild static bias at this L
        model._static = static_bias(model._static_scheme, model.n_head, ctx, device)
    gen = torch.Generator().manual_seed(1234)
    it = qg.batch_iter(data, ctx, batch, device, gen)
    tot = cnt = 0
    for _ in range(n_batches):
        x, y = next(it)
        _, loss = model(x, targets=y)
        if math.isfinite(loss.item()):
            tot += loss.item(); cnt += 1
    model.train()
    return math.exp(tot / max(cnt, 1))


# v2 configs: γ-regularization + val early-stop to fight the overfitting that
# inverted the screen→full ranking. The corpus is also enlarged (see main()).
SCREEN = dict(d_model=384, n_layer=6, n_head=6, d_ff=1536, ctx=512, batch=16,
              steps=2000, lr=3e-4, max_extrap=2048, window=512,
              gamma_l2=1e-3, eval_every=250, patience=3, max_chars=8_000_000)
FULL = dict(d_model=512, n_layer=8, n_head=8, d_ff=2048, ctx=512, batch=24,
            steps=8000, lr=3e-4, max_extrap=2048, window=512,
            gamma_l2=1e-3, eval_every=400, patience=4, max_chars=16_000_000)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["screen", "full"], default="screen")
    ap.add_argument("--schemes", nargs="+", default=None,
                    help="full-phase: which schemes (default: top-3 from manifest + baselines)")
    ap.add_argument("--manifest", default="autoresearch_screen.json")
    ap.add_argument("--output", default=None)
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    cfg = dict(SCREEN if args.phase == "screen" else FULL)
    tr, va, src = qg.load_corpus(max_chars=cfg.get("max_chars", 2_000_000))
    train_data, val_data = qg.to_bytes(tr), qg.to_bytes(va)
    epochs = cfg["steps"] * cfg["batch"] * cfg["ctx"] / max(train_data.numel(), 1)
    print("=" * 76)
    print(f"  CY-Sieve AUTORESEARCH v2 — phase={args.phase} on {device} | corpus={src}")
    print(f"  arch d_model={cfg['d_model']} L={cfg['n_layer']} H={cfg['n_head']} "
          f"ctx={cfg['ctx']} steps={cfg['steps']} | train {train_data.numel():,}B "
          f"~{epochs:.1f} epochs | gamma_l2={cfg.get('gamma_l2')} early-stop@{cfg.get('eval_every')}")
    print("=" * 76)

    if args.phase == "screen":
        schemes = ALL_SCHEMES
    else:
        schemes = args.schemes or _top3_plus_baselines(args.manifest)
    print(f"  schemes: {schemes}\n")

    runs = []
    for s in schemes:
        print(f"[{s}]")
        try:
            runs.append(train_one(s, train_data, val_data, cfg, device))
        except Exception as e:
            print(f"    ERROR {s}: {e}")
            runs.append({"scheme": s, "error": str(e)})
        print()

    Lk = str(cfg["ctx"])
    ranked = sorted([r for r in runs if r.get("ppl_by_ctx")],
                    key=lambda r: r["ppl_by_ctx"].get(Lk, 9e9))
    out = {"phase": args.phase, "device": device, "corpus_source": src,
           "config": cfg, "runs": runs,
           "ranking_by_train_ppl": [(r["scheme"], r["ppl_by_ctx"].get(Lk)) for r in ranked]}

    if args.phase == "screen":
        cy_ranked = [r["scheme"] for r in ranked
                     if r["scheme"] not in ("learned", "alibi", "sliding")]
        out["top3_cy"] = cy_ranked[:3]
        best_base = min((r["ppl_by_ctx"].get(Lk, 9e9)
                         for r in runs if r["scheme"] in ("learned", "alibi", "sliding")),
                        default=9e9)
        out["best_baseline_ppl"] = best_base

    outpath = args.output or args.manifest if args.phase == "screen" else (args.output or "autoresearch_full.json")
    json.dump(out, open(outpath, "w"), indent=2)
    print("=" * 76)
    print("  RANKING (val ppl @ train ctx):")
    for s, p in out["ranking_by_train_ppl"]:
        print(f"    {s:>16}: {p}")
    if args.phase == "screen":
        print(f"  -> TOP-3 CY hypotheses: {out['top3_cy']}")
    print(f"  -> {outpath}")
    print("=" * 76)
    return out


def _top3_plus_baselines(manifest):
    m = json.load(open(manifest))
    return m["top3_cy"] + ["learned", "sliding"]   # full run vs run-3's winners


if __name__ == "__main__":
    main()
