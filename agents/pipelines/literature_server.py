# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""FastAPI Server for the Literature Review Pipeline on Cloud Run.

Patent: US-PAT-PEND-2026-0525
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
import structlog

from agents.pipelines.literature_review import LiteratureReviewPipeline

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events for the literature pipeline server."""
    logger.info("literature_server_start", port=int(os.environ.get("PORT", 8080)))
    yield
    logger.info("literature_server_shutdown")


app = FastAPI(
    title="Agora Literature Review Pipeline",
    description="Scientific literature review with optimized memory and dreams.",
    version="1.0.0",
    lifespan=lifespan,
)


class LiteratureRequest(BaseModel):
    """Incoming request to run a literature review."""
    topic: str
    model: str = "gemini-2.5-pro"


@app.post("/v1/review/sync")
async def run_review_sync(req: LiteratureRequest) -> dict:
    """Run the literature review synchronously (not recommended for long jobs)."""
    try:
        pipeline = LiteratureReviewPipeline(model=req.model)
        result = await pipeline.run({"topic": req.topic})
        return {"status": "success", "result": result.to_dict()}
    except Exception as exc:
        logger.exception("pipeline_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/v1/review/async")
async def run_review_async(req: LiteratureRequest, bg_tasks: BackgroundTasks) -> dict:
    """Trigger the literature review asynchronously in the background."""
    async def _run():
        try:
            pipeline = LiteratureReviewPipeline(model=req.model)
            await pipeline.run({"topic": req.topic})
        except Exception as exc:
            logger.exception("async_pipeline_failed", error=str(exc))

    bg_tasks.add_task(_run)
    return {"status": "accepted", "message": "Literature review started in background."}


@app.get("/health")
def health_check() -> dict:
    """Healthcheck endpoint for Cloud Run."""
    return {"status": "ok", "service": "literature-pipeline"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
