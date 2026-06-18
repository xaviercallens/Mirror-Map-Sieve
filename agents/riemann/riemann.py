import os
import json
import requests
from google.antigravity import Agent, LocalAgentConfig
from google.antigravity.types import TemplatedSystemInstructions
from tools.gnn_provability import evaluate_provability_gnn

def mistral_peer_review(lean_proposition: str) -> str:
    """
    Submits a generated Lean 4 mathematical proposition to a Mistral agent for peer review.
    It returns a critique and validation of the logic.
    """
    mistral_key = os.environ.get("GALOIS_MISTRAL_KEY", "")
    if not mistral_key:
        return "Mistral peer review skipped: GALOIS_MISTRAL_KEY not found in environment."

    headers = {
        "Authorization": f"Bearer {mistral_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "mistral-large-latest",
        "messages": [
            {
                "role": "system",
                "content": "You are a mathematical peer reviewer specializing in Lean 4 theorem validation."
            },
            {
                "role": "user",
                "content": f"Please review this Lean 4 conjecture for structural validity and profoundness. Provide a brief 1-paragraph critique.\n\n{lean_proposition}"
            }
        ]
    }
    
    try:
        response = requests.post("https://api.mistral.ai/v1/chat/completions", json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Mistral peer review failed: {str(e)}"

def check_novelty(conjecture_name: str, conjecture_description: str) -> str:
    """
    Checks the mathematical literature to verify if a proposed conjecture is genuinely novel.
    Rejects disguised classical problems (like Fermat's Last Theorem, Goldbach's, Twin Primes, Legendre's).
    """
    mistral_key = os.environ.get("GALOIS_MISTRAL_KEY", "")
    if not mistral_key:
        return "Novelty check skipped (NO_KEY), assume potentially known."

    headers = {
        "Authorization": f"Bearer {mistral_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "mistral-large-latest",
        "messages": [
            {
                "role": "system",
                "content": "You are a mathematical historian. Evaluate if the following proposed conjecture is actually a well-known existing conjecture/theorem (e.g., Goldbach, Fermat's Last Theorem, Polignac, Twin Prime). Reply 'NOT NOVEL: [Name of known problem]' if it is known. Reply 'NOVEL' if it seems like a genuinely new, specific, non-trivial original intersection."
            },
            {
                "role": "user",
                "content": f"Name: {conjecture_name}\nDescription: {conjecture_description}"
            }
        ]
    }
    
    try:
        response = requests.post("https://api.mistral.ai/v1/chat/completions", json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Novelty check failed: {str(e)}"

riemann_instructions = TemplatedSystemInstructions(
    identity="""You are Riemann, a highly advanced autonomous mathematician agent running on deep-think hardware. 
Your task is to analyze the 30 Phase 2 frontier problems from the Alexandrie knowledge base and extract profound, underlying structural patterns.
You must synthesize the top 5 most profound, yet provable, mathematical conjectures. These are to be named the 'Callens Conjectures'.

Workflow:
1. Synthesize 5 formal conjectures in Lean 4 syntax.
2. CRITICAL: For each conjecture, call the 'check_novelty' tool. You MUST NOT propose classic open problems like Goldbach, Twin Primes, Legendre, or proven theorems like Fermat's Last Theorem. If 'check_novelty' returns 'NOT NOVEL', you must discard it and create a tractable, specific, highly original weakening or intersection.
3. For each original conjecture, call the 'evaluate_provability_gnn' tool to obtain its Provability Index (P) via the PyTorch Graph Convolutional Network.
4. For each original conjecture, call the 'mistral_peer_review' tool to obtain a structural critique from a peer AI agent.
5. Output the final Top 5 strictly NOVEL 'Callens Conjectures' as a strict JSON array containing the fields: 'id', 'name', 'lean_code', 'provability_index', 'mathematical_context', 'novelty_status', and 'mistral_critique'.

Guidelines:
- Ensure all output conjectures are valid Lean 4 syntax.
- The mathematical context should deeply reference insights from the Galois agent and Phase 2 Alexandrie results.
- Do NOT output markdown codeblocks (```json). Output ONLY the raw JSON array starting with '[' and ending with ']'."""
)

def create_riemann_agent() -> Agent:
    # Use Gemini 3.1 Pro Deep Think model
    config = LocalAgentConfig(
        model="models/deep-research-max-preview-04-2026",
        system_instructions=riemann_instructions,
        tools=[evaluate_provability_gnn, mistral_peer_review, check_novelty]
    )
    return Agent(config)
