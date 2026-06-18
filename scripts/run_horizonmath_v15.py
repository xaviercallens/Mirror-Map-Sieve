#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""
SymBrain v15 HorizonMath Orchestrator — Method of Exhaustion
============================================================

Implements the 5-hypothesis v15 improvement plan:

H1 — ARCHIMEDES AGENT (Lemma Decomposition)
    New agent that decomposes sorry stubs into targeted sub-lemmas, each
    attacked by a focused Galois call. Named after Archimedes' Method of
    Exhaustion (progressive subdivision until the gap is closed or classified
    as genuinely intractable).

H2 — AUTO-RESEARCH (Pre-Proof Literature Mining)
    Before Galois generates a conjecture, Hypatia queries arXiv and the
    Mathlib4 declaration index for relevant theorems and proof strategies.
    The research brief is injected into Galois's prompt as context.

H3 — SISYPHUS PROTOCOL (Iterative Sorry-Refinement Loop)
    Instead of running Galois→Euler once, the pipeline iterates up to 3 rounds:
    each round feeds Euler's sorry gap descriptions back to Galois for targeted
    refinement. Temperature escalates each round (0.70→0.85→0.95).

H4 — SOCRATIC DEBATE (Multi-LLM Adversarial Review)
    Gemini and Mistral generate competing proof sketches. Each model sees the
    other's sorry gaps and attempts to fill them. Euler selects the sketch with
    fewer remaining sorry stubs.

H5 — EUCLID INDEX (Mathlib4 Tactic Recommender)
    For each sorry gap, a lightweight Mathlib4 semantic search finds the most
    relevant existing lemmas and injects their names into the retry prompt.

GPU STRATEGY (L4-only, avoid H100/A100 quota issues):
    - L4 Spot instances in 3 regions (failover)
    - Keep-warm: process full domain batch before teardown ($0.01/problem vs $0.10)
    - No H100/A100 — quota unreliable, L4 sufficient for inference

Budget: $400 cap | v13+v14 spent: $30.69 | Remaining: ~$369

Architecture:
    Socrates (orchestrator)
      → Hypatia  (pre-proof literature research — H2)
      → Galois   (conjecture + Lean 4 sketch, SymBrain v11)
      → Archimedes (sorry decomposition + gap attack — H1)
      → Euler    (Zero-Sorry Guillotine + Bayesian priors)
      → [Sisyphus loop: rounds 2-3 if sorry_count > 0] (H3)
      → Pythagore (probabilistic gap classification)
      → Heraclite (monograph synthesis)
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
from agents.socrates.agent import SocratesAgent
from agents.archimedes.agent import ArchimedesAgent   # H1: NEW in v15

from agents.base import AgentConfig, AgentRole

logger = structlog.get_logger(__name__)

# ── Budget & Paths ────────────────────────────────────────────────────────────

BUDGET_CAP_USD         = 400.0
PREVIOUS_SPEND_USD     = 30.69       # v13 + v14 combined
BUDGET_REMAINING_USD   = BUDGET_CAP_USD - PREVIOUS_SPEND_USD

OUTPUT_DIR   = Path(__file__).parent.parent / "achievement_output"
SCRATCH_DIR  = OUTPUT_DIR / "v15_results"
DOWNLOADS    = Path.home() / "Downloads"
DOCS_DIR     = Path(__file__).parent.parent / "docs"

SCRATCH_DIR.mkdir(parents=True, exist_ok=True)

# ── GPU Strategy: L4 ONLY (avoid H100/A100 quota limits) ────────────────────
# H100/A100 quotas are unreliable; L4 is always available in multiple regions.
# Keep-warm: deploy ONCE per domain batch, not per problem.
GPU_TYPE     = "L4"   # Never H100/A100 in v15
GPU_REGIONS  = [
    "us-central1",   # Primary
    "us-east4",      # Secondary (different quota pool from us-east1)
    "europe-west4",  # Tertiary — Netherlands
]
GPU_SPOT     = True   # Spot L4 = 60-70% cheaper, 2-min preemption is safe for ~2min/problem

# ── v15 Hypothesis Flags ─────────────────────────────────────────────────────
# Set False to disable a hypothesis for ablation testing
ENABLE_H1_ARCHIMEDES    = True    # Lemma decomposition
ENABLE_H2_AUTO_RESEARCH = True    # Pre-proof literature mining
ENABLE_H3_SISYPHUS      = True    # Iterative refinement (max 3 rounds)
ENABLE_H4_DEBATE        = False   # Multi-LLM debate (disabled by default: expensive)
ENABLE_H5_EUCLID        = True    # Mathlib4 tactic recommender

# H3 Sisyphus: max rounds and temperature escalation
SISYPHUS_MAX_ROUNDS    = 3
SISYPHUS_TEMPERATURES  = [0.70, 0.85, 0.95]

# Sketch truncation: v14 used 800 chars — v15 uses 2000 (critical fix!)
SKETCH_CHAR_LIMIT      = 2000
CONJECTURE_CHAR_LIMIT  = 800

# ── 5-Second monitoring interval (as requested) ──────────────────────────────
MONITOR_INTERVAL_S = 300  # 5-minute status prints

# ── Problem List (all 50 HorizonMath — re-run those not VERIFIED) ────────────
V14_PROBLEMS: list[dict[str, Any]] = [
    {"pid": "knot_volume_6_3",                  "domain": "discrete_geometry",    "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 7},
    {"pid": "euler_mascheroni_closed_form",     "domain": "number_theory",        "class": 3, "v14_status": "REFUTED",    "v14_sorry": 0},
    {"pid": "feigenbaum_alpha",                 "domain": "continuum_physics",    "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 3},
    {"pid": "feigenbaum_delta",                 "domain": "continuum_physics",    "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 2},
    {"pid": "saw_simple_cubic",                 "domain": "stat_mechanics",       "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 3},
    {"pid": "saw_square_lattice",               "domain": "stat_mechanics",       "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 3},
    {"pid": "saw_triangular_lattice",           "domain": "stat_mechanics",       "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 2},
    {"pid": "w5_watson_integral",               "domain": "stat_mechanics",       "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 3},
    {"pid": "w6_watson_integral",               "domain": "stat_mechanics",       "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 2},
    {"pid": "bessel_moment_c5_0",               "domain": "special_functions",    "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 3},
    {"pid": "bessel_moment_c5_1",               "domain": "special_functions",    "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 2},
    {"pid": "elliptic_k_moment_4",              "domain": "special_functions",    "class": 4, "v14_status": "REFUTED",    "v14_sorry": 0},
    {"pid": "autocorr_signed_upper",            "domain": "combinatorics",        "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 3},
    {"pid": "calabi_yau_c5",                    "domain": "special_functions",    "class": 4, "v14_status": "INCOMPLETE", "v14_sorry": 5},
    {"pid": "knot_volume_7_2",                  "domain": "discrete_geometry",    "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 7},
    {"pid": "anderson_lyapunov_exponent",       "domain": "mathematical_physics", "class": 4, "v14_status": "INCOMPLETE", "v14_sorry": 4},
    {"pid": "quartic_oscillator_lambda",        "domain": "spectral_theory",      "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 3},
    {"pid": "spheroidal_eigenvalue_lambda_m0",  "domain": "spectral_theory",      "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 3},
    {"pid": "nested_radical_kasner",            "domain": "number_theory",        "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 5},
    {"pid": "mrb_constant",                     "domain": "number_theory",        "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 3},
    {"pid": "torsional_rigidity_square",        "domain": "special_functions",    "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 3},
    {"pid": "mahler_1_x_y_z_w",                "domain": "number_theory",        "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 3},
    {"pid": "schur_6",                          "domain": "combinatorics",        "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 4},
    {"pid": "diff_basis_optimal_10000",         "domain": "combinatorics",        "class": 3, "v14_status": "REFUTED",    "v14_sorry": 1},
    {"pid": "general_diff_basis_algo",          "domain": "combinatorics",        "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 3},
    {"pid": "merit_factor_6_5",                 "domain": "coding_theory",        "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 3},
    {"pid": "parametric_spherical_codes",       "domain": "coding_theory",        "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 3},
    {"pid": "bklc_68_15",                       "domain": "coding_theory",        "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 3},
    {"pid": "lattice_packing_dim10",            "domain": "discrete_geometry",    "class": 4, "v14_status": "INCOMPLETE", "v14_sorry": 4},
    {"pid": "periodic_packing_dim10",           "domain": "discrete_geometry",    "class": 4, "v14_status": "INCOMPLETE", "v14_sorry": 4},
    {"pid": "bessel_moment_c6_0",               "domain": "special_functions",    "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 6},
    {"pid": "feynman_3loop_sunrise",            "domain": "mathematical_physics", "class": 4, "v14_status": "REFUTED",    "v14_sorry": 8},
    {"pid": "townes_soliton",                   "domain": "mathematical_physics", "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 3},
    {"pid": "mahler_elliptic_product",          "domain": "number_theory",        "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 3},
    {"pid": "closed_form_ramanujan_soldner",    "domain": "number_theory",        "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 2},
    {"pid": "elliptic_curve_rank_30",           "domain": "number_theory",        "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 3},
    {"pid": "elliptic_curve_rank_torsion_z7z",  "domain": "number_theory",        "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 3},
    {"pid": "mzv_decomposition_c5",             "domain": "number_theory",        "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 6},
    {"pid": "tracy_widom_f2_mean",              "domain": "mathematical_physics", "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 3},
    {"pid": "tracy_widom_f2_variance",          "domain": "mathematical_physics", "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 3},
    {"pid": "tracy_widom_f1_mean",              "domain": "mathematical_physics", "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 3},
    {"pid": "crossing_number_kn",               "domain": "combinatorics",        "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 2},
    {"pid": "kcore_threshold_c3",               "domain": "combinatorics",        "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 4},
    {"pid": "covering_C13_k7_t4",               "domain": "combinatorics",        "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 7},
    {"pid": "cwcode_29_8_5",                    "domain": "coding_theory",        "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 10},
    {"pid": "inverse_galois_m23",               "domain": "number_theory",        "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 3},
    {"pid": "inverse_galois_suzuki",            "domain": "number_theory",        "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 3},
    {"pid": "hensley_hausdorff_dim",            "domain": "number_theory",        "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 2},
    {"pid": "spherical_mode_quality_factor_te_tm", "domain": "spectral_theory",   "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 6},
    {"pid": "bernstein_constant",               "domain": "special_functions",    "class": 3, "v14_status": "INCOMPLETE", "v14_sorry": 3},
]

# ── Result Dataclass ─────────────────────────────────────────────────────────

@dataclass
class V15ProblemResult:
    """Result for one HorizonMath problem in the v15 run."""
    pid: str = ""
    domain: str = ""
    problem_class: int = 3

    # v14 baseline
    v14_status: str = ""
    v14_sorry: int = 0

    # v15 outputs
    conjecture_statement: str = ""
    lean4_sketch: str = ""                   # Full sketch (2000-char limit)
    lean4_sketch_archimedes: str = ""        # After Archimedes refinement (H1)
    sorry_count: int = 0                     # Original sorry count
    sorry_count_after_archimedes: int = 0    # After H1
    sorry_count_final: int = 0              # After all hypotheses
    archimedes_reduction: int = 0            # How many sorrys H1 eliminated
    sisyphus_rounds: int = 0                 # H3: how many refinement rounds ran
    research_brief: str = ""                 # H2: literature mining result
    v15_confidence: float = 0.0
    v15_verdict: str = ""                   # VERIFIED | INCOMPLETE | REFUTED | CB_TRIPPED
    sorry_guillotine_applied: bool = False
    gap_probability_map: dict[str, float] = field(default_factory=dict)
    domain_prior: float = 0.15
    cost_usd: float = 0.0
    elapsed_s: float = 0.0
    hypotheses_applied: list[str] = field(default_factory=list)


# ── Domain confidence priors (from Euler's skeptical_auditor.py) ──────────────

_DOMAIN_PRIORS: dict[str, float] = {
    "number_theory":      0.05,
    "continuum_physics":  0.10,
    "mathematical_physics": 0.15,
    "discrete_geometry":  0.20,
    "spectral_theory":    0.20,
    "special_functions":  0.25,
    "stat_mechanics":     0.30,
    "coding_theory":      0.30,
    "combinatorics":      0.35,
}


def _get_domain_prior(domain: str) -> float:
    """Return Euler's Bayesian confidence prior for a domain."""
    return _DOMAIN_PRIORS.get(domain, 0.15)


# ── H2: Auto-Research Literature Mining ──────────────────────────────────────

def _build_research_brief(pid: str, domain: str, problem_text: str) -> str:
    """Query arXiv for relevant papers and return a compact research brief.

    This is H2 (Hypatia Auto-Research). The brief is injected into Galois's prompt
    to give it knowledge of relevant existing results before generating the conjecture.

    Returns empty string on failure (fails silently — research is optional).
    """
    if not ENABLE_H2_AUTO_RESEARCH:
        return ""

    try:
        # Extract key mathematical terms from problem ID and domain
        # Use the domain to build arXiv search terms
        domain_arxiv_map = {
            "number_theory":      "math.NT",
            "combinatorics":      "math.CO",
            "special_functions":  "math.CA",
            "discrete_geometry":  "math.MG",
            "mathematical_physics": "math-ph",
            "spectral_theory":    "math.SP",
            "stat_mechanics":     "cond-mat.stat-mech",
            "coding_theory":      "cs.IT",
        }
        arxiv_cat = domain_arxiv_map.get(domain, "math.GR")

        # Build search query from problem ID (convert snake_case to readable)
        search_terms = pid.replace("_", " ").replace("c5", "").replace("c6", "")

        # arXiv API query
        url = (
            f"https://export.arxiv.org/api/query?"
            f"search_query=ti:{urllib.request.quote(search_terms)}+AND+cat:{arxiv_cat}"
            f"&max_results=3&sortBy=relevance"
        )

        req = urllib.request.Request(url, headers={"User-Agent": "SocrateAI-Agora/15.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = resp.read().decode("utf-8")

        # Extract titles and summaries from Atom XML response
        titles = re.findall(r"<title>(.*?)</title>", data, re.DOTALL)[1:]  # Skip feed title
        summaries = re.findall(r"<summary>(.*?)</summary>", data, re.DOTALL)

        if not titles:
            return ""

        brief_lines = [f"[Auto-Research Brief for {pid} | {domain}]"]
        for i, (title, summary) in enumerate(zip(titles[:3], summaries[:3])):
            title = title.strip().replace("\n", " ")
            summary_short = summary.strip()[:200].replace("\n", " ")
            brief_lines.append(f"  [{i+1}] {title}: {summary_short}...")

        brief = "\n".join(brief_lines)
        logger.info("h2_research_brief_built", pid=pid, papers_found=len(titles))
        return brief

    except Exception as e:
        logger.debug("h2_research_brief_failed", pid=pid, error=str(e)[:80])
        return ""  # Fail silently


# ── H5: Mathlib4 Tactic Recommender ──────────────────────────────────────────

# A compact static index of Mathlib4 lemma names relevant to common gap types.
# In v16 this will be replaced by a full vector-indexed Mathlib4 search.
# For v15, this is a curated lookup table covering the most common sorry patterns.
_MATHLIB4_TACTIC_INDEX: dict[str, list[str]] = {
    "convergence":  [
        "Filter.Tendsto.comp", "tendsto_const_nhds", "Real.tendsto_atTop_atTop",
        "Metric.tendsto_iff_dist_tendsto_zero", "summable_of_summable_norm",
    ],
    "inequality":   [
        "Real.add_pow_le_pow_mul_pow_of_sq_le_sq", "abs_sub_lt_iff", "Real.rpow_le_rpow",
        "div_le_iff (by positivity)", "Finset.sum_le_sum",
    ],
    "existence":    [
        "⟨_, rfl⟩", "Finset.mem_image.mpr", "Set.mem_range.mpr", "Classical.choice",
        "FiniteDimensional.exists_smul_eq_zero",
    ],
    "algebraic":    [
        "ring", "field_simp; ring", "norm_cast; ring", "Polynomial.ext (fun n => _)",
        "GroupHom.ext (fun x => _)",
    ],
    "analytic":     [
        "Complex.integral_eq_nhds_lim", "MeasureTheory.integral_add (by measurability)",
        "Real.HasDerivAt.integral_comp_sub_right", "Complex.differentiableAt_id.congr_deriv",
    ],
    "special_functions": [
        "Real.Gamma_pos_of_pos", "Complex.Gamma_ne_zero", "Real.log_abs",
        "Real.besseli_zero_pos", "Polynomial.aeval_eq_sum_range",
    ],
    "number_theory": [
        "Nat.Coprime.pow_dvd_of_pow_dvd", "ZMod.val_natCast", "Int.emod_emod_of_dvd",
        "Nat.Prime.eq_one_or_self_of_dvd", "ArithmeticFunction.IsMultiplicative.iff_ne_zero",
    ],
    "decidable": [
        "decide", "norm_num", "omega", "Nat.decEq", "Finset.decidableMem",
    ],
    "definition": [
        "exact ⟨⟩", "refine ⟨?_, ?_⟩", "constructor; · intro; exact",
        "⟨fun h => ?_, fun h => ?_⟩",
    ],
}


def _get_mathlib4_hints(gap_type: str, domain: str) -> str:
    """Return a formatted hint string with relevant Mathlib4 lemma names.

    This is H5 (Euclid Index). Injected into Galois's retry prompt.
    """
    if not ENABLE_H5_EUCLID:
        return ""

    hints = []
    # Match gap type first
    lemmas = _MATHLIB4_TACTIC_INDEX.get(gap_type, [])
    # Also add domain-specific hints
    domain_key = domain.replace("_functions", "").replace("stat_mechanics", "convergence")
    domain_lemmas = _MATHLIB4_TACTIC_INDEX.get(domain_key, [])
    all_hints = (lemmas + domain_lemmas)[:6]

    if all_hints:
        return f"\nMathlib4 hints (H5-Euclid): {', '.join(all_hints)}"
    return ""


# ── Core Problem Processor ────────────────────────────────────────────────────

async def process_problem_v15(
    problem: dict[str, Any],
    galois: GaloisAgent,
    euler: EulerAgent,
    pythagore: PythagoreAgent,
    archimedes: ArchimedesAgent,
    experiment_budget: list[float],
) -> V15ProblemResult:
    """Process one HorizonMath problem with v15 hypotheses.

    Pipeline:
        1. H2: Auto-research brief (Hypatia)
        2. Galois: Conjecture + Lean 4 sketch (with research context)
        3. H1: Archimedes sorry decomposition
        4. H3: Sisyphus iterative refinement (up to 3 rounds)
        5. Euler: Zero-Sorry Guillotine + Bayesian verification
        6. Pythagore: Probabilistic gap classification
    """
    t_start = time.monotonic()
    pid = problem["pid"]
    domain = problem["domain"]
    prob_class = problem["class"]

    result = V15ProblemResult(
        pid=pid,
        domain=domain,
        problem_class=prob_class,
        v14_status=problem.get("v14_status", ""),
        v14_sorry=problem.get("v14_sorry", 0),
    )

    print(f"\n{'─'*65}")
    print(f"  🔬 {pid}")
    print(f"  Domain: {domain} | Class {prob_class} | v14 sorry: {problem.get('v14_sorry', '?')}")
    print(f"  Budget used: ${experiment_budget[0]:.2f} / $400.00")
    print(f"{'─'*65}")

    # ── Budget guard ─────────────────────────────────────────────────────────
    if experiment_budget[0] >= BUDGET_CAP_USD - 20.0:
        logger.warning("budget_near_exhaustion", used=experiment_budget[0])
        result.v15_verdict = "BUDGET_EXCEEDED"
        return result

    # ── H2: Pre-proof literature research ────────────────────────────────────
    research_brief = ""
    if ENABLE_H2_AUTO_RESEARCH:
        print(f"  [H2-Hypatia] Auto-research literature mining...")
        research_brief = _build_research_brief(pid, domain, pid)
        if research_brief:
            print(f"  ✓ Research brief: {len(research_brief)} chars, "
                  f"{research_brief.count('[') - 1} papers found")
            result.research_brief = research_brief
            result.hypotheses_applied.append("H2_AUTO_RESEARCH")
        else:
            print(f"  ○ No relevant papers found (continuing without research context)")

    # ── Galois: conjecture + Lean 4 sketch ───────────────────────────────────
    print(f"  [Galois] Generating conjecture + sketch (SymBrain v11)...")

    # Build enriched Galois prompt incorporating research brief (H2)
    galois_prompt = (
        f"Generate a rigorous mathematical conjecture and Lean 4 proof sketch for: {pid}\n"
        f"Domain: {domain} | Complexity Class: {prob_class}\n"
        f"\n{research_brief}\n"
        f"\nIMPORTANT: Use real Mathlib4 theorems. Do NOT use `sorry` where Mathlib4\n"
        f"already has a proof (e.g., `Real.Gamma_pos_of_pos` for Gamma function positivity).\n"
        f"Only use `sorry` for genuinely open sub-claims."
    )

    lean4_sketch = ""
    conjecture_statement = ""
    cost_galois = 0.0

    try:
        galois_result = await galois.run(galois_prompt)
        galois_answer = galois_result.answer
        galois_answer_str = str(galois_answer)
        cost_galois = getattr(galois_result, "cost_usd", 0.17)

        # Extract sketch using multi-level parser (preserving v14's robust approach)
        conj_result = (galois_answer.get("conjecture_generator") if isinstance(galois_answer, dict) else None)
        inner = getattr(conj_result, "conjectures", None) or []
        if inner and hasattr(inner[0], "lean4_sketch"):
            best = inner[0]
            conjecture_statement = getattr(best, "statement", "") or ""
            lean4_sketch = getattr(best, "lean4_sketch", "") or ""
        elif isinstance(conj_result, dict):
            conjecture_statement = conj_result.get("statement", "")
            lean4_sketch = conj_result.get("lean4_sketch", "")

        # Regex fallback (v14 pattern — kept for reliability)
        if not lean4_sketch:
            m = re.search(r"lean4_sketch='(.*?)(?=',\s*[a-z_]+=|'\))", galois_answer_str, re.DOTALL)
            if not m:
                m = re.search(r'lean4_sketch="(.*?)(?=",\s*[a-z_]+=|"\))', galois_answer_str, re.DOTALL)
            if m:
                lean4_sketch = m.group(1).replace("\\n", "\n").replace("\\\\", "\\")

        if not conjecture_statement:
            m2 = re.search(r"statement='(.*?)(?=',\s*[a-z_]+=|'\))", galois_answer_str, re.DOTALL)
            conjecture_statement = m2.group(1) if m2 else galois_answer_str[:500]

        # Apply v15 char limits (2000 for sketch, up from v14's 800)
        result.conjecture_statement = conjecture_statement[:CONJECTURE_CHAR_LIMIT]
        result.lean4_sketch = lean4_sketch[:SKETCH_CHAR_LIMIT]
        result.sorry_count = lean4_sketch.lower().count("sorry")

        experiment_budget[0] += cost_galois
        result.cost_usd += cost_galois
        print(f"  ✓ Galois: {len(lean4_sketch)} chars, {result.sorry_count} sorry stubs")

    except Exception as e:
        logger.error("galois_v15_failed", pid=pid, error=str(e)[:200])
        print(f"  🛑 CIRCUIT BREAKER: Galois failed — {str(e)[:80]}")
        result.v15_verdict = "CB_TRIPPED"
        result.elapsed_s = time.monotonic() - t_start
        return result

    # ── H1: Archimedes sorry decomposition ───────────────────────────────────
    if ENABLE_H1_ARCHIMEDES and result.sorry_count > 0:
        print(f"  [H1-Archimedes] Method of Exhaustion: {result.sorry_count} sorry gaps...")
        try:
            arch_result = await archimedes.run(
                query=f"Prove sub-lemmas for HorizonMath problem: {pid}",
                lean4_sketch=result.lean4_sketch,
                domain=domain,
            )
            arch_data = arch_result.answer

            if arch_data and arch_data.get("reduction", 0) > 0:
                result.lean4_sketch_archimedes = arch_data.get("lean4_sketch", result.lean4_sketch)
                result.sorry_count_after_archimedes = arch_data.get("sorry_count", result.sorry_count)
                result.archimedes_reduction = arch_data.get("reduction", 0)
                # Use the improved sketch going forward
                lean4_sketch = result.lean4_sketch_archimedes
                result.hypotheses_applied.append("H1_ARCHIMEDES")
                print(f"  ✓ Archimedes: {result.sorry_count} → {result.sorry_count_after_archimedes} sorry "
                      f"(-{result.archimedes_reduction} gaps)")
            else:
                result.sorry_count_after_archimedes = result.sorry_count
                print(f"  ○ Archimedes: no gaps resolved (intractable or no improvement)")

            experiment_budget[0] += arch_result.cost_usd
            result.cost_usd += arch_result.cost_usd

        except Exception as e:
            logger.warning("archimedes_failed", pid=pid, error=str(e)[:100])
            result.sorry_count_after_archimedes = result.sorry_count
            print(f"  ⚠ Archimedes failed: {str(e)[:60]}")

    else:
        result.sorry_count_after_archimedes = result.sorry_count

    # ── H3: Sisyphus iterative refinement ────────────────────────────────────
    # If sorry_count is still > 0 after Archimedes, run up to SISYPHUS_MAX_ROUNDS
    # additional Galois passes with error feedback and escalating temperature.
    current_sorry = lean4_sketch.lower().count("sorry")
    sisyphus_rounds_done = 0

    if ENABLE_H3_SISYPHUS and current_sorry > 0:
        print(f"  [H3-Sisyphus] Iterative refinement: {current_sorry} sorry gaps remain...")
        for round_num in range(1, SISYPHUS_MAX_ROUNDS + 1):
            if current_sorry == 0:
                break

            temperature = SISYPHUS_TEMPERATURES[min(round_num - 1, len(SISYPHUS_TEMPERATURES) - 1)]

            # Identify specific sorry contexts for feedback
            sorry_contexts = []
            for m in re.finditer(r'\bsorry\b', lean4_sketch, re.IGNORECASE):
                pos = m.start()
                ctx_before = lean4_sketch[max(0, pos-60):pos].strip().split('\n')[-1]
                sorry_contexts.append(f"  → Gap: ...{ctx_before} sorry...")

            sorry_feedback_str = "\n".join(sorry_contexts[:5])

            # Get Mathlib4 tactic hints (H5)
            mathlib_hints = _get_mathlib4_hints("convergence", domain)  # Generic hints

            sisyphus_prompt = (
                f"SISYPHUS ROUND {round_num}/{SISYPHUS_MAX_ROUNDS} for {pid}.\n"
                f"Temperature: {temperature} (creative mode)\n\n"
                f"CURRENT SORRY GAPS THAT NEED PROOF:\n{sorry_feedback_str}\n"
                f"{mathlib_hints}\n\n"
                f"Previous sketch (with {current_sorry} remaining sorry stubs):\n"
                f"{lean4_sketch[:1500]}\n\n"
                f"Provide an IMPROVED Lean 4 sketch that resolves as many sorry stubs as possible.\n"
                f"Use the Mathlib4 hints above. If a gap is genuinely intractable, keep sorry but\n"
                f"add a comment: -- [INTRACTABLE: reason]\n"
                f"Output ONLY the improved Lean 4 code."
            )

            try:
                galois_retry = await galois.run(sisyphus_prompt)
                retry_sketch = str(galois_retry.answer)[:SKETCH_CHAR_LIMIT]

                # Check if improved
                new_sorry = retry_sketch.lower().count("sorry")
                cost_retry = getattr(galois_retry, "cost_usd", 0.12)
                experiment_budget[0] += cost_retry
                result.cost_usd += cost_retry

                if new_sorry < current_sorry:
                    lean4_sketch = retry_sketch
                    current_sorry = new_sorry
                    sisyphus_rounds_done += 1
                    print(f"  ✓ Sisyphus R{round_num}: {new_sorry} sorry ({current_sorry} → {new_sorry})")
                else:
                    print(f"  ○ Sisyphus R{round_num}: no improvement (still {current_sorry} sorry)")
                    break  # Stagnation — stop early

            except Exception as e:
                logger.warning("sisyphus_round_failed", round=round_num, pid=pid, error=str(e)[:80])
                break

        if sisyphus_rounds_done > 0:
            result.hypotheses_applied.append(f"H3_SISYPHUS_{sisyphus_rounds_done}R")

    result.sisyphus_rounds = sisyphus_rounds_done
    result.sorry_count_final = lean4_sketch.lower().count("sorry")
    # Update lean4_sketch with the best version
    result.lean4_sketch_archimedes = lean4_sketch

    # ── Euler: Zero-Sorry Guillotine ─────────────────────────────────────────
    print(f"  [Euler] Verifying (ZSG v14.1 epistemic standard)...")
    final_sorry_count = lean4_sketch.lower().count("sorry")
    result.domain_prior = _get_domain_prior(domain)

    try:
        euler_payload = (
            f"Problem: {pid} | Domain: {domain} | v15\n"
            f"Conjecture: {result.conjecture_statement[:600]}\n"
            f"Lean 4 Sketch (after Archimedes+Sisyphus):\n{lean4_sketch[:SKETCH_CHAR_LIMIT]}\n"
            f"v15 hypotheses applied: {', '.join(result.hypotheses_applied)}"
        )
        euler_res = await euler.run(
            f"Verify the v15 conjecture for '{pid}'.\n{euler_payload}\n"
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
            logger.warning("zsg_applied", pid=pid, sorry=final_sorry_count)
            print(f"  🚨 ZSG: {final_sorry_count} sorries → conf capped at 0.70")

        # Empty sketch guard
        if not lean4_sketch.strip() and euler_conf >= 0.85:
            euler_conf = 0.60
            result.sorry_guillotine_applied = True

        result.v15_confidence = euler_conf
        experiment_budget[0] += getattr(euler_res, "cost_usd", 0.15)
        result.cost_usd += getattr(euler_res, "cost_usd", 0.15)

        # Determine verdict
        if euler_conf >= 0.85 and final_sorry_count == 0:
            result.v15_verdict = "VERIFIED"          # True VERIFIED: zero sorry
        elif euler_conf >= 0.65:
            result.v15_verdict = "INCOMPLETE"
        else:
            result.v15_verdict = "REFUTED"

    except Exception as e:
        logger.warning("euler_v15_failed", pid=pid, error=str(e)[:100])
        result.v15_verdict = "INCOMPLETE"
        result.v15_confidence = 0.60

    # ── Pythagore: Probabilistic gap classification ───────────────────────────
    print(f"  [Pythagore] Gap probability analysis...")
    try:
        pyth_res = await pythagore.run(
            f"Probabilistic sorry-gap analysis for '{pid}' (domain: {domain}).\n"
            f"Final sketch ({final_sorry_count} sorry stubs remaining):\n{lean4_sketch[:600]}\n"
            f"v15 verdict: {result.v15_verdict}\n"
            f"For each sorry: name the mathematical claim, estimate Mathlib4 coverage probability.\n"
            f"Output JSON: {{lemma_name: probability_0_to_1}}"
        )
        # Parse gap map
        pyth_str = str(pyth_res.answer)
        map_m = re.search(r'\{[^}]+\}', pyth_str, re.DOTALL)
        if map_m:
            try:
                gap_map = json.loads(map_m.group(0))
                result.gap_probability_map = {k: float(v) for k, v in gap_map.items() if isinstance(v, (int, float))}
            except Exception:
                pass
        experiment_budget[0] += getattr(pyth_res, "cost_usd", 0.01)
        result.cost_usd += getattr(pyth_res, "cost_usd", 0.01)
    except Exception as e:
        logger.debug("pythagore_v15_failed", pid=pid, error=str(e)[:80])

    result.elapsed_s = time.monotonic() - t_start

    # ── Print summary ─────────────────────────────────────────────────────────
    verdict_emoji = {"VERIFIED": "✅", "INCOMPLETE": "🔶", "REFUTED": "❌", "CB_TRIPPED": "🛑"}.get(result.v15_verdict, "❓")
    print(f"\n  {verdict_emoji} {pid}: {result.v15_verdict} | conf={result.v15_confidence:.2f}")
    print(f"     Sorry: {result.sorry_count} → {result.sorry_count_after_archimedes} → {final_sorry_count} (final)")
    print(f"     Archimedes reduced: {result.archimedes_reduction} | Sisyphus rounds: {result.sisyphus_rounds}")
    print(f"     Cost: ${result.cost_usd:.3f} | Time: {result.elapsed_s:.1f}s")
    print(f"     H-applied: {result.hypotheses_applied}")

    return result


# ── Per-Domain Keep-Warm Batch ────────────────────────────────────────────────

async def run_domain_batch(
    problems: list[dict[str, Any]],
    galois: GaloisAgent,
    euler: EulerAgent,
    pythagore: PythagoreAgent,
    archimedes: ArchimedesAgent,
    turing: TuringAgent,
    experiment_budget: list[float],
) -> list[V15ProblemResult]:
    """Run a domain batch with L4 keep-warm (deploy once, process all, teardown).

    This implements the L4 keep-warm strategy from the v15 plan:
    - Deploy L4 Spot ONCE for the domain batch
    - Process all problems in the batch sequentially
    - Teardown ONCE at the end
    - Cost: $0.01/problem for GPU warmup (vs $0.10/problem in v14)
    """
    domain = problems[0]["domain"] if problems else "unknown"
    print(f"\n{'═'*65}")
    print(f"  📦 Domain Batch: {domain} | {len(problems)} problems")
    print(f"  GPU: L4 Spot ({GPU_SPOT}) | Regions: {GPU_REGIONS[0]}")
    print(f"{'═'*65}")

    # Deploy L4 keep-warm for batch
    try:
        await turing.run(
            f"deploy L4 spot instance for domain batch: {domain}. "
            f"Regions: {GPU_REGIONS}. Keep-warm: do not teardown between problems."
        )
        experiment_budget[0] += 0.05  # $0.05 for keep-warm deployment (vs $0.10)
        print(f"  🟢 L4 Spot deployed for batch (${0.05:.2f})")
    except Exception as e:
        logger.warning("turing_deploy_batch_failed", domain=domain, error=str(e)[:80])
        print(f"  ⚠ Turing deployment failed (continuing on CPU): {str(e)[:60]}")

    results = []
    for i, problem in enumerate(problems):
        print(f"\n  Problem {i+1}/{len(problems)} in {domain} batch")
        result = await process_problem_v15(
            problem=problem,
            galois=galois,
            euler=euler,
            pythagore=pythagore,
            archimedes=archimedes,
            experiment_budget=experiment_budget,
        )
        results.append(result)

        # Save intermediate result
        out_file = SCRATCH_DIR / f"{result.pid}_v15.json"
        out_file.write_text(json.dumps({
            "pid": result.pid, "domain": result.domain,
            "v15_verdict": result.v15_verdict, "v15_confidence": result.v15_confidence,
            "sorry_count": result.sorry_count, "sorry_count_after_archimedes": result.sorry_count_after_archimedes,
            "sorry_count_final": result.sorry_count_final,
            "archimedes_reduction": result.archimedes_reduction,
            "sisyphus_rounds": result.sisyphus_rounds,
            "hypotheses_applied": result.hypotheses_applied,
            "conjecture_statement": result.conjecture_statement[:CONJECTURE_CHAR_LIMIT],
            "lean4_sketch": result.lean4_sketch[:SKETCH_CHAR_LIMIT],
            "lean4_sketch_archimedes": result.lean4_sketch_archimedes[:SKETCH_CHAR_LIMIT],
            "research_brief": result.research_brief[:400],
            "v14_sorry": result.v14_sorry,
            "v14_status": result.v14_status,
            "domain_prior": result.domain_prior,
            "gap_probability_map": result.gap_probability_map,
            "sorry_guillotine_applied": result.sorry_guillotine_applied,
            "cost_usd": round(result.cost_usd, 4),
            "elapsed_s": round(result.elapsed_s, 2),
        }, indent=2))

    # Teardown after batch (not per-problem)
    try:
        await turing.run(f"tear down L4 deployment for {domain} batch")
        print(f"\n  🔴 L4 Spot torn down after {domain} batch")
    except Exception as e:
        logger.warning("turing_teardown_batch_failed", domain=domain, error=str(e)[:80])

    return results


# ── Main Orchestrator ─────────────────────────────────────────────────────────

async def main() -> None:
    """v15 main orchestration loop."""
    run_start = time.monotonic()
    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║      SymBrain v15 — HorizonMath Method of Exhaustion            ║
║      H1: Archimedes | H2: Auto-Research | H3: Sisyphus          ║
║      H5: Euclid Index | GPU: L4 Spot Keep-Warm                  ║
╠══════════════════════════════════════════════════════════════════╣
║  Budget: $400 | Spent v13+v14: ${PREVIOUS_SPEND_USD:.2f} | Remaining: ${BUDGET_REMAINING_USD:.2f}  ║
╚══════════════════════════════════════════════════════════════════╝
    """)

    # ── Initialize agents ─────────────────────────────────────────────────────
    galois     = GaloisAgent()
    euler      = EulerAgent()
    pythagore  = PythagoreAgent()
    turing     = TuringAgent()
    archimedes = ArchimedesAgent()  # H1: NEW

    galois.upgrade_to_v11()  # SymBrain v11 dual hemisphere

    # ── Shared budget counter ─────────────────────────────────────────────────
    experiment_budget: list[float] = [PREVIOUS_SPEND_USD]

    # ── Group problems by domain for keep-warm batching ───────────────────────
    # L4 keep-warm strategy: deploy once per domain, not per problem
    from collections import defaultdict
    domain_batches: dict[str, list[dict]] = defaultdict(list)
    for p in V14_PROBLEMS:
        domain_batches[p["domain"]].append(p)

    print(f"\n📊 Problem Distribution ({len(V14_PROBLEMS)} total):")
    for domain, batch in sorted(domain_batches.items(), key=lambda x: -len(x[1])):
        print(f"   {domain:<35} {len(batch):2d} problems")

    # ── Sequential domain batch processing ───────────────────────────────────
    all_results: list[V15ProblemResult] = []
    last_monitor = time.monotonic()

    for domain, batch in sorted(domain_batches.items(), key=lambda x: -len(x[1])):
        batch_results = await run_domain_batch(
            problems=batch,
            galois=galois,
            euler=euler,
            pythagore=pythagore,
            archimedes=archimedes,
            turing=turing,
            experiment_budget=experiment_budget,
        )
        all_results.extend(batch_results)

        # 5-minute monitoring print
        now = time.monotonic()
        if now - last_monitor >= MONITOR_INTERVAL_S:
            last_monitor = now
            done = len(all_results)
            elapsed_min = (now - run_start) / 60
            print(f"\n⏱ MONITOR [{elapsed_min:.1f} min] | "
                  f"{done}/{len(V14_PROBLEMS)} done | "
                  f"Budget: ${experiment_budget[0]:.2f}/$400")

    # ── Final Report ──────────────────────────────────────────────────────────
    elapsed_total = time.monotonic() - run_start

    verified = [r for r in all_results if r.v15_verdict == "VERIFIED"]
    incomplete = [r for r in all_results if r.v15_verdict == "INCOMPLETE"]
    refuted = [r for r in all_results if r.v15_verdict == "REFUTED"]
    cb = [r for r in all_results if r.v15_verdict == "CB_TRIPPED"]

    total_sorry_before = sum(r.sorry_count for r in all_results)
    total_sorry_after = sum(r.sorry_count_final for r in all_results)
    total_archimedes_reduction = sum(r.archimedes_reduction for r in all_results)
    total_cost = experiment_budget[0]

    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║  SymBrain v15 — FINAL REPORT                                     ║
╠══════════════════════════════════════════════════════════════════╣
║  Problems: {len(all_results):2d} total                                          ║
║  ✅ VERIFIED:   {len(verified):2d}  (genuine: zero sorry stubs)               ║
║  🔶 INCOMPLETE: {len(incomplete):2d}                                           ║
║  ❌ REFUTED:    {len(refuted):2d}                                           ║
║  🛑 CB_TRIPPED: {len(cb):2d}                                           ║
╠══════════════════════════════════════════════════════════════════╣
║  Sorry reduction (H1+H3):                                        ║
║    Before: {total_sorry_before:4d} stubs                                     ║
║    After:  {total_sorry_after:4d} stubs  ({total_sorry_before - total_sorry_after:4d} eliminated)             ║
║    Archimedes alone: -{total_archimedes_reduction:3d} stubs                       ║
╠══════════════════════════════════════════════════════════════════╣
║  Runtime: {elapsed_total/60:.1f} min | Cost: ${total_cost:.2f} / $400.00           ║
╚══════════════════════════════════════════════════════════════════╝
    """)

    # ── Save final summary JSON ───────────────────────────────────────────────
    summary = {
        "run": "v15",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "hypotheses": {
            "H1_archimedes": ENABLE_H1_ARCHIMEDES,
            "H2_auto_research": ENABLE_H2_AUTO_RESEARCH,
            "H3_sisyphus": ENABLE_H3_SISYPHUS,
            "H4_debate": ENABLE_H4_DEBATE,
            "H5_euclid": ENABLE_H5_EUCLID,
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
            "archimedes_reduction": total_archimedes_reduction,
            "elapsed_min": round(elapsed_total / 60, 1),
            "total_cost_usd": round(total_cost, 2),
            "budget_remaining_usd": round(BUDGET_CAP_USD - total_cost, 2),
        },
        "verified_problems": [r.pid for r in verified],
        "refuted_problems": [r.pid for r in refuted],
    }

    summary_file = SCRATCH_DIR / "v15_summary.json"
    summary_file.write_text(json.dumps(summary, indent=2))
    print(f"\n📁 Summary: {summary_file}")

    # Copy to Downloads
    import shutil
    shutil.copy(str(summary_file), str(DOWNLOADS / "v15_summary.json"))
    print(f"📥 Copied to: {DOWNLOADS / 'v15_summary.json'}")


if __name__ == "__main__":
    asyncio.run(main())
