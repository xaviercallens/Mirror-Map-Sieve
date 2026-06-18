# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""GCP Serverless Lean 4 Compiler Endpoint.

Exposes a REST API to accept Lean 4 source code, build a temporary
lake project, and return the compilation results including exit code,
stdout, stderr, and whether sorry placeholders were detected.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import shutil
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(
    title="🏛️ Agora GCP Lean 4 Compiler Endpoint",
    description="Serverless API to compile Lean 4 code securely and at scale.",
    version="1.0.0"
)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CompileRequest(BaseModel):
    code: str = Field(..., description="The complete Lean 4 source code to compile.")
    timeout: int = Field(60, description="Compilation timeout in seconds.")

class CompileResponse(BaseModel):
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    has_sorry: bool
    sorry_count: int

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

_SORRY_PATTERN = re.compile(r'\bsorry\b', re.IGNORECASE)

@app.post("/compile", response_model=CompileResponse)
async def compile_lean_code(req: CompileRequest):
    code = req.code
    
    # 1. Static sorry check
    lines = code.splitlines()
    sorry_count = sum(1 for line in lines if _SORRY_PATTERN.search(line) and not line.strip().startswith("--"))
    has_sorry = sorry_count > 0

    # 2. Setup isolated file in existing project
    import time
    
    # Use the existing project to leverage pre-built mathlib
    project_dir = "/Users/xcallens/xdev/SocrateAI-Scientific-Agora/verifiers/lean4"
    module_name = f"CloudCompile_{int(time.time()*1000)}"
    lib_file_path = os.path.join(project_dir, "Agora", f"{module_name}.lean")
    
    try:
        # Write the code to the library file
        with open(lib_file_path, "w", encoding="utf-8") as f:
            f.write(code)
            
        # 3. Run lake build
        build_proc = subprocess.run(
            ["lake", "build", f"Agora.{module_name}"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=req.timeout
        )
        
        success = (build_proc.returncode == 0)
        
        return CompileResponse(
            success=success,
            exit_code=build_proc.returncode,
            stdout=build_proc.stdout[:5000],  # truncate to prevent massive payloads
            stderr=build_proc.stderr[:5000],
            has_sorry=has_sorry,
            sorry_count=sorry_count
        )
        
    except subprocess.TimeoutExpired:
        return CompileResponse(
            success=False,
            exit_code=-1,
            stdout="",
            stderr=f"Compilation timed out after {req.timeout} seconds.",
            has_sorry=has_sorry,
            sorry_count=sorry_count
        )
    finally:
        if os.path.exists(lib_file_path):
            os.remove(lib_file_path)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "agora-lean-compiler"}
