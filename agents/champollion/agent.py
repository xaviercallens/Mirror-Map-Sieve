# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Champollion Agent — The Executive Decoder.

Generates compliance-ready certification documents from verification results.
When the proof succeeds: issues a Mathematical Certificate of Assurance.
When the proof fails: issues a Critical Zero-Day Advisory with exploit details.

A CEO paying $30,000 for an audit cannot read a Lean 4 AST. Champollion
translates formal verification results into beautiful, branded documents
that executives, regulators, and auditors can understand.

Reference: THE AGORA SENTINEL CODEX, Chapter 9 & Bourbaki Layer §4.
Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import hashlib
import pathlib
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

from agents.base import AbstractAgent, AgentConfig, AgentResult, AgentRole

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Template paths
# ---------------------------------------------------------------------------

_TEMPLATES_DIR = pathlib.Path(__file__).parent / "templates"


# ---------------------------------------------------------------------------
# Report Data Structures
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CertificateOfAssurance:
    """A Mathematical Certificate of Assurance.

    Issued when the Galois MCTS engine successfully proves all
    security invariants with zero sorry gaps remaining.
    """

    contract_name: str
    certificate_id: str
    timestamp: float
    theorems_proven: list[str]
    proof_summary: str
    compute_cost_usd: float
    dag_stats: dict[str, Any]
    lean_version: str = "4.14.0"
    mathlib_version: str = "Mathlib4"

    @property
    def signature_hash(self) -> str:
        """Cryptographic hash of the certificate for integrity."""
        content = (
            f"{self.certificate_id}:{self.contract_name}:"
            f"{self.timestamp}:{':'.join(self.theorems_proven)}"
        )
        return hashlib.sha256(content.encode()).hexdigest()


@dataclass(slots=True)
class ZeroDayAdvisory:
    """A Critical Zero-Day Advisory.

    Issued when the proof engine fails and Descartes synthesizes
    an exploit vector demonstrating the vulnerability.
    """

    contract_name: str
    advisory_id: str
    timestamp: float
    vulnerability_type: str
    severity: str
    exploit_description: str
    exploit_payload: str
    affected_function: str
    remediation: str
    cwe_id: str
    lean_contradiction: str


# ---------------------------------------------------------------------------
# Champollion Agent
# ---------------------------------------------------------------------------

class ChampollionAgent(AbstractAgent):
    """Champollion: generates executive-readable certification reports.

    Two output modes:
    1. SECURE: Mathematical Certificate of Assurance (proof succeeded)
    2. VULNERABLE: Critical Zero-Day Advisory (proof failed + exploit found)

    Output format: Markdown (with optional LaTeX PDF compilation).
    """

    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                name="champollion",
                model="gemini-2.5-flash",
                role=AgentRole.EXPERIMENTER,  # Will be REPORTER
                budget_limit=5.0,
                project_budget=50.0,
                temperature=0.1,
                tools=["generate_certificate", "generate_advisory"],
            )
        super().__init__(config)
        self._log = logger.bind(agent="champollion")
        self._reports_generated = 0

    def generate_certificate(
        self,
        contract_name: str,
        theorems_proven: list[str],
        proof_summary: str,
        compute_cost_usd: float = 0.0,
        dag_stats: dict[str, Any] | None = None,
    ) -> str:
        """Generate a Mathematical Certificate of Assurance.

        Args:
            contract_name: Name of the verified contract/system.
            theorems_proven: List of theorem names with zero sorry.
            proof_summary: Human-readable proof strategy summary.
            compute_cost_usd: Total compute cost of the verification.
            dag_stats: DAG cache statistics.

        Returns:
            Formatted Markdown certificate.
        """
        timer = self._start_timer()

        cert = CertificateOfAssurance(
            contract_name=contract_name,
            certificate_id=hashlib.md5(
                f"{contract_name}:{time.time()}".encode()
            ).hexdigest()[:12].upper(),
            timestamp=time.time(),
            theorems_proven=theorems_proven,
            proof_summary=proof_summary,
            compute_cost_usd=compute_cost_usd,
            dag_stats=dag_stats or {},
        )

        # Load template
        template = self._load_template("certificate_of_assurance.md")
        report = self._render_certificate(template, cert)

        self._reports_generated += 1
        elapsed = self._stop_timer(timer, "certificate_generation")
        self._log.info(
            "certificate_generated",
            contract=contract_name,
            theorems=len(theorems_proven),
            elapsed_ms=elapsed,
        )
        return report

    def generate_advisory(
        self,
        contract_name: str,
        vulnerability_type: str,
        severity: str,
        exploit_description: str,
        exploit_payload: str,
        affected_function: str,
        remediation: str,
        cwe_id: str = "",
        lean_contradiction: str = "",
    ) -> str:
        """Generate a Critical Zero-Day Advisory.

        Args:
            contract_name: Name of the vulnerable contract/system.
            vulnerability_type: Classification of the vulnerability.
            severity: CRITICAL / HIGH / MEDIUM / LOW.
            exploit_description: Human-readable vulnerability explanation.
            exploit_payload: Proof-of-concept exploit code.
            affected_function: Name of the vulnerable function.
            remediation: Suggested fix.
            cwe_id: CWE identifier.
            lean_contradiction: The Lean 4 state that proves the vulnerability.

        Returns:
            Formatted Markdown advisory.
        """
        timer = self._start_timer()

        advisory = ZeroDayAdvisory(
            contract_name=contract_name,
            advisory_id=hashlib.md5(
                f"{contract_name}:{vulnerability_type}:{time.time()}".encode()
            ).hexdigest()[:12].upper(),
            timestamp=time.time(),
            vulnerability_type=vulnerability_type,
            severity=severity,
            exploit_description=exploit_description,
            exploit_payload=exploit_payload,
            affected_function=affected_function,
            remediation=remediation,
            cwe_id=cwe_id,
            lean_contradiction=lean_contradiction,
        )

        template = self._load_template("zero_day_advisory.md")
        report = self._render_advisory(template, advisory)

        self._reports_generated += 1
        elapsed = self._stop_timer(timer, "advisory_generation")
        self._log.warning(
            "advisory_generated",
            contract=contract_name,
            severity=severity,
            type=vulnerability_type,
            elapsed_ms=elapsed,
        )
        return report

    # ------ Template Rendering ---------------------------------------------

    def _load_template(self, filename: str) -> str:
        """Load a Markdown template from the templates directory."""
        path = _TEMPLATES_DIR / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
        # Fallback: inline template
        self._log.warning("template_not_found", filename=filename)
        return "{content}"

    def _render_certificate(
        self, template: str, cert: CertificateOfAssurance
    ) -> str:
        """Render a certificate from template + data."""
        from datetime import datetime, timezone

        ts = datetime.fromtimestamp(cert.timestamp, tz=timezone.utc)

        theorems_list = "\n".join(
            f"  - `{t}` — **VERIFIED** (zero sorry, zero axiom)"
            for t in cert.theorems_proven
        )

        replacements = {
            "{{CONTRACT_NAME}}": cert.contract_name,
            "{{CERTIFICATE_ID}}": cert.certificate_id,
            "{{TIMESTAMP}}": ts.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "{{THEOREMS_LIST}}": theorems_list,
            "{{THEOREMS_COUNT}}": str(len(cert.theorems_proven)),
            "{{PROOF_SUMMARY}}": cert.proof_summary,
            "{{COMPUTE_COST}}": f"${cert.compute_cost_usd:.2f}",
            "{{SIGNATURE_HASH}}": cert.signature_hash,
            "{{LEAN_VERSION}}": cert.lean_version,
            "{{MATHLIB_VERSION}}": cert.mathlib_version,
        }

        result = template
        for key, value in replacements.items():
            result = result.replace(key, value)
        return result

    def _render_advisory(
        self, template: str, advisory: ZeroDayAdvisory
    ) -> str:
        """Render an advisory from template + data."""
        from datetime import datetime, timezone

        ts = datetime.fromtimestamp(advisory.timestamp, tz=timezone.utc)

        replacements = {
            "{{CONTRACT_NAME}}": advisory.contract_name,
            "{{ADVISORY_ID}}": advisory.advisory_id,
            "{{TIMESTAMP}}": ts.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "{{VULNERABILITY_TYPE}}": advisory.vulnerability_type,
            "{{SEVERITY}}": advisory.severity,
            "{{EXPLOIT_DESCRIPTION}}": advisory.exploit_description,
            "{{EXPLOIT_PAYLOAD}}": advisory.exploit_payload,
            "{{AFFECTED_FUNCTION}}": advisory.affected_function,
            "{{REMEDIATION}}": advisory.remediation,
            "{{CWE_ID}}": advisory.cwe_id or "N/A",
            "{{LEAN_CONTRADICTION}}": advisory.lean_contradiction,
        }

        result = template
        for key, value in replacements.items():
            result = result.replace(key, value)
        return result

    # ------ AbstractAgent lifecycle ----------------------------------------

    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "mode": context.get("mode", "certificate"),
            "data": context,
        }

    async def act(self, plan: dict[str, Any]) -> dict[str, Any]:
        data = plan["data"]
        if plan["mode"] == "advisory":
            report = self.generate_advisory(
                contract_name=data.get("contract_name", "Unknown"),
                vulnerability_type=data.get("vulnerability_type", "unknown"),
                severity=data.get("severity", "HIGH"),
                exploit_description=data.get("exploit_description", ""),
                exploit_payload=data.get("exploit_payload", ""),
                affected_function=data.get("affected_function", ""),
                remediation=data.get("remediation", ""),
                cwe_id=data.get("cwe_id", ""),
                lean_contradiction=data.get("lean_contradiction", ""),
            )
        else:
            report = self.generate_certificate(
                contract_name=data.get("contract_name", "Unknown"),
                theorems_proven=data.get("theorems_proven", []),
                proof_summary=data.get("proof_summary", ""),
                compute_cost_usd=data.get("compute_cost_usd", 0.0),
                dag_stats=data.get("dag_stats"),
            )
        return {"report": report}

    async def run(self, query: str, **kwargs: Any) -> AgentResult:
        self._guard_iterations()
        context = {"contract_name": query, **kwargs}
        plan = await self.think(context)
        result = await self.act(plan)
        return AgentResult(
            answer=result["report"],
            confidence=1.0,
            telemetry={"reports_generated": self._reports_generated},
        )
