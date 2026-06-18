#!/usr/bin/env bash
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
# Patent: US-PAT-PEND-2026-0525
#
# Run all tests for SocrateAI Scientific Agora

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "================================================================"
echo "SocrateAI Scientific Agora — Test Suite"
echo "================================================================"

# Activate venv
VENV_DIR="$PROJECT_ROOT/.venv"
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
fi

cd "$PROJECT_ROOT"

# ---------------------------------------------------------------------------
# Python tests
# ---------------------------------------------------------------------------
echo ""
echo "▶ Running Python tests..."

if command -v pytest &>/dev/null; then
    # Run with verbose output and async support
    pytest \
        --tb=short \
        -v \
        --strict-markers \
        -x \
        "${@:-}" \
        2>&1 || {
        echo "  ❌ Python tests failed"
        exit 1
    }
    echo "  ✅ Python tests passed"
else
    echo "  ⚠️  pytest not found. Install: pip install pytest pytest-asyncio"
    # Fallback: basic import tests
    echo "  Running basic import tests..."
    python3 -c "
from agents.common.budget_guard import BudgetGuard, BudgetExceededError
from agents.common.telemetry import AgentTelemetry
from agents.galileo.tools.sundials_solver import sundials_cvode_solver
from agents.galileo.tools.data_integrity import validate_scientific_data_integrity
from agents.galileo.tools.cost_estimator import estimate_cost
from agents.euler.tools.lean4_compiler import compile_lean4_proof
from agents.euler.tools.deepproblog_gate import evaluate_probabilistic_query
from agents.euler.tools.skeptical_auditor import audit_demonstration
print('All imports successful')

# Quick functional tests
guard = BudgetGuard()
assert guard.check_budget(50.0)
guard.record_cost(50.0)
assert guard.experiment_cost == 50.0

result = estimate_cost(gpu_type='L4', hours=1.0, replicas=1)
assert result['within_experiment_budget']
assert result['total_cost'] == 0.70

result = sundials_cvode_solver('robertson', (0.0, 100.0), [1.0, 0.0, 0.0])
assert result['success']

result = audit_demonstration('This is obviously true by inspection.')
assert not result['passed']

print('All functional tests passed ✓')
"
    echo "  ✅ Basic tests passed"
fi

# ---------------------------------------------------------------------------
# Rust tests
# ---------------------------------------------------------------------------
echo ""
echo "▶ Running Rust tests..."
SOLVER_DIR="$PROJECT_ROOT/solvers"
if [ -f "$SOLVER_DIR/Cargo.toml" ]; then
    cd "$SOLVER_DIR"
    cargo test 2>&1 | tail -10
    echo "  ✅ Rust tests passed"
    cd "$PROJECT_ROOT"
else
    echo "  ⚠️  No Cargo.toml — skipping Rust tests"
fi

echo ""
echo "================================================================"
echo "All tests complete!"
echo "================================================================"
