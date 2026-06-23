#!/usr/bin/env python3
"""
cy_sieve_bias_families.py — autoresearch bake-off of LEARNABLE positional-bias
families (Karpathy-style propose→screen→select). Lesson from S20: adaptability >
mathematical elegance; avoid fixed sequences. Every family here is fully learnable.

Top-5 selected by the user's ★ rating (plus controls), each O(L)-cheap:

  alibi_fixed   -m_h*d                          ★ baseline control (fixed ALiBi)
  alibi_learn   -a_h*d                           learnable slope (the +3.8% control)
  linlog        -a_h*d + b_h*log(d)              ★★★★★ learnable-ALiBi (the +8% winner)
  exp_decay     -a_h*d  (== linear in log-space) ★★★★ exponential e^{-λd}; here the
                                                  additive log-bias IS -λd, so we add a
                                                  learnable *scale* s_h on exp side:
                                                  bias=log(s_h)+(-a_h*d) → folds to slope
  hybrid        0 for d<=W_h (learnable softded);★★★★★ local window + gentle linlog tail
                -a_h*(d-W)+b_h*log(d-W) beyond
  fourier       -a_h*d + Σ_k c_hk*sin(ω_k d+φ)  ★★★★ low-freq Fourier features on top
                                                  of a learnable linear trend
  cheby         -a_h*d + Σ_k g_hk*T_k(dn)        ★★★ Chebyshev basis on normalized dist

We screen the top-5 (linlog, hybrid, fourier, exp_decay, alibi_learn) + the fixed
ALiBi control. CPU-first to "simulate the interest", then GPU.

Author: SocrateAI Laboratory (X. Callens) + Claude (Opus 4.8). License: MIT.
"""
from __future__ import annotations
import argparse, json, math, os, sys, time
import torch, torch.nn as nn, torch.nn.functional as F

sys.path.insert(0, os.path.dirname(__file__))
import cy_sieve_quality_gate as qg
import cy_sieve_autoresearch as ar


def _alibi_slopes(H):
    return [2.0 ** (-8.0 * h / H) for h in range(1, H + 1)]


class LinLogBias(nn.Module):
    """-a_h*d + b_h*log d (a softplus-positive, b free). The proven family."""
    def __init__(self, H, max_d, learn_slope=True):
        super().__init__()
        d = torch.arange(max_d + 1, dtype=torch.float32)
        self.register_buffer("d", d)
        self.register_buffer("logd", torch.where(d >= 1, torch.log(d.clamp(min=1)), torch.zeros_like(d)))
        a = torch.tensor(_alibi_slopes(H)).clamp(min=1e-4)
        self.a_raw = nn.Parameter(torch.log(torch.expm1(a)), requires_grad=learn_slope)
        self.b = nn.Parameter(torch.zeros(H))
        self.use_log = True
    def forward(self, L, device):
        a = F.softplus(self.a_raw).to(device); b = self.b.to(device)
        idx = torch.arange(L, device=device); dist = (idx[:, None] - idx[None, :]).clamp(min=0)
        dd = self.d.to(device)[dist.clamp(max=self.d.numel()-1)]
        ll = self.logd.to(device)[dist.clamp(max=self.logd.numel()-1)]
        out = -a[:, None, None] * dd[None]
        if self.use_log:
            out = out + b[:, None, None] * ll[None]
        return out
    def report(self):
        return {"a": [round(float(x),4) for x in F.softplus(self.a_raw)],
                "b": [round(float(x),4) for x in self.b.detach()]}


class AlibiLearn(LinLogBias):
    """-a_h*d only (learnable slope, no log term) — the +3.8% control."""
    def __init__(self, H, max_d):
        super().__init__(H, max_d, learn_slope=True); self.use_log = False
        self.b.requires_grad_(False)


class AlibiFixed(nn.Module):
    """-m_h*d with fixed ALiBi slopes (no learnable params) — the baseline."""
    def __init__(self, H, max_d):
        super().__init__()
        self.register_buffer("m", torch.tensor(_alibi_slopes(H)))
    def forward(self, L, device):
        m = self.m.to(device); idx = torch.arange(L, device=device)
        dist = (idx[:, None] - idx[None, :]).clamp(min=0).float()
        return -m[:, None, None] * dist[None]
    def report(self): return {"m": [round(float(x),4) for x in self.m]}


class HybridBias(nn.Module):
    """0 for d<=W_h (learnable per-head window via softplus), then
    -a_h*(d-W)+b_h*log(d-W) for d>W. Local exact + gentle tail (★★★★★)."""
    def __init__(self, H, max_d, w_init=64):
        super().__init__()
        self.max_d = max_d
        a = torch.tensor(_alibi_slopes(H)).clamp(min=1e-4)
        self.a_raw = nn.Parameter(torch.log(torch.expm1(a)))
        self.b = nn.Parameter(torch.zeros(H))
        self.w_raw = nn.Parameter(torch.log(torch.expm1(torch.tensor(float(w_init)))).repeat(H))
    def windows(self): return F.softplus(self.w_raw)
    def forward(self, L, device):
        a = F.softplus(self.a_raw).to(device); b = self.b.to(device); W = self.windows().to(device)
        idx = torch.arange(L, device=device); dist = (idx[:, None] - idx[None, :]).clamp(min=0).float()  # [L,L]
        H = a.numel(); out = torch.zeros(H, L, L, device=device)
        for h in range(H):
            beyond = (dist - W[h]).clamp(min=0)
            tail = -a[h]*beyond + b[h]*torch.log(beyond.clamp(min=1))
            # soft gate: 0 inside window, tail outside (sigmoid ramp of width ~4)
            gate = torch.sigmoid((dist - W[h]))
            out[h] = gate * tail
        return out
    def report(self): return {"a":[round(float(x),4) for x in F.softplus(self.a_raw)],
                              "W":[round(float(x),1) for x in self.windows()]}


class FourierBias(nn.Module):
    """-a_h*d + Σ_k c_hk*sin(ω_k d + φ_hk). Learnable linear trend + K low-freq
    Fourier features (★★★★, highly expressive)."""
    def __init__(self, H, max_d, K=4):
        super().__init__()
        a = torch.tensor(_alibi_slopes(H)).clamp(min=1e-4)
        self.a_raw = nn.Parameter(torch.log(torch.expm1(a)))
        # fixed log-spaced low frequencies; learnable amplitudes/phases per head
        self.register_buffer("omega", torch.tensor([math.pi/(2**(k+3)) for k in range(K)]))
        self.c = nn.Parameter(torch.zeros(H, K)); self.phi = nn.Parameter(torch.zeros(H, K))
        self.K = K
    def forward(self, L, device):
        a = F.softplus(self.a_raw).to(device); idx = torch.arange(L, device=device)
        dist = (idx[:, None] - idx[None, :]).clamp(min=0).float()                 # [L,L]
        out = -a[:, None, None] * dist[None]                                       # [H,L,L]
        om = self.omega.to(device); c = self.c.to(device); phi = self.phi.to(device)
        for k in range(self.K):
            out = out + c[:, k][:, None, None] * torch.sin(om[k]*dist[None] + phi[:, k][:, None, None])
        return out
    def report(self): return {"a":[round(float(x),4) for x in F.softplus(self.a_raw)],
                              "c_absmean": round(float(self.c.abs().mean()),4)}


class ExpScaleBias(LinLogBias):
    """Exponential family e^{-λd}: in additive log-space this is just -λ_h*d, i.e.
    learnable-slope linear. We expose it distinctly (no log term) to confirm it
    matches alibi_learn — a sanity that 'exp decay' ≡ linear-in-logspace."""
    def __init__(self, H, max_d):
        super().__init__(H, max_d, learn_slope=True); self.use_log = False
        self.b.requires_grad_(False)


FAMILIES = {
    "alibi_fixed": lambda H, m: AlibiFixed(H, m),
    "alibi_learn": lambda H, m: AlibiLearn(H, m),
    "linlog":      lambda H, m: LinLogBias(H, m),
    "exp_decay":   lambda H, m: ExpScaleBias(H, m),
    "hybrid":      lambda H, m: HybridBias(H, m),
    "fourier":     lambda H, m: FourierBias(H, m),
}
TOP5 = ["alibi_learn", "linlog", "hybrid", "fourier", "exp_decay"]   # + alibi_fixed control


CFG = dict(d_model=128, n_layer=3, n_head=4, d_ff=512, ctx=512, batch=12,
           steps=800, lr=3e-4, max_extrap=1024, gamma_l2=1e-3)
FULL = dict(d_model=512, n_layer=8, n_head=8, d_ff=2048, ctx=512, batch=24,
            steps=4000, lr=3e-4, max_extrap=2048, gamma_l2=1e-3,
            eval_every=400, patience=4, max_chars=16_000_000)


def train_eval(name, td, vd, device, cfg):
    torch.manual_seed(0)
    H, maxd = cfg["n_head"], cfg["max_extrap"]
    bias_mod = FAMILIES[name](H, maxd)
    model = ar.TinyGPT(256, cfg["d_model"], cfg["n_layer"], H, cfg["d_ff"],
                       maxd, False, bias_mod).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg["lr"], weight_decay=0.1)
    gen = torch.Generator().manual_seed(42)
    it = qg.batch_iter(td, cfg["ctx"], cfg["batch"], device, gen)
    eval_every = cfg.get("eval_every", 0); pmax = cfg.get("patience", 4)
    best_val = float("inf"); best_res = None; best_rep = None; patience = 0
    model.train()
    for step in range(1, cfg["steps"]+1):
        x, y = next(it); _, loss = model(x, targets=y)
        # tiny L2 on slope only to stabilize (keep expressivity free elsewhere)
        if cfg.get("gamma_l2") and hasattr(bias_mod, "a_raw"):
            loss = loss + cfg["gamma_l2"] * (F.softplus(bias_mod.a_raw)**2).sum()
        opt.zero_grad(set_to_none=True); loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
        if eval_every and step % eval_every == 0:
            vp = _ppl(model, vd, cfg["ctx"], device)
            if vp < best_val - 1e-3:
                best_val = vp; patience = 0
                best_res = {str(L): round(_ppl(model, vd, L, device),4)
                            for L in [cfg["ctx"], 2*cfg["ctx"]] if L <= maxd}
                best_rep = bias_mod.report() if hasattr(bias_mod,"report") else None
            else:
                patience += 1
                if patience >= pmax: print(f"    {name} early-stop @ {step}"); break
    if best_res is None:
        best_res = {str(L): round(_ppl(model, vd, L, device),4)
                    for L in [cfg["ctx"], 2*cfg["ctx"]] if L <= maxd}
        best_rep = bias_mod.report() if hasattr(bias_mod,"report") else None
    np_ = sum(p.numel() for p in model.parameters())
    if device == "cuda": del model; torch.cuda.empty_cache()
    return {"scheme": name, "ppl_by_ctx": best_res, "params": np_, "report": best_rep,
            "best_val": round(best_val,4) if best_val<9e8 else None}


@torch.no_grad()
def _ppl(model, data, ctx, device, n_batches=15, batch=8):
    model.eval(); gen = torch.Generator().manual_seed(1234)
    it = qg.batch_iter(data, ctx, batch, device, gen); tot = cnt = 0
    for _ in range(n_batches):
        x, y = next(it); _, loss = model(x, targets=y)
        if math.isfinite(loss.item()): tot += loss.item(); cnt += 1
    model.train(); return math.exp(tot/max(cnt,1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", choices=["smoke","full"], default="smoke")
    ap.add_argument("--schemes", nargs="+", default=["alibi_fixed"]+TOP5)
    ap.add_argument("--steps", type=int, default=None)
    ap.add_argument("--output", default="bias_families_results.json")
    args = ap.parse_args()
    cfg = dict(FULL if args.preset=="full" else CFG)
    if args.steps: cfg["steps"] = args.steps
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tr, va, src = qg.load_corpus(max_chars=cfg.get("max_chars", 2_000_000))
    td, vd = qg.to_bytes(tr), qg.to_bytes(va)
    print(f"BIAS FAMILIES ({args.preset}) | corpus={src} train={td.numel():,}B "
          f"steps={cfg['steps']} device={device}\n")
    runs = []
    for s in args.schemes:
        t0 = time.perf_counter()
        try:
            r = train_eval(s, td, vd, device, cfg); runs.append(r)
            Lk = str(cfg["ctx"])
            print(f"  {s:>12}: ppl@{Lk} {r['ppl_by_ctx'].get(Lk)} "
                  f"@{2*cfg['ctx']} {r['ppl_by_ctx'].get(str(2*cfg['ctx']))} "
                  f"params{r['params']:>9} ({time.perf_counter()-t0:.0f}s) {r.get('report')}")
        except Exception as e:
            print(f"  {s:>12}: ERROR {e}"); runs.append({"scheme":s,"error":str(e)})
    Lk = str(cfg["ctx"])
    ok = [r for r in runs if r.get("ppl_by_ctx")]
    ranked = sorted(ok, key=lambda r: r["ppl_by_ctx"].get(Lk, 9e9))
    base = next((r["ppl_by_ctx"].get(Lk) for r in runs if r["scheme"]=="alibi_fixed"), None)
    print("\n  RANKING:", [(r["scheme"], r["ppl_by_ctx"].get(Lk)) for r in ranked])
    if base:
        print(f"  vs fixed-ALiBi baseline {base}:")
        for r in ranked:
            g = (base - r["ppl_by_ctx"].get(Lk,9e9))/base*100
            print(f"    {r['scheme']:>12}: {g:+.2f}%")
    json.dump({"corpus":src,"cfg":cfg,"runs":runs,"baseline_ppl":base},
              open(args.output,"w"), indent=2)
    print(f"\n-> {args.output}")


if __name__ == "__main__":
    main()
