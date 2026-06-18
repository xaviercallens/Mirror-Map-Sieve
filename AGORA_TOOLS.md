# Agora Tools Registry

This document serves as a registry of the mathematical, symbolic, logic, and optimization tools used by the SocrateAI Scientific Agora system to conduct automated discoveries, proofs, and analyses.

## Core Proof Assistants & Formalization
- **Lean 4**: The foundational proof assistant used for rigorous formalization of combinatorics, summation identities, and graph theory.
- **LeanBERT / Mathlib AI Tools**: Advanced language model extensions tailored for mathematical proofs in Lean, used for automated proof synthesis and self-correction.

## Optimization & Numerical Solvers
- **CVXPY**: Semidefinite Programming (SDP) solver integration for Delsarte Linear Programming bounds and finding extremal bounds in association schemes (e.g., Grassmann graphs, Hamming graphs).
- **MOSEK / SCS**: Underlying solvers coupled with CVXPY for large-scale convex optimization problems.

## Symbolic Computation & Algebra
- **SymPy**: Core Python library for symbolic mathematics, used to evaluate exact rational polynomial shifts in Sister Celine's algorithm for creative telescoping.
- **SageMath**: Extended algebraic computation suite (used when specialized q-series algebra or intensive multivariate symbolic manipulation is required).

## Probabilistic Logic & Neuro-Symbolic
- **DeepProbLog / ProbLog**: Neural-probabilistic logic programming frameworks. Leveraged for hypothesis generation, probabilistic reasoning over mathematical conjectures, and integrating deep learning with logical constraints.

## High-Performance Solvers
- **Rust Solvers**: High-performance, memory-safe parallel solvers used for massive combinatorial exploration, subgraph isomorphism searches, and heavy graph-theoretic calculations where Python bounds are too restrictive.

## Agents & Pipelines
- **Tesla**: Prototyping and Applied Engineering agent, responsible for numeric validation, specification generation, and executing discovery pipelines.
- **Hypathie**: Librarian/Literature Review agent, leveraging Memory and Dreams architectures to conduct honest novelty checks against known databases (OEIS, arXiv, Mathlib).
