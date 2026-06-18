# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Alexandrie Core Storage Hub Implementation.

Handles storage segregation, cryptographic hashing, metadata logging,
retrieval of model checkpoints, proofs, and datasets, and
semantic vector search via the AlexandrieMemory engine.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import time
from typing import Any

import structlog

from alexandrie.metadata import ArtifactMetadata, ArtifactType, RoomType
from alexandrie.science_library import ScienceLibrary
from alexandrie.semantic_memory import AlexandrieMemory

logger = structlog.get_logger(__name__)


class AlexandrieHub:
    """The Alexandrie Hub engine for scientific artifact storage and retrieval.

    Manages two main directories (Open Access vs. Private Vaults) and
    ensures hash-based file integrity and metadata cataloging.
    """

    def __init__(
        self,
        vault_root: str | None = None,
        enable_semantic_memory: bool = True,
        embedding_model: str = "all-MiniLM-L6-v2",
    ) -> None:
        self.bucket_name = os.environ.get("AGORA_VAULT_BUCKET", "socrateai-alexandrie-vault")
        self.gcs_client = None
        self.bucket = None
        
        try:
            from google.cloud import storage
            self.gcs_client = storage.Client()
            self.bucket = self.gcs_client.bucket(self.bucket_name)
        except Exception as exc:
            logger.warning("gcs_alexandrie_init_failed", error=str(exc))
        
        # Local cache for hot artifacts and semantic index
        self.local_cache = pathlib.Path("/tmp/alexandrie_cache")
        self.local_cache.mkdir(parents=True, exist_ok=True)
        
        self._log = logger.bind(component="alexandrie_hub", bucket=self.bucket_name)
        self._catalog_path = self.local_cache / "catalog.json"
        self._catalog: dict[str, dict[str, Any]] = self._load_catalog()

        # Semantic vector memory (Math-RAG)
        self.semantic_memory: AlexandrieMemory | None = None
        if enable_semantic_memory:
            try:
                mem_dir = self.local_cache / "semantic_index"
                self.semantic_memory = AlexandrieMemory(
                    model_name=embedding_model,
                    persist_dir=str(mem_dir),
                )
                self._log.info(
                    "semantic_memory_enabled",
                    model=embedding_model,
                    entries=self.semantic_memory.total_entries,
                )
            except ImportError as exc:
                self._log.warning(
                    "semantic_memory_disabled",
                    reason=str(exc),
                )
                self.semantic_memory = None

        # Science Library (checkpointing + agent memory)
        self._science_library: ScienceLibrary | None = None

    @property
    def science_library(self) -> ScienceLibrary:
        """Lazily-initialized Science Library for checkpointing and agent memory."""
        if self._science_library is None:
            self._science_library = ScienceLibrary(bucket=self.bucket)
        return self._science_library

    def _load_catalog(self) -> dict[str, dict[str, Any]]:
        """Load the catalog metadata index from GCS."""
        if self.bucket:
            try:
                blob = self.bucket.blob("catalog.json")
                if blob.exists():
                    content = blob.download_as_text()
                    # Cache locally
                    self._catalog_path.write_text(content, encoding="utf-8")
                    return json.loads(content)
            except Exception as exc:
                self._log.error("failed_to_load_catalog_from_gcs", error=str(exc))
                
        # Fallback to local cache
        if self._catalog_path.exists():
            try:
                return json.loads(self._catalog_path.read_text(encoding="utf-8"))
            except Exception as exc:
                self._log.error("failed_to_load_local_catalog", error=str(exc))
        return {}

    def _save_catalog(self) -> None:
        """Write the catalog metadata index to disk and GCS."""
        content = json.dumps(self._catalog, indent=2, ensure_ascii=False)
        try:
            self._catalog_path.write_text(content, encoding="utf-8")
        except Exception as exc:
            self._log.error("failed_to_save_local_catalog", error=str(exc))
            
        if self.bucket:
            try:
                blob = self.bucket.blob("catalog.json")
                blob.upload_from_string(content, content_type="application/json")
            except Exception as exc:
                self._log.error("failed_to_save_catalog_to_gcs", error=str(exc))

    def _get_target_prefix(self, room_type: RoomType) -> str:
        """Get the GCS path prefix for the given room type."""
        return "private" if room_type == RoomType.PRIVATE else "open_access"

    def store_artifact(
        self,
        artifact_id: str,
        title: str,
        content: str | bytes,
        artifact_type: ArtifactType,
        room_type: RoomType,
        creator: str,
        tags: list[str] | None = None,
        requirements: list[str] | None = None,
        metrics: dict[str, Any] | None = None,
        dependencies: list[str] | None = None,
        extra_attributes: dict[str, Any] | None = None,
    ) -> ArtifactMetadata:
        """Store an artifact securely in the specified room in Alexandrie.

        Args:
            artifact_id: Unique artifact identifier (e.g., "G_Socratique_v4").
            title: Plain English title.
            content: Payload data as text or bytes.
            artifact_type: Artifact category classification.
            room_type: OPEN_ACCESS or PRIVATE room placement.
            creator: Name of the agent or scientist creating it.
            tags: Descriptive tag strings.
            requirements: Necessary system imports or prerequisites.
            metrics: Empirical evaluation statistics.
            dependencies: List of related artifact IDs.
            extra_attributes: Custom key-value pairs.

        Returns:
            Recorded :class:`ArtifactMetadata`.
        """
        # Calculate SHA256 of payload
        payload_bytes = content if isinstance(content, bytes) else content.encode("utf-8")
        sha256 = hashlib.sha256(payload_bytes).hexdigest()

        metadata = ArtifactMetadata(
            id=artifact_id,
            title=title,
            artifact_type=artifact_type,
            room_type=room_type,
            creator=creator,
            timestamp=time.time(),
            sha256_hash=sha256,
            tags=tags or [],
            requirements=requirements or [],
            metrics=metrics or {},
            dependencies=dependencies or [],
            extra_attributes=extra_attributes or {},
        )

        # Determine GCS path
        prefix = f"{self._get_target_prefix(room_type)}/{artifact_type.name.lower()}"
        file_name = f"{artifact_id}.bin" if isinstance(content, bytes) else f"{artifact_id}.txt"
        gcs_path = f"{prefix}/{file_name}"
        
        # Local cache path
        local_dir = self.local_cache / prefix
        local_dir.mkdir(parents=True, exist_ok=True)
        local_path = local_dir / file_name
        # Ensure parent dirs exist for nested artifact IDs (e.g., discovery/RUN_ID/conjecture_001)
        local_path.parent.mkdir(parents=True, exist_ok=True)

        # Write payload locally
        if isinstance(content, bytes):
            local_path.write_bytes(content)
        else:
            local_path.write_text(content, encoding="utf-8")
            
        # Upload to GCS
        if self.bucket:
            try:
                blob = self.bucket.blob(gcs_path)
                if isinstance(content, bytes):
                    blob.upload_from_string(content, content_type="application/octet-stream")
                else:
                    blob.upload_from_string(content, content_type="text/plain")
            except Exception as exc:
                self._log.error("failed_to_upload_artifact_to_gcs", error=str(exc))

        # Record in catalog
        self._catalog[artifact_id] = {
            "id": metadata.id,
            "title": metadata.title,
            "artifact_type": metadata.artifact_type.name,
            "room_type": metadata.room_type.name,
            "creator": metadata.creator,
            "timestamp": metadata.timestamp,
            "sha256_hash": metadata.sha256_hash,
            "tags": metadata.tags,
            "requirements": metadata.requirements,
            "metrics": metadata.metrics,
            "dependencies": metadata.dependencies,
            "extra_attributes": metadata.extra_attributes,
            "gcs_path": gcs_path,
            "file_path": str(local_path), # fallback
        }
        self._save_catalog()

        # Auto-index proof artifacts into the semantic memory
        if (
            self.semantic_memory is not None
            and artifact_type == ArtifactType.PROOF
            and isinstance(content, str)
        ):
            blueprint = (extra_attributes or {}).get("blueprint", title)
            tactic = (extra_attributes or {}).get("winning_tactic", "")
            self.semantic_memory.memorize_success(
                lean_state=content,
                informal_blueprint=blueprint,
                winning_tactic=tactic,
                source_agent=creator,
                metadata={"artifact_id": artifact_id, "tags": tags or []},
            )

        self._log.info(
            "artifact_stored",
            id=artifact_id,
            type=artifact_type.name,
            room=room_type.name,
            sha256=sha256[:8],
        )
        return metadata

    def store_symposium_package(
        self,
        symposium_id: str,
        title: str,
        pdf_bytes: bytes,
        tex_content: str,
        audit_jsonl: str,
        simulation_figures: list[str],
        lean_theorems: list[str],
        creator: str,
        room_type: RoomType = RoomType.OPEN_ACCESS,
        owner_email: str = "",
    ) -> list[ArtifactMetadata]:
        """Store a complete Symposium run package in Alexandrie.

        Each component is stored as a separate artifact with cross-references
        linking them all under the same symposium run. All artifacts are
        uploaded to the ``symposium/{symposium_id}/`` GCS prefix.

        Args:
            symposium_id: Unique run identifier (e.g., ``sym_20260612_080000``).
            title: Human-readable Symposium title.
            pdf_bytes: Compiled PDF monograph bytes.
            tex_content: Raw LaTeX source of the monograph.
            audit_jsonl: Newline-delimited JSON audit trail string.
            simulation_figures: List of local paths to simulation figure files.
            lean_theorems: List of Lean 4 theorem source strings.
            creator: Agent or pipeline name that produced the package.
            room_type: OPEN_ACCESS or PRIVATE room placement.
            owner_email: E-mail of the human owner for access control.

        Returns:
            List of :class:`ArtifactMetadata` for every stored component.
        """
        results: list[ArtifactMetadata] = []
        prefix = f"symposium/{symposium_id}"
        common_extra = {
            "symposium_id": symposium_id,
            "owner_email": owner_email,
            "gcs_prefix": prefix,
        }

        # ── 1. PDF monograph ─────────────────────────────────────────
        pdf_meta = self.store_artifact(
            artifact_id=f"{prefix}/monograph.pdf",
            title=f"{title} — PDF Monograph",
            content=pdf_bytes,
            artifact_type=ArtifactType.MONOGRAPH,
            room_type=room_type,
            creator=creator,
            tags=["symposium", "monograph", "pdf"],
            extra_attributes={**common_extra, "format": "application/pdf"},
        )
        results.append(pdf_meta)

        # ── 2. LaTeX source ──────────────────────────────────────────
        tex_meta = self.store_artifact(
            artifact_id=f"{prefix}/monograph.tex",
            title=f"{title} — LaTeX Source",
            content=tex_content,
            artifact_type=ArtifactType.MONOGRAPH,
            room_type=room_type,
            creator=creator,
            tags=["symposium", "monograph", "latex"],
            dependencies=[pdf_meta.id],
            extra_attributes={**common_extra, "format": "application/x-latex"},
        )
        results.append(tex_meta)

        # ── 3. Audit trail ───────────────────────────────────────────
        audit_meta = self.store_artifact(
            artifact_id=f"{prefix}/audit_trail.jsonl",
            title=f"{title} — Scientific Audit Trail",
            content=audit_jsonl,
            artifact_type=ArtifactType.AUDIT_TRAIL,
            room_type=room_type,
            creator=creator,
            tags=["symposium", "audit", "jsonl"],
            dependencies=[pdf_meta.id],
            extra_attributes={
                **common_extra,
                "format": "application/x-ndjson",
                "entry_count": len(audit_jsonl.strip().splitlines()),
            },
        )
        results.append(audit_meta)

        # ── 4. Simulation figures ────────────────────────────────────
        for idx, fig_path in enumerate(simulation_figures):
            fig_name = pathlib.Path(fig_path).name
            try:
                fig_bytes = pathlib.Path(fig_path).read_bytes()
            except OSError as exc:
                self._log.warning(
                    "symposium_figure_read_failed",
                    path=fig_path,
                    error=str(exc),
                )
                continue

            fig_meta = self.store_artifact(
                artifact_id=f"{prefix}/figures/{fig_name}",
                title=f"{title} — Simulation Figure {idx + 1}",
                content=fig_bytes,
                artifact_type=ArtifactType.SIMULATION,
                room_type=room_type,
                creator=creator,
                tags=["symposium", "simulation", "figure"],
                dependencies=[pdf_meta.id],
                extra_attributes={
                    **common_extra,
                    "figure_index": idx,
                    "source_path": fig_path,
                },
            )
            results.append(fig_meta)

        # ── 5. Lean 4 theorems ───────────────────────────────────────
        for idx, theorem_src in enumerate(lean_theorems):
            thm_meta = self.store_artifact(
                artifact_id=f"{prefix}/lean4/theorem_{idx:03d}.lean",
                title=f"{title} — Lean 4 Theorem {idx + 1}",
                content=theorem_src,
                artifact_type=ArtifactType.PROOF,
                room_type=room_type,
                creator=creator,
                tags=["symposium", "lean4", "theorem"],
                dependencies=[pdf_meta.id],
                extra_attributes={
                    **common_extra,
                    "theorem_index": idx,
                    "has_sorry": "sorry" in theorem_src,
                },
            )
            results.append(thm_meta)

        # ── 6. Symposium package manifest ────────────────────────────
        manifest_meta = self.store_artifact(
            artifact_id=f"{prefix}/manifest.json",
            title=f"{title} — Symposium Package Manifest",
            content=json.dumps(
                {
                    "symposium_id": symposium_id,
                    "title": title,
                    "creator": creator,
                    "owner_email": owner_email,
                    "room_type": room_type.name,
                    "artifact_ids": [m.id for m in results],
                    "component_count": len(results),
                },
                indent=2,
            ),
            artifact_type=ArtifactType.SYMPOSIUM,
            room_type=room_type,
            creator=creator,
            tags=["symposium", "manifest"],
            dependencies=[m.id for m in results],
            extra_attributes=common_extra,
        )
        results.append(manifest_meta)

        self._log.info(
            "symposium_package_stored",
            symposium_id=symposium_id,
            component_count=len(results),
            owner=owner_email,
        )
        return results

    def retrieve_artifact(
        self,
        artifact_id: str,
        room_type: RoomType | None = None,
    ) -> tuple[ArtifactMetadata, str | bytes] | None:
        """Retrieve an artifact and its metadata.

        Args:
            artifact_id: The artifact's unique ID.
            room_type: Optional room type filter.

        Returns:
            Tuple of (Metadata, content) or None if not found.
        """
        entry = self._catalog.get(artifact_id)
        if entry is None:
            return None

        # Filter by room type if requested
        if room_type is not None and entry["room_type"] != room_type.name:
            return None

        # Load content from GCS or local cache
        gcs_path = entry.get("gcs_path")
        local_path = pathlib.Path(entry["file_path"])
        
        content = None
        if self.bucket and gcs_path:
            try:
                blob = self.bucket.blob(gcs_path)
                if blob.exists():
                    if gcs_path.endswith(".bin"):
                        content = blob.download_as_bytes()
                    else:
                        content = blob.download_as_text(encoding="utf-8")
            except Exception as exc:
                self._log.error("failed_to_download_from_gcs", path=gcs_path, error=str(exc))
                
        if content is None:
            if not local_path.exists():
                self._log.error("file_missing_from_vault", id=artifact_id, path=str(local_path))
                return None
            if local_path.suffix == ".bin":
                content = local_path.read_bytes()
            else:
                content = local_path.read_text(encoding="utf-8")

        # Construct metadata
        metadata = ArtifactMetadata(
            id=entry["id"],
            title=entry["title"],
            artifact_type=ArtifactType[entry["artifact_type"]],
            room_type=RoomType[entry["room_type"]],
            creator=entry["creator"],
            timestamp=entry["timestamp"],
            sha256_hash=entry["sha256_hash"],
            tags=entry["tags"],
            requirements=entry["requirements"],
            metrics=entry["metrics"],
            dependencies=entry["dependencies"],
            extra_attributes=entry["extra_attributes"],
        )

        return metadata, content

    def search_vault(
        self,
        query: str,
        room_type: RoomType | None = None,
        artifact_type: ArtifactType | None = None,
    ) -> list[ArtifactMetadata]:
        """Search the vault for matching metadata.

        Args:
            query: Keyword search string matching title, creator, tags, etc.
            room_type: Filter by room type (OPEN_ACCESS/PRIVATE).
            artifact_type: Filter by category.

        Returns:
            List of matching :class:`ArtifactMetadata` entries.
        """
        query_lower = query.lower()
        results = []

        for entry in self._catalog.values():
            if room_type is not None and entry["room_type"] != room_type.name:
                continue
            if artifact_type is not None and entry["artifact_type"] != artifact_type.name:
                continue

            matches = (
                query_lower in entry["id"].lower()
                or query_lower in entry["title"].lower()
                or query_lower in entry["creator"].lower()
                or any(query_lower in t.lower() for t in entry["tags"])
            )

            if matches:
                metadata = ArtifactMetadata(
                    id=entry["id"],
                    title=entry["title"],
                    artifact_type=ArtifactType[entry["artifact_type"]],
                    room_type=RoomType[entry["room_type"]],
                    creator=entry["creator"],
                    timestamp=entry["timestamp"],
                    sha256_hash=entry["sha256_hash"],
                    tags=entry["tags"],
                    requirements=entry["requirements"],
                    metrics=entry["metrics"],
                    dependencies=entry["dependencies"],
                    extra_attributes=entry["extra_attributes"],
                )
                results.append(metadata)

        return results

    def semantic_search(
        self,
        query_state: str,
        k: int = 3,
    ) -> list[dict[str, Any]]:
        """Semantic similarity search over proof artifacts.

        Uses the AlexandrieMemory FAISS index to find the top-k
        most semantically similar historical proof states.

        Args:
            query_state: Lean 4 tactic state to search for.
            k: Number of results to return.

        Returns:
            List of dicts with 'similarity', 'lean_state', 'blueprint',
            'winning_tactic', and 'source_agent' keys.
        """
        if self.semantic_memory is None:
            return []

        results = self.semantic_memory.search_similar(query_state, k=k)
        return [
            {
                "similarity": score,
                "lean_state": artifact.lean_state,
                "blueprint": artifact.informal_blueprint,
                "winning_tactic": artifact.winning_tactic,
                "source_agent": artifact.source_agent,
                "metadata": artifact.metadata,
            }
            for score, artifact in results
        ]

    def get_rag_prompt(self, current_state: str, k: int = 3) -> str:
        """Get a formatted RAG injection prompt for the MCTS engine.

        Args:
            current_state: The current Lean 4 tactic state.
            k: Number of similar historical states to retrieve.

        Returns:
            Formatted string for LLM prompt injection, or empty string.
        """
        if self.semantic_memory is None:
            return ""
        return self.semantic_memory.retrieve_collaborative_hints(current_state, k=k)

    def get_rag_tactics(self, current_state: str, k: int = 3) -> list[str]:
        """Get actionable tactics directly from semantic memory.
        
        Args:
            current_state: The current Lean 4 tactic state.
            k: Number of similar historical states to retrieve.
            
        Returns:
            List of actionable tactic strings.
        """
        if self.semantic_memory is None:
            return []
        return self.semantic_memory.retrieve_collaborative_tactics(current_state, k=k)
