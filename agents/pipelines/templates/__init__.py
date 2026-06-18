# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Symposium research templates — pre-configured SymposiumConfig factories.

Each template module exports a ``build_config() -> SymposiumConfig`` function
that returns a frozen configuration for a specific research domain.

Usage::

    from agents.pipelines.templates import load_template

    config = load_template("quantum_computing")
"""

from __future__ import annotations

from typing import Callable

from agents.pipelines.symposium import SymposiumConfig

from agents.pipelines.templates.quantum_computing import build_config as _qc
from agents.pipelines.templates.airline_revenue_mgmt import build_config as _arm
from agents.pipelines.templates.airport_operations import build_config as _aop
from agents.pipelines.templates.cycloreactor_environment import build_config as _cre
from agents.pipelines.templates.plasma_fusion_iter import build_config as _pfi

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

TEMPLATE_REGISTRY: dict[str, Callable[[], SymposiumConfig]] = {
    "quantum_computing": _qc,
    "airline_revenue_mgmt": _arm,
    "airport_operations": _aop,
    "cycloreactor_environment": _cre,
    "plasma_fusion_iter": _pfi,
}


def load_template(name: str) -> SymposiumConfig:
    """Load a symposium template by name.

    Args:
        name: Template identifier (must exist in :data:`TEMPLATE_REGISTRY`).

    Returns:
        Frozen :class:`SymposiumConfig` for the requested domain.

    Raises:
        KeyError: If *name* is not a registered template.
    """
    if name not in TEMPLATE_REGISTRY:
        raise KeyError(
            f"Unknown template '{name}'. "
            f"Available: {sorted(TEMPLATE_REGISTRY.keys())}"
        )
    return TEMPLATE_REGISTRY[name]()


__all__ = [
    "TEMPLATE_REGISTRY",
    "load_template",
]
