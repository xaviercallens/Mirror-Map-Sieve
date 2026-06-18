#!/usr/bin/env bash
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
# Patent: US-PAT-PEND-2026-0525
#
# Full build pipeline for SocrateAI Scientific Agora

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "================================================================"
echo "SocrateAI Scientific Agora — Build Pipeline"
echo "================================================================"

# Activate venv if available
VENV_DIR="$PROJECT_ROOT/.venv"
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
fi

# ---------------------------------------------------------------------------
# Step 1: Python package checks
# ---------------------------------------------------------------------------
echo ""
echo "▶ Step 1: Python syntax check..."
python3 -m py_compile "$PROJECT_ROOT/agents/__init__.py"
python3 -m py_compile "$PROJECT_ROOT/agents/base.py"
python3 -m py_compile "$PROJECT_ROOT/agents/common/budget_guard.py"
python3 -m py_compile "$PROJECT_ROOT/agents/common/telemetry.py"
python3 -m py_compile "$PROJECT_ROOT/agents/galileo/agent.py"
python3 -m py_compile "$PROJECT_ROOT/agents/euler/agent.py"
python3 -m py_compile "$PROJECT_ROOT/agents/socrates/agent.py"
echo "  ✅ All Python files compile successfully"

# ---------------------------------------------------------------------------
# Step 2: Rust build (rusty-SUNDIALS)
# ---------------------------------------------------------------------------
echo ""
echo "▶ Step 2: Rust build..."
SOLVER_DIR="$PROJECT_ROOT/solvers"
if [ -f "$SOLVER_DIR/Cargo.toml" ]; then
    cd "$SOLVER_DIR"
    cargo build --release 2>&1 | tail -5
    echo "  ✅ Rust solver built"
    cd "$PROJECT_ROOT"
else
    echo "  ⚠️  No Cargo.toml found in solvers/ — skipping Rust build"
fi

# ---------------------------------------------------------------------------
# Step 3: Docker images (optional)
# ---------------------------------------------------------------------------
echo ""
echo "▶ Step 3: Docker images..."
if command -v docker &>/dev/null; then
    echo "  Docker available. Build with:"
    echo "    docker build -f deploy/docker/Dockerfile.agent -t agora-agent ."
    echo "    docker build -f deploy/docker/Dockerfile.solver -t agora-solver ."
else
    echo "  ⚠️  Docker not found — skipping container builds"
fi

# ---------------------------------------------------------------------------
# Step 4: Terraform validation (optional)
# ---------------------------------------------------------------------------
echo ""
echo "▶ Step 4: Terraform validation..."
TF_DIR="$PROJECT_ROOT/deploy/terraform"
if command -v terraform &>/dev/null && [ -f "$TF_DIR/main.tf" ]; then
    cd "$TF_DIR"
    terraform fmt -check -recursive 2>/dev/null || echo "  ⚠️  Format differences found"
    terraform validate 2>/dev/null && echo "  ✅ Terraform valid" || echo "  ⚠️  Terraform validation requires init"
    cd "$PROJECT_ROOT"
else
    echo "  ⚠️  Terraform not available or no config — skipping"
fi

echo ""
echo "================================================================"
echo "Build complete!"
echo "================================================================"
