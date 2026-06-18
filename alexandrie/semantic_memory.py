# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Alexandrie Semantic Memory Engine (Math-RAG).

Provides AST-aware contrastive embedding retrieval for Lean 4 tactic states.
When Galois closes a sorry gap, the winning tactic + state is memorized.
When a new sorry gap is encountered, the top-k semantically similar historical
states are retrieved and injected into the LLM prompt as few-shot RAG examples.

Architecture:
    - Encoder: SentenceTransformer (default: all-MiniLM-L6-v2, swappable for
      a Lean 4-fine-tuned model like ReProver)
    - Index: FAISS IndexFlatIP (cosine similarity via normalized embeddings)
    - Persistence: JSON memory bank + FAISS binary index on disk

Reference: AGORA v4 — THE ALEXANDRIE MEMORY UPGRADE spec.
Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import json
import pathlib
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Lazy imports for heavy dependencies (FAISS, sentence-transformers)
# ---------------------------------------------------------------------------

_faiss = None
_SentenceTransformer = None


def _ensure_faiss():
    global _faiss
    if _faiss is None:
        try:
            import faiss
            _faiss = faiss
        except ImportError:
            raise ImportError(
                "FAISS is required for Alexandrie Semantic Memory. "
                "Install with: pip install faiss-cpu"
            )
    return _faiss


def _ensure_sentence_transformers():
    global _SentenceTransformer
    if _SentenceTransformer is None:
        try:
            from sentence_transformers import SentenceTransformer
            _SentenceTransformer = SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for Alexandrie Semantic Memory. "
                "Install with: pip install sentence-transformers"
            )
    return _SentenceTransformer


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ProofArtifact:
    """A single memorized proof success from the MCTS engine.

    Attributes:
        lean_state: The Lean 4 tactic state at the moment of success.
        informal_blueprint: Human-readable decomposition strategy.
        winning_tactic: The exact Lean 4 tactic string that closed the gap.
        timestamp: Unix epoch when this was memorized.
        source_agent: Name of the agent that discovered this proof.
        metadata: Optional extra context (lemma name, file path, etc.).
    """

    lean_state: str
    informal_blueprint: str
    winning_tactic: str
    timestamp: float = field(default_factory=time.time)
    source_agent: str = "galois"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "lean_state": self.lean_state,
            "informal_blueprint": self.informal_blueprint,
            "winning_tactic": self.winning_tactic,
            "timestamp": self.timestamp,
            "source_agent": self.source_agent,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ProofArtifact:
        return cls(
            lean_state=d["lean_state"],
            informal_blueprint=d["informal_blueprint"],
            winning_tactic=d["winning_tactic"],
            timestamp=d.get("timestamp", 0.0),
            source_agent=d.get("source_agent", "unknown"),
            metadata=d.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# Alexandrie Semantic Memory Engine
# ---------------------------------------------------------------------------

class AlexandrieMemory:
    """FAISS-backed semantic vector memory for Lean 4 proof artifacts.

    The encoder converts Lean 4 tactic states into dense vectors.
    Cosine similarity search retrieves the most relevant historical proofs.

    Args:
        model_name: HuggingFace model ID for the sentence encoder.
            Default: 'all-MiniLM-L6-v2' (384-dim, fast, free).
            For production: swap to a Lean 4-fine-tuned model.
        persist_dir: Directory for saving the FAISS index and memory bank.
            If None, memory is ephemeral (lost on process exit).
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        persist_dir: str | pathlib.Path | None = None,
    ) -> None:
        SentenceTransformer = _ensure_sentence_transformers()
        faiss = _ensure_faiss()

        self._model_name = model_name
        self.encoder = SentenceTransformer(model_name)
        self._dim = self.encoder.get_sentence_embedding_dimension()

        # FAISS Inner Product index (cosine similarity with normalized vectors)
        self.index = faiss.IndexFlatIP(self._dim)
        self.memory_bank: list[ProofArtifact] = []

        self._persist_dir: pathlib.Path | None = None
        if persist_dir is not None:
            self._persist_dir = pathlib.Path(persist_dir)
            self._persist_dir.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

        self._log = logger.bind(component="alexandrie_memory", model=model_name)
        self._log.info(
            "memory_initialized",
            dim=self._dim,
            entries=len(self.memory_bank),
            persist=str(self._persist_dir),
        )

    # ------ Core API -------------------------------------------------------

    def memorize_success(
        self,
        lean_state: str,
        informal_blueprint: str,
        winning_tactic: str,
        source_agent: str = "galois",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Memorize a successful proof closure.

        Called every time the MCTS engine successfully closes a sorry gap.

        Args:
            lean_state: The Lean 4 tactic state (e.g., 'h : x > 0 ⊢ x^2 > 0').
            informal_blueprint: English description of the strategy.
            winning_tactic: The exact tactic string that closed the gap.
            source_agent: Which agent discovered this proof.
            metadata: Optional extra context.
        """
        # Encode and normalize for cosine similarity
        vector = self.encoder.encode(
            lean_state, normalize_embeddings=True
        ).astype(np.float32)

        self.index.add(np.array([vector]))

        artifact = ProofArtifact(
            lean_state=lean_state,
            informal_blueprint=informal_blueprint,
            winning_tactic=winning_tactic,
            source_agent=source_agent,
            metadata=metadata or {},
        )
        self.memory_bank.append(artifact)

        self._log.info(
            "proof_memorized",
            tactic=winning_tactic[:60],
            total_entries=len(self.memory_bank),
        )

        # Auto-persist if configured
        if self._persist_dir is not None:
            self._save_to_disk()

    def retrieve_collaborative_hints(
        self,
        current_lean_state: str,
        k: int = 3,
        min_similarity: float = 0.3,
    ) -> str:
        """Retrieve RAG-augmented hints from historical proof memory.

        Called by Galois before querying the LLM for new tactics.

        Args:
            current_lean_state: The current Lean 4 tactic state with sorry gap.
            k: Number of similar historical states to retrieve.
            min_similarity: Minimum cosine similarity threshold.

        Returns:
            A formatted RAG injection string for the LLM prompt.
            Empty string if memory is empty.
        """
        if self.index.ntotal == 0:
            return ""

        # Clamp k to available entries
        k = min(k, self.index.ntotal)

        query_vector = self.encoder.encode(
            current_lean_state, normalize_embeddings=True
        ).astype(np.float32)

        distances, indices = self.index.search(
            np.array([query_vector]), k
        )

        rag_prompt = "\n[ALEXANDRIE HISTORICAL MEMORY INJECTION]\n"
        rag_prompt += (
            "The engine previously solved semantically similar "
            "mathematical states:\n\n"
        )

        hits = 0
        for sim, idx in zip(distances[0], indices[0]):
            if idx == -1 or sim < min_similarity:
                continue
            past = self.memory_bank[idx]
            rag_prompt += f"--- Similar Past State (similarity={sim:.3f}) ---\n"
            rag_prompt += f"State: {past.lean_state}\n"
            rag_prompt += f"Blueprint: {past.informal_blueprint}\n"
            rag_prompt += f"Winning Tactic: {past.winning_tactic}\n\n"
            hits += 1

        if hits == 0:
            return ""

        rag_prompt += (
            "INSTRUCTION: Adapt these historical tactics as structural "
            "inspiration for the current state. Do not copy verbatim — "
            "adapt variable names and proof context.\n"
        )

        self._log.info(
            "rag_retrieved",
            hits=hits,
            top_similarity=float(distances[0][0]),
        )

        return rag_prompt

    def retrieve_collaborative_tactics(
        self,
        current_lean_state: str,
        k: int = 3,
        min_similarity: float = 0.3,
    ) -> list[str]:
        """Retrieve raw tactics from semantically similar historical proof states.
        
        Avoids paragraph wrapping and returns actionable tactics directly.
        """
        if self.index.ntotal == 0:
            return []

        k = min(k, self.index.ntotal)

        query_vector = self.encoder.encode(
            current_lean_state, normalize_embeddings=True
        ).astype(np.float32)

        distances, indices = self.index.search(
            np.array([query_vector]), k
        )

        tactics = []
        for sim, idx in zip(distances[0], indices[0]):
            if idx == -1 or sim < min_similarity:
                continue
            past = self.memory_bank[idx]
            tactics.append(past.winning_tactic)

        return tactics

    def search_similar(
        self,
        query_state: str,
        k: int = 5,
    ) -> list[tuple[float, ProofArtifact]]:
        """Raw similarity search returning (score, artifact) pairs.

        Args:
            query_state: Lean 4 state to search for.
            k: Number of results.

        Returns:
            List of (similarity_score, ProofArtifact) tuples.
        """
        if self.index.ntotal == 0:
            return []

        k = min(k, self.index.ntotal)
        query_vector = self.encoder.encode(
            query_state, normalize_embeddings=True
        ).astype(np.float32)

        distances, indices = self.index.search(np.array([query_vector]), k)

        results = []
        for sim, idx in zip(distances[0], indices[0]):
            if idx != -1:
                results.append((float(sim), self.memory_bank[idx]))
        return results

    # ------ Persistence ----------------------------------------------------

    def _save_to_disk(self) -> None:
        """Persist FAISS index and memory bank to disk."""
        if self._persist_dir is None:
            return

        faiss = _ensure_faiss()

        index_path = self._persist_dir / "alexandrie.faiss"
        bank_path = self._persist_dir / "memory_bank.json"

        faiss.write_index(self.index, str(index_path))
        bank_path.write_text(
            json.dumps(
                [a.to_dict() for a in self.memory_bank],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        self._log.debug(
            "memory_persisted",
            entries=len(self.memory_bank),
            path=str(self._persist_dir),
        )

    def _load_from_disk(self) -> None:
        """Load FAISS index and memory bank from disk if available."""
        if self._persist_dir is None:
            return

        faiss = _ensure_faiss()

        index_path = self._persist_dir / "alexandrie.faiss"
        bank_path = self._persist_dir / "memory_bank.json"

        if index_path.exists() and bank_path.exists():
            try:
                self.index = faiss.read_index(str(index_path))
                raw = json.loads(bank_path.read_text(encoding="utf-8"))
                self.memory_bank = [ProofArtifact.from_dict(d) for d in raw]
                self._log.info(
                    "memory_loaded_from_disk",
                    entries=len(self.memory_bank),
                )
            except Exception as exc:
                self._log.error("failed_to_load_memory", error=str(exc))

    # ------ Introspection --------------------------------------------------

    @property
    def total_entries(self) -> int:
        """Number of proof artifacts in memory."""
        return len(self.memory_bank)

    @property
    def embedding_dim(self) -> int:
        """Dimensionality of the embedding vectors."""
        return self._dim

    def __repr__(self) -> str:
        return (
            f"<AlexandrieMemory model={self._model_name!r} "
            f"entries={self.total_entries} dim={self._dim}>"
        )
