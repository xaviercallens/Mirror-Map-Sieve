# Agora Pipeline Handoff Document

This document serves as the formal knowledge transfer from the Alien Mathematics investigation back to the core SocrateAI Agora system.

## New Tools & Methodologies Available

### 1. High-Performance Rust Solver (`discovery/rust_ramsey/`)
- **Capability:** Evaluates Ramsey colorings at up to 21 million steps per second via Simulated Annealing.
- **Key Tech:** Uses bitsets (`u64`) for O(1) adjacency intersection and delta-evaluation (only evaluating cliques involving the flipped edge).
- **Integration:** Can be wrapped by Python scripts and integrated into the `Galileo` (Experimenter) agent's toolset for massive falsification sweeps.

### 2. The `ClaimVerificationPipeline` Architecture
- **Capability:** Automates the 4-gate verification standard (Literature -> Computation -> Lean 4 -> Peer Review).
- **Integration:** Should become a standard master pipeline orchestrating `Socrate`, `Galileo`, and `Euler` agents whenever a heuristic LLM engine (e.g., AlphaEvolve, LeanBert, DeepSeek) proposes a novel theorem.

### 3. `ExactRationalWitness` Formalization (`verifiers/lean4/Agora/AlienMath/ExactRationalWitness.lean`)
- **Capability:** Maps continuous polynomial bounds (like Krawtchouk polynomials on hypercubes) into the exact rational field $\mathbb{Q}$.
- **Integration:** The `Euler` (Verifier) agent can use this template to turn complex analysis optimization problems into decidable inequalities that compile with `native_decide` in Lean 4.

## Recommended Architectural Changes for Agora

1. **Adversarial Latent Space:** When using models like Lean GAN or DeepSeek-Prover, pair them explicitly with an adversarial agent designed solely to falsify their output. Do not pass the output directly to the verifier without passing the computational falsification gate.
2. **"Alien Mathematics" Guardrails:** Implement automatic checks for definitional tautologies. If Lean 4 proves a theorem instantly (`by rfl` or `simp`), flag it for human review—it is likely trivial rather than profound.
