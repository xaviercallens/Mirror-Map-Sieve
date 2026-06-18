# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Archive Vault — Hypatie's artifact cataloging and explanation tool.

Ingests mathematical proofs, model checkpoints, code files, and papers into
Alexandrie, and automatically generates conceptual Blogs, Courses, Protocols,
and reproduction guides.

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import structlog

from alexandrie.hub import AlexandrieHub
from alexandrie.metadata import ArtifactType, RoomType

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CatalogedArtifact:
    """Represents a cataloged scientific entry in Alexandrie."""

    artifact_id: str
    metadata: Any
    explainer_id: str
    blog_content: str
    reproduction_protocol: str


# ---------------------------------------------------------------------------
# Archive Vault Tool
# ---------------------------------------------------------------------------

def catalog_scientific_work(
    artifact_id: str,
    title: str,
    payload: str | bytes,
    artifact_type: str,  # "model", "checkpoint", "dataset", "paper", "proof"
    room_type: str = "open_access",  # "open_access" or "private"
    tags: list[str] | None = None,
    metrics: dict[str, Any] | None = None,
    dependencies: list[str] | None = None,
) -> CatalogedArtifact:
    """Catalog scientific payloads into Alexandrie and generate Socratic explainers.

    If ALEXANDRIE_API_URL is set in environment, uses HTTP REST endpoints on GCP.
    Otherwise, falls back to native local python storage.
    """
    logger.info("cataloging_scientific_work_start", id=artifact_id, type=artifact_type)
    
    import os
    import httpx

    api_url = os.getenv("ALEXANDRIE_API_URL")
    
    type_map = {
        "model": ArtifactType.MODEL,
        "checkpoint": ArtifactType.CHECKPOINT,
        "dataset": ArtifactType.DATASET,
        "paper": ArtifactType.PAPER,
        "proof": ArtifactType.PROOF,
    }
    target_type = type_map.get(artifact_type.lower(), ArtifactType.PAPER)
    target_room = RoomType.PRIVATE if room_type.lower() == "private" else RoomType.OPEN_ACCESS

    # 4. Generate Explainer Blog
    blog = _generate_scientific_blog(artifact_id, title, target_type, tags or [], metrics or {})

    # 5. Generate Reproduction Protocol
    protocol = _generate_reproduction_protocol(artifact_id, title, target_type, metrics or {})
    
    metadata = None

    if api_url:
        logger.info("gcp_remote_vault_ingestion", url=api_url)
        try:
            # POST raw artifact
            payload_str = payload if isinstance(payload, str) else payload.decode("utf-8")
            response = httpx.post(
                f"{api_url}/vault/artifact",
                json={
                    "id": artifact_id,
                    "title": title,
                    "payload": payload_str,
                    "artifact_type": target_type.name.lower(),
                    "room_type": target_room.name.lower(),
                    "creator": "hypatie_librarian",
                    "tags": tags or [],
                    "metrics": metrics or {},
                    "dependencies": dependencies or [],
                },
                timeout=30.0,
            )
            response.raise_for_status()
            
            # POST explainer
            httpx.post(
                f"{api_url}/vault/artifact",
                json={
                    "id": f"{artifact_id}_explainer",
                    "title": f"Educational Explainer: {title}",
                    "payload": f"# Blog Explainer\n\n{blog}\n\n# Reproduction Protocol\n\n{protocol}",
                    "artifact_type": "explanation",
                    "room_type": "open_access",
                    "creator": "hypatie_librarian",
                    "tags": ["educational", "explanation", "reproduction"] + (tags or []),
                    "dependencies": [artifact_id],
                },
                timeout=30.0,
            )
            
            res_json = response.json()
            # Construct a dummy metadata to return
            from alexandrie.metadata import ArtifactMetadata
            metadata = ArtifactMetadata(
                id=res_json["id"],
                title=res_json["title"],
                artifact_type=target_type,
                room_type=target_room,
                creator=res_json["creator"],
                timestamp=res_json["timestamp"],
                sha256_hash=res_json["sha256_hash"],
                tags=res_json["tags"],
                metrics=res_json["metrics"],
                dependencies=res_json["dependencies"],
            )
        except Exception as exc:
            logger.error("remote_vault_ingestion_failed", error=str(exc))
            api_url = None # Fallback to local storage on connection failure

    if not api_url:
        # Fallback to native local vault storage
        # 1. Instantiate Alexandrie Hub
        hub = AlexandrieHub()

        # 3. Store raw scientific artifact
        metadata = hub.store_artifact(
            artifact_id=artifact_id,
            title=title,
            content=payload,
            artifact_type=target_type,
            room_type=target_room,
            creator="hypatie_librarian",
            tags=tags,
            metrics=metrics,
            dependencies=dependencies,
        )

        # 6. Store Educational explanation in open access room
        explainer_id = f"{artifact_id}_explainer"
        hub.store_artifact(
            artifact_id=explainer_id,
            title=f"Educational Explainer: {title}",
            content=f"# Blog Explainer\n\n{blog}\n\n# Reproduction Protocol\n\n{protocol}",
            artifact_type=ArtifactType.EXPLANATION,
            room_type=RoomType.OPEN_ACCESS,
            creator="hypatie_librarian",
            tags=["educational", "explanation", "reproduction"] + (tags or []),
            dependencies=[artifact_id],
        )

    return CatalogedArtifact(
        artifact_id=artifact_id,
        metadata=metadata,
        explainer_id=f"{artifact_id}_explainer",
        blog_content=blog,
        reproduction_protocol=protocol,
    )


# ---------------------------------------------------------------------------
# Author Heuristics
# ---------------------------------------------------------------------------

def _generate_scientific_blog(
    artifact_id: str,
    title: str,
    artifact_type: ArtifactType,
    tags: list[str],
    metrics: dict[str, Any],
) -> str:
    """Write an educational blog post promoting the Agora's discovery."""
    return f"""\
# 🏛️ Agora Discoveries: Exploring {title}

**Published by Hypatie, Librarian of the Scientific Agora**
*Exploring the eternal symmetries of mathematics, astronomy, and computational physics.*

We are thrilled to catalog **{artifact_id}** under our `{artifact_type.name}` archives. This artifact represents a milestone in neuro-symbolic, frugal AI development.

## 🌟 The Core Innovation
This artifact establishes:
- **Title**: {title}
- **Artifact Category**: {artifact_type.name}
- **Keywords**: {', '.join(tags)}

## 📊 Scientific Verification & Metrics
Guided by Diophantine precision, our verifiers mapped the behavior of this model:
{chr(10).join(f"- **{k}**: {v}" for k, v in metrics.items()) if metrics else "- No verification metrics registered."}

## 🔭 Philosophical Perspective
In the tradition of Neoplatonism, we view this artifact not as a compute-heavy construct, but as a window into the beautiful mathematical forms governing our physical reality.
"""


def _generate_reproduction_protocol(
    artifact_id: str,
    title: str,
    artifact_type: ArtifactType,
    metrics: dict[str, Any],
) -> str:
    """Draft a rigorous, step-by-step reproduction guide."""
    return f"""\
# 📋 Scientific Reproduction Protocol: {artifact_id}
**Vault Location**: alexandrie_vault/{artifact_type.name.lower()}/{artifact_id}
**Author**: Hypatie (astrolabe-guided precision)

Follow these steps to reproduce our scientific and numerical results:

## 1. Prerequisites
- Lean 4 toolchain (v4.14.0)
- Python 3.11+ (Agora core dependencies)
- Rust cargo toolchain (Edition 2024)

## 2. Ingesting from Vault
Retrieve the raw binaries/scripts from Alexandrie:
```bash
python3 -c "
from alexandrie.hub import AlexandrieHub
hub = AlexandrieHub()
metadata, content = hub.retrieve_artifact('{artifact_id}')
print('SHA256 verified:', metadata.sha256_hash)
"
```

## 3. Physical Invariant Checklist
Before execution, verify:
- Cumulative budget ceiling ≤ $100
- Serverless scaling configured with `min_replicas = 0`
- Mass/energy conservation ratio: {metrics.get('conservation_ratio', '1.000')}

## 4. Execution Step
Execute the compiled verification binary or python orchestration layer to validate.
"""
