#!/usr/bin/env python3
"""
h13_comparative_training.py — H13 comparative training experiment.
Prepares a synthetic corpus of structured Python code vs. standard natural language text,
and runs parallel training sweeps to observe slope evolution under gradient descent.
"""

import math
import os
import json
import time
import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoTokenizer, BloomConfig, BloomForCausalLM
import transformers.models.bloom.modeling_bloom as bloom_mod

# ---------------------------------------------------------------------------
# Slope Holder & Monkey Patching
# ---------------------------------------------------------------------------
class SlopeHolder(nn.Module):
    def __init__(self, init_slopes: torch.Tensor, learnable: bool):
        super().__init__()
        self.log_slopes = nn.Parameter(torch.log(init_slopes.clamp(min=1e-8)),
                                       requires_grad=learnable)

    def slopes(self):
        return torch.exp(self.log_slopes)

def _default_alibi_slopes(num_heads: int) -> torch.Tensor:
    return torch.tensor([2.0 ** (-8.0 * h / num_heads) for h in range(1, num_heads + 1)],
                        dtype=torch.float32)

def patch_bloom_learnable_slopes(num_heads: int, device, learnable: bool):
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
# Synthetic Corpus Generators
# ---------------------------------------------------------------------------
def generate_structured_python_code():
    """Generates synthetic, highly structured, nested Python code to train the model."""
    snippets = []
    # Class structures with deep loops, conditionals, and matching indents
    for i in range(150):
        code = f"""
class ProcessEngine_{i}:
    def __init__(self, capacity, speed_factor):
        self.capacity = capacity
        self.speed = speed_factor
        self.active_jobs = []
        self.metrics_log = {{}}

    def execute_pipeline(self, job_list, multiplier):
        accumulated_score = 0
        for job in job_list:
            if job.status == "PENDING":
                for step in range(self.capacity):
                    if step % 2 == 0:
                        score = step * self.speed * multiplier
                        if score > 100:
                            for sub_task in range(5):
                                val = score + sub_task * 10
                                accumulated_score += val
                        else:
                            accumulated_score -= score
                    else:
                        accumulated_score += 1
            elif job.status == "FAILED":
                accumulated_score -= 50
        return accumulated_score
"""
        snippets.append(code.strip())
    return "\n\n# ---\n\n".join(snippets)

def generate_natural_language_text():
    """Generates synthetic, standard, sequential natural language paragraphs."""
    paragraphs = []
    nouns = ["river", "mountain", "forest", "scientist", "traveler", "builder", "artist", "merchant", "soldier", "teacher"]
    verbs = ["observed", "built", "crossed", "painted", "discovered", "guarded", "taught", "explored", "carried", "wrote"]
    adjectives = ["ancient", "mysterious", "glowing", "diligent", "silent", "creative", "brave", "thoughtful", "glorious", "quiet"]
    
    # Generate sequential narrative text
    for i in range(150):
        para = f"The {adjectives[i%10]} {nouns[i%10]} {verbs[(i+1)%10]} the path through the forest. " \
               f"It was a peaceful day where everyone was focused on their tasks. " \
               f"They walked slowly past the old mill in the long afternoon of a forgotten century. " \
               f"Many people believe that learning is a wonderful way to expand your mind and understand new things. " \
               f"The mountain peak was covered in a thick layer of fresh, glittering white snow. " \
               f"After a long day of hard work, they gathered around the campfire to tell stories and sing songs. " \
               f"They looked up at the stars and wondered about the vast universe that surrounded them."
        paragraphs.append(para)
    return " ".join(paragraphs)

# ---------------------------------------------------------------------------
# Training Sweep Routine
# ---------------------------------------------------------------------------
def run_training_sweep(corpus_text, tokenizer, num_heads, device, steps=100, ctx=128, batch=4, lr=1e-3):
    # Setup fresh model for this sweep
    d_model = 128
    n_layer = 2
    n_head = num_heads
    vocab = tokenizer.vocab_size
    
    # Tokenize corpus and chunk into contiguous blocks
    tokens = tokenizer(corpus_text, return_tensors="pt")["input_ids"][0]
    total_tokens = tokens.size(0)
    
    # Generator for batches of ctx length
    buf = tokens.tolist()
    def get_batch():
        nonlocal buf
        need = batch * ctx
        while len(buf) < need:
            buf += tokens.tolist()  # Repeat if exhausted
        blk = torch.tensor(buf[:need], device=device).view(batch, ctx)
        buf = buf[need:]
        return blk

    # Patch and build model
    holder = patch_bloom_learnable_slopes(n_head, device, learnable=True)
    cfg = BloomConfig(vocab_size=vocab, hidden_size=d_model, n_layer=n_layer,
                      n_head=n_head, attention_dropout=0.0, hidden_dropout=0.0,
                      use_cache=False)
    model = BloomForCausalLM(cfg).to(device=device, dtype=torch.float32)
    
    # Optimization
    params = list(model.parameters()) + [holder.log_slopes]
    opt = torch.optim.AdamW(params, lr=lr, weight_decay=0.01)
    
    slope_history = []
    loss_history = []
    
    print(f"  Starting sweep ({steps} steps) on device {device}...")
    model.train()
    for step in range(1, steps + 1):
        blk = get_batch()
        out = model(input_ids=blk)
        loss = F.cross_entropy(out.logits[:, :-1].reshape(-1, out.logits.size(-1)),
                               blk[:, 1:].reshape(-1))
        
        # Add tiny slope regularization to encourage stable profiles (H13 slope dynamics)
        loss = loss + 1e-4 * (holder.slopes() ** 2).sum()
        
        opt.zero_grad(set_to_none=True)
        loss.backward()
        nn.utils.clip_grad_norm_(params, 1.0)
        opt.step()
        
        current_slopes = holder.slopes().detach().cpu().tolist()
        slope_history.append(current_slopes)
        loss_history.append(loss.item())
        
        if step % 20 == 0 or step == steps:
            print(f"    Step {step}/{steps} | Loss: {loss.item():.4f} | Slopes: {[round(s, 5) for s in current_slopes]}")
            
    return slope_history, loss_history

# ---------------------------------------------------------------------------
# Main Experiment Execution
# ---------------------------------------------------------------------------
def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"=== H13 COMPARATIVE TRAINING SWEEP ===")
    print(f"Device: {device}")
    
    # Load Bloom tokenizer
    print("Loading Bloom tokenizer...")
    tok = AutoTokenizer.from_pretrained("bigscience/bloom-560m")
    num_heads = 4
    init_slopes = _default_alibi_slopes(num_heads).tolist()
    print(f"Initial ALiBi slopes: {[round(s, 5) for s in init_slopes]}")
    
    # Generate Corpora
    print("\nGenerating synthetic corpora...")
    code_corpus = generate_structured_python_code()
    nl_corpus = generate_natural_language_text()
    
    print(f"  * Structured Python Code corpus length: {len(code_corpus)} chars")
    print(f"  * Natural Language text corpus length: {len(nl_corpus)} chars")
    
    # Run Sweep 1: Python Code
    print("\n--- RUNNING SWEEP 1: STRUCTURED PYTHON CODE ---")
    code_slopes, code_losses = run_training_sweep(code_corpus, tok, num_heads, device, steps=120)
    
    # Run Sweep 2: Natural Language
    print("\n--- RUNNING SWEEP 2: NATURAL LANGUAGE TEXT ---")
    nl_slopes, nl_losses = run_training_sweep(nl_corpus, tok, num_heads, device, steps=120)
    
    # Analyze final slope profiles
    final_code_slopes = code_slopes[-1]
    final_nl_slopes = nl_slopes[-1]
    
    print("\n=== H13 COMPARATIVE SLOPE FINDINGS ===")
    print(f"Initial Slopes:                {[round(s, 5) for s in init_slopes]}")
    print(f"Final Code-Trained Slopes:     {[round(s, 5) for s in final_code_slopes]}")
    print(f"Final NL-Trained Slopes:       {[round(s, 5) for s in final_nl_slopes]}")
    
    # Compute average slope magnitudes
    avg_init = sum(init_slopes) / len(init_slopes)
    avg_code = sum(final_code_slopes) / len(final_code_slopes)
    avg_nl = sum(final_nl_slopes) / len(final_nl_slopes)
    
    print(f"\nAverage slope magnitudes:")
    print(f"  * Initial:                 {avg_init:.5f}")
    print(f"  * Code-Trained (H13):      {avg_code:.5f} (Flattening ratio: {avg_code/avg_init - 1:+.2%})")
    print(f"  * NL-Trained:              {avg_nl:.5f} (Flattening ratio: {avg_nl/avg_init - 1:+.2%})")
    
    # Save the history for results presentation
    results = {
        "num_heads": num_heads,
        "initial_slopes": init_slopes,
        "code_final_slopes": final_code_slopes,
        "nl_final_slopes": final_nl_slopes,
        "code_slope_history": code_slopes,
        "nl_slope_history": nl_slopes,
        "code_losses": code_losses,
        "nl_losses": nl_losses,
        "avg_init": avg_init,
        "avg_code": avg_code,
        "avg_nl": avg_nl
    }
    
    results_path = "/home/callensxavier_gmail_com/Mirror-Map-Sieve/4_ai_hardware_attention/h13_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved H13 results to {results_path}")

if __name__ == "__main__":
    main()
