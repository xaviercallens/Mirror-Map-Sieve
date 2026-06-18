import pytest
from fastapi.testclient import TestClient
from deploy.gcp_prover_endpoint import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_prove_matched_solution():
    req_data = {
        "theorem_header": "theorem imo2024sl_A1_stuff",
        "initial_proof_stub": "by sorry",
        "imports": [],
        "model_name": "AI-MO/NuminaMath-7B-CoT",
        "max_tactic_depth": 5
    }
    response = client.post("/prove", json=req_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert data["lean_verified"] is True
    assert "imo2024sl_A1" in data["final_proof"]
    assert len(data["suggestions"]) == 3

def test_prove_fallback():
    req_data = {
        "theorem_header": "theorem some_random_theorem",
        "initial_proof_stub": "by sorry",
        "imports": [],
        "model_name": "AI-MO/NuminaMath-7B-CoT",
        "max_tactic_depth": 5
    }
    response = client.post("/prove", json=req_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert data["lean_verified"] is False
    assert "intro n" in data["final_proof"]
    assert len(data["suggestions"]) == 2
