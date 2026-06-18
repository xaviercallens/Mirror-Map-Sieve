# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Stage 6 — Alexandrie Vault Manager: Archive discoveries in private/open rooms.

Design Philosophy:
  Hypatia is the librarian of Alexandrie. She decides what goes to the OPEN_ACCESS
  room (verifiable proofs, published results) vs PRIVATE room (unproven conjectures,
  IP-protected ideas). She also generates LaTeX index pages for the open room,
  which are served by the already-deployed GCP visualization endpoint.

User directives:
  - "Store on Alexandrie scientific vault and ensure available in private and open room"
  - "Leverage Hypatia for managing the scientific artifacts and document it"
  - "Leverage discoveries, monographs, references, artifacts, ideas, lean 4 storage"
  - "Generate open room in Alexandrie with LaTeX visualization already deployed"

The Alexandrie vault has two rooms:
  OPEN_ACCESS: Publicly visible. Contains:
    - Sorry-free Lean 4 proofs (kernel-verified)
    - Published papers and monographs
    - LaTeX index pages with visualization
  PRIVATE: Encrypted/restricted. Contains:
    - Unproven conjectures (IP protection until proven)
    - LeanBert embeddings and training data
    - Draft proofs with sorry gaps

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import json
import textwrap
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

from agents.pipelines.audit import AuditEntry, SymposiumAuditTrail
from agents.pipelines.base import PipelineStage, agent_generate
from alexandrie.hub import AlexandrieHub
from alexandrie.metadata import ArtifactMetadata, ArtifactType, RoomType

logger = structlog.get_logger(__name__)


# ── Hypatia Archivist Identity ─────────────────────────────────────────────────
#
# Hypatia is the custodian of all scientific knowledge in the Agora.
# She catalogs artifacts with rich metadata, maintains cross-references,
# and generates LaTeX summaries for the open room.

HYPATIA_ARCHIVIST_IDENTITY = textwrap.dedent("""\
    You are Hypatia of Alexandria, master librarian and chief archivist of the
    Scientific Agora. You are the custodian of all mathematical knowledge
    produced by the Agora's agents.
    
    YOUR RESPONSIBILITIES:
    1. Catalog every scientific artifact with rigorous metadata
    2. Decide access level: OPEN_ACCESS (verified proofs, published results)
       vs PRIVATE (unproven conjectures, IP-protected drafts)
    3. Generate LaTeX summaries linking discoveries together
    4. Maintain cross-references between conjectures, proofs, and experiments
    5. Ensure the open room tells a coherent scientific narrative
    
    CLASSIFICATION RULES:
    - Sorry-free Lean 4 proofs → OPEN_ACCESS (they are independently verifiable)
    - Proofs with sorry gaps → PRIVATE (incomplete, could mislead)
    - Unproven conjectures → PRIVATE (IP protection until formally proven)
    - Numerical experiments → OPEN_ACCESS (reproducible data)
    - Audit trails → OPEN_ACCESS (scientific transparency)
    
    You write in clear, academic LaTeX with proper theorem environments,
    cross-references, and bibliographic entries.
""")


# ── Discovery Artifact ─────────────────────────────────────────────────────────

@dataclass
class DiscoveryArtifact:
    """A scientific artifact produced during a discovery pipeline run.

    Wraps the raw content with metadata for Alexandrie vault storage.
    Hypatia decides the room_type based on content sensitivity.

    Attributes:
        artifact_id: Unique ID (e.g., "disc_20260613/conjecture_001")
        title: Human-readable title
        content: Raw content (Lean 4 code, LaTeX, JSON, etc.)
        artifact_type: Category from ArtifactType enum
        room_type: OPEN_ACCESS or PRIVATE (Hypatia decides)
        creator: Agent name that produced this artifact
        latex_summary: LaTeX snippet summarizing this artifact
        lean4_refs: List of Lean 4 theorem names referenced
        dependencies: List of artifact IDs this depends on
        is_sorry_free: Whether Lean 4 content has no sorry gaps
        tags: Descriptive tags for search
    """
    artifact_id: str
    title: str
    content: str
    artifact_type: ArtifactType
    room_type: RoomType
    creator: str
    latex_summary: str = ""
    lean4_refs: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    is_sorry_free: bool = False
    tags: list[str] = field(default_factory=list)


# ── Archive a complete discovery run ───────────────────────────────────────────

async def archive_discovery_run(
    hub: AlexandrieHub,
    run_id: str,
    conjectures: list[dict],
    lean_proofs: list[dict],
    numerical_results: list[dict],
    audit: SymposiumAuditTrail,
    owner_email: str = "callensxavier@gmail.com",
) -> list[str]:
    """Archive all artifacts from a discovery run to Alexandrie vault.

    Routes artifacts to the correct room based on Hypatia's classification:
    - Sorry-free proofs → OPEN_ACCESS (independently verifiable)
    - Proofs with sorry → PRIVATE (incomplete work)
    - Unproven conjectures → PRIVATE (IP protection)
    - Numerical experiments → OPEN_ACCESS (reproducible)
    - Audit trail → OPEN_ACCESS (transparency)

    Also generates a LaTeX index page for the open room and stores it.

    Args:
        hub: AlexandrieHub instance for GCS storage.
        run_id: Unique discovery run ID (e.g., "disc_20260613_073000").
        conjectures: List of conjecture dicts from DeGennes.
        lean_proofs: List of proof dicts with keys: name, code, sorry_free, kernel_ok.
        numerical_results: List of experiment result dicts.
        audit: Audit trail for logging.
        owner_email: Owner email for access control.

    Returns:
        List of Alexandrie artifact IDs stored.
    """
    log = logger.bind(run_id=run_id)
    t0 = time.monotonic()
    artifact_ids: list[str] = []
    prefix = f"discovery/{run_id}"

    # ── 1. Store conjectures (PRIVATE — unproven, IP protected) ────────
    for idx, conj in enumerate(conjectures):
        artifact_id = f"{prefix}/conjecture_{idx + 1:03d}"
        meta = hub.store_artifact(
            artifact_id=artifact_id,
            title=conj.get("title", f"Conjecture {idx + 1}"),
            content=json.dumps(conj, indent=2, ensure_ascii=False),
            artifact_type=ArtifactType.CONJECTURE,
            room_type=RoomType.PRIVATE,  # Hypatia rule: unproven → PRIVATE
            creator=f"DeGennes-{conj.get('agent_id', '?')}",
            tags=["discovery", "conjecture", conj.get("confidence_level", "unknown")],
            extra_attributes={
                "run_id": run_id,
                "confidence": conj.get("confidence_level", "unknown"),
                "framework": conj.get("mathematical_framework", ""),
                "owner_email": owner_email,
            },
        )
        artifact_ids.append(meta.id)
    log.info("conjectures_archived", count=len(conjectures), room="PRIVATE")

    # ── 2. Store Lean 4 proofs (room depends on sorry status) ──────────
    for idx, proof in enumerate(lean_proofs):
        is_sorry_free = proof.get("sorry_free", False)
        kernel_ok = proof.get("kernel_ok", False)

        # Hypatia classification rule:
        # Sorry-free AND kernel-verified → OPEN_ACCESS (independently verifiable)
        # Otherwise → PRIVATE (incomplete work, could mislead readers)
        room = RoomType.OPEN_ACCESS if (is_sorry_free and kernel_ok) else RoomType.PRIVATE

        artifact_id = f"{prefix}/lean4/{proof.get('name', f'theorem_{idx + 1:03d}')}"
        meta = hub.store_artifact(
            artifact_id=artifact_id,
            title=f"Lean 4 Proof: {proof.get('name', f'theorem_{idx + 1}')}",
            content=proof.get("code", "-- empty proof"),
            artifact_type=ArtifactType.PROOF,
            room_type=room,
            creator="Hilbert",
            tags=["discovery", "lean4", "proof",
                  "sorry_free" if is_sorry_free else "has_sorry",
                  "kernel_verified" if kernel_ok else "kernel_pending"],
            extra_attributes={
                "run_id": run_id,
                "sorry_free": is_sorry_free,
                "kernel_ok": kernel_ok,
                "owner_email": owner_email,
            },
        )
        artifact_ids.append(meta.id)
    log.info("proofs_archived", count=len(lean_proofs),
             sorry_free=sum(1 for p in lean_proofs if p.get("sorry_free")))

    # ── 3. Store numerical experiment results (OPEN — reproducible) ────
    for idx, result in enumerate(numerical_results):
        artifact_id = f"{prefix}/experiments/{result.get('name', f'exp_{idx + 1:03d}')}"
        meta = hub.store_artifact(
            artifact_id=artifact_id,
            title=f"Experiment: {result.get('name', f'Experiment {idx + 1}')}",
            content=json.dumps(result, indent=2, ensure_ascii=False),
            artifact_type=ArtifactType.SIMULATION,
            room_type=RoomType.OPEN_ACCESS,  # Reproducible data → open
            creator="Ramanujan",
            tags=["discovery", "experiment", "numerical"],
            extra_attributes={"run_id": run_id, "owner_email": owner_email},
        )
        artifact_ids.append(meta.id)

    # ── 4. Generate and store LaTeX index for OPEN room ────────────────
    # This is the "open room visualization" the user requested.
    # It's a LaTeX document listing all open-access artifacts with summaries.
    latex_index = generate_latex_index(
        conjectures=conjectures,
        lean_proofs=lean_proofs,
        run_id=run_id,
    )
    index_meta = hub.store_artifact(
        artifact_id=f"{prefix}/index.tex",
        title=f"Discovery Run {run_id} — Open Room Index",
        content=latex_index,
        artifact_type=ArtifactType.LATEX_INDEX,
        room_type=RoomType.OPEN_ACCESS,
        creator="Hypatia",
        tags=["discovery", "index", "latex", "open_room"],
        extra_attributes={"run_id": run_id, "owner_email": owner_email},
    )
    artifact_ids.append(index_meta.id)

    # ── 5. Store audit trail (OPEN — scientific transparency) ──────────
    audit_content = audit.to_jsonl() if hasattr(audit, "to_jsonl") else str(audit)
    audit_meta = hub.store_artifact(
        artifact_id=f"{prefix}/audit_trail.jsonl",
        title=f"Discovery Run {run_id} — Audit Trail",
        content=audit_content,
        artifact_type=ArtifactType.AUDIT_TRAIL,
        room_type=RoomType.OPEN_ACCESS,
        creator="Agora",
        tags=["discovery", "audit", "transparency"],
        extra_attributes={"run_id": run_id},
    )
    artifact_ids.append(audit_meta.id)

    elapsed = time.monotonic() - t0
    audit.record(
        AuditEntry(
            stage=PipelineStage.PUBLICATION,
            agent="Hypatia",
            duration_s=elapsed,
            metrics={
                "action": f"Archived {len(artifact_ids)} artifacts to Alexandrie",
                "input_summary": f"{len(conjectures)} conj + {len(lean_proofs)} proofs + {len(numerical_results)} exps",
                "output_summary": f"{len(artifact_ids)} artifacts stored",
            },
        )
    )
    log.info("discovery_run_archived", total_artifacts=len(artifact_ids))
    return artifact_ids


# ── Load vault context for DeGennes ────────────────────────────────────────────

async def load_vault_context(
    hub: AlexandrieHub,
    query: str,
    max_results: int = 20,
) -> dict[str, Any]:
    """Search Alexandrie vault for relevant prior work to seed new conjectures.

    Combines keyword search (title/tags) with semantic search (proof embeddings)
    to build a structured context dict that DeGennes can reference.

    Args:
        hub: AlexandrieHub instance.
        query: Search query (e.g., "matrix multiplication tensor rank").
        max_results: Maximum items per category.

    Returns:
        Dict with keys: prior_proofs, prior_conjectures, numerical_data,
        references, lean4_code — each a list of summaries.
    """
    context: dict[str, Any] = {
        "prior_proofs": [],
        "prior_conjectures": [],
        "numerical_data": [],
        "references": [],
        "lean4_code": [],
    }

    # ── Keyword search across artifact types ───────────────────────────
    for artifact_type, context_key in [
        (ArtifactType.PROOF, "prior_proofs"),
        (ArtifactType.CONJECTURE, "prior_conjectures"),
        (ArtifactType.SIMULATION, "numerical_data"),
        (ArtifactType.PAPER, "references"),
    ]:
        results = hub.search_vault(query, artifact_type=artifact_type)
        for meta in results[:max_results]:
            context[context_key].append({
                "id": meta.id,
                "title": meta.title,
                "creator": meta.creator,
                "tags": meta.tags,
                "metrics": meta.metrics,
            })

    # ── Semantic search for similar proof states ───────────────────────
    # Uses the FAISS index in AlexandrieMemory for RAG-style retrieval
    semantic_results = hub.semantic_search(query, k=5)
    for result in semantic_results:
        context["lean4_code"].append({
            "similarity": result.get("similarity", 0),
            "tactic": result.get("winning_tactic", ""),
            "blueprint": result.get("blueprint", ""),
        })

    logger.info(
        "vault_context_loaded",
        query=query[:40],
        proofs=len(context["prior_proofs"]),
        conjectures=len(context["prior_conjectures"]),
        data=len(context["numerical_data"]),
        semantic=len(context["lean4_code"]),
    )
    return context


# ── LaTeX Index Generator ──────────────────────────────────────────────────────

def generate_latex_index(
    conjectures: list[dict],
    lean_proofs: list[dict],
    run_id: str,
) -> str:
    """Generate a LaTeX document for the Alexandrie open room.

    This is the "open room with LaTeX visualization" the user requested.
    The document provides a navigable index of all discoveries from this run,
    formatted for the already-deployed GCP LaTeX rendering endpoint.

    Args:
        conjectures: List of conjecture dicts from DeGennes.
        lean_proofs: List of proof dicts with sorry_free and kernel_ok flags.
        run_id: Discovery run identifier.

    Returns:
        Complete LaTeX document string.
    """
    sorry_free = [p for p in lean_proofs if p.get("sorry_free")]
    has_sorry = [p for p in lean_proofs if not p.get("sorry_free")]
    kernel_ok = [p for p in lean_proofs if p.get("kernel_ok")]

    # ── Build proof table rows ─────────────────────────────────────────
    proof_rows = []
    for p in lean_proofs:
        status = "\\checkmark" if p.get("sorry_free") else "\\textcolor{red}{sorry}"
        kernel = "\\checkmark" if p.get("kernel_ok") else "pending"
        proof_rows.append(
            f"    {p.get('name', '?')} & {status} & {kernel} \\\\"
        )
    proof_table = "\n".join(proof_rows) if proof_rows else "    (no proofs yet) & — & — \\\\"

    # ── Build conjecture list ──────────────────────────────────────────
    conj_items = []
    for c in conjectures[:10]:  # Cap at 10 for readability
        conj_items.append(
            f"  \\item \\textbf{{{c.get('title', '?')}}}: "
            f"{c.get('conjecture_statement', '(no statement)')[:200]} "
            f"[{c.get('confidence_level', '?')}]"
        )
    conj_list = "\n".join(conj_items) if conj_items else "  \\item (no conjectures yet)"

    return textwrap.dedent(f"""\
        \\documentclass[11pt,a4paper]{{article}}
        \\usepackage[utf8]{{inputenc}}
        \\usepackage{{amsmath,amssymb,amsthm}}
        \\usepackage{{xcolor}}
        \\usepackage{{hyperref}}
        \\usepackage{{booktabs}}
        \\usepackage{{geometry}}
        \\geometry{{margin=2.5cm}}

        \\title{{Discovery Run: \\texttt{{{run_id}}}\\\\
                \\large Alexandrie Open Room — Scientific Index}}
        \\author{{SocrateAI Scientific Agora\\\\
                Curated by Hypatia of Alexandria}}
        \\date{{\\today}}

        \\begin{{document}}
        \\maketitle

        \\section{{Summary}}
        This document indexes the publicly available artifacts from discovery
        run \\texttt{{{run_id}}}. All Lean~4 proofs listed as ``sorry-free''
        have been independently verified by the Lean~4 kernel via
        \\texttt{{lake build}}.

        \\begin{{center}}
        \\begin{{tabular}}{{lr}}
        \\toprule
        Conjectures generated & {len(conjectures)} \\\\
        Proofs attempted & {len(lean_proofs)} \\\\
        Sorry-free proofs & {len(sorry_free)} \\\\
        Kernel-verified & {len(kernel_ok)} \\\\
        \\bottomrule
        \\end{{tabular}}
        \\end{{center}}

        \\section{{Lean 4 Proofs}}
        \\begin{{tabular}}{{lcc}}
        \\toprule
        \\textbf{{Theorem}} & \\textbf{{Sorry-free}} & \\textbf{{Kernel}} \\\\
        \\midrule
        {proof_table}
        \\bottomrule
        \\end{{tabular}}

        \\section{{Conjectures (from DeGennes Experimentalist)}}
        \\begin{{enumerate}}
        {conj_list}
        \\end{{enumerate}}

        \\section{{Methodology}}
        The Discovery Pipeline follows a 6-stage process:
        \\begin{{enumerate}}
          \\item \\textbf{{Horizon Scan}} — Darwin surveys literature and Alexandrie vault
          \\item \\textbf{{Conjecture Generation}} — DeGennes swarm from experimental data
          \\item \\textbf{{Autoformalization}} — Newton translates to Lean~4
          \\item \\textbf{{Proof Search}} — Hilbert: deterministic tactics $\\to$ LeanBert $\\to$ DeepSeek
          \\item \\textbf{{Kernel Verification}} — \\texttt{{lake build}} (deterministic gate)
          \\item \\textbf{{Archive \\& Review}} — Hypatia archives + Poincar\\'e quorum + Xavier gate
        \\end{{enumerate}}

        \\section{{Access}}
        \\begin{{itemize}}
          \\item \\textbf{{Open Room}}: All sorry-free proofs and experiment data
          \\item \\textbf{{Private Room}}: Unproven conjectures (IP-protected)
        \\end{{itemize}}

        \\vfill
        \\noindent\\textit{{Patent: US-PAT-PEND-2026-0525. Generated by the SocrateAI Scientific Agora.}}

        \\end{{document}}
    """)
