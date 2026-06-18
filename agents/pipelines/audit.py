# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Symposium audit trail — structured, append-only execution log.

Every pipeline stage appends an :class:`AuditEntry` to the
:class:`SymposiumAuditTrail`.  The trail is serialisable to JSONL for
machine consumption and to LaTeX for inclusion in the Hypatia monograph
appendix.  Entries record SHA-256 hashes, Socrate verdicts, Lean 4
sorry/axiom counts, cost, and per-stage timing.

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import structlog

from agents.pipelines.base import PipelineStage
from alexandrie.hub import AlexandrieHub
from alexandrie.metadata import ArtifactType, RoomType

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Socrate Verdict Enum
# ---------------------------------------------------------------------------

class SocrateVerdict(str, Enum):
    """Outcome of a Socrate dialectical validation on a stage output."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


# ---------------------------------------------------------------------------
# Audit Entry
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class AuditEntry:
    """Single audit record for one pipeline stage or sub-step.

    Attributes:
        stage: The :class:`PipelineStage` this entry corresponds to.
        timestamp: ISO-8601 UTC timestamp (auto-set at creation).
        agent: Agent identity that produced the output.
        input_sha256: SHA-256 hex digest of the stage input payload.
        output_sha256: SHA-256 hex digest of the stage output payload.
        socrate_verdict: Socrate validation outcome (PASS / WARN / FAIL).
        socrate_violations: List of Socrate rule violations found.
        duration_s: Wall-clock time for this stage in seconds.
        cost_usd: Estimated LLM / compute cost in USD.
        warnings: Non-fatal issues encountered.
        metrics: Arbitrary key-value metrics (scores, token counts, etc.).
        lean_sorry_count: Number of ``sorry`` placeholders in Lean 4 output.
        lean_axiom_count: Number of custom axioms declared in Lean 4 output.
        entry_id: Unique entry identifier (auto-generated).
    """

    stage: PipelineStage
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    agent: str = ""
    input_sha256: str = ""
    output_sha256: str = ""
    socrate_verdict: SocrateVerdict = SocrateVerdict.PASS
    socrate_violations: list[str] = field(default_factory=list)
    duration_s: float = 0.0
    cost_usd: float = 0.0
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    lean_sorry_count: int = 0
    lean_axiom_count: int = 0
    entry_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    # ── Convenience helpers ──────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        return {
            "entry_id": self.entry_id,
            "stage": self.stage.name,
            "stage_order": self.stage.value,
            "timestamp": self.timestamp,
            "agent": self.agent,
            "input_sha256": self.input_sha256,
            "output_sha256": self.output_sha256,
            "socrate_verdict": self.socrate_verdict.value,
            "socrate_violations": self.socrate_violations,
            "duration_s": round(self.duration_s, 3),
            "cost_usd": round(self.cost_usd, 6),
            "warnings": self.warnings,
            "metrics": self.metrics,
            "lean_sorry_count": self.lean_sorry_count,
            "lean_axiom_count": self.lean_axiom_count,
        }


# ---------------------------------------------------------------------------
# Convenience: compute SHA-256 for audit hashing
# ---------------------------------------------------------------------------

def _sha256(data: str | bytes) -> str:
    """Compute SHA-256 hex digest of the given data.

    Args:
        data: Input string or bytes to hash.

    Returns:
        Lowercase hex digest string.
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Audit Trail
# ---------------------------------------------------------------------------

class SymposiumAuditTrail:
    """Append-only, structured audit log for a Symposium pipeline run.

    Provides methods to record entries, serialise to JSONL (one entry
    per line), upload to the Alexandrie Vault, and render a LaTeX
    appendix for inclusion in the final monograph.

    Usage::

        trail = SymposiumAuditTrail(symposium_id="SYM-ABC123")

        trail.record(AuditEntry(
            stage=PipelineStage.HYPOTHESIS_GENERATION,
            agent="DeGennes-1",
            input_sha256=_sha256(prompt),
            output_sha256=_sha256(response),
            duration_s=12.3,
            cost_usd=0.05,
        ))

        jsonl = trail.to_jsonl()
        trail.upload_to_vault(hub)
        latex = trail.generate_report_latex()
    """

    def __init__(self, symposium_id: str = "") -> None:
        self._entries: list[AuditEntry] = []
        self._symposium_id: str = symposium_id or f"SYM-{uuid.uuid4().hex[:12].upper()}"
        self._start_time: float = time.monotonic()
        self._log = logger.bind(
            component="audit_trail",
            symposium_id=self._symposium_id,
        )
        self._log.info("audit_trail_created")

    # ── Properties ───────────────────────────────────────────────────────

    @property
    def symposium_id(self) -> str:
        """The symposium run this trail belongs to."""
        return self._symposium_id

    @property
    def entries(self) -> list[AuditEntry]:
        """Read-only snapshot of all recorded entries."""
        return list(self._entries)

    @property
    def total_elapsed_s(self) -> float:
        """Wall-clock elapsed since trail creation in seconds."""
        return time.monotonic() - self._start_time

    @property
    def total_cost_usd(self) -> float:
        """Sum of ``cost_usd`` across all entries."""
        return sum(e.cost_usd for e in self._entries)

    @property
    def total_sorry_count(self) -> int:
        """Total Lean 4 sorry placeholders across all entries."""
        return sum(e.lean_sorry_count for e in self._entries)

    # ── Recording ────────────────────────────────────────────────────────

    def record(self, entry: AuditEntry) -> AuditEntry:
        """Append an audit entry to the trail.

        Args:
            entry: A fully constructed :class:`AuditEntry`.

        Returns:
            The same entry (for chaining convenience).
        """
        self._entries.append(entry)
        self._log.info(
            "audit_entry_recorded",
            stage=entry.stage.name,
            agent=entry.agent,
            verdict=entry.socrate_verdict.value,
            duration_s=round(entry.duration_s, 2),
            cost_usd=round(entry.cost_usd, 6),
            sorry_count=entry.lean_sorry_count,
        )
        return entry

    # ── Serialisation: JSONL ─────────────────────────────────────────────

    def to_jsonl(self) -> str:
        """Serialise the trail to JSONL (one JSON object per line).

        Returns:
            A string where each line is a JSON-encoded :class:`AuditEntry`.
        """
        lines: list[str] = []
        header = {
            "type": "header",
            "symposium_id": self._symposium_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "total_entries": len(self._entries),
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_elapsed_s": round(self.total_elapsed_s, 3),
        }
        lines.append(json.dumps(header, ensure_ascii=False))
        for entry in self._entries:
            lines.append(json.dumps(entry.to_dict(), ensure_ascii=False))
        return "\n".join(lines) + "\n"

    def save_jsonl(self, path: str | Path) -> Path:
        """Write the JSONL trail to a file.

        Args:
            path: Destination file path.

        Returns:
            The resolved :class:`Path` written to.
        """
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(self.to_jsonl(), encoding="utf-8")
        self._log.info("audit_trail_saved", path=str(dest), entries=len(self._entries))
        return dest

    # ── Vault Upload ─────────────────────────────────────────────────────

    def upload_to_vault(
        self,
        hub: AlexandrieHub,
        room_type: RoomType = RoomType.PRIVATE,
    ) -> str:
        """Upload the JSONL audit trail to the Alexandrie Vault.

        Args:
            hub: An initialised :class:`AlexandrieHub` instance.
            room_type: Vault room to store the artifact in.

        Returns:
            The artifact ID assigned in Alexandrie.
        """
        artifact_id = f"audit_{self._symposium_id}"
        content = self.to_jsonl()

        try:
            hub.store_artifact(
                artifact_id=artifact_id,
                title=f"Audit Trail — {self._symposium_id}",
                content=content,
                artifact_type=ArtifactType.METADATA,
                room_type=room_type,
                creator="SymposiumAuditTrail",
                tags=["audit", "pipeline", self._symposium_id],
                metrics={
                    "total_entries": len(self._entries),
                    "total_cost_usd": round(self.total_cost_usd, 6),
                    "total_sorry_count": self.total_sorry_count,
                },
            )
            self._log.info(
                "audit_trail_uploaded",
                artifact_id=artifact_id,
                entries=len(self._entries),
            )
        except Exception as exc:
            self._log.error(
                "audit_trail_upload_failed",
                artifact_id=artifact_id,
                error=str(exc),
            )

        return artifact_id

    # ── LaTeX Report ─────────────────────────────────────────────────────

    def generate_report_latex(self) -> str:
        r"""Render the audit trail as a LaTeX appendix section.

        Produces a ``longtable`` with columns for stage, agent, verdict,
        sorry count, cost, and duration — suitable for direct inclusion
        in the Hypatia monograph via ``\input{}``.

        Returns:
            LaTeX fragment (no ``\documentclass``) for the appendix.
        """
        rows: list[str] = []
        for e in self._entries:
            # Escape LaTeX specials
            safe_agent = e.agent.replace("_", r"\_").replace("&", r"\&")
            verdict_cmd = {
                SocrateVerdict.PASS: r"\textcolor{green!60!black}{PASS}",
                SocrateVerdict.WARN: r"\textcolor{orange}{WARN}",
                SocrateVerdict.FAIL: r"\textcolor{red}{FAIL}",
            }[e.socrate_verdict]
            rows.append(
                f"  {e.stage.name} & {safe_agent} & {verdict_cmd} "
                f"& {e.lean_sorry_count} & \\${e.cost_usd:.4f} "
                f"& {e.duration_s:.1f}s \\\\"
            )

        table_body = "\n".join(rows) if rows else "  (no entries) & & & & & \\\\"

        # Summary statistics
        n_pass = sum(1 for e in self._entries if e.socrate_verdict == SocrateVerdict.PASS)
        n_warn = sum(1 for e in self._entries if e.socrate_verdict == SocrateVerdict.WARN)
        n_fail = sum(1 for e in self._entries if e.socrate_verdict == SocrateVerdict.FAIL)

        return (
            r"\section*{Appendix: Pipeline Audit Trail}" "\n"
            r"\addcontentsline{toc}{section}{Pipeline Audit Trail}" "\n"
            f"\\noindent\\textbf{{Symposium ID:}} \\texttt{{{self._symposium_id}}} \\\\\n"
            f"\\noindent\\textbf{{Total cost:}} \\${self.total_cost_usd:.4f} \\quad "
            f"\\textbf{{Elapsed:}} {self.total_elapsed_s:.1f}s \\quad "
            f"\\textbf{{Sorry count:}} {self.total_sorry_count}\n\n"
            r"\begin{longtable}{"
            r">{\raggedright}p{3.8cm} "
            r">{\raggedright}p{2cm} "
            r"c "
            r"r "
            r"r "
            r"r}" "\n"
            r"\toprule" "\n"
            r"\textbf{Stage} & \textbf{Agent} & \textbf{Verdict} "
            r"& \textbf{Sorry} & \textbf{Cost} & \textbf{Time} \\" "\n"
            r"\midrule" "\n"
            r"\endhead" "\n"
            f"{table_body}\n"
            r"\bottomrule" "\n"
            r"\end{longtable}" "\n\n"
            r"\noindent\textit{Verdicts: "
            f"{n_pass} PASS, {n_warn} WARN, {n_fail} FAIL"
            r"}" "\n"
        )
