# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""GCP Serverless Lean 4 Compiler Endpoint.

Exposes a REST API to accept Lean 4 source code, compile it using
the pre-built lake project in the container, and return the results.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(
    title="🏛️ Agora GCP Lean 4 Compiler Endpoint",
    description="Serverless API to compile Lean 4 code securely and at scale.",
    version="1.0.0"
)

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

_SORRY_PATTERN = re.compile(r'\bsorry\b', re.IGNORECASE)

@app.post("/compile", response_model=CompileResponse)
async def compile_lean_code(req: CompileRequest):
    code = req.code
    
    # 1. Static sorry check
    lines = code.splitlines()
    sorry_count = sum(1 for line in lines if _SORRY_PATTERN.search(line) and not line.strip().startswith("--"))
    has_sorry = sorry_count > 0

    # 2. Setup isolated file in existing project
    project_dir = "/app/verifiers/lean4"
    module_name = f"CloudCompile_{int(time.time()*1000)}"
    lib_file_path = os.path.join(project_dir, "Agora", f"{module_name}.lean")
    
    # Create the Agora directory if it does not exist
    os.makedirs(os.path.dirname(lib_file_path), exist_ok=True)
    
    try:
        # Write the code to the library file
        with open(lib_file_path, "w", encoding="utf-8") as f:
            f.write(code)
            
        # 3. Run lean compiler in lake environment
        build_proc = subprocess.run(
            ["lake", "env", "lean", lib_file_path],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=req.timeout
        )
        
        success = (build_proc.returncode == 0)
        
        return CompileResponse(
            success=success,
            exit_code=build_proc.returncode,
            stdout=build_proc.stdout[:5000],
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
