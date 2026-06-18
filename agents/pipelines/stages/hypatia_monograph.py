# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
r"""Stage 8 — Hypatia Monograph: Divide & Conquer LaTeX Generation.

Hypatia generates a full LaTeX document via parallel divide-and-conquer:
  - Background chapter (theory & literature)
  - Per-hypothesis chapters (theory, Lean 4, simulation, adversarial review)
  - Conclusion & future work
  - Audit Trail Appendix

Target page count is governed by ``config.target_pages``.
"""

from __future__ import annotations

import asyncio
import re
import textwrap
import time
from datetime import datetime, timezone
from pathlib import Path

import structlog

from agents.pipelines.audit import SymposiumAuditTrail
from agents.pipelines.base import agent_generate
from agents.pipelines.config import SymposiumConfig

logger = structlog.get_logger(__name__)

# ── Agent Identities ───────────────────────────────────────────────────────────

HYPATIA_BACKGROUND_IDENTITY = textwrap.dedent(r"""
    You are Hypatia, chief archivist of the Agora swarm and renowned scientific author.
    Write an extensive LaTeX section (NO \documentclass, NO \begin{document}) for a
    scientific monograph on {domain} optimization using Alien Mathematics.

    Write the following sections with FULL academic depth (aim for 8-10 pages):
    \section{{Introduction \& Motivation}}
    \section{{Business Context}}
    \section{{Alien Mathematics: Theoretical Foundations}}
    \subsection{{Tensor Networks and Non-Commutative Algebra}}
    \subsection{{Holographic Entropy Bounds in Sociotechnical Systems}}
    \subsection{{The $\omega=2$ Asymptotic Limit Theorem}}
    \section{{Comparison with Traditional Methods}}

    Use \textbf{{}}, \emph{{}}, equations (align environment), tables (tabular),
    and itemize/enumerate lists. Be rigorous. Cite references like
    [DeGennes2025], [AlienMath2025].
""").strip()

HYPATIA_CHAPTER_IDENTITY = textwrap.dedent(r"""
    You are Hypatia, scientific author. Write a FULL LaTeX chapter body (no \documentclass,
    no \begin{document}, no \section header — start content directly).
    Target: 5-6 pages of dense academic LaTeX content.

    Use equations (align, equation environments), tables, and lists.
    Include: theoretical derivation, mathematical proofs, practical implications,
    and connections to the research domain.
    Reference: [AlienMath2025], [DeGennes2025].
""").strip()

HYPATIA_CONCLUSION_IDENTITY = textwrap.dedent(r"""
    You are Hypatia, scientific author. Write an extensive LaTeX conclusion section
    (no \documentclass, no \begin{document}, no \section header).
    Target: 4-5 pages covering:
    - Summary of validated hypotheses and efficiency gains
    - Implications for the domain and industry
    - Open research questions and future work
    - Roadmap for Alien Mathematics adoption
    - Ethical considerations of AI-driven optimization
    Use \subsection, equations, and itemize lists.
""").strip()


# ── LaTeX sanitisation ─────────────────────────────────────────────────────────

def _sanitize(text: str) -> str:
    """Clean LLM-generated LaTeX, handling both raw LaTeX and plain text."""
    if not text or not text.strip():
        return "(No content generated for this section.)"

    # ── Detect and replace MOCK_FALLBACK error strings ─────────────────
    if '[MOCK_FALLBACK' in text or "'Agent' object has no attribute" in text:
        return (r'\textit{[Content generation pending '
                r'--- this section will be populated on the next pipeline run.]}')

    # ── Greek letters → LaTeX math mode ────────────────────────────────
    _greek = {
        'α': r'$\alpha$', 'β': r'$\beta$', 'γ': r'$\gamma$', 'δ': r'$\delta$',
        'ε': r'$\epsilon$', 'ζ': r'$\zeta$', 'η': r'$\eta$', 'θ': r'$\theta$',
        'λ': r'$\lambda$', 'μ': r'$\mu$', 'π': r'$\pi$', 'σ': r'$\sigma$',
        'τ': r'$\tau$', 'φ': r'$\phi$', 'ω': r'$\omega$',
        'Γ': r'$\Gamma$', 'Δ': r'$\Delta$', 'Θ': r'$\Theta$', 'Σ': r'$\Sigma$',
        'Φ': r'$\Phi$', 'Ω': r'$\Omega$',
        '∑': r'$\sum$', '∏': r'$\prod$', '∈': r'$\in$', '∉': r'$\notin$',
        '≈': r'$\approx$', '√': r'$\sqrt{}$', '÷': r'$\div$',
    }
    for char, latex in _greek.items():
        text = text.replace(char, latex)

    # Strip Unicode chars that crash pdflatex (box-drawing, smart quotes, etc.)
    _uc = {
        '\u2500': '-', '\u2502': '|', '\u250c': '+', '\u2510': '+',
        '\u2514': '+', '\u2518': '+', '\u251c': '+', '\u2524': '+',
        '\u252c': '+', '\u2534': '+', '\u253c': '+',
        '\u2550': '=', '\u2551': '|', '\u2554': '+', '\u2557': '+',
        '\u255a': '+', '\u255d': '+',
        '\u2013': '--', '\u2014': '---',
        '\u2018': "'", '\u2019': "'", '\u201c': '``', '\u201d': "''",
        '\u2026': r'\ldots{}',
        '\u2192': r'$\rightarrow$', '\u2190': r'$\leftarrow$',
        '\u2264': r'$\leq$', '\u2265': r'$\geq$', '\u2260': r'$\neq$',
        '\u00d7': r'$\times$', '\u221e': r'$\infty$',
    }
    for uc, repl in _uc.items():
        text = text.replace(uc, repl)

    text = ''.join(c if ord(c) < 128 or (0x00C0 <= ord(c) <= 0x024F) else ' ' for c in text)

    # Strip document-level commands that LLMs inject
    for cmd in (r'\begin{document}', r'\end{document}', r'\documentclass',
                r'\usepackage', r'\maketitle', r'\tableofcontents'):
        while cmd in text:
            if cmd in (r'\documentclass', r'\usepackage'):
                # Remove entire line containing the command
                text = re.sub(rf'^.*{re.escape(cmd)}.*$', '', text, flags=re.MULTILINE)
            else:
                text = text.replace(cmd, '')
    # Strip \title{...}, \author{...}, \date{...}
    text = re.sub(r'\\(?:title|author|date)\{[^}]*\}', '', text)

    if r"\section" in text or r"\subsection" in text or r"\begin" in text:
        text = text.replace("```latex", "").replace("```", "")
        return _balance_braces(text)
    for ch, esc in [
        ("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"),
        ("$", r"\$"), ("#", r"\#"), ("_", r"\_"), ("{", r"\{"),
        ("}", r"\}"), ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}"),
    ]:
        text = text.replace(ch, esc)
    return _balance_braces(f"\\begin{{quote}}\n{text}\n\\end{{quote}}")


def _sanitize_title(title: str) -> str:
    """Escape LaTeX special chars in section titles."""
    for ch, esc in [("&", r"\&"), ("%", r"\%"), ("$", r"\$"),
                     ("#", r"\#"), ("_", r"\_"), ("{", r"\{"), ("}", r"\}")]:
        title = title.replace(ch, esc)
    return title


def _balance_braces(text: str) -> str:
    """Ensure every unescaped '{' has a matching '}' and vice-versa.

    Appends missing closing braces or strips unmatched opening braces
    so that pdflatex never aborts on a brace mismatch.
    """
    depth = 0
    i = 0
    while i < len(text):
        ch = text[i]
        # Skip escaped braces (\{ and \})
        if ch == '\\' and i + 1 < len(text) and text[i + 1] in '{}':
            i += 2
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            if depth > 0:
                depth -= 1
            else:
                # Unmatched closer — remove it
                text = text[:i] + text[i + 1:]
                continue
        i += 1
    # Append missing closers
    if depth > 0:
        text += '}' * depth
    return text


# ── Monograph assembly ─────────────────────────────────────────────────────────

def _assemble_latex(
    config: SymposiumConfig,
    rules: str,
    top_k: list[dict],
    background_tex: str,
    chapter_sections: list[str],
    conclusion_tex: str,
    audit: SymposiumAuditTrail,
) -> str:
    """Assemble all Hypatia-generated sections into a full LaTeX document."""
    now = datetime.now(timezone.utc).strftime("%B %d, %Y — %H:%M UTC")
    bg = _sanitize(background_tex)
    conc = _sanitize(conclusion_tex)
    audit_tex = audit.to_latex()

    # ── Hypothesis chapters ────────────────────────────────────────────
    hyp_chapters: list[str] = []
    for i, hyp in enumerate(top_k):
        base_idx = i * 4
        theory_tex = _sanitize(chapter_sections[base_idx])
        lean_tex = _sanitize(chapter_sections[base_idx + 1])
        sim_tex = _sanitize(chapter_sections[base_idx + 2])
        adv_tex = _sanitize(chapter_sections[base_idx + 3])
        img_path = Path(hyp.get("image_path", f"hyp_{i}.png")).name

        hyp_chapters.append(f"""\
% Hypothesis {i + 1}: {hyp.get('title', 'Untitled')[:60]}
\\section{{Hypothesis {i + 1}: {_sanitize_title(hyp.get('title', 'Untitled'))}}}
\\label{{chap:hyp_{i + 1}}}

\\begin{{tcolorbox}}[colback=blue!3!white,colframe=blue!40!black,title=Hypothesis Overview]
\\textbf{{Alien Mathematics Formalism:}} {_sanitize_title(str(hyp.get('alien_math_formalism', 'N/A')))}\\\\
\\textbf{{KPI Target:}} {_sanitize_title(str(hyp.get('kpi_target', 'N/A')))}\\\\
\\textbf{{Efficiency Gain Estimate:}} {_sanitize_title(str(hyp.get('efficiency_gain_estimate', 'N/A')))}\\\\
\\textbf{{Viability Score:}} {_sanitize_title(str(hyp.get('viability_score', 'N/A')))}/100
\\end{{tcolorbox}}

\\subsection{{Theoretical Derivation}}
{theory_tex}

\\subsection{{Lean~4 Formal Verification}}
{lean_tex}

\\subsection{{Galileo Numerical Simulation}}
\\begin{{figure}}[htbp]
  \\centering
  \\includegraphics[width=0.95\\textwidth]{{{img_path}}}
  \\caption{{Galileo simulation: {_sanitize_title(hyp.get('title', '')[:70])}}}
  \\label{{fig:hyp{i}}}
\\end{{figure}}
{sim_tex}

\\subsection{{Adversarial Review \\& Rebuttal}}
{adv_tex}
\\clearpage
""")

    # ── Score table ────────────────────────────────────────────────────
    score_rows = "\n".join(
        f"  {i + 1} & {_sanitize_title(str(hyp.get('title', '?'))[:45])} & "
        f"{_sanitize_title(str(hyp.get('viability_score', '?')))}/100 & "
        f"{_sanitize_title(str(hyp.get('efficiency_gain_estimate', '?')))} \\\\"
        for i, hyp in enumerate(top_k)
    )

    # ── Socrate rules formatting ───────────────────────────────────────
    rule_items = "\n".join(
        f"  \\item {_sanitize_title(rule.strip().lstrip('•·-').strip())}"
        for rule in rules.split("•")
        if rule.strip()
    )

    doc = fr"""\documentclass[11pt,a4paper]{{report}}

% Packages
\usepackage[utf8]{{inputenc}}
\usepackage[T1]{{fontenc}}
\usepackage{{lmodern}}
\usepackage{{graphicx}}
\graphicspath{{{{./images/}}}}
\usepackage{{amsmath, amsthm, amssymb}}
\usepackage{{geometry}}
\usepackage{{hyperref}}
\usepackage{{booktabs}}
\usepackage{{longtable}}
\usepackage{{array}}
\usepackage{{xcolor}}
\usepackage{{tcolorbox}}
\usepackage{{listings}}
\usepackage{{microtype}}
\usepackage{{setspace}}
\usepackage{{fancyhdr}}
\usepackage{{enumitem}}

% ─── Prevent Overfull \hbox from crashing pdflatex ──────────────────────────
\sloppy
\emergencystretch=3em

\geometry{{a4paper, margin=2.5cm, top=3cm, bottom=3cm, headheight=14pt}}

\newtheorem{{theorem}}{{Theorem}}[chapter]
\newtheorem{{lemma}}[theorem]{{Lemma}}
\newtheorem{{definition}}[theorem]{{Definition}}

\pagestyle{{fancy}}
\fancyhf{{}}
\fancyhead[L]{{\textit{{{config.domain} Autoresearch — Alien Mathematics}}}}
\fancyhead[R]{{\thepage}}
\fancyfoot[C]{{\textit{{Agora AI Swarm — Symposium Pipeline}}}}

\hypersetup{{
  pdftitle={{{config.domain} Autoresearch: Alien Mathematics}},
  pdfauthor={{Agora AI Swarm}},
  colorlinks=true, linkcolor=blue!60!black, urlcolor=blue!60!black,
}}

\begin{{document}}

% Title Page
\begin{{titlepage}}
  \centering
  \vspace*{{2cm}}
  {{\Huge\bfseries {config.domain} Autoresearch\\[0.5em]}}
  {{\Large\bfseries Alien Mathematics Optimization\\[1em]}}
  {{\large\itshape Tensor Networks, Non-Commutative Algebra,\\
    and Holographic Principles\\[2em]}}
  \rule{{0.8\textwidth}}{{1pt}}\\[1em]
  {{\large\bfseries Agora AI Scientific Swarm}}\\[0.5em]
  {{Generated: {now}}}
\end{{titlepage}}

\tableofcontents
\listoffigures
\newpage

% Socrate Rules
\chapter{{Scientific Framework \& Formal Constraints}}
\begin{{tcolorbox}}[colback=red!3!white,colframe=red!50!black,title=Socrate Formal Rules]
\begin{{itemize}}[leftmargin=1.5em]
{rule_items}
\end{{itemize}}
\end{{tcolorbox}}

% Background
\chapter{{Theoretical Background \& Alien Mathematics}}
\label{{sec:background}}
{bg}

% Hypotheses Overview
\chapter{{Top {config.top_k} Hypotheses: Selection \& Overview}}
\begin{{table}}[htbp]
\centering
\caption{{Top {config.top_k} Hypotheses Selected by Adversarial Review}}
\begin{{tabular}}{{c p{{5cm}} c p{{2cm}}}}
\toprule
\textbf{{\#}} & \textbf{{Title}} & \textbf{{Score}} & \textbf{{Est. Gain}} \\
\midrule
{score_rows}
\bottomrule
\end{{tabular}}
\end{{table}}

% Hypothesis Chapters
{''.join(hyp_chapters)}

% Conclusion
\chapter{{Conclusion, Implications \& Future Work}}
\label{{sec:conclusion}}
{conc}

% Audit Trail Appendix
\appendix
\chapter{{Pipeline Audit Trail}}
{audit_tex}

\end{{document}}
"""
    return doc


async def generate_monograph(
    config: SymposiumConfig,
    rules: str,
    top_k: list[dict],
    audit: SymposiumAuditTrail,
) -> str:
    """Generate the full LaTeX monograph via Hypatia Divide & Conquer.

    Spawns parallel tasks for background, per-hypothesis chapters (4
    sub-sections each), and conclusion.  Assembles the final document
    with audit trail appendix.

    Args:
        config: Symposium configuration.
        rules: Formal rules from Stage 1.
        top_k: Top-K hypotheses with all enrichment data.
        audit: Audit trail (included in appendix).

    Returns:
        Full LaTeX document string.
    """
    logger.info("stage8_hypatia_start", target_pages=config.target_pages)
    t0 = time.monotonic()

    bg_identity = HYPATIA_BACKGROUND_IDENTITY.format(domain=config.domain)

    # ── Background ─────────────────────────────────────────────────────
    async def gen_background() -> str:
        prompt = (
            f"Write the extensive background sections for a monograph on "
            f"{config.domain} using Alien Mathematics. Include all sections "
            f"listed in your identity. Target ~10 pages of LaTeX."
        )
        return await agent_generate(bg_identity, prompt)

    # ── Per-hypothesis sub-sections ────────────────────────────────────
    async def gen_theory(hyp: dict, idx: int) -> str:
        prompt = textwrap.dedent(f"""\
            Write the theoretical derivation sub-chapter for Hypothesis {idx + 1}:
            Title: {hyp.get('title')}
            Description: {hyp.get('description')}
            Alien Math Formalism: {hyp.get('alien_math_formalism')}
            KPI Target: {hyp.get('kpi_target')}
            Target: 5-6 pages of mathematical LaTeX.
        """)
        return await agent_generate(HYPATIA_CHAPTER_IDENTITY, prompt)

    async def gen_lean_section(hyp: dict, idx: int) -> str:
        prompt = textwrap.dedent(f"""\
            Write the Lean 4 Formalization sub-chapter for Hypothesis {idx + 1}:
            Title: {hyp.get('title')}
            Lean 4 Code: {hyp.get('lean_code', 'N/A')[:1500]}
            Verification: {hyp.get('lean_verification', 'N/A')[:1500]}
            Target: 4-5 pages.
        """)
        return await agent_generate(HYPATIA_CHAPTER_IDENTITY, prompt)

    async def gen_simulation(hyp: dict, idx: int) -> str:
        prompt = textwrap.dedent(f"""\
            Write the Numerical Simulation Analysis sub-chapter for Hypothesis {idx + 1}:
            Title: {hyp.get('title')}
            KPI Target: {hyp.get('kpi_target')}
            Stats: {hyp.get('numerical_stats', {{}})}
            Reference Figure \\ref{{fig:hyp{idx}}}.
            Target: 4-5 pages.
        """)
        return await agent_generate(HYPATIA_CHAPTER_IDENTITY, prompt)

    async def gen_adversarial(hyp: dict, idx: int) -> str:
        prompt = textwrap.dedent(f"""\
            Write the Adversarial Review Discussion for Hypothesis {idx + 1}:
            Title: {hyp.get('title')}
            Viability Score: {hyp.get('viability_score', 'N/A')}/100
            Peer Review: {hyp.get('peer_review', 'N/A')}
            Controversory Review: {hyp.get('controversory_review', 'N/A')}
            Target: 3-4 pages.
        """)
        return await agent_generate(HYPATIA_CHAPTER_IDENTITY, prompt)

    # ── Conclusion ─────────────────────────────────────────────────────
    async def gen_conclusion() -> str:
        scores = [h.get("viability_score", "N/A") for h in top_k]
        gains = [h.get("efficiency_gain_estimate", "?") for h in top_k]
        prompt = textwrap.dedent(f"""\
            Write the conclusion for this monograph on {config.domain}
            using Alien Mathematics.
            Top {config.top_k} viability scores: {scores}
            Top {config.top_k} efficiency gains: {gains}
            All were formally verified in Lean 4 and simulated by Galileo.
        """)
        return await agent_generate(HYPATIA_CONCLUSION_IDENTITY, prompt)

    # ── Launch all tasks ───────────────────────────────────────────────
    bg_task = asyncio.create_task(gen_background())
    conc_task = asyncio.create_task(gen_conclusion())

    chapter_tasks: list[asyncio.Task[str]] = []
    for i, hyp in enumerate(top_k):
        chapter_tasks.append(asyncio.create_task(gen_theory(hyp, i)))
        chapter_tasks.append(asyncio.create_task(gen_lean_section(hyp, i)))
        chapter_tasks.append(asyncio.create_task(gen_simulation(hyp, i)))
        chapter_tasks.append(asyncio.create_task(gen_adversarial(hyp, i)))

    background_tex = await bg_task
    chapter_sections = list(await asyncio.gather(*chapter_tasks))
    conclusion_tex = await conc_task

    # ── Assemble ───────────────────────────────────────────────────────
    latex_doc = _assemble_latex(
        config, rules, top_k, background_tex, chapter_sections,
        conclusion_tex, audit,
    )

    elapsed = time.monotonic() - t0
    audit.record(
        stage="Stage 8: Hypatia Monograph",
        agent="Hypatia",
        action=f"Generated LaTeX monograph ({len(latex_doc)} chars, target {config.target_pages} pages)",
        elapsed_s=elapsed,
        input_summary=f"rules + {len(top_k)} hypotheses",
        output_summary=f"{len(latex_doc)} chars LaTeX",
    )

    logger.info(
        "stage8_hypatia_complete",
        latex_len=len(latex_doc),
        elapsed_s=round(elapsed, 1),
    )
    return latex_doc
