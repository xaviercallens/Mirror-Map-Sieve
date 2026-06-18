# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Discovery template registry — mirrors agents/pipelines/templates/__init__.py.

Each template is a factory function returning a DiscoveryConfig for a
specific mathematical target.  Adding a new template requires only:
  1. Create agents/pipelines/templates/discovery/<name>.py with build_config()
  2. Register it in DISCOVERY_TEMPLATE_REGISTRY below
"""

from __future__ import annotations

from agents.pipelines.templates.discovery.h1_strassen_witness import (
    build_config as _h1,
)
from agents.pipelines.templates.discovery.h2_stirling_identities import (
    build_config as _h2,
)
from agents.pipelines.templates.discovery.h3_callens_schmidt import (
    build_config as _h3,
)
from agents.pipelines.discovery import DiscoveryConfig

DISCOVERY_TEMPLATE_REGISTRY: dict[str, callable] = {
    # H1: Strassen ⟨2,2,2⟩ witness — validation run, known result
    "h1_strassen_witness": _h1,
    # H2: Stirling Numbers (Second Kind) identities — recurrences & decomposition
    "h2_stirling_identities": _h2,
    # H3: Callens-Schmidt Sequence — Calabi-Yau period diagonal & order-5 minimal recurrence
    "h3_callens_schmidt": _h3,
}



def load_discovery_template(name: str) -> DiscoveryConfig:
    """Load a discovery template by name.

    Args:
        name: Template name (e.g., 'h1_strassen_witness').

    Returns:
        Configured :class:`DiscoveryConfig` ready for pipeline execution.

    Raises:
        KeyError: If the template name is not registered.
    """
    if name not in DISCOVERY_TEMPLATE_REGISTRY:
        raise KeyError(
            f"Unknown discovery template '{name}'. "
            f"Available: {sorted(DISCOVERY_TEMPLATE_REGISTRY)}"
        )
    return DISCOVERY_TEMPLATE_REGISTRY[name]()
