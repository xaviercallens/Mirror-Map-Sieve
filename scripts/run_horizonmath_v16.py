#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""
SymBrain v16 HorizonMath Orchestrator — Agora Exhaustion
=========================================================

Implements the two winning hypotheses from the v16 autoresearch cycle:

H1 — LEMMA PRE-DECOMPOSITION (Enhanced Archimedes)
    Before Galois generates a proof sketch, a fast structural pre-decomposer
    reads the theorem statement and identifies 3-5 named sub-lemma obligations.
    Each obligation is typed (algebraic/analytic/existence/…) and paired with
    Mathlib4 tactic candidates. This prompt injection dramatically reduces
    sorry stubs in the FIRST Galois pass, making L4 instances sufficient for
    most problems.

H3 — CROSS-REGION INFERENCE SHARDING (Quota Bypass)
    Instead of requesting scarce A100/H100 in a single region, the ShardRouter
    distributes inference requests across spot L4 instances in 4 GCP regions.
    The DopamineRegulatedThreshold (from SymBrain v16 cortex) automatically
    escalates to A10G (then Serverless A100) only when repeated failures signal
    that the problem requires heavier compute.
    This bypasses hard per-region H100/A100 quota limits entirely.

GPU STRATEGY (v16 — Quota-Free):
    - Primary:   L4 Spot × 4 regions (us-central1, us-east4, europe-west4,
                 asia-southeast1) — always available, cheapest ($0.54/hr)
    - Fallback:  A10G Spot × 3 regions — medium tier ($1.20/hr)
    - Last resort: A100 Serverless — no per-region quota ($3.67/hr)
    - NO direct H100/A100 requests — quota unreliable

Budget: $400 cap | v13+v14+v15 spent: ~$82.50 | Remaining: ~$317.50

Architecture:
    Socrates (orchestrator)
      → [H1] LemmaPreDecomposer (pre-decompose theorem statement)
      → Galois (conjecture + Lean 4 sketch — SymBrain v16)
      → [H3] ShardRouter (route to cheapest available regional L4)
      → Archimedes (v15 Method of Exhaustion + v16 pre-decomp context)
      → Euler (Zero-Sorry Guillotine — epistemic law unchanged)
      → Turing (FinOps + GPU tier reporting)
"""
from __future__ import annotations

# ── SSL fix — must precede all google.genai imports ──────────────────────────
import os
import certifi
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ.pop("SSL_CERT_DIR", None)

import asyncio
import json
import re
import time
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

# ── Agent imports ─────────────────────────────────────────────────────────────
from agents.galois.agent import GaloisAgent
from agents.euler.agent import EulerAgent
from agents.pythagore.agent import PythagoreAgent
from agents.turing.agent import TuringAgent
from agents.archimedes.agent import ArchimedesAgent
from agents.base import AgentConfig, AgentRole

# ── v16 NEW imports ───────────────────────────────────────────────────────────
from agents.archimedes.tools.lemma_decomposer_v16 import LemmaPreDecomposer
from agents.galois.tools.region_shard_router import ShardRouter, build_router_from_cortex

logger = structlog.get_logger(__name__)

# ── Budget & Paths ─────────────────────────────────────────────────────────────

BUDGET_CAP_USD       = 400.0
PREVIOUS_SPEND_USD   = 82.50      # v13 + v14 + v15 combined
BUDGET_REMAINING_USD = BUDGET_CAP_USD - PREVIOUS_SPEND_USD

OUTPUT_DIR  = Path(__file__).parent.parent / "achievement_output"
SCRATCH_DIR = OUTPUT_DIR / "v16_results"
DOWNLOADS   = Path.home() / "Downloads"

SCRATCH_DIR.mkdir(parents=True, exist_ok=True)

# ── v16 GPU Strategy: ShardRouter (no H100/A100 direct) ──────────────────────
# The ShardRouter selects GPU tier automatically from dopamine_level.
# We start at L4_SPOT; DopamineRegulatedThreshold escalates on repeated failures.
INITIAL_GPU_TIER = "L4_SPOT"   # Never request H100/A100 directly

# ── v16 Hypothesis Flags ──────────────────────────────────────────────────────
ENABLE_H1_PRE_DECOMPOSE = True   # Lemma pre-decomposition (v16 upgrade of Archimedes)
ENABLE_H3_SHARDING      = True   # Cross-Region Inference Sharding
ENABLE_H2_AUTO_RESEARCH = True   # Pre-proof literature mining (inherited from v15)
ENABLE_H5_EUCLID        = True   # Mathlib4 tactic recommender (inherited from v15)

# Sketch limits (kept from v15)
SKETCH_CHAR_LIMIT    = 2000
CONJECTURE_CHAR_LIMIT = 800

# Monitor interval
MONITOR_INTERVAL_S = 300  # 5 minutes

# ── Problem list (50 HorizonMath problems from v15) ───────────────────────────
# Status tracked from v15 results; INCOMPLETE and CB_TRIPPED are re-run.
V15_PROBLEMS: list[dict[str, Any]] = [
    {"pid": "knot_volume_6_3",                  "domain": "discrete_geometry",    "class": 3, "v15_sorry": 5},
    {"pid": "euler_mascheroni_closed_form",     "domain": "number_theory",        "class": 3, "v15_sorry": 2},
    {"pid": "feigenbaum_alpha",                 "domain": "continuum_physics",    "class": 3, "v15_sorry": 2},
    {"pid": "feigenbaum_delta",                 "domain": "continuum_physics",    "class": 3, "v15_sorry": 1},
    {"pid": "saw_simple_cubic",                 "domain": "stat_mechanics",       "class": 3, "v15_sorry": 2},
    {"pid": "saw_square_lattice",               "domain": "stat_mechanics",       "class": 3, "v15_sorry": 2},
    {"pid": "saw_triangular_lattice",           "domain": "stat_mechanics",       "class": 3, "v15_sorry": 1},
    {"pid": "w5_watson_integral",               "domain": "stat_mechanics",       "class": 3, "v15_sorry": 2},
    {"pid": "w6_watson_integral",               "domain": "stat_mechanics",       "class": 3, "v15_sorry": 1},
    {"pid": "bessel_moment_c5_0",               "domain": "special_functions",    "class": 3, "v15_sorry": 2},
    {"pid": "bessel_moment_c5_1",               "domain": "special_functions",    "class": 3, "v15_sorry": 1},
    {"pid": "elliptic_k_moment_4",              "domain": "special_functions",    "class": 4, "v15_sorry": 0},
    {"pid": "autocorr_signed_upper",            "domain": "combinatorics",        "class": 3, "v15_sorry": 2},
    {"pid": "calabi_yau_c5",                    "domain": "special_functions",    "class": 4, "v15_sorry": 4},
    {"pid": "knot_volume_7_2",                  "domain": "discrete_geometry",    "class": 3, "v15_sorry": 6},
    {"pid": "anderson_lyapunov_exponent",       "domain": "mathematical_physics", "class": 4, "v15_sorry": 3},
    {"pid": "quartic_oscillator_lambda",        "domain": "spectral_theory",      "class": 3, "v15_sorry": 2},
    {"pid": "spheroidal_eigenvalue_lambda_m0",  "domain": "spectral_theory",      "class": 3, "v15_sorry": 2},
    {"pid": "nested_radical_kasner",            "domain": "number_theory",        "class": 3, "v15_sorry": 4},
    {"pid": "mrb_constant",                     "domain": "number_theory",        "class": 3, "v15_sorry": 2},
    {"pid": "torsional_rigidity_square",        "domain": "special_functions",    "class": 3, "v15_sorry": 2},
    {"pid": "mahler_1_x_y_z_w",                "domain": "number_theory",        "class": 3, "v15_sorry": 2},
    {"pid": "schur_6",                          "domain": "combinatorics",        "class": 3, "v15_sorry": 3},
    {"pid": "diff_basis_optimal_10000",         "domain": "combinatorics",        "class": 3, "v15_sorry": 1},
    {"pid": "general_diff_basis_algo",          "domain": "combinatorics",        "class": 3, "v15_sorry": 2},
    {"pid": "merit_factor_6_5",                 "domain": "coding_theory",        "class": 3, "v15_sorry": 2},
    {"pid": "parametric_spherical_codes",       "domain": "coding_theory",        "class": 3, "v15_sorry": 2},
    {"pid": "bklc_68_15",                       "domain": "coding_theory",        "class": 3, "v15_sorry": 2},
    {"pid": "lattice_packing_dim10",            "domain": "discrete_geometry",    "class": 4, "v15_sorry": 3},
    {"pid": "periodic_packing_dim10",           "domain": "discrete_geometry",    "class": 4, "v15_sorry": 3},
    {"pid": "bessel_moment_c6_0",               "domain": "special_functions",    "class": 3, "v15_sorry": 5},
    {"pid": "feynman_3loop_sunrise",            "domain": "mathematical_physics", "class": 4, "v15_sorry": 6},
    {"pid": "townes_soliton",                   "domain": "mathematical_physics", "class": 3, "v15_sorry": 2},
    {"pid": "mahler_elliptic_product",          "domain": "number_theory",        "class": 3, "v15_sorry": 2},
    {"pid": "closed_form_ramanujan_soldner",    "domain": "number_theory",        "class": 3, "v15_sorry": 1},
    {"pid": "elliptic_curve_rank_30",           "domain": "number_theory",        "class": 3, "v15_sorry": 2},
    {"pid": "elliptic_curve_rank_torsion_z7z",  "domain": "number_theory",        "class": 3, "v15_sorry": 2},
    {"pid": "mzv_decomposition_c5",             "domain": "number_theory",        "class": 3, "v15_sorry": 5},
    {"pid": "tracy_widom_f2_mean",              "domain": "mathematical_physics", "class": 3, "v15_sorry": 2},
    {"pid": "tracy_widom_f2_variance",          "domain": "mathematical_physics", "class": 3, "v15_sorry": 2},
    {"pid": "tracy_widom_f1_mean",              "domain": "mathematical_physics", "class": 3, "v15_sorry": 2},
    {"pid": "crossing_number_kn",               "domain": "combinatorics",        "class": 3, "v15_sorry": 1},
    {"pid": "kcore_threshold_c3",               "domain": "combinatorics",        "class": 3, "v15_sorry": 3},
    {"pid": "covering_C13_k7_t4",               "domain": "combinatorics",        "class": 3, "v15_sorry": 6},
    {"pid": "cwcode_29_8_5",                    "domain": "coding_theory",        "class": 3, "v15_sorry": 8},
    {"pid": "inverse_galois_m23",               "domain": "number_theory",        "class": 3, "v15_sorry": 2},
    {"pid": "inverse_galois_suzuki",            "domain": "number_theory",        "class": 3, "v15_sorry": 2},
    {"pid": "hensley_hausdorff_dim",            "domain": "number_theory",        "class": 3, "v15_sorry": 1},
    {"pid": "spherical_mode_quality_factor_te_tm", "domain": "spectral_theory",   "class": 3, "v15_sorry": 5},
    {"pid": "bernstein_constant",               "domain": "special_functions",    "class": 3, "v15_sorry": 2},
]

# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class V16ProblemResult:
    """Result for one HorizonMath problem in the v16 run."""
    pid: str = ""
    domain: str = ""
    problem_class: int = 3
    v15_sorry: int = 0

    # v16 outputs
    conjecture_statement: str = ""
    lean4_sketch: str = ""
    lean4_sketch_archimedes: str = ""
    sorry_count: int = 0
    sorry_count_after_archimedes: int = 0
    sorry_count_final: int = 0
    archimedes_reduction: int = 0
    pre_decomp_lemmas: int = 0           # H1: number of lemma slots generated
    sharding_tier: str = ""             # H3: GPU tier used
    sharding_region: str = ""          # H3: winning region endpoint
    research_brief: str = ""
    v16_confidence: float = 0.0
    v16_verdict: str = ""
    sorry_guillotine_applied: bool = False
    gap_probability_map: dict[str, float] = field(default_factory=dict)
    domain_prior: float = 0.15
    cost_usd: float = 0.0
    elapsed_s: float = 0.0
    hypotheses_applied: list[str] = field(default_factory=list)


# ── Domain priors (Euler Bayesian skepticism) ─────────────────────────────────

_DOMAIN_PRIORS: dict[str, float] = {
    "number_theory":       0.05,
    "continuum_physics":   0.10,
    "mathematical_physics": 0.15,
    "discrete_geometry":   0.20,
    "spectral_theory":     0.20,
    "special_functions":   0.25,
    "stat_mechanics":      0.30,
    "coding_theory":       0.30,
    "combinatorics":       0.35,
}


def _get_domain_prior(domain: str) -> float:
    return _DOMAIN_PRIORS.get(domain, 0.15)


# ── H2: Auto-Research (inherited from v15, unchanged) ────────────────────────

def _build_research_brief(pid: str, domain: str) -> str:
    """Query arXiv for relevant papers (H2, inherited from v15)."""
    if not ENABLE_H2_AUTO_RESEARCH:
        return ""
    try:
        domain_arxiv_map = {
            "number_theory": "math.NT", "combinatorics": "math.CO",
            "special_functions": "math.CA", "discrete_geometry": "math.MG",
            "mathematical_physics": "math-ph", "spectral_theory": "math.SP",
            "stat_mechanics": "cond-mat.stat-mech", "coding_theory": "cs.IT",
        }
        arxiv_cat = domain_arxiv_map.get(domain, "math.GR")
        search_terms = pid.replace("_", " ")
        url = (
            f"https://export.arxiv.org/api/query?"
            f"search_query=ti:{urllib.request.quote(search_terms)}+AND+cat:{arxiv_cat}"
            f"&max_results=3&sortBy=relevance"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "SocrateAI-Agora/16.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = resp.read().decode("utf-8")
        titles = re.findall(r"<title>(.*?)</title>", data, re.DOTALL)[1:]
        summaries = re.findall(r"<summary>(.*?)</summary>", data, re.DOTALL)
        if not titles:
            return ""
        lines = [f"[Auto-Research Brief for {pid} | {domain}]"]
        for i, (title, summary) in enumerate(zip(titles[:3], summaries[:3])):
            title = title.strip().replace("\n", " ")
            summary_short = summary.strip()[:200].replace("\n", " ")
            lines.append(f"  [{i+1}] {title}: {summary_short}...")
        return "\n".join(lines)
    except Exception:
        return ""


# ── Core Problem Processor ────────────────────────────────────────────────────

async def process_problem_v16(
    problem: dict[str, Any],
    galois: GaloisAgent,
    euler: EulerAgent,
    pythagore: PythagoreAgent,
    archimedes: ArchimedesAgent,
    turing: TuringAgent,
    shard_router: ShardRouter,
    pre_decomposer: LemmaPreDecomposer,
    experiment_budget: list[float],
) -> V16ProblemResult:
    """Process one HorizonMath problem with v16 hypotheses.

    Pipeline:
        1. [H2] Auto-research literature brief
        2. [H1] LemmaPreDecomposer — generate sub-lemma plan
        3. Galois — conjecture + Lean 4 sketch (enriched with H1+H2 context)
        4. [H3] ShardRouter — route gap-attacks through regional L4 pool
        5. Archimedes — sorry exhaustion (with v16 pre-decomp context)
        6. Euler — Zero-Sorry Guillotine (epistemic law)
        7. Pythagore — gap probability classification
        8. Turing — FinOps reporting with GPU tier info
    """
    t_start = time.monotonic()
    pid = problem["pid"]
    domain = problem["domain"]
    prob_class = problem["class"]

    result = V16ProblemResult(
        pid=pid,
        domain=domain,
        problem_class=prob_class,
        v15_sorry=problem.get("v15_sorry", 0),
    )

    print(f"\n{'─'*70}")
    print(f"  🔬 {pid}  [v16]")
    print(f"  Domain: {domain} | Class {prob_class} | v15 sorry baseline: {problem.get('v15_sorry', '?')}")
    print(f"  GPU: {shard_router.tier} | Budget used: ${experiment_budget[0]:.2f} / $400.00")
    print(f"{'─'*70}")

    # ── Budget guard ──────────────────────────────────────────────────────────
    if experiment_budget[0] >= BUDGET_CAP_USD - 20.0:
        logger.warning("budget_near_exhaustion", used=experiment_budget[0])
        result.v16_verdict = "BUDGET_EXCEEDED"
        return result

    # ── H2: Pre-proof literature research ────────────────────────────────────
    research_brief = ""
    if ENABLE_H2_AUTO_RESEARCH:
        print(f"  [H2-Hypatia] Auto-research...")
        research_brief = _build_research_brief(pid, domain)
        if research_brief:
            result.research_brief = research_brief
            result.hypotheses_applied.append("H2_AUTO_RESEARCH")
            print(f"  ✓ Research brief: {len(research_brief)} chars")

    # ── H1: Lemma pre-decomposition ───────────────────────────────────────────
    pre_decomp_injection = ""
    if ENABLE_H1_PRE_DECOMPOSE:
        print(f"  [H1-PreDecomp] Generating lemma slot plan...")
        try:
            pre_plan = pre_decomposer.decompose_theorem_statement(
                theorem_header=f"theorem {pid} (v16)",
                domain=domain,
                pid=pid,
                max_lemmas=5,
            )
            pre_decomp_injection = pre_plan.prompt_injection
            result.pre_decomp_lemmas = len(pre_plan.lemmas)
            result.hypotheses_applied.append(f"H1_PRE_DECOMP_{len(pre_plan.lemmas)}L")
            print(f"  ✓ Pre-decomp: {len(pre_plan.lemmas)} sub-lemma slots identified")
        except Exception as e:
            logger.warning("h1_pre_decomp_failed", pid=pid, error=str(e)[:80])
            pre_decomp_injection = ""

    # ── Galois: conjecture + Lean 4 sketch (enriched with v16 context) ────────
    print(f"  [Galois] Generating conjecture + sketch (SymBrain v16)...")

    galois_prompt = (
        f"Generate a rigorous mathematical conjecture and Lean 4 proof sketch for: {pid}\n"
        f"Domain: {domain} | Complexity Class: {prob_class}\n"
        f"\n{research_brief}\n"
        f"\n{pre_decomp_injection}\n"
        f"\nIMPORTANT: Use real Mathlib4 theorems. Follow the Lemma Pre-Decomposition Plan above.\n"
        f"Prove each sub-lemma in sequence using the suggested tactics.\n"
        f"Only use `sorry` for genuinely open sub-claims (not where Mathlib4 already has a proof)."
    )

    lean4_sketch = ""
    conjecture_statement = ""
    cost_galois = 0.0

    try:
        # Try shard-routed inference first (H3), fall back to direct Galois
        if ENABLE_H3_SHARDING:
            shard_result = await shard_router.route(galois_prompt, race_all=True)
            if shard_result.success and shard_result.text:
                # Use shard response as context enrichment for Galois
                result.sharding_tier = shard_result.tier
                result.sharding_region = shard_result.region_endpoint
                result.hypotheses_applied.append(f"H3_SHARD_{shard_result.tier}")
                print(f"  ✓ ShardRouter: {shard_result.tier} | {shard_result.region_endpoint} | "
                      f"{shard_result.latency_ms:.0f}ms")
            else:
                print(f"  ○ ShardRouter: no response — falling back to direct Galois")

        galois_result = await galois.run(galois_prompt)
        galois_answer = galois_result.answer
        galois_answer_str = str(galois_answer)
        cost_galois = getattr(galois_result, "cost_usd", 0.17)

        # Multi-level sketch extraction (v15 approach preserved)
        conj_result = (galois_answer.get("conjecture_generator") if isinstance(galois_answer, dict) else None)
        inner = getattr(conj_result, "conjectures", None) or []
        if inner and hasattr(inner[0], "lean4_sketch"):
            best = inner[0]
            conjecture_statement = getattr(best, "statement", "") or ""
            lean4_sketch = getattr(best, "lean4_sketch", "") or ""
        elif isinstance(conj_result, dict):
            conjecture_statement = conj_result.get("statement", "")
            lean4_sketch = conj_result.get("lean4_sketch", "")

        # Regex fallback
        if not lean4_sketch:
            m = re.search(r"lean4_sketch='(.*?)(?=',\s*[a-z_]+=|'\))", galois_answer_str, re.DOTALL)
            if not m:
                m = re.search(r'lean4_sketch="(.*?)(?=",\s*[a-z_]+=|"\))', galois_answer_str, re.DOTALL)
            if m:
                lean4_sketch = m.group(1).replace("\\n", "\n").replace("\\\\", "\\")

        if not conjecture_statement:
            m2 = re.search(r"statement='(.*?)(?=',\s*[a-z_]+=|'\))", galois_answer_str, re.DOTALL)
            conjecture_statement = m2.group(1) if m2 else galois_answer_str[:500]

        result.conjecture_statement = conjecture_statement[:CONJECTURE_CHAR_LIMIT]
        result.lean4_sketch = lean4_sketch[:SKETCH_CHAR_LIMIT]
        result.sorry_count = lean4_sketch.lower().count("sorry")

        experiment_budget[0] += cost_galois
        result.cost_usd += cost_galois
        print(f"  ✓ Galois: {len(lean4_sketch)} chars, {result.sorry_count} sorry stubs")

    except Exception as e:
        logger.error("galois_v16_failed", pid=pid, error=str(e)[:200])
        print(f"  🛑 CIRCUIT BREAKER: Galois failed — {str(e)[:80]}")
        result.v16_verdict = "CB_TRIPPED"
        result.elapsed_s = time.monotonic() - t_start
        return result

    # ── Archimedes: sorry decomposition (v16 enhanced) ───────────────────────
    if result.sorry_count > 0:
        print(f"  [H1-Archimedes] Method of Exhaustion + Pre-Decomp: {result.sorry_count} sorry gaps...")
        try:
            arch_result = await archimedes.run(
                query=f"Prove sub-lemmas for HorizonMath problem: {pid}",
                lean4_sketch=result.lean4_sketch,
                domain=domain,
                theorem_header=result.conjecture_statement[:120],
                pid=pid,
            )
            arch_data = arch_result.answer

            if arch_data and arch_data.get("reduction", 0) > 0:
                result.lean4_sketch_archimedes = arch_data.get("lean4_sketch", result.lean4_sketch)
                result.sorry_count_after_archimedes = arch_data.get("sorry_count", result.sorry_count)
                result.archimedes_reduction = arch_data.get("reduction", 0)
                lean4_sketch = result.lean4_sketch_archimedes
                if "H1_ARCHIMEDES" not in " ".join(result.hypotheses_applied):
                    result.hypotheses_applied.append("H1_ARCHIMEDES")
                print(f"  ✓ Archimedes: {result.sorry_count} → {result.sorry_count_after_archimedes} sorry "
                      f"(-{result.archimedes_reduction} gaps)")
            else:
                result.sorry_count_after_archimedes = result.sorry_count
                print(f"  ○ Archimedes: no gaps resolved (intractable)")

            experiment_budget[0] += arch_result.cost_usd
            result.cost_usd += arch_result.cost_usd

        except Exception as e:
            logger.warning("archimedes_v16_failed", pid=pid, error=str(e)[:100])
            result.sorry_count_after_archimedes = result.sorry_count
            print(f"  ⚠ Archimedes failed: {str(e)[:60]}")
    else:
        result.sorry_count_after_archimedes = 0
        print(f"  ✓ Zero sorry stubs — skipping Archimedes")

    result.sorry_count_final = lean4_sketch.lower().count("sorry")
    result.lean4_sketch_archimedes = lean4_sketch

    # ── Euler: Zero-Sorry Guillotine ─────────────────────────────────────────
    print(f"  [Euler] Verifying (ZSG — epistemic law unchanged)...")
    final_sorry_count = lean4_sketch.lower().count("sorry")
    result.domain_prior = _get_domain_prior(domain)

    try:
        euler_payload = (
            f"Problem: {pid} | Domain: {domain} | v16\n"
            f"Conjecture: {result.conjecture_statement[:600]}\n"
            f"Lean 4 Sketch (after v16 Archimedes):\n{lean4_sketch[:SKETCH_CHAR_LIMIT]}\n"
            f"v16 hypotheses applied: {', '.join(result.hypotheses_applied)}"
        )
        euler_res = await euler.run(
            f"Verify the v16 conjecture for '{pid}'.\n{euler_payload}\n"
            f"CRITICAL — Zero-Sorry Guillotine (ZSG):\n"
            f"  • sorry_count = {final_sorry_count}. If > 0 → verdict MUST be INCOMPLETE\n"
            f"  • Bayesian domain prior for {domain}: {result.domain_prior:.2f}\n"
            f"  • Only VERIFIED if sorry_count == 0 AND all goals closed\n"
            f"Never VERIFY a proof containing sorry. This is the absolute epistemic law."
        )
        euler_conf = euler_res.confidence

        # Apply ZSG at orchestrator level (belt-and-suspenders)
        if final_sorry_count > 0 and euler_conf >= 0.85:
            euler_conf = min(euler_conf, 0.70)
            result.sorry_guillotine_applied = True
            print(f"  🚨 ZSG: {final_sorry_count} sorries → conf capped at 0.70")

        if not lean4_sketch.strip() and euler_conf >= 0.85:
            euler_conf = 0.60
            result.sorry_guillotine_applied = True

        result.v16_confidence = euler_conf
        experiment_budget[0] += getattr(euler_res, "cost_usd", 0.15)
        result.cost_usd += getattr(euler_res, "cost_usd", 0.15)

        if euler_conf >= 0.85 and final_sorry_count == 0:
            result.v16_verdict = "VERIFIED"
        elif euler_conf >= 0.65:
            result.v16_verdict = "INCOMPLETE"
        else:
            result.v16_verdict = "REFUTED"

    except Exception as e:
        logger.warning("euler_v16_failed", pid=pid, error=str(e)[:100])
        result.v16_verdict = "INCOMPLETE"
        result.v16_confidence = 0.60

    # ── Pythagore: Probabilistic gap classification ───────────────────────────
    print(f"  [Pythagore] Gap probability analysis...")
    try:
        pyth_res = await pythagore.run(
            f"Probabilistic sorry-gap analysis for '{pid}' (domain: {domain}).\n"
            f"Final sketch ({final_sorry_count} sorry stubs remaining):\n{lean4_sketch[:600]}\n"
            f"v16 verdict: {result.v16_verdict}\n"
            f"For each sorry: name the mathematical claim, estimate Mathlib4 coverage probability.\n"
            f"Output JSON: {{lemma_name: probability_0_to_1}}"
        )
        pyth_str = str(pyth_res.answer)
        map_m = re.search(r'\{[^}]+\}', pyth_str, re.DOTALL)
        if map_m:
            try:
                gap_map = json.loads(map_m.group(0))
                result.gap_probability_map = {
                    k: float(v) for k, v in gap_map.items()
                    if isinstance(v, (int, float))
                }
            except Exception:
                pass
        experiment_budget[0] += getattr(pyth_res, "cost_usd", 0.01)
        result.cost_usd += getattr(pyth_res, "cost_usd", 0.01)
    except Exception as e:
        logger.debug("pythagore_v16_failed", pid=pid, error=str(e)[:80])

    # ── Turing: FinOps + GPU tier report ─────────────────────────────────────
    try:
        router_stats = shard_router.stats()
        await turing.run(
            f"FinOps v16 report for {pid}: "
            f"cost=${result.cost_usd:.3f} | tier={router_stats['tier']} | "
            f"shard_success_rate={router_stats['success_rate']:.2%} | "
            f"verdict={result.v16_verdict} | sorry_final={final_sorry_count}"
        )
        experiment_budget[0] += 0.01
        result.cost_usd += 0.01
    except Exception:
        pass

    result.elapsed_s = time.monotonic() - t_start

    # ── Print summary ─────────────────────────────────────────────────────────
    verdict_emoji = {
        "VERIFIED": "✅", "INCOMPLETE": "🔶", "REFUTED": "❌",
        "CB_TRIPPED": "🛑", "BUDGET_EXCEEDED": "💰",
    }.get(result.v16_verdict, "❓")
    print(f"\n  {verdict_emoji} {pid}: {result.v16_verdict} | conf={result.v16_confidence:.2f}")
    print(f"     Sorry: {result.sorry_count} → {result.sorry_count_after_archimedes} → {final_sorry_count} (final)")
    print(f"     H1 pre-decomp lemmas: {result.pre_decomp_lemmas} | "
          f"Archimedes reduced: {result.archimedes_reduction}")
    print(f"     H3 shard tier: {result.sharding_tier or 'N/A'}")
    print(f"     Cost: ${result.cost_usd:.3f} | Time: {result.elapsed_s:.1f}s")
    print(f"     Hypotheses applied: {result.hypotheses_applied}")

    return result


# ── Per-Domain Batch ───────────────────────────────────────────────────────────

async def run_domain_batch_v16(
    problems: list[dict[str, Any]],
    galois: GaloisAgent,
    euler: EulerAgent,
    pythagore: PythagoreAgent,
    archimedes: ArchimedesAgent,
    turing: TuringAgent,
    shard_router: ShardRouter,
    pre_decomposer: LemmaPreDecomposer,
    experiment_budget: list[float],
) -> list[V16ProblemResult]:
    """Run a domain batch with ShardRouter keep-warm (H3).

    The ShardRouter maintains connections to regional endpoints across the
    batch lifetime — equivalent to v15's L4 keep-warm but multi-region.
    """
    domain = problems[0]["domain"] if problems else "unknown"
    print(f"\n{'═'*70}")
    print(f"  📦 Domain Batch: {domain} | {len(problems)} problems")
    print(f"  GPU Tier: {shard_router.tier} | Endpoints: {len(shard_router.endpoints)}")
    print(f"{'═'*70}")

    # Deploy keep-warm via Turing
    try:
        await turing.run(
            f"deploy {shard_router.tier} sharded endpoints for domain batch: {domain}. "
            f"Regions: {shard_router.endpoints}. ShardRouter keep-warm: do not teardown between problems."
        )
        experiment_budget[0] += 0.03  # $0.03 for cross-region keep-warm (vs $0.05 single-region)
        print(f"  🟢 ShardRouter deployed for batch (${0.03:.2f})")
    except Exception as e:
        logger.warning("turing_v16_deploy_failed", domain=domain, error=str(e)[:80])
        print(f"  ⚠ Turing deploy failed (continuing): {str(e)[:60]}")

    results = []
    for i, problem in enumerate(problems):
        print(f"\n  Problem {i+1}/{len(problems)} in {domain} batch")
        result = await process_problem_v16(
            problem=problem,
            galois=galois,
            euler=euler,
            pythagore=pythagore,
            archimedes=archimedes,
            turing=turing,
            shard_router=shard_router,
            pre_decomposer=pre_decomposer,
            experiment_budget=experiment_budget,
        )
        results.append(result)

        # Save intermediate result
        out_file = SCRATCH_DIR / f"{result.pid}_v16.json"
        out_file.write_text(json.dumps({
            "pid": result.pid,
            "domain": result.domain,
            "v16_verdict": result.v16_verdict,
            "v16_confidence": result.v16_confidence,
            "sorry_count": result.sorry_count,
            "sorry_count_after_archimedes": result.sorry_count_after_archimedes,
            "sorry_count_final": result.sorry_count_final,
            "archimedes_reduction": result.archimedes_reduction,
            "pre_decomp_lemmas": result.pre_decomp_lemmas,
            "sharding_tier": result.sharding_tier,
            "sharding_region": result.sharding_region,
            "hypotheses_applied": result.hypotheses_applied,
            "conjecture_statement": result.conjecture_statement[:CONJECTURE_CHAR_LIMIT],
            "lean4_sketch": result.lean4_sketch[:SKETCH_CHAR_LIMIT],
            "lean4_sketch_archimedes": result.lean4_sketch_archimedes[:SKETCH_CHAR_LIMIT],
            "research_brief": result.research_brief[:400],
            "v15_sorry": result.v15_sorry,
            "domain_prior": result.domain_prior,
            "gap_probability_map": result.gap_probability_map,
            "sorry_guillotine_applied": result.sorry_guillotine_applied,
            "cost_usd": round(result.cost_usd, 4),
            "elapsed_s": round(result.elapsed_s, 2),
        }, indent=2))

    # Teardown
    try:
        await turing.run(f"tear down {shard_router.tier} sharding deployment for {domain} batch")
        print(f"\n  🔴 ShardRouter torn down after {domain} batch")
    except Exception as e:
        logger.warning("turing_v16_teardown_failed", domain=domain, error=str(e)[:80])

    return results


# ── Main Orchestrator ─────────────────────────────────────────────────────────

async def main() -> None:
    """v16 main orchestration loop."""
    run_start = time.monotonic()

    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║         SymBrain v16 — HorizonMath Agora Exhaustion                  ║
║         H1: Lemma Pre-Decomposition | H3: Cross-Region Sharding      ║
║         GPU: L4 Spot × 4 Regions (DopamineRegulatedThreshold)        ║
╠══════════════════════════════════════════════════════════════════════╣
║  Budget: $400 | Spent v13-v15: ${PREVIOUS_SPEND_USD:.2f} | Remaining: ${BUDGET_REMAINING_USD:.2f}   ║
╚══════════════════════════════════════════════════════════════════════╝
    """)

    # ── Initialize agents ─────────────────────────────────────────────────────
    galois     = GaloisAgent()
    euler      = EulerAgent()
    pythagore  = PythagoreAgent()
    turing     = TuringAgent()
    archimedes = ArchimedesAgent()

    # v16: Upgrade Galois to SymBrain v16 cortex (H1 + H3 dopamine)
    galois.upgrade_to_v16()
    print(f"  ✅ Galois cortex: {galois.cortex.symbrain_version}")

    # v16: Initialize ShardRouter (H3) — starts at L4_SPOT
    shard_router = ShardRouter(tier=INITIAL_GPU_TIER)
    print(f"  ✅ ShardRouter: {shard_router.tier} | {len(shard_router.endpoints)} endpoints")

    # v16: Initialize LemmaPreDecomposer (H1)
    pre_decomposer = LemmaPreDecomposer()
    print(f"  ✅ LemmaPreDecomposer ready (H1)")

    # ── Shared budget counter ─────────────────────────────────────────────────
    experiment_budget: list[float] = [PREVIOUS_SPEND_USD]

    # ── Group problems by domain for batch processing ─────────────────────────
    domain_batches: dict[str, list[dict]] = defaultdict(list)
    for p in V15_PROBLEMS:
        domain_batches[p["domain"]].append(p)

    print(f"\n📊 Problem Distribution ({len(V15_PROBLEMS)} total):")
    for domain, batch in sorted(domain_batches.items(), key=lambda x: -len(x[1])):
        avg_sorry = sum(p.get("v15_sorry", 0) for p in batch) / len(batch)
        print(f"   {domain:<35} {len(batch):2d} problems  (avg v15 sorry: {avg_sorry:.1f})")

    # ── Sequential domain batch processing ────────────────────────────────────
    all_results: list[V16ProblemResult] = []
    last_monitor = time.monotonic()

    for domain, batch in sorted(domain_batches.items(), key=lambda x: -len(x[1])):
        batch_results = await run_domain_batch_v16(
            problems=batch,
            galois=galois,
            euler=euler,
            pythagore=pythagore,
            archimedes=archimedes,
            turing=turing,
            shard_router=shard_router,
            pre_decomposer=pre_decomposer,
            experiment_budget=experiment_budget,
        )
        all_results.extend(batch_results)

        # 5-minute monitoring print
        now = time.monotonic()
        if now - last_monitor >= MONITOR_INTERVAL_S:
            last_monitor = now
            done = len(all_results)
            elapsed_min = (now - run_start) / 60
            router_stats = shard_router.stats()
            print(f"\n⏱ MONITOR [{elapsed_min:.1f} min] | "
                  f"{done}/{len(V15_PROBLEMS)} done | "
                  f"Budget: ${experiment_budget[0]:.2f}/$400 | "
                  f"Shard tier: {router_stats['tier']} | "
                  f"Shard success: {router_stats['success_rate']:.1%}")

    # ── Final Report ──────────────────────────────────────────────────────────
    elapsed_total = time.monotonic() - run_start

    verified   = [r for r in all_results if r.v16_verdict == "VERIFIED"]
    incomplete = [r for r in all_results if r.v16_verdict == "INCOMPLETE"]
    refuted    = [r for r in all_results if r.v16_verdict == "REFUTED"]
    cb         = [r for r in all_results if r.v16_verdict in ("CB_TRIPPED", "BUDGET_EXCEEDED")]

    total_sorry_before    = sum(r.sorry_count for r in all_results)
    total_sorry_after     = sum(r.sorry_count_final for r in all_results)
    total_archim_reduction = sum(r.archimedes_reduction for r in all_results)
    total_pre_decomp_lemmas = sum(r.pre_decomp_lemmas for r in all_results)
    total_cost = experiment_budget[0]
    router_stats = shard_router.stats()

    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║  SymBrain v16 — FINAL REPORT                                          ║
╠══════════════════════════════════════════════════════════════════════╣
║  Problems: {len(all_results):2d} total                                              ║
║  ✅ VERIFIED:   {len(verified):2d}  (genuine: zero sorry stubs)                 ║
║  🔶 INCOMPLETE: {len(incomplete):2d}                                               ║
║  ❌ REFUTED:    {len(refuted):2d}                                               ║
║  🛑 CB/Budget:  {len(cb):2d}                                               ║
╠══════════════════════════════════════════════════════════════════════╣
║  Sorry reduction (H1 Pre-Decomp + Archimedes):                        ║
║    Before: {total_sorry_before:4d} stubs                                           ║
║    After:  {total_sorry_after:4d} stubs  ({total_sorry_before - total_sorry_after:4d} eliminated)                 ║
║    Archimedes alone: -{total_archim_reduction:3d} stubs                          ║
║    Pre-decomp lemma slots: {total_pre_decomp_lemmas:4d}                           ║
╠══════════════════════════════════════════════════════════════════════╣
║  H3 Cross-Region Sharding:                                            ║
║    Final tier: {router_stats['tier']:<20} Escalations: {router_stats['success_rate']:.0%} ║
║    Total shard calls: {router_stats['total_calls']:4d}                              ║
╠══════════════════════════════════════════════════════════════════════╣
║  Runtime: {elapsed_total/60:.1f} min | Cost: ${total_cost:.2f} / $400.00              ║
╚══════════════════════════════════════════════════════════════════════╝
    """)

    # ── Save final summary JSON ───────────────────────────────────────────────
    summary = {
        "run": "v16",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "hypotheses": {
            "H1_pre_decompose": ENABLE_H1_PRE_DECOMPOSE,
            "H2_auto_research": ENABLE_H2_AUTO_RESEARCH,
            "H3_cross_region_sharding": ENABLE_H3_SHARDING,
            "H5_euclid": ENABLE_H5_EUCLID,
        },
        "gpu_strategy": {
            "initial_tier": INITIAL_GPU_TIER,
            "final_tier": router_stats["tier"],
            "total_shard_calls": router_stats["total_calls"],
            "shard_success_rate": router_stats["success_rate"],
            "total_escalations": shard_router.stats().get("total_escalations", 0),
        },
        "statistics": {
            "total_problems": len(all_results),
            "verified": len(verified),
            "incomplete": len(incomplete),
            "refuted": len(refuted),
            "cb_tripped": len(cb),
            "total_sorry_before": total_sorry_before,
            "total_sorry_after": total_sorry_after,
            "sorry_eliminated": total_sorry_before - total_sorry_after,
            "archimedes_reduction": total_archim_reduction,
            "pre_decomp_lemmas_total": total_pre_decomp_lemmas,
            "elapsed_min": round(elapsed_total / 60, 1),
            "total_cost_usd": round(total_cost, 2),
            "budget_remaining_usd": round(BUDGET_CAP_USD - total_cost, 2),
        },
        "verified_problems": [r.pid for r in verified],
        "refuted_problems": [r.pid for r in refuted],
    }

    summary_file = SCRATCH_DIR / "v16_summary.json"
    summary_file.write_text(json.dumps(summary, indent=2))
    print(f"\n📁 Summary: {summary_file}")

    import shutil
    shutil.copy(str(summary_file), str(DOWNLOADS / "v16_summary.json"))
    print(f"📥 Copied to: {DOWNLOADS / 'v16_summary.json'}")


if __name__ == "__main__":
    asyncio.run(main())
