#!/usr/bin/env bash
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
# Patent: US-PAT-PEND-2026-0525
#
# Environment setup for SocrateAI Scientific Agora
# Installs: Python 3.11+, Rust, Lean 4, and Python dependencies

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "================================================================"
echo "SocrateAI Scientific Agora — Environment Setup"
echo "================================================================"

# ---------------------------------------------------------------------------
# Detect OS
# ---------------------------------------------------------------------------
OS="$(uname -s)"
ARCH="$(uname -m)"
echo "Platform: $OS ($ARCH)"

# ---------------------------------------------------------------------------
# Python 3.11+
# ---------------------------------------------------------------------------
echo ""
echo "▶ Checking Python..."
if command -v python3.11 &>/dev/null; then
    PYTHON=python3.11
elif command -v python3 &>/dev/null; then
    PYTHON=python3
    PY_VERSION=$($PYTHON --version 2>&1 | grep -oP '\d+\.\d+')
    echo "  Python version: $PY_VERSION"
else
    echo "  ❌ Python 3.11+ not found. Install from https://python.org"
    exit 1
fi
echo "  ✅ Python: $($PYTHON --version)"

# ---------------------------------------------------------------------------
# Virtual environment
# ---------------------------------------------------------------------------
echo ""
echo "▶ Setting up virtual environment..."
VENV_DIR="$PROJECT_ROOT/.venv"
if [ ! -d "$VENV_DIR" ]; then
    $PYTHON -m venv "$VENV_DIR"
    echo "  Created: $VENV_DIR"
else
    echo "  Exists: $VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

# ---------------------------------------------------------------------------
# Python dependencies
# ---------------------------------------------------------------------------
echo ""
echo "▶ Installing Python dependencies..."
pip install --upgrade pip setuptools wheel -q

pip install -q \
    structlog \
    pydantic \
    httpx \
    pytest \
    pytest-asyncio \
    ruff \
    mypy

echo "  ✅ Python packages installed"

# ---------------------------------------------------------------------------
# Rust (for rusty-SUNDIALS)
# ---------------------------------------------------------------------------
echo ""
echo "▶ Checking Rust..."
if command -v rustc &>/dev/null; then
    echo "  ✅ Rust: $(rustc --version)"
else
    echo "  Installing Rust via rustup..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
    echo "  ✅ Rust installed: $(rustc --version)"
fi

# Ensure clippy and rustfmt
rustup component add clippy rustfmt 2>/dev/null || true

# ---------------------------------------------------------------------------
# Lean 4 (for formal verification)
# ---------------------------------------------------------------------------
echo ""
echo "▶ Checking Lean 4..."
if command -v lean &>/dev/null; then
    echo "  ✅ Lean: $(lean --version 2>&1 | head -1)"
else
    echo "  ⚠️  Lean 4 not found."
    echo "  Install from: https://leanprover.github.io/lean4/doc/setup.html"
    echo "  Or run: curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh"
    echo "  (Skipping — Euler agent will work with limited functionality)"
fi

# ---------------------------------------------------------------------------
# Pre-commit hooks
# ---------------------------------------------------------------------------
echo ""
echo "▶ Setting up pre-commit..."
if command -v pre-commit &>/dev/null; then
    echo "  pre-commit available"
else
    pip install -q pre-commit
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "================================================================"
echo "Setup complete!"
echo "================================================================"
echo ""
echo "To activate the environment:"
echo "  source $VENV_DIR/bin/activate"
echo ""
echo "To build:"
echo "  bash scripts/build.sh"
echo ""
echo "To test:"
echo "  bash scripts/test.sh"
echo ""
echo "To lint:"
echo "  bash scripts/lint.sh"
