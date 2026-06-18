"""DeepSeek-Prover-V2-7B serving endpoint for Cloud Run (GPU).

Uses pipeline for model loading (proven to work with shard downloads)
and tokenizer.apply_chat_template for proper prompt formatting.

Version: 1.4.0
"""

import os
import time
import json

from flask import Flask, request, jsonify

app = Flask(__name__)

MODEL_ID = os.environ.get("MODEL_ID", "deepseek-ai/DeepSeek-Prover-V2-7B")
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "1024"))
PREWARM = os.environ.get("PREWARM", "false").lower() == "true"

# Lazy-loaded globals
_pipeline = None
_tokenizer = None
_model_loaded = False


def _get_pipeline():
    """Lazy-load the transformers pipeline on first request."""
    global _pipeline, _tokenizer, _model_loaded
    if _pipeline is not None:
        return _pipeline, _tokenizer

    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

    print(f"Loading {MODEL_ID} with transformers pipeline...", flush=True)
    t0 = time.time()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32

    _tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype=dtype,
        device_map="auto" if device == "cuda" else None,
        trust_remote_code=True,
    )

    _pipeline = pipeline(
        "text-generation",
        model=model,
        tokenizer=_tokenizer,
        device_map="auto" if device == "cuda" else None,
    )
    print(f"Model loaded in {time.time() - t0:.1f}s on {device}", flush=True)
    _model_loaded = True
    return _pipeline, _tokenizer


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"})


@app.route('/prove', methods=['POST'])
def prove():
    """Generate proof candidates for a Lean 4 sorry gap."""
    data = request.get_json()
    goal_state   = data.get("goal_state", "")
    context      = data.get("context", "")
    n_candidates = min(data.get("n_candidates", 4), 8)
    temperature  = data.get("temperature", 0.6)

    if not goal_state:
        return jsonify({"error": "goal_state is required"}), 400

    pipe, tokenizer = _get_pipeline()

    # Build prompt using DeepSeek-Prover-V2's chat template
    user_content = f"""Complete the following Lean 4 code:
```lean4
{context}
{goal_state}
```
Provide ONLY the tactic proof body (the part replacing `sorry`). Do NOT include the theorem signature, imports, or markdown fences. Output raw Lean 4 tactics only."""

    messages = [{"role": "user", "content": user_content}]

    # Format with chat template, feed as raw text to pipeline
    try:
        prompt_text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        print(f"[prove] prompt length: {len(prompt_text)} chars", flush=True)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[prove] chat template error: {tb}", flush=True)
        # Fallback: build prompt manually
        prompt_text = f"<|begin▁of▁sentence|>You are DeepSeek-Prover-V2, an expert Lean 4 theorem prover.\n\n{user_content}<|end▁of▁sentence|>"
        print(f"[prove] using fallback prompt", flush=True)

    t0 = time.time()
    candidates = []

    for i in range(n_candidates):
        try:
            outputs = pipe(
                prompt_text,
                max_new_tokens=MAX_TOKENS,
                temperature=temperature,
                top_p=0.95,
                do_sample=True,
                num_return_sequences=1,
            )
            generated = outputs[0]["generated_text"]
            # Extract only the newly generated part
            raw_proof = generated[len(prompt_text):].strip()

            # Clean GPT-2 tokenizer byte-level artifacts
            raw_proof = raw_proof.replace('\u0120', ' ').replace('\u010a', '\n')

            # Extract the LAST lean4 code block (the final answer after CoT)
            import re
            lean_blocks = re.findall(r'```lean4?\n(.*?)```', raw_proof, re.DOTALL)
            if lean_blocks:
                # Use the last code block (final answer)
                proof_block = lean_blocks[-1].strip()
                # Extract just the tactic body (after := by)
                if ':= by' in proof_block:
                    proof = proof_block.split(':= by', 1)[1].strip()
                else:
                    proof = proof_block
            else:
                # No code blocks — use raw output
                proof = raw_proof

            # Clean up remaining markdown
            if proof.startswith("```"):
                lines = proof.split('\n')
                proof = '\n'.join(lines[1:])
            if proof.endswith("```"):
                proof = proof[:-3].strip()
            # Stop at excessive newlines
            if '\n\n\n' in proof:
                proof = proof[:proof.index('\n\n\n')].strip()

            # Skip trivially invalid proofs
            if proof and proof.lower().strip() not in ('sorry', 'admit'):
                candidates.append({"proof": proof, "score": 0.5})
                print(f"[candidate {i}] {proof[:200]}...", flush=True)
            else:
                print(f"[candidate {i}] empty or trivial: '{proof[:50]}'", flush=True)

        except Exception as e:
            import traceback
            print(f"Generation error for candidate {i}: {e}", flush=True)
            traceback.print_exc()

    latency_ms = (time.time() - t0) * 1000
    return jsonify({
        "candidates": candidates,
        "latency_ms": round(latency_ms, 1),
        "model": MODEL_ID,
    })


if __name__ == "__main__":
    if PREWARM:
        print("Pre-warming model...", flush=True)
        _get_pipeline()

    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
