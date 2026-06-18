# Agora — Lean 4 Formal Verification Library

> **SocrateAI Scientific Agora**
> Copyright © 2025-2026 Socrate AI Lab, Paris, France
> Author: Xavier Callens · Patent US-PAT-PEND-2026-0525

Machine-checked proofs for the core mathematical invariants of the
SymBrain cognitive engine, RunuX memory arena, and scientific-agent
pipeline. Every theorem statement is precise; proofs that require deep
Mathlib lemmas carry `sorry` stubs with adjacent proof sketches.

---

## Quick Start

```bash
# Prerequisites: elan (Lean version manager)
curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | sh

# Build the library
cd verifiers/lean4
lake update          # fetch Mathlib + dependencies
lake build           # type-check all modules
```

The first build fetches Mathlib (~20 min, cached thereafter).

## Module Index

| Module | File | Description |
|--------|------|-------------|
| `Agora.Basic` | [Agora/Basic.lean](Agora/Basic.lean) | Core types: `WeightMatrix`, `LoRAConfig`, `ArenaConfig`, `MemoryZone`, `ComplexityScore`, `BudgetLimit` |
| `Agora.PFC` | [Agora/PFC.lean](Agora/PFC.lean) | PFC gating axioms (C²-smoothness, homeostatic stability, Lipschitz), deductive-floor elimination |
| `Agora.RLCF` | [Agora/RLCF.lean](Agora/RLCF.lean) | RLCF stochastic update rule, monotone descent under L-smoothness, Lyapunov stability, Lévy α ∈ [1.7, 1.9] |
| `Agora.LoRA` | [Agora/LoRA.lean](Agora/LoRA.lean) | Low-rank adaptation norm bounds, gradient bounds for A and B factors |
| `Agora.Memory` | [Agora/Memory.lean](Agora/Memory.lean) | Arena memory safety, zone non-overlap, allocation invariant preservation |
| `Agora.Gating` | [Agora/Gating.lean](Agora/Gating.lean) | Dynamic gating monotonicity, boundedness, sigmoid correctness |
| `Agora.Conservation` | [Agora/Conservation.lean](Agora/Conservation.lean) | Physical conservation laws (mass, energy, charge), boundary-condition well-formedness |

## Theorem Index

### PFC (Prefrontal Cortex Router)

| ID | Statement | Status |
|----|-----------|--------|
| `PFC_GatingFunction.axiom_smooth` | G is C² (ContDiff ℝ 2) | Axiom |
| `PFC_GatingFunction.axiom_homeostatic` | ‖G(d,g)‖_F ≤ C / (1 + ‖∇L‖_F²) | Axiom |
| `PFC_GatingFunction.axiom_lipschitz` | LipschitzWith K G | Axiom |
| `deductive_floor_elimination` | σ_ded ≥ 0.30 → deductive path selected | `sorry` (sketch) |

### RLCF (Reinforcement Learning with Continuous Feedback)

| ID | Statement | Status |
|----|-----------|--------|
| `rlcf_monotone_descent` | L(W_{t+1}) ≤ L(W_t) − (η/2)‖∇L‖² under L-smooth | `sorry` (sketch) |
| `rlcf_lyapunov_decrease` | V(t+1) ≤ V(t) under bounded noise | `sorry` (sketch) |

### LoRA (Low-Rank Adaptation)

| ID | Statement | Status |
|----|-----------|--------|
| `lora_norm_bound` | ‖ΔW‖ ≤ \|α/r\| · ‖B‖ · ‖A‖ | `sorry` (sketch) |
| `lora_gradient_bound_A` | ‖∂L/∂A‖ ≤ (α/r) · ‖B‖ · ‖∂L/∂Y‖ | `sorry` (sketch) |
| `lora_gradient_bound_B` | ‖∂L/∂B‖ ≤ (α/r) · ‖A‖ · ‖∂L/∂Y‖ | `sorry` (sketch) |

### Memory Arena

| ID | Statement | Status |
|----|-----------|--------|
| `arena_boundary_safety` | Σ zone.allocated ≤ arena.capacity | `sorry` (sketch) |
| `allocation_preserves_invariant` | valid(arena) → valid(allocate(arena, zone, n)) | `sorry` (sketch) |
| `zone_non_overlap` | disjoint zone address ranges | `sorry` (sketch) |

### Dynamic Gating

| ID | Statement | Status |
|----|-----------|--------|
| `gating_monotone` | C₁ ≤ C₂ → f(C₁) ≤ f(C₂) | Proved |
| `gating_bounded` | 0 ≤ f(C) ≤ 1 | `sorry` (sketch) |
| `sigmoid_self_inverse` | σ(σ⁻¹(x)) = x | `sorry` (sketch) |

### Conservation Laws

| ID | Statement | Status |
|----|-----------|--------|
| `mass_conservation` | ∫ ρ dV = const over time | `sorry` (sketch) |
| `energy_conservation` | dE/dt = −∮ F·n dS | `sorry` (sketch) |
| `charge_conservation` | ∂ρ/∂t + ∇·J = 0 | `sorry` (sketch) |

## Architecture

The Euler Agent (AGY SDK) invokes `lake build` in CI to type-check
all theorem statements. When a `sorry` is replaced by a full proof,
the CI pipeline upgrades the theorem's trust level from `sketch` to
`verified`. The Socrates Agent references trust levels during
dialectical evaluation of scientific claims.

## References

- [Mathlib4](https://github.com/leanprover-community/mathlib4)
- [Lean 4 Manual](https://lean-lang.org/lean4/doc/)
- Callens, X. (2026). *SymBrain: Biomimetic Cognitive Engine*. Socrate AI Lab Technical Report.
- US Patent Application US-PAT-PEND-2026-0525.

## License

Framework code: Apache-2.0 · Proprietary methods: CC-BY-NC-ND 4.0
