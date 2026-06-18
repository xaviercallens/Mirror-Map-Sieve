#!/usr/bin/env python3
"""
Alexandrie Context Limit Auto-Optimizer.
Finds the optimal `k` (number of RAG tactics) to inject into the LLM context.
Increments `k` until API constraints (latency, 400 Bad Request, max tokens) are hit.
Saves the optimal `k` to config.json.
"""

import os
import json
import time
import requests
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "agents", "galois", "rag_config.json")

def generate_dummy_tactics(k: int) -> str:
    tactics = []
    for i in range(k):
        tactics.append(f"apply theorem_number_{i} (x : Nat) : x = x := rfl")
    return "\n".join(tactics)

def test_context_size(k: int, api_key: str) -> dict:
    """Mock an MCTS Policy call with k injected tactics."""
    model_name = "gemini-2.5-pro"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    
    tactics_str = generate_dummy_tactics(k)
    prompt = f"Current Goal State:\n⊢ a + b = b + a\n\nHistorically useful tactics:\n{tactics_str}"
    
    payload = {
        "systemInstruction": {
            "parts": [{"text": "You are a Lean 4 solver. Output a JSON with 'thought' and 'tactics' list."}]
        },
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7}
    }
    
    start_time = time.perf_counter()
    try:
        resp = requests.post(url, json=payload, timeout=30)
        elapsed = time.perf_counter() - start_time
        
        if resp.status_code == 200:
            return {"success": True, "latency": elapsed, "status": 200}
        else:
            return {"success": False, "latency": elapsed, "status": resp.status_code, "error": resp.text}
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        return {"success": False, "latency": elapsed, "status": 0, "error": str(e)}

def optimize():
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.environ.get("GALOIS_GEMINI_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("No API key found. Using mock simulation for dry-run.")
        # For dry-run simulation when keys aren't available locally
        api_key = "mock"

    logger.info("Starting context auto-optimization loop...")
    k = 1
    optimal_k = 3 # default fallback
    max_latency = 5.0 # We don't want DAG node expansion to take longer than 5 seconds
    
    consecutive_failures = 0
    
    while True:
        logger.info(f"Testing k={k}...")
        
        if api_key == "mock":
            # Simulate optimization behavior
            time.sleep(0.1)
            latency = 0.5 + (k * 0.1)
            if k > 25:
                res = {"success": False, "latency": latency, "status": 400, "error": "Context limit exceeded"}
            else:
                res = {"success": True, "latency": latency, "status": 200}
        else:
            res = test_context_size(k, api_key)
            
        if res["success"]:
            logger.info(f"[SUCCESS] k={k} | Latency: {res['latency']:.2f}s")
            if res["latency"] > max_latency:
                logger.warning(f"Latency threshold exceeded ({res['latency']:.2f}s > {max_latency}s). Stopping.")
                optimal_k = max(1, k - 5)
                break
            
            # Save valid k
            optimal_k = k
            
            # Step aggressively at first, then fine-tune
            if k < 10:
                k += 3
            else:
                k += 5
            consecutive_failures = 0
        else:
            logger.warning(f"[FAILED] k={k} | Status: {res['status']} | Latency: {res['latency']:.2f}s")
            consecutive_failures += 1
            if consecutive_failures >= 2:
                logger.info("Hit hard API limit. Backing off.")
                optimal_k = max(1, k - 10)
                break
            k += 1 # Try a slightly higher one just in case it was a fluke
            
    logger.info(f"Optimization complete. Sweet spot for RAG context limit is k={optimal_k}")
    
    config = {"optimal_k": optimal_k, "last_updated": time.time()}
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    logger.info(f"Saved config to {CONFIG_PATH}")

if __name__ == "__main__":
    optimize()
