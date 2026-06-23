#!/usr/bin/env python3
"""
cy_sieve_hetero_pos.py — test the HETEROGENEOUS-POSITIONAL hypothesis.

CHAIN OF THOUGHT (why this experiment):
  The GPU bake-off winner, learnable-ALiBi, learned per-head slopes spanning 125×
  (0.70 -> 0.006), with 2/8 heads going NoPE-like (slope~0). So its +8% is NOT "a
  better curve" — it is the model SELF-ORGANIZING into sharp-local heads + near-
  global (content-only) heads. The failed variants (CY shape, log-curvature,
  Fourier) added more *distance shape* and overfit. The untried, orthogonal axis is
  per-head CONTENT<->POSITION BALANCE: ALiBi fixes the weight of the content score
  q.k relative to the positional penalty -a*d. Give each head a learnable content
  scale c_h so it can explicitly become "global/content" or "local/positional".

HYPOTHESIS: making the local<->NoPE mixture explicit (learnable slope a_h AND
learnable content scale c_h) should improve perplexity modestly and — the LLM
prize — improve LENGTH EXTRAPOLATION, without the overfit that killed "more shape".

  score_h(i,j) = c_h * (q_i . k_j)/sqrt(D)  -  a_h * (i-j)        [content_balance]

Schemes:
  alibi_fixed      fixed ALiBi (baseline)
  alibi_learn      learnable slope a_h (the bake-off winner / control)
  nope             no positional term (content only) — extrapolation sanity
  content_balance  learnable a_h AND learnable c_h (THE HYPOTHESIS)
  cb_softmax_temp  content_balance + per-head softmax temperature (extra knob ablation)

PRIMARY METRIC: length extrapolation — val ppl at 1x/2x/4x/8x the train context.
KILL: if content_balance gives no extrapolation gain over alibi_learn.

CPU smoke + GPU --preset full. Author: SocrateAI Lab (X. Callens) + Claude. MIT.
"""
from __future__ import annotations
import argparse, json, math, os, sys, time
import torch, torch.nn as nn, torch.nn.functional as F

sys.path.insert(0, os.path.dirname(__file__))
import cy_sieve_quality_gate as qg


def _alibi_slopes(H):
    return [2.0 ** (-8.0 * h / H) for h in range(1, H + 1)]


# ---------------------------------------------------------------------------
# Attention block with per-head learnable slope a_h and content scale c_h.
# We compute scores explicitly (so c_h can scale q.k) rather than via SDPA.
# ---------------------------------------------------------------------------

class HeteroBlock(nn.Module):
    def __init__(self, d_model, n_head, d_ff, mode):
        super().__init__()
        self.ln1 = nn.LayerNorm(d_model); self.ln2 = nn.LayerNorm(d_model)
        self.qkv = nn.Linear(d_model, 3 * d_model); self.proj = nn.Linear(d_model, d_model)
        self.mlp = nn.Sequential(nn.Linear(d_model, d_ff), nn.GELU(), nn.Linear(d_ff, d_model))
        self.H = n_head; self.dh = d_model // n_head; self.mode = mode
        a = torch.tensor(_alibi_slopes(n_head)).clamp(min=1e-4)
        learn_a = mode in ("alibi_learn", "content_balance", "cb_softmax_temp")
        self.a_raw = nn.Parameter(torch.log(torch.expm1(a)), requires_grad=learn_a)
        # content scale c_h (1.0 = standard); learnable only in content_balance modes
        learn_c = mode in ("content_balance", "cb_softmax_temp")
        self.c_raw = nn.Parameter(torch.zeros(n_head), requires_grad=learn_c)  # softplus(0)+1≈1.69→ we use exp
        self.logc = nn.Parameter(torch.zeros(n_head), requires_grad=learn_c)   # c_h = exp(logc), init 1
        # per-head softmax temperature (extra ablation)
        learn_t = mode == "cb_softmax_temp"
        self.logtau = nn.Parameter(torch.zeros(n_head), requires_grad=learn_t)

    def slopes(self): return F.softplus(self.a_raw)
    def contents(self): return torch.exp(self.logc)

    def forward(self, x):
        B, L, _ = x.shape; H, dh = self.H, self.dh
        h = self.ln1(x)
        q, k, v = self.qkv(h).split(h.shape[-1], dim=-1)
        q = q.view(B, L, H, dh).transpose(1, 2); k = k.view(B, L, H, dh).transpose(1, 2)
        v = v.view(B, L, H, dh).transpose(1, 2)                 # [B,H,L,dh]
        scale = 1.0 / math.sqrt(dh)
        scores = torch.matmul(q, k.transpose(-1, -2)) * scale   # [B,H,L,L]
        if self.mode != "nope":
            c = self.contents().to(x.device) if self.mode in ("content_balance", "cb_softmax_temp") \
                else torch.ones(H, device=x.device)
            scores = scores * c[None, :, None, None]
            a = self.slopes().to(x.device)
            idx = torch.arange(L, device=x.device)
            dist = (idx[:, None] - idx[None, :]).clamp(min=0).float()   # [L,L]
            scores = scores - a[None, :, None, None] * dist[None, None]
        if self.mode == "cb_softmax_temp":
            tau = torch.exp(self.logtau).to(x.device)
            scores = scores / tau[None, :, None, None]
        causal = torch.tril(torch.ones(L, L, device=x.device, dtype=torch.bool))
        scores = scores.masked_fill(~causal[None, None], float("-inf"))
        attn = torch.softmax(scores, dim=-1)
        out = torch.matmul(attn, v).transpose(1, 2).contiguous().view(B, L, -1)
        x = x + self.proj(out)
        return x + self.mlp(self.ln2(x))

    def report(self):
        r = {"a": [round(float(x), 4) for x in self.slopes().detach().cpu()]}
        if self.mode in ("content_balance", "cb_softmax_temp"):
            r["c"] = [round(float(x), 4) for x in self.contents().detach().cpu()]
        if self.mode == "cb_softmax_temp":
            r["tau"] = [round(float(x), 4) for x in torch.exp(self.logtau).detach().cpu()]
        return r


class HeteroGPT(nn.Module):
    def __init__(self, vocab, d_model, n_layer, n_head, d_ff, mode):
        super().__init__()
        self.wte = nn.Embedding(vocab, d_model)
        self.blocks = nn.ModuleList([HeteroBlock(d_model, n_head, d_ff, mode) for _ in range(n_layer)])
        self.ln_f = nn.LayerNorm(d_model); self.head = nn.Linear(d_model, vocab, bias=False)
        self.head.weight = self.wte.weight
    def forward(self, idx, targets=None):
        x = self.wte(idx)
        for b in self.blocks: x = b(x)
        logits = self.head(self.ln_f(x))
        loss = None if targets is None else F.cross_entropy(
            logits.view(-1, logits.size(-1)), targets.view(-1), ignore_index=-100)
        return logits, loss
    def report(self): return self.blocks[0].report()


CFG = dict(d_model=128, n_layer=3, n_head=8, d_ff=512, ctx=256, batch=12,
           steps=800, lr=3e-4, gamma_l2=1e-3)
FULL = dict(d_model=512, n_layer=8, n_head=8, d_ff=2048, ctx=512, batch=24,
            steps=4000, lr=3e-4, gamma_l2=1e-3, eval_every=400, patience=4,
            max_chars=16_000_000)
MODES = ["alibi_fixed", "alibi_learn", "nope", "content_balance", "cb_softmax_temp"]


@torch.no_grad()
def ppl(model, data, ctx, device, n_batches=12, batch=8):
    model.eval(); gen = torch.Generator().manual_seed(1234)
    it = qg.batch_iter(data, ctx, batch, device, gen); tot = cnt = 0
    for _ in range(n_batches):
        x, y = next(it); _, loss = model(x, targets=y)
        if math.isfinite(loss.item()): tot += loss.item(); cnt += 1
    model.train(); return math.exp(tot / max(cnt, 1))


def train_eval(mode, td, vd, device, cfg):
    torch.manual_seed(0)
    model = HeteroGPT(256, cfg["d_model"], cfg["n_layer"], cfg["n_head"], cfg["d_ff"], mode).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg["lr"], weight_decay=0.1)
    gen = torch.Generator().manual_seed(42)
    it = qg.batch_iter(td, cfg["ctx"], cfg["batch"], device, gen)
    ev = cfg.get("eval_every", 0); pmax = cfg.get("patience", 4)
    best = float("inf"); patience = 0; best_state = None
    model.train()
    for step in range(1, cfg["steps"] + 1):
        x, y = next(it); _, loss = model(x, targets=y)
        # tiny L2 on slopes only (stabilize; keep c free)
        a2 = sum((F.softplus(b.a_raw) ** 2).sum() for b in model.blocks)
        loss = loss + cfg.get("gamma_l2", 0) * a2
        opt.zero_grad(set_to_none=True); loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
        if ev and step % ev == 0:
            vp = ppl(model, vd, cfg["ctx"], device)
            if vp < best - 1e-3:
                best = vp; patience = 0
                best_state = {kk: vv.detach().clone() for kk, vv in model.state_dict().items()}
            else:
                patience += 1
                if patience >= pmax: print(f"    {mode} early-stop @ {step}"); break
    if best_state is not None:
        model.load_state_dict(best_state)
    # PRIMARY METRIC: extrapolation at 1x/2x/4x/8x
    ctx = cfg["ctx"]; extrap = {}
    for mult in (1, 2, 4, 8):
        L = ctx * mult
        try:
            extrap[f"{mult}x"] = round(ppl(model, vd, L, device), 4)
        except Exception:
            extrap[f"{mult}x"] = None
    rep = model.report()
    np_ = sum(p.numel() for p in model.parameters())
    if device == "cuda": del model; torch.cuda.empty_cache()
    return {"mode": mode, "extrap": extrap, "params": np_, "report": rep,
            "best_val": round(best, 4) if best < 9e8 else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", choices=["smoke", "full"], default="smoke")
    ap.add_argument("--modes", nargs="+", default=MODES)
    ap.add_argument("--steps", type=int, default=None)
    ap.add_argument("--output", default="hetero_pos_results.json")
    args = ap.parse_args()
    cfg = dict(FULL if args.preset == "full" else CFG)
    if args.steps: cfg["steps"] = args.steps
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tr, va, src = qg.load_corpus(max_chars=cfg.get("max_chars", 2_000_000))
    td, vd = qg.to_bytes(tr), qg.to_bytes(va)
    print(f"HETERO-POS ({args.preset}) | corpus={src} steps={cfg['steps']} "
          f"ctx={cfg['ctx']} device={device}\n")
    runs = []
    for m in args.modes:
        t0 = time.perf_counter()
        try:
            r = train_eval(m, td, vd, device, cfg); runs.append(r)
            print(f"  {m:>16}: extrap {r['extrap']}  ({time.perf_counter()-t0:.0f}s)")
            print(f"  {'':>16}  report {r['report']}")
        except Exception as e:
            print(f"  {m:>16}: ERROR {e}"); runs.append({"mode": m, "error": str(e)})
    # verdict: compare content_balance vs alibi_learn on extrapolation
    def get(m, k):
        x = next((r for r in runs if r.get("mode") == m), None)
        return x["extrap"].get(k) if x and x.get("extrap") else None
    print("\n  EXTRAPOLATION verdict (val ppl; lower=better):")
    print(f"    {'mode':>16} | 1x   2x   4x   8x")
    for r in runs:
        if r.get("extrap"):
            e = r["extrap"]; print(f"    {r['mode']:>16} | {e.get('1x')} {e.get('2x')} {e.get('4x')} {e.get('8x')}")
    al, cb = get("alibi_learn", "4x"), get("content_balance", "4x")
    if al and cb:
        print(f"\n  content_balance vs alibi_learn @4x extrap: "
              f"{(al-cb)/al*100:+.2f}% ({'BETTER' if cb<al else 'WORSE/EQUAL'})")
    json.dump({"corpus": src, "cfg": cfg, "runs": runs}, open(args.output, "w"), indent=2)
    print(f"\n-> {args.output}")


if __name__ == "__main__":
    main()
