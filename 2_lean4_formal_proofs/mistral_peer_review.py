#!/usr/bin/env python3
"""
mistral_peer_review.py — 5-Run Mistral Peer Review of S20Recurrence.lean

Sends the Lean 4 formal proof to the Mistral API for peer review across 5 runs
with different temperatures to capture diverse mathematical perspectives.

Requires:
    export MISTRAL_API_KEY=<your-key>

Usage:
    python mistral_peer_review.py
"""
import os
import json
import time
import requests

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")
if not MISTRAL_API_KEY:
    raise SystemExit("ERROR: MISTRAL_API_KEY environment variable not set.")

LEAN_FILE = os.path.join(os.path.dirname(__file__), "S20Recurrence.lean")
with open(LEAN_FILE) as f:
    lean_content = f.read()

SYSTEM_PROMPT = """You are a world-class expert in formal verification, algebraic combinatorics,
and Calabi-Yau geometry. You are reviewing a Lean 4 formal proof as a rigorous mathematical peer reviewer.

Your review should address:
1. Mathematical correctness: Is the definition of S_20(n) correct?
2. Proof strategy: Is the use of `decide` appropriate and sound?
3. Completeness: Does the proof establish what is claimed (0 sorry, 0 axioms)?
4. Significance: Is the mathematical content novel and correctly interpreted?
5. Suggestions: What would strengthen this formalization?

Be rigorous, honest, and specific. Cite Lean 4 syntax where relevant."""

USER_PROMPT = f"""Please review the following Lean 4 formal proof of the Callens-ALIX sequence
(formerly Callens-Schmidt) recurrence:

```lean
{lean_content}
```

This is claimed to be a 0-sorry, 0-axiom formal verification of the order-5, degree-9
holonomic recurrence for S_20(n) = sum_{{k=0}}^n C(n,k)^4 * C(n+k,k),
which represents the holomorphic period of a mirror Calabi-Yau 4-fold.

Provide your peer review."""

def call_mistral(run_id: int, temperature: float = 0.3) -> dict:
    """Call Mistral API and return structured review."""
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "mistral-large-latest",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT}
        ],
        "temperature": temperature,
        "max_tokens": 1500
    }
    
    print(f"\n  [Run {run_id}/5] Calling Mistral (temperature={temperature})...")
    t0 = time.time()
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    elapsed = time.time() - t0
    
    if resp.status_code != 200:
        return {"run_id": run_id, "error": f"HTTP {resp.status_code}: {resp.text}", "elapsed_s": elapsed}
    
    data = resp.json()
    review_text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    
    return {
        "run_id": run_id,
        "temperature": temperature,
        "model": data.get("model", "mistral-large-latest"),
        "review": review_text,
        "tokens": usage,
        "elapsed_s": round(elapsed, 2)
    }


def main():
    print("=" * 70)
    print("  MISTRAL PEER REVIEW — S20Recurrence.lean (5 independent runs)")
    print("=" * 70)
    print(f"\nModel: mistral-large-latest")
    print(f"File: {LEAN_FILE}")
    print(f"Lean content length: {len(lean_content)} chars")
    
    # 5 runs with varying temperatures for diverse perspectives
    temperatures = [0.1, 0.2, 0.3, 0.4, 0.5]
    reviews = []
    
    for i, temp in enumerate(temperatures, 1):
        review = call_mistral(i, temp)
        reviews.append(review)
        
        if "error" in review:
            print(f"  ❌ Run {i} failed: {review['error']}")
        else:
            print(f"  ✅ Run {i} complete ({review['elapsed_s']:.1f}s)")
            # Print first 200 chars of review
            preview = review["review"][:200].replace("\n", " ")
            print(f"     Preview: {preview}...")
    
    # Save all reviews
    output = {
        "metadata": {
            "date": time.strftime("%Y-%m-%d"),
            "lean_file": "S20Recurrence.lean",
            "model": "mistral-large-latest",
            "n_runs": 5
        },
        "reviews": reviews
    }
    
    out_file = os.path.join(os.path.dirname(__file__), "mistral_peer_reviews.json")
    with open(out_file, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\n{'='*70}")
    print(f"  PEER REVIEW SUMMARY")
    print(f"{'='*70}")
    for r in reviews:
        if "review" in r:
            print(f"\n── Run {r['run_id']} (T={r['temperature']}) ──")
            print(r["review"][:600])
            print("...")
    
    print(f"\n✅ Full reviews saved to: {out_file}")
    return output


if __name__ == "__main__":
    main()
