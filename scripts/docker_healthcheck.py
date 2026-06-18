"""Docker build-time health check for the Agora Discovery Pipeline.

Imported only during `docker build`. Verifies that the pipeline submodules
can be imported without triggering agents/__init__.py (which eagerly loads
Galileo, Galois, Euler... pulling in ray/lean_dojo/transformers/openai).
"""
import sys

# agents.pipelines.* does NOT trigger agents/__init__.py
from agents.pipelines.discovery import DiscoveryPipeline, DiscoveryConfig
from agents.pipelines.stages.degennes_experimentalist import generate_experimental_conjectures
from agents.pipelines.stages.alexandrie_vault_manager import archive_discovery_run
from agents.pipelines.templates.discovery import load_discovery_template

# Quick config validation
cfg = load_discovery_template("h1_strassen_witness")
assert cfg.num_conjectures >= 1, "Template config invalid"
assert cfg.max_budget_usd <= 30.0, "Budget exceeds cap"

print("OK: Discovery Pipeline imports verified")
print(f"    Template 'h1_strassen_witness' loaded: {cfg.num_conjectures} conjectures, ${cfg.max_budget_usd} budget")
sys.exit(0)
