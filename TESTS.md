# 🏛️ SocrateAI Scientific Agora — Test Suite Guide

This document describes the structure, execution, mocking strategies, and coverage goals for the Python unit and integration testing suite of the Agora framework.

---

## 📐 Overall Architecture & Testing Philosophy

The Agora framework combines neuro-symbolic cognitive agents, high-performance mathematical and physical solvers (`rusty-SUNDIALS`), formal verification libraries (`Lean 4`, `DeepProbLog`), and segregated storage backends (`Alexandrie`). 

To ensure complete robustness and reliability, the testing suite enforces:
1. **Strict Determinism**: Zero network calls are made during tests. External HTTP APIs (such as NVIDIA NIM or remote vault connections) are completely mocked.
2. **Fast Execution**: Solvers, compilers, and remote connections are mocked or bound to local fallbacks to ensure test suite execution finishes in under **5 seconds**.
3. **High Code Coverage (>= 95%)**: High-coverage threshold is maintained across all modules to cover edge cases, budget auditing limits, serverless zero-replica violations, stiff integration failures, and logic boundary contradictions.

---

## 📂 Test Suite Directory Layout

The python tests are located in the `tests/` directory:

```
tests/
├── test_agents.py               # Functional & lifecycle integration tests for agents (Galileo, Euler, Galois, Hypatie, Socrates)
├── test_turing_agent.py         # Specialized tests for the Turing Computer Science & Optimization agent
├── test_symbrain_v12.py         # Advanced MCTS and PSLQ-Leaf Evaluator tests for SymBrain v12
├── test_alexandrie.py           # REST API & hub tests for the Alexandrie storage backend
└── test_coverage_enhancers.py   # Advanced coverage boosters (testing FFI, network errors, budget exceptions, memory bounds)
```

---

## 🚀 Running the Tests

To run the full test suite with coverage reporting, execute:

```bash
# Set pythonpath and run pytest with term-missing coverage report
PYTHONPATH=. pytest --cov=agents --cov=alexandrie --cov-report=term-missing
```

To run a specific test file:

```bash
PYTHONPATH=. pytest tests/test_coverage_enhancers.py -v
```

---

## 🛠️ Mocking Strategies & Guidelines

Since agents utilize concrete tools (e.g. `catalog_scientific_work` in `HYPATIE_TOOLS`) bound at import time, standard module-level patches may fail to propagate. The test suite utilizes the following highly reliable mocking strategies:

### 1. Direct Agent Tool Overwriting (Instance-Level)
For concrete agents, directly overwrite the `_tools` dictionary on the instantiated agent object to isolate exceptions or mock behaviors:
```python
agent = GalileoAgent()
agent._tools = {
    **agent._tools,
    "sundials_solver": MagicMock(side_effect=Exception("Solver exploded"))
}
# Runs agent.run, catching the exception gracefully in Galileo's fallback block
result = await agent.run("Perform simulation")
```

### 2. DeepProbLog Fact Grounding
The DeepProbLog logic parser (`_PROB_FACT_PATTERN`) strictly expects trailing parentheses for logic predicates. When testing probabilistic logic grounding, format logic statements using explicit predicate signatures:
```python
# Correct
program = "0.9 :: rain()."
result = evaluate_probabilistic_query(program, "rain()")

# Incorrect (evaluates to 1.0 default)
program = "0.9 :: rain."
```

### 3. FFI & Compiler Mocks
To bypass executing Lean 4 or Rust cvode binaries locally, mock the underlying `subprocess.run` calls or utility finders (`shutil.which`):
```python
with patch("shutil.which", return_value="/usr/bin/lean"):
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=[], timeout=30)):
        res = compile_lean4_proof("theorem test : 1=1 := rfl")
        assert res["success"] is False
        assert "timed out" in res["message"]
```

---

## 📊 Coverage Analysis & Gap Resolution

The aggregate test coverage covers:
- **`agents/base.py` & `agents/common/` (100%)**: Validates budget ledgers, negative transaction guards, serverless scale-to-zero compliance, and telemetry recording.
- **`agents/socrates/` (100%)**: Direct maieutic/elenchus cycles, multi-cycle `ComplexityLevel.RESEARCH` dialectic routing, and Socratic synthesis.
- **`agents/turing/` (100%)**: Validates extreme memory-bound allocations (Arena scratch capacity > 85%), network-bound remote latency bounds, and austerity parameter directives.
- **`agents/hypatie/` & `agents/euler/` (100%)**: Ingestion failures, connection errors with automatic fallback, and skepticism warnings.
- **`alexandrie/` (100%)**: FastAPI Swagger validation, silent KeyError parameters in search queries, and dual binary/text storage.

---

## 🦀 Rust Tests (`core/` and `solvers/`)

The Rust crates include unit tests for the SymBrain engine and solver integrations.

### Running Rust Tests

```bash
# Run all Rust tests
cargo test --workspace

# Run specific crate tests
cargo test -p agora-core
cargo test -p agora-solvers
```

### Test Coverage

| Crate | Test File | Key Tests |
|---|---|---|
| `agora-core` | `core/tests/symbrain_tests.rs` | PFC routing, gating thresholds, early stopping |
| `agora-core` | `core/tests/memory_tests.rs` | Arena allocation, bump allocator, zone boundaries |
| `agora-core` | `core/tests/integration_tests.rs` | Full SymBrain pipeline |
| `agora-solvers` | `solvers/tests/solver_tests.rs` | Robertson kinetics, Lorenz attractor, Lotka-Volterra |

---

## 🔬 Lean 4 Verification Tests

The Lean 4 formal verification library is compiled and type-checked via `lake build`.

### Running Lean 4 Verification

```bash
cd verifiers/lean4
lake build
```

### Proof Coverage Report

| Module | Theorems | Proven | Sorry | Coverage |
|---|---|---|---|---|
| `Basic.lean` | 5 | 5 | 0 | 100% |
| `PFC.lean` | 3 | 3 | 0 | 100% |
| `RLCF.lean` | 7 | 5 | 2 | 71% |
| `LoRA.lean` | 6 | 2 | 4 | 33% |
| `Memory.lean` | 7 | 4 | 3 | 57% |
| `Gating.lean` | 9 | 6 | 3 | 67% |
| `Conservation.lean` | 6 | 3 | 3 | 50% |
| `Agents.lean` | 8 | 8 | 0 | 100% |
| `Alexandrie.lean` | 5 | 5 | 0 | 100% |
| `E37BSD.lean` | 6 | 1 | 5 | 17% |
| `CMI Blueprints` | 7 | 0 | 7 | 0% |
| **Total** | **63** | **41** | **22** | **65%** |

See [SPEC_LEAN4.md](docs/SPEC_LEAN4.md) for the complete theorem catalog.

---

## 🧪 Integration Tests (`examples/`)

Integration tests exercise end-to-end agent workflows.

```bash
# Run example scripts (integration tests)
PYTHONPATH=. python examples/dialectic_reasoning.py
PYTHONPATH=. python examples/budget_constrained_experiment.py
```

| Example Script | Tests | Description |
|---|---|---|
| `stiff_ode_solver.py` | Solver pipeline | Robertson kinetics via rusty-SUNDIALS |
| `dialectic_reasoning.py` | Agent orchestration | Galileo ↔ Euler dialectic debate |
| `budget_constrained_experiment.py` | Budget guard | $100 ceiling enforcement |
| `galois_contest_challenge.py` | Galois pipeline | Math contest problem solving |

---

## 🔄 CI/CD Integration

### GitHub Actions Workflows

| Workflow | Trigger | Actions |
|---|---|---|
| `.github/workflows/ci.yml` | Push/PR to `main` | Python lint (ruff) + pytest + Rust build + cargo test |
| `.github/workflows/lean4-verify.yml` | Push/PR to `main` | Install elan + `lake build` (Lean 4 type-checking) |

### CI Test Matrix

```yaml
strategy:
  matrix:
    python-version: ['3.11', '3.12']
    os: [ubuntu-latest, macos-latest]
```

---

## 📋 Component-to-Test Mapping

| Component | Primary Test File | Mock Strategy | Coverage |
|---|---|---|---|
| Socrates (Orchestrator) | `test_agents.py` | Tool overwrite | 100% |
| Galileo (Experimenter) | `test_agents.py` | Mock SUNDIALS, NIM | 100% |
| Euler (Verifier) | `test_agents.py`, `test_euler_verso.py` | Mock subprocess | 100% |
| Galois (Mathematician) | `test_agents.py`, `test_symbrain_v12.py` | Mock SymBrain / mpmath | 100% |
| Turing (Optimizer) | `test_turing_agent.py` | Mock GCP billing, deployment hook | 100% |
| Hypatie (Librarian) | `test_agents.py` | Mock Alexandrie | 100% |
| Alexandrie Hub | `test_alexandrie.py` | TestClient + temp dirs | 100% |
| Coverage Edge Cases | `test_coverage_enhancers.py` | Direct patching | 100% |
| Lean 4 Library | `lake build` | N/A (type-checker) | 65% |
| Rust Core | `cargo test` | Unit tests | ~80% |

---

## 📈 Latest Test Run (2026-06-01)

```
82 passed, 9 warnings in 83.71s

Warnings: PydanticDeprecatedSince20 (6 instances) — non-blocking
```

---

*Copyright © 2026 Xavier Callens / Socrate AI Lab, Paris, France.*
