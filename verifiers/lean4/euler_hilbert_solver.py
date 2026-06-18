#!/usr/bin/env python3
"""
SocrateAI Agora — Euler-Hilbert Lean 4 Proof Solver
=====================================================
Iterative, dual-tier LLM pipeline for closing ``sorry`` gaps in Lean 4
formalisations.

Architecture
------------
The solver follows a **tiered escalation** strategy inspired by the
historical Euler → Hilbert progression from intuitive calculation to
rigorous formalisation:

**Tier 1 — Euler (fast, cheap, iterative):**
    Uses Gemini 2.5 Pro with an "Euler formalist" persona.  Each sorry
    gap is attacked in a tight compile→fix loop (up to 5 iterations).
    The model receives the theorem context and cumulative compiler errors,
    learning from each failure.  Cost: ~$0.10/call.

**Tier 2 — Hilbert (heavy, specialised, last resort):**
    If Euler exhausts its iterations, the gap is escalated to a
    specialised model selected by a **model-selection heuristic**:

    • **DeepSeek-Prover-V2** — for tactic-heavy proofs involving deep
      Mathlib dependencies (analysis, topology, category theory).
    • **LeanBERT** — for structural proofs where simple tactic chains
      (``simp``, ``ring``, ``norm_num``, ``linarith``) suffice.

    Hilbert receives the full context *plus* all of Euler's failed
    attempts, so it can avoid known dead ends.  Cost: ~$0.50/call.

    .. note::

       DeepSeek-Prover-V2 and LeanBERT are **mock endpoints** in this
       version.  Their classes define the API contract and intended
       specialisation, but fall back to Gemini 2.5 Pro with tailored
       system prompts.  Swap in real endpoints when available.

Budget
------
Every LLM call is metered.  The pipeline enforces a cumulative budget
(default $50) and halts gracefully if exceeded.

Patent: US-PAT-PEND-2026-0525

Usage::

    # Solve all sorry gaps in a file
    python euler_hilbert_solver.py --file Agora/AlienMath/SomeFile.lean

    # Dry run (no LLM calls)
    python euler_hilbert_solver.py --file Agora/AlienMath/SomeFile.lean --dry-run

    # Custom budget and iterations
    python euler_hilbert_solver.py --file Agora/AlienMath/SomeFile.lean \\
        --max-euler-iterations 3 --budget 25
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import structlog

from google.antigravity import Agent, LocalAgentConfig
from google.antigravity.types import TemplatedSystemInstructions

logger = structlog.get_logger(__name__)

# ─── Constants ───────────────────────────────────────────────────────

LEAN4_ROOT = Path(__file__).parent
DEFAULT_MAX_EULER_ITERATIONS = 5
DEFAULT_BUDGET_USD = 50.0
COMPILE_TIMEOUT_S = 120

# Cost estimates per LLM call (USD)
EULER_CALL_COST = 0.10
HILBERT_CALL_COST = 0.50


# ─── Lean Compilation ───────────────────────────────────────────────


def compile_lean(lean_file: str, project_dir: str) -> tuple[bool, str]:
    """Compile a single Lean 4 file via ``lake build``.

    Runs ``lake build`` in the given project directory, targeting the
    module path derived from *lean_file*.  Captures combined stdout and
    stderr so that compiler diagnostics can be fed back to the LLM on
    failure.

    Args:
        lean_file: Path to the ``.lean`` file **relative to**
            *project_dir* (e.g. ``"Agora/AlienMath/Foo.lean"``).
        project_dir: Absolute or relative path to the Lake project root
            (the directory containing ``lakefile.lean``).

    Returns:
        A ``(success, output)`` tuple where *success* is ``True`` iff
        the compiler exited with code 0, and *output* is the merged
        stdout + stderr text.

    Raises:
        No exceptions — all errors (timeout, missing ``lake``, etc.)
        are captured and returned as ``(False, error_message)``.
    """
    # Convert filesystem path to Lean module name: Agora/Foo/Bar.lean → Agora.Foo.Bar
    module_name = lean_file.removesuffix(".lean").replace(os.sep, ".").replace("/", ".")

    log = logger.bind(module=module_name, project_dir=project_dir)
    log.info("compile_lean_start")

    try:
        t0 = time.monotonic()
        result = subprocess.run(
            ["lake", "build", module_name],
            capture_output=True,
            text=True,
            timeout=COMPILE_TIMEOUT_S,
            cwd=project_dir,
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        output = (result.stdout + "\n" + result.stderr).strip()
        success = result.returncode == 0

        log.info(
            "compile_lean_done",
            success=success,
            elapsed_ms=elapsed_ms,
            output_len=len(output),
        )
        return success, output

    except subprocess.TimeoutExpired:
        msg = f"COMPILE TIMEOUT ({COMPILE_TIMEOUT_S}s) for {lean_file}"
        log.warning("compile_lean_timeout", timeout_s=COMPILE_TIMEOUT_S)
        return False, msg

    except FileNotFoundError:
        msg = "'lake' not found on PATH. Ensure the Lean 4 toolchain is active."
        log.error("compile_lean_no_lake")
        return False, msg

    except Exception as exc:
        msg = f"Unexpected compile error: {exc}"
        log.error("compile_lean_error", error=str(exc)[:200])
        return False, msg


# ─── Sorry Extraction ───────────────────────────────────────────────


@dataclass(slots=True)
class SorryGap:
    """A single ``sorry`` gap extracted from a Lean 4 source file.

    Attributes:
        line_number: 1-indexed line where the ``sorry`` appears.
        context: The surrounding source lines (typically ±15 lines)
            that give the LLM enough context to generate a replacement.
        theorem_name: The enclosing theorem/lemma name, if detected.
        full_line: The raw line containing ``sorry``.
    """

    line_number: int
    context: str
    theorem_name: str = ""
    full_line: str = ""


def extract_sorry_gaps(lean_file_path: str) -> list[SorryGap]:
    """Parse a ``.lean`` file and extract all ``sorry`` gaps with context.

    For each ``sorry`` found (outside comments and string literals), we
    capture ±15 surrounding lines to give the LLM enough structural
    context.  We also attempt to identify the enclosing ``theorem`` or
    ``lemma`` declaration.

    Args:
        lean_file_path: Absolute or relative path to a ``.lean`` file.

    Returns:
        List of :class:`SorryGap` instances, ordered by line number.
    """
    filepath = Path(lean_file_path)
    if not filepath.exists():
        logger.warning("extract_sorry_gaps_no_file", path=str(filepath))
        return []

    lines = filepath.read_text(encoding="utf-8").splitlines()
    gaps: list[SorryGap] = []
    in_block_comment = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Track block comments (/-  … -/)
        if "/-" in stripped:
            in_block_comment = True
        if "-/" in stripped:
            in_block_comment = False
            continue
        if in_block_comment:
            continue
        if stripped.startswith("--"):
            continue

        # Strip string literals before checking for sorry
        no_strings = re.sub(r'"[^"]*"', '""', stripped)
        if not re.search(r"\bsorry\b", no_strings):
            continue

        # Found a sorry — gather context window
        ctx_start = max(0, i - 15)
        ctx_end = min(len(lines), i + 16)
        context_lines = lines[ctx_start:ctx_end]
        context = "\n".join(
            f"{ctx_start + j + 1:4d} | {cl}" for j, cl in enumerate(context_lines)
        )

        # Attempt to find enclosing theorem/lemma name
        theorem_name = ""
        for back in range(i, max(i - 50, -1), -1):
            m = re.match(
                r"^\s*(?:theorem|lemma|def|noncomputable def)\s+(\S+)", lines[back]
            )
            if m:
                theorem_name = m.group(1)
                break

        gaps.append(
            SorryGap(
                line_number=i + 1,  # 1-indexed
                context=context,
                theorem_name=theorem_name,
                full_line=stripped,
            )
        )

    logger.info(
        "extract_sorry_gaps_done",
        file=str(filepath),
        gaps_found=len(gaps),
    )
    return gaps


# ─── Budget Tracker ──────────────────────────────────────────────────


@dataclass
class BudgetTracker:
    """Tracks cumulative LLM spend and enforces a hard budget cap.

    Each call to :meth:`record` logs the cost and checks whether the
    running total exceeds the configured maximum.

    Attributes:
        max_budget_usd: Hard ceiling.  Pipeline halts if exceeded.
        total_cost_usd: Running total of all recorded costs.
        call_log: Per-call cost entries for auditing.
    """

    max_budget_usd: float = DEFAULT_BUDGET_USD
    total_cost_usd: float = 0.0
    call_log: list[dict] = field(default_factory=list)

    def record(self, caller: str, cost_usd: float) -> None:
        """Record a single LLM call cost.

        Args:
            caller: Identifier string (e.g. ``"euler"`` or ``"hilbert/deepseek"``).
            cost_usd: Estimated cost in USD for this call.

        Raises:
            BudgetExceededError: If cumulative cost exceeds the cap.
        """
        self.total_cost_usd += cost_usd
        entry = {
            "caller": caller,
            "cost_usd": round(cost_usd, 4),
            "cumulative_usd": round(self.total_cost_usd, 4),
            "timestamp": time.time(),
        }
        self.call_log.append(entry)
        logger.info("budget_record", **entry)

        if self.total_cost_usd > self.max_budget_usd:
            raise BudgetExceededError(
                f"Budget exceeded: ${self.total_cost_usd:.2f} > "
                f"${self.max_budget_usd:.2f}"
            )

    @property
    def remaining(self) -> float:
        return max(0.0, self.max_budget_usd - self.total_cost_usd)


class BudgetExceededError(RuntimeError):
    """Raised when the cumulative LLM spend exceeds the configured budget."""


# ─── LLM Helper (standalone — no import from agents.pipelines) ──────


async def _llm_generate(identity: str, prompt: str, model: str = "gemini-2.5-pro") -> str:
    """Invoke a single LLM generation via the ``google.antigravity`` SDK.

    Mirrors :func:`agents.pipelines.base.agent_generate` but is fully
    standalone — no imports from ``agents.pipelines``.

    Args:
        identity: System-instruction text defining the agent persona.
        prompt: The user prompt to send.
        model: Foundation model identifier.

    Returns:
        The model's text response, or a ``[MOCK_FALLBACK: …]`` string
        if the real call fails.
    """
    log = logger.bind(agent_identity=identity[:40], model=model)

    no_tools_prefix = (
        "CRITICAL: You must output your response as plain text directly. "
        "Do NOT use any tools, function calls, or file operations. "
        "Simply write your complete response as text output.\n\n"
    )
    augmented_identity = no_tools_prefix + identity

    try:
        cfg = LocalAgentConfig(
            system_instructions=TemplatedSystemInstructions(
                identity=augmented_identity,
            ),
            model=model,
        )
        t0 = time.monotonic()
        async with Agent(config=cfg) as agent:
            response = await agent.chat(prompt)
            result_text = await response.text()
        elapsed_ms = (time.monotonic() - t0) * 1000
        log.info(
            "llm_generate_ok",
            elapsed_ms=round(elapsed_ms, 1),
            response_len=len(result_text),
        )
        return result_text

    except Exception as exc:
        error_msg = str(exc)[:120]
        log.warning("llm_generate_fallback", error=error_msg)
        return f"[MOCK_FALLBACK: {error_msg}]"


# ─── Euler Solver (Tier 1) ──────────────────────────────────────────


class EulerSolver:
    """Tier-1 iterative proof solver using Gemini 2.5 Pro.

    Named after Leonhard Euler — the prolific calculator who generated
    proofs at extraordinary speed.  This solver attacks each sorry gap
    with a tight compile → fix feedback loop, using compiler errors from
    previous iterations to converge on a valid proof.

    The solver's persona is a master formalist fluent in Lean 4 and
    Mathlib, prioritising tactic-based proofs.

    Attributes:
        max_iterations: Maximum compile → fix cycles per sorry gap.
        budget: Shared :class:`BudgetTracker` instance.
    """

    IDENTITY = (
        "You are Leonhard Euler, master formalist and the most prolific "
        "mathematician in history.  Generate valid Lean 4 proofs using "
        "Mathlib tactics.\n\n"
        "Rules:\n"
        "1. Output ONLY the replacement tactic block — no markdown fences, "
        "   no explanation, no imports.\n"
        "2. Use Mathlib tactics: simp, ring, norm_num, linarith, omega, "
        "   positivity, field_simp, nlinarith, aesop, decide, exact?, "
        "   apply?, rfl, ext, funext, intro, constructor, cases, induction.\n"
        "3. Prefer short proofs.  Chain with <;> when possible.\n"
        "4. If previous compiler errors are provided, fix them specifically.\n"
        "5. Do NOT introduce new sorry.\n"
        "6. Do NOT add import statements.\n"
    )

    def __init__(
        self,
        max_iterations: int = DEFAULT_MAX_EULER_ITERATIONS,
        budget: BudgetTracker | None = None,
    ) -> None:
        self.max_iterations = max_iterations
        self.budget = budget or BudgetTracker()

    async def solve(
        self,
        sorry_context: str,
        compiler_errors: str = "",
        iteration: int = 0,
    ) -> str:
        """Generate a replacement tactic block for a sorry gap.

        Args:
            sorry_context: The theorem statement and surrounding code
                containing the ``sorry`` to be replaced.
            compiler_errors: Compiler diagnostics from the previous
                iteration (empty on the first attempt).
            iteration: Current iteration index (0-based), used for
                logging and prompt engineering.

        Returns:
            A string containing Lean 4 tactic code intended to replace
            the ``sorry``.
        """
        prompt_parts = [
            f"## Sorry Gap (Euler iteration {iteration + 1}/{self.max_iterations})\n",
            "Replace the `sorry` in the following Lean 4 code with a valid proof.\n\n",
            "```lean\n",
            sorry_context,
            "\n```\n",
        ]

        if compiler_errors:
            prompt_parts.extend([
                "\n## Previous Compiler Errors\n",
                "Your last attempt produced these errors.  Fix them:\n\n",
                "```\n",
                compiler_errors,
                "\n```\n",
            ])

        if iteration > 0:
            prompt_parts.append(
                f"\nThis is attempt {iteration + 1}.  Try a different approach "
                "than previous attempts.\n"
            )

        prompt = "".join(prompt_parts)
        result = await _llm_generate(self.IDENTITY, prompt)
        self.budget.record("euler", EULER_CALL_COST)

        # Strip markdown fences if the model wraps the output
        result = _strip_code_fences(result)
        return result


# ─── Hilbert Solver (Tier 2) ────────────────────────────────────────


class DeepSeekProverMock:
    """Mock endpoint for **DeepSeek-Prover-V2**.

    DeepSeek-Prover-V2 is a specialised model fine-tuned on formal
    mathematics corpora (Lean, Coq, Isabelle) with particular strength
    in:

    - Complex Mathlib tactic chains involving ``Filter``, ``Topology``,
      ``MeasureTheory``, and ``CategoryTheory``.
    - Proofs requiring deep import-chain awareness.
    - Novel tactic compositions not well-represented in general LLM
      training data.

    **API Contract (for real endpoint):**

    .. code-block:: python

       class DeepSeekProver:
           async def generate(
               self,
               context: str,        # Lean 4 source with sorry
               failed_attempts: list[str],  # Previous failed proofs
               temperature: float = 0.4,
           ) -> str:
               '''Return tactic block replacing sorry.'''

    This mock falls back to Gemini 2.5 Pro with a specialised prompt
    that mimics DeepSeek-Prover's strengths.
    """

    IDENTITY = (
        "You are a specialised Lean 4 proof engine modelled after "
        "DeepSeek-Prover-V2.  You excel at complex tactic proofs "
        "involving Mathlib's analysis, topology, measure theory, and "
        "category theory libraries.\n\n"
        "Rules:\n"
        "1. Output ONLY the replacement tactic block.\n"
        "2. You have deep knowledge of Mathlib's Filter, Topology, "
        "   MeasureTheory, and CategoryTheory APIs.\n"
        "3. Use advanced tactics: exact?, apply?, refine, calc, conv, "
        "   simp only [...], rw [...], have, suffices, obtain.\n"
        "4. You receive all previous failed attempts — avoid them.\n"
        "5. Do NOT introduce new sorry or axiom.\n"
    )

    async def generate(
        self, context: str, failed_attempts: list[str], temperature: float = 0.4
    ) -> str:
        """Generate a proof using the DeepSeek-Prover mock.

        Falls back to Gemini 2.5 Pro with a specialised prompt.
        """
        prompt_parts = [
            "## Escalated Sorry Gap (DeepSeek-Prover mode)\n\n",
            "```lean\n",
            context,
            "\n```\n",
        ]

        if failed_attempts:
            prompt_parts.append("\n## Failed Euler Attempts (avoid these):\n")
            for i, attempt in enumerate(failed_attempts, 1):
                prompt_parts.extend([
                    f"\n### Attempt {i}:\n```lean\n",
                    attempt,
                    "\n```\n",
                ])

        return await _llm_generate(self.IDENTITY, "".join(prompt_parts))


class LeanBERTMock:
    """Mock endpoint for **LeanBERT**.

    LeanBERT is a lightweight, encoder-based model fine-tuned on Lean 4
    type-checking and simple tactic rewriting.  It excels at:

    - Simple structural proofs (``rfl``, ``trivial``, ``exact``).
    - Tactic chains consisting of ``simp``, ``ring``, ``norm_num``,
      ``linarith``, ``omega``, ``positivity``.
    - Fast inference (< 100 ms per call) making it suitable for
      batch-closing trivial sorry gaps.

    It is **not** suitable for proofs requiring deep Mathlib API
    navigation or multi-step reasoning chains.

    **API Contract (for real endpoint):**

    .. code-block:: python

       class LeanBERT:
           async def generate(
               self,
               context: str,        # Lean 4 source with sorry
               failed_attempts: list[str],
           ) -> str:
               '''Return tactic block replacing sorry.'''

    This mock falls back to Gemini 2.5 Pro with a prompt constraining
    it to simple tactic usage.
    """

    IDENTITY = (
        "You are LeanBERT, a lightweight Lean 4 proof assistant "
        "specialised in simple, structural proofs.\n\n"
        "Rules:\n"
        "1. Output ONLY the replacement tactic block.\n"
        "2. Use ONLY simple tactics: simp, ring, norm_num, linarith, "
        "   omega, positivity, rfl, trivial, exact, decide, constructor.\n"
        "3. Prefer one-line proofs.  Combine with <;> where possible.\n"
        "4. If a one-liner doesn't work, use at most 3 tactic steps.\n"
        "5. Do NOT use advanced Mathlib API calls.\n"
        "6. Do NOT introduce new sorry or axiom.\n"
    )

    async def generate(
        self, context: str, failed_attempts: list[str]
    ) -> str:
        """Generate a proof using the LeanBERT mock.

        Falls back to Gemini 2.5 Pro with a constrained prompt.
        """
        prompt_parts = [
            "## Simple Sorry Gap (LeanBERT mode)\n\n",
            "```lean\n",
            context,
            "\n```\n",
        ]

        if failed_attempts:
            prompt_parts.append("\n## Failed attempts (avoid these):\n")
            for i, attempt in enumerate(failed_attempts, 1):
                prompt_parts.extend([
                    f"\n### Attempt {i}:\n```lean\n",
                    attempt,
                    "\n```\n",
                ])

        return await _llm_generate(self.IDENTITY, "".join(prompt_parts))


class HilbertSolver:
    """Tier-2 escalation solver with model-selection heuristic.

    Named after David Hilbert — who sought to place all of mathematics
    on rigorous axiomatic foundations.  When Euler's fast iterative
    approach fails, Hilbert brings specialised firepower.

    Model Selection Heuristic
    ~~~~~~~~~~~~~~~~~~~~~~~~~
    The heuristic examines the sorry context for domain-specific
    keywords to route to the most appropriate backend:

    +---------------------------------------+---------------------+
    | Context signals                       | Selected model      |
    +=======================================+=====================+
    | ``Mathlib.Analysis``, ``Topology``,   | DeepSeek-Prover-V2  |
    | ``Filter``, ``MeasureTheory``         |                     |
    +---------------------------------------+---------------------+
    | ``category``, ``functor``, ``sheaf``, | DeepSeek-Prover-V2  |
    | ``Monad``, ``NatTrans``               |                     |
    +---------------------------------------+---------------------+
    | ``ring``, ``simp``, ``norm_num``,     | LeanBERT            |
    | ``positivity``, ``linarith``,         |                     |
    | ``omega``, ``decide``                 |                     |
    +---------------------------------------+---------------------+
    | Default                               | DeepSeek-Prover-V2  |
    +---------------------------------------+---------------------+

    Rationale: DeepSeek-Prover handles the "hard" proofs with deep
    Mathlib dependency chains, while LeanBERT efficiently closes
    trivial gaps.  The default is DeepSeek-Prover because unresolved
    gaps that survived Euler are unlikely to be trivial.

    Attributes:
        budget: Shared :class:`BudgetTracker` instance.
        deepseek: The DeepSeek-Prover backend (mock or real).
        leanbert: The LeanBERT backend (mock or real).
    """

    # Keywords that route to DeepSeek-Prover
    _DEEPSEEK_PATTERNS: list[str] = [
        "Mathlib.Analysis",
        "Mathlib.Topology",
        "Mathlib.MeasureTheory",
        "Mathlib.Order.Filter",
        "Filter.",
        "TopologicalSpace",
        "MeasurableSpace",
        "category",
        "functor",
        "Functor",
        "sheaf",
        "Sheaf",
        "NatTrans",
        "Monad",
        "CommRing",
        "Module",
        "Ideal",
    ]

    # Keywords that route to LeanBERT
    _LEANBERT_PATTERNS: list[str] = [
        "ring",
        "simp",
        "norm_num",
        "positivity",
        "linarith",
        "omega",
        "decide",
        "rfl",
        "trivial",
        "constructor",
        "Nat.succ",
        "Nat.zero",
    ]

    def __init__(self, budget: BudgetTracker | None = None) -> None:
        self.budget = budget or BudgetTracker()
        self.deepseek = DeepSeekProverMock()
        self.leanbert = LeanBERTMock()

    def select_model(self, sorry_context: str) -> str:
        """Select the best backend model for a given sorry context.

        Examines the context for domain-specific keywords and returns
        the model name.

        Args:
            sorry_context: The Lean 4 source around the sorry gap.

        Returns:
            Either ``"deepseek-prover"`` or ``"leanbert"``.
        """
        # Check for DeepSeek-Prover signals (higher priority)
        for pattern in self._DEEPSEEK_PATTERNS:
            if pattern in sorry_context:
                logger.info("hilbert_model_select", model="deepseek-prover", trigger=pattern)
                return "deepseek-prover"

        # Check for LeanBERT signals
        leanbert_hits = sum(
            1 for p in self._LEANBERT_PATTERNS if p in sorry_context
        )
        if leanbert_hits >= 2:
            # Require at least 2 LeanBERT signals to avoid false positives
            # (e.g. a single `simp` in a complex proof context)
            logger.info(
                "hilbert_model_select",
                model="leanbert",
                hits=leanbert_hits,
            )
            return "leanbert"

        # Default: DeepSeek-Prover (surviving gaps are likely non-trivial)
        logger.info("hilbert_model_select", model="deepseek-prover", trigger="default")
        return "deepseek-prover"

    async def solve(
        self,
        sorry_context: str,
        euler_attempts: list[str],
    ) -> str:
        """Generate a proof using the Hilbert-tier specialised model.

        Args:
            sorry_context: The Lean 4 source containing the sorry gap,
                including surrounding context.
            euler_attempts: All tactic blocks that Euler tried and
                failed.  The Hilbert model uses these to avoid known
                dead ends.

        Returns:
            A string containing Lean 4 tactic code intended to replace
            the ``sorry``.
        """
        model_name = self.select_model(sorry_context)

        if model_name == "leanbert":
            result = await self.leanbert.generate(sorry_context, euler_attempts)
        else:
            result = await self.deepseek.generate(sorry_context, euler_attempts)

        self.budget.record(f"hilbert/{model_name}", HILBERT_CALL_COST)

        # Strip markdown fences
        result = _strip_code_fences(result)
        return result


# ─── Pipeline Orchestrator ──────────────────────────────────────────


@dataclass
class GapResult:
    """Result of solving a single sorry gap.

    Attributes:
        gap: The original :class:`SorryGap`.
        resolved: Whether the gap was successfully closed.
        solution: The accepted tactic block (empty if unresolved).
        solver_used: Which solver closed it (``"euler"``/``"hilbert"``).
        euler_iterations: Number of Euler compile→fix cycles used.
        hilbert_model: Which Hilbert model was selected (if escalated).
        total_cost_usd: Total LLM spend on this gap.
    """

    gap: SorryGap
    resolved: bool = False
    solution: str = ""
    solver_used: str = ""
    euler_iterations: int = 0
    hilbert_model: str = ""
    total_cost_usd: float = 0.0


class EulerHilbertPipeline:
    """Orchestrates the full Euler → Hilbert sorry-closing pipeline.

    For each sorry gap in the target file:

    1. **Euler phase** — iterate up to *max_euler_iterations* times,
       feeding compiler errors back to the model each round.
    2. **Hilbert phase** — if Euler fails, escalate to a specialised
       model, passing all of Euler's failed attempts.
    3. **Verification** — if Hilbert produces a candidate, verify it
       with ``compile_lean()``.
    4. **Reporting** — generate a structured report of all gaps.

    Attributes:
        lean_file: Path to the target ``.lean`` file.
        project_dir: Lake project root directory.
        max_euler_iterations: Max Euler compile→fix cycles per gap.
        budget: Shared budget tracker.
        euler: The Euler solver instance.
        hilbert: The Hilbert solver instance.
        dry_run: If ``True``, log what would be attempted without
            making LLM calls.
    """

    def __init__(
        self,
        lean_file: str,
        project_dir: str | None = None,
        max_euler_iterations: int = DEFAULT_MAX_EULER_ITERATIONS,
        budget_usd: float = DEFAULT_BUDGET_USD,
        dry_run: bool = False,
    ) -> None:
        self.lean_file = lean_file
        self.project_dir = project_dir or str(LEAN4_ROOT)
        self.max_euler_iterations = max_euler_iterations
        self.dry_run = dry_run

        self.budget = BudgetTracker(max_budget_usd=budget_usd)
        self.euler = EulerSolver(
            max_iterations=max_euler_iterations,
            budget=self.budget,
        )
        self.hilbert = HilbertSolver(budget=self.budget)

    async def run(self) -> list[GapResult]:
        """Execute the full pipeline on the target file.

        Returns:
            List of :class:`GapResult` for each sorry gap found.

        Raises:
            BudgetExceededError: If cumulative LLM spend exceeds the
                configured budget.
        """
        lean_path = Path(self.project_dir) / self.lean_file
        gaps = extract_sorry_gaps(str(lean_path))

        if not gaps:
            logger.info("pipeline_no_gaps", file=self.lean_file)
            print(f"✅ No sorry gaps found in {self.lean_file}")
            return []

        print(f"🔍 Found {len(gaps)} sorry gap(s) in {self.lean_file}")
        print(f"💰 Budget: ${self.budget.max_budget_usd:.2f}")
        print(f"🔄 Max Euler iterations: {self.max_euler_iterations}")
        if self.dry_run:
            print("🏜️  DRY RUN — no LLM calls will be made\n")

        results: list[GapResult] = []

        for gap_idx, gap in enumerate(gaps):
            print(f"\n{'='*60}")
            print(
                f"Gap {gap_idx + 1}/{len(gaps)}: line {gap.line_number}"
                + (f" ({gap.theorem_name})" if gap.theorem_name else "")
            )
            print(f"{'='*60}")

            if self.dry_run:
                result = self._dry_run_gap(gap)
                results.append(result)
                continue

            try:
                result = await self._solve_gap(gap)
            except BudgetExceededError as exc:
                logger.warning("pipeline_budget_exceeded", error=str(exc))
                print(f"\n🚨 {exc}")
                result = GapResult(gap=gap)
                results.append(result)
                break

            results.append(result)

        # Print summary
        self._print_summary(results)
        return results

    async def _solve_gap(self, gap: SorryGap) -> GapResult:
        """Solve a single sorry gap through the Euler → Hilbert pipeline."""
        result = GapResult(gap=gap)
        cost_before = self.budget.total_cost_usd

        # ── Euler Phase ──
        euler_attempts: list[str] = []
        compiler_errors = ""

        for iteration in range(self.max_euler_iterations):
            print(f"\n  🧮 Euler iteration {iteration + 1}/{self.max_euler_iterations}...")

            tactic = await self.euler.solve(
                sorry_context=gap.context,
                compiler_errors=compiler_errors,
                iteration=iteration,
            )
            euler_attempts.append(tactic)
            result.euler_iterations = iteration + 1

            if tactic.startswith("[MOCK_FALLBACK:"):
                print(f"    ⚠️  LLM fallback: {tactic[:80]}")
                compiler_errors = "LLM call failed — try a different approach."
                continue

            # Test-compile with the proposed tactic
            success, output = self._test_compile(gap, tactic)
            if success:
                print(f"    ✅ Euler solved it in {iteration + 1} iteration(s)!")
                result.resolved = True
                result.solution = tactic
                result.solver_used = "euler"
                result.total_cost_usd = self.budget.total_cost_usd - cost_before
                return result

            compiler_errors = output
            print(f"    ❌ Compilation failed. Feeding errors back...")

        # ── Hilbert Phase ──
        print(f"\n  🏛️  Escalating to Hilbert solver...")
        model = self.hilbert.select_model(gap.context)
        print(f"    Model selected: {model}")
        result.hilbert_model = model

        tactic = await self.hilbert.solve(gap.context, euler_attempts)

        if not tactic.startswith("[MOCK_FALLBACK:"):
            success, output = self._test_compile(gap, tactic)
            if success:
                print(f"    ✅ Hilbert ({model}) solved it!")
                result.resolved = True
                result.solution = tactic
                result.solver_used = f"hilbert/{model}"
                result.total_cost_usd = self.budget.total_cost_usd - cost_before
                return result
            else:
                print(f"    ❌ Hilbert solution also failed compilation.")
        else:
            print(f"    ⚠️  LLM fallback: {tactic[:80]}")

        print(f"    🔴 Gap UNRESOLVED after Euler + Hilbert.")
        result.total_cost_usd = self.budget.total_cost_usd - cost_before
        return result

    def _test_compile(self, gap: SorryGap, tactic: str) -> tuple[bool, str]:
        """Substitute a tactic for sorry and test-compile.

        Creates a temporary modified version of the source file with the
        sorry replaced, then runs ``compile_lean`` on it.

        Args:
            gap: The sorry gap being solved.
            tactic: The candidate tactic block to substitute.

        Returns:
            ``(success, compiler_output)`` from :func:`compile_lean`.
        """
        lean_path = Path(self.project_dir) / self.lean_file
        original = lean_path.read_text(encoding="utf-8")
        lines = original.splitlines()

        # Replace the sorry line with the tactic
        sorry_line_idx = gap.line_number - 1  # 0-indexed
        if sorry_line_idx < len(lines):
            # Preserve indentation
            leading_ws = re.match(r"^(\s*)", lines[sorry_line_idx])
            indent = leading_ws.group(1) if leading_ws else ""
            tactic_lines = tactic.strip().splitlines()
            indented_tactic = "\n".join(
                indent + tl if i > 0 else indent + tl.lstrip()
                for i, tl in enumerate(tactic_lines)
            )
            lines[sorry_line_idx] = indented_tactic

        modified = "\n".join(lines) + "\n"

        # Write modified file, compile, then restore original
        try:
            lean_path.write_text(modified, encoding="utf-8")
            success, output = compile_lean(self.lean_file, self.project_dir)
        finally:
            lean_path.write_text(original, encoding="utf-8")

        return success, output

    def _dry_run_gap(self, gap: SorryGap) -> GapResult:
        """Log what would be attempted for a gap without making LLM calls."""
        model = self.hilbert.select_model(gap.context)
        print(f"  [DRY RUN] Would attempt:")
        print(f"    - Euler: up to {self.max_euler_iterations} iterations")
        print(f"    - Hilbert model: {model}")
        print(f"    - Estimated cost: ${EULER_CALL_COST * self.max_euler_iterations + HILBERT_CALL_COST:.2f}")
        print(f"    - Context preview ({gap.theorem_name or 'unknown'}):")
        for line in gap.context.splitlines()[:5]:
            print(f"      {line}")
        return GapResult(gap=gap)

    def _print_summary(self, results: list[GapResult]) -> None:
        """Print a human-readable summary of all gap results."""
        resolved = [r for r in results if r.resolved]
        unresolved = [r for r in results if not r.resolved]

        print(f"\n{'='*60}")
        print("📊 Euler-Hilbert Pipeline Summary")
        print(f"{'='*60}")
        print(f"  Total gaps:      {len(results)}")
        print(f"  ✅ Resolved:     {len(resolved)}")
        print(f"  🔴 Unresolved:   {len(unresolved)}")
        print(f"  💰 Total cost:   ${self.budget.total_cost_usd:.2f}")
        print(f"  💰 Remaining:    ${self.budget.remaining:.2f}")

        if resolved:
            print(f"\n  Resolved gaps:")
            for r in resolved:
                print(
                    f"    ✅ Line {r.gap.line_number} "
                    f"({r.gap.theorem_name or '?'}) — "
                    f"{r.solver_used}, {r.euler_iterations} Euler iter(s), "
                    f"${r.total_cost_usd:.2f}"
                )

        if unresolved:
            print(f"\n  Unresolved gaps:")
            for r in unresolved:
                print(
                    f"    🔴 Line {r.gap.line_number} "
                    f"({r.gap.theorem_name or '?'}) — "
                    f"{r.euler_iterations} Euler iter(s)"
                    + (f", Hilbert/{r.hilbert_model}" if r.hilbert_model else "")
                )

    def generate_report(self, results: list[GapResult]) -> dict:
        """Generate a machine-readable JSON report.

        Args:
            results: List of :class:`GapResult` from :meth:`run`.

        Returns:
            JSON-serialisable dictionary with full pipeline metrics.
        """
        return {
            "file": self.lean_file,
            "project_dir": self.project_dir,
            "max_euler_iterations": self.max_euler_iterations,
            "dry_run": self.dry_run,
            "budget": {
                "max_usd": self.budget.max_budget_usd,
                "spent_usd": round(self.budget.total_cost_usd, 4),
                "remaining_usd": round(self.budget.remaining, 4),
            },
            "summary": {
                "total_gaps": len(results),
                "resolved": sum(1 for r in results if r.resolved),
                "unresolved": sum(1 for r in results if not r.resolved),
            },
            "gaps": [
                {
                    "line": r.gap.line_number,
                    "theorem": r.gap.theorem_name,
                    "resolved": r.resolved,
                    "solver": r.solver_used,
                    "euler_iterations": r.euler_iterations,
                    "hilbert_model": r.hilbert_model,
                    "cost_usd": round(r.total_cost_usd, 4),
                    "solution_preview": r.solution[:200] if r.solution else "",
                }
                for r in results
            ],
            "cost_log": self.budget.call_log,
        }


# ─── Utilities ──────────────────────────────────────────────────────


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences from LLM output.

    Models sometimes wrap their output in ````lean ... ```` blocks
    despite being told not to.  This strips them.
    """
    text = text.strip()
    # Remove opening fence
    text = re.sub(r"^```\w*\s*\n?", "", text)
    # Remove closing fence
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


# ─── CLI ─────────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="euler_hilbert_solver",
        description=(
            "Euler-Hilbert iterative Lean 4 proof solver. "
            "Closes sorry gaps using a dual-tier LLM pipeline."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python euler_hilbert_solver.py --file Agora/AlienMath/Foo.lean\n"
            "  python euler_hilbert_solver.py --file Agora/AlienMath/Foo.lean --dry-run\n"
            "  python euler_hilbert_solver.py --file Agora/AlienMath/Foo.lean "
            "--max-euler-iterations 3 --budget 25\n"
        ),
    )
    parser.add_argument(
        "--file",
        required=True,
        help="Path to the .lean file (relative to the project root).",
    )
    parser.add_argument(
        "--max-euler-iterations",
        type=int,
        default=DEFAULT_MAX_EULER_ITERATIONS,
        help=f"Maximum Euler compile→fix cycles per gap (default: {DEFAULT_MAX_EULER_ITERATIONS}).",
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=DEFAULT_BUDGET_USD,
        help=f"Maximum LLM spend in USD (default: ${DEFAULT_BUDGET_USD:.0f}).",
    )
    parser.add_argument(
        "--project-dir",
        default=None,
        help="Lake project root directory (default: directory of this script).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be attempted without making LLM calls.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to write the JSON report (default: proof/euler_hilbert_report.json).",
    )
    parser.add_argument(
        "--sweep",
        default=None,
        help=(
            "Sweep mode: scan all .lean files under this directory "
            "(e.g. 'Agora/AlienMath') instead of targeting a single file."
        ),
    )
    parser.add_argument(
        "--use-hilbert-agent",
        action="store_true",
        help=(
            "Delegate to the production Hilbert sorry_completer "
            "(10-hypothesis pipeline: LeanBERT + DeepSeek-Prover + Gemini). "
            "Requires agents.hilbert.tools.sorry_completer on PYTHONPATH."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply successful proofs to disk (only with --use-hilbert-agent).",
    )
    parser.add_argument(
        "--max-difficulty",
        default="medium",
        choices=["low", "medium", "hard", "extreme"],
        help="Maximum difficulty for --use-hilbert-agent sweep (default: medium).",
    )
    return parser.parse_args(argv)


def _run_hilbert_agent_sweep(args: argparse.Namespace) -> None:
    """Run the production Hilbert 10-hypothesis sorry_completer.

    This delegates to the battle-tested pipeline in
    ``agents/hilbert/tools/sorry_completer.py`` which uses:
      - LeanBERT GAN generator (CPU, ~negligible cost)
      - DeepSeek-Prover-V2-7B (T4 GPU, ~$0.005/hypothesis)
      - Gemini 2.5 Flash (API, ~$0.015/hypothesis)
      - 3 ratchet iterations with compiler-error feedback

    Source: /Users/xcallens/xdev/SocrateAI-Lean-Verification
    """
    # Add the Agora repo root to sys.path so we can import agents.*
    agora_root = Path(__file__).resolve().parent.parent.parent
    if str(agora_root) not in sys.path:
        sys.path.insert(0, str(agora_root))

    try:
        from agents.hilbert.tools.sorry_completer import complete_all_sorrys
    except ImportError as e:
        print(f"❌ Cannot import Hilbert sorry_completer: {e}")
        print("   Ensure agents/hilbert/tools/ is on PYTHONPATH.")
        print("   Falling back to Euler-Hilbert pipeline.")
        return

    project_root = args.project_dir or str(LEAN4_ROOT)
    root_dir = args.sweep or "Agora"

    print(f"🔬 Hilbert Agent: sweeping {root_dir}/ (max_difficulty={args.max_difficulty})")
    print(f"   project_root={project_root}")
    print(f"   apply_proofs={args.apply}")
    print()

    report = complete_all_sorrys(
        root=root_dir,
        project_root=project_root,
        apply_proofs=args.apply,
        max_difficulty=args.max_difficulty,
    )

    # Write report
    output_path = args.output or str(LEAN4_ROOT / "proof" / "hilbert_sweep_report.json")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    # Summary
    print()
    print("=" * 60)
    print(f"✅ Closed: {report['sorrys_closed']}")
    print(f"❌ Failed: {report['sorrys_failed']}")
    print(f"💰 Cost:   ${report['total_cost_usd']:.4f}")
    print(f"⏱  Time:   {report['elapsed_s']:.1f}s")
    print(f"📄 Report: {output_path}")
    print("=" * 60)


async def async_main(args: argparse.Namespace) -> None:
    """Async entry point for the Euler-Hilbert pipeline."""
    if args.sweep:
        # Sweep mode: process all .lean files in a directory
        sweep_dir = Path(args.project_dir or str(LEAN4_ROOT)) / args.sweep
        lean_files = sorted(sweep_dir.rglob("*.lean"))
        print(f"📂 Sweep mode: found {len(lean_files)} .lean files in {sweep_dir}")

        all_results = []
        for lf in lean_files:
            rel_path = str(lf.relative_to(Path(args.project_dir or str(LEAN4_ROOT))))
            pipeline = EulerHilbertPipeline(
                lean_file=rel_path,
                project_dir=args.project_dir,
                max_euler_iterations=args.max_euler_iterations,
                budget_usd=args.budget,
                dry_run=args.dry_run,
            )
            results = await pipeline.run()
            all_results.extend(results)

        # Aggregate report
        report = {
            "mode": "sweep",
            "directory": args.sweep,
            "files_scanned": len(lean_files),
            "gaps_found": len(all_results),
            "gaps_resolved": sum(1 for r in all_results if r.get("resolved", False)),
        }
    else:
        # Single-file mode
        pipeline = EulerHilbertPipeline(
            lean_file=args.file,
            project_dir=args.project_dir,
            max_euler_iterations=args.max_euler_iterations,
            budget_usd=args.budget,
            dry_run=args.dry_run,
        )
        results = await pipeline.run()
        report = pipeline.generate_report(results)

    # Write report
    output_path = args.output or str(LEAN4_ROOT / "proof" / "euler_hilbert_report.json")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n📄 Report written to: {output_path}")


def main() -> None:
    """CLI entry point.

    Modes:
        --file: Single-file Euler-Hilbert pipeline (default)
        --sweep: Batch process all .lean files in a directory
        --use-hilbert-agent: Delegate to the production 10-hypothesis pipeline
    """
    args = parse_args()

    print("=" * 60)
    print("SocrateAI Agora — Euler-Hilbert Lean 4 Proof Solver")
    print("=" * 60)
    print()

    if args.use_hilbert_agent:
        _run_hilbert_agent_sweep(args)
    else:
        asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
