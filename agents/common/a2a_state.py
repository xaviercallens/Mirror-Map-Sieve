# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Firestore-backed A2A task state store.

Provides lightweight persistence for async A2A Claim Check tasks.
When running outside GCP (local dev / CI), falls back to an in-memory
store so tests can run without a real Firestore connection.
"""

from __future__ import annotations

import os
import time
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# In-memory fallback store (used in tests / local dev)
# ---------------------------------------------------------------------------

_IN_MEMORY_STORE: dict[str, dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# Firestore helpers
# ---------------------------------------------------------------------------

def _get_firestore_client():
    """Return a Firestore async client, or None if unavailable."""
    try:
        from google.cloud import firestore  # type: ignore[import]
        return firestore.AsyncClient()
    except Exception as exc:
        logger.warning("firestore_client_unavailable", error=str(exc))
        return None


async def create_task(
    task_id: str,
    agent: str,
    prompt: str,
    context_uri: str | None = None,
) -> None:
    """Create a new task record in Firestore (or in-memory fallback).

    Args:
        task_id: Unique task identifier (typically a UUID).
        agent: Name of the target agent (e.g. "Galois").
        prompt: Task description string.
        context_uri: Optional GCS URI for large context payload.
    """
    doc = {
        "task_id": task_id,
        "agent": agent,
        "prompt": prompt,
        "context_uri": context_uri,
        "status": "accepted",
        "created_at": time.time(),
        "updated_at": time.time(),
        "result": None,
        "error": None,
    }

    use_firestore = os.getenv("FIRESTORE_ENABLED", "0") == "1"
    if use_firestore:
        client = _get_firestore_client()
        if client:
            await client.collection("a2a_tasks").document(task_id).set(doc)
            logger.info("a2a_task_created_firestore", task_id=task_id, agent=agent)
            return

    # Fallback to in-memory
    _IN_MEMORY_STORE[task_id] = doc
    logger.info("a2a_task_created_memory", task_id=task_id, agent=agent)


async def update_task_status(
    task_id: str,
    status: str,
    result: dict[str, Any] | None = None,
) -> None:
    """Update the status and result of an existing task.

    Args:
        task_id: Task identifier to update.
        status: New status string — "running" | "complete" | "failed".
        result: Optional result payload dict.
    """
    update = {
        "status": status,
        "updated_at": time.time(),
        "result": result,
    }

    use_firestore = os.getenv("FIRESTORE_ENABLED", "0") == "1"
    if use_firestore:
        client = _get_firestore_client()
        if client:
            await client.collection("a2a_tasks").document(task_id).update(update)
            logger.info("a2a_task_updated_firestore", task_id=task_id, status=status)
            return

    # Fallback to in-memory
    if task_id in _IN_MEMORY_STORE:
        _IN_MEMORY_STORE[task_id].update(update)
    else:
        _IN_MEMORY_STORE[task_id] = {
            "task_id": task_id,
            **update,
        }
    logger.info("a2a_task_updated_memory", task_id=task_id, status=status)


async def get_task(task_id: str) -> dict[str, Any] | None:
    """Retrieve a task record by task_id.

    Args:
        task_id: Task identifier to look up.

    Returns:
        Task dict or None if not found.
    """
    use_firestore = os.getenv("FIRESTORE_ENABLED", "0") == "1"
    if use_firestore:
        client = _get_firestore_client()
        if client:
            doc_ref = client.collection("a2a_tasks").document(task_id)
            doc = await doc_ref.get()
            if doc.exists:
                return doc.to_dict()
            return None

    # Fallback to in-memory
    return _IN_MEMORY_STORE.get(task_id)


def reset_in_memory_store() -> None:
    """Clear the in-memory store — used only in tests."""
    _IN_MEMORY_STORE.clear()
