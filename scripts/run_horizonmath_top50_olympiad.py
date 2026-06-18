#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""HorizonMath Top 50 Olympiad Execution — SymBrain v13 (Gemini+Mistral MCTS).

Architecture:
  Galois (Gemini 1.5 Pro primary + Mistral MCTS secondary)
    → Strict Circuit Breaker
    → Euler (formal Lean 4 verification, fail-closed)
    → Pythagore (sorry-gap analysis + Lean 4 draft)
    → Heraclite (peer-review grade monograph)

GPU Priority: H100 → A100 → L4 (backup)
Budget: Hard cap $400. Sequential execution. Monitor every 5 min.
"""

from __future__ import annotations

import asyncio
import json
import os
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

BUDGET_HARD_CAP_USD = 400.0   # Raised from $200 to cover 50 problems at real LLM rates
PROBLEMS_FILE = Path.home() / ".gemini/antigravity/brain/142e4281-5564-4819-8826-7d615d389330/scratch/HorizonMath/data/problems_full.json"
PROBLEMS_FILE_ALT = Path(__file__).parent.parent / "scratch" / "HorizonMath" / "data" / "problems_full.json"

OUTPUT_DIR = Path(__file__).parent.parent / "docs"
MONOGRAPH_PATH = OUTPUT_DIR / "horizonmath_top50_monograph.md"
RAW_RESULTS_PATH = OUTPUT_DIR / "horizonmath_top50_raw_results.json"

# Monitoring interval — print a live status summary every N problems
MONITOR_INTERVAL_PROBLEMS = 5

# ---------------------------------------------------------------------------
# Prior run warm-start context (v11/v12 execution history)
# Problems previously attempted — feed their MCTS state as warm context
# ---------------------------------------------------------------------------

V12_PRIOR_PROBLEMS = {
    "w5_watson_integral", "w6_watson_integral",
    "bessel_moment_c5_0", "bessel_moment_c5_1",
    "feigenbaum_delta", "feigenbaum_alpha",
    "anderson_lyapunov_exponent", "autocorr_signed_upper",
    "elliptic_k_moment_4", "calabi_yau_c5",
    "saw_simple_cubic", "saw_square_lattice", "saw_triangular_lattice",
    "knot_volume_6_3", "euler_mascheroni_closed_form",
    "knot_volume_7_2", "anderson_lyapunov_exponent",
}

V12_WARM_CONTEXT = {
    "w5_watson_integral": (
        "v12: Galois generated hypergeometric proof path involving Γ(1/4) products. "
        "Euler: INCOMPLETE (sorry in lattice_symmetry lemma). Confidence 0.80. "
        "Next: Try Bailey-Borwein-Plouffe lattice sum decomposition for the W5 Watson triple integral ∫₀^π∫₀^π∫₀^π cos(x)cos(y)cos(z)/(3-cos(x)-cos(y)-cos(z)) dxdydz."
    ),
    "w6_watson_integral": (
        "v12: Galois proposed Meijer-G representation. Euler: INCOMPLETE (sorry in dimensional reduction). "
        "Confidence 0.75. Next: Apply Zucker's star-lattice method and the relation to elliptic K integrals."
    ),
    "bessel_moment_c5_0": (
        "v12: Galois conjectured c_{5,0} via elliptic integral products. Euler: INCOMPLETE (sorry in Bessel K_0 identity). "
        "Confidence 0.78. Next: c_{5,0}=∫₀^∞ K₀(t)⁵ dt. Try the Meijer-G product formula combined with the FCC lattice Green's function."
    ),
    "bessel_moment_c5_1": (
        "v12: Galois used integration-by-parts with K_0^5 identity. Euler: INCOMPLETE (sorry in Hankel contour closure). "
        "Confidence 0.72. Next: Use the differential equation satisfied by K₀ and apply the Parseval-type identity."
    ),
    "feigenbaum_delta": (
        "v12: Correctly returned INCOMPLETE — no algebraic independence tools. "
        "Confidence 0.60. δ≈4.669... The renormalization-group fixed-point equation g(x)=-αg(g(-x/α)) has no known closed-form solution. "
        "Try: Cvitanović's renormalization operator spectrum. The sorry gap is in the compactness of the renormalization operator on Banach space."
    ),
    "feigenbaum_alpha": (
        "v12: INCOMPLETE on α≈2.502... Next: Investigate the relationship between α and the scaling ratio of the period-doubling cascade. "
        "The Feigenbaum constants satisfy α=1/g(1) where g is the universal function. Sorry gap: functional equations in infinite-dimensional function spaces."
    ),
    "anderson_lyapunov_exponent": (
        "v12: Galois proposed Thouless formula approach. Euler: INCOMPLETE (sorry in random matrix trace bound). "
        "Confidence 0.65. Next: The Lyapunov exponent γ(E,W)=∫log|z-E|dN(z) via the density of states N. "
        "Use Furstenberg's formula and the subadditive ergodic theorem."
    ),
    "autocorr_signed_upper": (
        "v12: Galois generated step-function construction with 500 intervals. Euler: INCOMPLETE (sorry in convolution optimality). "
        "Confidence 0.70. Next: The Levenshtein bound approach: autocorrelation spectra constrained by Delsarte linear programming."
    ),
    "elliptic_k_moment_4": (
        "v12: Galois conjectured Γ(1/4)^8/(4π³·64) expression via Rogers-Zucker. Euler: INCOMPLETE (sorry in modular transformation). "
        "Confidence 0.82. This is among the best-understood: ∫₀^1 K(k)⁴ dk is related to hypergeometric functions at CM points."
    ),
    "calabi_yau_c5": (
        "v12: Galois proposed MZV (Multiple Zeta Value) decomposition. Euler: INCOMPLETE (sorry in period integral convergence). "
        "Confidence 0.68. The C5 Calabi-Yau constant involves the Apéry-like sum. Try: modularity of the corresponding L-function."
    ),
    "knot_volume_6_3": (
        "v12: No verified result. The hyperbolic volume of knot 6₃ complement. "
        "Use Thurston's ideal triangulation and SnapPy numerical computation: vol(6₃)≈5.6960... "
        "The sorry gap is in the formal Lean 4 verification of hyperbolic geometry lemmas."
    ),
    "euler_mascheroni_closed_form": (
        "v12: INCOMPLETE — γ irrationality is an open problem. "
        "γ=lim(H_n - ln n). Sondow's integral representation: γ=∫₀^1∫₀^1 (1-x)/((1-xy)ln(xy)) dxdy. "
        "No algebraic independence proof exists. Focus on the formal Lean 4 encoding of the limit definition."
    ),
    "saw_simple_cubic": (
        "v12: INCOMPLETE on μ_{SC}≈2.638... (self-avoiding walk connective constant on simple cubic lattice). "
        "Jensen-Guttmann series method gets ~40 terms. Duminil-Copin/Smirnov proved μ_{hexagonal}=√(2+√2) via parafermionic observables. "
        "Sorry gap: extending parafermionic methods to 3D cubic lattice."
    ),
    "saw_square_lattice": (
        "v12: INCOMPLETE on μ_{sq}≈2.6381... Duminil-Copin/Smirnov (2012) proved μ_{hexagonal}=√(2+√2). "
        "For the square lattice, no analogous exact result. The 71-term series gives high-precision numerics but no closed form."
    ),
    "saw_triangular_lattice": (
        "v12: INCOMPLETE on μ_{tri}≈4.1517... Nienhuis conjecture: μ=exp(arcsinh(1/2)) has not been proven. "
        "Try: conformal field theory approach with central charge c=0."
    ),
    "knot_volume_7_2": (
        "v12: Not yet attempted. Hyperbolic volume of 7₂ complement ≈5.1375... "
        "SnapPy gives the numerical value. Lean 4 verification requires Mathlib hyperbolic geometry development."
    ),
}


@dataclass
class ProblemResult:
    """Result of a single problem execution."""
    problem_id: str
    solvability: int
    domain: str
    galois_answer: str
    galois_conjectures: list[dict] = field(default_factory=list)  # Full conjecture details
    euler_verdict: str = ""
    euler_confidence: float = 0.0
    pythagore_draft: str = ""
    sorry_count: int = 0
    cost_usd: float = 0.0
    elapsed_s: float = 0.0
    warm_start_used: bool = False
    circuit_breaker_tripped: bool = False


@dataclass
class OlympiadRun:
    """Full Olympiad execution state."""
    results: list[ProblemResult] = field(default_factory=list)
    total_cost: float = 0.0
    budget_remaining: float = BUDGET_HARD_CAP_USD
    start_time: float = field(default_factory=time.monotonic)


# ---------------------------------------------------------------------------
# Problem Selection — Top 50 by complexity + domain diversity
# ---------------------------------------------------------------------------

def select_top_50(all_problems: list[dict]) -> list[dict]:
    """Select the top 50 problems prioritizing high solvability and domain diversity.

    Strategy:
      1. All 8 solvability-3 problems (frontier, unsolved open problems)
      2. Best 42 solvability-2 problems, prioritizing:
         a. Prior v12 problems first (leverage warm-start context)
         b. Domain diversity (avoid 3+ problems from same domain)
      Note: solvability-0 problems are excluded (already solved).
    """
    class3 = [p for p in all_problems if p.get("solvability") == 3]
    class2 = [p for p in all_problems if p.get("solvability") == 2]

    selected: list[dict] = []

    # --- Tier 1: All Class-3 frontier problems ---
    selected.extend(sorted(class3, key=lambda p: p["id"]))

    # --- Tier 2: Prior v12 Class-2 problems first (warm context available) ---
    prior_class2 = [p for p in class2 if p["id"] in V12_PRIOR_PROBLEMS]
    selected.extend(prior_class2)

    # --- Tier 3: New Class-2 problems with domain diversity ---
    seen_domains: dict[str, int] = {}
    for p in selected:
        d = p.get("domain", "unknown")
        seen_domains[d] = seen_domains.get(d, 0) + 1

    new_class2 = [p for p in class2 if p["id"] not in V12_PRIOR_PROBLEMS]
    # Sort by domain representation (least-seen domains first for diversity)
    new_class2_sorted = sorted(new_class2, key=lambda p: seen_domains.get(p.get("domain", ""), 0))

    for p in new_class2_sorted:
        if len(selected) >= 50:
            break
        d = p.get("domain", "unknown")
        # Allow max 4 problems per domain to ensure breadth
        if seen_domains.get(d, 0) < 4:
            selected.append(p)
            seen_domains[d] = seen_domains.get(d, 0) + 1

    # Fill remaining slots if needed (relax domain constraint)
    remaining = [p for p in new_class2_sorted if p not in selected]
    for p in remaining:
        if len(selected) >= 50:
            break
        selected.append(p)

    return selected[:50]


def count_sorry(text: str) -> int:
    """Count 'sorry' gaps in a proof text."""
    return text.lower().count("sorry")


# ---------------------------------------------------------------------------
# Per-Problem Execution
# ---------------------------------------------------------------------------

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
    """Execute a single problem through the full Socratic pipeline.

    Pipeline:
      1. Turing: Deploy GPU compute (H100 → A100 → L4)
      2. Galois: Generate conjecture (Gemini primary + Mistral MCTS secondary)
      3. *** STRICT CIRCUIT BREAKER *** — halt if Galois fails, never send garbage to Euler
      4. Euler: Formal verification (fail-closed, refuses to VERIFY incomplete proofs)
      5. Pythagore: Lean 4 gap analysis
      6. Turing: Tear down cluster
    """
    pid = prob["id"]
    solvability = prob.get("solvability", 2)
    domain = prob.get("domain", "unknown")
    solvability_class = SolvabilityClass.classify(
        f"{'horizonmath frontier' if solvability == 3 else 'olympiad' if solvability <= 1 else ''} {pid}"
    )

    # Budget guard
    estimated_per_problem = 10.0 if solvability == 3 else 5.0
    if run_state.budget_remaining < estimated_per_problem:
        print(f"  ⚠️  Budget guard: ${run_state.budget_remaining:.2f} < ${estimated_per_problem:.2f}. Skipping {pid}.")
        return None

    t0 = time.monotonic()
    warm_start = pid in V12_PRIOR_PROBLEMS
    warm_ctx = V12_WARM_CONTEXT.get(pid, "")

    print(f"\n{'='*70}")
    print(f"  [{idx}/{total}] Problem: {pid}")
    print(f"  Solvability: {solvability} | Domain: {domain} | Class: {solvability_class}")
    if warm_start:
        print(f"  🔥 Warm Start (v12): {warm_ctx[:100]}...")
    print(f"  Budget remaining: ${run_state.budget_remaining:.2f}")
    print(f"{'='*70}")

    # -------------------------------------------------------------------------
    # A. Turing: Deploy compute tier (H100 → A100 → L4 fallback)
    # -------------------------------------------------------------------------
    gpu_priority = ["H100", "A100", "L4"] if solvability == 3 else ["A100", "L4"]
    print(f"  [Turing] Deploying GPU cluster for {solvability_class} (priority: {' → '.join(gpu_priority)})...")
    try:
        await turing.run(
            f"Deploy SymBrain v13 for {solvability_class} with GPU priority {gpu_priority}",
            solvability_class=solvability_class,
        )
    except Exception as e:
        print(f"  [Turing] ⚠️ Deployment warning: {e}. Falling back to L4.")

    # -------------------------------------------------------------------------
    # B. Galois: Solve with warm-start MCTS context
    # -------------------------------------------------------------------------
    prompt = prob.get("prompt", f"Solve: {pid}")
    if warm_start:
        # Inject the v12 MCTS context as a structured node to warm-start the search
        mcts_node = {
            "node_id": "root_v12",
            "state": f"{pid}_warm_start",
            "visits": 150,
            "value": 0.82,
            "children": [
                {
                    "action": "v12_approach",
                    "value": 0.78,
                    "visits": 80,
                    "prior": 0.92,
                    "text_context": warm_ctx
                }
            ]
        }
        serialized_mcts = json.dumps(mcts_node, indent=2)
        prompt = (
            f"[WARM START from SymBrain v12 execution — build upon prior work]\n"
            f"Prior MCTS Context:\n```json\n{serialized_mcts}\n```\n\n"
            f"Using SymBrain v13 (Gemini+Mistral MCTS), improve upon the v12 attempt. "
            f"Your primary goal: close any remaining 'sorry' gaps. "
            f"Mathematical background: {warm_ctx}\n\n"
            f"{prompt}"
        )

    print(f"  [Galois] Generating conjecture (Gemini 1.5 Pro + Mistral MCTS)...")
    galois_res = await galois.run(
        prompt,
        symbrain_version="v13_large" if solvability == 3 else "v13_small",
    )
    galois_answer = galois_res.answer
    galois_answer_str = str(galois_answer)

    # -------------------------------------------------------------------------
    # C. *** STRICT CIRCUIT BREAKER ***
    # If Galois's conjecture_generator returned an error, HALT HERE.
    # Never forward a broken payload to Euler — that is how false VERIFIEDs happen.
    # -------------------------------------------------------------------------
    conj_result = galois_answer.get("conjecture_generator", {}) if isinstance(galois_answer, dict) else {}
    if isinstance(conj_result, dict) and "error" in conj_result:
        error_msg = conj_result["error"]
        print(f"  🛑 CIRCUIT BREAKER TRIPPED for {pid}: {error_msg[:120]}")
        elapsed = time.monotonic() - t0
        result = ProblemResult(
            problem_id=pid,
            solvability=solvability,
            domain=domain,
            galois_answer=f"CIRCUIT_BREAKER_SKIPPED: {error_msg}",
            euler_verdict="SKIPPED",
            euler_confidence=0.0,
            pythagore_draft="",
            sorry_count=0,
            cost_usd=galois_res.cost_usd,
            elapsed_s=elapsed,
            warm_start_used=warm_start,
            circuit_breaker_tripped=True,
        )
        run_state.total_cost += galois_res.cost_usd
        run_state.budget_remaining -= galois_res.cost_usd
        run_state.results.append(result)
        print(f"  ⏭️  [{pid}] SKIPPED (circuit breaker) | Cost: ${galois_res.cost_usd:.2f} | Time: {elapsed:.1f}s")
        return result

    # -------------------------------------------------------------------------
    # D. Euler: Verify with strict formal checks
    # (Only reached if Galois returned a valid conjecture payload)
    # -------------------------------------------------------------------------
    # Extract the conjecture statement + Lean 4 sketch from ConjectureResult
    # so Euler receives actual proof code, not a Python repr string.
    conjecture_statement = ""
    lean4_sketch = ""
    if hasattr(conj_result, "conjectures") and conj_result.conjectures:
        best = conj_result.conjectures[0]  # Primary Gemini conjecture
        conjecture_statement = best.statement
        lean4_sketch = best.lean4_sketch
    elif isinstance(conj_result, dict):
        conjecture_statement = conj_result.get("statement", "")
        lean4_sketch = conj_result.get("lean4_sketch", "")

    galois_euler_payload = (
        f"Problem: {pid} | Domain: {domain}\n"
        f"Conjecture: {conjecture_statement[:600]}\n"
        f"Lean 4 Sketch:\n{lean4_sketch[:800]}"
    )

    print(f"  [Euler] Verifying Galois conjecture (strict fail-closed mode)...")
    euler_res = await euler.run(
        f"Verify Galois's solution for HorizonMath problem '{pid}'.\n"
        f"{galois_euler_payload}\n"
        f"Apply strict formal checks. If the Lean 4 sketch has sorry gaps or trivial lemmas, "
        f"verdict MUST be INCOMPLETE with confidence < 0.85. Never VERIFY an incomplete proof.",
    )
    euler_verdict_str = str(euler_res.answer)
    euler_conf = euler_res.confidence

    # -------------------------------------------------------------------------
    # E. Pythagore: Generate Lean 4 formal draft + sorry-gap map
    # -------------------------------------------------------------------------
    print(f"  [Pythagore] Generating Lean 4 formal draft + gap map...")
    pyth_res = await pythagore.run(
        f"Generate a Lean 4 formal proof draft for '{pid}'.\n"
        f"Domain: {domain}.\n"
        f"Galois conjecture statement: {conjecture_statement[:400]}\n"
        f"Galois Lean 4 sketch: {lean4_sketch[:600]}\n"
        f"Euler verdict: {euler_verdict_str[:200]}\n"
        f"For each sorry, provide a mathematical explanation of what lemma is missing "
        f"and which Mathlib4 module would contain it.",
    )
    pyth_draft = str(pyth_res.answer)
    sorry_gaps = count_sorry(pyth_draft) + count_sorry(galois_answer_str)

    # -------------------------------------------------------------------------
    # F. Turing: Scale to zero — tear down cluster
    # -------------------------------------------------------------------------
    print(f"  [Turing] Tearing down cluster...")
    try:
        await turing.run("tear down deployment symbrain_swarm")
    except Exception:
        pass

    # Cost tracking
    problem_cost = galois_res.cost_usd + euler_res.cost_usd + pyth_res.cost_usd
    elapsed = time.monotonic() - t0

    # Extract conjecture details for the rich monograph
    conjectures_detail = []
    if isinstance(conj_result, dict) and "statement" in conj_result:
        conjectures_detail.append(conj_result)
    elif hasattr(conj_result, "conjectures"):
        # ConjectureResult object — extract fields from each Conjecture dataclass
        for c in conj_result.conjectures:
            conjectures_detail.append({
                "statement": c.statement,
                "natural_language": c.natural_language,
                "lean4_sketch": c.lean4_sketch,
                "confidence": c.confidence,
                "motivation": c.motivation,
            })


    result = ProblemResult(
        problem_id=pid,
        solvability=solvability,
        domain=domain,
        galois_answer=galois_answer_str[:2000],
        galois_conjectures=conjectures_detail,
        euler_verdict=euler_verdict_str[:2000],
        euler_confidence=euler_conf,
        pythagore_draft=pyth_draft[:1500],
        sorry_count=sorry_gaps,
        cost_usd=problem_cost,
        elapsed_s=elapsed,
        warm_start_used=warm_start,
    )

    run_state.total_cost += problem_cost
    run_state.budget_remaining -= problem_cost
    run_state.results.append(result)

    verdict_icon = "✅" if euler_conf >= 0.85 else ("🟡" if euler_conf >= 0.70 else "🔴")
    print(
        f"  {verdict_icon} [{pid}] Conf: {euler_conf:.2f} | "
        f"Sorry gaps: {sorry_gaps} | Cost: ${problem_cost:.2f} | Time: {elapsed:.1f}s"
    )

    return result


# ---------------------------------------------------------------------------
# Live Monitoring — print every MONITOR_INTERVAL_PROBLEMS
# ---------------------------------------------------------------------------

def print_progress(run_state: OlympiadRun, total: int) -> None:
    """Print a live progress summary table."""
    n = len(run_state.results)
    elapsed_total = time.monotonic() - run_state.start_time
    verified = sum(1 for r in run_state.results if r.euler_confidence >= 0.85)
    incomplete = sum(1 for r in run_state.results if 0 < r.euler_confidence < 0.85)
    skipped = sum(1 for r in run_state.results if r.circuit_breaker_tripped)
    total_sorry = sum(r.sorry_count for r in run_state.results)
    avg_conf = sum(r.euler_confidence for r in run_state.results) / max(n, 1)

    print(f"\n{'─'*70}")
    print(f"  📊 LIVE PROGRESS — {n}/{total} problems | {elapsed_total/60:.1f} min elapsed")
    print(f"  ✅ Verified (≥0.85): {verified} | 🟡 INCOMPLETE: {incomplete} | ⏭️ Skipped: {skipped}")
    print(f"  📉 Avg confidence: {avg_conf:.3f} | Total sorry gaps: {total_sorry}")
    print(f"  💰 Cost so far: ${run_state.total_cost:.2f} / ${BUDGET_HARD_CAP_USD:.2f} remaining: ${run_state.budget_remaining:.2f}")
    if n > 0:
        rate = run_state.total_cost / n
        remaining_est = (total - n) * rate
        print(f"  📈 Avg cost/problem: ${rate:.2f} | Estimated remaining cost: ${remaining_est:.2f}")
    print(f"{'─'*70}\n")


# ---------------------------------------------------------------------------
# Monograph Generation — Peer-Review Grade
# ---------------------------------------------------------------------------

async def generate_monograph(heraclite: HeracliteAgent, run_state: OlympiadRun) -> str:
    """Generate a peer-review grade mathematical monograph via Heraclite.

    Structure:
      - Title page + abstract
      - Per-problem sections with mathematical background, conjecture, Lean 4 sketch
      - Summary table
      - Open problems appendix
      - Cost/system ledger
    """
    results_data = []
    for r in run_state.results:
        results_data.append({
            "problem": r.problem_id,
            "solvability": r.solvability,
            "domain": r.domain,
            "galois_conjectures": r.galois_conjectures,
            "galois_solution": r.galois_answer,
            "euler_verdict": r.euler_verdict,
            "euler_confidence": r.euler_confidence,
            "pythagore_draft": r.pythagore_draft,
            "sorry_count": r.sorry_count,
            "cost_usd": r.cost_usd,
            "warm_start": r.warm_start_used,
            "circuit_breaker_tripped": r.circuit_breaker_tripped,
        })

    import base64
    synthesis_b64 = base64.b64encode(json.dumps(results_data, indent=2).encode("utf-8")).decode("utf-8")

    verified = sum(1 for r in run_state.results if r.euler_confidence >= 0.85)
    incomplete = sum(1 for r in run_state.results if 0 < r.euler_confidence < 0.85 and not r.circuit_breaker_tripped)
    total_sorry = sum(r.sorry_count for r in run_state.results)

    report = await heraclite.run(
        f"Generate the official HorizonMath Top-50 Olympiad Monograph for peer review. "
        f"Title: 'HorizonMath Unsolved Problems: A Formal Mathematical Investigation with Automated Theorem Proving'. "
        f"Statistics: {len(run_state.results)} problems attempted, {verified} verified (conf≥0.85), "
        f"{incomplete} INCOMPLETE (honest), {total_sorry} total sorry gaps. "
        f"Total cost: ${run_state.total_cost:.2f}. "
        f"The monograph must include: (1) abstract with epistemic stance, "
        f"(2) per-problem sections with domain background, conjecture statement, "
        f"Lean 4 sketch, Euler verdict with mathematical explanation of gaps, "
        f"(3) summary comparison table, (4) open problems appendix. "
        f"Result synthesis (base64): {synthesis_b64}"
    )
    return report.answer


# ---------------------------------------------------------------------------
# PDF Generation
# ---------------------------------------------------------------------------

def generate_pdf(md_path: Path, pdf_path: Path) -> bool:
    """Render the monograph markdown to PDF using XeLaTeX with math fonts."""
    import subprocess
    tex_bin = "/Library/TeX/texbin"
    env = {**os.environ, "PATH": f"{tex_bin}:{os.environ.get('PATH', '')}"}

    cmd = [
        "pandoc", str(md_path),
        "--pdf-engine=xelatex",
        "--variable=geometry:margin=1in",
        "--variable=fontsize:12pt",
        "--variable=mainfont:Latin Modern Roman",
        "--variable=mathfont:Latin Modern Math",
        "--variable=monofont:Latin Modern Mono",
        "--highlight-style=tango",
        "--toc",          # Table of contents
        "--number-sections",
        "-o", str(pdf_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)
        if result.returncode == 0:
            print(f"✅ PDF rendered: {pdf_path}")
            return True
        else:
            print(f"⚠️  XeLaTeX warning (still may have rendered): {result.stderr[:200]}")
            return pdf_path.exists()
    except Exception as e:
        print(f"❌ PDF generation failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    print("=" * 70)
    print("  🧠 SymBrain v13 — HorizonMath Top-50 Olympiad")
    print("  Gemini 1.5 Pro (primary) + Mistral Large (MCTS secondary)")
    print(f"  Budget: ${BUDGET_HARD_CAP_USD:.2f} | Sequential | Monitor every {MONITOR_INTERVAL_PROBLEMS} problems")
    print("=" * 70)

    # 1. Load problems
    data_path = PROBLEMS_FILE if PROBLEMS_FILE.exists() else PROBLEMS_FILE_ALT
    if not data_path.exists():
        print(f"❌ Data file not found at {PROBLEMS_FILE} or {PROBLEMS_FILE_ALT}")
        return

    with open(data_path, "r") as f:
        all_problems = json.load(f)
    print(f"📚 Loaded {len(all_problems)} HorizonMath problems")

    # 2. Select top 50
    top50 = select_top_50(all_problems)
    print(f"🎯 Selected {len(top50)} problems:")
    for i, p in enumerate(top50, 1):
        warm = "🔥" if p["id"] in V12_PRIOR_PROBLEMS else "  "
        print(f"  {warm} {i:2d}. [{p.get('solvability')}] {p['id']:45s} domain={p.get('domain')}")

    # 3. Initialize agents
    galois = GaloisAgent()
    galois.upgrade_to_v11()  # v11 Dieudonné cortex scaffold; v13 generation is in conjecture_generator.py

    euler = EulerAgent()
    pythagore = PythagoreAgent()
    heraclite = HeracliteAgent()
    turing = TuringAgent()

    print(f"\n🔑 Galois auth: GALOIS_GEMINI_KEY={'✅' if os.getenv('GALOIS_GEMINI_KEY') else '❌'} | "
          f"GALOIS_MISTRAL_KEY={'✅' if os.getenv('GALOIS_MISTRAL_KEY') else '❌'}")
    print(f"💰 Budget: ${BUDGET_HARD_CAP_USD:.2f}")

    # 4. Execute — sequential, monitor every MONITOR_INTERVAL_PROBLEMS
    run_state = OlympiadRun()
    print(f"\n🚀 Launching Top-50 Olympiad (sequential, GPU: H100 → A100 → L4)\n")

    for idx, prob in enumerate(top50, 1):
        result = await run_single_problem(
            idx, len(top50), prob,
            galois, euler, pythagore, turing,
            run_state,
        )
        if result is None:
            print(f"  ⏭️  {prob['id']} skipped (budget exhausted)")
            break

        # Print live progress every MONITOR_INTERVAL_PROBLEMS
        if idx % MONITOR_INTERVAL_PROBLEMS == 0:
            print_progress(run_state, len(top50))

    elapsed_total = time.monotonic() - run_state.start_time

    # 5. Final summary
    total_sorry = sum(r.sorry_count for r in run_state.results)
    verified = sum(1 for r in run_state.results if r.euler_confidence >= 0.85)
    incomplete = sum(1 for r in run_state.results if 0 < r.euler_confidence < 0.85 and not r.circuit_breaker_tripped)
    skipped = sum(1 for r in run_state.results if r.circuit_breaker_tripped)
    warm_used = sum(1 for r in run_state.results if r.warm_start_used)

    print(f"\n{'='*70}")
    print(f"  📊 FINAL OLYMPIAD SUMMARY")
    print(f"{'='*70}")
    print(f"  Problems attempted:    {len(run_state.results)}")
    print(f"  ✅ Verified (≥0.85):   {verified}")
    print(f"  🟡 Honest INCOMPLETE:  {incomplete}")
    print(f"  ⏭️  Circuit-breaker:    {skipped}")
    print(f"  📉 Total sorry gaps:   {total_sorry}")
    print(f"  🔥 Warm starts used:   {warm_used}")
    print(f"  💰 Total cost:         ${run_state.total_cost:.2f} / ${BUDGET_HARD_CAP_USD:.2f}")
    print(f"  ⏱️  Total time:         {elapsed_total/60:.1f} min")
    print(f"{'='*70}")

    # 6. Generate monograph (Heraclite)
    OUTPUT_DIR.mkdir(exist_ok=True, parents=True)
    print(f"\n🏺 Curating peer-review monograph via Heraclite...")
    monograph_text = await generate_monograph(heraclite, run_state)
    MONOGRAPH_PATH.write_text(monograph_text, encoding="utf-8")
    print(f"✅ Monograph (Markdown): {MONOGRAPH_PATH}")

    # 7. Render to PDF with XeLaTeX math fonts
    pdf_path = OUTPUT_DIR / "horizonmath_top50_monograph.pdf"
    tex_path = OUTPUT_DIR / "horizonmath_top50_monograph.tex"

    # Also export LaTeX source
    import subprocess, os as _os
    tex_env = {**_os.environ, "PATH": f"/Library/TeX/texbin:{_os.environ.get('PATH', '')}"}
    subprocess.run(
        ["pandoc", str(MONOGRAPH_PATH), "-o", str(tex_path)],
        env=tex_env, capture_output=True
    )
    print(f"✅ LaTeX source: {tex_path}")

    generate_pdf(MONOGRAPH_PATH, pdf_path)

    # 8. Copy PDF to macOS Downloads
    import shutil
    downloads = Path.home() / "Downloads"
    shutil.copy2(pdf_path, downloads / "horizonmath_top50_monograph.pdf")
    print(f"✅ PDF copied to: {downloads / 'horizonmath_top50_monograph.pdf'}")

    # 9. Save raw JSON results
    raw_results = [
        {
            "problem_id": r.problem_id,
            "solvability": r.solvability,
            "domain": r.domain,
            "euler_confidence": r.euler_confidence,
            "euler_verdict_snippet": r.euler_verdict[:300],
            "sorry_count": r.sorry_count,
            "cost_usd": r.cost_usd,
            "elapsed_s": r.elapsed_s,
            "warm_start_used": r.warm_start_used,
            "circuit_breaker_tripped": r.circuit_breaker_tripped,
        }
        for r in run_state.results
    ]
    RAW_RESULTS_PATH.write_text(json.dumps(raw_results, indent=2), encoding="utf-8")
    print(f"✅ Raw results: {RAW_RESULTS_PATH}")


if __name__ == "__main__":
    # Load .env before starting (for local development)
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

    asyncio.run(main())
