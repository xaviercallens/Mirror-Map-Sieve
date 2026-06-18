# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Descartes Agent — The Exploit Synthesizer.

When the Galois MCTS engine exhausts its compute budget without closing
a proof, a hack is mathematically possible. Descartes analyzes the
dead-end nodes, extracts the deepest contradictory Lean state, and
back-translates it into an actionable exploit vector.

This is the "Billion-Dollar Feature" — the ability to not just say
"we couldn't prove safety" but to demonstrate exactly HOW the system
can be exploited, with a concrete proof-of-concept payload.

Reference: THE AGORA SENTINEL CODEX, Chapter 9 & Bourbaki Layer §3.
Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import json
import os
from agents.common.secrets import get_secret
from dataclasses import dataclass, field
from typing import Any

import structlog

from agents.base import AbstractAgent, AgentConfig, AgentResult, AgentRole

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ExploitVector:
    """A synthesized exploit derived from a failed proof state.

    Attributes:
        vulnerability_type: Classification (e.g., 'integer_overflow',
            'reentrancy', 'access_control').
        lean_contradiction: The exact Lean 4 state showing the failure.
        english_description: Human-readable explanation of the vulnerability.
        exploit_payload: Concrete proof-of-concept code (Python/JS/Solidity).
        affected_function: Name of the vulnerable function.
        severity: CRITICAL / HIGH / MEDIUM / LOW.
        remediation: Suggested fix description.
        cwe_id: Common Weakness Enumeration identifier (if applicable).
    """

    vulnerability_type: str
    lean_contradiction: str
    english_description: str
    exploit_payload: str
    affected_function: str
    severity: str = "HIGH"
    remediation: str = ""
    cwe_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "vulnerability_type": self.vulnerability_type,
            "lean_contradiction": self.lean_contradiction,
            "english_description": self.english_description,
            "exploit_payload": self.exploit_payload,
            "affected_function": self.affected_function,
            "severity": self.severity,
            "remediation": self.remediation,
            "cwe_id": self.cwe_id,
        }


# ---------------------------------------------------------------------------
# Descartes Agent
# ---------------------------------------------------------------------------

class DescartesAgent(AbstractAgent):
    """Descartes: exploit synthesizer from failed proof states.

    When Galois fails to close a proof, Descartes:
    1. Extracts the deepest contradictory Lean state from the MCTS tree
    2. Classifies the vulnerability type
    3. Back-translates the mathematical contradiction into source-language
       exploit code
    4. Generates remediation recommendations

    The output is a structured ExploitVector that can be consumed by
    Champollion for report generation.
    """

    # Known vulnerability patterns in failed Lean states
    _VULNERABILITY_PATTERNS: dict[str, dict[str, str]] = {
        "overflow": {
            "pattern": "amount > balance",
            "type": "integer_overflow",
            "cwe": "CWE-190",
            "severity": "CRITICAL",
        },
        "reentrancy": {
            "pattern": "call.value",
            "type": "reentrancy",
            "cwe": "CWE-841",
            "severity": "CRITICAL",
        },
        "access_control": {
            "pattern": "msg.sender ≠ owner",
            "type": "access_control_bypass",
            "cwe": "CWE-284",
            "severity": "HIGH",
        },
        "division_by_zero": {
            "pattern": "divisor = 0",
            "type": "division_by_zero",
            "cwe": "CWE-369",
            "severity": "HIGH",
        },
    }

    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                name="descartes",
                model="gemini-2.5-pro",
                role=AgentRole.EXPERIMENTER,  # Will be EXPLOIT_SYNTHESIZER
                budget_limit=25.0,
                project_budget=200.0,
                temperature=0.3,
                tools=["synthesize_exploit", "classify_vulnerability"],
            )
        super().__init__(config)
        self._log = logger.bind(agent="descartes")
        self._exploits_found: list[ExploitVector] = []

    async def synthesize_exploit(
        self,
        dead_end_state: str,
        source_language: str = "solidity",
        source_function: str = "",
    ) -> ExploitVector:
        """Synthesize an exploit from a failed proof dead-end.

        Args:
            dead_end_state: The Lean 4 state at the deepest failed node.
            source_language: Original source language for payload generation.
            source_function: Name of the function being verified.

        Returns:
            ExploitVector with the synthesized exploit.
        """
        timer = self._start_timer()

        # Step 1: Classify the vulnerability
        vuln_type, cwe, severity = self._classify_vulnerability(dead_end_state)

        # Step 2: Generate exploit payload via LLM
        exploit_payload, description, remediation = await self._generate_exploit(
            dead_end_state=dead_end_state,
            vulnerability_type=vuln_type,
            source_language=source_language,
            source_function=source_function,
        )

        exploit = ExploitVector(
            vulnerability_type=vuln_type,
            lean_contradiction=dead_end_state,
            english_description=description,
            exploit_payload=exploit_payload,
            affected_function=source_function,
            severity=severity,
            remediation=remediation,
            cwe_id=cwe,
        )

        self._exploits_found.append(exploit)
        elapsed = self._stop_timer(timer, "exploit_synthesis")

        self._log.warning(
            "exploit_synthesized",
            type=vuln_type,
            severity=severity,
            function=source_function,
            elapsed_ms=elapsed,
        )

        return exploit

    def _classify_vulnerability(
        self, lean_state: str
    ) -> tuple[str, str, str]:
        """Classify the vulnerability type from the failed Lean state.

        Args:
            lean_state: The contradictory Lean 4 state.

        Returns:
            Tuple of (vulnerability_type, cwe_id, severity).
        """
        state_lower = lean_state.lower()

        for _, pattern_info in self._VULNERABILITY_PATTERNS.items():
            if pattern_info["pattern"].lower() in state_lower:
                return (
                    pattern_info["type"],
                    pattern_info["cwe"],
                    pattern_info["severity"],
                )

        # Default: unknown vulnerability
        return "logic_violation", "CWE-682", "HIGH"

    async def _generate_exploit(
        self,
        dead_end_state: str,
        vulnerability_type: str,
        source_language: str,
        source_function: str,
    ) -> tuple[str, str, str]:
        """Generate exploit payload and remediation via LLM.

        Args:
            dead_end_state: The failed Lean 4 state.
            vulnerability_type: Classified vulnerability type.
            source_language: Target language for exploit code.
            source_function: Name of the vulnerable function.

        Returns:
            Tuple of (exploit_code, english_description, remediation).
        """
        prompt = (
            "You are a formal verification security researcher.\n"
            "The proof engine FAILED to verify a security invariant.\n"
            "The failure reveals a mathematically provable vulnerability.\n\n"
            f"FAILED LEAN 4 STATE:\n{dead_end_state}\n\n"
            f"VULNERABILITY TYPE: {vulnerability_type}\n"
            f"SOURCE LANGUAGE: {source_language}\n"
            f"AFFECTED FUNCTION: {source_function}\n\n"
            "Generate:\n"
            "1. A concrete exploit payload in Python that demonstrates the attack\n"
            "2. A clear English description of the vulnerability\n"
            "3. A remediation recommendation\n\n"
            "Reply as JSON: "
            '{"exploit_code": "...", "description": "...", "remediation": "..."}'
        )

        try:
            result = await self._call_llm(prompt)
            parsed = json.loads(result)
            return (
                parsed.get("exploit_code", "# Exploit generation failed"),
                parsed.get("description", "Vulnerability detected but description generation failed."),
                parsed.get("remediation", "Manual security review recommended."),
            )
        except Exception as exc:
            self._log.error("exploit_generation_failed", error=str(exc))
            return (
                f"# Exploit auto-generation failed: {exc}",
                f"The proof engine failed at state: {dead_end_state[:200]}",
                "Manual review of the contradictory proof state is required.",
            )

    async def _call_llm(self, prompt: str) -> str:
        """Call the LLM for exploit generation."""
        import requests

        api_key = get_secret("GEMINI_API_KEY")
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/"
            f"models/{self.config.model}:generateContent"
            f"?key={api_key}"
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": self.config.temperature,
                "maxOutputTokens": 1024,
            },
        }

        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        text = data["candidates"][0]["content"]["parts"][0]["text"]
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].strip()
        return text

    # ------ AbstractAgent lifecycle ----------------------------------------

    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "dead_end_state": context.get("dead_end_state", ""),
            "source_language": context.get("source_language", "solidity"),
            "source_function": context.get("source_function", ""),
        }

    async def act(self, plan: dict[str, Any]) -> dict[str, Any]:
        exploit = await self.synthesize_exploit(
            dead_end_state=plan["dead_end_state"],
            source_language=plan["source_language"],
            source_function=plan["source_function"],
        )
        return {"exploit": exploit.to_dict()}

    async def run(self, query: str, **kwargs: Any) -> AgentResult:
        self._guard_iterations()
        context = {
            "dead_end_state": query,
            "source_language": kwargs.get("source_language", "solidity"),
            "source_function": kwargs.get("source_function", ""),
        }
        plan = await self.think(context)
        result = await self.act(plan)

        return AgentResult(
            answer=result["exploit"],
            confidence=0.7,
            telemetry={
                "total_exploits": len(self._exploits_found),
                "exploit_types": [e.vulnerability_type for e in self._exploits_found],
            },
        )
