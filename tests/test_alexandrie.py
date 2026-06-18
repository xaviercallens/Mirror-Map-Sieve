# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Unit tests for the Alexandrie Storage Hub and FastAPI Backend Server."""

from __future__ import annotations

import base64
import os
import pathlib
import pytest
from fastapi.testclient import TestClient

from alexandrie.hub import AlexandrieHub
from alexandrie.metadata import ArtifactType, RoomType
from alexandrie.server import app, hub


@pytest.fixture
def temp_hub(tmp_path: pathlib.Path) -> AlexandrieHub:
    """Fixture to create a clean temporary hub instance."""
    return AlexandrieHub(vault_root=str(tmp_path))


def test_hub_lifecycle(temp_hub: AlexandrieHub):
    """Test direct Hub storage, retrieval, and search."""
    artifact_id = "test_artifact_01"
    title = "Symmetric Conics Proof"
    payload = "theorem conic_symm (n : Nat) : n = n := by rfl"
    
    # Store
    meta = temp_hub.store_artifact(
        artifact_id=artifact_id,
        title=title,
        content=payload,
        artifact_type=ArtifactType.PROOF,
        room_type=RoomType.OPEN_ACCESS,
        creator="euler_test",
        tags=["math", "proof", "conics"],
    )
    
    assert meta.id == artifact_id
    assert meta.title == title
    assert meta.creator == "euler_test"
    assert meta.tags == ["math", "proof", "conics"]
    
    # Retrieve
    retrieved = temp_hub.retrieve_artifact(artifact_id, RoomType.OPEN_ACCESS)
    assert retrieved is not None
    metadata, content = retrieved
    assert metadata.id == artifact_id
    assert content == payload
    
    # Private isolation check
    assert temp_hub.retrieve_artifact(artifact_id, RoomType.PRIVATE) is None

    # Search
    search_res = temp_hub.search_vault("symmetric")
    assert len(search_res) == 1
    assert search_res[0].id == artifact_id

    # Store binary bytes
    bin_id = "binary_check"
    bin_payload = b"\x00\x01\x02\x03\x04"
    temp_hub.store_artifact(
        artifact_id=bin_id,
        title="Binary Weights",
        content=bin_payload,
        artifact_type=ArtifactType.CHECKPOINT,
        room_type=RoomType.PRIVATE,
        creator="turing_test",
    )
    
    ret_bin = temp_hub.retrieve_artifact(bin_id, RoomType.PRIVATE)
    assert ret_bin is not None
    _, content_bin = ret_bin
    assert content_bin == bin_payload


def test_api_health():
    """Verify FastAPI /health endpoint."""
    with TestClient(app) as client:
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert data["service"] == "Alexandrie Storage Hub"
        assert "min_replicas" in data


def test_api_artifact_lifecycle(tmp_path: pathlib.Path):
    """Verify endpoint ingestion, search, and retrieval workflow."""
    # Temporarily point server's hub to tmp_path
    original_root = hub.root
    hub.__init__(vault_root=str(tmp_path))
    
    try:
        with TestClient(app) as client:
            artifact_id = "nim_adapter_v1"
            payload_text = "base64_encoded_lora_weights"
            
            # Post Ingestion
            body = {
                "id": artifact_id,
                "title": "BioNeMo ESM2 Adapter",
                "payload": payload_text,
                "artifact_type": "checkpoint",
                "room_type": "open_access",
                "creator": "galileo_nim",
                "tags": ["biology", "esm2"],
                "requirements": ["import torch"],
                "metrics": {"loss": 0.045},
                "dependencies": [],
                "extra_attributes": {}
            }
            res_post = client.post("/vault/artifact", json=body)
            assert res_post.status_code == 201
            data_post = res_post.json()
            assert data_post["id"] == artifact_id
            assert data_post["creator"] == "galileo_nim"
            assert data_post["metrics"]["loss"] == 0.045
            
            # Retrieval
            res_get = client.get(f"/vault/artifact/{artifact_id}?room=open_access")
            assert res_get.status_code == 200
            data_get = res_get.json()
            assert data_get["metadata"]["id"] == artifact_id
            assert data_get["payload"] == payload_text
            
            # Bad room retrieval
            res_bad_room = client.get(f"/vault/artifact/{artifact_id}?room=private")
            assert res_bad_room.status_code == 404
            
            # Search
            res_search = client.get("/vault/search?query=esm2")
            assert res_search.status_code == 200
            search_data = res_search.json()
            assert len(search_data) == 1
            assert search_data[0]["id"] == artifact_id
            
            # Search with invalid tags
            res_empty_search = client.get("/vault/search?query=physics")
            assert len(res_empty_search.json()) == 0

    finally:
        hub.__init__(vault_root=str(original_root))


def test_api_astrolabe(tmp_path: pathlib.Path):
    """Verify astrolabe navigation endpoint returns correct alignments."""
    original_root = hub.root
    original_env = os.environ.get("ALEXANDRIE_VAULT_ROOT")
    hub.__init__(vault_root=str(tmp_path))
    os.environ["ALEXANDRIE_VAULT_ROOT"] = str(tmp_path)
    
    try:
        with TestClient(app) as client:
            # Seed artifact 1
            client.post("/vault/artifact", json={
                "id": "proof_conics_01",
                "title": "Algebraic Conic Ellipse",
                "payload": "conic definition",
                "artifact_type": "proof",
                "room_type": "open_access",
                "creator": "galois",
                "tags": ["conics", "ellipse"],
                "requirements": [],
                "metrics": {},
                "dependencies": []
            })
            
            # Seed artifact 2
            client.post("/vault/artifact", json={
                "id": "proof_conics_02",
                "title": "Projective Hyperbola",
                "payload": "hyperbola definition",
                "artifact_type": "proof",
                "room_type": "open_access",
                "creator": "galois",
                "tags": ["conics", "hyperbola"],
                "requirements": [],
                "metrics": {},
                "dependencies": []
            })

            res = client.get("/vault/astrolabe?focus_topic=conics&required_alignment=0.10")
            assert res.status_code == 200
            data = res.json()
            assert "astronomical_zenith" in data
            assert "alignments" in data
            assert len(data["alignments"]) > 0
            assert "astrolabe_suggestions" in data

    finally:
        hub.__init__(vault_root=str(original_root))
        if original_env is not None:
            os.environ["ALEXANDRIE_VAULT_ROOT"] = original_env
        else:
            os.environ.pop("ALEXANDRIE_VAULT_ROOT", None)
