#!/usr/bin/env bash
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
# Patent: US-PAT-PEND-2026-0525
#
# Lint all code: Python (ruff, mypy) and Rust (clippy, fmt)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "================================================================"
echo "SocrateAI Scientific Agora — Linting"
echo "================================================================"

# Activate venv
VENV_DIR="$PROJECT_ROOT/.venv"
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
fi

cd "$PROJECT_ROOT"

EXIT_CODE=0

# ---------------------------------------------------------------------------
# Python: ruff
# ---------------------------------------------------------------------------
echo ""
echo "▶ Python: ruff check..."
if command -v ruff &>/dev/null; then
    ruff check agents/ nvidia/ benchmarks/ examples/ scripts/ \
        --select E,W,F,I,UP,B,SIM,C4 \
        --target-version py311 \
        2>&1 || EXIT_CODE=1

    echo ""
    echo "▶ Python: ruff format check..."
    ruff format --check agents/ nvidia/ benchmarks/ examples/ \
        2>&1 || {
        echo "  ⚠️  Format differences found. Run: ruff format agents/ nvidia/"
        EXIT_CODE=1
    }
else
    echo "  ⚠️  ruff not found. Install: pip install ruff"
fi

# ---------------------------------------------------------------------------
# Python: mypy (type checking)
# ---------------------------------------------------------------------------
echo ""
echo "▶ Python: mypy type check..."
if command -v mypy &>/dev/null; then
    mypy agents/ nvidia/ \
        --python-version 3.11 \
        --ignore-missing-imports \
        --no-strict-optional \
        --warn-return-any \
        --warn-unused-configs \
        2>&1 || {
        echo "  ⚠️  Type errors found"
        EXIT_CODE=1
    }
else
    echo "  ⚠️  mypy not found. Install: pip install mypy"
fi

# ---------------------------------------------------------------------------
# Rust: clippy and fmt
# ---------------------------------------------------------------------------
echo ""
echo "▶ Rust: clippy & fmt..."
SOLVER_DIR="$PROJECT_ROOT/solvers"
if [ -f "$SOLVER_DIR/Cargo.toml" ] && command -v cargo &>/dev/null; then
    cd "$SOLVER_DIR"

    echo "  Running cargo clippy..."
    cargo clippy -- -D warnings 2>&1 | tail -10 || EXIT_CODE=1

    echo "  Running cargo fmt check..."
    cargo fmt -- --check 2>&1 || {
        echo "  ⚠️  Rust format differences. Run: cargo fmt"
        EXIT_CODE=1
    }

    cd "$PROJECT_ROOT"
else
    echo "  ⚠️  Rust not available or no Cargo.toml — skipping"
fi

# ---------------------------------------------------------------------------
# Terraform: fmt
# ---------------------------------------------------------------------------
echo ""
echo "▶ Terraform: fmt check..."
TF_DIR="$PROJECT_ROOT/deploy/terraform"
if command -v terraform &>/dev/null && [ -d "$TF_DIR" ]; then
    terraform fmt -check -recursive "$TF_DIR" 2>/dev/null || {
        echo "  ⚠️  Terraform format differences. Run: terraform fmt -recursive deploy/terraform/"
        EXIT_CODE=1
    }
else
    echo "  ⚠️  Terraform not available — skipping"
fi

echo ""
echo "================================================================"
if [ $EXIT_CODE -eq 0 ]; then
    echo "All linting passed! ✅"
else
    echo "Linting issues found ⚠️  (exit code $EXIT_CODE)"
fi
echo "================================================================"

exit $EXIT_CODE
