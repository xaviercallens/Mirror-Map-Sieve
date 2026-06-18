# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Modulus physics-informed neural solver integrations."""

from nvidia.modulus.navier_stokes import solve_navier_stokes
from nvidia.modulus.convergence_checker import check_convergence

__all__ = ["solve_navier_stokes", "check_convergence"]
