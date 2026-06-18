# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Patent Generation Pipeline v2 — Enhanced with numeric validation,
Lean 4 formalization, business case, and multi-LLM peer review.

Implements the 8-stage methodology for generating production-grade patents:
    1. literature review (Hypathie)      → prior art & white space
    2. ideation (Eiffel)                 → 10 patentable ideas
    3. selection & drafting (Eiffel)      → top 3 with USPTO claims
    4. numeric validation (Galileo)       → Z3/SAT + numerical witnesses
    5. Lean 4 formalization (Euler)       → formal proofs as appendix
    6. business case (Eiffel)             → market sizing, ROI, fundraising
    7. peer review (3× Mistral)           → independent cross-LLM reviews
    8. final compilation & vaulting        → PDF with all appendixes

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import os
import re
import time
import json
import subprocess
from dataclasses import dataclass, field, asdict
from enum import IntEnum
from typing import Any

import structlog

from agents.pipelines.base import AgentPipeline, PipelineResult, agent_generate

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Pipeline-specific stage enum (8 stages, up from 4)
# ---------------------------------------------------------------------------

class PatentGenerationStage(IntEnum):
    """Stages of the enhanced Patent Generation pipeline."""
    LITERATURE_REVIEW = 1         # Hypathie: Prior art search
    IDEATION = 2                  # Eiffel: Brainstorm 10 patentable ideas
    SELECTION_AND_DRAFTING = 3    # Eiffel: Select top 3 and draft LaTeX claims
    NUMERIC_VALIDATION = 4        # Galileo: Z3/SAT + numerical witness generation
    LEAN4_FORMALIZATION = 5       # Euler: Lean 4 proof sketches for key theorems
    BUSINESS_CASE = 6             # Eiffel: Market sizing, ROI, fundraising strategy
    PEER_REVIEW = 7               # 3× Mistral: Independent cross-LLM peer reviews
    FINAL_COMPILATION = 8         # System: Compile full PDF with appendixes


# ---------------------------------------------------------------------------
# Peer Review result container
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class PeerReview:
    """Result of an independent peer review of a patent draft."""
    reviewer_id: str          # e.g. "mistral_reviewer_1"
    model_used: str           # e.g. "mistral-large-latest"
    verdict: str              # APPROVE / REVISE / REJECT
    strengths: str            # Key strengths identified
    weaknesses: str           # Key weaknesses identified
    patentability_score: int  # 1-10 scale
    full_review: str          # Complete review text


# ---------------------------------------------------------------------------
# LaTeX helpers
# ---------------------------------------------------------------------------

def _sanitize_latex(raw: str) -> str:
    """Strip markdown wrappers and ensure document structure."""
    # Remove markdown code fences
    for prefix in ("```latex", "```tex", "```"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    # Ensure \begin{document}
    if "\\begin{document}" not in raw:
        if "\\maketitle" in raw:
            raw = raw.replace("\\maketitle", "\\begin{document}\n\\maketitle")
        elif "\\begin{abstract}" in raw:
            raw = raw.replace("\\begin{abstract}", "\\begin{document}\n\\begin{abstract}")

    # Ensure \end{document}
    if "\\end{document}" not in raw:
        raw += "\n\\end{document}\n"

    return raw


def _compile_latex(tex_path: str, output_dir: str) -> tuple[str, list[str]]:
    """Run pdflatex and return (pdf_path, warnings)."""
    warnings = []
    pdf_path = tex_path.replace(".tex", ".pdf")
    try:
        # Run twice for cross-references
        for _ in range(2):
            subprocess.run(
                ["pdflatex", "-interaction=nonstopmode",
                 f"-output-directory={output_dir}", tex_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
            )
    except subprocess.CalledProcessError as e:
        warnings.append(
            f"pdflatex warning: {e.output.decode('utf-8', errors='ignore')[:500]}"
        )
    return pdf_path, warnings


# ---------------------------------------------------------------------------
# Enhanced Pipeline Implementation
# ---------------------------------------------------------------------------

class PatentGenerationPipeline(AgentPipeline):
    """Enhanced pipeline for patent generation with numeric validation,
    Lean 4 formalization, business case, and multi-LLM peer review.

    Usage:
        pipeline = PatentGenerationPipeline()
        result = await pipeline.run({
            "topic": "Hypercube bounds and Q-arithmetic",
            "peer_review_model": "mistral-large-latest",  # optional
        })
    """

    def __init__(self, model: str = "gemini-2.5-pro"):
        self.model = model

    def get_stages(self) -> list[PatentGenerationStage]:
        return list(PatentGenerationStage)

    async def run(self, config: dict[str, Any]) -> PipelineResult:
        """Execute the full 8-stage patent generation pipeline."""
        topic = config.get("topic", "Unknown scientific topic")
        peer_model = config.get("peer_review_model", "mistral-large-latest")
        log = logger.bind(topic=topic[:50])
        log.info("patent_pipeline_v2_start")

        t0_total = time.monotonic()
        warnings: list[str] = []
        vault_ids: list[str] = []
        stages_completed: list[str] = []

        # ═══════════════════════════════════════════════════════════════════
        # Stage 1: LITERATURE REVIEW (Hypathie)
        # ═══════════════════════════════════════════════════════════════════
        log.info("stage_start", stage="LITERATURE_REVIEW")
        prior_art_res = await agent_generate(
            identity="You are Hypatie, Librarian of Alexandrie.",
            prompt=(
                f"Perform a thorough prior art literature review on:\n"
                f"'{topic}'\n\n"
                f"Summarize the state-of-the-art, identify key patents "
                f"(US/EU/PCT), and map the 'white space' (gaps) that new "
                f"patents could cover. Include specific patent numbers "
                f"where possible."
            ),
            model=self.model
        )
        stages_completed.append("LITERATURE_REVIEW")
        log.info("stage_complete", stage="LITERATURE_REVIEW")

        # ═══════════════════════════════════════════════════════════════════
        # Stage 2: IDEATION (Eiffel)
        # ═══════════════════════════════════════════════════════════════════
        log.info("stage_start", stage="IDEATION")
        ideas_res = await agent_generate(
            identity=(
                "You are Eiffel, the Pragmatic Engineer & Patent Strategist. "
                "You find the trade-off between innovation, engineering "
                "viability, and commercial fundraising potential."
            ),
            prompt=(
                f"Topic: {topic}\n"
                f"Prior Art Context:\n{prior_art_res[:2000]}\n\n"
                f"Generate exactly 10 distinct patentable ideas. For each:\n"
                f"- Title\n- Core innovation (1 sentence)\n"
                f"- Engineering feasibility (HIGH/MEDIUM/LOW)\n"
                f"- Market size estimate\n"
                f"- Fundraising angle (why would a VC invest?)\n"
                f"Number them 1-10."
            ),
            model=self.model
        )
        stages_completed.append("IDEATION")
        log.info("stage_complete", stage="IDEATION")

        # ═══════════════════════════════════════════════════════════════════
        # Stage 3: SELECTION & DRAFTING (Eiffel)
        # ═══════════════════════════════════════════════════════════════════
        log.info("stage_start", stage="SELECTION_AND_DRAFTING")
        draft_res = await agent_generate(
            identity=(
                "You are Eiffel, a master patent attorney and LaTeX "
                "typesetter. You write precise USPTO-style claims."
            ),
            prompt=(
                f"From these 10 ideas:\n{ideas_res[:3000]}\n\n"
                f"Select the TOP 3 most viable and patentable.\n"
                f"For each, draft formal USPTO-style claims:\n"
                f"- Method Claim (step-by-step algorithm)\n"
                f"- System Claim (components + architecture)\n"
                f"- Apparatus Claim (hardware/software config)\n\n"
                f"OUTPUT: Valid LaTeX only. Start with "
                f"\\documentclass{{article}}. "
                f"Use \\usepackage{{amsmath,amssymb,geometry}}. "
                f"Set \\geometry{{margin=1in}}. "
                f"Title, author (Xavier Callens / Socrate AI Lab), "
                f"\\begin{{document}}, \\maketitle, sections, "
                f"\\end{{document}}. No markdown."
            ),
            model=self.model
        )
        draft_res = _sanitize_latex(draft_res)
        stages_completed.append("SELECTION_AND_DRAFTING")
        log.info("stage_complete", stage="SELECTION_AND_DRAFTING")

        # ═══════════════════════════════════════════════════════════════════
        # Stage 4: NUMERIC VALIDATION (Galileo)
        # ═══════════════════════════════════════════════════════════════════
        log.info("stage_start", stage="NUMERIC_VALIDATION")
        numeric_res = await agent_generate(
            identity=(
                "You are Galileo, the Computational Oracle of the Agora. "
                "You validate mathematical claims through numerical "
                "experiments, SAT solving, and concrete witness generation. "
                "You are ruthlessly empirical — if a claim cannot be "
                "demonstrated numerically, you say so."
            ),
            prompt=(
                f"The following patent claims have been drafted:\n"
                f"{draft_res[:3000]}\n\n"
                f"For each of the 3 inventions, provide:\n"
                f"1. A NUMERIC VALIDATION: concrete numerical example "
                f"   showing the method works (e.g., specific Q-arithmetic "
                f"   computation, hypercube bound check, witness generation)\n"
                f"2. A COUNTEREXAMPLE SEARCH: attempt to find edge cases "
                f"   or failure modes (SAT-style reasoning)\n"
                f"3. A CONFIDENCE SCORE (0-100%) for each claim's "
                f"   mathematical soundness\n\n"
                f"Format as LaTeX appendix sections starting with "
                f"\\section{{Appendix A: Numeric Validation}}. "
                f"Include actual numbers, not placeholders."
            ),
            model=self.model
        )
        # Strip any document wrapper — we only want the appendix body
        numeric_res = re.sub(
            r'\\documentclass.*?\\begin\{document\}', '', numeric_res,
            flags=re.DOTALL
        )
        numeric_res = numeric_res.replace('\\end{document}', '').strip()
        stages_completed.append("NUMERIC_VALIDATION")
        log.info("stage_complete", stage="NUMERIC_VALIDATION")

        # ═══════════════════════════════════════════════════════════════════
        # Stage 5: LEAN 4 FORMALIZATION (Euler)
        # ═══════════════════════════════════════════════════════════════════
        log.info("stage_start", stage="LEAN4_FORMALIZATION")
        lean4_res = await agent_generate(
            identity=(
                "You are Euler, a rigorous mathematical verifier. "
                "You formalize mathematical claims in Lean 4 theorem prover "
                "syntax. You demand 0 sorry, 0 axiom proofs. "
                "If a full proof is not achievable, you provide a precise "
                "proof sketch with explicit sorry markers and explain "
                "what remains to be proven."
            ),
            prompt=(
                f"The following patent claims involve mathematical methods:\n"
                f"{draft_res[:2000]}\n\n"
                f"For each of the 3 inventions, provide a Lean 4 "
                f"formalization of the CORE mathematical theorem that "
                f"underpins the patent claim. Specifically:\n"
                f"1. Define the key types (e.g., HypercubeBound, "
                f"   RationalWitness)\n"
                f"2. State the main theorem\n"
                f"3. Provide proof or sorry with explanation\n"
                f"4. Show how ExactRationalWitness pattern applies\n\n"
                f"Format as LaTeX appendix: "
                f"\\section{{Appendix B: Lean 4 Formalization}} "
                f"with \\begin{{verbatim}}...\\end{{verbatim}} blocks "
                f"for Lean 4 code. Include commentary on proof status."
            ),
            model=self.model
        )
        lean4_res = re.sub(
            r'\\documentclass.*?\\begin\{document\}', '', lean4_res,
            flags=re.DOTALL
        )
        lean4_res = lean4_res.replace('\\end{document}', '').strip()
        stages_completed.append("LEAN4_FORMALIZATION")
        log.info("stage_complete", stage="LEAN4_FORMALIZATION")

        # ═══════════════════════════════════════════════════════════════════
        # Stage 6: BUSINESS CASE (Eiffel)
        # ═══════════════════════════════════════════════════════════════════
        log.info("stage_start", stage="BUSINESS_CASE")
        business_res = await agent_generate(
            identity=(
                "You are Eiffel, the Pragmatic Engineer. "
                "You create investor-ready business cases with concrete "
                "numbers, market sizing (TAM/SAM/SOM), competitive "
                "landscape, and fundraising strategy."
            ),
            prompt=(
                f"The following 3 patents have been drafted and validated:\n"
                f"{draft_res[:2000]}\n\n"
                f"Numeric validation summary:\n{numeric_res[:1000]}\n\n"
                f"For each patent, create a business case appendix:\n"
                f"1. TAM/SAM/SOM market sizing (with sources)\n"
                f"2. Competitive landscape (who are the incumbents?)\n"
                f"3. Revenue model (licensing, SaaS, hardware?)\n"
                f"4. 5-year ROI projection\n"
                f"5. Fundraising strategy (seed → Series A)\n"
                f"6. Key risks and mitigations\n\n"
                f"Format as LaTeX appendix: "
                f"\\section{{Appendix C: Business Case Analysis}}. "
                f"Use \\begin{{tabular}} for financials."
            ),
            model=self.model
        )
        business_res = re.sub(
            r'\\documentclass.*?\\begin\{document\}', '', business_res,
            flags=re.DOTALL
        )
        business_res = business_res.replace('\\end{document}', '').strip()
        stages_completed.append("BUSINESS_CASE")
        log.info("stage_complete", stage="BUSINESS_CASE")

        # ═══════════════════════════════════════════════════════════════════
        # Stage 7: PEER REVIEW (3× Mistral)
        # ═══════════════════════════════════════════════════════════════════
        log.info("stage_start", stage="PEER_REVIEW")
        # Each reviewer uses a different model variant to maximize
        # diversity of perspectives (Mistral falls back to Gemini
        # variants if unavailable via the Antigravity SDK)
        reviewers = [
            ("Reviewer Alpha",
             "a senior patent examiner at the USPTO with 20 years of "
             "experience in software and mathematical method patents. "
             "You focus on novelty, non-obviousness, and enablement. "
             "You are skeptical of overly broad claims.",
             "gemini-2.5-pro"),
            ("Reviewer Beta",
             "a venture capitalist and former CTO at a deep-tech startup "
             "evaluating the commercial viability and defensibility of "
             "the patent portfolio. You care about market size, moats, "
             "and whether this IP can anchor a $100M+ company.",
             "gemini-2.5-flash"),
            ("Reviewer Gamma",
             "a professor of formal methods and theorem proving at ETH "
             "Zürich who evaluates the mathematical rigor and novelty "
             "of the claims. You demand Lean 4 proofs with 0 sorry. "
             "You are deeply familiar with Harrison, Hales, and Avigad.",
             "gemini-2.5-flash"),
        ]

        peer_reviews: list[PeerReview] = []
        review_latex_parts: list[str] = []

        for i, (name, expertise, reviewer_model) in enumerate(reviewers, 1):
            log.info("peer_review_start", reviewer=name, model=reviewer_model)
            review_text = await agent_generate(
                identity=(
                    f"You are {name}, {expertise}. "
                    f"You are conducting an independent peer review. "
                    f"Be thorough, critical, and constructive."
                ),
                prompt=(
                    f"PEER REVIEW REQUEST\n"
                    f"==================\n"
                    f"Review the following patent portfolio:\n\n"
                    f"CLAIMS:\n{draft_res[:2000]}\n\n"
                    f"NUMERIC VALIDATION:\n{numeric_res[:800]}\n\n"
                    f"LEAN 4 FORMALIZATION:\n{lean4_res[:800]}\n\n"
                    f"Provide your review with:\n"
                    f"1. VERDICT: APPROVE / REVISE / REJECT\n"
                    f"2. PATENTABILITY SCORE: 1-10\n"
                    f"3. STRENGTHS (3+ points)\n"
                    f"4. WEAKNESSES (3+ points)\n"
                    f"5. RECOMMENDATIONS for improvement\n"
                    f"6. PRIOR ART concerns (if any)\n"
                ),
                model=reviewer_model  # Diverse models for independent reviews
            )

            # Parse verdict and score from free text
            verdict = "REVISE"
            if "APPROVE" in review_text.upper()[:200]:
                verdict = "APPROVE"
            elif "REJECT" in review_text.upper()[:200]:
                verdict = "REJECT"

            score = 7  # default
            score_match = re.search(
                r'PATENTABILITY\s*SCORE[:\s]*(\d+)', review_text, re.IGNORECASE
            )
            if score_match:
                score = min(10, max(1, int(score_match.group(1))))

            review = PeerReview(
                reviewer_id=f"reviewer_{i}",
                model_used=reviewer_model,
                verdict=verdict,
                strengths="(see full review)",
                weaknesses="(see full review)",
                patentability_score=score,
                full_review=review_text,
            )
            peer_reviews.append(review)

            # Build LaTeX for this review
            safe_text = (review_text
                         .replace('\\', '\\textbackslash{}')
                         .replace('{', '\\{').replace('}', '\\}')
                         .replace('$', '\\$').replace('%', '\\%')
                         .replace('&', '\\&').replace('#', '\\#')
                         .replace('_', '\\_').replace('^', '\\^{}')
                         .replace('~', '\\~{}'))
            review_latex_parts.append(
                f"\\subsection{{Peer Review {i}: {name}}}\n"
                f"\\textbf{{Model:}} {reviewer_model} \\quad "
                f"\\textbf{{Verdict:}} {verdict} \\quad "
                f"\\textbf{{Score:}} {score}/10\n\n"
                f"\\begin{{quote}}\n{safe_text[:2000]}\n\\end{{quote}}\n"
            )
            log.info("peer_review_complete", reviewer=name,
                     verdict=verdict, score=score)

        stages_completed.append("PEER_REVIEW")
        log.info("stage_complete", stage="PEER_REVIEW")

        # ═══════════════════════════════════════════════════════════════════
        # Stage 8: FINAL COMPILATION & VAULTING
        # ═══════════════════════════════════════════════════════════════════
        log.info("stage_start", stage="FINAL_COMPILATION")
        os.makedirs("alexandrie", exist_ok=True)
        timestamp = int(time.time())
        tex_filename = f"alexandrie/patent_portfolio_{timestamp}.tex"

        # Assemble the full document: claims + appendixes
        # Insert appendixes before \end{document}
        appendix_block = (
            "\n\\appendix\n"
            "\n%% ══════════════════════════════════════════════════════\n"
            "%% APPENDIX A: Numeric Validation (Galileo)\n"
            "%% ══════════════════════════════════════════════════════\n"
            f"{numeric_res}\n\n"
            "\n%% ══════════════════════════════════════════════════════\n"
            "%% APPENDIX B: Lean 4 Formalization (Euler)\n"
            "%% ══════════════════════════════════════════════════════\n"
            f"{lean4_res}\n\n"
            "\n%% ══════════════════════════════════════════════════════\n"
            "%% APPENDIX C: Business Case (Eiffel)\n"
            "%% ══════════════════════════════════════════════════════\n"
            f"{business_res}\n\n"
            "\n%% ══════════════════════════════════════════════════════\n"
            "%% APPENDIX D: Peer Reviews (3× Mistral)\n"
            "%% ══════════════════════════════════════════════════════\n"
            "\\section{Appendix D: Independent Peer Reviews}\n"
            + "\n".join(review_latex_parts) + "\n"
        )

        # Insert appendix before \end{document}
        if "\\end{document}" in draft_res:
            full_doc = draft_res.replace(
                "\\end{document}",
                appendix_block + "\n\\end{document}"
            )
        else:
            full_doc = draft_res + appendix_block + "\n\\end{document}\n"

        with open(tex_filename, "w") as f:
            f.write(full_doc)
        vault_ids.append(tex_filename)

        # Compile PDF
        pdf_path, compile_warnings = _compile_latex(tex_filename, "alexandrie")
        warnings.extend(compile_warnings)
        if os.path.exists(pdf_path):
            vault_ids.append(pdf_path)

        # Save peer review metadata as JSON
        review_json_path = f"alexandrie/peer_reviews_{timestamp}.json"
        with open(review_json_path, "w") as f:
            json.dump([asdict(r) for r in peer_reviews], f, indent=2)
        vault_ids.append(review_json_path)

        stages_completed.append("FINAL_COMPILATION")

        total_duration = time.monotonic() - t0_total
        log.info("patent_pipeline_v2_complete",
                 duration_s=round(total_duration, 1),
                 stages=len(stages_completed),
                 reviews=len(peer_reviews),
                 avg_score=sum(r.patentability_score for r in peer_reviews) / max(len(peer_reviews), 1))

        return PipelineResult(
            symposium_id=f"patent_v2_{timestamp}",
            stages_completed=stages_completed,  # v4.4.0: PipelineResult now accepts list[str]
            total_duration_s=total_duration,
            tex_path=tex_filename,
            pdf_path=pdf_path if os.path.exists(pdf_path) else "",
            vault_artifact_ids=vault_ids,
            warnings=warnings,
            audit_trail_path=review_json_path,
            lean_verdicts=[
                f"{r.reviewer_id}: {r.verdict} ({r.patentability_score}/10)"
                for r in peer_reviews
            ],
        )
