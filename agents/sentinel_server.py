# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Sentinel Pipeline FastAPI Server.

Exposes the Sentinel verification orchestration over a REST API.
"""

import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import structlog

from agents.sentinel_pipeline import SentinelPipeline

logger = structlog.get_logger(__name__)

app = FastAPI(title="Sentinel Verification API")

class VerificationRequest(BaseModel):
    source_code: str
    language: str = "solidity"
    contract_name: str | None = None
    run_galois: bool = False

@app.post("/verify")
async def verify_contract(req: VerificationRequest):
    pipeline = SentinelPipeline()
    try:
        result = await pipeline.run(
            source_code=req.source_code,
            language=req.language,
            contract_name=req.contract_name,
            run_galois=req.run_galois
        )
        return result.to_dict()
    except Exception as exc:
        logger.error("sentinel_verify_error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
