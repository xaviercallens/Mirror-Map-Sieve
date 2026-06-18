#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""HorizonMath Top 20 Olympiad Execution — SymBrain v12.3 (PSLQ-Discovery).

Leverages prior v10/v11/v12 execution results as warm-start context for the
Galois MCTS search. Each problem goes through the full Socratic dialectic:
  Galois (SymBrain v12.3) → Euler (strict formal) → Pythagore (Lean 4 gap map)

GPU Priority: H100 → A100 → L4 (backup)
Budget: Hard cap $200.  Scale: Galois 1→4 replicas on A100/H100.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agents.galois.agent import GaloisAgent
from agents.euler.agent import EulerAgent
from agents.pythagore.agent import PythagoreAgent
from agents.heraclite.agent import HeracliteAgent
from agents.turing.agent import TuringAgent
from agents.socrates.agent import SocratesAgent, SolvabilityClass

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BUDGET_HARD_CAP_USD = 200.0
PROBLEMS_FILE = Path.home() / ".gemini/antigravity/brain/142e4281-5564-4819-8826-7d615d389330/scratch/HorizonMath/data/problems_full.json"
# Fallback location inside the repo
PROBLEMS_FILE_ALT = Path(__file__).parent.parent / "scratch" / "HorizonMath" / "data" / "problems_full.json"

OUTPUT_DIR = Path(__file__).parent.parent / "docs"
MONOGRAPH_PATH = OUTPUT_DIR / "horizonmath_top20_monograph.md"

# v10/v11 prior results — problem IDs that were already attempted
V11_PRIOR_PROBLEMS = {
    "w5_watson_integral",
    "w6_watson_integral",
    "bessel_moment_c5_0",
    "bessel_moment_c5_1",
    "feigenbaum_delta",
    "anderson_lyapunov_exponent",
    "autocorr_signed_upper",
    "elliptic_k_moment_4",
    "calabi_yau_c5",
}

# v11 known findings to feed as warm-start context
V11_WARM_CONTEXT = {
    "w5_watson_integral": "v11: Galois generated hypergeometric proof path involving Γ(1/4) products. Euler: INCOMPLETE (sorry in lattice_symmetry lemma). Confidence 0.80.",
    "w6_watson_integral": "v11: Galois proposed Meijer-G representation. Euler: INCOMPLETE (sorry in dimensional reduction step). Confidence 0.75.",
    "bessel_moment_c5_0": "v11: Galois conjectured c_{5,0} via elliptic integral products. Euler: INCOMPLETE (sorry in Bessel K_0 product identity). Confidence 0.78.",
    "bessel_moment_c5_1": "v11: Galois used integration-by-parts with K_0^5 identity. Euler: INCOMPLETE (sorry in Hankel contour closure). Confidence 0.72.",
    "feigenbaum_delta": "v11: Galois CORRECTLY returned INCOMPLETE — no algebraic independence tools exist. v1 wrongly REFUTED. Confidence 0.60.",
    "anderson_lyapunov_exponent": "v11: Galois proposed Thouless formula approach. Euler: INCOMPLETE (sorry in random matrix trace bound). Confidence 0.65.",
    "autocorr_signed_upper": "v11: Galois generated step-function construction with 500 intervals. Euler: INCOMPLETE (sorry in convolution optimality proof). Confidence 0.70.",
    "elliptic_k_moment_4": "v11: Galois conjectured Γ(1/4)^8 expression via Rogers-Zucker. Euler: INCOMPLETE (sorry in modular transformation). Confidence 0.82.",
    "calabi_yau_c5": "v11: Galois proposed MZV decomposition. Euler: INCOMPLETE (sorry in period integral convergence). Confidence 0.68.",
}


@dataclass
class ProblemResult:
    """Result of a single problem execution."""
    problem_id: str
    solvability: int
    domain: str
    galois_answer: str
    euler_verdict: str
    euler_confidence: float
    pythagore_draft: str
    sorry_count: int
    cost_usd: float
    elapsed_s: float
    warm_start_used: bool


@dataclass
class OlympiadRun:
    """Full Olympiad execution state."""
    results: list[ProblemResult] = field(default_factory=list)
    total_cost: float = 0.0
    budget_remaining: float = BUDGET_HARD_CAP_USD


def select_top_20(all_problems: list[dict]) -> list[dict]:
    """Select the top 20 problems prioritizing high solvability and diversity.

    Selection strategy:
      1. All solvability 3 problems (frontier, hardest)
      2. Fill remaining with solvability 2, preferring diverse domains
      3. Include at least 1 solvability 1 construction problem
    """
    class3 = [p for p in all_problems if p.get("solvability") == 3]
    class2 = [p for p in all_problems if p.get("solvability") == 2]
    class1 = [p for p in all_problems if p.get("solvability") == 1]

    selected: list[dict] = []

    # All Class 3 first (frontier)
    selected.extend(class3)

    # Prioritize v11 prior problems in Class 2 (leverage warm start)
    prior_class2 = [p for p in class2 if p["id"] in V11_PRIOR_PROBLEMS]
    new_class2 = [p for p in class2 if p["id"] not in V11_PRIOR_PROBLEMS]

    selected.extend(prior_class2)

    # Fill remaining slots with diverse Class 2 problems
    seen_domains: set[str] = {p.get("domain", "") for p in selected}
    for p in new_class2:
        if len(selected) >= 19:
            break
        domain = p.get("domain", "")
        # Prefer unseen domains for diversity
        if domain not in seen_domains:
            selected.append(p)
            seen_domains.add(domain)
        elif len(selected) < 15:
            selected.append(p)

    # Add 1 construction problem from Class 1
    if class1 and len(selected) < 20:
        selected.append(class1[0])

    return selected[:20]


def count_sorry(text: str) -> int:
    """Count 'sorry' gaps in a proof text."""
    return text.lower().count("sorry")


async def run_single_problem(
    idx: int,
    total: int,
    prob: dict,
    galois: GaloisAgent,
    euler: EulerAgent,
    pythagore: PythagoreAgent,
    turing: TuringAgent,
    run_state: OlympiadRun,
) -> ProblemResult | None:
    """Execute a single problem through the Socratic pipeline."""
    pid = prob["id"]
    solvability = prob.get("solvability", 2)
    domain = prob.get("domain", "unknown")
    solvability_class = SolvabilityClass.classify(
        f"{'horizonmath frontier' if solvability == 3 else 'olympiad' if solvability <= 1 else ''} {pid}"
    )

    # Budget guard
    estimated_per_problem = 8.0 if solvability == 3 else 5.0
    if run_state.budget_remaining < estimated_per_problem:
        print(f"  ⚠️  Budget guard: ${run_state.budget_remaining:.2f} remaining < ${estimated_per_problem:.2f} estimated. Skipping {pid}.")
        return None

    t0 = time.monotonic()
    warm_start = pid in V11_PRIOR_PROBLEMS
    warm_ctx = V11_WARM_CONTEXT.get(pid, "")

    print(f"\n{'='*70}")
    print(f"  [{idx}/{total}] Problem: {pid}")
    print(f"  Solvability: {solvability} | Domain: {domain} | Class: {solvability_class}")
    if warm_start:
        print(f"  🔥 Warm Start (v11): {warm_ctx[:80]}...")
    print(f"  Budget remaining: ${run_state.budget_remaining:.2f}")
    print(f"{'='*70}")

    # A. Turing: Deploy compute tier (H100 → A100 → L4 fallback)
    gpu_priority = ["H100", "A100", "L4"] if solvability == 3 else ["A100", "L4"]
    print(f"  [Turing] Deploying GPU cluster for {solvability_class} (priority: {' → '.join(gpu_priority)})...")
    try:
        await turing.run(
            f"Deploy SymBrain v12.3 for {solvability_class} with GPU priority {gpu_priority}",
            solvability_class=solvability_class,
        )
    except Exception as e:
        print(f"  [Turing] Deployment warning: {e}")
        print(f"  [Turing] ⚠️ Falling back to L4 backup tier.")

    # B. Galois: Solve with warm-start context
    prompt = prob.get("prompt", f"Solve: {pid}")
    if warm_start:
        import json
        mcts_node = {
            "node_id": "root",
            "state": f"{pid}_start",
            "visits": 100,
            "value": 0.8,
            "children": [
               {
                   "action": "v11_approach",
                   "value": 0.75,
                   "visits": 50,
                   "prior": 0.9,
                   "text_context": warm_ctx
               }
            ]
        }
        serialized_mcts = json.dumps(mcts_node, indent=2)
        prompt = (
            f"[WARM START from SymBrain v11 Dieudonné execution]\n"
            f"Serialized MCTS Context:\n```json\n{serialized_mcts}\n```\n\n"
            f"Using SymBrain v12 PSLQ-Discovery, improve upon the v11 attempt. "
            f"Close any remaining 'sorry' gaps identified in the prior run.\n\n"
            f"{prompt}"
        )

    print(f"  [Galois] Attempting solution with SymBrain v12 (PSLQ-Discovery)...")
    galois_res = await galois.run(
        prompt,
        symbrain_version="v12.3_large" if solvability == 3 else "v12.3_small",
    )

    # C. Euler: Verify with strict formal checks
    galois_answer_str = str(galois_res.answer)
    print(f"  [Euler] Verifying Galois solution (strict mode)...")
    euler_res = await euler.run(
        f"Verify Galois's solution for HorizonMath problem '{pid}': {galois_answer_str[:500]}. "
        f"Apply strict formal checks. If proof is empty or contains sorry, verdict MUST be INCOMPLETE.",
    )

    euler_verdict_str = str(euler_res.answer)
    euler_conf = euler_res.confidence

    # D. Pythagore: Generate formal draft
    print(f"  [Pythagore] Generating Lean 4 gap map...")
    pyth_res = await pythagore.run(
        f"Generate a Lean 4 formal proof draft for '{pid}'. "
        f"Galois solution: {galois_answer_str[:300]}. "
        f"Euler verdict: {euler_verdict_str[:200]}",
    )

    pyth_draft = str(pyth_res.answer)
    sorry_gaps = count_sorry(pyth_draft) + count_sorry(galois_answer_str)

    # E. Turing: Scale to zero
    print(f"  [Turing] Tearing down cluster...")
    try:
        await turing.run("tear down deployment symbrain_swarm")
    except Exception:
        pass

    # Cost tracking
    problem_cost = galois_res.cost_usd + euler_res.cost_usd + pyth_res.cost_usd
    elapsed = time.monotonic() - t0

    result = ProblemResult(
        problem_id=pid,
        solvability=solvability,
        domain=domain,
        galois_answer=galois_answer_str[:1000],
        euler_verdict=euler_verdict_str[:1000],
        euler_confidence=euler_conf,
        pythagore_draft=pyth_draft[:500],
        sorry_count=sorry_gaps,
        cost_usd=problem_cost,
        elapsed_s=elapsed,
        warm_start_used=warm_start,
    )

    run_state.total_cost += problem_cost
    run_state.budget_remaining -= problem_cost
    run_state.results.append(result)

    print(f"  ✅ [{pid}] Verdict: {euler_conf:.2f} | Sorry gaps: {sorry_gaps} | Cost: ${problem_cost:.2f} | Time: {elapsed:.1f}s")

    return result


async def generate_monograph(heraclite: HeracliteAgent, run_state: OlympiadRun) -> str:
    """Generate the final monograph via Heraclite."""
    synthesis = []
    for r in run_state.results:
        synthesis.append({
            "problem": r.problem_id,
            "solvability": r.solvability,
            "domain": r.domain,
            "galois_solution": r.galois_answer,
            "euler_verdict": r.euler_verdict,
            "euler_confidence": r.euler_confidence,
            "pythagore_draft": r.pythagore_draft,
            "sorry_count": r.sorry_count,
            "cost_usd": r.cost_usd,
            "warm_start": r.warm_start_used,
        })

    synthesis_str = json.dumps(synthesis, indent=2)
    import base64
    synthesis_b64 = base64.b64encode(synthesis_str.encode("utf-8")).decode("utf-8")
    report = await heraclite.run(
        f"Generate the official HorizonMath Top 20 Olympiad Monograph. "
        f"Total cost: ${run_state.total_cost:.2f}. "
        f"Budget: ${BUDGET_HARD_CAP_USD:.2f}. "
        f"Synthesis data (base64): {synthesis_b64}"
    )
    return report.answer


async def main():
    # 1. Load problems
    data_path = PROBLEMS_FILE if PROBLEMS_FILE.exists() else PROBLEMS_FILE_ALT
    if not data_path.exists():
        print(f"❌ Data file not found at {PROBLEMS_FILE} or {PROBLEMS_FILE_ALT}")
        return

    with open(data_path, "r") as f:
        all_problems = json.load(f)

    print(f"📚 Loaded {len(all_problems)} HorizonMath problems")

    # 2. Select top 20
    top20 = select_top_20(all_problems)
    print(f"🎯 Selected {len(top20)} problems for Olympiad execution")
    for i, p in enumerate(top20, 1):
        warm = "🔥" if p["id"] in V11_PRIOR_PROBLEMS else "  "
        print(f"  {warm} {i:2d}. {p['id']:45s} solv={p.get('solvability')} domain={p.get('domain')}")

    # 3. Initialize agents
    galois = GaloisAgent()
    galois.upgrade_to_v12()
    euler = EulerAgent()
    pythagore = PythagoreAgent()
    heraclite = HeracliteAgent()
    turing = TuringAgent()

    print(f"\n🧠 Galois cortex: {galois.cortex.symbrain_version}")
    print(f"💰 Budget: ${BUDGET_HARD_CAP_USD:.2f}")

    # 4. Execute
    run_state = OlympiadRun()

    print(f"\n🚀 Launching HorizonMath Top 20 Olympiad Execution (SymBrain v12.3)")
    print(f"   GPU Priority: H100 → A100 → L4 (backup)")
    print(f"   Leveraging v10/v11 warm-start for {len(V11_PRIOR_PROBLEMS)} problems")

    t_total = time.monotonic()

    for idx, prob in enumerate(top20, 1):
        result = await run_single_problem(
            idx, len(top20), prob,
            galois, euler, pythagore, turing,
            run_state,
        )
        if result is None:
            print(f"  ⏭️  Skipped {prob['id']} (budget guard)")

    elapsed_total = time.monotonic() - t_total

    # 5. Summary
    total_sorry = sum(r.sorry_count for r in run_state.results)
    verified = sum(1 for r in run_state.results if r.euler_confidence >= 0.85)
    incomplete = sum(1 for r in run_state.results if r.euler_confidence < 0.85)
    warm_used = sum(1 for r in run_state.results if r.warm_start_used)

    print(f"\n{'='*70}")
    print(f"  📊 OLYMPIAD EXECUTION SUMMARY")
    print(f"{'='*70}")
    print(f"  Problems attempted:  {len(run_state.results)}")
    print(f"  Verified (≥0.85):    {verified}")
    print(f"  Honest INCOMPLETE:   {incomplete}")
    print(f"  Total sorry gaps:    {total_sorry}")
    print(f"  Warm starts used:    {warm_used}")
    print(f"  Total cost:          ${run_state.total_cost:.2f} / ${BUDGET_HARD_CAP_USD:.2f}")
    print(f"  Total time:          {elapsed_total:.1f}s")
    print(f"{'='*70}")

    # 6. Generate monograph
    print(f"\n🏺 Curating final monograph via Heraclite...")
    monograph = await generate_monograph(heraclite, run_state)

    OUTPUT_DIR.mkdir(exist_ok=True, parents=True)
    MONOGRAPH_PATH.write_text(monograph)
    print(f"✅ Monograph saved to {MONOGRAPH_PATH}")

    # 7. Save raw results
    raw_path = OUTPUT_DIR / "horizonmath_top20_raw_results.json"
    raw_results = [
        {
            "problem_id": r.problem_id,
            "solvability": r.solvability,
            "domain": r.domain,
            "euler_confidence": r.euler_confidence,
            "sorry_count": r.sorry_count,
            "cost_usd": r.cost_usd,
            "elapsed_s": r.elapsed_s,
            "warm_start_used": r.warm_start_used,
        }
        for r in run_state.results
    ]
    raw_path.write_text(json.dumps(raw_results, indent=2))
    print(f"✅ Raw results saved to {raw_path}")


if __name__ == "__main__":
    asyncio.run(main())
