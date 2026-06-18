<![CDATA[# Contributing to SocrateAI Scientific Agora

Thank you for your interest in contributing to the SocrateAI Scientific Agora! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Environment](#development-environment)
- [Code Standards](#code-standards)
- [Commit Conventions](#commit-conventions)
- [Pull Request Process](#pull-request-process)
- [Lean 4 Proof Requirements](#lean-4-proof-requirements)
- [Budget Awareness](#budget-awareness)
- [Issue Reporting](#issue-reporting)
- [License](#license)

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to callensxavier@gmail.com.

## Getting Started

1. **Fork** the repository on GitHub
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/<your-username>/SocrateAI-Scientific-Agora.git
   cd SocrateAI-Scientific-Agora
   ```
3. **Add upstream** remote:
   ```bash
   git remote add upstream https://github.com/xaviercallens/SocrateAI-Scientific-Agora.git
   ```
4. **Create a branch** for your work:
   ```bash
   git checkout -b feat/your-feature-name
   ```

## Development Environment

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Rust | ≥ 1.85 (2024 edition) | Core engine, solvers, RunuX kernel |
| Python | ≥ 3.11 | Agents, orchestration, NIM integration |
| Lean 4 | Latest (via elan) | Formal verification of mathematical proofs |
| Docker | Latest | Containerized builds and deployment |

### Setup

```bash
# Install Rust toolchain
rustup default stable
rustup component add clippy rustfmt

# Install Python dependencies
pip install -e '.[dev]'

# Install Lean 4 via elan
curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh

# Verify setup
make build
make test
make verify
```

## Code Standards

### Rust

- **Edition**: 2024
- **Formatting**: `cargo fmt` (enforced in CI)
- **Linting**: `cargo clippy -- -D warnings` (zero warnings policy)
- **Documentation**: All public items must have `///` doc comments
- **Testing**: Unit tests in the same file, integration tests in `tests/`
- **Safety**: No `unsafe` blocks without a `// SAFETY:` comment explaining the invariant
- **Error handling**: Use `thiserror` for library errors, `anyhow` for application errors

```rust
// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// SPDX-License-Identifier: Apache-2.0

/// Solves a stiff ODE system using the CVODE integrator.
///
/// # Arguments
///
/// * `system` - The ODE system to solve
/// * `t_span` - Time interval [t0, tf]
/// * `y0` - Initial state vector
///
/// # Errors
///
/// Returns `SolverError::Convergence` if the solver fails to converge
/// within the specified tolerance.
pub fn solve_ivp(
    system: &dyn OdeSystem,
    t_span: (f64, f64),
    y0: &[f64],
) -> Result<Solution, SolverError> {
    // implementation
}
```

### Python

- **Formatter**: `ruff format` (enforced in CI)
- **Linter**: `ruff check` (zero warnings policy)
- **Type checking**: `mypy --strict` on all agent code
- **Docstrings**: Google-style docstrings on all public functions and classes
- **Testing**: `pytest` with `>=90%` coverage on agent logic

```python
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# SPDX-License-Identifier: Apache-2.0

"""Galileo Agent: Scientific experimenter for the Agora."""

from __future__ import annotations

from typing import Final

MAX_EXPERIMENT_BUDGET: Final[float] = 100.0  # USD


def run_experiment(
    hypothesis: str,
    *,
    budget_limit: float = MAX_EXPERIMENT_BUDGET,
    dry_run: bool = False,
) -> ExperimentResult:
    """Execute a scientific experiment within budget constraints.

    Args:
        hypothesis: The scientific hypothesis to test.
        budget_limit: Maximum allowed spend in USD.
        dry_run: If True, simulate without incurring costs.

    Returns:
        The experiment result with evidence and cost breakdown.

    Raises:
        BudgetExceededError: If the experiment would exceed the budget.
    """
    ...
```

### Lean 4

- All mathematical claims in agent output **must** have corresponding Lean 4 proofs
- Proofs must be in `verifiers/lean4/`
- Use `lake build` to verify all proofs compile
- Prefer `simp`, `omega`, and `decide` tactics where applicable
- Document proof strategies with comments

```lean
-- Copyright (c) 2026 Xavier Callens / Socrate AI Lab
-- SPDX-License-Identifier: Apache-2.0

/-- The sum of the first n natural numbers equals n*(n+1)/2. -/
theorem sum_naturals (n : Nat) :
    2 * (Finset.range (n + 1)).sum id = n * (n + 1) := by
  induction n with
  | zero => simp
  | succ n ih =>
    simp [Finset.sum_range_succ]
    omega
```

## Commit Conventions

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Types

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, no logic change |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `perf` | Performance improvement |
| `test` | Adding or correcting tests |
| `build` | Build system or external dependencies |
| `ci` | CI configuration |
| `chore` | Maintenance tasks |
| `proof` | New or updated Lean 4 proof |
| `solver` | Changes to rusty-SUNDIALS solvers |
| `agent` | Changes to AGY SDK agents |

### Scopes

`symbrain`, `galileo`, `euler`, `socrates`, `sundials`, `runux`, `nim`, `lean4`, `deepproblog`, `ci`, `docs`

### Examples

```
feat(galileo): add NVIDIA BioNeMo protein folding tool

proof(lean4): verify convergence bound for CVODE integrator

fix(sundials): correct Jacobian computation for stiff DAE systems

agent(socrates): implement dialectical synthesis with 3-round consensus

perf(symbrain): reduce PFC router latency by 40% via batch dispatch
```

## Pull Request Process

1. **Ensure all checks pass** before submitting:
   ```bash
   make lint       # Rust clippy + Python ruff
   make test       # Full test suite
   make verify     # Lean 4 proofs
   ```

2. **Fill out the PR template** completely, including:
   - Clear description of changes
   - Testing performed
   - Lean 4 proof status (if applicable)
   - Budget impact assessment

3. **Keep PRs focused**: One logical change per PR. Split large changes into a stack of smaller PRs.

4. **Review process**:
   - All PRs require at least one approval from `@xaviercallens`
   - CI must pass (Rust build, Python tests, Lean 4 verification)
   - No decrease in test coverage

5. **Merge strategy**: Squash-and-merge for feature branches, rebase for release branches.

## Lean 4 Proof Requirements

Any PR that introduces or modifies mathematical claims **must** include:

1. **Formal statement** in Lean 4 matching the claim
2. **Complete proof** that compiles with `lake build`
3. **Documentation** explaining the proof strategy
4. **Connection** to the agent code that produces or relies on the claim

### When proofs are required

- New solver algorithms or convergence guarantees
- Mathematical optimizations in SymBrain routing
- Benchmark claims or bounds
- Any theorem referenced in agent output

### When proofs are optional

- Empirical benchmarks (tested, not proved)
- Infrastructure and CI changes
- Documentation updates
- UI/UX changes

## Budget Awareness

The Agora operates under strict frugal-AI constraints:

- **$100 per experiment** maximum
- **$500 total budget** across all experiments
- **`min_replicas=0`** for all serverless deployments

When contributing:

- Always set `min_replicas=0` in deployment configurations
- Include cost estimates for any new NIM model integrations
- Test with the smallest viable model before scaling up
- Document expected costs in PR descriptions

## Issue Reporting

- **Bugs**: Use the [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.md)
- **Features**: Use the [Feature Request template](.github/ISSUE_TEMPLATE/feature_request.md)
- **Experiments**: Use the [Experiment Proposal template](.github/ISSUE_TEMPLATE/experiment_proposal.md)
- **Security**: See [SECURITY.md](SECURITY.md) for responsible disclosure

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE). Proprietary components (model weights, trained adapters) remain under [CC BY-NC-ND 4.0](LICENSE-COMMERCIAL).

---

*Copyright © 2026 Xavier Callens / Socrate AI Lab, Paris, France.*
]]>
