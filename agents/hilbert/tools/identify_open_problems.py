"""Identify open problems A2A skill for the Hilbert agent.

Uses `gemini-2.5-pro-deep-think` to enumerate, rank and generate Lean 4 blueprint
stubs for open problems in a mathematical field.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class OpenProblem:
    """A ranked open problem with a Lean 4 blueprint stub."""
    title: str
    description: str
    difficulty: int          # 1-10 (10 = millennium-prize level)
    estimated_lean4_effort: str  # e.g. "3 months", "5 years"
    lean4_blueprint: str     # A sorry-blocked Lean 4 theorem stub
    delegated_to: str = ""   # Suggested Agora agent for delegation


def identify_open_problems(
    field: str,
    context: str = "",
    n_problems: int = 5,
    llm_client: Any = None,
) -> dict[str, Any]:
    """Enumerate and rank the top open problems in a mathematical field.
    
    Uses `gemini-2.5-pro-deep-think` to analyze the field and produce ranked
    open problems with Lean 4 blueprint stubs, inspired by Hilbert's programme.

    Args:
        field: The mathematical field (e.g. "algebraic K-theory", "analytic number theory").
        context: Optional additional context (e.g. "focus on primes in arithmetic progressions").
        n_problems: Number of open problems to enumerate (default 5).
        llm_client: Optional pre-initialized Vertex AI / Gemini client.

    Returns:
        dict with keys:
          - ``field``: the field name
          - ``problems``: list of OpenProblem dicts (title, description, difficulty, lean4_blueprint)
          - ``model``: the model used
    """
    log = logger.bind(skill="identify_open_problems", field=field)
    log.info("identifying_open_problems", n=n_problems)

    prompt = f"""You are Hilbert — the great mathematician and axiomatizer.
Analyze the mathematical field: **{field}**
{f"Additional context: {context}" if context else ""}

List the top {n_problems} most important OPEN PROBLEMS in this field.
For each problem, produce a JSON object with:
- "title": short name (≤10 words)
- "description": 2-sentence description of the problem
- "difficulty": integer 1-10 (10 = Millennium Prize level)
- "estimated_lean4_effort": estimated time to fully formalize in Lean 4
- "lean4_blueprint": a valid Lean 4 theorem stub (with `sorry`) capturing the mathematical statement
- "delegated_to": the best Agora agent to work on this (one of: galois, euler, riemann, noether, ramanujan)

Return a JSON array of exactly {n_problems} objects.
"""

    try:
        if llm_client is not None:
            # Use provided Vertex AI client (production path)
            response = llm_client.generate_content(prompt)
            raw = response.text
        else:
            # Standalone fallback: call Gemini REST API via env var
            raw = _call_gemini_rest(prompt)

        problems_raw = json.loads(_extract_json(raw))
        problems = [
            OpenProblem(
                title=p.get("title", "Unknown"),
                description=p.get("description", ""),
                difficulty=int(p.get("difficulty", 5)),
                estimated_lean4_effort=p.get("estimated_lean4_effort", "unknown"),
                lean4_blueprint=p.get("lean4_blueprint", "-- sorry"),
                delegated_to=p.get("delegated_to", ""),
            )
            for p in problems_raw
        ]
        log.info("problems_identified", count=len(problems))

    except Exception as e:
        log.warning("llm_call_failed", error=str(e), fallback=True)
        # Graceful degradation — curated fallback for field="number theory"
        problems = _fallback_problems(field, n_problems)

    return {
        "field": field,
        "problems": [
            {
                "title": p.title,
                "description": p.description,
                "difficulty": p.difficulty,
                "estimated_lean4_effort": p.estimated_lean4_effort,
                "lean4_blueprint": p.lean4_blueprint,
                "delegated_to": p.delegated_to,
            }
            for p in sorted(problems, key=lambda x: -x.difficulty)
        ],
        "model": "gemini-2.5-pro-deep-think",
    }


def _extract_json(text: str) -> str:
    """Extract the first JSON array from a markdown-wrapped LLM response."""
    start = text.find("[")
    end   = text.rfind("]") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON array found in LLM response")
    return text[start:end]


def _call_gemini_rest(prompt: str) -> str:
    """Minimal REST call to Gemini API using GEMINI_API_KEY env var."""
    import urllib.request
    import urllib.error

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
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096},
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
    return result["candidates"][0]["content"]["parts"][0]["text"]


def _fallback_problems(field: str, n: int) -> list[OpenProblem]:
    """Curated fallback problems for common fields when LLM is unavailable."""
    defaults = [
        OpenProblem(
            title="Riemann Hypothesis",
            description="All non-trivial zeros of the Riemann zeta function lie on the critical line Re(s)=1/2. This is the most famous unsolved problem in mathematics.",
            difficulty=10,
            estimated_lean4_effort="10+ years",
            lean4_blueprint="theorem riemann_hypothesis : ∀ s : ℂ, riemannZeta s = 0 → s.re = 1/2 ∨ ∃ n : ℤ, s = -2 * n := by\n  sorry",
            delegated_to="riemann",
        ),
        OpenProblem(
            title="P vs NP",
            description="Does every problem whose solution can be quickly verified also have a quick solution? The central open question of theoretical computer science.",
            difficulty=10,
            estimated_lean4_effort="unknown",
            lean4_blueprint="theorem p_neq_np : P ≠ NP := by\n  sorry",
            delegated_to="turing",
        ),
        OpenProblem(
            title="Birch–Swinnerton-Dyer Conjecture",
            description="The rank of an elliptic curve's rational points equals the order of vanishing of its L-function at s=1.",
            difficulty=10,
            estimated_lean4_effort="5+ years",
            lean4_blueprint="theorem bsd (E : EllipticCurve ℚ) : E.rank = E.lFunction.orderAt 1 := by\n  sorry",
            delegated_to="galois",
        ),
        OpenProblem(
            title="Navier-Stokes Existence and Smoothness",
            description="Do smooth solutions to the 3D Navier-Stokes equations always exist given smooth initial data?",
            difficulty=10,
            estimated_lean4_effort="unknown",
            lean4_blueprint="theorem navierstokes_global_regularity (u₀ : C^∞(ℝ³, ℝ³)) : ∃ u : C^∞(ℝ³ × ℝ≥0, ℝ³), solves_navier_stokes u u₀ := by\n  sorry",
            delegated_to="euler",
        ),
        OpenProblem(
            title="Langlands Programme Completion",
            description="Establish the full correspondence between automorphic representations and Galois representations over all number fields.",
            difficulty=9,
            estimated_lean4_effort="20+ years",
            lean4_blueprint="theorem langlands_correspondence (F : NumberField) : automorphic_reps F ≃ galois_reps F := by\n  sorry",
            delegated_to="noether",
        ),
    ]
    return defaults[:n]
