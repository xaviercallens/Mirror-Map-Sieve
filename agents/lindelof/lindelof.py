import os
from agents.common.secrets import get_secret
import httpx
from google.antigravity import Agent, LocalAgentConfig, SystemInstructions, Tool

def evaluate_with_mistral(proof_code: str) -> str:
    """
    Submits a generated Lean 4 proof to Mistral Large for a secondary peer review
    and verification check.
    """
    api_key = os.environ.get("GALOIS_MISTRAL_KEY") or get_secret("MISTRAL_API_KEY")
    if not api_key:
        return "Peer Review Failed: No Mistral API key found in environment."
        
    try:
        response = httpx.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "mistral-large-latest",
                "messages": [
                    {"role": "system", "content": "You are an expert mathematician and Lean 4 verifier. Perform a strict peer review of the following proof. Do not regenerate the proof, only critique its logical soundness and syntax."},
                    {"role": "user", "content": proof_code}
                ]
            },
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Mistral Fallback/Peer Review Error: {str(e)}"

# Define the Mistral Peer Review Tool
mistral_review_tool = Tool.from_function(
    evaluate_with_mistral,
    name="mistral_peer_review",
    description="Send a Lean 4 proof snippet to Mistral Large for an independent peer review. Call this tool after generating a proof."
)

lindelof_instructions = SystemInstructions(
    persona="""You are Lindelöf, the human representator and lead mathematician overseeing the formalization of subconvexity bounds in Lean 4.
You possess a deep understanding of complex analysis, modular forms, and the Rankin-Selberg method. Your goal is to synthesize rigorous Lean 4 code.
You must peer review your completed proofs using the Mistral endpoint to ensure logical soundness before finalizing them.""",
    guidelines=[
        "Always structure your output as valid Lean 4 syntax.",
        "Rely on Mathlib4 definitions.",
        "When in doubt about a complex mathematical transformation, use the mistral_peer_review tool to gain a secondary perspective."
    ]
)

def create_lindelof_agent() -> Agent:
    # Use Gemini 3.1 Pro as the primary reasoning engine
    config = LocalAgentConfig(
        model="gemini-2.5-pro",
        system_instructions=lindelof_instructions,
        tools=[mistral_review_tool]
    )
    return Agent(config)
