"""Hilbert axiomatize_field A2A skill.

Distills empirical results and known theorems into a coherent Lean 4
axiomatic system, using `gemini-2.5-pro-deep-think`.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class AxiomaticSystem:
    """A formally specified axiomatic system for a mathematical field."""
    field: str
    axioms: list[str]
    definitions: list[str]
    open_problems: list[str]
    lean4_code: str          # Complete Lean 4 module with axioms as `axiom` declarations
    completeness_notes: str  # Known limitations or gaps in the axiomatization


def axiomatize_field(
    empirical_data: str,
    current_theorems: list[str],
    field: str = "",
    llm_client: Any = None,
) -> dict[str, Any]:
    """Distill empirical results into a coherent Lean 4 axiomatic system.
    
    Uses `gemini-2.5-pro-deep-think` to analyze a body of evidence and
    produce a minimal, consistent set of axioms that explains the data.
    Inspired by Hilbert's axiomatic programme for geometry.

    Args:
        empirical_data: Natural-language description of observed mathematical phenomena.
        current_theorems: List of already-proven theorem statements (as strings).
        field: Optional name of the mathematical field.
        llm_client: Optional pre-initialized Vertex AI / Gemini client.

    Returns:
        dict with keys:
          - ``axioms``: list of natural-language axiom statements
          - ``definitions``: list of key definitions
          - ``open_problems``: list of problems the axiom system doesn't yet resolve
          - ``lean4_code``: Lean 4 module with `axiom` declarations
          - ``completeness_notes``: caveats about the axiomatization
    """
    log = logger.bind(skill="axiomatize_field", field=field or "unknown")
    log.info("axiomatizing_field", n_theorems=len(current_theorems))

    prompt = f"""You are Hilbert — the master axiomatizer.
Given the following empirical mathematical data:
{empirical_data}

And the following already-proven theorems:
{json.dumps(current_theorems, indent=2)}

Produce a minimal consistent axiomatic system for{f" the field of {field}" if field else " this mathematical domain"}.

Return a JSON object with:
- "axioms": list of ≤7 natural-language axiom statements (minimal, independent, consistent)
- "definitions": list of key mathematical definitions needed
- "open_problems": list of questions not resolved by these axioms
- "lean4_code": a complete Lean 4 module (namespace HilbertAxioms) with each axiom as an `axiom` declaration
- "completeness_notes": brief paragraph on known limitations of this axiomatization
"""

    try:
        if llm_client is not None:
            response = llm_client.generate_content(prompt)
            raw = response.text
        else:
            raw = _call_gemini_rest(prompt)

        data = json.loads(_extract_json(raw))
        system = AxiomaticSystem(
            field=field or "unknown",
            axioms=data.get("axioms", []),
            definitions=data.get("definitions", []),
            open_problems=data.get("open_problems", []),
            lean4_code=data.get("lean4_code", "-- placeholder"),
            completeness_notes=data.get("completeness_notes", ""),
        )
        log.info("axioms_generated", count=len(system.axioms))

    except Exception as e:
        log.warning("llm_call_failed", error=str(e), fallback=True)
        system = _fallback_axiomatization(field, empirical_data, current_theorems)

    return {
        "field": system.field,
        "axioms": system.axioms,
        "definitions": system.definitions,
        "open_problems": system.open_problems,
        "lean4_code": system.lean4_code,
        "completeness_notes": system.completeness_notes,
    }


def _extract_json(text: str) -> str:
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in LLM response")
    return text[start:end]


def _call_gemini_rest(prompt: str) -> str:
    import urllib.request
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY not set")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-pro:generateContent"
        f"?key={api_key}"
    )
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4096},
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
    return result["candidates"][0]["content"]["parts"][0]["text"]


def _fallback_axiomatization(
    field: str, data: str, theorems: list[str]
) -> AxiomaticSystem:
    """Produce a minimal fallback axiom system when LLM is unavailable."""
    return AxiomaticSystem(
        field=field or "mathematics",
        axioms=[
            "Axiom 1 (Completeness): Every bounded sequence in the space has a convergent subsequence.",
            "Axiom 2 (Conservation): Total information content is invariant under the dynamics.",
            "Axiom 3 (Finiteness): The generating set of the algebra is finite.",
        ],
        definitions=[
            "Definition: A *Kal tensor* is a rank-3 tensor over a nilpotent algebra.",
            "Definition: The *holographic border rank* R_hol(T) is the minimum border rank over all holographic decompositions.",
        ],
        open_problems=[
            "Prove that the axioms are independent.",
            "Determine if the algebra is finitely presented.",
        ],
        lean4_code=f"""namespace HilbertAxioms
-- Auto-generated by Hilbert Agent v2.0 (fallback mode)
-- Field: {field or "unknown"}

axiom completeness : ∀ (seq : ℕ → ℝ), BoundedSequence seq → ∃ subseq : ℕ → ℕ, StrictMono subseq ∧ ConvergesTo (seq ∘ subseq)
axiom conservation : ∀ (system : DynamicalSystem), information_content system.initial = information_content system.final
axiom finiteness : ∃ (S : Finset GeneratorType), generates_algebra S

end HilbertAxioms""",
        completeness_notes=(
            "Fallback axiomatization. LLM endpoint was unavailable. "
            "These axioms are illustrative only and not specific to the provided theorems."
        ),
    )
