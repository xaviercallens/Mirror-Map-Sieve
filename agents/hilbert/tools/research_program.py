"""Hilbert propose_research_program A2A skill.

Composes a formal research program blueprint with ranked milestones, A2A
agent delegations, and Lean 4 skeleton proof stubs.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ResearchMilestone:
    title: str
    description: str
    lean4_skeleton: str      # Lean 4 theorem stub (sorry-blocked)
    delegated_to: str        # Agora agent name
    estimated_months: int
    priority: int            # 1-10


@dataclass  
class ResearchProgram:
    title: str
    abstract: str
    milestones: list[ResearchMilestone]
    a2a_delegations: list[dict[str, str]]
    budget_usd: float
    expected_outputs: list[str]


def propose_research_program(
    open_problems: list[str],
    field: str = "",
    budget_usd: float = 100.0,
    llm_client: Any = None,
) -> dict[str, Any]:
    """Propose a formal research program blueprint.
    
    Inspired by Hilbert's 23 Problems, this skill takes a list of open
    problems and synthesizes a structured research program with:
    - Ranked milestones with Lean 4 proof stubs
    - A2A agent delegations (which Agora agent handles which milestone)
    - Budget allocation per milestone

    Args:
        open_problems: List of open problem titles/descriptions to address.
        field: The mathematical/scientific field.
        budget_usd: Total experiment budget in USD.
        llm_client: Optional pre-initialized Vertex AI / Gemini client.

    Returns:
        dict with keys:
          - ``program_title``: title of the research program
          - ``abstract``: summary paragraph
          - ``milestones``: list of milestone dicts with lean4_skeleton
          - ``a2a_delegations``: list of {agent, task, lean4_stub} dicts
          - ``budget_usd``: confirmed budget
          - ``expected_outputs``: list of deliverable descriptions
    """
    log = logger.bind(skill="propose_research_program", n_problems=len(open_problems))
    log.info("composing_research_program")

    prompt = f"""You are Hilbert — designing the next great research programme.
Mathematical field: {field or "Kal Alien Mathematics and Formal Verification"}
Budget: ${budget_usd} per experiment
Available Agora agents for delegation: galois, euler, riemann, noether, ramanujan, turing, bourbaki

Open problems to address:
{json.dumps(open_problems, indent=2)}

Design a structured research program inspired by Hilbert's 23 Problems.
Return a JSON object with:
- "program_title": a memorable title (e.g. "Hilbert's 2026 Programme for Kal Mathematics")
- "abstract": 3-sentence summary of the program's vision
- "milestones": list of up to 5 milestone objects, each with:
  - "title": short name
  - "description": what will be achieved
  - "lean4_skeleton": a sorry-blocked Lean 4 theorem capturing the milestone's key result
  - "delegated_to": best Agora agent name
  - "estimated_months": integer
  - "priority": 1-10
- "a2a_delegations": list of {{agent, task, lean4_stub}} objects
- "expected_outputs": list of deliverable descriptions (Lean 4 modules, papers, etc.)
"""

    try:
        if llm_client is not None:
            response = llm_client.generate_content(prompt)
            raw = response.text
        else:
            raw = _call_gemini_rest(prompt)

        data = json.loads(_extract_json(raw))
        program = ResearchProgram(
            title=data.get("program_title", f"Hilbert's Programme for {field}"),
            abstract=data.get("abstract", ""),
            milestones=[
                ResearchMilestone(
                    title=m.get("title", ""),
                    description=m.get("description", ""),
                    lean4_skeleton=m.get("lean4_skeleton", "-- sorry"),
                    delegated_to=m.get("delegated_to", "galois"),
                    estimated_months=int(m.get("estimated_months", 6)),
                    priority=int(m.get("priority", 5)),
                )
                for m in data.get("milestones", [])
            ],
            a2a_delegations=data.get("a2a_delegations", []),
            budget_usd=budget_usd,
            expected_outputs=data.get("expected_outputs", []),
        )
        log.info("program_designed", n_milestones=len(program.milestones))

    except Exception as e:
        log.warning("llm_call_failed", error=str(e), fallback=True)
        program = _fallback_program(field, open_problems, budget_usd)

    return {
        "program_title": program.title,
        "abstract": program.abstract,
        "milestones": [
            {
                "title": m.title,
                "description": m.description,
                "lean4_skeleton": m.lean4_skeleton,
                "delegated_to": m.delegated_to,
                "estimated_months": m.estimated_months,
                "priority": m.priority,
            }
            for m in sorted(program.milestones, key=lambda x: -x.priority)
        ],
        "a2a_delegations": program.a2a_delegations,
        "budget_usd": program.budget_usd,
        "expected_outputs": program.expected_outputs,
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
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096},
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
    return result["candidates"][0]["content"]["parts"][0]["text"]


def _fallback_program(
    field: str, problems: list[str], budget: float
) -> ResearchProgram:
    return ResearchProgram(
        title="Hilbert's 2026 Programme for Kal Alien Mathematics",
        abstract=(
            "This programme formalizes the foundational axioms of Kal Alien Mathematics "
            "in Lean 4, proves holographic border rank bounds, and establishes the "
            "Kal Entropy as a rigorous thermodynamic invariant. "
            f"Budget: ${budget:.0f}/experiment."
        ),
        milestones=[
            ResearchMilestone(
                title="Formalize Kal Charging Algebra",
                description="Prove non-associativity and nilpotency of the Kal Charging Algebra in full generality.",
                lean4_skeleton="theorem kal_charging_non_associative : ¬ ∀ a b c : KalChargingAlgebra, (a * b) * c = a * (b * c) := by\n  sorry",
                delegated_to="galois",
                estimated_months=3,
                priority=10,
            ),
            ResearchMilestone(
                title="Prove Holographic Border Rank Lower Bound",
                description="Construct a matching lower bound for the holographic border rank, closing the gap with the upper bound O(N² log N).",
                lean4_skeleton="theorem kal_hbr_lower_bound (N : ℕ) (hN : N ≥ 2) : ∃ lb : ℕ, lb ≥ N^2 / 2 ∧ KalHolographicBorderRank N ≥ lb := by\n  sorry",
                delegated_to="euler",
                estimated_months=6,
                priority=9,
            ),
            ResearchMilestone(
                title="Kal Entropy Instantiation",
                description="Instantiate kal_alien_mathematics_entropy for a specific metric space (e.g. hex lattice) and prove μ₃ ≥ 1 concretely.",
                lean4_skeleton="theorem kal_entropy_hex_lattice : kal_alien_mathematics_entropy hex_lattice_walks ≥ Real.log (264 / 100) := by\n  sorry",
                delegated_to="ramanujan",
                estimated_months=4,
                priority=8,
            ),
        ],
        a2a_delegations=[
            {"agent": "galois",   "task": "Prove Kal Charging Algebra non-associativity.", "lean4_stub": "-- delegated to galois agent"},
            {"agent": "euler",    "task": "Prove holographic border rank lower bound.",      "lean4_stub": "-- delegated to euler agent"},
            {"agent": "ramanujan","task": "Instantiate Kal Entropy on hex lattice.",        "lean4_stub": "-- delegated to ramanujan agent"},
        ],
        budget_usd=budget,
        expected_outputs=[
            "Lean 4 module: KalChargingAlgebraFull.lean (fully proved, zero sorry)",
            "Lean 4 module: KalBorderRankComplete.lean (both upper and lower bounds)",
            "Lean 4 module: KalEntropyInstantiated.lean (concrete metric space)",
            "Academic paper: 'Kal Alien Mathematics: A Complete Axiomatic Foundation'",
        ],
    )
