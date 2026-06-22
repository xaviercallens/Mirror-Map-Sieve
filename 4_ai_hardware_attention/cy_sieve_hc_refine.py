#!/usr/bin/env python3
"""
cy_sieve_hc_refine.py — go further on H-C (the winning learnable-γ Holonomic-ALiBi
bias, +2% vs ALiBi). Two goals:

  1. ATTRIBUTION: is the +2% from the Calabi–Yau *shape* (the β=2 log-curvature on
     top of the linear slope), or just from making the slope *learnable*? We can't
     know until we compare against a learnable-ALiBi control and let the curvature
     be a free parameter that the model places itself.

  2. IMPROVEMENT: refined parameterizations that might push the gain further.

Central construction — the NESTED bias (per head h, distance d>=1):

      bias_h(d) = -a_h * d  +  b_h * log(d)          (a_h,b_h >= 0 learnable)

  * b_h = 0                  -> learnable ALiBi (pure linear)  [the control]
  * b_h = beta = 2           -> the CY-3fold log-curvature     [the H-C prior]
  * b_h learned freely       -> the model TELLS us where the curvature wants to be
                                 -> attributes the gain.

Schemes:
  alibi             fixed ALiBi slopes (baseline)
  alibi_learn       learnable per-head slope, NO log term  (b_h := 0)   [control]
  holo_fixed        the H-C winner: -gamma_h*(d*logλ - β*log d), gamma learnable
  nested_free       -a_h*d + b_h*log d, BOTH learnable, b init at CY value 2*a/logλ
  nested_curv0      same but b init 0 (does GD ADD curvature from a linear start?)
  log_only          -gamma_h*log S20(d) via the exact tiered curve (current holo)

CPU, tiny, minutes. Reuses qg corpus + ar TinyGPT.
Author: SocrateAI Laboratory (X. Callens) + Claude (Opus 4.8). License: MIT.
"""
from __future__ import annotations
import argparse, json, math, os, sys, time
import torch, torch.nn as nn, torch.nn.functional as F

sys.path.insert(0, os.path.dirname(__file__))
import cy_sieve_reference as cy
import cy_sieve_quality_gate as qg
import cy_sieve_autoresearch as ar

LOGLAMBDA = cy.S20_LOG_LAMBDA   # 3.7622
BETA = cy.S20_BETA              # 2.0


class NestedBias(nn.Module):
    """bias_h(d) = -softplus(a_raw_h)*d + b_h*log d, d>=1; 0 at d=0.
    a (slope) is softplus-positive; b (log-curvature) is free (can be 0/+/-),
    optionally frozen to isolate the control. Tracks where b lands for attribution.
    O(L): two scalars per head over precomputed d and log d vectors."""
    def __init__(self, H, max_d, a_init, b_init, learn_b=True, learn_a=True):
        super().__init__()
        d = torch.arange(max_d + 1, dtype=torch.float32)
        self.register_buffer("d", d)
        self.register_buffer("logd", torch.where(d >= 1, torch.log(d.clamp(min=1)), torch.zeros_like(d)))
        a = torch.tensor(a_init, dtype=torch.float32).clamp(min=1e-4)
        self.a_raw = nn.Parameter(torch.log(torch.expm1(a)), requires_grad=learn_a)  # softplus^-1
        self.b = nn.Parameter(torch.tensor(b_init, dtype=torch.float32), requires_grad=learn_b)

    def slopes(self):
        return F.softplus(self.a_raw)

    def forward(self, L, device):
        a = self.slopes().to(device)                  # [H]
        b = self.b.to(device)                         # [H]
        idx = torch.arange(L, device=device)
        dist = (idx[:, None] - idx[None, :]).clamp(min=0)        # [L,L]
        dd = self.d.to(device)[dist.clamp(max=self.d.numel() - 1)]
        ll = self.logd.to(device)[dist.clamp(max=self.logd.numel() - 1)]
        return (-a[:, None, None] * dd[None] + b[:, None, None] * ll[None])

    def report(self):
        return {"slope_a": [round(float(x), 4) for x in self.slopes().detach().cpu()],
                "logcurv_b": [round(float(x), 4) for x in self.b.detach().cpu()]}


def make_refined(name, H, max_d):
    # ALiBi slopes m_h = 2^(-8h/H); CY linear slope per head ~ gamma_h*logλ.
    alibi_slopes = [2.0 ** (-8.0 * h / H) for h in range(1, H + 1)]
    gamma_ladder = [1.0 / t for t in cy.alibi_style_tau_ladder(H)]
    a_cy = [g * LOGLAMBDA for g in gamma_ladder]            # CY linear coefficient
    b_cy = [g * BETA for g in gamma_ladder]                 # CY log-curvature coeff
    if name == "learned_pos":    return True, None, None      # learned-abs control
    if name == "alibi":          return False, None, "alibi"
    if name == "alibi_learn":    # learnable slope, NO log term (control)
        return False, (lambda: NestedBias(H, max_d, alibi_slopes, [0.0] * H, learn_b=False)), None
    if name == "holo_fixed":     # the H-C winner from autoresearch
        return False, (lambda: ar.HolonomicBias(H, max_d, gamma_ladder, clamp_pos=True)), None
    if name == "nested_free":    # both learnable, b init at CY curvature
        return False, (lambda: NestedBias(H, max_d, a_cy, b_cy, learn_b=True)), None
    if name == "nested_curv0":   # both learnable, b init 0 (does GD add curvature?)
        return False, (lambda: NestedBias(H, max_d, alibi_slopes, [0.0] * H, learn_b=True)), None
    if name == "log_only":       # -gamma*logS20(d) exact tiered (== holo)
        return False, (lambda: ar.HolonomicBias(H, max_d, gamma_ladder)), None
    raise ValueError(name)


# local CPU smoke config; FULL (GPU) mirrors the trustworthy v2 setup.
CFG = dict(d_model=128, n_layer=3, n_head=4, d_ff=512, ctx=512, batch=12,
           steps=800, lr=3e-4, max_extrap=1024, gamma_l2=1e-3)
FULL = dict(d_model=512, n_layer=8, n_head=8, d_ff=2048, ctx=512, batch=24,
            steps=8000, lr=3e-4, max_extrap=2048, gamma_l2=1e-3,
            eval_every=400, patience=4, max_chars=16_000_000)


def train_eval(name, td, vd, device, cfg=CFG):
    torch.manual_seed(0)
    H, maxd = cfg["n_head"], cfg["max_extrap"]
    learned_pos, factory, static = make_refined(name, H, maxd)
    bias_mod = factory() if factory else None
    model = ar.TinyGPT(256, cfg["d_model"], cfg["n_layer"], H, cfg["d_ff"],
                       maxd, learned_pos, bias_mod).to(device)
    if static:
        model._static = ar.static_bias(static, H, cfg["ctx"], device); model._static_scheme = static
    opt = torch.optim.AdamW(model.parameters(), lr=cfg["lr"], weight_decay=0.1)
    gen = torch.Generator().manual_seed(42)
    it = qg.batch_iter(td, cfg["ctx"], cfg["batch"], device, gen)
    eval_every = cfg.get("eval_every", 0); patience_max = cfg.get("patience", 4)
    best_val = float("inf"); best_res = None; best_rep = None; patience = 0
    model.train()
    for step in range(1, cfg["steps"] + 1):
        x, y = next(it); _, loss = model(x, targets=y)
        # light L2 only on the slope (NOT the curvature b — we want b free)
        if cfg.get("gamma_l2") and bias_mod is not None and hasattr(bias_mod, "slopes"):
            loss = loss + cfg["gamma_l2"] * (bias_mod.slopes() ** 2).sum()
        elif cfg.get("gamma_l2") and bias_mod is not None and hasattr(bias_mod, "scales"):
            loss = loss + cfg["gamma_l2"] * (bias_mod.scales() ** 2).sum()
        opt.zero_grad(set_to_none=True); loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
        if eval_every and step % eval_every == 0:
            vp = qg_eval(model, vd, cfg["ctx"], device)
            if vp < best_val - 1e-3:
                best_val = vp; patience = 0
                best_res = {str(L): round(qg_eval(model, vd, L, device), 4)
                            for L in [cfg["ctx"], 2 * cfg["ctx"]] if L <= maxd}
                best_rep = bias_mod.report() if (bias_mod is not None and hasattr(bias_mod, "report")) else None
            else:
                patience += 1
                if patience >= patience_max:
                    print(f"    {name} early-stop @ {step} (best val {best_val:.3f})")
                    break
    if best_res is not None:
        res, rep = best_res, best_rep
    else:
        res = {str(L): round(qg_eval(model, vd, L, device), 4)
               for L in [cfg["ctx"], 2 * cfg["ctx"]] if L <= maxd}
        rep = bias_mod.report() if (bias_mod is not None and hasattr(bias_mod, "report")) else None
    if device == "cuda":
        del model; torch.cuda.empty_cache()
    return {"scheme": name, "ppl_by_ctx": res, "params": sum(p.numel() for p in model.parameters()),
            "bias_report": rep, "best_val": round(best_val, 4) if best_res else None}


@torch.no_grad()
def qg_eval(model, data, ctx, device, n_batches=15, batch=8):
    model.eval()
    if getattr(model, "_static_scheme", None):
        model._static = ar.static_bias(model._static_scheme, model.n_head, ctx, device)
    gen = torch.Generator().manual_seed(1234)
    it = qg.batch_iter(data, ctx, batch, device, gen); tot = cnt = 0
    for _ in range(n_batches):
        x, y = next(it); _, loss = model(x, targets=y)
        if math.isfinite(loss.item()): tot += loss.item(); cnt += 1
    model.train(); return math.exp(tot / max(cnt, 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--schemes", nargs="+",
                    default=["alibi", "alibi_learn", "holo_fixed", "nested_free",
                             "nested_curv0", "log_only"])
    ap.add_argument("--preset", choices=["smoke", "full"], default="smoke")
    ap.add_argument("--steps", type=int, default=None)
    ap.add_argument("--output", default="hc_refine_results.json")
    args = ap.parse_args()
    if args.preset == "full":
        CFG.clear(); CFG.update(FULL)
    if args.steps:
        CFG["steps"] = args.steps
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tr, va, src = qg.load_corpus(max_chars=CFG.get("max_chars", 2_000_000))
    td, vd = qg.to_bytes(tr), qg.to_bytes(va)
    epochs = CFG["steps"] * CFG["batch"] * CFG["ctx"] / max(td.numel(), 1)
    print(f"H-C REFINE ({args.preset}) | corpus={src} train={td.numel():,}B "
          f"steps={CFG['steps']} ~{epochs:.1f}ep device={device}\n")
    runs = []
    for s in args.schemes:
        t0 = time.perf_counter()
        r = train_eval(s, td, vd, device)
        runs.append(r)
        Lk = str(CFG["ctx"])
        extra = ""
        if r["bias_report"] and "logcurv_b" in r["bias_report"]:
            extra = f"  b(logcurv)={r['bias_report']['logcurv_b']}"
        print(f"  {s:>13}: ppl@{Lk} {r['ppl_by_ctx'].get(Lk)}  "
              f"@{2*CFG['ctx']} {r['ppl_by_ctx'].get(str(2*CFG['ctx']))}  "
              f"({time.perf_counter()-t0:.0f}s){extra}")
    Lk = str(CFG["ctx"])
    ranked = sorted(runs, key=lambda r: r["ppl_by_ctx"].get(Lk, 9e9))
    base_ppls = [r["ppl_by_ctx"].get(Lk, 9e9) for r in runs
                 if r["scheme"] in ("alibi", "alibi_learn", "learned_pos")]
    best_base = min(base_ppls) if base_ppls else float("inf")
    print("\n  RANKING:", [(r["scheme"], r["ppl_by_ctx"].get(Lk)) for r in ranked])
    print(f"  best learnable/fixed-ALiBi baseline ppl: {best_base}")
    best = ranked[0]
    print(f"  WINNER: {best['scheme']} {best['ppl_by_ctx'].get(Lk)} "
          f"({(best_base-best['ppl_by_ctx'].get(Lk))/best_base*100:+.2f}% vs ALiBi family)")
    # attribution note
    nf = next((r for r in runs if r["scheme"] == "nested_free"), None)
    if nf and nf["bias_report"]:
        print(f"  ATTRIBUTION — nested_free learned log-curvature b = "
              f"{nf['bias_report']['logcurv_b']} (CY prior β≈2 per unit slope; "
              f"b≈0 ⇒ gain is learnability, b>0 ⇒ CY shape helps)")
    json.dump({"corpus": src, "cfg": CFG, "runs": runs,
               "best": best["scheme"], "best_baseline_ppl": best_base},
              open(args.output, "w"), indent=2)
    print(f"\n-> {args.output}")


if __name__ == "__main__":
    main()
