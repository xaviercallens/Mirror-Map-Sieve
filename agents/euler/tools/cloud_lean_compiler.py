# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Cloud-based Lean 4 proof compiler and type-checker.

Sends Lean 4 code to the GCP Cloud Run serverless endpoint to run
`lake build` in an isolated, scalable environment.

Improvement 3 (Lean 4 Compilation): When the GCP endpoint is unavailable
or USE_LOCAL_LAKE=1 is set, falls back to running `lake build` locally
against the verifiers/lean4 project which has Mathlib pre-cached.
This ensures real compilation (not just sorry-counting) in all environments.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────

# The local Lean 4 / Mathlib project used for offline compilation.
# lake-manifest.json and .lake/packages/ are pre-built here.
_LEAN4_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent / "verifiers" / "lean4"
_AGORA_MODULE_DIR = _LEAN4_PROJECT_ROOT / "Agora"

_SORRY_PATTERN = re.compile(r'\bsorry\b', re.IGNORECASE)


# ── Local lake build  ─────────────────────────────────────────────────────────

def _compile_with_local_lake(proof_code: str, timeout: int = 180) -> dict[str, Any]:
    """Compile proof_code using the local lake project at verifiers/lean4/.

    Steps:
    1. Write proof_code to a temporary Lean module in Agora/CloudCompile_<ts>.lean
    2. Run `lake build Agora.CloudCompile_<ts>`
    3. Parse stdout/stderr, detect sorry, return structured result.
    4. Always clean up the temp module file.

    Returns dict with keys: success, has_sorry, exit_code, stdout, stderr,
                             sorry_count, message, compilation_mode.
    """
    if not _LEAN4_PROJECT_ROOT.exists():
        return {
            "success": False,
            "has_sorry": True,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Local Lean 4 project not found at {_LEAN4_PROJECT_ROOT}",
            "sorry_count": 0,
            "message": "Local lake project missing — cannot compile",
            "compilation_mode": "local_lake_missing",
        }

    lake_bin = shutil.which("lake")
    if lake_bin is None:
        return {
            "success": False,
            "has_sorry": True,
            "exit_code": -1,
            "stdout": "",
            "stderr": "lake not found on PATH",
            "sorry_count": 0,
            "message": "lake binary not found — install via elan",
            "compilation_mode": "lake_not_found",
        }

    # Static sorry analysis (before compilation)
    lines = proof_code.splitlines()
    sorry_count = sum(
        1 for ln in lines
        if _SORRY_PATTERN.search(ln) and not ln.strip().startswith("--")
    )
    has_sorry = sorry_count > 0

    # Create a unique module name to avoid name collisions
    ts = int(time.time() * 1000)
    module_name = f"CloudCompile_{ts}"
    module_file = _AGORA_MODULE_DIR / f"{module_name}.lean"

    logger.info(
        "local_lake_build_start",
        module=module_name,
        sorry_count=sorry_count,
        project_root=str(_LEAN4_PROJECT_ROOT),
    )

    try:
        _AGORA_MODULE_DIR.mkdir(parents=True, exist_ok=True)
        module_file.write_text(proof_code, encoding="utf-8")

        # Fix SSL_CERT_FILE pointing to directory (local env quirk)
        env = os.environ.copy()
        if "SSL_CERT_FILE" in env and os.path.isdir(env["SSL_CERT_FILE"]):
            del env["SSL_CERT_FILE"]

        proc = subprocess.run(
            [lake_bin, "build", f"Agora.{module_name}"],
            cwd=str(_LEAN4_PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )

        success = proc.returncode == 0

        # lake build exits 0 even when sorry is present (it's a warning).
        # We apply the Zero-Sorry Guillotine: sorry == INCOMPLETE regardless.
        if success and has_sorry:
            msg = (
                f"lake build PASSED (exit 0) but {sorry_count} sorry gap(s) detected "
                f"— proof is INCOMPLETE per Zero-Sorry Guillotine."
            )
        elif success:
            msg = "lake build PASSED ✓ — proof compiled without sorry gaps. VERIFIED."
        else:
            msg = f"lake build FAILED (exit {proc.returncode}) ✗"

        logger.info(
            "local_lake_build_done",
            success=success,
            has_sorry=has_sorry,
            sorry_count=sorry_count,
            exit_code=proc.returncode,
            module=module_name,
        )

        return {
            "success": success,
            "has_sorry": has_sorry,
            "exit_code": proc.returncode,
            "stdout": proc.stdout[:5000],
            "stderr": proc.stderr[:5000],
            "sorry_count": sorry_count,
            "message": msg,
            "compilation_mode": "local_lake_build",
        }

    except subprocess.TimeoutExpired:
        logger.error("local_lake_build_timeout", timeout=timeout, module=module_name)
        return {
            "success": False,
            "has_sorry": has_sorry,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"lake build timed out after {timeout}s",
            "sorry_count": sorry_count,
            "message": f"lake build timed out after {timeout}s",
            "compilation_mode": "local_lake_timeout",
        }
    except Exception as exc:
        import traceback
        logger.error("local_lake_build_error", error=str(exc),
                     traceback=traceback.format_exc()[:500])
        return {
            "success": False,
            "has_sorry": has_sorry,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(exc),
            "sorry_count": sorry_count,
            "message": f"local lake build error: {exc}",
            "compilation_mode": "local_lake_error",
        }
    finally:
        if module_file.exists():
            module_file.unlink(missing_ok=True)


# ── GCP Cloud Run endpoint ────────────────────────────────────────────────────

def compile_lean4_proof_cloud(
    proof_code: str,
    timeout: int = 120,
    use_local_lake: bool | None = None,
) -> dict[str, Any]:
    """Compile and type-check a Lean 4 proof.

    Priority order (Improvement 3):
    1. If USE_LOCAL_LAKE=1 env var is set OR use_local_lake=True: run lake locally.
    2. Try GCP Cloud Run endpoint (LEAN_COMPILER_ENDPOINT).
    3. If GCP endpoint is unreachable (ConnectionError / Timeout): fall back to
       local lake build automatically so the pipeline never silently skips compilation.

    Args:
        proof_code: Lean 4 source code as a string.
        timeout: Compilation timeout in seconds.
        use_local_lake: Force local lake build. If None, reads USE_LOCAL_LAKE env var.

    Returns:
        Dict with keys: success, has_sorry, exit_code, stdout, stderr,
                        sorry_count, message, compilation_mode.
    """
    logger.info("cloud_lean4_compile_start", code_length=len(proof_code))

    # ── Determine execution mode ──────────────────────────────────────────────
    if use_local_lake is None:
        use_local_lake = os.getenv("USE_LOCAL_LAKE", "0") == "1"

    if use_local_lake:
        logger.info("cloud_lean4_routing", mode="local_lake_forced")
        return _compile_with_local_lake(proof_code, timeout=min(timeout, 300))

    # ── Attempt GCP endpoint ──────────────────────────────────────────────────
    endpoint_url = os.getenv("LEAN_COMPILER_ENDPOINT", "http://127.0.0.1:8080/compile")

    payload = {"code": proof_code, "timeout": timeout}

    try:
        # Fix SSL_CERT_FILE pointing to directory (local env quirk)
        if "SSL_CERT_FILE" in os.environ and os.path.isdir(os.environ["SSL_CERT_FILE"]):
            del os.environ["SSL_CERT_FILE"]

        with httpx.Client(timeout=timeout + 10) as client:
            response = client.post(endpoint_url, json=payload)
            response.raise_for_status()

        data = response.json()
        success = data.get("success", False)
        has_sorry = data.get("has_sorry", False)
        sorry_count = data.get("sorry_count", 0)

        if os.getenv("AGORA_STRICT_MODE") == "1" and not success:
            raise RuntimeError(
                f"Cloud Lean 4 compilation failed under AGORA_STRICT_MODE: {data.get('stderr')}"
            )

        msg_parts = []
        if success and not has_sorry:
            msg_parts.append("GCP lake build PASSED ✓ — proof compiled without sorry gaps.")
        elif success and has_sorry:
            msg_parts.append(
                f"GCP lake build PASSED (exit 0) but {sorry_count} sorry gap(s) detected "
                f"— proof is INCOMPLETE per Zero-Sorry Guillotine."
            )
        else:
            msg_parts.append("GCP lake build FAILED ✗")

        result = {
            "success": success,
            "has_sorry": has_sorry,
            "exit_code": data.get("exit_code", -1),
            "stdout": data.get("stdout", ""),
            "stderr": data.get("stderr", ""),
            "sorry_count": sorry_count,
            "message": " | ".join(msg_parts),
            "compilation_mode": "gcp_cloud_run",
        }

        logger.info("cloud_lean4_compile_done", success=success, has_sorry=has_sorry,
                    compilation_mode="gcp_cloud_run")
        return result

    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.RemoteProtocolError) as conn_exc:
        # ── Improvement 3: Automatic fallback to local lake build ─────────────
        logger.warning(
            "cloud_lean4_endpoint_unreachable",
            endpoint=endpoint_url,
            error=str(conn_exc),
            action="falling_back_to_local_lake_build",
        )
        result = _compile_with_local_lake(proof_code, timeout=min(timeout, 300))
        result["message"] = f"[GCP unreachable → local lake] {result['message']}"
        result["gcp_fallback"] = True
        return result

    except httpx.TimeoutException:
        logger.error("cloud_lean4_timeout", timeout=timeout)
        if os.getenv("AGORA_STRICT_MODE") == "1":
            raise RuntimeError(
                f"Cloud Lean 4 compilation timed out after {timeout}s under AGORA_STRICT_MODE"
            )
        return {
            "success": False,
            "has_sorry": True,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Compilation timed out after {timeout}s",
            "sorry_count": 0,
            "message": f"GCP Lean 4 compilation timed out after {timeout} seconds",
            "compilation_mode": "gcp_timeout",
        }

    except Exception as exc:
        import traceback
        logger.error("cloud_lean4_error", error=str(exc),
                     traceback=traceback.format_exc()[:500], endpoint=endpoint_url)
        # Last resort: try local lake
        logger.warning("cloud_lean4_last_resort_local_lake", error=str(exc))
        result = _compile_with_local_lake(proof_code, timeout=min(timeout, 300))
        result["message"] = f"[GCP error → local lake] {result['message']}"
        result["gcp_error"] = str(exc)
        return result
