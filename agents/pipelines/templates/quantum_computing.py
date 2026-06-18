# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Symposium template — Quantum Computing & Tensor Network Optimization.

Archived configuration for reproducible re-runs of the quantum computing
symposium investigating tensor-network approaches to variational quantum
eigensolvers, QAOA, and holographic quantum error correction.
"""

from __future__ import annotations

from pathlib import Path

from agents.pipelines.symposium import SymposiumConfig


def build_config() -> SymposiumConfig:
    """Build a frozen SymposiumConfig for Quantum Computing research.

    Returns:
        Configuration targeting tensor-network optimization of quantum
        circuits with NIST QC standards and error correction thresholds.
    """
    return SymposiumConfig(
        field="Quantum Computing & Tensor Network Optimization",
        research_question=(
            "Can Alien Mathematics tensor decomposition and holographic codes "
            "reduce the gate complexity of variational quantum eigensolvers "
            "while maintaining fault-tolerance below quantum error correction "
            "thresholds?"
        ),
        formalisms=[
            "tensor networks (MPS, PEPS, MERA)",
            "holographic quantum error-correcting codes",
            "ω-limit quantum circuit families",
            "non-commutative operator algebras on qubit lattices",
        ],
        constraints=[
            "NIST Post-Quantum Cryptography standards (FIPS 203/204/205)",
            "quantum error correction thresholds (surface code d ≥ 17)",
            "decoherence time bounds (T₁, T₂ for superconducting qubits)",
            "circuit depth limits for NISQ-era devices (< 1000 gates)",
        ],
        comparison_baselines=[
            "Variational Quantum Eigensolver (VQE)",
            "Quantum Approximate Optimization Algorithm (QAOA)",
            "Quantum Monte Carlo (QMC)",
            "Density Matrix Renormalization Group (DMRG)",
        ],
        target_pages=100,
        template_name="quantum_computing",
        output_dir=Path("output/symposium/quantum_computing"),
    )
