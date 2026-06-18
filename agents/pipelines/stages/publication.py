# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Stage 10 — Publication: PDF Compilation, GCS Upload & Alexandrie Vault.

Compiles the LaTeX document to PDF via 2-pass pdflatex, uploads outputs
to a GCS bucket, and stores the artefact in the Alexandrie Vault
(private room, accessible to ``config.owner_email``).

Returns a dict with pdf_path, tex_path, gcs_uri, and vault_artifact_id.
"""

from __future__ import annotations

import subprocess
import time
import uuid
from pathlib import Path

import structlog

from agents.pipelines.audit import SymposiumAuditTrail
from agents.pipelines.config import SymposiumConfig

logger = structlog.get_logger(__name__)


def _compile_pdf(tex_path: Path, output_dir: Path) -> Path | None:
    """Run 2-pass pdflatex in batchmode.

    Returns:
        Path to the PDF if compilation succeeded, else None.
    """
    pdf_path = tex_path.with_suffix(".pdf")
    log_path = tex_path.with_suffix(".log")

    for pass_num in (1, 2):
        try:
            result = subprocess.run(
                ["pdflatex", "-interaction=batchmode", tex_path.name],
                cwd=str(output_dir),
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                logger.warning(
                    "pdflatex_warning",
                    pass_num=pass_num,
                    returncode=result.returncode,
                )
            else:
                logger.info("pdflatex_pass_ok", pass_num=pass_num)
        except FileNotFoundError:
            logger.error("pdflatex_not_installed")
            return None
        except subprocess.TimeoutExpired:
            logger.error("pdflatex_timeout", pass_num=pass_num)
            return None

    if pdf_path.exists():
        return pdf_path

    # ── Fallback: strip non-ASCII and retry ────────────────────────────
    logger.warning("pdflatex_no_pdf_retrying_clean")
    if log_path.exists():
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        error_lines = [l for l in log_text.split("\n") if l.startswith("!")]
        if error_lines:
            logger.warning("pdflatex_errors", count=len(error_lines),
                           first=error_lines[0][:120])

    tex_content = tex_path.read_text(encoding="utf-8", errors="replace")
    clean = tex_content.encode("ascii", errors="replace").decode("ascii")
    clean = clean.replace("?", " ")
    tex_path.write_text(clean, encoding="utf-8")

    for pass_num in (1, 2):
        try:
            subprocess.run(
                ["pdflatex", "-interaction=batchmode", tex_path.name],
                cwd=str(output_dir),
                capture_output=True,
                text=True,
                timeout=120,
            )
        except Exception:
            pass

    return pdf_path if pdf_path.exists() else None


def _upload_to_gcs(
    config: SymposiumConfig,
    *file_paths: Path,
) -> str:
    """Upload files to GCS bucket.  Returns the gs:// URI prefix."""
    try:
        from google.cloud import storage  # noqa: F811

        client = storage.Client()
        bucket = client.bucket(config.gcs_bucket)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        prefix = f"symposium/{timestamp}/"

        for fp in file_paths:
            if fp.exists():
                blob = bucket.blob(f"{prefix}{fp.name}")
                blob.upload_from_filename(str(fp))
                logger.info("gcs_uploaded", file=fp.name,
                            uri=f"gs://{config.gcs_bucket}/{prefix}{fp.name}")

        return f"gs://{config.gcs_bucket}/{prefix}"
    except Exception as exc:
        logger.warning("gcs_upload_failed", error=str(exc))
        return f"local://{file_paths[0].parent}" if file_paths else "local://unknown"


def _store_in_alexandrie(
    config: SymposiumConfig,
    pdf_path: Path,
    tex_path: Path,
) -> str:
    """Store outputs in the Alexandrie Vault (private room).

    Returns:
        Vault artifact ID.
    """
    try:
        from agents.common.alexandrie import AlexandrieVault

        vault = AlexandrieVault()
        artifact_id = uuid.uuid4().hex[:16]
        room_prefix = f"symposium/private/{config.owner_email}/{artifact_id}"

        if pdf_path.exists():
            vault.upload_file(str(pdf_path), f"{room_prefix}/monograph.pdf")
        if tex_path.exists():
            vault.upload_file(str(tex_path), f"{room_prefix}/monograph.tex")

        # Store metadata
        vault.store_json(f"{room_prefix}/metadata.json", {
            "artifact_id": artifact_id,
            "owner_email": config.owner_email,
            "domain": config.domain,
            "room_type": "private",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "access": [config.owner_email],
        })

        logger.info(
            "alexandrie_stored",
            artifact_id=artifact_id,
            room=room_prefix,
        )
        return artifact_id
    except Exception as exc:
        logger.warning("alexandrie_store_failed", error=str(exc))
        return f"local-{uuid.uuid4().hex[:8]}"


async def publish(
    config: SymposiumConfig,
    latex_doc: str,
    audit: SymposiumAuditTrail,
) -> dict:
    """Compile PDF, upload to GCS, and store in Alexandrie Vault.

    Args:
        config: Symposium configuration.
        latex_doc: Final LaTeX document from Stage 9.
        audit: Audit trail.

    Returns:
        Dict with keys: pdf_path, tex_path, gcs_uri, vault_artifact_id.
    """
    logger.info("stage10_publication_start")
    t0 = time.monotonic()

    output_dir = config.output_dir
    tex_path = output_dir / "symposium_monograph.tex"
    tex_path.write_text(latex_doc, encoding="utf-8")
    logger.info("tex_written", path=str(tex_path), size_kb=tex_path.stat().st_size // 1024)

    # ── Compile PDF ────────────────────────────────────────────────────
    pdf_path = _compile_pdf(tex_path, output_dir)
    pdf_str = str(pdf_path) if pdf_path else ""

    if pdf_path:
        logger.info("pdf_compiled", path=str(pdf_path),
                     size_kb=pdf_path.stat().st_size // 1024)
    else:
        logger.error("pdf_compilation_failed")

    # ── Upload to GCS ──────────────────────────────────────────────────
    files_to_upload = [tex_path]
    if pdf_path:
        files_to_upload.append(pdf_path)
    log_path = tex_path.with_suffix(".log")
    if log_path.exists():
        files_to_upload.append(log_path)

    gcs_uri = _upload_to_gcs(config, *files_to_upload)

    # ── Store in Alexandrie ────────────────────────────────────────────
    vault_artifact_id = _store_in_alexandrie(
        config,
        pdf_path or tex_path,
        tex_path,
    )

    elapsed = time.monotonic() - t0
    result = {
        "pdf_path": pdf_str,
        "tex_path": str(tex_path),
        "gcs_uri": gcs_uri,
        "vault_artifact_id": vault_artifact_id,
    }

    audit.record(
        stage="Stage 10: Publication",
        agent="Publisher",
        action=(
            f"Compiled PDF, uploaded to GCS, stored in Alexandrie. "
            f"vault_id={vault_artifact_id}"
        ),
        elapsed_s=elapsed,
        input_summary=f"latex_doc={len(latex_doc)} chars",
        output_summary=f"pdf={'OK' if pdf_path else 'FAILED'}, gcs={gcs_uri[:60]}",
        vault_artifact_id=vault_artifact_id,
    )

    logger.info(
        "stage10_publication_complete",
        pdf=pdf_str,
        gcs=gcs_uri,
        vault=vault_artifact_id,
        elapsed_s=round(elapsed, 1),
    )
    return result
