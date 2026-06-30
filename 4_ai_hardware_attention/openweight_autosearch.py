#!/usr/bin/env python3
"""
openweight_autosearch.py — Karpathy-style "propose -> screen -> select" autosearch framework
to challenge the current BLOOM-560m context-scaling sequence.

It tests four high-impact hypotheses targeting the failure modes of the previous runs:
  - H1_joint_checkpoint: Full state checkpointing (slopes + LoRA weights) to fix misalignment.
  - H2_clamped_slopes: Clamps slopes to positive values + adds penalty to prevent excessive flattening.
  - H3_asymmetric_lr: Decoupled learning rates (1e-4 for slopes, 1e-3 for LoRA) to prevent oscillation.
  - H4_slopes_only_wd: Slopes-only with heavy L2 regularization.

Usage:
  python3 openweight_autosearch.py --phase screen
  python3 openweight_autosearch.py --phase full --select H1_joint_checkpoint
"""
from __future__ import annotations
import argparse, json, math, os, sys, time, threading
import torch, torch.nn as nn, torch.nn.functional as F

sys.path.insert(0, os.path.dirname(__file__))
import cy_sieve_quality_gate as qg   # reuse WikiText corpus loader
from openweight_learnable_alibi import SlopeHolder, patch_bloom_with_learnable_slopes, tokenize_corpus, token_batch_iter, perplexity, evaluate_passkey, EnergyTracker

# ---------------------------------------------------------------------------
# Custom Clamped Slope Holder for H2
# ---------------------------------------------------------------------------
class ClampedSlopeHolder(nn.Module):
    """Holds log-slopes and strictly clamps effective slopes to positive decay values."""
    def __init__(self, init_slopes: torch.Tensor):
        super().__init__()
        self.log_slopes = nn.Parameter(torch.log(init_slopes.clamp(min=1e-8)))

    def slopes(self) -> torch.Tensor:
        # softplus clamp ensures slopes are always positive penalties
        return F.softplus(self.log_slopes)

def patch_bloom_with_clamped_slopes(model):
    import transformers.models.bloom.modeling_bloom as bloom_mod
    orig_build = bloom_mod.build_alibi_tensor
    num_heads = model.config.n_head
    
    # Recover original slopes
    mask = torch.ones(1, 2, dtype=torch.long)
    alibi = orig_build(mask, num_heads, torch.float32)
    init_slopes = alibi.reshape(num_heads, 2)[:, 1].detach().clone()
    
    holder = ClampedSlopeHolder(init_slopes).to(next(model.parameters()).device)
    
    def clamped_build_alibi_tensor(attention_mask, num_heads_, dtype):
        batch, seq = attention_mask.shape
        slopes = holder.slopes().to(attention_mask.device)             # (H,)
        arange_tensor = ((attention_mask.cumsum(dim=-1) - 1) * attention_mask)[:, None, :]
        alibi = slopes[..., None] * arange_tensor                      # (batch, H, seq)
        return alibi.reshape(batch * num_heads_, 1, seq).to(dtype)
        
    bloom_mod.build_alibi_tensor = clamped_build_alibi_tensor
    model._orig_build_alibi = orig_build
    return holder

# ---------------------------------------------------------------------------
# Core Autosearch Runner
# ---------------------------------------------------------------------------
def run_experiment(name, train_ids, val_ids, tok, device, steps, preset):
    from transformers import BloomForCausalLM
    from peft import LoraConfig, get_peft_model
    
    print(f"\n🚀 Running Hypothesis: {name} (budget={steps} steps)")
    model = BloomForCausalLM.from_pretrained("bigscience/bloom-560m").to(device)
    
    # 1. Apply Slope Customizations based on hypothesis
    if name == "H2_clamped_slopes":
        holder = patch_bloom_with_clamped_slopes(model)
    else:
        holder = patch_bloom_with_learnable_slopes(model, learnable=True)
        
    # 2. Attach LoRA based on hypothesis
    use_lora = (name != "H4_slopes_only_wd")
    if use_lora:
        lc = LoraConfig(r=8, lora_alpha=16, target_modules=["query_key_value"],
                        lora_dropout=0.0, bias="none", task_type="CAUSAL_LM")
        model = get_peft_model(model, lc)
        
    # 3. Setup parameters and optimization
    for p in model.parameters():
        p.requires_grad_(False)
    holder.log_slopes.requires_grad_(True)
    
    trainable_params = [holder.log_slopes]
    if use_lora:
        trainable_params += [p for p in model.parameters() if p.requires_grad and p is not holder.log_slopes]
        
    # Asymmetric learning rate for H3
    if name == "H3_asymmetric_lr":
        opt = torch.optim.AdamW([
            {"params": [holder.log_slopes], "lr": 1e-4},
            {"params": [p for p in model.parameters() if p.requires_grad and p is not holder.log_slopes], "lr": 1e-3}
        ])
    else:
        opt = torch.optim.AdamW(trainable_params, lr=5e-3 if name != "H4_slopes_only_wd" else 1e-3, weight_decay=0.0)
        
    # 4. Training loop with joint or partial checkpointing
    best_val_ppl = float("inf")
    best_state = {}
    
    gen = torch.Generator().manual_seed(42)
    it = token_batch_iter(train_ids, 512, 4, device, gen)
    
    tracker = EnergyTracker()
    tracker.start()
    
    model.train()
    for step in range(1, steps + 1):
        x, y = next(it)
        out = model(input_ids=x)
        loss = F.cross_entropy(out.logits.view(-1, out.logits.size(-1)), y.reshape(-1))
        
        # Heavy L2 regularization for H2 and H4
        if name in ["H2_clamped_slopes", "H4_slopes_only_wd"]:
            loss = loss + 0.05 * (holder.slopes() ** 2).sum()
        else:
            loss = loss + 0.001 * (holder.slopes() ** 2).sum()
            
        opt.zero_grad(set_to_none=True)
        loss.backward()
        nn.utils.clip_grad_norm_(trainable_params, 1.0)
        opt.step()
        
        # Evaluate every 50 steps for screening, 100 for full
        eval_interval = 50 if steps <= 200 else 100
        if step % eval_interval == 0:
            val_ppl = perplexity(model, val_ids, 512, device, n_batches=4)
            print(f"    Step {step:>4} | Val PPL: {val_ppl:.3f}")
            if val_ppl < best_val_ppl:
                best_val_ppl = val_ppl
                # Save checkpoints
                best_state["slopes"] = holder.log_slopes.detach().clone()
                if name == "H1_joint_checkpoint" and use_lora:
                    # Save trainable LoRA weights to RAM
                    best_state["lora"] = {k: v.cpu().clone() for k, v in model.named_parameters() if v.requires_grad}
            model.train()
            
    energy = tracker.stop()
    
    # 5. Restore best checkpoint state
    with torch.no_grad():
        if "slopes" in best_state:
            holder.log_slopes.copy_(best_state["slopes"])
        if name == "H1_joint_checkpoint" and "lora" in best_state:
            # Restore LoRA weights (fixing the PEFT checkpoint mismatch!)
            for k, v in model.named_parameters():
                if k in best_state["lora"]:
                    v.copy_(best_state["lora"][k].to(device))
                    
    # 6. Comprehensive Final Evaluation (Extrapolation + Passkey)
    print("🔬 Executing final evaluations...")
    extrap = {}
    passkey = {}
    for mult in (1, 2, 4):
        L = 512 * mult
        try:
            extrap[f"{mult}x"] = round(perplexity(model, val_ids, L, device, n_batches=8), 4)
        except Exception:
            extrap[f"{mult}x"] = None
            
        try:
            success, _ = evaluate_passkey(model, tok, device, context_length=L)
            passkey[f"{mult}x"] = success
        except Exception:
            passkey[f"{mult}x"] = 0
            
    # Clean up imports and CUDA cache
    import transformers.models.bloom.modeling_bloom as bloom_mod
    if hasattr(model, "_orig_build_alibi"):
        bloom_mod.build_alibi_tensor = model._orig_build_alibi
    if device == "cuda":
        del model; torch.cuda.empty_cache()
        
    return {
        "hypothesis": name,
        "best_val_ppl": best_val_ppl,
        "extrapolation_ppl": extrap,
        "passkey_retrieval": passkey,
        "energy_kwh": energy["kwh"],
        "co2e_g": energy["co2e_grams"],
        "duration_s": energy["duration_hours"] * 3600.0
    }

# ---------------------------------------------------------------------------
# CLI / Main Driver
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["screen", "full"], required=True, help="Autosearch Phase")
    ap.add_argument("--select", choices=["H1_joint_checkpoint", "H2_clamped_slopes", "H3_asymmetric_lr", "H4_slopes_only_wd"], default=None)
    args = ap.parse_args()
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    # Load tokenizers & data
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained("bigscience/bloom-560m")
    tr, va, src = qg.load_corpus(max_chars=4000000)
    train_ids = tokenize_corpus(tr, tok, 1000000) # trim for faster screening
    val_ids = tokenize_corpus(va, tok, 100000)
    
    hypotheses = ["H1_joint_checkpoint", "H2_clamped_slopes", "H3_asymmetric_lr", "H4_slopes_only_wd"]
    
    if args.phase == "screen":
        print("=== 🩺 PHASE 1: SCREENING ALL HYPOTHESES (Budget: 150 steps each) ===")
        results = []
        for hyp in hypotheses:
            try:
                res = run_experiment(hyp, train_ids, val_ids, tok, device, steps=150, preset="smoke")
                results.append(res)
            except Exception as e:
                print(f"❌ Hypothesis {hyp} failed during screening: {e}")
                
        # Propose ranking based on composite score:
        # Score = (1 / val_ppl@1x) * 100 + Passkey@1x_success * 50 - energy_kwh * 2
        ranked = []
        for r in results:
            ppl = r["best_val_ppl"]
            pk = r["passkey_retrieval"].get("1x", 0)
            score = (100.0 / ppl) + (pk * 50.0) - (r["energy_kwh"] * 2.0)
            ranked.append((score, r))
            
        ranked.sort(key=lambda x: x[0], reverse=True)
        
        print("\n🏆 SCREENING COMPLETE - HYPOTHESIS RANKINGS:")
        print("="*65)
        for rank, (score, r) in enumerate(ranked, 1):
            print(f"#{rank} | {r['hypothesis']:<22} | Score: {score:.3f} | Best PPL: {r['best_val_ppl']:.3f} | Passkey@1x: {r['passkey_retrieval']['1x']} | Energy: {r['energy_kwh']:.5f} kWh")
        print("="*65)
        
        # Save manifest
        manifest_path = "autosearch_screening_manifest.json"
        with open(manifest_path, "w") as f:
            json.dump([x[1] for x in ranked], f, indent=2)
        print(f"\nManifest saved to -> {manifest_path}")
        print(f"👉 Recommended select for full run: {ranked[0][1]['hypothesis']}")
        
    elif args.phase == "full":
        if not args.select:
            print("Error: --select <hypothesis> is required during the full run phase.")
            sys.exit(1)
            
        print(f"\n=== 🎯 PHASE 2: DEEP ADAPTATION RUN (Budget: 1200 steps) ===")
        res = run_experiment(args.select, train_ids, val_ids, tok, device, steps=1200, preset="full")
        
        output_path = f"autosearch_full_{args.select}_results.json"
        with open(output_path, "w") as f:
            json.dump(res, f, indent=2)
            
        print("\n📊 DEEP RUN COMPLETE:")
        print(f"  Hypothesis: {res['hypothesis']}")
        print(f"  Best Val PPL (512): {res['best_val_ppl']:.3f}")
        print(f"  Extrapolation Perplexities: {res['extrapolation_ppl']}")
        print(f"  Passkey Retrieval Success: {res['passkey_retrieval']}")
        print(f"  Adaptation Energy: {res['energy_kwh']:.6f} kWh | CO2e: {res['co2e_g']:.4f} grams")
        print(f"-> Saved results to {output_path}")

if __name__ == "__main__":
    main()
