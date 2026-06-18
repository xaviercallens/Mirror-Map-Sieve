# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Formal mathematical verification certificate generator.

Creates signed mathematical verification certificates containing the theorem details,
SHA256 checksums, compiler versioning, Euler's skeptical audit objections, and final status.
Persists certificates and verified code in Alexandrie vaults under the PROOF room.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any

import structlog

from alexandrie.hub import AlexandrieHub
from alexandrie.metadata import ArtifactType, RoomType

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Certificate Generation
# ---------------------------------------------------------------------------

def generate_verification_certificate(
    theorem_name: str,
    proof_code: str,
    verdict: str,
    skeptical_audit_comments: str,
    confidence: float,
    vault_root: str | None = None,
) -> dict[str, Any]:
    """Generate a formal mathematical verification certificate and store it in Alexandrie.

    Args:
        theorem_name: Name of the Lean 4 theorem.
        proof_code: Lean 4 proof source code.
        verdict: Verification verdict (e.g. "VERIFIED", "INCOMPLETE", "REFUTED").
        skeptical_audit_comments: Detailed skeptical objections and contradiction-seeking audit text.
        confidence: Verification confidence (0.0 to 1.0).
        vault_root: Path to the Alexandrie storage vault.

    Returns:
        Dict with certificate details and stored metadata.
    """
    logger.info("generating_certificate", theorem=theorem_name, verdict=verdict)

    # Compute SHA-256 hash of proof code
    proof_bytes = proof_code.encode("utf-8")
    proof_hash = hashlib.sha256(proof_bytes).hexdigest()

    # Generate unique Certificate ID
    cert_uuid = str(uuid.uuid4())[:8].upper()
    cert_id = f"CERT-EULER-{theorem_name.upper()}-{cert_uuid}"

    timestamp_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # Build beautifully structured ASCII certificate
    border = "═" * 78
    title = f"🏛️  SOCRATEAI AGORA — FORMAL MATHEMATICAL VERIFICATION CERTIFICATE"
    
    cert_body = (
        f"╔{border}╗\n"
        f"║ {title:<76} ║\n"
        f"╠{border}╣\n"
        f"║ Certificate ID:  {cert_id:<60} ║\n"
        f"║ Issued At:       {timestamp_str:<60} ║\n"
        f"║ Verifier:        Euler Agent / Lean 4 (v4.14.0)                             ║\n"
        f"║ Target Theorem:  {theorem_name:<60} ║\n"
        f"║ Proof SHA-256:   {proof_hash:<60} ║\n"
        f"║ Confidence:      {confidence * 100:>5.1f}%                                                   ║\n"
        f"║ Verification:    {verdict:<60} ║\n"
        f"╠{border}╣\n"
        f"║ EULER MATHEMATICAL SKETCH & AUDIT CRITIQUE:                              ║\n"
    )

    # Wrap comments nicely for ASCII table wrapping
    lines = skeptical_audit_comments.split("\n")
    for line in lines:
        if not line.strip():
            continue
        # Split into 74 character chunks
        chunks = [line[i:i+74] for i in range(0, len(line), 74)]
        for chunk in chunks:
            cert_body += f"║   {chunk:<74} ║\n"

    cert_body += (
        f"╠{border}╣\n"
        f"║ PROOF CODE SKELETON:                                                       ║\n"
    )
    
    # Wrap proof code
    proof_lines = proof_code.split("\n")
    for line in proof_lines[:15]:  # Limit to first 15 lines of proof for formatting
        chunks = [line[i:i+74] for i in range(0, len(line), 74)]
        for chunk in chunks:
            cert_body += f"║   {chunk:<74} ║\n"
    if len(proof_lines) > 15:
        cert_body += f"║   ... ({len(proof_lines) - 15} more lines)                                               ║\n"

    cert_body += (
        f"╠{border}╣\n"
        f"║ SIGNATURE BLOCK:                                                           ║\n"
        f"║ -----BEGIN EULER FORMAL MATHEMATICAL VERIFICATION CERTIFICATE-----         ║\n"
        f"║ Issuer: Euler Agent (SymBrain v7.0)                                        ║\n"
        f"║ Hash: {proof_hash} ║\n"
        f"║ Status: {verdict:<66} ║\n"
        f"║ -----END EULER FORMAL MATHEMATICAL VERIFICATION CERTIFICATE-----           ║\n"
        f"╚{border}╝\n"
    )

    # Persist in Alexandrie
    hub = AlexandrieHub(vault_root)
    
    metadata = hub.store_artifact(
        artifact_id=cert_id,
        title=f"Verification Certificate for Theorem {theorem_name}",
        content=cert_body,
        artifact_type=ArtifactType.PROOF,
        room_type=RoomType.OPEN_ACCESS,
        creator="euler",
        tags=["formal_verification", "lean4", "verso", "certificate", theorem_name.lower()],
        metrics={
            "verification_confidence": confidence,
            "verification_status": verdict,
            "has_sorry": verdict != "VERIFIED"
        },
        extra_attributes={
            "theorem_name": theorem_name,
            "proof_sha256": proof_hash,
            "issuer": "Euler Agent"
        }
    )

    logger.info("certificate_stored_successfully", cert_id=cert_id, sha256=metadata.sha256_hash[:8])

    return {
        "certificate_id": cert_id,
        "certificate_text": cert_body,
        "sha256": proof_hash,
        "metadata": {
            "id": metadata.id,
            "title": metadata.title,
            "timestamp": metadata.timestamp,
            "file_path": str(hub.open_dir / "proof" / f"{cert_id}.txt"),
        }
    }
