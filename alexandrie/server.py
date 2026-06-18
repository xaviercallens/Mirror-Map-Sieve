# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""FastAPI Backend Server for the Alexandrie Storage Hub.

Provides documented REST API endpoints for scientific artifact cataloging,
secure open-access/private room segregation, and astrolabe concept alignments.

Endpoints:
  • POST /vault/artifact  — Ingest and store a scientific artifact.
  • GET  /vault/artifact  — Retrieve a specific artifact and its content.
  • GET  /vault/search    — Search the scientific catalog.
  • GET  /vault/astrolabe — Compute astronomical conics alignment on topic.
  • GET  /health          — Server health check and budget ledger overview.

Run locally:
  uvicorn alexandrie.server:app --host 0.0.0.0 --port 8080 --reload
"""

from __future__ import annotations

import os
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field

from alexandrie.hub import AlexandrieHub
from alexandrie.metadata import ArtifactType, RoomType
from agents.hypatie.tools.astrolabe_navigator import navigate_astrolabe

logger = structlog.get_logger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="🏛️ Alexandrie Scientific Artifact Vault API",
    description="Backend server for storing serialized models, Lean 4 proofs, datasets, and scientific papers.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Initialize core hub (supports local directory or GCS mounts)
vault_path = os.getenv("ALEXANDRIE_VAULT_ROOT", "/Users/xcallens/.gemini/antigravity/alexandrie_vault")
enable_semantic = os.getenv("ALEXANDRIE_SEMANTIC_MEMORY", "true").lower() == "true"
embedding_model = os.getenv("ALEXANDRIE_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
hub = AlexandrieHub(
    vault_root=vault_path,
    enable_semantic_memory=enable_semantic,
    embedding_model=embedding_model,
)


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class ArtifactCreate(BaseModel):
    """Schema for creating/storing a new scientific artifact."""

    id: str = Field(..., example="G_Socratique_v4", description="Unique identifier.")
    title: str = Field(..., example="G_Socratique Model Weights", description="Title of the work.")
    payload: str = Field(..., description="The mathematical proof source code, LaTeX, or serialized weights in Base64.")
    artifact_type: str = Field(..., example="proof", description="Type: model, checkpoint, dataset, paper, proof.")
    room_type: str = Field("open_access", example="open_access", description="open_access or private.")
    creator: str = Field("anonymous_scientist", example="galois_agent")
    tags: list[str] = Field(default_factory=list, example=["mathematics", "lean4", "algebra"])
    requirements: list[str] = Field(default_factory=list, example=["import Mathlib.Analysis"])
    metrics: dict[str, Any] = Field(default_factory=dict, example={"conservation_ratio": 1.0})
    dependencies: list[str] = Field(default_factory=list, example=["add_comm_proof"])
    extra_attributes: dict[str, Any] = Field(default_factory=dict)


class SemanticSearchRequest(BaseModel):
    """Schema for semantic similarity search over proof artifacts."""

    lean_state: str = Field(
        ...,
        example="h : x > 0 ⊢ x^2 > 0",
        description="The Lean 4 tactic state to search for similar historical proofs.",
    )
    k: int = Field(3, ge=1, le=20, description="Number of similar results to return.")


class ArtifactResponse(BaseModel):
    """Schema returned for a cataloged artifact."""

    id: str
    title: str
    artifact_type: str
    room_type: str
    creator: str
    timestamp: float
    sha256_hash: str
    tags: list[str]
    metrics: dict[str, Any]
    dependencies: list[str]


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", status_code=status.HTTP_200_OK, tags=["System"])
def health_check() -> dict[str, str]:
    """Retrieve health and serverless cold-start verification metrics."""
    return {
        "status": "healthy",
        "service": "Alexandrie Storage Hub",
        "version": "1.0.0",
        "gcp_optimized": "true",
        "min_replicas": "0 (Serverless Cost Optimized)",
    }


@app.post(
    "/vault/artifact",
    response_model=ArtifactResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Vault Ingestion"],
)
def ingest_artifact(artifact: ArtifactCreate) -> dict[str, Any]:
    """Ingest, catalog, and secure a new scientific artifact in Alexandrie."""
    # Map raw strings to core Enums
    try:
        a_type = ArtifactType[artifact.artifact_type.upper()]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid artifact type. Choose from: model, checkpoint, dataset, paper, proof.",
        )

    try:
        r_type = RoomType[artifact.room_type.upper()]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid room type. Choose from: open_access, private.",
        )

    try:
        metadata = hub.store_artifact(
            artifact_id=artifact.id,
            title=artifact.title,
            content=artifact.payload,
            artifact_type=a_type,
            room_type=r_type,
            creator=artifact.creator,
            tags=artifact.tags,
            requirements=artifact.requirements,
            metrics=artifact.metrics,
            dependencies=artifact.dependencies,
            extra_attributes=artifact.extra_attributes,
        )

        return {
            "id": metadata.id,
            "title": metadata.title,
            "artifact_type": metadata.artifact_type.name,
            "room_type": metadata.room_type.name,
            "creator": metadata.creator,
            "timestamp": metadata.timestamp,
            "sha256_hash": metadata.sha256_hash,
            "tags": metadata.tags,
            "metrics": metadata.metrics,
            "dependencies": metadata.dependencies,
        }

    except Exception as exc:
        logger.error("ingestion_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inward storage failure: {str(exc)}",
        )


@app.get("/vault/artifact/{artifact_id}", tags=["Vault Retrieval"])
def retrieve_artifact(
    artifact_id: str,
    room: str = Query("open_access", description="open_access or private"),
) -> dict[str, Any]:
    """Retrieve artifact content and full scientific metadata."""
    try:
        r_type = RoomType[room.upper()]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid room type. Choose from: open_access, private.",
        )

    res = hub.retrieve_artifact(artifact_id, r_type)
    if res is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{artifact_id}' not found in room '{room}'.",
        )

    metadata, content = res
    return {
        "metadata": {
            "id": metadata.id,
            "title": metadata.title,
            "artifact_type": metadata.artifact_type.name,
            "room_type": metadata.room_type.name,
            "creator": metadata.creator,
            "timestamp": metadata.timestamp,
            "sha256_hash": metadata.sha256_hash,
            "tags": metadata.tags,
            "metrics": metadata.metrics,
            "dependencies": metadata.dependencies,
        },
        "payload": content,
    }


@app.get("/vault/search", tags=["Vault Query"])
def search_vault(
    query: str = Query("", description="Keyword tags, creator or name"),
    room: str | None = Query(None, description="open_access or private"),
    type: str | None = Query(None, description="model, checkpoint, dataset, paper, proof"),
) -> list[dict[str, Any]]:
    """Search for artifacts cataloged in Alexandrie matching keywords."""
    r_type = None
    if room is not None:
        try:
            r_type = RoomType[room.upper()]
        except KeyError:
            pass

    a_type = None
    if type is not None:
        try:
            a_type = ArtifactType[type.upper()]
        except KeyError:
            pass

    results = hub.search_vault(query, r_type, a_type)
    return [
        {
            "id": m.id,
            "title": m.title,
            "artifact_type": m.artifact_type.name,
            "room_type": m.room_type.name,
            "creator": m.creator,
            "timestamp": m.timestamp,
            "sha256_hash": m.sha256_hash,
            "tags": m.tags,
            "metrics": m.metrics,
            "dependencies": m.dependencies,
        }
        for m in results
    ]


@app.get("/vault/astrolabe", tags=["Conceptual Alignments"])
def astrolabe_navigator(
    focus_topic: str = Query("algebraic conics", description="Concept keyword mapping"),
    required_alignment: float = Query(0.30, ge=0.0, le=1.0),
) -> dict[str, Any]:
    """Perform astrolabe-guided conic alignments on stored artifacts."""
    report = navigate_astrolabe(focus_topic, required_alignment)
    
    alignments_serialized = [
        {
            "source_id": a.source_id,
            "target_id": a.target_id,
            "alignment_degree": a.alignment_degree,
            "conic_correlation": a.conic_correlation,
            "philosophical_connection": a.philosophical_connection,
            "suggested_hypothesis": a.suggested_hypothesis,
        }
        for a in report.alignments
    ]

    return {
        "astronomical_zenith": report.astronomical_zenith,
        "alignments": alignments_serialized,
        "astrolabe_suggestions": report.astrolabe_suggestions,
        "elapsed_ms": report.elapsed_ms,
    }


@app.post("/vault/semantic_search", tags=["Semantic Memory"])
def semantic_search(request: SemanticSearchRequest) -> dict[str, Any]:
    """Search for semantically similar proof artifacts using vector embeddings.

    Uses the Alexandrie FAISS-backed memory engine to find historical proofs
    whose Lean 4 tactic states are closest in embedding space to the query.
    Returns similarity scores and the winning tactics for RAG injection.
    """
    if hub.semantic_memory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Semantic memory is not enabled. Set ALEXANDRIE_SEMANTIC_MEMORY=true.",
        )

    results = hub.semantic_search(request.lean_state, k=request.k)
    rag_prompt = hub.get_rag_prompt(request.lean_state, k=request.k)

    return {
        "query": request.lean_state,
        "results": results,
        "rag_prompt": rag_prompt,
        "total_memory_entries": hub.semantic_memory.total_entries,
    }


# ---------------------------------------------------------------------------
# Sentinel Pipeline Endpoint (Spec Phase 4: API Wrap)
# ---------------------------------------------------------------------------

class VerifyRequest(BaseModel):
    """Schema for the /verify endpoint — full Sentinel Pipeline run."""
    source_code: str = Field(..., description="Source code to verify")
    language: str = Field(default="solidity", description="Source language (solidity, python, rust)")
    contract_name: str | None = Field(default=None, description="Override auto-detected contract name")
    run_galois: bool = Field(default=False, description="Run Galois MCTS proof search (requires Lean REPL)")


@app.post("/verify", tags=["Sentinel Pipeline"])
async def verify_contract(request: VerifyRequest) -> dict[str, Any]:
    """Run the full Agora Sentinel verification pipeline.

    **Pipeline stages:**
    1. **Bourbaki** — Translate source code → Lean 4 with sorry-gapped theorems
    2. **Aristotle** — Pre-screen decomposition quality (inside MCTS loop)
    3. **Galois+Euler** — MCTS proof search to close sorry gaps (optional)
    4. **Descartes** — If proof fails, synthesize exploit vector
    5. **Champollion** — Generate executive report (certificate or advisory)

    Returns:
        Structured verification result with Lean code, report, and exploits.
    """
    from agents.sentinel_pipeline import SentinelPipeline

    pipeline = SentinelPipeline()

    try:
        result = await pipeline.run(
            source_code=request.source_code,
            language=request.language,
            contract_name=request.contract_name,
            run_galois=request.run_galois,
        )
        return result.to_dict()
    except Exception as exc:
        logger.error("pipeline_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline execution failed: {exc}",
        )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)

